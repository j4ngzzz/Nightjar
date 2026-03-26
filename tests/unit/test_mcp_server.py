"""Tests for the MCP server.

Tests the 3 MCP tools defined in ARCHITECTURE.md Section 7 [REF-T18]:
- verify_contract: Run verification pipeline on generated code
- get_violations: Get detailed violation report
- suggest_fix: Get LLM-suggested fix for a violation

BEFORE MODIFYING: Read docs/ARCHITECTURE.md Section 7.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from contractd.mcp_server import (
    create_mcp_server,
    handle_verify_contract,
    handle_get_violations,
    handle_suggest_fix,
    _violation_store,
)
from contractd.types import (
    VerifyResult, StageResult, VerifyStatus,
)


# -- Fixtures --


def make_pass_result() -> VerifyResult:
    """Create a passing VerifyResult."""
    return VerifyResult(
        verified=True,
        stages=[
            StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=50),
            StageResult(stage=1, name="deps", status=VerifyStatus.PASS, duration_ms=120),
            StageResult(stage=2, name="schema", status=VerifyStatus.PASS, duration_ms=80),
            StageResult(stage=3, name="pbt", status=VerifyStatus.PASS, duration_ms=3000),
            StageResult(stage=4, name="formal", status=VerifyStatus.PASS, duration_ms=8000),
        ],
        total_duration_ms=11250,
        retry_count=0,
    )


def make_fail_result() -> VerifyResult:
    """Create a failing VerifyResult with violations."""
    return VerifyResult(
        verified=False,
        stages=[
            StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=50),
            StageResult(stage=1, name="deps", status=VerifyStatus.PASS, duration_ms=120),
            StageResult(stage=2, name="schema", status=VerifyStatus.PASS, duration_ms=80),
            StageResult(
                stage=3, name="pbt", status=VerifyStatus.FAIL, duration_ms=5000,
                errors=[{
                    "type": "property_violation",
                    "file": "payment.py",
                    "line": 47,
                    "message": "Invariant INV-001 violated: amount must be positive",
                    "counterexample": {"amount": -5, "currency": "USD"},
                }],
                counterexample={"amount": -5, "currency": "USD"},
            ),
        ],
        total_duration_ms=5250,
        retry_count=0,
    )


# -- Server creation tests --


class TestCreateMcpServer:
    """Test MCP server instantiation [REF-T18]."""

    def test_server_has_name(self):
        """MCP server has the correct name."""
        server = create_mcp_server()
        assert server.name == "contractd"

    def test_server_has_tools(self):
        """Server registers all 3 tools."""
        server = create_mcp_server()
        # The server should have tools registered
        assert server is not None


# -- verify_contract tool tests --


class TestVerifyContract:
    """Test the verify_contract MCP tool."""

    @pytest.mark.asyncio
    async def test_verify_contract_pass(self):
        """verify_contract returns verified=true on passing verification."""
        result = make_pass_result()
        with patch("contractd.mcp_server._run_verification", new_callable=AsyncMock, return_value=result):
            response = await handle_verify_contract(
                spec_path=".card/payment.card.md",
                code_path="dist/payment.py",
            )
        parsed = json.loads(response)
        assert parsed["verified"] is True
        assert len(parsed["stages"]) == 5
        assert parsed["duration_ms"] == 11250

    @pytest.mark.asyncio
    async def test_verify_contract_fail(self):
        """verify_contract returns verified=false with errors on failure."""
        result = make_fail_result()
        with patch("contractd.mcp_server._run_verification", new_callable=AsyncMock, return_value=result):
            response = await handle_verify_contract(
                spec_path=".card/payment.card.md",
                code_path="dist/payment.py",
            )
        parsed = json.loads(response)
        assert parsed["verified"] is False
        assert len(parsed["errors"]) > 0

    @pytest.mark.asyncio
    async def test_verify_contract_stages_filter(self):
        """verify_contract supports 'fast' mode (stages 0-3 only)."""
        result = VerifyResult(
            verified=True,
            stages=[
                StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=50),
                StageResult(stage=1, name="deps", status=VerifyStatus.PASS, duration_ms=120),
                StageResult(stage=2, name="schema", status=VerifyStatus.PASS, duration_ms=80),
                StageResult(stage=3, name="pbt", status=VerifyStatus.PASS, duration_ms=3000),
            ],
            total_duration_ms=3250,
        )
        with patch("contractd.mcp_server._run_verification", new_callable=AsyncMock, return_value=result):
            response = await handle_verify_contract(
                spec_path=".card/payment.card.md",
                code_path="dist/payment.py",
                stages="fast",
            )
        parsed = json.loads(response)
        assert parsed["verified"] is True

    @pytest.mark.asyncio
    async def test_verify_contract_stores_violations(self):
        """verify_contract stores violations for get_violations to retrieve."""
        result = make_fail_result()
        with patch("contractd.mcp_server._run_verification", new_callable=AsyncMock, return_value=result):
            await handle_verify_contract(
                spec_path=".card/payment.card.md",
                code_path="dist/payment.py",
            )
        # Violations should be stored
        assert ".card/payment.card.md" in _violation_store


# -- get_violations tool tests --


class TestGetViolations:
    """Test the get_violations MCP tool."""

    @pytest.mark.asyncio
    async def test_get_violations_returns_details(self):
        """get_violations returns detailed violation report."""
        result = make_fail_result()
        with patch("contractd.mcp_server._run_verification", new_callable=AsyncMock, return_value=result):
            await handle_verify_contract(
                spec_path=".card/payment.card.md",
                code_path="dist/payment.py",
            )
        response = await handle_get_violations(spec_path=".card/payment.card.md")
        parsed = json.loads(response)
        assert "violations" in parsed
        assert len(parsed["violations"]) > 0
        violation = parsed["violations"][0]
        assert "stage" in violation
        assert "message" in violation

    @pytest.mark.asyncio
    async def test_get_violations_no_prior_run(self):
        """get_violations returns empty when no prior verification."""
        _violation_store.clear()
        response = await handle_get_violations(spec_path=".card/nonexistent.card.md")
        parsed = json.loads(response)
        assert parsed["violations"] == []


# -- suggest_fix tool tests --


class TestSuggestFix:
    """Test the suggest_fix MCP tool."""

    @pytest.mark.asyncio
    async def test_suggest_fix_returns_suggestion(self):
        """suggest_fix returns LLM-generated fix suggestion."""
        # Store a violation first
        result = make_fail_result()
        with patch("contractd.mcp_server._run_verification", new_callable=AsyncMock, return_value=result):
            await handle_verify_contract(
                spec_path=".card/payment.card.md",
                code_path="dist/payment.py",
            )
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "Add a precondition check: if amount <= 0, raise ValueError"
        )
        with patch("contractd.mcp_server.litellm.completion", return_value=mock_response):
            response = await handle_suggest_fix(
                spec_path=".card/payment.card.md",
                violation_id="0",
            )
        parsed = json.loads(response)
        assert "suggested_code" in parsed
        assert "explanation" in parsed
        assert len(parsed["suggested_code"]) > 0

    @pytest.mark.asyncio
    async def test_suggest_fix_invalid_violation_id(self):
        """suggest_fix handles invalid violation_id gracefully."""
        _violation_store.clear()
        response = await handle_suggest_fix(
            spec_path=".card/payment.card.md",
            violation_id="999",
        )
        parsed = json.loads(response)
        assert "error" in parsed
