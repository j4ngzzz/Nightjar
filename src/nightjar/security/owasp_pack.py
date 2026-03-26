"""OWASP Security Invariant Pack for Nightjar.

Provides a library of OWASP Top 10 invariant templates that auto-inject into
any .card.md spec. For each OWASP category, a formal invariant pattern that
is IMPOSSIBLE to violate in generated code (when Dafny proves it).

Week 1 priorities (Scout 7 build plan): SQL Injection + XSS.
Week 2: remaining OWASP categories.

The holy shit moment:
  'Our AI-generated login function is formally proven to have no SQL injection
   vulnerability. Here is the mathematical proof.'

References:
- Scout 7 Feature 1 — OWASP Security Invariant Pack
- OWASP ASVS v5.0: https://owasp.org/www-project-application-security-verification-standard/
- Scout 7 Section 10 — Nightjar Security Mode bundle
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OWASPCategory(str, Enum):
    """OWASP Top 10 vulnerability categories.

    Priority order follows Scout 7 build plan:
    Week 1 = SQL_INJECTION + XSS (highest AI code failure rates).
    """

    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    BROKEN_AUTH = "broken_auth"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    XXEID = "xxe_injection"
    BROKEN_ACCESS = "broken_access_control"
    SECURITY_MISCONFIGURATION = "security_misconfiguration"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    USING_KNOWN_VULN_COMPONENTS = "known_vulnerable_components"


@dataclass
class OWASPInvariant:
    """Formal invariant template for a single OWASP category.

    Provides icontract and Dafny templates for injection into .card.md specs.
    """

    category: OWASPCategory
    description: str
    icontract_template: str  # Python icontract @require/@ensure snippet
    dafny_precondition: str  # Dafny requires clause
    asvs_reference: str      # OWASP ASVS v5.0 section reference


# ── SQL Injection (OWASP A03:2021) ───────────────────────
# ASVS v5.0 Section V5 (Input Validation and Sanitization)
# Formally prove: NO raw user input reaches a SQL query string.
_SQL_INJECTION_INVARIANT = OWASPInvariant(
    category=OWASPCategory.SQL_INJECTION,
    description=(
        "SQL Injection prevention: all query parameters must be sanitized. "
        "Raw user input MUST NOT appear directly in SQL query strings. "
        "Use parameterized queries or ORM methods exclusively. "
        "[OWASP ASVS v5.0, V5.3 Output Encoding and Injection Prevention]"
    ),
    icontract_template=(
        "@require(lambda query_params: all(\n"
        "    not _contains_sql_metachar(p) for p in query_params\n"
        "), 'SQL injection: unsanitized parameter detected')"
    ),
    dafny_precondition=(
        "requires forall p :: p in queryParams ==> IsSanitized(p)"
    ),
    asvs_reference="OWASP ASVS v5.0 V5.3.4 — SQL injection prevention",
)

# ── XSS (OWASP A03:2021) ─────────────────────────────────
# ASVS v5.0 Section V5 (Output Encoding)
# Formally prove: NO unescaped HTML/JS appears in rendered output.
_XSS_INVARIANT = OWASPInvariant(
    category=OWASPCategory.XSS,
    description=(
        "Cross-Site Scripting (XSS) prevention: all user-controlled data "
        "MUST be HTML-escaped before rendering. Output MUST NOT contain "
        "raw <script>, onerror=, or javascript: patterns. "
        "[OWASP ASVS v5.0, V5.3.3 Output Encoding]"
    ),
    icontract_template=(
        "@ensure(lambda result: not _contains_xss_pattern(result),\n"
        "    'XSS: unescaped HTML/JS in output')"
    ),
    dafny_precondition=(
        "ensures !ContainsXSSPattern(output)"
    ),
    asvs_reference="OWASP ASVS v5.0 V5.3.3 — XSS output encoding",
)

# ── Command Injection (OWASP A03:2021) ───────────────────
_COMMAND_INJECTION_INVARIANT = OWASPInvariant(
    category=OWASPCategory.COMMAND_INJECTION,
    description=(
        "Command Injection prevention: no user-controlled input may appear "
        "unescaped in shell commands. Use allowlist validation and "
        "shlex.quote() for any shell-bound strings. "
        "[OWASP ASVS v5.0, V5.3.8 — OS Command Injection]"
    ),
    icontract_template=(
        "@require(lambda cmd_args: all(\n"
        "    _is_allowlisted(arg) for arg in cmd_args\n"
        "), 'Command injection: unapproved command argument')"
    ),
    dafny_precondition=(
        "requires forall a :: a in cmdArgs ==> IsAllowlisted(a)"
    ),
    asvs_reference="OWASP ASVS v5.0 V5.3.8 — OS command injection prevention",
)

# ── Registry: category → invariant ───────────────────────
_INVARIANT_REGISTRY: dict[OWASPCategory, OWASPInvariant] = {
    OWASPCategory.SQL_INJECTION: _SQL_INJECTION_INVARIANT,
    OWASPCategory.XSS: _XSS_INVARIANT,
    OWASPCategory.COMMAND_INJECTION: _COMMAND_INJECTION_INVARIANT,
}


# ── SQL injection detection ───────────────────────────────
# Pattern-based detection for the check_sql_injection() helper.
# Detects common SQL metacharacter patterns used in injection attacks.
# NOTE: This is a DETECTION helper for testing/validation, NOT a sanitizer.
# Production code must use parameterized queries.

_SQL_METACHAR_PATTERN = re.compile(
    r"(?:'|--|;|/\*|\*/|xp_|UNION\s+SELECT|OR\s+\d+=\d+|AND\s+\d+=\d+)",
    re.IGNORECASE,
)


def check_sql_injection(value: str) -> bool:
    """Detect SQL injection metacharacters in a string.

    Used to verify the SQL injection invariant catches dangerous inputs.
    Returns True if the value contains SQL injection patterns.

    Security note: This is pattern-based detection for testing. In production,
    ALWAYS use parameterized queries — never sanitize by pattern matching.

    Args:
        value: String to check for SQL injection patterns.

    Returns:
        True if SQL injection patterns detected, False if safe.
    """
    return bool(_SQL_METACHAR_PATTERN.search(value))


def _contains_sql_metachar(value: str) -> bool:
    """Internal alias used in icontract template strings."""
    return check_sql_injection(value)


# ── XSS detection ────────────────────────────────────────
# Detects unescaped HTML/JS patterns in output strings.

_XSS_PATTERN = re.compile(
    r"(?:<script|onerror\s*=|onload\s*=|javascript:|<img[^>]+on\w+\s*=|<svg[^>]+on\w+\s*=)",
    re.IGNORECASE,
)


def check_xss(value: str) -> bool:
    """Detect unescaped XSS patterns in an output string.

    Used to verify the XSS invariant catches dangerous outputs.
    Returns True if the value contains XSS-exploitable patterns.

    Args:
        value: Output string to check for XSS patterns.

    Returns:
        True if XSS patterns detected, False if safe.
    """
    return bool(_XSS_PATTERN.search(value))


def _contains_xss_pattern(value: str) -> bool:
    """Internal alias used in icontract template strings."""
    return check_xss(value)


# ── Public API ────────────────────────────────────────────


def get_invariant(category: OWASPCategory) -> OWASPInvariant:
    """Get the OWASP invariant template for a category.

    Args:
        category: OWASP vulnerability category.

    Returns:
        OWASPInvariant with description, icontract template, and Dafny precondition.

    Raises:
        KeyError: If the category is not yet implemented (future categories).
    """
    return _INVARIANT_REGISTRY[category]


def list_categories() -> list[OWASPCategory]:
    """List all implemented OWASP invariant categories.

    Returns:
        List of OWASPCategory values with available invariants.
        Priority order: SQL_INJECTION, XSS, COMMAND_INJECTION (Week 1+2).
    """
    return list(_INVARIANT_REGISTRY.keys())


def generate_security_block(categories: list[OWASPCategory]) -> str:
    """Generate a YAML security: block for insertion into a .card.md spec.

    Produces the `security:` section that auto-injects OWASP invariants
    into the verification pipeline when running `nightjar verify`.

    Args:
        categories: List of OWASP categories to enable.

    Returns:
        YAML string for the security: block in .card.md.

    References:
        Scout 7 Feature 1 — 'Templates cover: SQL injection, XSS, command injection'
    """
    if not categories:
        return "security:\n  # No OWASP categories enabled\n  enabled: []\n"

    lines = ["security:"]
    lines.append("  # Nightjar Security Mode — OWASP invariant pack")
    lines.append("  # Formally proves absence of selected vulnerability categories")
    lines.append("  enabled:")

    for cat in categories:
        try:
            inv = get_invariant(cat)
            lines.append(f"    - {cat.value}  # {inv.asvs_reference}")
        except KeyError:
            lines.append(f"    - {cat.value}  # (not yet implemented)")

    lines.append("")
    lines.append("  # Reference: OWASP ASVS v5.0")
    lines.append(
        "  # https://owasp.org/www-project-application-security-verification-standard/"
    )

    return "\n".join(lines) + "\n"
