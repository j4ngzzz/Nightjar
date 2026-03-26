"""Structural abstraction layer for PII-free failure signatures.

Converts concrete failure traces into structural signatures that
contain NO personally identifiable information. Only type-level
patterns are preserved:
  User{email: null} → ObjectType{optional_field: null} → NullAccess

This enables cross-tenant invariant sharing without exposing
customer data.

References:
- [REF-C10] Herd immunity via differential privacy — abstraction enables sharing
- [REF-P18] Self-healing software — structural pattern recognition
- [REF-C09] Immune system acquired immunity
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AbstractionConfig:
    """Configuration for the abstraction layer.

    References:
    - [REF-C10] Privacy-preserving abstraction config
    """

    strip_field_names: bool = True
    strip_values: bool = True


@dataclass
class StructuralSignature:
    """A PII-free structural representation of a failure trace.

    Contains only type-level patterns — no field names, values,
    or customer identifiers.

    References:
    - [REF-C10] Structural abstraction for cross-tenant sharing
    - [REF-P18] Self-healing software pattern recognition
    """

    exception_class: str
    pattern: str
    input_shape: str
    fingerprint: str


def abstract_type(value: Any) -> str:
    """Convert a concrete value to its structural type representation.

    Strips all PII — only the type structure is preserved.

    Examples:
        "hello" → "StringType"
        42 → "IntType"
        {"name": "Alice", "age": 30} → "ObjectType{f0: StringType, f1: IntType}"
        [1, 2, 3] → "ListType[IntType]"
        None → "NullType"

    References:
    - [REF-C10] Type-level structural abstraction
    """
    if value is None:
        return "NullType"
    if isinstance(value, bool):
        return "BoolType"
    if isinstance(value, int):
        return "IntType"
    if isinstance(value, float):
        return "FloatType"
    if isinstance(value, str):
        return "StringType"
    if isinstance(value, list):
        if not value:
            return "ListType[EmptyType]"
        # Use type of first element as representative
        elem_type = abstract_type(value[0])
        return f"ListType[{elem_type}]"
    if isinstance(value, dict):
        if not value:
            return "ObjectType{}"
        # Abstract field names to positional indices
        field_types = []
        for i, v in enumerate(value.values()):
            field_types.append(f"f{i}: {abstract_type(v)}")
        return "ObjectType{" + ", ".join(field_types) + "}"

    return f"UnknownType({type(value).__name__})"


def abstract_value(value: Any) -> str:
    """Abstract a value to its structural representation, stripping all PII.

    Returns only the type shape — no actual values, field names, or
    identifiable content.

    References:
    - [REF-C10] PII-free value abstraction
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "BoolType"
    if isinstance(value, (int, float)):
        return f"NumberType"
    if isinstance(value, str):
        return f"StringType(len={len(value)})"
    if isinstance(value, list):
        return f"ListType(len={len(value)})"
    if isinstance(value, dict):
        # Abstract to shape: number of fields and their types
        field_types = [abstract_type(v) for v in value.values()]
        return "ObjectType(" + ", ".join(field_types) + ")"

    return "UnknownType"


def _compute_input_shape(args: dict[str, Any]) -> str:
    """Compute the structural shape of function arguments.

    Strips field names and values, preserving only type structure.
    """
    if not args:
        return "EmptyArgs"
    shapes = []
    for i, v in enumerate(args.values()):
        shapes.append(f"arg{i}: {abstract_type(v)}")
    return "(" + ", ".join(shapes) + ")"


def _compute_fingerprint(
    exception_class: str, input_shape: str
) -> str:
    """Compute a semantic fingerprint for error grouping.

    Two errors with the same exception class and input shape get
    the same fingerprint, regardless of stack trace or specific values.

    References:
    - [REF-P18] Self-healing software — semantic error grouping
    """
    content = f"{exception_class}:{input_shape}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def abstract_trace(
    trace: dict[str, Any],
    config: AbstractionConfig | None = None,
) -> StructuralSignature:
    """Convert a concrete failure trace into a PII-free structural signature.

    Args:
        trace: Dict with keys: exception, message, function, args, stack.
        config: Optional abstraction configuration.

    Returns:
        StructuralSignature with no PII — only type-level patterns.

    References:
    - [REF-C10] Structural abstraction for cross-tenant sharing
    - [REF-P18] Self-healing software pattern recognition
    """
    if config is None:
        config = AbstractionConfig()

    exception_class = trace.get("exception", "UnknownException")
    args = trace.get("args", {})

    input_shape = _compute_input_shape(args)

    # Build pattern: exception class + input type shape
    pattern = f"{exception_class} on {input_shape}"

    fingerprint = _compute_fingerprint(exception_class, input_shape)

    return StructuralSignature(
        exception_class=exception_class,
        pattern=pattern,
        input_shape=input_shape,
        fingerprint=fingerprint,
    )
