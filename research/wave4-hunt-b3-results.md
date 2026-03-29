# Wave 4 Hunt B3 — mlflow + celery Security Scan

**Date:** 2026-03-29
**Versions:** mlflow 3.10.1, celery 5.6.2, Python 3.14
**Method:** CVE review + source code audit + live PoC execution
**Verdict per target below — zero false positives policy enforced.**

---

## CVE Background

### mlflow

Active CVE cluster around path traversal (all pre-3.x):
- CVE-2024-1594 — `artifact_location` fragment `#` bypass (patched: `#` now blocked in `validate_path_is_safe`)
- CVE-2024-2928 — URI fragment directory traversal RFI (patched)
- CVE-2024-3573 — `is_local_uri` empty/file scheme misparse (patched)
- CVE-2025-11201 — model version `source` traversal RCE (patched in recent versions)

No CVE found for NaN/inf silent storage in `log_metric`.

### celery

All recent CVEs (CVE-2024-40628, CVE-2024-40629, CVE-2024-29201/29202) are JumpServer deployment issues where Celery runs as root — not defects in the celery library itself.
No CVE found for `jsonify` idempotency or `set_chord_size` zero.

---

## Target 1 — mlflow `log_metric()`: NaN, inf, -inf silent storage

**Status: BUG CONFIRMED**

### Root Cause

`_validate_metric()` in `mlflow/utils/validation.py:206` delegates to `_is_numeric()`:

```python
def _is_numeric(value):
    return not isinstance(value, bool) and isinstance(value, numbers.Number)
```

`float('nan')`, `float('inf')`, and `float('-inf')` all satisfy `isinstance(v, numbers.Number)` and are not `bool`. `_validate_metric` performs no `math.isfinite()` check. The `Metric.__init__` constructor (in `mlflow/entities/metric.py`) stores `value` directly with no validation at all.

### PoC

```python
from mlflow.utils.validation import _validate_metric
import math

_validate_metric("loss", float('nan'),  1000, 0)  # no exception
_validate_metric("loss", float('inf'),  1000, 0)  # no exception
_validate_metric("loss", float('-inf'), 1000, 0)  # no exception
```

End-to-end confirmation (sqlite backend):
```
log_metric(nan)  -> STORED SILENTLY
log_metric(inf)  -> STORED SILENTLY
log_metric(-inf) -> STORED SILENTLY
```

### Impact

- NaN/inf stored in the metrics database without any error signal to the caller
- The docstring for `log_metric` warns "some special values such as +/- Infinity may be replaced" (SQLAlchemy store) but `_validate_metric` does not enforce any contract
- Downstream code reading metrics back may receive `nan` without knowing the upstream call was semantically invalid
- The docstring promise of consistent validation across backends is broken: SQLAlchemy silently replaces infinity, file store serializes the literal string "inf", REST store forwards to the server — three different behaviors for the same input, all silent

### Relevant Files

- `mlflow/utils/validation.py:197-231` — `_is_numeric`, `_validate_metric`
- `mlflow/entities/metric.py:13-37` — `Metric.__init__` (no value check)
- `mlflow/store/tracking/file_store.py:1071-1076` — calls `_validate_metric` then writes

---

## Target 2 — mlflow `download_artifacts()`: URI path traversal

**Status: CLEAN (with one cosmetic note)**

### Analysis

`validate_path_is_safe()` in `mlflow/utils/uri.py:487` implements a layered defense:

1. Iteratively URL-decodes via `_decode()` (up to 10 rounds) — blocks `%2e%2e`, `%252e%252e`, double-encoded variants
2. Checks for `#` fragment characters (CVE-2024-1594 fix)
3. Checks for OS alt separators (`_OS_ALT_SEPS`)
4. Splits on `/` and checks for `..` components
5. Checks `PureWindowsPath.is_absolute()` and `PurePosixPath.is_absolute()`
6. Windows drive letter check (`path[1] == ':'`)

After `validate_path_is_safe`, `LocalArtifactRepository.download_artifacts` also calls `validate_path_within_directory` which uses `pathlib.Path.resolve()` + `is_relative_to()` — a second independent barrier.

### Test Results

