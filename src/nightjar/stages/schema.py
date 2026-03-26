"""Stage 2: Schema validation — Pydantic v2 contract checking.

Validates that generated code output data matches the contract schema
defined in the .card.md spec. Dynamically builds Pydantic models from
contract output definitions, then validates sample data against them.

Cost: ~0.5-1s, $0.00
Runs in parallel with Stage 3 (PBT).

References:
- [REF-T08] Pydantic v2 — data validation
- docs/ARCHITECTURE.md Section 3 (Stage 2)
"""

import time
from typing import Any, Optional

from pydantic import BaseModel, ValidationError, create_model

from nightjar.types import CardSpec, ContractOutput, StageResult, VerifyStatus

# Mapping from .card.md type names to Python types for Pydantic
_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def build_pydantic_model(
    output: ContractOutput,
) -> Optional[type[BaseModel]]:
    """Dynamically build a Pydantic model from a ContractOutput definition.

    For 'object' type outputs with a schema dict, creates a Pydantic model
    with fields matching the schema. For scalar types, creates a wrapper model.

    Args:
        output: ContractOutput from the .card.md contract.

    Returns:
        A Pydantic model class, or None if no schema to validate.
    """
    if output.type == "object" and output.schema:
        # Build field definitions from schema
        fields: dict[str, Any] = {}
        for field_name, field_type_str in output.schema.items():
            python_type = _TYPE_MAP.get(field_type_str, Any)
            # All schema fields are required (no default)
            fields[field_name] = (python_type, ...)

        return create_model(
            output.name,
            **fields,
        )

    if output.type in _TYPE_MAP and output.type != "object":
        # Scalar output — wrap in a model with a single 'value' field
        python_type = _TYPE_MAP[output.type]
        return create_model(
            output.name,
            value=(python_type, ...),
        )

    return None


def run_schema_check(
    spec: CardSpec,
    output_data: dict[str, Any],
) -> StageResult:
    """Run Stage 2 schema validation on output data against contract.

    Builds Pydantic models from the contract's output definitions,
    then validates the provided output data against them.

    Args:
        spec: Parsed .card.md specification.
        output_data: The output data to validate (e.g., from generated code).

    Returns:
        StageResult with stage=2, name='schema', and pass/fail status.
    """
    start = time.monotonic()
    errors: list[dict] = []

    # No outputs to validate → pass
    if not spec.contract.outputs:
        return _pass(start)

    # Try to validate against each output schema
    validated_any = False
    for output in spec.contract.outputs:
        if output.type != "object" or not output.schema:
            continue

        model_cls = build_pydantic_model(output)
        if model_cls is None:
            continue

        try:
            model_cls.model_validate(output_data)
            validated_any = True
            # At least one output schema matched — pass
            break
        except ValidationError as exc:
            # Collect validation errors
            for err in exc.errors():
                errors.append({
                    "message": f"Schema validation error for '{output.name}': "
                               f"{err['msg']}",
                    "output": output.name,
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "type": err["type"],
                })

    # If there were outputs to validate but none matched, fail
    if errors and not validated_any:
        return _fail(start, errors)

    return _pass(start)


def _elapsed_ms(start: float) -> int:
    """Calculate elapsed milliseconds since start."""
    return int((time.monotonic() - start) * 1000)


def _pass(start: float) -> StageResult:
    """Create a passing StageResult."""
    return StageResult(
        stage=2,
        name="schema",
        status=VerifyStatus.PASS,
        duration_ms=_elapsed_ms(start),
    )


def _fail(start: float, errors: list[dict]) -> StageResult:
    """Create a failing StageResult with error details."""
    return StageResult(
        stage=2,
        name="schema",
        status=VerifyStatus.FAIL,
        duration_ms=_elapsed_ms(start),
        errors=errors,
    )
