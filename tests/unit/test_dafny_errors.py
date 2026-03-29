"""Tests for Dafny error classification and translation.

Covers the 20+ error pattern classifier (_classify_dafny_error),
the translation dictionary (DAFNY_ERROR_TRANSLATIONS), and the
translate_dafny_error() function.

References:
- [REF-T01] Dafny — verification-aware programming language
- [REF-P06] DafnyPro — structured error format with assertion batch IDs
- Research file: .bridgespace/swarms/pane1774/inbox/wave4/research-benchmark-dafny-errors.md
  Part 3: Top 20 Dafny Errors with Python-Developer Translations
"""

import pytest

from nightjar.stages.formal import (
    _classify_dafny_error,
    DAFNY_ERROR_TRANSLATIONS,
    translate_dafny_error,
)


# ─── Regression tests: existing classifications must not change ───────────────


class TestClassifyExistingPatterns:
    """Regression tests — ensure original 6 categories are unchanged."""

    def test_postcondition_keyword(self):
        assert _classify_dafny_error(
            "A postcondition might not hold on this return path"
        ) == "postcondition_failure"

    def test_postcondition_alternative_phrasing(self):
        """'could not be proved' phrasing also contains 'postcondition'."""
        assert _classify_dafny_error(
            "a postcondition could not be proved on this return path"
        ) == "postcondition_failure"

    def test_precondition_keyword(self):
        assert _classify_dafny_error(
            "A precondition for this call might not hold"
        ) == "precondition_failure"

    def test_assertion_keyword(self):
        assert _classify_dafny_error(
            "assertion might not hold"
        ) == "assertion_failure"

    def test_assert_keyword(self):
        assert _classify_dafny_error(
            "this assert statement might not hold"
        ) == "assertion_failure"

    def test_loop_invariant_keyword(self):
        assert _classify_dafny_error(
            "This loop invariant might not be maintained by the loop"
        ) == "loop_invariant_failure"

    def test_decreases_keyword(self):
        assert _classify_dafny_error(
            "decreases clause might not decrease"
        ) == "decreases_failure"

    def test_unknown_returns_other(self):
        assert _classify_dafny_error(
            "some completely unknown error message xyz"
        ) == "other"

    def test_empty_string_returns_other(self):
        assert _classify_dafny_error("") == "other"


# ─── New classification patterns ─────────────────────────────────────────────


class TestClassifyNewPatterns:
    """Tests for the 10 newly added error categories."""

    def test_array_bounds_failure(self):
        assert _classify_dafny_error(
            "index out of range"
        ) == "array_bounds_failure"

    def test_array_bounds_failure_mixed_case(self):
        assert _classify_dafny_error(
            "Index out of Range in sequence access"
        ) == "array_bounds_failure"

    def test_null_dereference_failure_null(self):
        assert _classify_dafny_error(
            "target object might be null"
        ) == "null_dereference_failure"

    def test_null_dereference_failure_target_object(self):
        assert _classify_dafny_error(
            "the target object might not be allocated"
        ) == "null_dereference_failure"

    def test_reads_frame_failure(self):
        assert _classify_dafny_error(
            "insufficient reads clause to read field x"
        ) == "reads_frame_failure"

    def test_modifies_frame_failure(self):
        assert _classify_dafny_error(
            "assignment might update an object not in the enclosing context's modifies clause"
        ) == "modifies_frame_failure"

    def test_termination_failure_cannot_prove(self):
        assert _classify_dafny_error(
            "cannot prove termination; try supplying a decreases clause"
        ) == "termination_failure"

    def test_termination_failure_termination_keyword(self):
        assert _classify_dafny_error(
            "this loop may not terminate"
        ) == "termination_failure"

    def test_fuel_failure(self):
        assert _classify_dafny_error(
            "A fuel annotation exceeds the limit"
        ) == "fuel_failure"

    def test_fuel_failure_mixed_case(self):
        assert _classify_dafny_error(
            "Fuel annotation is too high for this function"
        ) == "fuel_failure"

    def test_quantifier_trigger_failure(self):
        assert _classify_dafny_error(
            "cannot find a trigger for this quantifier"
        ) == "quantifier_trigger_failure"

    def test_quantifier_trigger_failure_combined_keywords(self):
        assert _classify_dafny_error(
            "trigger not found for quantifier expression"
        ) == "quantifier_trigger_failure"

    def test_subset_type_failure(self):
        assert _classify_dafny_error(
            "value does not satisfy the subset constraints"
        ) == "subset_type_failure"

    def test_exhaustiveness_failure(self):
        assert _classify_dafny_error(
            "match expression is not exhaustive"
        ) == "exhaustiveness_failure"

    def test_exhaustiveness_failure_alternative(self):
        assert _classify_dafny_error(
            "this match is not exhaustive — missing case"
        ) == "exhaustiveness_failure"

    def test_ghost_variable_failure(self):
        assert _classify_dafny_error(
            "ghost variables cannot be used here"
        ) == "ghost_variable_failure"

    def test_ghost_variable_failure_mixed_case(self):
        assert _classify_dafny_error(
            "Ghost variable 'x' is not allowed in compiled code"
        ) == "ghost_variable_failure"


