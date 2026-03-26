"""Experience replay store for successful generation+verification runs.

When generation + verification succeeds, stores the (spec, prompt,
generated_code, verification_result) tuple. On future generation for
similar specs, retrieves top-K successful examples as few-shot context
using TF-IDF cosine similarity.

References:
- [REF-C06] LLM-driven invariant enrichment — few-shot from past successes
- [REF-P04] AlphaVerus — self-improving loop uses replay of successful runs
- [REF-P15] Agentic PBT — experience-driven property generation
"""

import json
import math
import re
import sqlite3
import time
from collections import Counter
from typing import Any


def _tokenize(text: str) -> list[str]:
    """Simple whitespace+punctuation tokenizer for TF-IDF.

    Lowercases and splits on non-alphanumeric characters.
    Filters out single-character tokens.
    """
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return [t for t in tokens if len(t) > 1]


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency: count / total tokens."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {term: count / total for term, count in counts.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF-IDF vectors."""
    common_terms = set(vec_a.keys()) & set(vec_b.keys())
    if not common_terms:
        return 0.0

    dot_product = sum(vec_a[t] * vec_b[t] for t in common_terms)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class ReplayStore:
    """SQLite-backed experience replay for successful verification runs.

    Stores successful (spec, prompt, code, result) tuples and retrieves
    the most similar past successes as few-shot context for new generation.

    Similarity is computed via TF-IDF cosine on the combined spec_text + prompt.

    References:
    - [REF-C06] LLM enrichment with few-shot examples
    - [REF-P04] AlphaVerus self-improving loop
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create the successes table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS successes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spec_id TEXT NOT NULL,
                    spec_text TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    generated_code TEXT NOT NULL,
                    verification_result_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_successes_spec_id
                ON successes(spec_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def store_success(
        self,
        spec_id: str,
        spec_text: str,
        prompt: str,
        generated_code: str,
        verification_result: dict[str, Any],
    ) -> int:
        """Store a successful generation+verification tuple. Returns entry ID.

        Args:
            spec_id: The .card.md module identifier.
            spec_text: Full spec text.
            prompt: The prompt sent to the LLM.
            generated_code: The generated code that passed verification.
            verification_result: The verification result dict.

        Returns:
            The auto-incremented entry ID.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO successes
                   (spec_id, spec_text, prompt, generated_code,
                    verification_result_json, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    spec_id,
                    spec_text,
                    prompt,
                    generated_code,
                    json.dumps(verification_result),
                    time.time(),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def retrieve_similar(
        self, query: str, k: int = 3
    ) -> list[dict[str, Any]]:
        """Retrieve top-K similar past successes for few-shot context.

        Uses TF-IDF cosine similarity between the query and the
        combined spec_text + prompt of each stored entry.

        Args:
            query: The search query (typically the current spec or intent).
            k: Maximum number of results to return.

        Returns:
            List of dicts with spec_id, spec_text, prompt, generated_code,
            verification_result, and similarity score. Ordered by
            similarity descending.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT id, spec_id, spec_text, prompt, generated_code,
                          verification_result_json
                   FROM successes"""
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return []

        query_tokens = _tokenize(query)
        query_tf = _compute_tf(query_tokens)

        scored = []
        for row in rows:
            doc_text = f"{row[2]} {row[3]}"  # spec_text + prompt
            doc_tokens = _tokenize(doc_text)
            doc_tf = _compute_tf(doc_tokens)
            sim = _cosine_similarity(query_tf, doc_tf)
            scored.append((sim, row))

        # Sort by similarity descending, take top-k
        scored.sort(key=lambda x: x[0], reverse=True)
        top_k = scored[:k]

        return [
            {
                "spec_id": row[1],
                "spec_text": row[2],
                "prompt": row[3],
                "generated_code": row[4],
                "verification_result": json.loads(row[5]),
                "similarity": sim,
            }
            for sim, row in top_k
        ]

    def get_count(self) -> int:
        """Total number of stored successes."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM successes").fetchone()
            return row[0]
        finally:
            conn.close()


# --- Module-level convenience functions ---


def store_success(
    db_path: str,
    spec_id: str,
    spec_text: str,
    prompt: str,
    generated_code: str,
    verification_result: dict[str, Any],
) -> int:
    """Store a successful run. Convenience wrapper."""
    return ReplayStore(db_path).store_success(
        spec_id, spec_text, prompt, generated_code, verification_result
    )


def retrieve_similar(
    db_path: str, query: str, k: int = 3
) -> list[dict[str, Any]]:
    """Retrieve similar past successes. Convenience wrapper."""
    return ReplayStore(db_path).retrieve_similar(query, k)


def get_replay_count(db_path: str) -> int:
    """Total stored successes. Convenience wrapper."""
    return ReplayStore(db_path).get_count()
