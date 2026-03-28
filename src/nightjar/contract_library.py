"""Domain-knowledge contract pattern library for nightjar infer.

Provides few-shot example expressions for LLM-based contract inference.
Patterns encode common semantic constraints (age, price, email, etc.)
that the LLM can use as templates when generating Python assert expressions.

Based on the PropertyGPT RAG pattern: retrieve semantically similar verified
contracts as few-shot examples to reduce hallucinations in LLM generation.

References:
- [REF-NEW-08] NL2Contract: "Beyond Postconditions: Can LLMs infer Formal Contracts?"
  URL: https://arxiv.org/abs/2510.12702
- [REF-NEW-12] PropertyGPT: RAG over verified contracts for few-shot prompting
  URL: https://arxiv.org/abs/2405.02580
"""

from __future__ import annotations

from typing import Any

# DOMAIN_PATTERNS: seed library of common domain invariant patterns.
#
# Each entry is a dict with:
#   name     (str)        — human-readable pattern label
#   keywords (list[str])  — terms matched against function/param names
#   examples (list[str])  — assert EXPRESSIONS (no "assert " prefix) used
#                           as few-shot examples in LLM prompting
#
# Keyword matching uses substring search on the lowercased combined text of
# function_name and param_names. Sort by hit count descending to rank the
# most relevant patterns first.
DOMAIN_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "age",
        "keywords": ["age"],
        "examples": ["age >= 0", "age <= 150"],
    },
    {
        "name": "price",
        "keywords": ["price", "cost", "amount", "fee"],
        "examples": ["price >= 0"],
    },
    {
        "name": "percentage",
        "keywords": ["percentage", "percent", "rate", "ratio"],
        "examples": ["0.0 <= percentage <= 1.0"],
    },
    {
        "name": "email",
        "keywords": ["email", "mail"],
        "examples": ["'@' in email", "'.' in email"],
    },
    {
        "name": "username",
        "keywords": ["username", "user_name", "login", "handle"],
        "examples": ["1 <= len(username) <= 255"],
    },
    {
        "name": "password",
        "keywords": ["password", "passwd", "pwd"],
        "examples": ["len(password) >= 8"],
    },
    {
        "name": "count",
        "keywords": ["count", "num", "number", "total", "quantity"],
        "examples": ["count >= 0"],
    },
    {
        "name": "index",
        "keywords": ["index", "idx", "offset", "position"],
        "examples": ["index >= 0"],
    },
    {
        "name": "score",
        "keywords": ["score", "grade", "rating"],
        "examples": ["0 <= score <= 100"],
    },
    {
        "name": "discount",
        "keywords": ["discount", "reduction"],
        "examples": ["0.0 <= discount <= 1.0"],
    },
    {
        "name": "timeout",
        "keywords": ["timeout", "deadline", "ttl", "wait", "delay"],
        "examples": ["timeout > 0"],
    },
    {
        "name": "url",
        "keywords": ["url", "uri", "link", "endpoint", "href"],
        "examples": ["url.startswith('http://') or url.startswith('https://')"],
    },
]


def retrieve_examples(
    function_name: str,
    param_names: list[str],
    top_k: int = 3,
) -> list[str]:
    """Retrieve contract example expressions matching function/param names.

    Scores each pattern in DOMAIN_PATTERNS by counting how many of its
    keywords appear (as substrings) in the lowercased combined text of
    function_name and param_names. Patterns with at least one hit are sorted
    by hit count descending; examples are collected from those patterns up to
    top_k total.

    Returns expression strings suitable for use as few-shot examples in LLM
    prompting — no "assert " prefix.

    Args:
        function_name: Name of the function being analyzed.
        param_names:   List of parameter names for that function.
        top_k:         Maximum number of example expression strings to return.

    Returns:
        List of expression strings. Empty list [] when no pattern matches or
        top_k == 0.
    """
    if top_k <= 0:
        return []

    combined = function_name.lower() + " " + " ".join(p.lower() for p in param_names)

    # Score each pattern by keyword hit count
    scored: list[tuple[int, dict[str, Any]]] = []
    for pattern in DOMAIN_PATTERNS:
        hits = sum(1 for kw in pattern["keywords"] if kw in combined)
        if hits > 0:
            scored.append((hits, pattern))

    if not scored:
        return []

    # Sort by hit count descending; stable sort preserves DOMAIN_PATTERNS order
    # for ties, so the most general/authoritative patterns come first.
    scored.sort(key=lambda x: x[0], reverse=True)

    # Collect examples from patterns in relevance order, up to top_k
    result: list[str] = []
    for _, pattern in scored:
        for example in pattern["examples"]:
            if len(result) >= top_k:
                return result
            result.append(example)

    return result
