"""Tests for benchmark adapter — vericoding (POPL 2026) and DafnyBench loaders.

TDD: Tests written BEFORE implementation.

References:
- Vericoding paper: https://arxiv.org/abs/2509.22908
- DafnyBench paper: https://arxiv.org/abs/2406.08467
"""

import json
import textwrap
from pathlib import Path

import pytest

from nightjar.benchmark_adapter import (
    BenchmarkTask,
    load_vericoding_tasks,
    load_dafnybench_tasks,
    task_to_card_spec,
    detect_cheating,
    fill_template,
    load_benchmark_suite,
)
from nightjar.types import CardSpec, InvariantTier


# ── Fixture data ──────────────────────────────────────────────────────────────

VERICODING_TASK_1 = {
    "task_id": "humaneval_dafny_0",
    "dataset": "HumanEval-Dafny",
    "difficulty": "easy",
    "preamble": "// HumanEval problem 0\ndatatype Option<T> = Some(val: T) | None",
    "spec": textwrap.dedent("""\
        method HasCloseElements(numbers: seq<real>, threshold: real) returns (result: bool)
          requires threshold > 0.0
          ensures result <==> exists i, j :: 0 <= i < j < |numbers| &&
                  numbers[i] - numbers[j] < threshold
        {
          <vc-code>
        }
    """),
    "full_template": textwrap.dedent("""\
        // HumanEval problem 0
        datatype Option<T> = Some(val: T) | None

        method HasCloseElements(numbers: seq<real>, threshold: real) returns (result: bool)
          requires threshold > 0.0
          ensures result <==> exists i, j :: 0 <= i < j < |numbers| &&
                  numbers[i] - numbers[j] < threshold
        {
          <vc-code>
        }
    """),
    "helpers_template": "",
    "metadata": {"source": "HumanEval", "index": 0},
}

VERICODING_TASK_2 = {
    "task_id": "apps_dafny_42",
    "dataset": "APPS",
    "difficulty": "medium",
    "preamble": "",
    "spec": textwrap.dedent("""\
        method ReverseArray(a: array<int>) returns (result: array<int>)
          requires a != null
          ensures result != null
          ensures result.Length == a.Length
          ensures forall i :: 0 <= i < a.Length ==> result[i] == a[a.Length - 1 - i]
        {
          <vc-code>
          <vc-helpers>
        }
    """),
    "full_template": textwrap.dedent("""\
        method ReverseArray(a: array<int>) returns (result: array<int>)
          requires a != null
          ensures result != null
          ensures result.Length == a.Length
          ensures forall i :: 0 <= i < a.Length ==> result[i] == a[a.Length - 1 - i]
        {
          <vc-code>
          <vc-helpers>
        }
    """),
    "helpers_template": "<vc-helpers>",
    "metadata": {"source": "APPS", "index": 42},
}

VERICODING_TASK_3 = {
    "task_id": "dafnybench_123",
    "dataset": "DafnyBench",
    "difficulty": "hard",
    "preamble": "function Max(a: int, b: int): int { if a > b then a else b }",
    "spec": textwrap.dedent("""\
        method BinarySearch(a: array<int>, key: int) returns (index: int)
          requires a != null
          requires forall i, j :: 0 <= i < j < a.Length ==> a[i] <= a[j]
          ensures -1 <= index < a.Length
          ensures index >= 0 ==> a[index] == key
          ensures index == -1 ==> forall i :: 0 <= i < a.Length ==> a[i] != key
        {
          <vc-code>
        }
    """),
    "full_template": textwrap.dedent("""\
        function Max(a: int, b: int): int { if a > b then a else b }

        method BinarySearch(a: array<int>, key: int) returns (index: int)
          requires a != null
          requires forall i, j :: 0 <= i < j < a.Length ==> a[i] <= a[j]
          ensures -1 <= index < a.Length
          ensures index >= 0 ==> a[index] == key
          ensures index == -1 ==> forall i :: 0 <= i < a.Length ==> a[i] != key
        {
          <vc-code>
        }
    """),
    "helpers_template": "",
    "metadata": {"source": "DafnyBench"},
}