All standard traversal payloads blocked:
- `../etc/passwd` — BLOCKED
- `../../etc/passwd` — BLOCKED
- `%2e%2e/etc/passwd` — BLOCKED
- `%252e%252e/etc/passwd` — BLOCKED (iterative decode catches it)
- `..%2fetc%2fpasswd` — BLOCKED
- `foo#/../etc/passwd` — BLOCKED (# check fires first)
- `/etc/passwd` — BLOCKED (absolute path check)
- Null byte injection — BLOCKED

### Cosmetic Note (not a vulnerability)

`validate_path_is_safe` accepts `..;/etc/passwd` and `....//' — both are NOT traversal vectors. `os.path.normpath("..;/etc/passwd")` produces `..;\etc\passwd` on Windows, where `..;` is a literal directory name (not parent traversal). `validate_path_within_directory`'s `resolve()` + `is_relative_to()` check would also independently block any actual escape. No exploitable path traversal exists.

---

## Target 3 — celery `jsonify()` idempotency

**Status: CLEAN**

### Analysis

`jsonify()` in `celery/utils/serialization.py:233` converts objects to JSON-serializable primitives. For idempotency to hold, `jsonify(jsonify(x)) == jsonify(x)` for all inputs in the function's domain.

The type dispatch:
- `None`, `numbers.Real`, `str` — returned as-is; second pass identical
- `list`, `tuple` — recursively processed into list; second pass on a list is identical
- `dict` — recursively processed; second pass on a dict of primitives is identical
- `datetime.datetime/date/time` — converted to ISO string; second pass on a string returns it unchanged
- `datetime.timedelta` — converted to `str()`; second pass on a string returns it unchanged
- Unknown type with `unknown_type_filter` — converted to whatever filter returns (typically str); second pass on str returns it unchanged

### Test Results

All tested inputs idempotent including: str, int, float, None, list, nested list, dict, datetime, date, timedelta, tuple, nested-datetime dict, nested-tuple dict, empty dict/list, float('nan'), float('inf'), and unknown types with filter.

```
jsonify(jsonify(x)) == jsonify(x)  # True for all tested inputs
```

No bug. The implementation is correctly idempotent over its output domain.

---

## Target 4 — celery `chord._set_chord_size()` / `set_chord_size()`: zero must raise

**Status: BUG CONFIRMED (behavioral, no exception raised)**

### Root Cause

`RedisBackend.set_chord_size` in `celery/backends/redis.py:484`:

```python
def set_chord_size(self, group_id, chord_size):
    self.set(self.get_key_for_group(group_id, '.s'), chord_size)
```

No guard. `chord_size=0` is stored directly in Redis under the `.s` key.

`BaseBackend.set_chord_size` in `celery/backends/base.py:781`:

```python
def set_chord_size(self, group_id, chord_size):
    pass
```

Also no guard. A scan of all files in `celery/backends/` confirms no backend validates `chord_size > 0`.

### Downstream Impact

In `celery/backends/redis.py:534-542`, `on_chord_part_return` reads back the stored chord size:

```python
_, readycount, totaldiff, chord_size_bytes = pipeline.execute()[:4]
totaldiff = int(totaldiff or 0)
if chord_size_bytes:
    total = int(chord_size_bytes) + totaldiff   # total = 0 + 0 = 0
    if readycount == total:                      # 0 == 0 -> True immediately
        # ... fires chord body callback
```

When `chord_size=0` is stored:
- `total` evaluates to `0`
- `readycount` starts at `0` (no tasks have completed yet)
- `readycount == total` is `True` immediately upon the first task return
- The chord body callback fires with an incomplete result set

This is a logic error: a chord with zero declared members fires its body spuriously before any actual work is done (or never fires if no tasks ever call `on_chord_part_return`). No exception is raised at the point of the zero write, making the failure silent and delayed.

### Call Site

`celery/canvas.py:1790`:
```python
app.backend.set_chord_size(group_id, chord_size)
```

`chord_size` is accumulated via `chord._descend()` starting from 0. If the chord header is empty (zero tasks), `chord_size` remains 0 and is passed through without rejection.

### Relevant Files

- `celery/backends/redis.py:484-485` — `set_chord_size` (no zero guard)
- `celery/backends/base.py:781-782` — base `set_chord_size` (no-op, no guard)
- `celery/backends/redis.py:534-542` — `on_chord_part_return` reads back size
- `celery/canvas.py:1787-1790` — call site where `chord_size` accumulates

---

## Summary Table

| # | Package | Target | Status | Severity |
|---|---------|--------|--------|----------|
| 1 | mlflow 3.10.1 | `log_metric()` NaN/inf/−inf | **BUG** — silently stored, no exception | Medium |
| 2 | mlflow 3.10.1 | `download_artifacts()` path traversal | **CLEAN** — all vectors blocked | — |
| 3 | celery 5.6.2 | `jsonify()` idempotency | **CLEAN** — idempotent across all tested inputs | — |
| 4 | celery 5.6.2 | `set_chord_size()` zero | **BUG** — zero stored silently, causes spurious chord completion | Medium |

**Confirmed bugs: 2 of 4 targets.**
**False positives: 0.**
