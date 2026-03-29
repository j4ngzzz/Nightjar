# Disclosure: web3.py — ENS Fullwidth Unicode Homoglyph Attack (CRITICAL)

**Package:** web3.py (includes ens package)
**Affected version:** web3 7.14.1, ens 7.14.1
**Report date:** 2026-03-29
**Severity:** CRITICAL (B2-03), ANOMALY (B2-01)
**Preferred channel:** GitHub Security Advisory — https://github.com/ethereum/web3.py/security/advisories/new (for B2-03). For B2-01, a public GitHub issue is appropriate.

> **Channel note:** No SECURITY.md found in the ethereum/web3.py repository. The Ethereum Foundation has a general security contact at security@ethereum.org. For web3.py SDK bugs, the GitHub Security Advisory tab is the right channel. Finding B2-03 (ENS homoglyph — direct ETH address hijacking vector) must go through the Security Advisory path due to financial impact. Finding B2-01 (trailing bytes ignored by ABICodec.decode) is lower-risk and can be a public issue.

---

## Subject

Nightjar formal verification: B2-03 — 62 fullwidth Unicode characters silently fold to ASCII in ENS normalize_name(), enabling direct homoglyph address hijacking in web3.py 7.14.1

---

## Email Body

Hi web3.py team,

We have been running a public scan of Python packages using Nightjar's property-based testing pipeline. We found a critical issue in the ENS name normalization in web3.py 7.14.1: the entire fullwidth alphanumeric Unicode block (U+FF10–U+FF5A, 62 characters) silently folds to its ASCII equivalent during normalization. This creates a direct ENS address hijacking vector.

---

## Finding B2-03 (CRITICAL): ENS `normalize_name()` — 62 fullwidth Unicode characters silently map to ASCII

**Affected component**

Package: `ens` 7.14.1 (bundled in web3.py 7.14.1)
Function: `ens.utils.normalize_name` (via `ens._normalization.normalize_name_ensip15`)

**Bug description**

ENSIP-15 includes a "width mapping" step derived from Unicode Technical Standard #46 (UTS#46) that maps fullwidth Latin alphanumeric characters (U+FF10–U+FF5A) to their ASCII equivalents before script-mixing checks run. Because the mapped label becomes pure ASCII, no script-mixing violation fires. The result is that all 62 fullwidth characters — digits U+FF10–U+FF19, uppercase A–Z at U+FF21–U+FF3A, lowercase a–z at U+FF41–U+FF5A — produce identical normalized output to their plain ASCII counterparts. `normalize_name("vit\uff41lik.eth")` returns `"vitalik.eth"`, the same result as `normalize_name("vitalik.eth")`. An attacker who registers a name using fullwidth characters receives the same resolved address as any wallet that normalizes before display, because the display shows the normalized form — not the raw input.

The correct behavior for every other homoglyph class has been implemented: Cyrillic, Greek, Arabic, ZWJ/ZWNJ all raise `InvalidName`. Fullwidth Latin is the only class that silently maps through.

**Affected Unicode codepoints**

| Block | Codepoints | Count |
|-------|------------|-------|
| Fullwidth digits | U+FF10–U+FF19 (０–９) | 10 |
| Fullwidth uppercase | U+FF21–U+FF3A (Ａ–Ｚ) | 26 |
| Fullwidth lowercase | U+FF41–U+FF5A (ａ–ｚ) | 26 |
| **Total** | | **62** |

**Attack scenario**

1. Attacker registers `vit\uff41lik.eth` (using fullwidth `ａ`, U+FF41 — visually distinct from `a`).
2. Victim's wallet calls `normalize_name("vit\uff41lik.eth")`.
3. Normalization returns `"vitalik.eth"` — identical to the real target name.
4. The wallet resolves the name to the attacker's address.
5. The victim sees `"vitalik.eth"` displayed (the normalized form) and proceeds with the transaction.

Any application that: (a) displays the normalized name rather than the raw input, or (b) compares names in normalized form, is vulnerable to this attack.

**Reproduction (100% reproducible)**

```python
from ens.utils import normalize_name

# All 62 fullwidth characters fold silently to ASCII:
assert normalize_name("vit\uff41lik.eth") == "vitalik.eth"  # fullwidth a (ａ)
assert normalize_name("vit\uff21LIK.eth") == "vitalik.eth"  # fullwidth A folded then lowercased
assert normalize_name("\uff56\uff49\uff54\uff41\uff4c\uff49\uff4b.eth") == "vitalik.eth"  # all fullwidth

# Contrast — other homoglyphs correctly raise:
from ens.exceptions import InvalidName

try:
    normalize_name("vita\u043cik.eth")  # Cyrillic м (U+043C)
    assert False, "Should have raised"
except InvalidName:
    pass  # CORRECT — blocked

try:
    normalize_name("vitalik\u200b.eth")  # Zero-width space
    assert False, "Should have raised"
except InvalidName:
    pass  # CORRECT — blocked

# Only fullwidth silently passes through:
print(normalize_name("vit\uff41lik.eth"))  # 'vitalik.eth' — ATTACK SUCCEEDS
```

