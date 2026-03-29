# Dafny Setup Guide

> **Dafny is optional.** Nightjar works without it. If you just want property-based testing and schema validation, skip this page and run `nightjar verify --fast`.

---

## 1. Do You Need Dafny?

Nightjar runs a 6-stage pipeline. The first four stages require zero external tools:

| Stage | What it checks | Requires Dafny? |
|-------|---------------|-----------------|
| 0 — Preflight | Spec syntax, completeness | No |
| 1 — Deps | Dependency security (pip-audit) | No |
| 2 — Schema | Pydantic contract validation | No |
| 3 — PBT | Property-based testing (Hypothesis) | No |
| 2.5 — Negation | Falsification via counterexample | No |
| **4 — Formal** | **Mathematical proof for all inputs** | **Yes** |

**Stage 4 adds one guarantee the others cannot:** it proves your code's contracts hold for every possible input, not just the inputs Hypothesis happened to generate. If your spec has `tier: formal` invariants, Stage 4 is where they get discharged.

If your specs only use `tier: property` or `tier: example` invariants, you can skip Dafny entirely and still get useful results from Stages 0–3.

---

## 2. Installing Dafny

Dafny 4.x ships as a self-contained binary that bundles its own .NET 8 runtime. You do **not** need to install .NET separately.

### Windows

```bash
# Download and extract
curl -LO https://github.com/dafny-lang/dafny/releases/download/v4.8.0/dafny-4.8.0-x64-win.zip
unzip dafny-4.8.0-x64-win.zip

# Add the extracted folder to PATH (bash/Git Bash)
export PATH="$PATH:$(pwd)/dafny"

# Verify
dafny --version
```

In PowerShell, set the path permanently:

```powershell
$env:PATH += ";C:\path\to\dafny"
# Or use DAFNY_PATH to point directly at the binary:
$env:DAFNY_PATH = "C:\path\to\dafny\dafny.exe"
```

### macOS

```bash
curl -LO https://github.com/dafny-lang/dafny/releases/download/v4.8.0/dafny-4.8.0-x64-osx.zip
unzip dafny-4.8.0-x64-osx.zip
chmod +x dafny/dafny
export PATH="$PATH:$(pwd)/dafny"
dafny --version
```

### Linux

```bash
curl -LO https://github.com/dafny-lang/dafny/releases/download/v4.8.0/dafny-4.8.0-x64-linux.zip
unzip dafny-4.8.0-x64-linux.zip
chmod +x dafny/dafny
export PATH="$PATH:$(pwd)/dafny"
dafny --version
```

> **Note:** Dafny's bundled .NET 8 binary requires **glibc**. Alpine Linux uses musl and is incompatible — use a glibc-based distro (Debian, Ubuntu, Fedora, etc.).

### Docker (zero local install)

The published Nightjar image bundles Dafny. No installation needed.

```bash
# Build from source
docker build -t nightjar .

# Or pull the published image
docker pull ghcr.io/nightjar-dev/nightjar

# Run verification against your project
docker run --rm -v $(pwd):/workspace nightjar verify --spec .card/payment.card.md

# Run the full build pipeline
docker run --rm -v $(pwd):/workspace nightjar build --target py
```

The Docker image is built on `python:3.11-slim` (Debian-based, glibc) with the runtime libraries Dafny needs: `libicu`, `libssl3`, `zlib1g`.

---

## 3. Custom Dafny Path

If Dafny is installed somewhere that is not on your `PATH`, point Nightjar at the binary directly:

```bash
# Point to the binary file itself, not its parent directory
export DAFNY_PATH=/opt/dafny-4.8.0/dafny

nightjar verify --spec .card/payment.card.md
```

Nightjar resolves Dafny in this order:

1. `shutil.which("dafny")` — standard PATH lookup
2. `DAFNY_PATH` environment variable — must be the **full path to the binary file**

`DAFNY_PATH` must point to the executable file itself, not the directory that contains it. Setting `DAFNY_PATH=/opt/dafny-4.8.0` (directory) will not work; use `DAFNY_PATH=/opt/dafny-4.8.0/dafny` (binary).

---

## 4. What Happens Without Dafny

If Dafny is not found, what happens depends on whether your spec has `tier: formal` invariants:

- **No `tier: formal` invariants** — Stage 4 is **skipped** (`SKIP`). The pipeline completes normally.
- **Has `tier: formal` invariants** — Stage 4 returns **FAIL** with a `dafny_not_found` error. Install Dafny or remove `tier: formal` from your spec to proceed.

