# nightjar-demo.tape — 30-second README GIF
# Shows: failed verification → counterexample-guided retry → proved
# Reference: VHS (charmbracelet/vhs, MIT) [REF-NEW-12]
# Run (Windows): docker run --rm -v ${PWD}:/vhs ghcr.io/charmbracelet/vhs demo/nightjar-demo.tape
# Run (Linux/Mac): vhs demo/nightjar-demo.tape

Output demo/nightjar-demo.gif

Set Shell "bash"
Set Theme "Catppuccin Mocha"
Set FontFamily "JetBrains Mono"
Set FontSize 16
Set Width 1000
Set Height 550
Set Framerate 30
Set TypingSpeed 75ms
Set CursorBlink false
Set WindowBar Colorful
Set BorderRadius 8
Set Margin 30
Set MarginFill "#1e1e2e"
Set LoopOffset 50%

# Force Rich/Textual true-color rendering inside VHS capture
Env COLORTERM "truecolor"
Env TERM "xterm-256color"
Env FORCE_COLOR "1"

# Silent setup — never appears in recording
Hide
Type "pip install -e . -q 2>/dev/null; clear" Enter
Sleep 2s
Show

# Show the broken spec
Type "cat demo/payment.card.md" Enter
Sleep 2s

Type "clear" Enter
Sleep 200ms

# Run verification — this should FAIL with a counterexample
Type "nightjar verify demo/payment.card.md" Enter
Sleep 300ms

Wait+Screen /Stage 0.*PASS/
Sleep 150ms
Wait+Screen /Stage 1.*PASS/
Sleep 150ms
Wait+Screen /Stage 2.*PASS/
Sleep 150ms

# Stage 3 or 4 surfaces the counterexample
Wait+Screen@60s /COUNTEREXAMPLE|FAIL|fail/
Sleep 2.5s

Type "clear" Enter
Sleep 200ms

# Counterexample-guided retry — fixes the spec and re-verifies
Type "nightjar retry demo/payment.card.md" Enter
Sleep 300ms

Wait+Screen@120s /PROVED|VERIFIED|verified/
Sleep 3s
