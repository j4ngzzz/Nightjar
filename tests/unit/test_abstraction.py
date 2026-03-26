"""Tests for structural abstraction layer.

Converts concrete failure traces into PII-free structural signatures.
User{email: null} → ObjectType{optional_field: null} → NullAccess in
notification_path. No field names, no values, no customer identifiers.

References:
- [REF-C10] Herd immunity via differential privacy — abstraction enables sharing
- [REF-P18] Self-healing software — structural pattern recognition
- [REF-C09] Immune system acquired immunity
"""

import pytest

from immune.abstraction import (
    abstract_trace,
    abstract_type,
    abstract_value,
    StructuralSignature,
    AbstractionConfig,
)


class TestAbstractType:
    """Tests for type abstraction."""

    def test_abstract_str(self):
        assert abstract_type("hello") == "StringType"

    def test_abstract_int(self):
        assert abstract_type(42) == "IntType"

    def test_abstract_float(self):
        assert abstract_type(3.14) == "FloatType"

    def test_abstract_none(self):
        assert abstract_type(None) == "NullType"

    def test_abstract_bool(self):
        assert abstract_type(True) == "BoolType"

    def test_abstract_list(self):
        assert abstract_type([1, 2, 3]) == "ListType[IntType]"

    def test_abstract_empty_list(self):
        assert abstract_type([]) == "ListType[EmptyType]"

    def test_abstract_dict(self):
        result = abstract_type({"name": "Alice", "age": 30})
        assert "ObjectType" in result

    def test_abstract_nested_dict(self):
        result = abstract_type({"user": {"email": None}})
        assert "ObjectType" in result
        assert "NullType" in result


class TestAbstractValue:
    """Tests for value abstraction — strips PII."""

    def test_abstract_string_strips_content(self):
        result = abstract_value("alice@example.com")
        assert "alice" not in result
        assert "example.com" not in result

    def test_abstract_int_strips_value(self):
        result = abstract_value(42)
        assert "42" not in result

    def test_abstract_none(self):
        result = abstract_value(None)
        assert result == "null"

    def test_abstract_dict_strips_field_names(self):
        result = abstract_value({"email": "alice@example.com", "ssn": "123-45-6789"})
        assert "email" not in result
        assert "alice" not in result
        assert "ssn" not in result
        assert "123" not in result

    def test_abstract_list_strips_contents(self):
        result = abstract_value(["secret1", "secret2"])
        assert "secret1" not in result
        assert "secret2" not in result


class TestAbstractTrace:
    """Tests for full trace abstraction."""

    def test_abstract_basic_error_trace(self):
        trace = {
            "exception": "AttributeError",
            "message": "NoneType has no attribute 'email'",
            "function": "send_notification",
            "args": {"user": {"name": "Alice", "email": None}},
            "stack": [
                "app.py:42 in send_notification",
                "app.py:10 in main",
            ],
        }
        sig = abstract_trace(trace)
        assert isinstance(sig, StructuralSignature)
        # No PII in the signature
        assert "Alice" not in sig.pattern
        assert "alice" not in sig.pattern.lower()

    def test_signature_has_exception_type(self):
        trace = {
            "exception": "TypeError",
            "message": "unsupported operand",
            "function": "calculate",
            "args": {"x": "not_a_number"},
            "stack": ["calc.py:5 in calculate"],
        }
        sig = abstract_trace(trace)
        assert "TypeError" in sig.exception_class

    def test_signature_has_structural_pattern(self):
        trace = {
            "exception": "KeyError",
            "message": "'missing_key'",
            "function": "lookup",
            "args": {"data": {"a": 1}},
            "stack": ["lookup.py:3 in lookup"],
        }
        sig = abstract_trace(trace)
        assert sig.pattern  # Non-empty pattern

    def test_signature_has_fingerprint(self):
        trace = {
            "exception": "ValueError",
            "message": "invalid literal",
            "function": "parse",
            "args": {"s": "abc"},
            "stack": ["parse.py:1 in parse"],
        }
        sig = abstract_trace(trace)
        assert sig.fingerprint  # Non-empty fingerprint

    def test_same_error_class_same_fingerprint(self):
        """Semantically identical errors should have the same fingerprint."""
        trace1 = {
            "exception": "AttributeError",
            "message": "NoneType has no attribute 'name'",
            "function": "get_user_name",
            "args": {"user": None},
            "stack": ["users.py:10 in get_user_name"],
        }
        trace2 = {
            "exception": "AttributeError",
            "message": "NoneType has no attribute 'email'",
            "function": "get_user_email",
            "args": {"user": None},
            "stack": ["users.py:20 in get_user_email"],
        }
        sig1 = abstract_trace(trace1)
        sig2 = abstract_trace(trace2)
        # Same exception class + same input pattern = same fingerprint
        assert sig1.fingerprint == sig2.fingerprint

    def test_different_error_class_different_fingerprint(self):
        trace1 = {
            "exception": "TypeError",
            "message": "msg",
            "function": "f",
            "args": {"x": 1},
            "stack": ["a.py:1 in f"],
        }
        trace2 = {
            "exception": "ValueError",
            "message": "msg",
            "function": "f",
            "args": {"x": 1},
            "stack": ["a.py:1 in f"],
        }
        sig1 = abstract_trace(trace1)
        sig2 = abstract_trace(trace2)
        assert sig1.fingerprint != sig2.fingerprint


class TestAbstractionConfig:
    """Tests for abstraction configuration."""

    def test_default_config(self):
        config = AbstractionConfig()
        assert config.strip_field_names is True
        assert config.strip_values is True

    def test_custom_config(self):
        config = AbstractionConfig(strip_field_names=False)
        assert config.strip_field_names is False

    def test_abstract_trace_with_config(self):
        trace = {
            "exception": "KeyError",
            "message": "key",
            "function": "f",
            "args": {"x": 1},
            "stack": ["a.py:1"],
        }
        config = AbstractionConfig(strip_field_names=True, strip_values=True)
        sig = abstract_trace(trace, config=config)
        assert isinstance(sig, StructuralSignature)
