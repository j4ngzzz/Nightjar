"""Versioned prompt templates for the CARD generation pipeline.

Externalizes all LLM prompts into versioned, file-backed templates with
performance metadata (version, pass_rate, last_optimized). The generator
loads the latest best-performing version. DSPy SIMBA and AutoResearch
hill climbing create new versions with improved prompts.

References:
- [REF-C03] Analyst → Formalizer → Coder pipeline
- [REF-P07] ReDeFo multi-agent architecture
- [REF-T26] DSPy — prompt optimization framework
- [REF-P04] AlphaVerus — self-improving loop
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class PromptTemplate:
    """A versioned prompt template with performance metadata.

    Each template has a name (e.g. "analyst"), a version number,
    the system and user prompt strings, and performance tracking fields.

    References:
    - [REF-C03] Pipeline stage prompts
    - [REF-T26] DSPy optimization creates new versions
    """

    name: str
    version: int
    system_prompt: str
    user_prompt_template: str
    pass_rate: float
    last_optimized: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PromptTemplate":
        """Deserialize from dict."""
        return cls(
            name=d["name"],
            version=d["version"],
            system_prompt=d["system_prompt"],
            user_prompt_template=d["user_prompt_template"],
            pass_rate=d["pass_rate"],
            last_optimized=d["last_optimized"],
        )


class PromptRegistry:
    """File-backed registry of versioned prompt templates.

    Templates are stored as JSON files in a directory, one file per
    name+version combination: {name}_v{version}.json.

    References:
    - [REF-C03] Pipeline prompts are externalized here
    - [REF-T26] DSPy SIMBA writes new versions
    """

    def __init__(self, registry_path: str) -> None:
        self.registry_path = registry_path
        os.makedirs(registry_path, exist_ok=True)

    def _file_path(self, name: str, version: int) -> str:
        """Path to the JSON file for a specific template version."""
        return os.path.join(self.registry_path, f"{name}_v{version}.json")

    def register(self, template: PromptTemplate) -> None:
        """Save a prompt template to the registry.

        Overwrites if same name+version already exists.
        """
        path = self._file_path(template.name, template.version)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(template.to_dict(), f, indent=2)

    def get(self, name: str, version: int | None = None) -> PromptTemplate | None:
        """Load a prompt template by name and optional version.

        If version is None, returns the latest (highest version number).
        Returns None if not found.
        """
        if version is not None:
            path = self._file_path(name, version)
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                return PromptTemplate.from_dict(json.load(f))

        # Find latest version
        versions = self._get_versions(name)
        if not versions:
            return None
        return self.get(name, version=max(versions))

    def _get_versions(self, name: str) -> list[int]:
        """List all version numbers for a given template name."""
        prefix = f"{name}_v"
        versions = []
        for fname in os.listdir(self.registry_path):
            if fname.startswith(prefix) and fname.endswith(".json"):
                try:
                    v = int(fname[len(prefix):-5])
                    versions.append(v)
                except ValueError:
                    continue
        return sorted(versions)

    def list_templates(self) -> list[str]:
        """List unique template names in the registry."""
        names = set()
        for fname in os.listdir(self.registry_path):
            if fname.endswith(".json") and "_v" in fname:
                name = fname[:fname.rindex("_v")]
                names.add(name)
        return sorted(names)

    def get_best(self, name: str) -> PromptTemplate | None:
        """Get the version with the highest pass_rate for a given name.

        Returns None if no templates exist for that name.
        """
        versions = self._get_versions(name)
        if not versions:
            return None

        best = None
        best_rate = -1.0
        for v in versions:
            tpl = self.get(name, version=v)
            if tpl and tpl.pass_rate > best_rate:
                best = tpl
                best_rate = tpl.pass_rate
        return best

    def update_pass_rate(
        self, name: str, version: int, pass_rate: float
    ) -> None:
        """Update the pass_rate of an existing template."""
        tpl = self.get(name, version=version)
        if tpl is None:
            raise ValueError(f"Template {name} v{version} not found")
        tpl.pass_rate = pass_rate
        self.register(tpl)


# --- Module-level convenience functions ---


def register_template(registry_path: str, template: PromptTemplate) -> None:
    """Register a template. Convenience wrapper."""
    PromptRegistry(registry_path).register(template)


def get_template(
    registry_path: str, name: str, version: int | None = None
) -> PromptTemplate | None:
    """Get a template. Convenience wrapper."""
    return PromptRegistry(registry_path).get(name, version)


def list_templates(registry_path: str) -> list[str]:
    """List template names. Convenience wrapper."""
    return PromptRegistry(registry_path).list_templates()


def get_best_template(
    registry_path: str, name: str
) -> PromptTemplate | None:
    """Get best template by pass_rate. Convenience wrapper."""
    return PromptRegistry(registry_path).get_best(name)


def update_pass_rate(
    registry_path: str, name: str, version: int, pass_rate: float
) -> None:
    """Update pass_rate. Convenience wrapper."""
    PromptRegistry(registry_path).update_pass_rate(name, version, pass_rate)