**Root cause**

This is a design tension in ENSIP-15 itself. The width-mapping step is included to allow CJK input-method users to type ASCII-equivalent names without keyboard switching. The mapping runs before the script-mixing checks that block other homoglyphs. The result is a gap where visually distinguishable characters produce identical normalized output. No existing CVE covers this specific vector in web3.py. The ACM Web Conference 2025 paper "Beyond Visual Confusion: Understanding How Inconsistencies in ENS Normalization Facilitate Homoglyph Attacks" identifies cross-app normalization inconsistency as a risk, but does not specifically document the fullwidth folding path in web3.py 7.14.1.

**Suggested mitigations (multiple options)**

1. **Detect and warn before normalization (recommended):** Before calling `normalize_name`, check whether the input contains any codepoint in U+FF10–U+FF5A and raise a warning or hard error with a message explaining the fullwidth folding.
2. **Reject-by-default in the normalizer:** Add an explicit check in the ENSIP-15 implementation that raises `InvalidName` when any fullwidth alphanumeric is detected, with a flag (`allow_fullwidth=True`) for applications that explicitly want the mapping behavior.
3. **Display raw input alongside resolved address:** Applications should always show the raw pre-normalization name to users, not just the normalized form, so the fullwidth characters are visible.

```python
# Minimal detection shim (option 1):
FULLWIDTH_RANGE = set(range(0xFF10, 0xFF1A)) | set(range(0xFF21, 0xFF3B)) | set(range(0xFF41, 0xFF5B))

def safe_normalize_name(name: str) -> str:
    for char in name:
        if ord(char) in FULLWIDTH_RANGE:
            raise ValueError(
                f"ENS name contains fullwidth character {char!r} (U+{ord(char):04X}) "
                f"that normalizes to ASCII equivalent. This may be a homoglyph attack."
            )
    return normalize_name(name)
```

**Severity:** CRITICAL

---

## Finding B2-01 (ANOMALY): `ABICodec.decode()` silently ignores trailing bytes

**Affected component**

Package: `eth-abi` 5.2.0 (web3.py dependency)
Function: `ABICodec.decode`

**Bug description**

`ABICodec.decode(["uint256"], data)` accepts input buffers with trailing bytes beyond the ABI-encoded length and silently ignores them. Truncated data (shorter than expected) correctly raises `InsufficientDataBytes`. Only the trailing direction is permissive. This matters in caller-side integrity checks: code that validates received payloads by decoding them and checking the value will not detect appended garbage bytes. In replay-protection schemes or signed-payload verification, undetected trailing data could be relevant. This is consistent with the Ethereum ABI specification, which does not require strict length checking — so this is an anomaly for caller awareness rather than a library defect.

**Reproduction**

```python
from eth_abi.codec import ABICodec
from eth_abi.registry import registry

codec = ABICodec(registry)
enc = codec.encode(["uint256"], [42])           # 32 bytes
extra = enc + b"\x00" * 32                      # 64 bytes — garbage appended
dec = codec.decode(["uint256"], extra)
assert dec[0] == 42                             # Correct value returned
assert len(extra) > 32                          # Extra bytes were present
# No exception. Trailing garbage silently dropped.
```

**Severity:** ANOMALY — recommend noting in eth-abi documentation that decode is not strict-length.

---

## Disclosure Timeline

We intend to publish our scan results publicly. We will not mention this specific finding or your package by name until you have had time to review and respond.

- **Day 0 (2026-03-29):** this report
- **Day 3:** please confirm receipt
- **Day 90 (2026-06-27):** public disclosure, or earlier if a fix or documented mitigation is available

Given the financial stakes of ENS name resolution (misresolved names lead to direct loss of ETH/tokens), we are prioritizing this report and are flexible on timeline if a design-level fix requires coordination with the ENS normalization standard body.

---

*Found by Nightjar's property-based testing pipeline. Reproduction environment: Python 3.14, web3 7.14.1, ens 7.14.1, eth-abi 5.2.0, Windows 11. B2-03 is 100% reproducible — `normalize_name("vit\uff41lik.eth")` always returns `"vitalik.eth"`.*
