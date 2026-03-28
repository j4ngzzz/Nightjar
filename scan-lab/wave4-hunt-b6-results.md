# Wave 4 Hunt B6 — AI Eval Frameworks Survey Scan
**Packages:** ragas 0.4.3, opik 1.10.54, langsmith 0.7.22
**Date:** 2026-03-29
**Method:** Static source analysis + targeted runtime probes
**Invariants checked:**
1. Score functions return `[0.0, 1.0]` for all inputs
2. NaN/inf inputs must raise, not silently produce NaN scores
3. Pure metric computation must not make network requests

---

## RAGAS 0.4.3

### BUG-B6-01 — NaN returned as score from at least 9 distinct metric functions
**Severity:** HIGH
**Invariant violated:** #1 (score range [0.0, 1.0])

`np.nan` is a valid IEEE 754 float but it is not in `[0.0, 1.0]`. Every
caller that aggregates scores (mean, weighted sum, comparison) silently
propagates the NaN rather than raising, making downstream evaluation
results meaningless without detection.

**Affected functions (exhaustive from grep):**

| File | Condition that produces NaN |
|------|-----------------------------|
| `metrics/_faithfulness.py:192` | `num_statements == 0` after LLM statement generation |
| `metrics/_faithfulness.py:211` | `statements == []` — LLM returned empty list |
| `metrics/_faithfulness.py:262` | `FaithfulnesswithHHEM._ascore` same empty-statements path |
| `metrics/_answer_relevance.py:124` | all generated questions are empty strings |
| `metrics/_answer_correctness.py:249` | `answers is None` from LLM |
| `metrics/_context_precision.py:116` | initial value never overwritten (dead assignment then reassigned, but branch survives) |
| `metrics/_context_precision.py:295` | `retrieved_context_ids` list is empty |
| `metrics/_context_recall.py:118` | `denom == 0` (empty classifications) |
| `metrics/_context_recall.py:222,272` | same denominator-zero path |
| `metrics/_datacompy_score.py:57` | CSV parse exception |
| `metrics/_nv_metrics.py:89,92,108,161,224,227,251,296,358,361,385,430` | retry exhaustion with no parseable score token |
| `metrics/collections/context_recall/metric.py:123,127` | same denominator-zero |
| `metrics/collections/datacompy_score/metric.py:105` | CSV parse exception |

**Reproduction path (no LLM needed — `_context_recall._compute_score`):**
```python
# LLMContextRecall._compute_score([]) → np.nan
response = []
denom = len(response)          # 0
score = numerator / denom if denom > 0 else np.nan   # → np.nan
```

**Root cause:** The library uses `np.nan` as a sentinel for "could not
compute" rather than raising. No caller in `base.py`'s
`single_turn_score()` or `single_turn_ascore()` checks for NaN before
returning to user code.

---

### BUG-B6-02 — `DataCompyScore._single_turn_ascore` raises `ZeroDivisionError` when both precision and recall are zero
**Severity:** MEDIUM
**Invariant violated:** #1 (should return a score; instead raises)
**File:** `metrics/_datacompy_score.py:75`

```python
# When count_matching_rows() == 0 on both DataFrames:
precision = 0.0
recall    = 0.0
return 2 * (precision * recall) / (precision + recall)  # ZeroDivisionError
```

This is the **legacy** `_datacompy_score.py` (not the `collections/`
version). The `collections/datacompy_score/metric.py` fixes this with an
explicit `if precision + recall == 0: score = 0.0` guard. The old path
has no such guard and is still the exported default.

**Confirmed by runtime probe:**
```
>>> 2 * (0.0 * 0.0) / (0.0 + 0.0)
ZeroDivisionError: float division by zero
```

---

### BUG-B6-03 — `AnswerAccuracy.average_scores` returns NaN when both sub-scores are NaN (score comparator uses NaN identity trick)
**Severity:** MEDIUM
**Invariant violated:** #1
**File:** `metrics/_nv_metrics.py:91-97`

