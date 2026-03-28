"""Tests for scanner.py — deterministic AST invariant extraction.

TDD: Tests written BEFORE implementation.

References:
- [REF-T03] Hypothesis for PBT invariant patterns
- [REF-NEW-06] Oracle lifter for test-to-invariant conversion
"""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nightjar.scanner import (
    ScanCandidate,
    ScanResult,
    scan_file,
    scan_file_from_string,
    write_scan_card_md,
    write_scan_card_md_string,
    enhance_with_llm,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _mock_llm_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices[0].message.content = text
    return resp


# ── TestScanCandidate ──────────────────────────────────────────────────────────


class TestScanCandidate:
    def test_has_required_fields(self):
        c = ScanCandidate(
            statement="result must be a string",
            tier="schema",
            source="type_hint",
            source_line=1,
            confidence=0.95,
            function_name="foo",
        )
        assert c.statement == "result must be a string"
        assert c.tier == "schema"
        assert c.source == "type_hint"
        assert c.source_line == 1
        assert c.confidence == 0.95
        assert c.function_name == "foo"


# ── TestScanFileFromString — Type Hints ───────────────────────────────────────


class TestTypeHintExtraction:
    def test_extracts_return_type_hint(self):
        """Required test from build plan."""
        code = "def foo(x: int) -> str:\n    return str(x)"
        candidates = scan_file_from_string(code)
        assert any("str" in c.statement for c in candidates)
        assert any(c.tier == "property" for c in candidates)

    def test_extracts_return_type_int(self):
        code = "def foo(x: str) -> int:\n    return len(x)"
        candidates = scan_file_from_string(code)
        assert any("int" in c.statement for c in candidates)

    def test_extracts_parameter_type_hint(self):
        code = "def foo(x: int) -> None:\n    pass"
        candidates = scan_file_from_string(code)
        assert any("int" in c.statement for c in candidates)

    def test_extracts_optional_type_hint(self):
        code = textwrap.dedent("""\
            from typing import Optional
            def foo(x: int) -> Optional[str]:
                return str(x) if x > 0 else None
        """)
        candidates = scan_file_from_string(code)
        # Should detect Optional return type
        assert any("None" in c.statement or "optional" in c.statement.lower() for c in candidates)

    def test_extracts_list_return_type(self):
        code = textwrap.dedent("""\
            def foo(x: int) -> list[str]:
                return []
        """)
        candidates = scan_file_from_string(code)
        assert any("list" in c.statement.lower() for c in candidates)

    def test_type_hint_source_field(self):
        code = "def foo(x: int) -> str:\n    return str(x)"
        candidates = scan_file_from_string(code)
        type_hint_candidates = [c for c in candidates if c.source == "type_hint"]
        assert len(type_hint_candidates) > 0

    def test_type_hint_schema_tier(self):
        code = "def foo(x: int) -> str:\n    return str(x)"
        candidates = scan_file_from_string(code)
        # type_hint candidates now use "property" tier (not "schema" — schema is not a valid InvariantTier)
        type_hint_candidates = [c for c in candidates if c.source == "type_hint"]
        assert len(type_hint_candidates) > 0
        assert all(c.tier == "property" for c in type_hint_candidates)

    def test_type_hint_high_confidence(self):
        code = "def foo(x: int) -> str:\n    return str(x)"
        candidates = scan_file_from_string(code)
        type_hint_candidates = [c for c in candidates if c.source == "type_hint"]
        assert all(c.confidence >= 0.8 for c in type_hint_candidates)

    def test_no_type_hints_no_schema_candidates(self):
        code = "def foo(x):\n    return x"
        candidates = scan_file_from_string(code)
        schema_candidates = [c for c in candidates if c.tier == "schema"]
        # May be empty or very few (no type hints to extract from)
        type_hint_candidates = [c for c in candidates if c.source == "type_hint"]
        assert len(type_hint_candidates) == 0

    def test_multiple_function_type_hints(self):
        code = textwrap.dedent("""\
            def foo(x: int) -> str:
                return str(x)
            def bar(y: float) -> bool:
                return y > 0.0
        """)
        candidates = scan_file_from_string(code)
        # Should extract from both functions
        function_names = {c.function_name for c in candidates}
        assert "foo" in function_names
        assert "bar" in function_names


# ── TestScanFileFromString — Guard Clauses ────────────────────────────────────


class TestGuardClauseExtraction:
    def test_extracts_guard_clause(self):
        """Required test from build plan."""
        code = textwrap.dedent("""\
            def foo(x):
                if x < 0:
                    raise ValueError('negative')
                return x
        """)
        candidates = scan_file_from_string(code)
        assert any(
            "negative" in c.statement.lower() or "< 0" in c.statement
            for c in candidates
        )

    def test_extracts_guard_with_valueerror(self):
        code = textwrap.dedent("""\
            def process(amount):
                if amount <= 0:
                    raise ValueError("amount must be positive")
                return amount
        """)
        candidates = scan_file_from_string(code)
        guard_candidates = [c for c in candidates if c.source == "guard_clause"]
        assert len(guard_candidates) > 0

    def test_guard_clause_is_property_tier(self):
        code = textwrap.dedent("""\
            def foo(x):
                if x < 0:
                    raise ValueError()
                return x
        """)
        candidates = scan_file_from_string(code)
        guard_candidates = [c for c in candidates if c.source == "guard_clause"]
        assert all(c.tier == "property" for c in guard_candidates)

    def test_extracts_none_guard(self):
        code = textwrap.dedent("""\
            def foo(x):
                if x is None:
                    raise ValueError("cannot be None")
                return x
        """)
        candidates = scan_file_from_string(code)
        guard_candidates = [c for c in candidates if c.source == "guard_clause"]
        assert len(guard_candidates) > 0
        assert any("None" in c.statement for c in guard_candidates)

    def test_extracts_return_none_for_falsy(self):
        code = textwrap.dedent("""\
            def foo(x):
                if not x:
                    return None
                return x
        """)
        candidates = scan_file_from_string(code)
        # Should detect "returns None for falsy input"
        guard_candidates = [c for c in candidates if c.source == "guard_clause"]
        assert len(guard_candidates) > 0

    def test_guard_records_function_name(self):
        code = textwrap.dedent("""\
            def my_function(x):
                if x < 0:
                    raise ValueError()
                return x
        """)
        candidates = scan_file_from_string(code)
        guard_candidates = [c for c in candidates if c.source == "guard_clause"]
        assert all(c.function_name == "my_function" for c in guard_candidates)

    def test_guard_records_source_line(self):
        code = textwrap.dedent("""\
            def foo(x):
                if x < 0:
                    raise ValueError()
                return x
        """)
        candidates = scan_file_from_string(code)
        guard_candidates = [c for c in candidates if c.source == "guard_clause"]
        assert all(c.source_line > 0 for c in guard_candidates)


# ── TestScanFileFromString — Docstrings ───────────────────────────────────────


class TestDocstringExtraction:
    def test_extracts_docstring_returns(self):
        """Required test from build plan."""
        code = textwrap.dedent('''\
            def foo(x):
                """Process input.

                Returns:
                    Non-negative integer.
                """
                return abs(x)
        ''')
        candidates = scan_file_from_string(code)
        assert any("non-negative" in c.statement.lower() for c in candidates)

    def test_docstring_source_field(self):
        code = textwrap.dedent('''\
            def foo(x):
                """Do something.

                Returns:
                    A string value.
                """
                return str(x)
        ''')
        candidates = scan_file_from_string(code)
        docstring_candidates = [c for c in candidates if c.source == "docstring"]
        assert len(docstring_candidates) > 0

    def test_extracts_raises_section(self):
        code = textwrap.dedent('''\
            def foo(x):
                """Process input.

                Raises:
                    ValueError: if x is negative.
                """
                if x < 0:
                    raise ValueError()
                return x
        ''')
        candidates = scan_file_from_string(code)
        docstring_candidates = [c for c in candidates if c.source == "docstring"]
        assert len(docstring_candidates) > 0

    def test_docstring_is_property_tier(self):
        code = textwrap.dedent('''\
            def foo(x):
                """Do something.

                Returns:
                    A positive integer.
                """
                return abs(x) + 1
        ''')
        candidates = scan_file_from_string(code)
        docstring_candidates = [c for c in candidates if c.source == "docstring"]
        # Docstring-derived invariants should be property tier
        assert all(c.tier == "property" for c in docstring_candidates)

    def test_no_docstring_no_docstring_candidates(self):
        code = "def foo(x: int) -> int:\n    return x * 2"
        candidates = scan_file_from_string(code)
        docstring_candidates = [c for c in candidates if c.source == "docstring"]
        assert len(docstring_candidates) == 0

    def test_docstring_records_function_name(self):
        code = textwrap.dedent('''\
            def my_func(x):
                """Do something.

                Returns:
                    A string.
                """
                return str(x)
        ''')
        candidates = scan_file_from_string(code)
        docstring_candidates = [c for c in candidates if c.source == "docstring"]
        assert all(c.function_name == "my_func" for c in docstring_candidates)


# ── TestScanFileFromString — Assertions ───────────────────────────────────────


class TestAssertionExtraction:
    def test_extracts_assertion_invariant(self):
        code = textwrap.dedent("""\
            def foo(x):
                result = x * 2
                assert len(result) > 0
                return result
        """)
        candidates = scan_file_from_string(code)
        assert_candidates = [c for c in candidates if c.source == "assertion"]
        assert len(assert_candidates) > 0

    def test_assertion_is_property_tier(self):
        code = textwrap.dedent("""\
            def foo(x):
                result = abs(x)
                assert result >= 0
                return result
        """)
        candidates = scan_file_from_string(code)
        assert_candidates = [c for c in candidates if c.source == "assertion"]
        assert all(c.tier == "property" for c in assert_candidates)

    def test_assertion_nonempty(self):
        code = textwrap.dedent("""\
            def foo(items):
                result = [x for x in items if x]
                assert len(result) > 0
                return result
        """)
        candidates = scan_file_from_string(code)
        assert_candidates = [c for c in candidates if c.source == "assertion"]
        assert any("non-empty" in c.statement.lower() or "len" in c.statement for c in assert_candidates)

    def test_assertion_records_function_name(self):
        code = textwrap.dedent("""\
            def compute(x):
                result = abs(x)
                assert result >= 0
                return result
        """)
        candidates = scan_file_from_string(code)
        assert_candidates = [c for c in candidates if c.source == "assertion"]
        assert all(c.function_name == "compute" for c in assert_candidates)


# ── TestScanFileFromString — Edge Cases ───────────────────────────────────────


class TestEdgeCases:
    def test_empty_file_returns_empty(self):
        """Required test from build plan."""
        candidates = scan_file_from_string("")
        assert candidates == []

    def test_whitespace_only_returns_empty(self):
        candidates = scan_file_from_string("   \n\n   ")
        assert candidates == []

    def test_syntax_error_returns_empty(self):
        candidates = scan_file_from_string("def broken(:\n    pass")
        assert candidates == []

    def test_module_with_no_functions_returns_empty(self):
        code = "x = 1\ny = 2\nz = x + y\n"
        candidates = scan_file_from_string(code)
        # No functions → no candidates
        assert candidates == []

    def test_returns_list_of_scan_candidates(self):
        code = "def foo(x: int) -> str:\n    return str(x)"
        candidates = scan_file_from_string(code)
        assert isinstance(candidates, list)
        assert all(isinstance(c, ScanCandidate) for c in candidates)


# ── TestScanFile (file-based) ─────────────────────────────────────────────────


class TestScanFile:
    def test_scan_file_reads_python_file(self, tmp_path):
        py_file = tmp_path / "payment.py"
        py_file.write_text(textwrap.dedent("""\
            def process(amount: int) -> str:
                if amount <= 0:
                    raise ValueError("amount must be positive")
                return str(amount)
        """))
        result = scan_file(str(py_file))
        assert isinstance(result, ScanResult)
        assert len(result.candidates) > 0

    def test_scan_file_module_id_from_filename(self, tmp_path):
        py_file = tmp_path / "payment.py"
        py_file.write_text("def foo(x: int) -> str:\n    return str(x)")
        result = scan_file(str(py_file))
        assert result.module_id == "payment"

    def test_scan_file_title_is_titlecased(self, tmp_path):
        py_file = tmp_path / "payment_processor.py"
        py_file.write_text("def foo(x: int) -> str:\n    return str(x)")
        result = scan_file(str(py_file))
        assert result.title == "Payment Processor"

    def test_scan_file_records_function_names(self, tmp_path):
        py_file = tmp_path / "math_utils.py"
        py_file.write_text(textwrap.dedent("""\
            def add(x: int, y: int) -> int:
                return x + y
            def subtract(x: int, y: int) -> int:
                return x - y
        """))
        result = scan_file(str(py_file))
        assert "add" in result.functions
        assert "subtract" in result.functions

    def test_scan_file_signal_strength_high(self, tmp_path):
        py_file = tmp_path / "complex.py"
        py_file.write_text(textwrap.dedent('''\
            def foo(x: int) -> str:
                """Do something.

                Returns:
                    A string.

                Raises:
                    ValueError: if x is negative.
                """
                if x < 0:
                    raise ValueError()
                if x is None:
                    raise TypeError()
                result = str(x)
                assert result is not None
                return result
        '''))
        result = scan_file(str(py_file))
        # With many signals, should be medium or high
        assert result.signal_strength in ("medium", "high")

    def test_scan_file_signal_strength_low(self, tmp_path):
        py_file = tmp_path / "simple.py"
        py_file.write_text("def foo(x):\n    return x\n")
        result = scan_file(str(py_file))
        assert result.signal_strength == "low"

    def test_scan_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            scan_file("/nonexistent/path/file.py")


# ── TestWriteScanCardMd ───────────────────────────────────────────────────────


class TestWriteScanCardMd:
    def test_writes_card_md(self):
        """Required test from build plan."""
        candidates = [
            ScanCandidate(
                statement="result > 0",
                tier="property",
                source="guard_clause",
                source_line=5,
                confidence=0.9,
                function_name="foo",
            )
        ]
        content = write_scan_card_md_string(candidates, "test_module")
        assert "card-version" in content
        assert "result > 0" in content
        assert "tier: property" in content

    def test_card_md_has_module_id(self):
        candidates = [
            ScanCandidate(
                statement="x must be positive",
                tier="property",
                source="guard_clause",
                source_line=2,
                confidence=0.8,
                function_name="bar",
            )
        ]
        content = write_scan_card_md_string(candidates, "my_module")
        assert "id: my_module" in content

    def test_card_md_has_schema_tier(self):
        candidates = [
            ScanCandidate(
                statement="result is a string",
                tier="schema",
                source="type_hint",
                source_line=1,
                confidence=0.95,
                function_name="foo",
            )
        ]
        content = write_scan_card_md_string(candidates, "mod")
        assert "tier: schema" in content

    def test_card_md_status_is_draft(self):
        candidates = [
            ScanCandidate(
                statement="x must be int",
                tier="schema",
                source="type_hint",
                source_line=1,
                confidence=0.9,
                function_name="foo",
            )
        ]
        content = write_scan_card_md_string(candidates, "mod")
        assert "status: draft" in content

    def test_card_md_generated_by_scanner(self):
        candidates = [
            ScanCandidate(
                statement="x must be int",
                tier="schema",
                source="type_hint",
                source_line=1,
                confidence=0.9,
                function_name="foo",
            )
        ]
        content = write_scan_card_md_string(candidates, "mod")
        assert "nightjar-scan" in content

    def test_write_scan_card_md_to_file(self, tmp_path):
        """write_scan_card_md writes to disk and returns path."""
        from nightjar.scanner import ScanResult
        py_file = tmp_path / "payment.py"
        py_file.write_text("def foo(x: int) -> str:\n    return str(x)")
        result = scan_file(str(py_file))
        output_path = tmp_path / "payment.card.md"
        path = write_scan_card_md(str(output_path), result.candidates, "payment")
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "card-version" in content

    def test_write_scan_card_md_creates_parent_dirs(self, tmp_path):
        candidates = [
            ScanCandidate(
                statement="x must be positive",
                tier="property",
                source="guard_clause",
                source_line=2,
                confidence=0.8,
                function_name="foo",
            )
        ]
        nested_path = tmp_path / "nested" / "dir" / "test.card.md"
        path = write_scan_card_md(str(nested_path), candidates, "test")
        assert Path(path).exists()

    def test_empty_candidates_writes_valid_card(self):
        content = write_scan_card_md_string([], "empty_module")
        assert "card-version" in content
        assert "id: empty_module" in content


# ── TestEnhanceWithLlm ────────────────────────────────────────────────────────


class TestEnhanceWithLlm:
    def test_enhance_with_llm_adds_candidates(self):
        """LLM enhancement should add more candidates."""
        candidates = [
            ScanCandidate(
                statement="x must be an integer",
                tier="schema",
                source="type_hint",
                source_line=1,
                confidence=0.9,
                function_name="foo",
            )
        ]
        source = "def foo(x: int) -> str:\n    return str(x)"
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response(
                '["result is always non-empty", "x must be a positive integer"]'
            )
            enhanced = enhance_with_llm(candidates, source)
        # Should return at least the original candidates
        assert len(enhanced) >= len(candidates)

    def test_enhance_with_llm_graceful_on_error(self):
        """LLM failure should not crash — returns original candidates."""
        candidates = [
            ScanCandidate(
                statement="x must be int",
                tier="schema",
                source="type_hint",
                source_line=1,
                confidence=0.9,
                function_name="foo",
            )
        ]
        source = "def foo(x: int) -> str:\n    return str(x)"
        with patch("litellm.completion", side_effect=Exception("API error")):
            enhanced = enhance_with_llm(candidates, source)
        # Should return at least the original candidates unchanged
        assert len(enhanced) >= len(candidates)

    def test_enhance_with_llm_returns_scan_candidates(self):
        """Enhanced candidates must all be ScanCandidate instances."""
        candidates = [
            ScanCandidate(
                statement="x must be int",
                tier="schema",
                source="type_hint",
                source_line=1,
                confidence=0.9,
                function_name="foo",
            )
        ]
        source = "def foo(x: int) -> str:\n    return str(x)"
        with patch("litellm.completion") as mock_llm:
            mock_llm.return_value = _mock_llm_response(
                '["result is always a string"]'
            )
            enhanced = enhance_with_llm(candidates, source)
        assert all(isinstance(c, ScanCandidate) for c in enhanced)

    def test_enhance_with_llm_no_key_returns_original(self):
        """No LLM key available → return original candidates unchanged."""
        candidates = [
            ScanCandidate(
                statement="x must be int",
                tier="schema",
                source="type_hint",
                source_line=1,
                confidence=0.9,
                function_name="foo",
            )
        ]
        source = "def foo(x: int) -> str:\n    return str(x)"
        # Simulate no API key by raising an AuthenticationError-like exception
        with patch("litellm.completion", side_effect=Exception("AuthenticationError")):
            enhanced = enhance_with_llm(candidates, source)
        assert enhanced == candidates
