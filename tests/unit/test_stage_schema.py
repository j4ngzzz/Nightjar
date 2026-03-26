"""Tests for Stage 2: Schema validation.

Stage 2 validates that generated code output types match the contract
schema defined in the .card.md spec. Uses Pydantic v2 for validation.

Cost: ~0.5-1s, $0.00
Runs in parallel with Stage 3 (PBT).

Reference:
- [REF-T08] Pydantic v2 — data validation
- docs/ARCHITECTURE.md Section 3 (Stage 2)
"""

import pytest
from nightjar.stages.schema import run_schema_check, build_pydantic_model
from nightjar.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    ModuleBoundary, Invariant, InvariantTier,
    StageResult, VerifyStatus,
)


def _make_spec(
    outputs: list[ContractOutput] | None = None,
    inputs: list[ContractInput] | None = None,
) -> CardSpec:
    """Helper to create a CardSpec with given contract outputs."""
    return CardSpec(
        card_version="1.0",
        id="test-module",
        title="Test Module",
        status="draft",
        module=ModuleBoundary(),
        contract=Contract(
            inputs=inputs or [],
            outputs=outputs or [],
        ),
        invariants=[],
    )


class TestBuildPydanticModel:
    """Test dynamic Pydantic model generation from contract outputs."""

    def test_build_model_simple_fields(self):
        """Build model from simple output schema."""
        outputs = [ContractOutput(
            name="PaymentResult",
            type="object",
            schema={"transaction_id": "string", "amount": "integer"},
        )]
        model_cls = build_pydantic_model(outputs[0])
        assert model_cls is not None
        # Should accept valid data
        instance = model_cls(transaction_id="tx-123", amount=500)
        assert instance.transaction_id == "tx-123"
        assert instance.amount == 500

    def test_build_model_string_type(self):
        """String-typed output should build a model."""
        output = ContractOutput(name="Token", type="string", schema={})
        model_cls = build_pydantic_model(output)
        # For scalar types, model just wraps the value
        assert model_cls is not None

    def test_build_model_rejects_invalid_data(self):
        """Pydantic model should reject data that doesn't match schema."""
        output = ContractOutput(
            name="Result",
            type="object",
            schema={"count": "integer"},
        )
        model_cls = build_pydantic_model(output)
        # Invalid type for count
        with pytest.raises(Exception):
            model_cls(count="not_an_integer")


class TestSchemaCheckPass:
    """Stage 2 should PASS when output data matches contract schema."""

    def test_matching_output_passes(self):
        """Output data that matches contract schema should pass."""
        spec = _make_spec(outputs=[ContractOutput(
            name="PaymentResult",
            type="object",
            schema={
                "transaction_id": "string",
                "status": "string",
                "amount_charged": "integer",
            },
        )])
        output_data = {
            "transaction_id": "tx-001",
            "status": "completed",
            "amount_charged": 500,
        }
        result = run_schema_check(spec, output_data)
        assert isinstance(result, StageResult)
        assert result.stage == 2
        assert result.name == "schema"
        assert result.status == VerifyStatus.PASS

    def test_empty_contract_passes(self):
        """Spec with no output schema should pass (nothing to validate)."""
        spec = _make_spec(outputs=[])
        result = run_schema_check(spec, {})
        assert result.status == VerifyStatus.PASS

    def test_extra_fields_pass(self):
        """Output with extra fields beyond schema should pass (open model)."""
        spec = _make_spec(outputs=[ContractOutput(
            name="Result",
            type="object",
            schema={"id": "string"},
        )])
        output_data = {"id": "x", "extra_field": "bonus"}
        result = run_schema_check(spec, output_data)
        assert result.status == VerifyStatus.PASS


class TestSchemaCheckFail:
    """Stage 2 should FAIL when output data violates contract schema."""

    def test_missing_required_field_fails(self):
        """Output missing a field from schema should fail."""
        spec = _make_spec(outputs=[ContractOutput(
            name="Result",
            type="object",
            schema={"id": "string", "name": "string"},
        )])
        output_data = {"id": "x"}  # missing 'name'
        result = run_schema_check(spec, output_data)
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0

    def test_wrong_type_fails(self):
        """Output with wrong field type should fail."""
        spec = _make_spec(outputs=[ContractOutput(
            name="Result",
            type="object",
            schema={"count": "integer"},
        )])
        output_data = {"count": "not_a_number"}
        result = run_schema_check(spec, output_data)
        assert result.status == VerifyStatus.FAIL

    def test_null_required_field_fails(self):
        """Output with None for a required field should fail."""
        spec = _make_spec(outputs=[ContractOutput(
            name="Result",
            type="object",
            schema={"id": "string"},
        )])
        output_data = {"id": None}
        result = run_schema_check(spec, output_data)
        assert result.status == VerifyStatus.FAIL


class TestSchemaCheckEdgeCases:
    """Edge cases for schema validation."""

    def test_duration_is_recorded(self):
        """Stage should record duration."""
        spec = _make_spec(outputs=[])
        result = run_schema_check(spec, {})
        assert result.duration_ms >= 0

    def test_multiple_outputs_validated(self):
        """All contract outputs should be validated."""
        spec = _make_spec(outputs=[
            ContractOutput(name="A", type="object", schema={"x": "integer"}),
            ContractOutput(name="B", type="object", schema={"y": "string"}),
        ])
        # Provide data for first output only — should validate against first match
        output_data = {"x": 42}
        result = run_schema_check(spec, output_data)
        assert result.status == VerifyStatus.PASS

    def test_boolean_type(self):
        """Boolean type in schema should validate correctly."""
        spec = _make_spec(outputs=[ContractOutput(
            name="Result",
            type="object",
            schema={"active": "boolean"},
        )])
        result = run_schema_check(spec, {"active": True})
        assert result.status == VerifyStatus.PASS

    def test_number_type(self):
        """Float/number type in schema should validate correctly."""
        spec = _make_spec(outputs=[ContractOutput(
            name="Result",
            type="object",
            schema={"rate": "number"},
        )])
        result = run_schema_check(spec, {"rate": 3.14})
        assert result.status == VerifyStatus.PASS