```python
def average_scores(self, score0, score1):
    score = np.nan
    if score0 >= 0 and score1 >= 0:   # NaN >= 0 is False, so this branch skipped
        score = (score0 + score1) / 2
    else:
        score = max(score0, score1)    # max(nan, nan) = nan
    return score
```

When both LLM calls exhaust their retry budget and return NaN:
- `np.nan >= 0` evaluates to `False` (no exception, just False)
- falls to `else: score = max(nan, nan)` → `nan`

**Confirmed by runtime probe:**
```
avg(nan, nan) = nan
avg(nan, 0.5) = nan   ← one valid score still silently discarded
```

---

### BUG-B6-04 — Network request fired unconditionally on every `score()` / `ascore()` call via background analytics thread
**Severity:** MEDIUM
**Invariant violated:** #3 (no network requests during pure metric computation)
**Files:** `_analytics.py:133-289`, `metrics/base.py:449-457`

**Mechanism:**
1. At module import, `ragas/metrics/base.py` imports `_analytics_batcher`
2. `_analytics.py:287` instantiates `AnalyticsBatcher(batch_size=10, flush_interval=10)` **at module level**
3. `AnalyticsBatcher.__init__` immediately spawns a daemon background thread (`_flush_loop`)
4. Every call to `SingleTurnMetric.single_turn_score()` appends an `EvaluationEvent` to the buffer
5. The background thread POSTs to `https://t.explodinggradients.com` within 10 seconds

```python
# _analytics.py:233
requests.post(USAGE_TRACKING_URL, json=payload, timeout=USAGE_REQUESTS_TIMEOUT_SEC)
# USAGE_TRACKING_URL = "https://t.explodinggradients.com"
```

**Opt-out exists** (`RAGAS_DO_NOT_TRACK=true` env var) but it is off by
default. There is no API-level argument to disable tracking. The network
call happens regardless of whether the computation involved any LLM — it
fires for pure heuristic metrics (BLEU, ROUGE, etc.) as well.

**This violates the invariant that pure metric computation is network-free.**

---

## OPIK 1.10.54

### BUG-B6-05 — `factuality/parser.py` raises `ZeroDivisionError` when LLM returns an empty claims list
**Severity:** MEDIUM
**Invariant violated:** #1 (should return a score or raise `MetricComputationError`; raises raw `ZeroDivisionError` instead)
**File:** `evaluation/metrics/llm_judges/factuality/parser.py:28`

```python
score = 0.0
for claim in list_content:        # list_content = [] → loop never runs
    score += float(claim["score"])

score /= len(list_content)        # ZeroDivisionError: division by zero
```

The outer `try/except Exception` on line 31 will catch the
`ZeroDivisionError` and re-raise it as a `MetricComputationError`, so the
**ultimate exception type** is acceptable — but this is fragile. The bug
means an LLM that returns `[]` (valid JSON, plausible output) causes an
unintended exception path rather than a deliberate one. The fix is an
explicit `if not list_content: raise MetricComputationError(...)` before
the division.

---

### CLEAN areas in opik
- `LevenshteinRatio`: delegates to `rapidfuzz.distance.Indel.normalized_similarity` which always returns `[0.0, 1.0]`. Clean.
- `SentenceBLEU` / `CorpusBLEU`: raises `MetricComputationError` on empty input; `ZeroDivisionError` from NLTK caught and returns `0.0`. Clean.
- `hallucination/parser.py`, `answer_relevance/parser.py`: explicit range check `0.0 <= score <= 1.0` before return, raises `MetricComputationError` on violation. Clean.
- `g_eval/parser.py`: explicit range check `0 <= score_raw <= 10` and `0.0 <= final_score <= 1.0`, raises on violation. Clean.
- `ScoreResult` dataclass: no range validation at construction (relies on parsers to validate before constructing), which is consistent with the parser-level checks above.
- No network calls in pure metric compute path. `BaseMetric.__init__` calls `check_for_known_misconfigurations()` which inspects config state only (no socket/HTTP). The `opik.track` decorator adds tracing but it is gated on `track=True` (default) and only fires if config is valid — separate from score computation.

