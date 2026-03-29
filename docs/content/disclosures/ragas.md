# Disclosure: ragas — 4 Bugs (1 HIGH, 3 MEDIUM)

**Package:** ragas
**Affected version:** 0.4.3
**Report date:** 2026-03-29
**Severity:** HIGH (BUG-B6-01), MEDIUM (BUG-B6-02, BUG-B6-03, BUG-B6-04)
**Preferred channel:**
- BUG-B6-04 (covert network telemetry): Email founders@vibrantlabs.com (per SECURITY.md in ragas repo)
- BUG-B6-01/02/03 (score correctness): Public GitHub issue at https://github.com/explodinggradients/ragas/issues

> **Channel note:** The ragas SECURITY.md specifies email founders@vibrantlabs.com for security reports. BUG-B6-04 (background telemetry thread firing on every `score()` call without user consent in offline/air-gapped environments) has privacy implications and should go through that channel. BUG-B6-01/02/03 are correctness failures — they produce wrong evaluation results — which are high-severity for an evaluation library but are not security vulnerabilities. File them as a linked set of public issues referencing the systemic NaN-as-sentinel pattern.

---

## Subject

GitHub Issue Title (BUG-B6-01 + 02 + 03): `np.nan` returned as score from 9+ metric functions — evaluation results silently invalidated when LLM returns empty output (ragas 0.4.3)

---

## Issue Body (for GitHub — public)

## Summary

`ragas 0.4.3` uses `np.nan` as a sentinel value for "computation was not possible" across at least 9 distinct metric functions. `np.nan` is a valid IEEE 754 float but is not in the documented `[0.0, 1.0]` score range. Any aggregation over evaluation results that contains even one NaN-producing sample silently corrupts the entire dataset mean without raising an error or logging at anything above WARNING level. This breaks the fundamental contract of an evaluation library.

## Environment

- Package version: ragas 0.4.3
- Python version: 3.14
- Method: source inspection + runtime probes

## Reproduction

### BUG-B6-01: `_compute_score` returns `np.nan` when denominator is zero

```python
import numpy as np

# Directly reproduce the denominator-zero path from _context_recall._compute_score:
response = []           # LLM returned empty classifications
denom = len(response)   # 0
score = (sum(r["verdict"] for r in response) / denom) if denom > 0 else np.nan
print(f"Score: {score}")         # nan
print(f"In range: {0.0 <= score <= 1.0}")  # False — NaN comparisons always False

# Downstream aggregation is silently poisoned:
scores = [0.8, 0.9, float('nan'), 0.7]
mean = sum(scores) / len(scores)
print(f"Mean of [0.8, 0.9, nan, 0.7]: {mean}")  # nan — entire result invalidated
```

### BUG-B6-02: `DataCompyScore` raises `ZeroDivisionError` when precision and recall are both zero

```python
# Reproduces the legacy _datacompy_score.py:75 path:
precision = 0.0
recall = 0.0
# F1 formula with no guard:
score = 2 * (precision * recall) / (precision + recall)
# ZeroDivisionError: float division by zero
```

Note: `metrics/collections/datacompy_score/metric.py` fixes this with `if precision + recall == 0: score = 0.0`. The legacy `metrics/_datacompy_score.py` path has no such guard and is still the exported default.

### BUG-B6-03: `AnswerAccuracy.average_scores` silently returns NaN when both sub-scores are NaN

```python
import numpy as np

def average_scores(score0, score1):
    score = np.nan
    if score0 >= 0 and score1 >= 0:    # NaN >= 0 is False — branch skipped
        score = (score0 + score1) / 2
    else:
        score = max(score0, score1)    # max(nan, nan) = nan
    return score

print(average_scores(np.nan, np.nan))  # nan
print(average_scores(np.nan, 0.5))     # nan — valid score silently discarded
```

## Affected files (exhaustive list of NaN-producing paths)

| File | Condition |
|------|-----------|
| `metrics/_faithfulness.py:192` | `num_statements == 0` |
| `metrics/_faithfulness.py:211` | `statements == []` |
| `metrics/_faithfulness.py:262` | `FaithfulnesswithHHEM` same path |
| `metrics/_answer_relevance.py:124` | all generated questions are empty strings |
| `metrics/_answer_correctness.py:249` | `answers is None` from LLM |
| `metrics/_context_precision.py:116` | dead assignment path |
| `metrics/_context_precision.py:295` | `retrieved_context_ids` list empty |
| `metrics/_context_recall.py:118` | `denom == 0` |
| `metrics/_context_recall.py:222,272` | same denominator-zero path |
| `metrics/_datacompy_score.py:57` | CSV parse exception |
| `metrics/_nv_metrics.py:89,92,108,161,224,227,251,296,358,361,385,430` | retry exhaustion |
| `metrics/collections/context_recall/metric.py:123,127` | denominator-zero |
| `metrics/collections/datacompy_score/metric.py:105` | CSV parse exception |