Example output when no formal-tier invariants are present:

```
Stage 0: PASS  preflight checks passed
Stage 1: PASS  dependency audit clean
Stage 2: PASS  schema validation passed
Stage 3: PASS  property-based tests passed (1000 examples)
Stage 4: SKIP  no formal-tier invariants — Dafny stage skipped
```

Use `nightjar verify --fast` to bypass Stage 4 regardless of invariant tier.

What you still get:
- Full Stages 0–3 results
- CrossHair symbolic execution as a lightweight formal fallback (install with `pip install crosshair-tool`)
- A confidence score based on PBT coverage density
- All violations surfaced by Hypothesis across the property-tier invariants

What you miss:
- Mathematical proof that contracts hold for **all** inputs, including adversarial edge cases that Hypothesis did not generate
- Termination guarantees (decreases clauses)
- Frame conditions (reads/modifies clauses)

If you want Stage 4 but not the full Dafny install right now, `pip install crosshair-tool` gives symbolic execution coverage for most Python-expressible properties.

---

## 5. Dafny Error Translation

When Stage 4 fails, Nightjar translates Dafny's low-level error messages into Python-developer-friendly explanations.

| Dafny says | What it means | Where to look |
|-----------|---------------|--------------|
| `A postcondition might not hold on this return path` | Your `ensures` clause (return-value guarantee) cannot be proven | Add loop invariants or intermediate assertions that accumulate toward the postcondition |
| `A precondition for this call might not hold` | The caller does not satisfy the `requires` clause of a function it calls | Strengthen the caller's preconditions or prove the argument is in range |
| `This assertion might not hold` | An explicit `assert` statement could be false | Add intermediate assertions to narrow down which assumption is wrong |
| `This loop invariant might not be maintained` | The invariant is not preserved by one iteration | Check that the invariant accounts for all ways the loop body mutates state |
| `This loop invariant might not hold on entry` | The invariant is false before the first iteration | Weaken the invariant or establish it before the loop |
| `A termination check might fail` | Dafny cannot prove the loop or recursion terminates | Add or tighten a `decreases` clause |
| `The reads clause may not include sufficient objects` | A function reads heap state not declared in its `reads` clause | Widen the `reads` clause or make the function pure |
| `Index out of range` | Array or sequence access might be out of bounds | Add a bounds precondition (`requires 0 <= i < a.Length`) |

Nightjar surfaces the translated message alongside the raw Dafny output, the file/line, and a fix hint. The CEGIS retry loop then attempts an automatic annotation repair before escalating to you.

---

## 6. Troubleshooting

**`dafny: command not found`**

Dafny is not on your PATH. Either add the extracted `dafny/` folder to PATH, or set `DAFNY_PATH` to the full path of the binary:

```bash
export DAFNY_PATH=/path/to/dafny/dafny
nightjar verify
```

**`Dafny timeout` / verification hangs**

The per-assertion timeout is hardcoded to 15 seconds in Stage 4 (`DAFNY_VERIFY_TIMEOUT`). If verification times out on a complex spec, the two practical options are:

- Skip Stage 4 for this run: `nightjar verify --fast`
- Simplify the invariants in your `.card.md` spec to reduce SMT solver load (fewer quantifiers, tighter bounds)

**`.NET runtime error` or missing shared library**

Dafny 4.x bundles its own .NET 8 runtime — you do not need a separate .NET installation. If you see shared library errors on Linux, install the runtime dependencies:

```bash
# Debian / Ubuntu
sudo apt-get install -y libicu-dev libssl3 zlib1g

# Fedora / RHEL
sudo dnf install -y libicu openssl-libs zlib

# Alpine is not supported — Dafny requires glibc, not musl
```

**`DAFNY_PATH set but Dafny still not found`**

`DAFNY_PATH` must point to the binary file, not its parent directory:

```bash
# Wrong — points to directory
export DAFNY_PATH=/opt/dafny

# Correct — points to the binary
export DAFNY_PATH=/opt/dafny/dafny
```

---

## Summary

- Run `nightjar verify --fast` to skip Dafny and still get Stages 0–3.
- Install Dafny 4.8.0 from the [GitHub releases page](https://github.com/dafny-lang/dafny/releases).
- Dafny bundles its own .NET 8 — no separate runtime needed.
- Set `DAFNY_PATH` to the **binary file path**, not the directory.
- On Linux, use a glibc-based distro. Alpine is incompatible.
- Use the Docker image for a zero-install verified environment.
