"""icontract runtime enforcement of verified invariants.

Takes verified invariants and generates icontract @require/@ensure decorators
that are injected into generated code as runtime guards. These decorators fire
in production and feed back into the immune system's collection loop when
violations occur.

The icontract library provides informative violation messages that include
the violated condition and the actual values, which makes them ideal for
feeding back into the invariant mining pipeline.

References:
- [REF-T10] icontract — Python Design by Contract (@require, @ensure, @invariant)
- [REF-C09] Immune System / Acquired Immunity — runtime enforcement stage
"""

import re
import textwrap
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InvariantSpec:
    """Specification for a single invariant to enforce. [REF-T10]

    Attributes:
        expression: Python expression (e.g., 'result >= 0' or 'x > 0').
        explanation: Human-readable explanation.
        is_precondition: If True, becomes @require; if False, @ensure.
            Auto-detected if not explicitly set: expressions containing
            'result' are postconditions, others are preconditions.
    """
    expression: str
    explanation: str = ""
    _is_precondition: Optional[bool] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._is_precondition is None:
            # Auto-detect: 'result' in expression → postcondition
            self._is_precondition = not bool(
                re.search(r'\bresult\b', self.expression)
            )

    @property
    def is_precondition(self) -> bool:
        return self._is_precondition  # type: ignore[return-value]

    @is_precondition.setter
    def is_precondition(self, value: bool) -> None:
        self._is_precondition = value

    def __init__(
        self,
        expression: str,
        explanation: str = "",
        is_precondition: Optional[bool] = None,
    ) -> None:
        self.expression = expression
        self.explanation = explanation
        self._is_precondition = is_precondition
        self.__post_init__()


def parse_invariant_to_contract(
    expression: str,
    explanation: str = "",
) -> str:
    """Convert an invariant expression to an icontract decorator string.

    Determines whether the expression is a precondition (@require) or
    postcondition (@ensure) based on whether it references 'result'.

    For @ensure decorators, 'result' is mapped to icontract's 'result'
    parameter which captures the return value. [REF-T10]

    Args:
        expression: Python boolean expression.
        explanation: Optional human-readable description.

    Returns:
        A string containing the icontract decorator (e.g.,
        '@icontract.ensure(lambda result: result >= 0, "Non-negative")').
    """
    has_result = bool(re.search(r'\bresult\b', expression))

    if has_result:
        # Postcondition — use @ensure with result parameter [REF-T10]
        # Extract parameter names from expression (excluding 'result')
        params = _extract_lambda_params(expression, include_result=True)
        lambda_str = f"lambda {params}: {expression}"
        decorator_type = "ensure"
    else:
        # Precondition — use @require [REF-T10]
        params = _extract_lambda_params(expression, include_result=False)
        lambda_str = f"lambda {params}: {expression}"
        decorator_type = "require"

    if explanation:
        return f'@icontract.{decorator_type}({lambda_str}, "{explanation}")'
    return f"@icontract.{decorator_type}({lambda_str})"


def _extract_lambda_params(expression: str, include_result: bool = False) -> str:
    """Extract variable names from an expression for the lambda signature.

    Finds all identifiers in the expression that could be function parameters.
    Excludes Python builtins and common functions.
    """
    # Find all identifiers
    identifiers = set(re.findall(r'\b([a-zA-Z_]\w*)\b', expression))

    # Remove Python builtins, keywords, and common functions
    excluded = {
        'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
        'len', 'abs', 'min', 'max', 'sum', 'int', 'float', 'str',
        'bool', 'list', 'dict', 'set', 'tuple', 'isinstance', 'type',
        'range', 'sorted', 'reversed', 'enumerate', 'zip', 'map',
        'filter', 'any', 'all', 'print', 'hasattr', 'getattr',
    }

    params = sorted(identifiers - excluded)

    if not include_result and 'result' in params:
        params.remove('result')

    return ", ".join(params) if params else "_"


def generate_enforced_source(
    func_source: str,
    func_name: str,
    invariants: list[InvariantSpec],
) -> str:
    """Generate source code with icontract decorators injected.

    Takes the original function source and a list of verified invariants,
    then produces new source with:
    1. An 'import icontract' statement at the top
    2. @icontract.require decorators for preconditions (before the def)
    3. @icontract.ensure decorators for postconditions (before the def)

    The function body remains unchanged. [REF-T10]

    Args:
        func_source: Original Python source code of the function.
        func_name: Name of the function to decorate.
        invariants: List of InvariantSpec objects to enforce.

    Returns:
        Modified source code with icontract decorators injected.
    """
    source = textwrap.dedent(func_source).rstrip()
    lines = source.split("\n")

    # Find the def line
    def_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {func_name}(") or line.strip().startswith(f"def {func_name} ("):
            def_idx = i
            break

    if def_idx == -1:
        # Function not found — return with import only
        return f"import icontract\n\n{source}\n"

    # Determine indentation of the def line
    def_line = lines[def_idx]
    indent = def_line[:len(def_line) - len(def_line.lstrip())]

    # Build decorator lines — preconditions first, then postconditions [REF-T10]
    pre_decorators = []
    post_decorators = []

    for inv in invariants:
        decorator = parse_invariant_to_contract(inv.expression, inv.explanation)
        if inv.is_precondition:
            pre_decorators.append(f"{indent}{decorator}")
        else:
            post_decorators.append(f"{indent}{decorator}")

    # Insert decorators before the def line (preconditions first)
    all_decorators = pre_decorators + post_decorators
    new_lines = (
        ["import icontract", ""]
        + lines[:def_idx]
        + all_decorators
        + lines[def_idx:]
    )

    return "\n".join(new_lines) + "\n"
