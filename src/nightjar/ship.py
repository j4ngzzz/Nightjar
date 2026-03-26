"""Artifact signing with provenance — nightjar ship.

After a successful build (generate + verify + compile), computes the
SHA-256 hash of the output artifact and writes provenance metadata
to .card/verify.json. This creates an auditable record tying the
generated code to the model, verification results, and timestamp.

References:
- [REF-C07] Don't Round-Trip — generated code is read-only
- [REF-C08] Sealed Dependency Manifest — deps.lock integrity
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Provenance:
    """Provenance metadata for a shipped artifact.

    Records everything needed to reproduce or audit a build:
    which model generated the code, whether verification passed,
    and the SHA-256 hash of the output artifact.
    """

    artifact_hash: str
    model: str
    verified: bool
    stages_passed: int
    stages_total: int
    target: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSON output."""
        return {
            "artifact_hash": self.artifact_hash,
            "model": self.model,
            "verified": self.verified,
            "stages_passed": self.stages_passed,
            "stages_total": self.stages_total,
            "target": self.target,
            "timestamp": self.timestamp,
        }


def hash_artifact(path: str) -> str:
    """Compute SHA-256 hash of a build artifact (file or directory).

    For a single file, hashes its content directly. For a directory,
    hashes all files sorted by relative path for determinism.

    Args:
        path: Path to the artifact file or directory.

    Returns:
        Hex-encoded SHA-256 hash, or empty string if path doesn't exist.
    """
    target = Path(path)
    if not target.exists():
        return ""

    hasher = hashlib.sha256()

    if target.is_file():
        hasher.update(target.read_bytes())
    elif target.is_dir():
        # Hash all files sorted by relative path for determinism
        for file_path in sorted(target.rglob("*")):
            if file_path.is_file():
                # Include the relative path in the hash for structure sensitivity
                rel = file_path.relative_to(target).as_posix()
                hasher.update(rel.encode("utf-8"))
                hasher.update(file_path.read_bytes())

    return hasher.hexdigest()


def build_provenance(
    artifact_path: str,
    model: str,
    verified: bool,
    stages_passed: int,
    stages_total: int,
    target: str,
) -> Provenance:
    """Build provenance metadata from verification results and artifact.

    Args:
        artifact_path: Path to the build artifact to hash.
        model: LLM model name used for generation.
        verified: Whether all verification stages passed.
        stages_passed: Number of stages that passed.
        stages_total: Total number of stages run.
        target: Compilation target language.

    Returns:
        Provenance with computed artifact hash and timestamp.
    """
    artifact_hash = hash_artifact(artifact_path)
    return Provenance(
        artifact_hash=artifact_hash,
        model=model,
        verified=verified,
        stages_passed=stages_passed,
        stages_total=stages_total,
        target=target,
    )


def write_provenance(provenance: Provenance, output_path: str) -> None:
    """Write provenance metadata to a JSON file.

    Creates parent directories if needed. Output is pretty-printed
    for human readability and git diff friendliness.

    Args:
        provenance: The provenance metadata to write.
        output_path: Path to the output JSON file (typically .card/verify.json).
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(provenance.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
