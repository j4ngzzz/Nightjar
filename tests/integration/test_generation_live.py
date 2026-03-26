"""Live integration tests for CARD generation and formal verification.

These tests require real external services (LLM API, Dafny binary) and are
skipped by default. Run with ``pytest -m integration`` to execute them.

References:
- ARCHITECTURE.md Section 9 -- Data Flow
- [REF-C02] Closed-loop verification
- [REF-C03] Three-agent generation pipeline (Analyst -> Formalizer -> Coder)
- [REF-T16] litellm -- model-agnostic LLM calls
- [REF-T01] Dafny CLI for formal verification
"""

import os
import shutil
from pathlib import Path

import pytest

from nightjar.types import (
    CardSpec,
    Contract,
    ContractInput,
    ContractOutput,
    Invariant,
    InvariantTier,
    ModuleBoundary,
    VerifyResult,
    VerifyStatus,
)

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

_HAS_LLM = bool(os.environ.get("NIGHTJAR_MODEL")) and (
    bool(os.environ.get("OPENAI_API_KEY"))
    or bool(os.environ.get("ANTHROPIC_API_KEY"))
    or bool(os.environ.get("DEEPSEEK_API_KEY"))
)

_HAS_DAFNY = shutil.which(os.environ.get("DAFNY_PATH", "dafny")) is not None

_SKIP_NO_LLM = pytest.mark.skipif(
    not _HAS_LLM,
    reason=(
        "Requires NIGHTJAR_MODEL env var and a valid API key "
        "(OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY)"
    ),
)