VERICODING_TASK_MINIMAL = {
    "task_id": "minimal_task",
    "dataset": "HumanEval-Dafny",
    "preamble": "",
    "spec": "method Trivial() { <vc-code> }",
    "full_template": "method Trivial() { <vc-code> }",
    # No difficulty or helpers_template fields — tests missing optional fields
}

DAFNYBENCH_DFY_CONTENT = textwrap.dedent("""\
    // DafnyBench: hints_removed version
    method BubbleSort(a: array<int>)
      requires a != null
      modifies a
      ensures forall i, j :: 0 <= i < j < a.Length ==> a[i] <= a[j]
    {
      var n := a.Length;
      var i := 0;
      while i < n
        // hint removed: invariant forall k, l :: 0 <= k < l < i ==> a[k] <= a[l]
      {
        var j := 0;
        while j < n - i - 1
        {
          if a[j] > a[j + 1] {
            var tmp := a[j];
            a[j] := a[j + 1];
            a[j + 1] := tmp;
          }
          j := j + 1;
        }
        i := i + 1;
      }
    }
""")


def _write_vericoding_jsonl(tmp_path: Path, tasks: list[dict]) -> Path:
    """Write tasks as JSONL file and return the path."""
    jsonl_path = tmp_path / "dafny_tasks.jsonl"
    lines = [json.dumps(t) for t in tasks]
    jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jsonl_path


