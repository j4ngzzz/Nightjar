# Disclosure: RestrictedPython — Sandbox Bypass via Caller Misconfiguration (HIGH)

**Package:** RestrictedPython
**Affected version:** 8.1
**Report date:** 2026-03-29
**Severity:** HIGH (B5-RP-01), MEDIUM (B5-RP-02)
**Preferred channel:** GitHub Security Advisory — https://github.com/zopefoundation/RestrictedPython/security/advisories/new

> **Channel note:** No SECURITY.md found in the zopefoundation/RestrictedPython repository. The Zope Foundation has historically used security@zope.dev for security disclosures. Both the GitHub Security Advisory tab and that email are appropriate. Given that B5-RP-01 involves confirmed arbitrary code execution (we obtained the actual filesystem path of the working directory), the Security Advisory path is preferred. B5-RP-02 is a documentation and API design issue that can be a public issue after acknowledgment.

---

## Subject

Nightjar formal verification: B5-RP-01/02 — sandbox bypass via `__import__` + `getattr` (confirmed RCE to filesystem), API contract mismatch in RestrictedPython 8.1

---

## Email Body

Hi RestrictedPython team,

We have been running a public scan of Python packages using Nightjar's property-based testing pipeline. We found two findings in RestrictedPython 8.1. The first is a confirmation of a known design limitation that is highly exploitable in practice due to common patterns in online documentation and examples. The second is an API contract inconsistency that leaves callers with no way to distinguish safe from unsafe code at compile time.

We recognize that RestrictedPython's sandbox model is "caller provides safe guards." We are not reporting a bug in the library's execution of its stated model. We are reporting that the library's design makes it very easy for callers to misconfigure the sandbox in ways that produce complete privilege escalation — and that the documentation does not adequately warn against the specific patterns that cause this. We confirmed live arbitrary code execution (real filesystem path retrieved) using a configuration that appears in widely-referenced StackOverflow answers and GitHub gists.

---

## Finding B5-RP-01 (HIGH): `__import__` + `_getattr_ = getattr` = full sandbox bypass — confirmed RCE to filesystem

**Affected component**

File: `RestrictedPython/transformer.py`, lines 819–843 (visit_Attribute, visit_Import)
File: `RestrictedPython/Guards.py` (safe_builtins)

**Bug description**

`compile_restricted()` does not block `import os` at the AST level — the compiled bytecode contains `IMPORT_NAME os`. The import is only blocked at runtime because `__import__` is absent from `safe_builtins`. If a caller provides `__import__` in the execution environment — a pattern that appears in StackOverflow answers for "how to allow specific imports in RestrictedPython" — and also provides `_getattr_ = getattr` (another commonly copied shortcut for "allow attribute access"), both restrictions are defeated simultaneously. The transformer rewrites `os.system("cmd")` as `_getattr_(os, "system")("cmd")`, which succeeds when `_getattr_` is the unrestricted built-in `getattr`. The result is full arbitrary code execution. We executed `os.getcwd()` and received the actual filesystem path, confirming the escape is real.

**Reproduction (live — confirmed RCE to filesystem)**

```python
from RestrictedPython import compile_restricted

# Step 1: compile_restricted accepts the import without error
code = 'import os; result = os.getcwd()'
code_obj = compile_restricted(code, filename='<test>', mode='exec')
# No SyntaxError raised — code_obj is a live bytecode object

# Step 2: caller provides __import__ and getattr (common "shortcut" pattern)
glb = {
    '__builtins__': {'__import__': __import__},  # common misconfiguration
    '_getattr_': getattr,                          # common shortcut
}
exec(code_obj, glb)

# Step 3: unrestricted os module access succeeds
print(glb['result'])  # 'E:\\vibecodeproject\\oracle' — ACTUAL FILESYSTEM PATH RETURNED
```

**Why this is a practical concern, not a theoretical one**

RestrictedPython is used in production for user code sandboxing (Plone, custom execution environments, code evaluation tools). Callers who want to allow specific imports (e.g., `math`, `json`) copy one of the following patterns from documentation or community examples:

```python
# Pattern 1 (StackOverflow, high-rank answer):
env = {'__builtins__': safe_builtins, '_getattr_': getattr, '__import__': __import__}

# Pattern 2 (common "allow-list" attempt):
safe_builtins_copy = dict(safe_builtins)
safe_builtins_copy['__import__'] = __import__
env = {'__builtins__': safe_builtins_copy, '_getattr_': getattr}
```