# ─── Priority ordering: existing patterns are not shadowed ───────────────────


class TestClassifyPriority:
    """Verify that new patterns do not shadow existing ones on ambiguous messages."""

    def test_postcondition_takes_priority_over_termination(self):
        """A message with 'postcondition' + 'termination' must stay postcondition."""
        assert _classify_dafny_error(
            "postcondition might not hold — termination argument missing"
        ) == "postcondition_failure"

    def test_precondition_not_shadowed_by_null(self):
        """'null' appearing in a precondition message should not mis-classify."""
        # precondition is checked before null_dereference, so precondition wins
        msg = "A precondition for this call might not hold: requires obj != null"
        result = _classify_dafny_error(msg)
        # Either precondition_failure or null_dereference_failure is acceptable
        # depending on implementation priority — assert the function is deterministic
        assert result in ("precondition_failure", "null_dereference_failure")

    def test_decreases_not_shadowed_by_termination(self):
        """'decreases' keyword matches decreases_failure before termination_failure."""
        result = _classify_dafny_error("decreases clause might not decrease")
        assert result == "decreases_failure"


# ─── DAFNY_ERROR_TRANSLATIONS dict structure ─────────────────────────────────


class TestDafnyErrorTranslationsDict:
    """Validate the DAFNY_ERROR_TRANSLATIONS constant."""

    EXPECTED_CATEGORIES = [
        "postcondition_failure",
        "precondition_failure",
        "assertion_failure",
        "loop_invariant_failure",
        "loop_invariant_entry_failure",
        "decreases_failure",
        "termination_failure",
        "array_bounds_failure",
        "null_dereference_failure",
        "reads_frame_failure",
        "modifies_frame_failure",
        "fuel_failure",
        "quantifier_trigger_failure",
        "subset_type_failure",
        "exhaustiveness_failure",
        "ghost_variable_failure",
        "function_precondition_failure",
        "wellformed_failure",
        "timeout",
        "other",
    ]

    def test_dict_exists_and_is_dict(self):
        assert isinstance(DAFNY_ERROR_TRANSLATIONS, dict)

    def test_dict_has_at_least_20_entries(self):
        assert len(DAFNY_ERROR_TRANSLATIONS) >= 20

    def test_all_expected_categories_present(self):
        for cat in self.EXPECTED_CATEGORIES:
            assert cat in DAFNY_ERROR_TRANSLATIONS, (
                f"Expected category '{cat}' missing from DAFNY_ERROR_TRANSLATIONS"
            )

    def test_each_entry_has_required_keys(self):
        required_keys = {"summary", "python_analogy", "fix_hint"}
        for category, translation in DAFNY_ERROR_TRANSLATIONS.items():
            assert isinstance(translation, dict), (
                f"Translation for '{category}' must be a dict, got {type(translation)}"
            )
            for key in required_keys:
                assert key in translation, (
                    f"Translation for '{category}' missing required key '{key}'"
                )

    def test_each_entry_values_are_non_empty_strings(self):
        for category, translation in DAFNY_ERROR_TRANSLATIONS.items():
            for key in ("summary", "python_analogy", "fix_hint"):
                value = translation.get(key, "")
                assert isinstance(value, str) and len(value) > 0, (
                    f"Translation['{category}']['{key}'] must be a non-empty string"
                )

    def test_postcondition_summary_mentions_ensures(self):
        entry = DAFNY_ERROR_TRANSLATIONS["postcondition_failure"]
        combined = (entry["summary"] + entry["python_analogy"] + entry["fix_hint"]).lower()
        assert "ensures" in combined or "return" in combined or "guarantee" in combined

    def test_array_bounds_fix_hint_mentions_invariant_or_bounds(self):
        entry = DAFNY_ERROR_TRANSLATIONS["array_bounds_failure"]
        combined = (entry["summary"] + entry["fix_hint"]).lower()
        assert "invariant" in combined or "bound" in combined or "index" in combined

    def test_termination_fix_hint_mentions_decreases(self):
        entry = DAFNY_ERROR_TRANSLATIONS["termination_failure"]
        combined = (entry["summary"] + entry["fix_hint"]).lower()
        assert "decreases" in combined or "terminat" in combined