def _write_dafnybench_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write a hints_removed/ directory with .dfy files and return the path."""
    hints_removed = tmp_path / "hints_removed"
    hints_removed.mkdir()
    for name, content in files.items():
        (hints_removed / name).write_text(content, encoding="utf-8")
    return tmp_path  # return the benchmark root, not hints_removed/


# ── TestBenchmarkTask dataclass ────────────────────────────────────────────────


class TestBenchmarkTaskDataclass:
    def test_required_fields_accessible(self):
        task = BenchmarkTask(
            task_id="test_0",
            source="vericoding",
            dataset="HumanEval-Dafny",
            preamble="// preamble",
            spec="method Foo() { <vc-code> }",
            code_placeholder="<vc-code>",
            helpers_placeholder="<vc-helpers>",
            full_template="method Foo() { <vc-code> }",
            difficulty="easy",
            metadata={},
        )
        assert task.task_id == "test_0"
        assert task.source == "vericoding"
        assert task.dataset == "HumanEval-Dafny"
        assert task.difficulty == "easy"

    def test_metadata_defaults_to_empty_dict(self):
        task = BenchmarkTask(
            task_id="x",
            source="vericoding",
            dataset="HumanEval-Dafny",
            preamble="",
            spec="",
            code_placeholder="<vc-code>",
            helpers_placeholder="<vc-helpers>",
            full_template="",
            difficulty="",
            metadata={},
        )
        assert isinstance(task.metadata, dict)


# ── TestLoadVericodingTasks ────────────────────────────────────────────────────


class TestLoadVericodingTasks:
    def test_loads_three_tasks(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(
            tmp_path,
            [VERICODING_TASK_1, VERICODING_TASK_2, VERICODING_TASK_3],
        )
        tasks = load_vericoding_tasks(jsonl_path)
        assert len(tasks) == 3

    def test_task_id_parsed(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].task_id == "humaneval_dafny_0"

    def test_source_is_vericoding(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].source == "vericoding"

    def test_dataset_field_parsed(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_2])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].dataset == "APPS"

    def test_preamble_parsed(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_vericoding_tasks(jsonl_path)
        assert "HumanEval problem 0" in tasks[0].preamble

    def test_spec_field_parsed(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_vericoding_tasks(jsonl_path)
        assert "HasCloseElements" in tasks[0].spec

    def test_code_placeholder_detected(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].code_placeholder == "<vc-code>"

    def test_helpers_placeholder_detected_when_present(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_2])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].helpers_placeholder == "<vc-helpers>"

    def test_difficulty_parsed(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_3])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].difficulty == "hard"

    def test_difficulty_empty_when_missing(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_MINIMAL])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].difficulty == ""

    def test_metadata_preserved(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks[0].metadata.get("source") == "HumanEval"

    def test_empty_jsonl_returns_empty_list(self, tmp_path):
        jsonl_path = tmp_path / "empty.jsonl"
        jsonl_path.write_text("", encoding="utf-8")
        tasks = load_vericoding_tasks(jsonl_path)
        assert tasks == []

    def test_malformed_json_line_skipped(self, tmp_path):
        jsonl_path = tmp_path / "bad.jsonl"
        jsonl_path.write_text(
            json.dumps(VERICODING_TASK_1) + "\n"
            + "THIS IS NOT JSON\n"
            + json.dumps(VERICODING_TASK_2) + "\n",
            encoding="utf-8",
        )
        tasks = load_vericoding_tasks(jsonl_path)
        # Malformed line skipped; the two valid ones parsed
        assert len(tasks) == 2

    def test_missing_required_field_skipped(self, tmp_path):
        """Tasks missing both preamble and spec are skipped gracefully."""
        bad_task = {"task_id": "broken", "dataset": "HumanEval-Dafny"}
        jsonl_path = _write_vericoding_jsonl(
            tmp_path, [VERICODING_TASK_1, bad_task]
        )
        tasks = load_vericoding_tasks(jsonl_path)
        # bad_task is missing spec field → should be skipped
        task_ids = [t.task_id for t in tasks]
        assert "humaneval_dafny_0" in task_ids
        assert "broken" not in task_ids

    def test_full_template_parsed(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_vericoding_tasks(jsonl_path)
        assert "<vc-code>" in tasks[0].full_template


# ── TestLoadDafnybenchTasks ────────────────────────────────────────────────────


class TestLoadDafnybenchTasks:
    def test_loads_dfy_files_from_hints_removed(self, tmp_path):
        _write_dafnybench_dir(
            tmp_path,
            {"bubble_sort.dfy": DAFNYBENCH_DFY_CONTENT, "binary_search.dfy": "method Foo() {}"},
        )
        tasks = load_dafnybench_tasks(tmp_path)
        assert len(tasks) == 2

    def test_source_is_dafnybench(self, tmp_path):
        _write_dafnybench_dir(tmp_path, {"foo.dfy": "method Foo() {}"})
        tasks = load_dafnybench_tasks(tmp_path)
        assert tasks[0].source == "dafnybench"

    def test_task_id_from_filename(self, tmp_path):
        _write_dafnybench_dir(tmp_path, {"bubble_sort.dfy": DAFNYBENCH_DFY_CONTENT})
        tasks = load_dafnybench_tasks(tmp_path)
        assert tasks[0].task_id == "bubble_sort"

    def test_spec_contains_file_content(self, tmp_path):
        _write_dafnybench_dir(tmp_path, {"sort.dfy": DAFNYBENCH_DFY_CONTENT})
        tasks = load_dafnybench_tasks(tmp_path)
        assert "BubbleSort" in tasks[0].spec

    def test_dataset_is_dafnybench(self, tmp_path):
        _write_dafnybench_dir(tmp_path, {"foo.dfy": "method Foo() {}"})
        tasks = load_dafnybench_tasks(tmp_path)
        assert tasks[0].dataset == "DafnyBench"

    def test_empty_directory_returns_empty(self, tmp_path):
        hints_removed = tmp_path / "hints_removed"
        hints_removed.mkdir()
        tasks = load_dafnybench_tasks(tmp_path)
        assert tasks == []

    def test_non_dfy_files_ignored(self, tmp_path):
        _write_dafnybench_dir(
            tmp_path,
            {"valid.dfy": "method Foo() {}", "readme.txt": "ignore me"},
        )
        tasks = load_dafnybench_tasks(tmp_path)
        assert len(tasks) == 1
        assert tasks[0].task_id == "valid"

    def test_missing_hints_removed_raises(self, tmp_path):
        # directory without hints_removed/ subdirectory
        with pytest.raises((FileNotFoundError, NotADirectoryError, ValueError)):
            load_dafnybench_tasks(tmp_path)


# ── TestTaskToCardSpec ─────────────────────────────────────────────────────────


class TestTaskToCardSpec:
    def _make_task(self, spec: str = "", task_id: str = "test_0", dataset: str = "HumanEval-Dafny") -> BenchmarkTask:
        return BenchmarkTask(
            task_id=task_id,
            source="vericoding",
            dataset=dataset,
            preamble="",
            spec=spec,
            code_placeholder="<vc-code>",
            helpers_placeholder="<vc-helpers>",
            full_template=spec,
            difficulty="easy",
            metadata={},
        )

    def test_returns_card_spec_instance(self):
        task = self._make_task("method Foo() requires x > 0 ensures y > 0 { <vc-code> }")
        card = task_to_card_spec(task)
        assert isinstance(card, CardSpec)

    def test_card_id_from_task_id(self):
        task = self._make_task(task_id="humaneval_dafny_0")
        card = task_to_card_spec(task)
        assert card.id == "humaneval_dafny_0"

    def test_card_title_from_task_id(self):
        task = self._make_task(task_id="binary_search_42")
        card = task_to_card_spec(task)
        assert card.title  # non-empty
        assert "binary_search" in card.title.lower() or "42" in card.title

    def test_invariants_extracted_from_requires(self):
        spec = textwrap.dedent("""\
            method Foo(x: int) returns (y: int)
              requires x > 0
              ensures y >= x
            { <vc-code> }
        """)
        task = self._make_task(spec)
        card = task_to_card_spec(task)
        inv_statements = [inv.statement for inv in card.invariants]
        assert any("x > 0" in s for s in inv_statements)

    def test_invariants_extracted_from_ensures(self):
        spec = textwrap.dedent("""\
            method Foo(x: int) returns (y: int)
              requires x > 0
              ensures y >= x
            { <vc-code> }
        """)
        task = self._make_task(spec)
        card = task_to_card_spec(task)
        inv_statements = [inv.statement for inv in card.invariants]
        assert any("y >= x" in s for s in inv_statements)

    def test_invariant_tier_is_formal(self):
        spec = "method Foo() requires true ensures true { <vc-code> }"
        task = self._make_task(spec)
        card = task_to_card_spec(task)
        for inv in card.invariants:
            assert inv.tier == InvariantTier.FORMAL

    def test_no_preconditions_yields_no_requires_invariants(self):
        spec = "method Foo() { <vc-code> }"
        task = self._make_task(spec)
        card = task_to_card_spec(task)
        # No requires/ensures → invariants list may be empty or only have placeholder
        assert isinstance(card.invariants, list)

    def test_card_spec_version_set(self):
        task = self._make_task()
        card = task_to_card_spec(task)
        assert card.card_version  # non-empty string

    def test_status_set(self):
        task = self._make_task()
        card = task_to_card_spec(task)
        assert card.status  # non-empty


# ── TestDetectCheating ─────────────────────────────────────────────────────────


class TestDetectCheating:
    def test_clean_code_returns_empty(self):
        clean = textwrap.dedent("""\
            method Add(a: int, b: int) returns (c: int)
              ensures c == a + b
            {
              c := a + b;
            }
        """)
        violations = detect_cheating(clean)
        assert violations == []

    def test_detects_assume_statement(self):
        code = textwrap.dedent("""\
            method Foo() {
              assume x > 0;
            }
        """)
        violations = detect_cheating(code)
        assert len(violations) > 0
        assert any("assume" in v.lower() for v in violations)

    def test_detects_axiom_attribute(self):
        code = textwrap.dedent("""\
            lemma {:axiom} SomeAxiom()
              ensures 1 == 1
        """)
        violations = detect_cheating(code)
        assert len(violations) > 0
        assert any("axiom" in v.lower() for v in violations)

    def test_detects_verify_false(self):
        code = textwrap.dedent("""\
            method {:verify false} Foo() {
              // skipped
            }
        """)
        violations = detect_cheating(code)
        assert len(violations) > 0
        assert any("verify" in v.lower() for v in violations)

    def test_multiple_violations_all_reported(self):
        code = textwrap.dedent("""\
            method {:verify false} Foo() {
              assume x > 0;
            }
        """)
        violations = detect_cheating(code)
        assert len(violations) >= 2

    def test_assume_in_comment_not_flagged(self):
        """// assume ... in a comment should not be flagged as cheating."""
        code = textwrap.dedent("""\
            method Foo(x: int) returns (y: int)
              // In a real implementation we would need assume here
              ensures y == x
            {
              y := x;
            }
        """)
        violations = detect_cheating(code)
        assert violations == []

    def test_returns_list_of_strings(self):
        code = "assume x > 0;"
        violations = detect_cheating(code)
        assert isinstance(violations, list)
        assert all(isinstance(v, str) for v in violations)


