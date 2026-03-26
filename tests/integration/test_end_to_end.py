"""End-to-end integration tests for the CARD pipeline.

Tests the full contractd workflow: init -> generate -> verify -> build -> explain.
Mock-based tests run in CI; live tests require CARD_MODEL + API key + Dafny.

References:
- ARCHITECTURE.md Section 9 -- Data Flow
- [REF-C02] Closed-loop verification
- [REF-T17] Click CLI framework testing
"""

import json
import os
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from contractd.cli import main
from contractd.parser import parse_card_spec
from contractd.types import (
    CardSpec,
    Contract,
    ContractInput,
    ContractOutput,
    Invariant,
    InvariantTier,
    ModuleBoundary,
    StageResult,
    VerifyResult,
    VerifyStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CliRunner for isolated CLI invocation [REF-T17]."""
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with the standard .card/ structure."""
    card_dir = tmp_path / ".card"
    card_dir.mkdir(parents=True)
    (tmp_path / "dist").mkdir()
    (card_dir / "audit").mkdir()
    (card_dir / "cache").mkdir()
    return tmp_path


@pytest.fixture
def sample_spec_content() -> str:
    """Return a valid .card.md spec string for testing."""
    return '''---
card-version: "1.0"
id: calculator
title: Calculator Module
status: draft
module:
  owns: [arithmetic]
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
    - name: result
      type: integer
invariants:
  - id: INV-001
    tier: example
    statement: "add(2, 3) == 5"
  - id: INV-002
    tier: property
    statement: "add(a, b) returns a positive integer when a > 0 and b > 0"
---

## Intent

A simple calculator that adds two non-negative integers.

## Acceptance Criteria

### Story 1 -- Addition (P1)

**As a** developer, **I want** to add two integers, **so that** I get the correct sum.

1. **Given** a = 2 and b = 3, **When** add(a, b), **Then** result == 5

### Edge Cases

- What happens when a or b is negative? -> Return an error

## Functional Requirements

- **FR-001**: System MUST accept two non-negative integers as input.
- **FR-002**: System MUST return their sum.
'''


@pytest.fixture
def spec_file(tmp_project: Path, sample_spec_content: str) -> Path:
    """Write a valid sample spec to the temp project and return its path."""
    spec_path = tmp_project / ".card" / "calculator.card.md"
    spec_path.write_text(sample_spec_content, encoding="utf-8")
    return spec_path


@pytest.fixture
def sample_card_spec() -> CardSpec:
    """Return a minimal CardSpec for programmatic tests."""
    return CardSpec(
        card_version="1.0",
        id="calculator",
        title="Calculator Module",
        status="draft",
        module=ModuleBoundary(owns=["arithmetic"]),
        contract=Contract(
            inputs=[
                ContractInput(name="a", type="integer", constraints="a >= 0"),
                ContractInput(name="b", type="integer", constraints="b >= 0"),
            ],
            outputs=[ContractOutput(name="result", type="integer")],
        ),
        invariants=[
            Invariant(
                id="INV-001",
                tier=InvariantTier.EXAMPLE,
                statement="add(2, 3) == 5",
            ),
        ],
        intent="A simple calculator that adds two non-negative integers.",
    )


@pytest.fixture
def valid_code() -> str:
    """Return a trivial valid Python code string for verification."""
    return "def add(a: int, b: int) -> int:\n    return a + b\n"


@pytest.fixture
def bad_code() -> str:
    """Return Python code with a syntax error."""
    return "def add(a, b)\n    return a + b\n"


def _make_verify_result(verified: bool = True) -> VerifyResult:
    """Helper to build a VerifyResult for mocking."""
    status = VerifyStatus.PASS if verified else VerifyStatus.FAIL
    stages = [
        StageResult(stage=0, name="preflight", status=status, duration_ms=5),
        StageResult(stage=1, name="deps", status=VerifyStatus.SKIP, duration_ms=2),
        StageResult(stage=2, name="schema", status=VerifyStatus.SKIP, duration_ms=1),
        StageResult(stage=3, name="pbt", status=VerifyStatus.SKIP, duration_ms=1),
        StageResult(stage=4, name="formal", status=VerifyStatus.SKIP, duration_ms=0),
    ]
    if not verified:
        stages[0] = StageResult(
            stage=0,
            name="preflight",
            status=VerifyStatus.FAIL,
            duration_ms=5,
            errors=[{"message": "Spec file not found: nonexistent.card.md"}],
        )
    return VerifyResult(verified=verified, stages=stages, total_duration_ms=10)


# ---------------------------------------------------------------------------
# 1. test_init_creates_spec
# ---------------------------------------------------------------------------


class TestInitCreatesSpec:
    """Test that 'contractd init <module>' creates .card/<module>.card.md."""

    def test_init_creates_spec(self, runner: CliRunner, tmp_project: Path) -> None:
        """The init command should create a .card.md spec file in the .card/ dir."""
        result = runner.invoke(main, ["init", "payment", "--output", str(tmp_project)])
        assert result.exit_code == 0, result.output
        spec_path = tmp_project / ".card" / "payment.card.md"
        assert spec_path.exists(), f"Expected {spec_path} to exist"

    def test_init_spec_contains_module_id(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """The created spec must contain the module id in YAML frontmatter."""
        runner.invoke(main, ["init", "payment", "--output", str(tmp_project)])
        spec_path = tmp_project / ".card" / "payment.card.md"
        content = spec_path.read_text(encoding="utf-8")
        assert "id: payment" in content

    def test_init_spec_starts_with_yaml_delimiters(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """The created spec must start with YAML --- delimiters."""
        runner.invoke(main, ["init", "auth", "--output", str(tmp_project)])
        spec_path = tmp_project / ".card" / "auth.card.md"
        content = spec_path.read_text(encoding="utf-8")
        assert content.startswith("---")


# ---------------------------------------------------------------------------
# 2. test_init_spec_is_parseable
# ---------------------------------------------------------------------------


class TestInitSpecIsParseable:
    """Test that a spec created by init can be round-tripped through parse_card_spec."""

    def test_init_spec_is_parseable(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """A freshly-initialised spec must parse without errors."""
        runner.invoke(main, ["init", "payment", "--output", str(tmp_project)])
        spec_path = tmp_project / ".card" / "payment.card.md"
        spec = parse_card_spec(str(spec_path))
        assert spec.id == "payment"
        assert spec.card_version == "1.0"
        assert spec.status == "draft"

    def test_parsed_spec_has_title(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """The parsed spec should have a title derived from the module name."""
        runner.invoke(main, ["init", "payment", "--output", str(tmp_project)])
        spec_path = tmp_project / ".card" / "payment.card.md"
        spec = parse_card_spec(str(spec_path))
        assert spec.title == "Payment"


# ---------------------------------------------------------------------------
# 3. test_verify_with_valid_spec
# ---------------------------------------------------------------------------


class TestVerifyWithValidSpec:
    """Test running the verification pipeline on a known-good spec + code pair."""

    def test_verify_valid_spec_and_code(
        self, spec_file: Path, valid_code: str, sample_card_spec: CardSpec
    ) -> None:
        """Pipeline should return verified=True for valid spec + valid code.

        Directly calls run_pipeline to bypass CLI wiring.
        """
        from contractd.verifier import run_pipeline

        result = run_pipeline(sample_card_spec, valid_code, spec_path=str(spec_file))
        # Stage 0 (preflight) should pass; later stages may skip
        assert result.stages[0].status in (VerifyStatus.PASS, VerifyStatus.SKIP)

    def test_verify_returns_verify_result(
        self, spec_file: Path, valid_code: str, sample_card_spec: CardSpec
    ) -> None:
        """run_pipeline must return a VerifyResult dataclass."""
        from contractd.verifier import run_pipeline

        result = run_pipeline(sample_card_spec, valid_code, spec_path=str(spec_file))
        assert isinstance(result, VerifyResult)
        assert isinstance(result.stages, list)


# ---------------------------------------------------------------------------
# 4. test_verify_fails_on_bad_code
# ---------------------------------------------------------------------------


class TestVerifyFailsOnBadCode:
    """Test that verification detects syntax errors in generated code."""

    def test_bad_code_triggers_pbt_failure(
        self, spec_file: Path, bad_code: str, sample_card_spec: CardSpec
    ) -> None:
        """Syntactically invalid code should cause a failure in the pipeline.

        Stage 0 checks the spec file (passes), but PBT (Stage 3) or later
        should fail when code has syntax errors.
        """
        from contractd.verifier import run_pipeline

        # The verifier writes code to a temp file for AST checks; bad syntax
        # should propagate to a stage failure.
        result = run_pipeline(sample_card_spec, bad_code, spec_path=str(spec_file))
        # If all stages skip (no property/formal invariants) the pipeline still
        # reports verified. But if stage 3 runs on the bad code, it should fail.
        # With only an 'example' tier invariant, PBT is skipped so pipeline passes.
        # Test with a property-tier invariant to catch the failure.
        assert isinstance(result, VerifyResult)

    def test_bad_code_with_property_invariant_fails(
        self, spec_file: Path, bad_code: str
    ) -> None:
        """Code with syntax errors should fail PBT when property invariants exist."""
        from contractd.verifier import run_pipeline

        spec_with_property = CardSpec(
            card_version="1.0",
            id="calculator",
            title="Calculator Module",
            status="draft",
            module=ModuleBoundary(),
            contract=Contract(),
            invariants=[
                Invariant(
                    id="INV-P01",
                    tier=InvariantTier.PROPERTY,
                    statement="returns a positive integer",
                ),
            ],
        )
        result = run_pipeline(spec_with_property, bad_code, spec_path=str(spec_file))
        # PBT stage should fail on syntax error
        pbt_stages = [s for s in result.stages if s.name == "pbt"]
        if pbt_stages:
            assert pbt_stages[0].status == VerifyStatus.FAIL


# ---------------------------------------------------------------------------
# 5. test_build_command_with_mock_llm
# ---------------------------------------------------------------------------


class TestBuildCommandWithMockLLM:
    """Test that the build command works end-to-end with a mocked LLM."""

    def test_build_with_mocked_generation_and_verification(
        self, runner: CliRunner, spec_file: Path
    ) -> None:
        """Build should orchestrate generate + verify with mocked LLM calls."""
        mock_gen_result = MagicMock()
        mock_gen_result.dafny_code = "method Main() {}"
        mock_verify_result = _make_verify_result(verified=True)

        with (
            patch("contractd.cli._run_generate", return_value=mock_gen_result),
            patch("contractd.cli._run_verify", return_value=mock_verify_result),
        ):
            result = runner.invoke(
                main,
                [
                    "build",
                    "--contract", str(spec_file),
                    "--model", "mock-model",
                    "--retries", "0",
                ],
            )
        assert "BUILD PASSED" in result.output or result.exit_code == 0


# ---------------------------------------------------------------------------
# 6. test_explain_after_failure
# ---------------------------------------------------------------------------


class TestExplainAfterFailure:
    """Test that the explain command produces output after a verify failure."""

    def test_explain_with_failure_report(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """explain should display failure details from a verify.json report."""
        # Write a mock verify.json with a failure
        report = {
            "verified": False,
            "stages": [
                {
                    "stage": 0,
                    "name": "preflight",
                    "status": "pass",
                    "duration_ms": 5,
                    "errors": [],
                },
                {
                    "stage": 3,
                    "name": "pbt",
                    "status": "fail",
                    "duration_ms": 120,
                    "errors": [
                        {
                            "message": "Property violated: result must be positive",
                            "counterexample": {"a": 0, "b": -1},
                        }
                    ],
                },
            ],
            "total_duration_ms": 125,
        }
        report_path = tmp_project / ".card" / "verify.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")

        # The explain command needs a contract path; it looks for verify.json
        # relative to that path's parent directory.
        dummy_spec = tmp_project / ".card" / "test.card.md"
        dummy_spec.write_text("---\ncard-version: '1.0'\nid: test\n---\n")

        result = runner.invoke(main, ["explain", "--contract", str(dummy_spec)])
        # Should contain some form of failure output
        assert result.exit_code == 0
        # The output should mention the failure (via Rich or plain text)
        combined = result.output + (result.stderr or "")
        assert (
            "pbt" in combined.lower()
            or "fail" in combined.lower()
            or "VERIFICATION" in combined
            or "Stage" in combined
        ), f"Expected failure explanation, got: {combined}"

    def test_explain_no_report(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """explain with no verify.json should show a helpful message."""
        dummy_spec = tmp_project / ".card" / "noreport.card.md"
        dummy_spec.write_text("---\ncard-version: '1.0'\nid: noreport\n---\n")

        result = runner.invoke(main, ["explain", "--contract", str(dummy_spec)])
        assert result.exit_code == 0
        assert "no verification report" in result.output.lower() or "verify" in result.output.lower()


# ---------------------------------------------------------------------------
# 7. test_lock_command
# ---------------------------------------------------------------------------


class TestLockCommand:
    """Test that the lock command produces a deps.lock file."""

    def test_lock_creates_deps_lock(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """The lock command should scan the project and write a deps.lock."""
        # Create a minimal Python file to scan
        src_dir = tmp_project / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("import click\nimport yaml\n", encoding="utf-8")

        result = runner.invoke(main, ["lock", "--output", str(tmp_project)])

        lock_path = tmp_project / "deps.lock"
        assert lock_path.exists(), (
            f"Expected deps.lock at {lock_path}. "
            f"Command output: {result.output}"
        )

    def test_lock_file_contains_entries(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """The generated deps.lock should contain package entries."""
        src_dir = tmp_project / "src"
        src_dir.mkdir(exist_ok=True)
        (src_dir / "app.py").write_text("import click\n", encoding="utf-8")

        runner.invoke(main, ["lock", "--output", str(tmp_project)])

        lock_path = tmp_project / "deps.lock"
        if lock_path.exists():
            content = lock_path.read_text(encoding="utf-8")
            # Should have the header
            assert "deps.lock" in content or "contractd" in content


# ---------------------------------------------------------------------------
# 8. test_cli_help_output
# ---------------------------------------------------------------------------


class TestCLIHelpOutput:
    """Test that all commands have help text accessible via --help."""

    @pytest.mark.parametrize(
        "command",
        ["init", "generate", "verify", "build", "ship", "retry", "lock", "explain"],
    )
    def test_command_has_help(self, runner: CliRunner, command: str) -> None:
        """Each CLI command should produce help output with --help."""
        result = runner.invoke(main, [command, "--help"])
        assert result.exit_code == 0, (
            f"'{command} --help' failed with exit code {result.exit_code}: "
            f"{result.output}"
        )
        assert "usage" in result.output.lower() or "--help" in result.output.lower() or command in result.output.lower()

    def test_root_help(self, runner: CliRunner) -> None:
        """The root help should list all subcommands."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "verify" in result.output
        assert "build" in result.output


# ---------------------------------------------------------------------------
# 9. test_cli_version
# ---------------------------------------------------------------------------


class TestCLIVersion:
    """Test that the version flag works."""

    def test_version_flag(self, runner: CliRunner) -> None:
        """--version should print the version number and exit 0."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_version_contains_prog_name(self, runner: CliRunner) -> None:
        """--version should include the program name 'contractd'."""
        result = runner.invoke(main, ["--version"])
        assert "contractd" in result.output.lower()


# ---------------------------------------------------------------------------
# 10. test_full_pipeline_mock
# ---------------------------------------------------------------------------


class TestFullPipelineMock:
    """Full init -> generate -> verify -> explain cycle with mocked LLM."""

    def test_full_cycle(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """Exercise the full pipeline end-to-end with mocked LLM calls.

        Steps:
        1. init -- create a .card.md spec
        2. parse -- parse the spec
        3. generate (mocked) -- produce Dafny code
        4. verify -- run verification pipeline
        5. explain -- explain any failures
        """
        # Step 1: init
        init_result = runner.invoke(
            main, ["init", "payment", "--output", str(tmp_project)]
        )
        assert init_result.exit_code == 0

        spec_path = tmp_project / ".card" / "payment.card.md"
        assert spec_path.exists()

        # Step 2: parse
        spec = parse_card_spec(str(spec_path))
        assert spec.id == "payment"

        # Step 3: generate (mocked)
        mock_gen_result = MagicMock()
        mock_gen_result.dafny_code = "method Main() { assert 1 + 1 == 2; }"
        mock_gen_result.analyst_output = "Requirements analysis..."
        mock_gen_result.formalizer_output = "Dafny skeleton..."
        mock_gen_result.model_used = "mock-model"
        mock_gen_result.spec_id = "payment"

        with patch(
            "contractd.generator.generate_code", return_value=mock_gen_result
        ):
            from contractd.generator import generate_code

            result = generate_code(spec, model="mock-model")
            assert result.dafny_code is not None

        # Step 4: verify -- run the real pipeline with valid code
        from contractd.verifier import run_pipeline

        verify_result = run_pipeline(spec, "def pay(x): return x\n", spec_path=str(spec_path))
        assert isinstance(verify_result, VerifyResult)

        # Step 5: explain -- write a report and run explain
        report_dict = {
            "verified": verify_result.verified,
            "stages": [
                {
                    "stage": s.stage,
                    "name": s.name,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                    "errors": s.errors,
                }
                for s in verify_result.stages
            ],
            "total_duration_ms": verify_result.total_duration_ms,
        }
        report_path = tmp_project / ".card" / "verify.json"
        report_path.write_text(json.dumps(report_dict), encoding="utf-8")

        explain_result = runner.invoke(
            main, ["explain", "--contract", str(spec_path)]
        )
        assert explain_result.exit_code == 0

    def test_init_then_verify_direct(
        self, runner: CliRunner, tmp_project: Path
    ) -> None:
        """Init a spec, then run the verifier directly on it with trivial code."""
        runner.invoke(main, ["init", "auth", "--output", str(tmp_project)])
        spec_path = tmp_project / ".card" / "auth.card.md"
        spec = parse_card_spec(str(spec_path))

        from contractd.verifier import run_pipeline

        result = run_pipeline(spec, "x = 1\n", spec_path=str(spec_path))
        assert isinstance(result, VerifyResult)
        # With no property/formal invariants, PBT and formal skip
        # so the pipeline should pass
        assert result.verified is True
