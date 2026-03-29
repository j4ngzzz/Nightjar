# aha-moment.tape — 90-second "aha moment" demo recording
# Story: Nightjar finds a hidden bug → counterexample shown → fix applied → formally proved
# Reference: VHS (charmbracelet/vhs, MIT) [REF-NEW-12]
# Research: "The Aha Moment Tutorial" — research-vscode-education.md
#
# Run (Docker, any platform):
#   docker run --rm -v ${PWD}:/vhs ghcr.io/charmbracelet/vhs demo/aha-moment.tape
# Run (native, Linux/Mac):
#   vhs demo/aha-moment.tape
# Output: demo/aha-moment.gif (embed in README, dev.to, HN post)

Output demo/aha-moment.gif

Set Shell "bash"
Set Theme "Catppuccin Mocha"
Set FontFamily "JetBrains Mono"
Set FontSize 18
Set Width 1000
Set Height 600
Set Framerate 30
Set TypingSpeed 40ms
Set CursorBlink false
Set WindowBar Colorful
Set BorderRadius 8
Set Margin 24
Set MarginFill "#1e1e2e"

# Preserve true-color output from Rich / nightjar CLI
Env COLORTERM "truecolor"
Env TERM "xterm-256color"
Env FORCE_COLOR "1"

# ── Silent setup — never visible ────────────────────────────────────────────
Hide
Type "pip install -e . -q 2>/dev/null; clear" Enter
Sleep 3s
Show

# ════════════════════════════════════════════════════════════════════════════
# ACT 1 — The Spec (10 seconds)
# Show the payment spec so the audience knows what we're verifying.
# ════════════════════════════════════════════════════════════════════════════

Type "# Step 1: write the spec — one critical invariant"
Sleep 600ms
Enter
Sleep 300ms

Type "cat demo/tutorial-payment.card.md" Enter
Sleep 2.5s

Type "clear" Enter
Sleep 200ms

# ════════════════════════════════════════════════════════════════════════════
# ACT 2 — The Bug (20 seconds)
# Run verification on the buggy code. Stage 3 finds the counterexample.
# ════════════════════════════════════════════════════════════════════════════

Type "# Step 2: verify — let Nightjar find what unit tests miss"
Sleep 600ms
Enter
Sleep 300ms

Type "nightjar verify demo/tutorial-payment.card.md" Enter
Sleep 400ms

# Watch stages pass one by one — audience sees real pipeline work
Wait+Screen /Stage 0.*PASS/
Sleep 400ms
Wait+Screen /Stage 1.*PASS/
Sleep 400ms
Wait+Screen /Stage 2.*PASS/
Sleep 400ms

# Stage 3 surfaces the counterexample — this is the aha moment
Wait+Screen@60s /COUNTEREXAMPLE|Counterexample|counterexample|FAIL|amount=-/
Sleep 3s

Type "clear" Enter
Sleep 300ms

# ════════════════════════════════════════════════════════════════════════════
# ACT 3 — The Fix (15 seconds)
# Show the one-line fix that closes the gap.
# ════════════════════════════════════════════════════════════════════════════

Type "# Step 3: the fix is one guard clause"
Sleep 600ms
Enter
Sleep 300ms

Type "python -c \"" Enter
Sleep 100ms
Type "import re, pathlib" Enter
Sleep 100ms
Type "src = pathlib.Path('demo/tutorial-payment.py').read_text()" Enter
Sleep 100ms
Type "fixed = src.replace(" Enter
Sleep 100ms
Type "    '    # BUG: missing validation — amount <= 0 silently accepted'," Enter
Sleep 100ms
Type "    '    if amount <= 0: raise ValueError(f\\\"amount must be positive, got {amount}\\\")')" Enter
Sleep 100ms
Type "pathlib.Path('demo/tutorial-payment.py').write_text(fixed)" Enter
Sleep 100ms
Type "print('Fixed: added amount > 0 guard')" Enter
Type "\"" Enter
Sleep 1.5s

Type "clear" Enter
Sleep 200ms

# ════════════════════════════════════════════════════════════════════════════
# ACT 4 — The Proof (20 seconds)
# Re-run verification. All stages pass. Formal proof delivered.
# ════════════════════════════════════════════════════════════════════════════

Type "# Step 4: re-verify — get a mathematical proof"
Sleep 600ms
Enter
Sleep 300ms

Type "nightjar verify demo/tutorial-payment.card.md" Enter
Sleep 400ms

Wait+Screen /Stage 0.*PASS/
Sleep 300ms
Wait+Screen /Stage 1.*PASS/
Sleep 300ms
Wait+Screen /Stage 2.*PASS/
Sleep 300ms
Wait+Screen /Stage 3.*PASS/
Sleep 500ms

# Stage 4 formal verification — the "FORMALLY VERIFIED" payoff
Wait+Screen@120s /VERIFIED|PROVED|verified|proved/
Sleep 3.5s

Type "clear" Enter
Sleep 300ms

# ════════════════════════════════════════════════════════════════════════════
# ACT 5 — The Kicker (10 seconds)
# Land the value proposition. Show the install command.
# ════════════════════════════════════════════════════════════════════════════

Type "# Nightjar found 74 bugs in popular Python packages."
Sleep 700ms
Enter
Sleep 200ms
Type "# What will it find in yours?"
Sleep 700ms
Enter
Sleep 1s

Type "pip install nightjar-verify" Enter
Sleep 2.5s