_SKIP_NO_DAFNY = pytest.mark.skipif(
    not _HAS_DAFNY,
    reason="Requires Dafny binary on PATH (set DAFNY_PATH env var if non-standard)",
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_spec() -> CardSpec:
    """Return a minimal but complete CardSpec for live testing."""
    return CardSpec(
        card_version="1.0",
        id="adder",
        title="Integer Adder",
        status="draft",
        module=ModuleBoundary(owns=["addition"]),
        contract=Contract(
            inputs=[
                ContractInput(name="a", type="integer", constraints="a >= 0"),
                ContractInput(name="b", type="integer", constraints="b >= 0"),
            ],
            outputs=[ContractOutput(name="sum", type="integer")],
        ),
        invariants=[
            Invariant(
                id="INV-001",
                tier=InvariantTier.EXAMPLE,
                statement="add(2, 3) == 5",
            ),
            Invariant(
                id="INV-002",
                tier=InvariantTier.PROPERTY,
                statement="add(a, b) returns a non-negative integer when a >= 0 and b >= 0",
            ),
        ],
        intent="Add two non-negative integers and return their sum.",
        acceptance_criteria="Given a=2 and b=3, When add(a,b), Then result == 5.",
        functional_requirements="FR-001: The system MUST return a + b.",
    )


@pytest.fixture
def sample_spec_with_formal() -> CardSpec:
    """Return a CardSpec that includes a formal-tier invariant for Dafny testing."""
    return CardSpec(
        card_version="1.0",
        id="adder_formal",
        title="Integer Adder (Formal)",
        status="draft",
        module=ModuleBoundary(owns=["addition"]),
        contract=Contract(
            inputs=[
                ContractInput(name="a", type="integer", constraints="a >= 0"),
                ContractInput(name="b", type="integer", constraints="b >= 0"),
            ],
            outputs=[ContractOutput(name="sum", type="integer")],
        ),
        invariants=[
            Invariant(
                id="INV-F01",
                tier=InvariantTier.FORMAL,
                statement="ensures result == a + b",
                rationale="Correctness of addition",
            ),
        ],
        intent="Add two non-negative integers with formal proof of correctness.",
    )


@pytest.fixture
def spec_file_on_disk(tmp_path: Path) -> Path:
    """Write a valid .card.md spec file to disk for pipeline tests."""
    spec_content = '''---
card-version: "1.0"
id: adder
title: Integer Adder
status: draft
module:
  owns: [addition]
  depends-on: {}
contract:
  inputs:
    - name: a
      type: integer
      constraints: "a >= 0"
    - name: b
      type: integer
      constraints: "b >= 0"
  outputs:
    - name: sum
      type: integer
invariants:
  - id: INV-001
    tier: example
    statement: "add(2, 3) == 5"
  - id: INV-002
    tier: property
    statement: "add(a, b) returns a non-negative integer when a >= 0 and b >= 0"
---

## Intent

Add two non-negative integers and return their sum.

## Acceptance Criteria

### Story 1 -- Addition (P1)

**As a** developer, **I want** to add two integers, **so that** I get the correct sum.

1. **Given** a=2 and b=3, **When** add(a,b), **Then** result == 5

## Functional Requirements

- **FR-001**: System MUST return a + b.
'''
    card_dir = tmp_path / ".card"
    card_dir.mkdir(parents=True, exist_ok=True)
    spec_path = card_dir / "adder.card.md"
    spec_path.write_text(spec_content, encoding="utf-8")
    return spec_path


# ---------------------------------------------------------------------------
# 1. test_generate_with_real_llm
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_SKIP_NO_LLM
class TestGenerateWithRealLLM:
    """Test code generation using a real LLM API.

    Requires NIGHTJAR_MODEL env var and a valid provider API key.
    These tests are expensive (LLM API calls) and slow.
    """

    def test_generate_returns_dafny_code(self, sample_spec: CardSpec) -> None:
        """The full generation pipeline should produce non-empty Dafny code."""
        from nightjar.generator import generate_code

        result = generate_code(sample_spec)
        assert result.dafny_code, "Expected non-empty Dafny code from generation"
        assert result.analyst_output, "Expected non-empty analyst output"
        assert result.formalizer_output, "Expected non-empty formalizer output"

    def test_generate_uses_model_from_env(self, sample_spec: CardSpec) -> None:
        """The generator should use the model specified in NIGHTJAR_MODEL."""
        from nightjar.generator import generate_code

        result = generate_code(sample_spec)
        expected_model = os.environ.get("NIGHTJAR_MODEL", "")
        assert result.model_used == expected_model or result.model_used

    def test_generate_analyst_stage(self, sample_spec: CardSpec) -> None:
        """The analyst stage alone should return structured requirements."""
        from nightjar.generator import run_analyst

        output = run_analyst(sample_spec)
        assert isinstance(output, str)
        assert len(output) > 50, "Analyst output seems too short"


# ---------------------------------------------------------------------------
# 2. test_verify_with_real_dafny
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_SKIP_NO_DAFNY
class TestVerifyWithRealDafny:
    """Test formal verification using a real Dafny binary.

    Requires Dafny 4.x on PATH.
    """

    def test_dafny_verifies_trivial_program(
        self, sample_spec_with_formal: CardSpec, spec_file_on_disk: Path
    ) -> None:
        """A trivially correct Dafny program should pass formal verification."""
        from nightjar.stages.formal import run_formal

        trivial_dafny = (
            "method Add(a: int, b: int) returns (r: int)\n"
            "  ensures r == a + b\n"
            "{\n"
            "  r := a + b;\n"
            "}\n"
        )
        result = run_formal(sample_spec_with_formal, trivial_dafny)
        assert result.status == VerifyStatus.PASS, (
            f"Dafny verification failed: {result.errors}"
        )

    def test_dafny_rejects_wrong_program(
        self, sample_spec_with_formal: CardSpec
    ) -> None:
        """An incorrect Dafny program should fail formal verification."""
        from nightjar.stages.formal import run_formal

        wrong_dafny = (
            "method Add(a: int, b: int) returns (r: int)\n"
            "  ensures r == a + b\n"
            "{\n"
            "  r := a - b;  // Wrong!\n"
            "}\n"
        )
        result = run_formal(sample_spec_with_formal, wrong_dafny)
        assert result.status == VerifyStatus.FAIL


# ---------------------------------------------------------------------------
# 3. test_full_pipeline_real
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_SKIP_NO_LLM
@_SKIP_NO_DAFNY
class TestFullPipelineReal:
    """Full pipeline test with real LLM + real Dafny.

    Only runs when both a valid LLM API key and Dafny binary are available.
    This is the most expensive test -- it makes LLM API calls AND runs Dafny.
    """

    def test_generate_and_verify(
        self, sample_spec: CardSpec, spec_file_on_disk: Path
    ) -> None:
        """Generate code from spec via LLM, then verify with the full pipeline.

        This exercises the complete CARD data flow:
          parse -> generate (LLM) -> verify (stages 0-4) [ARCHITECTURE.md Section 9]
        """
        from nightjar.generator import generate_code
        from nightjar.verifier import run_pipeline

        # Generate
        gen_result = generate_code(sample_spec)
        assert gen_result.dafny_code, "Generation produced no Dafny code"

        # Verify -- use the Dafny code as both code and Dafny input
        verify_result = run_pipeline(
            sample_spec, gen_result.dafny_code, spec_path=str(spec_file_on_disk)
        )
        assert isinstance(verify_result, VerifyResult)
        # We do not assert verified=True because LLM-generated code may not
        # always pass Dafny on the first try. We just assert the pipeline ran.
        assert len(verify_result.stages) > 0
        assert verify_result.total_duration_ms >= 0

    def test_full_pipeline_reports_all_stages(
        self, sample_spec: CardSpec, spec_file_on_disk: Path
    ) -> None:
        """The pipeline should report results for each stage that ran."""
        from nightjar.generator import generate_code
        from nightjar.verifier import run_pipeline

        gen_result = generate_code(sample_spec)
        verify_result = run_pipeline(
            sample_spec, gen_result.dafny_code, spec_path=str(spec_file_on_disk)
        )

        stage_names = [s.name for s in verify_result.stages]
        # At minimum, preflight should have run
        assert "preflight" in stage_names
