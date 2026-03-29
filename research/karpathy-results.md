# Karpathy Repo Scan Results

**Date:** 2026-03-28
**Scanner:** Nightjar code scanner agent
**Repos scanned:** minbpe (commit: depth-1 clone), makemore (depth-1 clone)
**Method:** source reading + direct execution + Hypothesis PBT

---

## minbpe

### BUG 1 — `BasicTokenizer.train()` and `RegexTokenizer.train()`: ValueError crash when `vocab_size` exceeds mergeable pairs

**File:** `minbpe/basic.py` line 35, `minbpe/regex.py` line 56
**Severity:** High — unguarded crash on valid user input

**Root cause:**
`train()` computes `num_merges = vocab_size - 256` and iterates exactly that many times. On each iteration it calls `max(stats, key=stats.get)`. When the training text has been fully compressed to a single token (or when `vocab_size - 256` exceeds the number of unique consecutive pairs in the text), `stats` is empty and `max()` raises `ValueError: max() iterable argument is empty`.

**Trigger condition:**
Any call where `vocab_size - 256` is greater than the maximum number of BPE merges possible for the given text. This is easy to hit:
- Short or repetitive training text
- A single repeated character
- Any text that collapses to one token before all requested merges are performed

**Reproduction script:**
```python
import sys
sys.path.insert(0, 'scan-lab/minbpe')
from minbpe.basic import BasicTokenizer

# 'aaaaaaaaaa' supports exactly 4 merges before it becomes a single token
tok = BasicTokenizer()
tok.train('aaaaaaaaaa', 256 + 5)  # requests 5 merges — CRASH on 5th
# ValueError: max() iterable argument is empty

# Other reproducers:
BasicTokenizer().train('a', 258)           # single char, 2 merges requested
BasicTokenizer().train('', 259)            # empty string
BasicTokenizer().train('hello', 356)       # 'hello' supports only 4 merges
```

**Verified boundary:**
```
'aaaaaaaaaa' (10 bytes) -> max 4 merges before stats is empty
  Merge 0: [97]*10 -> [256]*5
  Merge 1: [256]*5 -> [257,257,256]
  Merge 2: [257,257,256] -> [258,256]
  Merge 3: [258,256] -> [259]   <- single token, stats={}, CRASH on next iteration
```

**Affected functions:**
- `BasicTokenizer.train()` (basic.py:35)
- `RegexTokenizer.train()` (regex.py:56, same pattern)

**Fix:** Add a guard before `max(stats, ...)`:
```python
if not stats:
    break  # no more pairs to merge
pair = max(stats, key=stats.get)
```

---

### BUG 2 — `Tokenizer.load()`: ValueError crash when special token name contains a space

**File:** `minbpe/base.py` line 156
**Severity:** Medium — crashes on tokenizers with space-containing special token names

**Root cause:**
`load()` parses special tokens with:
```python
special, special_idx = f.readline().strip().split()
```
`.split()` with no argument splits on all whitespace, so a token like `"hello world"` produces three values (`'hello'`, `'world'`, `'99999'`), causing `ValueError: too many values to unpack (expected 2)`.

The format written by `save()` is:
```
hello world 99999
```
and `split()` cannot distinguish the token name boundary from the trailing integer.

**Reproduction script:**
```python
import sys, tempfile, os
sys.path.insert(0, 'scan-lab/minbpe')
from minbpe.regex import RegexTokenizer

tok = RegexTokenizer()
tok.train('hello world test', 256 + 3)
tok.register_special_tokens({'hello world': 99999})  # space in token name

with tempfile.NamedTemporaryFile(suffix='', delete=False, mode='w') as f:
    prefix = f.name
tok.save(prefix)

tok2 = RegexTokenizer()
tok2.load(prefix + '.model')  # ValueError: too many values to unpack (expected 2)
```

**Note:** Real-world special tokens (e.g. `<|endoftext|>`) don't contain spaces so this doesn't affect the standard GPT-4 tokenizer workflow. However it is a latent bug for any custom tokenizer that registers space-containing special tokens.

**Fix:** Use `rsplit(' ', 1)` instead of `split()` to split only on the last space, preserving multi-word token names:
```python
special, special_idx = f.readline().strip().rsplit(' ', 1)
```

---

## Invariants that held (no bugs)

Scanned with Hypothesis (200 examples each):

| Invariant | Tokenizer | Result |
|---|---|---|
| `encode(decode(encode(text))) == encode(text)` (roundtrip) | BasicTokenizer | CLEAN |
| `decode(encode(text)) == text` (roundtrip) | BasicTokenizer | CLEAN |
| `decode(encode(text)) == text` (roundtrip) | RegexTokenizer | CLEAN |
| All token IDs >= 0 | BasicTokenizer | CLEAN |
| `len(encode(text)) <= len(text.encode('utf-8'))` | BasicTokenizer | CLEAN |
| `get_stats([])` returns `{}` | base | CLEAN |
| `get_stats([x])` returns `{}` for single element | base | CLEAN |
| `merge()` boundary cases (pair at start, end, only element) | base | CLEAN |
| Wikipedia BPE example (`aaabdaaabac`, 3 merges = `[258,100,258,97,99]`) | BasicTokenizer | CLEAN |
| Special token `none_raise` raises on special token in text | RegexTokenizer | CLEAN |
| Special token `all` mode correctly encodes special token IDs | RegexTokenizer | CLEAN |
| `save()` / `load()` roundtrip for non-space special tokens | RegexTokenizer | CLEAN |

---

## makemore

**Status: SKIP**

makemore.py requires `torch` and `torch.utils.tensorboard` which are not installed in this environment. The file also uses `args` as a module-level global (populated by argparse at script entry), making isolated function testing impractical without significant scaffolding. No pure-Python utility functions were found suitable for invariant testing without the full ML framework stack.

---

## Summary

| Package | Functions Scanned | Bugs Found |
|---|---|---|
| minbpe | 8 (get_stats, merge, BasicTokenizer.train/encode/decode, RegexTokenizer.train/encode/load) | 2 real bugs |
| makemore | 0 (SKIP — torch not available) | N/A |

**Bug 1** (train crash on exhausted pairs) is reproducible with a one-liner and affects every user who trains on short or highly-repetitive text with a vocab_size that requests more merges than the text can support.

**Bug 2** (load crash on space-containing special token names) is latent but real — the save format is ambiguous for multi-word token names and crashes on reload.
