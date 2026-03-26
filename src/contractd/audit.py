"""Audit branch system — read-only archive of generated code.

After a successful build, generated code is copied to .card/audit/
with a header comment and read-only permissions. This creates a
git-trackable compliance record of every verified generation.

The audit directory is the ONLY place generated code is stored.
Files here are NEVER manually edited [REF-C07]. All changes go
through .card.md specs and the regeneration pipeline.

References:
- [REF-C07] Don't Round-Trip — generated code marked "DO NOT EDIT"
"""

import hashlib
import os
import shutil
import stat
from pathlib import Path

# Target extension map (target name → file extension)
_TARGET_EXTENSIONS: dict[str, str] = {
    "py": ".py",
    "js": ".js",
    "ts": ".ts",
    "go": ".go",
    "java": ".java",
    "cs": ".cs",
    "dfy": ".dfy",
}

# Header comment templates by language
_HEADER_TEMPLATES: dict[str, str] = {
    ".py": "# GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n# Regenerate with: contractd build\n",
    ".js": "// GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n// Regenerate with: contractd build\n",
    ".ts": "// GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n// Regenerate with: contractd build\n",
    ".go": "// GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n// Regenerate with: contractd build\n",
    ".java": "// GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n// Regenerate with: contractd build\n",
    ".cs": "// GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n// Regenerate with: contractd build\n",
    ".dfy": "// GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n// Regenerate with: contractd build\n",
}


def get_audit_path(module_id: str, target: str, audit_dir: str) -> str:
    """Get the expected path for a module's audit file.

    Args:
        module_id: The module identifier (e.g., 'payment').
        target: The target language/extension (e.g., 'py', 'dfy').
        audit_dir: Path to the audit directory.

    Returns:
        Full path to the audit file.
    """
    ext = _TARGET_EXTENSIONS.get(target, f".{target}")
    return str(Path(audit_dir) / f"{module_id}{ext}")


def archive_artifact(
    source_path: str,
    module_id: str,
    target: str,
    audit_dir: str,
) -> bool:
    """Copy generated code to the audit directory as read-only.

    Adds a header comment indicating the file is generated and should
    not be manually edited [REF-C07]. Sets file permissions to read-only.

    Args:
        source_path: Path to the generated source file.
        module_id: The module identifier.
        target: Target language/extension.
        audit_dir: Path to the audit directory.

    Returns:
        True if archived successfully, False if source doesn't exist.
    """
    source = Path(source_path)
    if not source.exists():
        return False

    # Ensure audit directory exists
    audit_path = Path(audit_dir)
    audit_path.mkdir(parents=True, exist_ok=True)

    dest_path = Path(get_audit_path(module_id, target, audit_dir))

    # If dest exists and is read-only, make it writable first so we can overwrite
    if dest_path.exists():
        dest_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    # Read source content and prepend header
    content = source.read_text(encoding="utf-8")
    ext = dest_path.suffix
    header = _HEADER_TEMPLATES.get(ext, f"# GENERATED FROM SPEC — DO NOT EDIT [REF-C07]\n")

    # Only add header if not already present
    if "GENERATED FROM SPEC" not in content:
        content = header + "\n" + content

    # Write to audit location
    dest_path.write_text(content, encoding="utf-8")

    # Set read-only permissions (remove all write bits)
    dest_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    return True


def list_audited_modules(audit_dir: str) -> list[str]:
    """List all modules that have archived audit files.

    Args:
        audit_dir: Path to the audit directory.

    Returns:
        List of module names (stems, without extensions).
    """
    audit_path = Path(audit_dir)
    if not audit_path.exists() or not audit_path.is_dir():
        return []

    return sorted(f.stem for f in audit_path.iterdir() if f.is_file())


def is_audit_current(
    source_path: str,
    module_id: str,
    target: str,
    audit_dir: str,
) -> bool:
    """Check if the audit file matches the current generated artifact.

    Compares SHA-256 hashes of the source content (without header) against
    the audit file content (with header stripped). Returns False if either
    file is missing or the content differs.

    Args:
        source_path: Path to the current generated source.
        module_id: The module identifier.
        target: Target language/extension.
        audit_dir: Path to the audit directory.

    Returns:
        True if audit file exists and matches source content.
    """
    source = Path(source_path)
    audit_file = Path(get_audit_path(module_id, target, audit_dir))

    if not source.exists() or not audit_file.exists():
        return False

    source_content = source.read_text(encoding="utf-8")
    audit_content = audit_file.read_text(encoding="utf-8")

    # Hash source content
    source_hash = hashlib.sha256(source_content.encode("utf-8")).hexdigest()

    # Strip the header from audit content before hashing
    # The header is everything before the first blank line after any comment lines
    lines = audit_content.split("\n")
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
            content_start = i
            break
        if not stripped and i > 0:
            content_start = i + 1
            break

    audit_body = "\n".join(lines[content_start:])
    audit_hash = hashlib.sha256(audit_body.encode("utf-8")).hexdigest()

    return source_hash == audit_hash
