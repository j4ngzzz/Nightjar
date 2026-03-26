# nightjar-demo.tape — 30-second README GIF
# Shows: failed verification → fix → proved
# Reference: VHS (charmbracelet/vhs, MIT) [REF-NEW-12]
# Run: vhs demo/nightjar-demo.tape

Output demo/nightjar-demo.gif

Set Theme "Catppuccin Mocha"
Set FontSize 16
Set Width 900
Set Height 500
Set Framerate 30

# Show the spec
Type "cat demo/payment.card.md" Enter
Sleep 1.5s

# Clear and run verification (shows a failure first — more compelling demo)
Type "clear" Enter
Sleep 200ms
Type "nightjar verify demo/payment.card.md" Enter
Sleep 500ms

# Wait for each stage to stream through
Wait /Stage 0.*PASS/
Sleep 200ms
Wait /Stage 1.*PASS/
Sleep 200ms
Wait /Stage 2.*PASS/
Sleep 200ms

# Stage 3 or 4 should surface the counterexample
Wait /COUNTEREXAMPLE\|FAIL\|fail/
Sleep 2s

# Now fix it
Type "nightjar fix demo/payment.card.md" Enter
Sleep 500ms
Wait /PROVED\|VERIFIED\|verified/
Sleep 2s