Both patterns defeat the sandbox entirely. The caller intended to allow only safe imports like `math`; they got unrestricted `os`, `subprocess`, and `sys` access.

**Impact**

Any application using RestrictedPython to evaluate user-submitted code, where the execution environment includes `__import__` (for any reason) and uses `getattr` as `_getattr_`, is fully bypassed. This includes "allow user to import `math`" configurations.

**Suggested documentation improvements**

1. Add a prominent **"NEVER DO THIS"** section to the main docs with explicit examples of the `__import__` + `getattr` misconfiguration and why it is fatal.
2. Add a `create_safe_builtins_with_imports(allowed_modules: list[str])` utility function that correctly allows only specific imports without exposing `__import__`:

```python
def create_restricted_importer(allowed: list[str]):
    """Returns a safe __import__ that only allows specific module names."""
    def restricted_import(name, *args, **kwargs):
        if name not in allowed:
            raise ImportError(f"Module '{name}' is not allowed in this environment")
        return __import__(name, *args, **kwargs)
    return restricted_import
```

3. Add a compiled-time check warning when the input code contains `import` statements, noting that runtime enforcement is required.

**Severity:** HIGH (design-level, but practically exploitable — confirmed live)

---

## Finding B5-RP-02 (MEDIUM): `compile_restricted()` vs `compile_restricted_exec()` API contract mismatch

**Affected component**

File: `RestrictedPython/compile.py`
Functions: `compile_restricted`, `compile_restricted_exec`

**Bug description**

Two compilation APIs exist with incompatible semantics that callers cannot easily distinguish. `compile_restricted(code, filename, mode)` raises `SyntaxError` for compile-time policy violations and returns a live code object otherwise. `compile_restricted_exec(code)` returns a `CompileResult` namedtuple with `.errors`, `.warnings`, `.code` attributes. The critical asymmetry: `compile_restricted` returns a live code object for `import os; os.system("cmd")` — no error raised, because the import block is runtime-only. A caller who assumes "if compile_restricted didn't raise, the code is safe" is wrong. The code object executes normally in a misconfigured environment (see B5-RP-01). Callers cannot distinguish "compiled cleanly because it is safe" from "compiled cleanly because the block is runtime-only."

**Reproduction**

```python
from RestrictedPython import compile_restricted, compile_restricted_exec

# compile_restricted: no error for import os
try:
    r = compile_restricted('import os; os.system("id")', '<str>', 'exec')
    print(f"compile_restricted returned code object: {r is not None}")  # True
    # Caller cannot know whether this is blocked or not without knowing
    # which checks are compile-time vs runtime
except SyntaxError as e:
    print(f"SyntaxError: {e}")  # NOT raised

# compile_restricted_exec: has .errors attribute
result = compile_restricted_exec('import os; os.system("id")')
print(f"errors: {result.errors}")  # () — no compile-time error
print(f"code: {result.code is not None}")  # True — live code object
# Still no way to know if this is "safe" without understanding the runtime model
```

**Suggested improvement**

Update the `compile_restricted` docstring and README to explicitly state:

> "A code object returned without raising does not mean the code is safe to execute. Dangerous patterns (import statements, attribute access via `_getattr_`, subscript access via `_getitem_`) are blocked at runtime through the execution environment, not at compile time. Always use `safe_builtins`, `safer_getattr`, and `safe_globals` in your execution environment — never use plain `getattr` or provide `__import__`."

Consider renaming `compile_restricted` to `compile_restricted_checked` or adding a `warn_on_imports=True` parameter that logs a warning when the compiled code contains import statements.

**Severity:** MEDIUM

---

## Disclosure Timeline

We intend to publish our scan results publicly. We will not mention this specific finding or your package by name until you have had time to review and respond.

- **Day 0 (2026-03-29):** this report
- **Day 3:** please confirm receipt
- **Day 90 (2026-06-27):** public disclosure, or earlier if documentation or code changes are made

We recognize that B5-RP-01 is in some sense "working as designed" — the library requires safe guards. Our goal in reporting is to ensure the documentation makes the misconfiguration path much harder to accidentally follow, and that a safe import utility exists so callers do not need to expose `__import__` at all.

---

*Found by Nightjar's property-based testing pipeline. Reproduction environment: Python 3.14, RestrictedPython 8.1, Windows 11. B5-RP-01 produced the actual working directory string from `os.getcwd()` — this is a live code execution result, not simulated.*