# ── TestFillTemplate ──────────────────────────────────────────────────────────


class TestFillTemplate:
    def _make_task_with_template(self, template: str) -> BenchmarkTask:
        return BenchmarkTask(
            task_id="fill_test",
            source="vericoding",
            dataset="HumanEval-Dafny",
            preamble="",
            spec=template,
            code_placeholder="<vc-code>",
            helpers_placeholder="<vc-helpers>",
            full_template=template,
            difficulty="easy",
            metadata={},
        )

    def test_replaces_vc_code_placeholder(self):
        template = "method Foo() { <vc-code> }"
        task = self._make_task_with_template(template)
        result = fill_template(task, generated_code="  result := 42;")
        assert "<vc-code>" not in result
        assert "result := 42;" in result

    def test_replaces_vc_helpers_placeholder(self):
        template = "method Foo() { <vc-code> }\n<vc-helpers>"
        task = self._make_task_with_template(template)
        result = fill_template(
            task,
            generated_code="  x := 1;",
            generated_helpers="lemma Helper() ensures true {}",
        )
        assert "<vc-helpers>" not in result
        assert "Helper()" in result

    def test_no_helpers_removes_helpers_placeholder(self):
        template = "method Foo() {\n  <vc-code>\n}\n<vc-helpers>"
        task = self._make_task_with_template(template)
        result = fill_template(task, generated_code="  x := 1;")
        assert "<vc-helpers>" not in result

    def test_template_with_no_placeholders_unchanged_except_code(self):
        template = "method Foo() { }"
        task = self._make_task_with_template(template)
        result = fill_template(task, generated_code="x := 1;")
        # No placeholder to replace — result equals original template
        assert result == template

    def test_returns_string(self):
        template = "method Foo() { <vc-code> }"
        task = self._make_task_with_template(template)
        result = fill_template(task, generated_code="x := 0;")
        assert isinstance(result, str)

    def test_preamble_preserved_in_template(self):
        template = "// preamble\nmethod Foo() { <vc-code> }"
        task = self._make_task_with_template(template)
        result = fill_template(task, generated_code="x := 1;")
        assert "// preamble" in result