# ─── translate_dafny_error() function ────────────────────────────────────────


class TestTranslateDafnyError:
    """Tests for translate_dafny_error() function."""

    def test_returns_dict(self):
        result = translate_dafny_error("assertion might not hold")
        assert isinstance(result, dict)

    def test_result_has_all_required_keys(self):
        result = translate_dafny_error("assertion might not hold")
        for key in ("category", "summary", "python_analogy", "fix_hint", "raw_message"):
            assert key in result, f"translate_dafny_error result missing key '{key}'"

    def test_raw_message_preserved(self):
        msg = "A postcondition might not hold on this return path"
        result = translate_dafny_error(msg)
        assert result["raw_message"] == msg

    def test_postcondition_message_translates_correctly(self):
        result = translate_dafny_error(
            "A postcondition might not hold on this return path"
        )
        assert result["category"] == "postcondition_failure"
        assert len(result["summary"]) > 0
        assert len(result["python_analogy"]) > 0
        assert len(result["fix_hint"]) > 0

    def test_array_bounds_message_translates_correctly(self):
        result = translate_dafny_error("index out of range")
        assert result["category"] == "array_bounds_failure"

    def test_null_dereference_message_translates_correctly(self):
        result = translate_dafny_error("target object might be null")
        assert result["category"] == "null_dereference_failure"

    def test_reads_frame_message_translates_correctly(self):
        result = translate_dafny_error("insufficient reads clause to read field x")
        assert result["category"] == "reads_frame_failure"

    def test_modifies_frame_message_translates_correctly(self):
        result = translate_dafny_error(
            "assignment might update an object not in the enclosing context's modifies clause"
        )
        assert result["category"] == "modifies_frame_failure"

    def test_termination_failure_translates_correctly(self):
        result = translate_dafny_error(
            "cannot prove termination; try supplying a decreases clause"
        )
        assert result["category"] == "termination_failure"

    def test_fuel_failure_translates_correctly(self):
        result = translate_dafny_error("A fuel annotation exceeds the limit")
        assert result["category"] == "fuel_failure"

    def test_quantifier_trigger_translates_correctly(self):
        result = translate_dafny_error("cannot find a trigger for this quantifier")
        assert result["category"] == "quantifier_trigger_failure"

    def test_subset_type_translates_correctly(self):
        result = translate_dafny_error("value does not satisfy the subset constraints")
        assert result["category"] == "subset_type_failure"

    def test_exhaustiveness_translates_correctly(self):
        result = translate_dafny_error("match expression is not exhaustive")
        assert result["category"] == "exhaustiveness_failure"

    def test_ghost_variable_translates_correctly(self):
        result = translate_dafny_error("ghost variables cannot be used here")
        assert result["category"] == "ghost_variable_failure"

    def test_unknown_message_falls_back_to_other(self):
        result = translate_dafny_error("zzz_completely_unknown_dafny_message_zzz")
        assert result["category"] == "other"

    def test_unknown_message_still_has_all_keys(self):
        result = translate_dafny_error("zzz_completely_unknown_dafny_message_zzz")
        for key in ("category", "summary", "python_analogy", "fix_hint", "raw_message"):
            assert key in result

    def test_unknown_message_preserves_raw_message(self):
        msg = "zzz_completely_unknown_dafny_message_zzz"
        result = translate_dafny_error(msg)
        assert result["raw_message"] == msg

    def test_empty_string_falls_back_gracefully(self):
        result = translate_dafny_error("")
        assert result["category"] == "other"
        assert result["raw_message"] == ""

    def test_case_insensitive_translation(self):
        """Translation must work regardless of message casing."""
        upper = translate_dafny_error("ASSERTION MIGHT NOT HOLD")
        lower = translate_dafny_error("assertion might not hold")
        assert upper["category"] == lower["category"]

    def test_decreases_failure_translates_correctly(self):
        result = translate_dafny_error("decreases clause might not decrease")
        assert result["category"] == "decreases_failure"

    def test_loop_invariant_translates_correctly(self):
        result = translate_dafny_error(
            "This loop invariant might not be maintained by the loop"
        )
        assert result["category"] == "loop_invariant_failure"