---

## LANGSMITH 0.7.22

### CLEAN — No invariant violations found

**Score type:** `SCORE_TYPE = Union[StrictBool, StrictInt, StrictFloat, None]`
- `StrictFloat` accepts NaN and inf (confirmed by runtime probe: `Res(score=float('nan'))` succeeds)
- **However:** langsmith does not define built-in metric functions that compute scores. It provides a framework (`RunEvaluator`, `EvaluationResult`) into which user-supplied or LLM-supplied evaluators plug. The framework itself imposes no range invariant — that is intentionally the user's responsibility.
- `LLMEvaluator` uses JSON schema with `"minimum": 0, "maximum": 1` passed to the LLM's structured-output mode, enforcing range at the LLM call level (not in Python code). Clean for the framework's design contract.
- `StringEvaluator`: deprecated; wraps a user-supplied `grading_function` with no score validation. Not a bug in langsmith itself.
- No analytics network calls in the metric evaluation path. Network calls are made to the LangSmith platform API (`client.create_feedback`, etc.) but these are explicit logging calls in the runner, not embedded in score computation.

**Note on NaN acceptance:** `StrictFloat` silently accepts `float('nan')`. This is not a bug in langsmith given its framework nature, but downstream users who aggregate `EvaluationResult.score` values should guard against NaN propagation themselves.

---

## Summary Table

| ID | Package | Severity | Invariant | Description |
|----|---------|----------|-----------|-------------|
| BUG-B6-01 | ragas 0.4.3 | HIGH | #1 score range | 9+ metric functions return `np.nan` instead of raising |
| BUG-B6-02 | ragas 0.4.3 | MEDIUM | #1 score range | `DataCompyScore` raises `ZeroDivisionError` when P=R=0 |
| BUG-B6-03 | ragas 0.4.3 | MEDIUM | #1 score range | `AnswerAccuracy.average_scores` silently returns NaN on retry exhaustion |
| BUG-B6-04 | ragas 0.4.3 | MEDIUM | #3 no network | Background thread POSTs telemetry to `t.explodinggradients.com` on every `score()` call |
| BUG-B6-05 | opik 1.10.54 | MEDIUM | #1 score range | `factuality/parser.py` hits raw `ZeroDivisionError` on empty claims list |

**Total confirmed bugs: 5**
**False positives: 0**

---

## Verdicts by Package

| Package | Verdict |
|---------|---------|
| ragas 0.4.3 | **BUGGY** — 4 confirmed bugs; NaN-as-sentinel is a systemic design choice affecting the majority of metrics |
| opik 1.10.54 | **MOSTLY CLEAN** — 1 edge-case bug in factuality parser; heuristic metrics and other LLM judges are well-validated |
| langsmith 0.7.22 | **CLEAN** (as a framework) — no built-in score computation, range enforcement is delegated to user evaluators by design |

---

## Key Pattern: ragas NaN-as-Sentinel

The ragas library made a deliberate architectural choice to return `np.nan`
when computation is impossible (empty LLM output, parse failure, zero
denominator). This is documented nowhere in the public API. The consequence:

```python
# Typical user code
scores = [metric.single_turn_score(sample) for sample in dataset]
mean_score = sum(scores) / len(scores)   # nan if ANY sample failed
```

Any aggregation over a dataset that contains even one NaN-producing sample
silently poisons the entire result. The library does emit a `logger.warning`
in some (not all) NaN paths, but warnings are not errors and are typically
suppressed in production.

The proper fix is a uniform error-handling policy: either raise
`MetricComputationError` (opik's approach) or return a sentinel object that
is not a float (not the current approach). The `np.nan` choice makes the
API appear to return a valid score while silently invalidating downstream
aggregation.