# ── TestLoadBenchmarkSuite ─────────────────────────────────────────────────────


class TestLoadBenchmarkSuite:
    def test_auto_detects_jsonl_as_vericoding(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1, VERICODING_TASK_2])
        tasks = load_benchmark_suite(jsonl_path, source="auto")
        assert len(tasks) == 2
        assert all(t.source == "vericoding" for t in tasks)

    def test_auto_detects_directory_as_dafnybench(self, tmp_path):
        _write_dafnybench_dir(tmp_path, {"foo.dfy": "method Foo() {}"})
        tasks = load_benchmark_suite(tmp_path, source="auto")
        assert len(tasks) == 1
        assert tasks[0].source == "dafnybench"

    def test_explicit_source_vericoding(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_benchmark_suite(jsonl_path, source="vericoding")
        assert tasks[0].source == "vericoding"

    def test_explicit_source_dafnybench(self, tmp_path):
        _write_dafnybench_dir(tmp_path, {"foo.dfy": "method Foo() {}"})
        tasks = load_benchmark_suite(tmp_path, source="dafnybench")
        assert tasks[0].source == "dafnybench"

    def test_unknown_source_raises_value_error(self, tmp_path):
        some_path = tmp_path / "something.txt"
        some_path.write_text("hello")
        with pytest.raises(ValueError):
            load_benchmark_suite(some_path, source="unknown_format")

    def test_returns_list_of_benchmark_tasks(self, tmp_path):
        jsonl_path = _write_vericoding_jsonl(tmp_path, [VERICODING_TASK_1])
        tasks = load_benchmark_suite(jsonl_path)
        assert isinstance(tasks, list)
        assert all(isinstance(t, BenchmarkTask) for t in tasks)
