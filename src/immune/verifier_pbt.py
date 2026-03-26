"""Hypothesis property-based testing verification of invariant candidates.

Takes a candidate invariant and a function, then generates 1000+ random inputs
using Hypothesis to verify the invariant holds across all of them. Returns
PASS if no counterexample is found, FAIL with the counterexample if one is,
or ERROR for setup issues.

This is a statistical verification complement to CrossHair's symbolic approach:
CrossHair proves universality via Z3, Hypothesis gives high confidence via
volume testing with smart shrinking.

References:
- [REF-T03] Hypothesis — Property-Based Testing for Python
- [REF-C06] LLM-Driven Invariant Enrichment (upstream in pipeline)
- [REF-P10] PGS — PBT raises correction rates from 46.6% to 75.9%
"""

import ast
import inspect
import re
import textwrap
import typing
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from hypothesis import given, settings, HealthCheck, Phase, Verbosity
from hypothesis import strategies as st


class PBTVerdict(str, Enum):
    """Outcome of PBT verification. [REF-T03]"""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class PBTResult:
    """Result of Hypothesis PBT verification. [REF-T03]

    Attributes:
        verdict: The outcome of verification.
        num_examples: Number of test inputs generated.
        counterexample: If FAIL, the inputs that violated the invariant.
        error: If ERROR, a description of what went wrong.
    """
    verdict: PBTVerdict
    num_examples: int = 0
    counterexample: Optional[dict] = None
    error: Optional[str] = None


# Mapping from Python type annotations to Hypothesis strategies [REF-T03]
_TYPE_STRATEGY_MAP: dict[type, Any] = {
    int: st.integers(),
    float: st.floats(allow_nan=False, allow_infinity=False),
    str: st.text(max_size=100),
    bool: st.booleans(),
    bytes: st.binary(max_size=100),
    list: st.lists(st.integers(), max_size=20),
    dict: st.dictionaries(st.text(max_size=10), st.integers(), max_size=10),
    tuple: st.tuples(st.integers()),
    set: st.frozensets(st.integers(), max_size=20).map(set),
    type(None): st.none(),
}


def _type_to_strategy(type_annotation: Any) -> Any:
    """Convert a Python type annotation to a Hypothesis strategy. [REF-T03]

    Handles basic types, Optional, List, Dict, and falls back to
    st.from_type for complex annotations.
    """
    if type_annotation is inspect.Parameter.empty or type_annotation is None:
        # No type annotation — default to integers
        return st.integers()

    # Handle string annotations
    if isinstance(type_annotation, str):
        simple_map = {
            "int": st.integers(),
            "float": st.floats(allow_nan=False, allow_infinity=False),
            "str": st.text(max_size=100),
            "bool": st.booleans(),
            "list": st.lists(st.integers(), max_size=20),
            "dict": st.dictionaries(st.text(max_size=10), st.integers(), max_size=10),
        }
        return simple_map.get(type_annotation, st.integers())

    # Direct type match
    if type_annotation in _TYPE_STRATEGY_MAP:
        return _TYPE_STRATEGY_MAP[type_annotation]

    # Try from_type as fallback
    try:
        return st.from_type(type_annotation)
    except Exception:
        return st.integers()


def _extract_param_types(func_source: str, func_name: str) -> dict[str, Any]:
    """Extract parameter names and type annotations from function source.

    Parses the function AST to get parameter types for strategy generation.
    """
    try:
        tree = ast.parse(textwrap.dedent(func_source))
    except SyntaxError:
        return {}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            params = {}
            for arg in node.args.args:
                name = arg.arg
                if arg.annotation:
                    # Get the annotation as a string and resolve to type
                    ann_str = ast.literal_eval(arg.annotation) if isinstance(arg.annotation, ast.Constant) else ast.unparse(arg.annotation)
                    params[name] = ann_str
                else:
                    params[name] = None
            return params

    return {}


def _build_strategies(param_types: dict[str, Any]) -> dict[str, Any]:
    """Build Hypothesis strategies for each parameter. [REF-T03]"""
    strategies = {}
    for name, type_ann in param_types.items():
        strategies[name] = _type_to_strategy(type_ann)
    return strategies


