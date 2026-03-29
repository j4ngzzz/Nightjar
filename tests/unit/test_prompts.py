"""Tests for versioned prompt templates.

Validates that LLM prompts are externalized into versioned files with
metadata (version, pass_rate, last_optimized). Generator loads the
latest best-performing version.

References:
- [REF-C03] Analyst → Formalizer → Coder pipeline
- [REF-P07] ReDeFo multi-agent architecture
- [REF-T26] DSPy — prompt optimization framework (inspiration)
"""

import json
import os
import time

import pytest

from nightjar.prompts import (
    PromptTemplate,
    PromptRegistry,
    get_template,
    list_templates,
    get_best_template,
    register_template,
    update_pass_rate,
)


@pytest.fixture
def registry_path(tmp_path):
    return str(tmp_path / "prompts")


@pytest.fixture
def registry(registry_path):
    return PromptRegistry(registry_path)


class TestPromptTemplate:
    """Tests for the PromptTemplate data class."""

    def test_create_template(self):
        tpl = PromptTemplate(
            name="analyst",
            version=1,
            system_prompt="You are an analyst.",
            user_prompt_template="Analyze: {spec_context}",
            pass_rate=0.0,
            last_optimized=0.0,
        )
        assert tpl.name == "analyst"
        assert tpl.version == 1

    def test_template_to_dict(self):
        tpl = PromptTemplate(
            name="analyst",
            version=1,
            system_prompt="System",
            user_prompt_template="User: {spec_context}",
            pass_rate=0.85,
            last_optimized=1000.0,
        )
        d = tpl.to_dict()
        assert d["name"] == "analyst"
        assert d["version"] == 1
        assert d["pass_rate"] == 0.85

    def test_template_from_dict(self):
        d = {
            "name": "coder",
            "version": 2,
            "system_prompt": "You are a coder.",
            "user_prompt_template": "Code: {dafny_skeleton}",
            "pass_rate": 0.92,
            "last_optimized": 2000.0,
        }
        tpl = PromptTemplate.from_dict(d)
        assert tpl.name == "coder"
        assert tpl.version == 2
        assert tpl.pass_rate == 0.92


class TestPromptRegistry:
    """Tests for the prompt registry."""

    def test_creates_directory(self, registry_path):
        PromptRegistry(registry_path)
        assert os.path.isdir(registry_path)

    def test_register_and_get(self, registry):
        tpl = PromptTemplate(
            name="analyst",
            version=1,
            system_prompt="You are an analyst.",
            user_prompt_template="Analyze: {spec_context}",
            pass_rate=0.0,
            last_optimized=time.time(),
        )
        registry.register(tpl)
        loaded = registry.get("analyst", version=1)
        assert loaded is not None
        assert loaded.name == "analyst"
        assert loaded.system_prompt == "You are an analyst."

    def test_get_nonexistent(self, registry):
        assert registry.get("nonexistent", version=1) is None

    def test_register_multiple_versions(self, registry):
        for v in range(1, 4):
            tpl = PromptTemplate(
                name="analyst",
                version=v,
                system_prompt=f"System v{v}",
                user_prompt_template="Analyze: {spec_context}",
                pass_rate=v * 0.1,
                last_optimized=time.time(),
            )
            registry.register(tpl)

        v1 = registry.get("analyst", version=1)
        v3 = registry.get("analyst", version=3)
        assert v1.system_prompt == "System v1"
        assert v3.system_prompt == "System v3"

    def test_list_templates(self, registry):
        for name in ["analyst", "formalizer", "coder"]:
            tpl = PromptTemplate(
                name=name,
                version=1,
                system_prompt=f"System {name}",
                user_prompt_template=f"Do: {{spec_context}}",
                pass_rate=0.0,
                last_optimized=time.time(),
            )
            registry.register(tpl)

        names = registry.list_templates()
        assert set(names) == {"analyst", "formalizer", "coder"}

    def test_get_best_template(self, registry):
        """Should return the version with highest pass_rate."""
        for v, rate in [(1, 0.5), (2, 0.9), (3, 0.7)]:
            tpl = PromptTemplate(
                name="analyst",
                version=v,
                system_prompt=f"System v{v}",
                user_prompt_template="Do: {spec_context}",
                pass_rate=rate,
                last_optimized=time.time(),
            )
            registry.register(tpl)

        best = registry.get_best("analyst")
        assert best is not None
        assert best.version == 2
        assert best.pass_rate == 0.9

    def test_get_best_no_templates(self, registry):
        assert registry.get_best("nonexistent") is None

    def test_update_pass_rate(self, registry):
        tpl = PromptTemplate(
            name="coder",
            version=1,
            system_prompt="Code.",
            user_prompt_template="Code: {dafny_skeleton}",
            pass_rate=0.5,
            last_optimized=time.time(),
        )
        registry.register(tpl)
        registry.update_pass_rate("coder", version=1, pass_rate=0.95)

        loaded = registry.get("coder", version=1)
        assert loaded.pass_rate == 0.95

    def test_get_latest_version(self, registry):
        """get with version=None should return the latest version."""
        for v in [1, 2, 3]:
            tpl = PromptTemplate(
                name="analyst",
                version=v,
                system_prompt=f"v{v}",
                user_prompt_template="{spec_context}",
                pass_rate=0.0,
                last_optimized=time.time(),
            )
            registry.register(tpl)

        latest = registry.get("analyst")
        assert latest is not None
        assert latest.version == 3

    def test_overwrite_existing_version(self, registry):
        """Re-registering same name+version overwrites."""
        tpl1 = PromptTemplate("a", 1, "old", "{x}", 0.1, 0.0)
        registry.register(tpl1)
        tpl2 = PromptTemplate("a", 1, "new", "{x}", 0.9, 0.0)
        registry.register(tpl2)

        loaded = registry.get("a", version=1)
        assert loaded.system_prompt == "new"
        assert loaded.pass_rate == 0.9


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_register_and_get_template(self, registry_path):
        tpl = PromptTemplate("analyst", 1, "Sys", "{x}", 0.0, 0.0)
        register_template(registry_path, tpl)
        loaded = get_template(registry_path, "analyst", version=1)
        assert loaded is not None
        assert loaded.name == "analyst"

    def test_list_templates_function(self, registry_path):
        register_template(
            registry_path,
            PromptTemplate("analyst", 1, "S", "{x}", 0.0, 0.0),
        )
        names = list_templates(registry_path)
        assert "analyst" in names

    def test_get_best_template_function(self, registry_path):
        register_template(
            registry_path,
            PromptTemplate("analyst", 1, "S", "{x}", 0.8, 0.0),
        )
        register_template(
            registry_path,
            PromptTemplate("analyst", 2, "S2", "{x}", 0.6, 0.0),
        )
        best = get_best_template(registry_path, "analyst")
        assert best.version == 1

    def test_update_pass_rate_function(self, registry_path):
        register_template(
            registry_path,
            PromptTemplate("coder", 1, "S", "{x}", 0.5, 0.0),
        )
        update_pass_rate(registry_path, "coder", 1, 0.99)
        loaded = get_template(registry_path, "coder", version=1)
        assert loaded.pass_rate == 0.99
