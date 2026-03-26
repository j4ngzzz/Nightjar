"""Tests for nightjar OWASP Security Invariant Pack.

TDD: Tests written FIRST before implementation.

Reference: Scout 7 Feature 1 + OWASP ASVS v5.0
Scout 7: 53% of AI code has OWASP violations. 86% XSS failure rate.
'No competitor offers formal proof of absence.'
Combined with F1+F2 = Nightjar Security Mode (Scout 7 S10).
"""
import pytest

from nightjar.security.owasp_pack import (
    OWASPCategory,
    OWASPInvariant,
    get_invariant,
    list_categories,
    generate_security_block,
)


class TestOWASPCategories:
    """Tests for OWASP category enumeration."""

    def test_sql_injection_category_exists(self):
        """OWASP pack includes SQL injection category."""
        categories = list_categories()
        assert OWASPCategory.SQL_INJECTION in categories

    def test_xss_category_exists(self):
        """OWASP pack includes XSS category."""
        categories = list_categories()
        assert OWASPCategory.XSS in categories

    def test_command_injection_category_exists(self):
        """OWASP pack includes command injection category."""
        categories = list_categories()
        assert OWASPCategory.COMMAND_INJECTION in categories

    def test_at_least_two_categories(self):
        """OWASP pack has at least SQL injection + XSS (Week 1 requirements)."""
        categories = list_categories()
        assert len(categories) >= 2


class TestOWASPInvariants:
    """Tests for OWASP invariant templates."""

    def test_get_sql_injection_invariant(self):
        """get_invariant returns an OWASPInvariant for SQL injection."""
        inv = get_invariant(OWASPCategory.SQL_INJECTION)
        assert isinstance(inv, OWASPInvariant)

    def test_sql_injection_invariant_has_description(self):
        """SQL injection invariant has a human-readable description."""
        inv = get_invariant(OWASPCategory.SQL_INJECTION)
        assert isinstance(inv.description, str)
        assert len(inv.description) > 10

    def test_sql_injection_invariant_has_icontract_template(self):
        """SQL injection invariant provides an icontract @require template."""
        inv = get_invariant(OWASPCategory.SQL_INJECTION)
        assert inv.icontract_template is not None
        assert "@require" in inv.icontract_template or "require" in inv.icontract_template

    def test_sql_injection_invariant_has_dafny_precondition(self):
        """SQL injection invariant provides a Dafny precondition template."""
        inv = get_invariant(OWASPCategory.SQL_INJECTION)
        assert inv.dafny_precondition is not None
        assert "requires" in inv.dafny_precondition

    def test_xss_invariant_has_icontract_template(self):
        """XSS invariant provides an icontract @ensure template."""
        inv = get_invariant(OWASPCategory.XSS)
        assert inv.icontract_template is not None

    def test_xss_invariant_has_description(self):
        """XSS invariant has a human-readable description."""
        inv = get_invariant(OWASPCategory.XSS)
        assert isinstance(inv.description, str)
        assert len(inv.description) > 10


class TestSQLInjectionInvariant:
    """Tests that SQL injection invariant catches unsanitized inputs."""

    def test_sql_injection_invariant_catches_unsanitized_input(self):
        """SQL injection invariant detects common SQL injection patterns.

        Scout 7: 'formally prove absence of SQL injection under ANY input'
        """
        from nightjar.security.owasp_pack import check_sql_injection

        # These are dangerous patterns that MUST be caught
        dangerous_inputs = [
            "' OR 1=1--",
            "'; DROP TABLE users;--",
            "1' UNION SELECT * FROM passwords--",
            "admin'--",
        ]
        for dangerous in dangerous_inputs:
            assert check_sql_injection(dangerous) is True, (
                f"check_sql_injection should detect: {dangerous!r}"
            )

    def test_sql_injection_safe_inputs_pass(self):
        """Safe inputs are not flagged as SQL injection."""
        from nightjar.security.owasp_pack import check_sql_injection

        safe_inputs = [
            "john.doe@example.com",
            "Hello World",
            "user123",
            "2024-01-01",
        ]
        for safe in safe_inputs:
            assert check_sql_injection(safe) is False, (
                f"check_sql_injection should NOT flag: {safe!r}"
            )


class TestXSSInvariant:
    """Tests that XSS invariant catches unescaped output."""

    def test_xss_invariant_catches_unescaped_output(self):
        """XSS invariant detects unescaped HTML/JS in output.

        Scout 7: '86% XSS failure rate in AI-generated code'
        """
        from nightjar.security.owasp_pack import check_xss

        dangerous_outputs = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:void(0)",
            "<svg onload=alert(1)>",
        ]
        for dangerous in dangerous_outputs:
            assert check_xss(dangerous) is True, (
                f"check_xss should detect: {dangerous!r}"
            )

    def test_xss_safe_outputs_pass(self):
        """Safe (properly escaped) outputs are not flagged."""
        from nightjar.security.owasp_pack import check_xss

        safe_outputs = [
            "&lt;script&gt;",
            "Hello World",
            "user@example.com",
            "1234",
        ]
        for safe in safe_outputs:
            assert check_xss(safe) is False, (
                f"check_xss should NOT flag: {safe!r}"
            )


class TestSecurityBlock:
    """Tests for generate_security_block() — .card.md security section generation."""

    def test_generate_security_block_returns_string(self):
        """generate_security_block returns a YAML string."""
        block = generate_security_block(
            categories=[OWASPCategory.SQL_INJECTION, OWASPCategory.XSS]
        )
        assert isinstance(block, str)

    def test_generate_security_block_includes_category_names(self):
        """Security block mentions included OWASP categories."""
        block = generate_security_block(
            categories=[OWASPCategory.SQL_INJECTION, OWASPCategory.XSS]
        )
        assert "sql" in block.lower() or "injection" in block.lower()
        assert "xss" in block.lower() or "cross" in block.lower()

    def test_generate_security_block_empty_categories(self):
        """generate_security_block handles empty category list gracefully."""
        block = generate_security_block(categories=[])
        assert isinstance(block, str)