def verify_invariant_pbt(
    func_source: str,
    func_name: str,
    invariant: str,
    preconditions: Optional[list[str]] = None,
    max_examples: int = 1000,
) -> PBTResult:
    """Verify an invariant candidate using Hypothesis PBT.

    Compiles the function source, generates random inputs via Hypothesis,
    calls the function, and checks the invariant against each result.
    Preconditions filter out invalid inputs via assume().

    Args:
        func_source: Python source code of the function under test.
        func_name: Name of the function to verify.
        invariant: Python expression using 'result' for return value and
            parameter names for inputs.
        preconditions: Optional list of Python expressions that filter inputs.
        max_examples: Number of random inputs to generate. [REF-T03]

    Returns:
        PBTResult with verdict, example count, and optional counterexample/error.

    References:
        [REF-T03] Hypothesis — property-based testing
        [REF-P10] PGS — PBT validation approach
    """
    if not invariant or not invariant.strip():
        return PBTResult(
            verdict=PBTVerdict.ERROR,
            error="Invariant expression is empty",
        )

    if not func_source or not func_source.strip():
        return PBTResult(
            verdict=PBTVerdict.ERROR,
            error="Function source is empty",
        )

    preconditions = preconditions or []

    # Compile the function
    try:
        namespace: dict[str, Any] = {}
        exec(compile(textwrap.dedent(func_source), "<immune_pbt>", "exec"), namespace)
    except SyntaxError as e:
        return PBTResult(
            verdict=PBTVerdict.ERROR,
            error=f"Syntax error in function source: {e}",
        )
    except Exception as e:
        return PBTResult(
            verdict=PBTVerdict.ERROR,
            error=f"Failed to compile function: {type(e).__name__}: {e}",
        )

    func = namespace.get(func_name)
    if func is None:
        return PBTResult(
            verdict=PBTVerdict.ERROR,
            error=f"Function '{func_name}' not found in source",
        )

    # Extract parameter types and build strategies
    param_types = _extract_param_types(func_source, func_name)
    if not param_types:
        # Function has no parameters
        try:
            result = func()
            local_ns = {"result": result}
            if not eval(invariant, {"__builtins__": {}}, local_ns):
                return PBTResult(
                    verdict=PBTVerdict.FAIL,
                    counterexample={},
                    num_examples=1,
                )
            return PBTResult(verdict=PBTVerdict.PASS, num_examples=1)
        except Exception as e:
            return PBTResult(
                verdict=PBTVerdict.ERROR,
                error=f"Error calling function: {type(e).__name__}: {e}",
            )

    strategies = _build_strategies(param_types)

    # Run the PBT verification [REF-T03]
    example_count = 0
    counterexample_found: Optional[dict] = None
    error_found: Optional[str] = None

    def check_invariant(**kwargs: Any) -> None:
        nonlocal example_count, counterexample_found
        from hypothesis import assume

        # Apply preconditions as Hypothesis assume() filters
        for pre in preconditions:
            try:
                if not eval(pre, {"__builtins__": {}}, kwargs):
                    assume(False)
                    return
            except Exception:
                assume(False)
                return

        example_count += 1

        # Call the function
        call_result = func(**kwargs)

        # Check the invariant — 'result' maps to return value,
        # param names map to input values
        local_ns = dict(kwargs)
        local_ns["result"] = call_result

        if not eval(invariant, {"__builtins__": {}}, local_ns):
            counterexample_found = dict(kwargs)
            counterexample_found["__result__"] = repr(call_result)
            raise AssertionError(
                f"Invariant '{invariant}' violated: {counterexample_found}"
            )

    # Build the @given decorator dynamically [REF-T03]
    decorated = given(**strategies)(
        settings(
            max_examples=max_examples,
            deadline=None,
            suppress_health_check=[
                HealthCheck.too_slow,
                HealthCheck.filter_too_much,
            ],
            phases=[Phase.generate],  # skip shrinking for speed in verification
            verbosity=Verbosity.quiet,
        )(check_invariant)
    )

    try:
        decorated()
        return PBTResult(verdict=PBTVerdict.PASS, num_examples=example_count)
    except AssertionError:
        return PBTResult(
            verdict=PBTVerdict.FAIL,
            counterexample=counterexample_found,
            num_examples=example_count,
        )
    except Exception as e:
        return PBTResult(
            verdict=PBTVerdict.ERROR,
            error=f"PBT execution error: {type(e).__name__}: {e}",
            num_examples=example_count,
        )