## Root cause

The library uses `np.nan` as a sentinel for "could not compute" rather than raising `MetricComputationError` (the approach taken by opik, which handles the same edge case correctly). `base.py`'s `single_turn_score()` and `single_turn_ascore()` do not check for NaN before returning to caller code. There is no opt-in "strict mode" that converts NaN returns to exceptions.

## Impact

Users who run ragas evaluations on datasets where some samples produce empty LLM output (a normal production occurrence — models sometimes return empty strings on failure) will see mean scores of `nan` with no indication that any samples failed. Evaluation reports that show `nan` or `NaN` are completely meaningless. There is no way to distinguish "all samples passed" from "some samples produced NaN" without manually checking each score value.

## Suggested fix

The correct fix is the opik approach: raise `MetricComputationError` at the division site when the denominator is zero, rather than returning `np.nan`. This ensures the caller receives a typed exception they can catch and handle, rather than a float sentinel that silently poisons aggregations.

```python
# Before (example from _context_recall.py:118):
score = numerator / denom if denom > 0 else np.nan

# After:
if denom == 0:
    raise MetricComputationError(
        "Context recall: denominator is zero (no classifications returned by LLM). "
        "This sample cannot be scored."
    )
score = numerator / denom
```

For `DataCompyScore` (BUG-B6-02), the `collections/` version already has the correct guard — backport it to the legacy `metrics/_datacompy_score.py:75`.

For `AnswerAccuracy.average_scores` (BUG-B6-03), treat either NaN sub-score as a computation failure rather than falling through to `max(nan, nan)`:

```python
def average_scores(self, score0, score1):
    if np.isnan(score0) and np.isnan(score1):
        return np.nan  # or raise MetricComputationError
    elif np.isnan(score0):
        return score1
    elif np.isnan(score1):
        return score0
    return (score0 + score1) / 2
```

## How this was found

This was found by Nightjar's property-based testing engine, which checked the invariant that `all metric functions return a score in [0.0, 1.0]`. The NaN sentinel violates this invariant. The counterexample was a dataset sample where the LLM returned an empty classifications list, triggering the denominator-zero path.

---

## BUG-B6-04 (separate — email to founders@vibrantlabs.com)

### Subject

ragas 0.4.3: analytics network request fires on every `score()` call — including pure heuristic metrics — without user opt-in

### Body

Hi ragas team,

We found that ragas 0.4.3 fires a background HTTP POST to `https://t.explodinggradients.com` on every `score()` / `ascore()` call, including calls to pure heuristic metrics (BLEU, ROUGE, etc.) that do not use an LLM. This violates the invariant that pure metric computation is network-free.

**Mechanism**

1. `ragas/metrics/base.py` imports `_analytics_batcher` at module level.
2. `_analytics.py:287` instantiates `AnalyticsBatcher(batch_size=10, flush_interval=10)` at import time.
3. `AnalyticsBatcher.__init__` immediately spawns a daemon background thread (`_flush_loop`).
4. Every `single_turn_score()` call appends an `EvaluationEvent` to the buffer.
5. The thread POSTs to `https://t.explodinggradients.com` within 10 seconds.

**Impact**

- Users running ragas in air-gapped environments, CI pipelines with no outbound internet, or environments with strict egress policies will experience unexpected network errors or timeouts during evaluation.
- `RAGAS_DO_NOT_TRACK=true` opt-out exists but is not visible in the top-level API docs or `score()` docstring. Users who don't know about it have no opportunity to consent.
- Pure heuristic metrics fire the telemetry event despite requiring no LLM — users computing BLEU scores do not expect a network request.

**Reproduction**

```python
import os
# Verify telemetry fires by confirming the background thread exists at import:
import threading
initial_threads = {t.name for t in threading.enumerate()}
import ragas  # noqa
post_import_threads = {t.name for t in threading.enumerate()}
new_threads = post_import_threads - initial_threads
print(f"New threads after import: {new_threads}")
# Output includes a daemon thread — analytics background flusher
```

**Suggested fix**

1. Default `RAGAS_DO_NOT_TRACK=true` — opt-in to telemetry, not opt-out.
2. Add a visible API parameter: `score(..., track=False)`.
3. Document the telemetry behavior prominently in `score()` and `ascore()` docstrings.
4. Do not spawn the background thread at module import time — defer it until the first `score()` call that has not opted out.

**Disclosure timeline:** We intend to publish scan results including this finding on 2026-06-27 (90 days from today). We will not name ragas specifically until after you have had time to respond. Please confirm receipt within 3 days.

---

*Found by Nightjar's property-based testing pipeline. Reproduction environment: Python 3.14, ragas 0.4.3, Windows 11. All findings verified by source inspection and direct execution.*
