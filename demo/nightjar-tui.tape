# nightjar-tui.tape — TUI dashboard showcase GIF
# Shows the Textual TUI with 5 collapsible stage panels + confidence bar
# Reference: VHS (charmbracelet/vhs, MIT) [REF-NEW-12]
# Run: vhs demo/nightjar-tui.tape
# NOTE: Requires U3.1 Textual TUI to be wired into nightjar verify

Output demo/nightjar-tui.gif

Set Theme "Catppuccin Mocha"
Set FontSize 15
Set Width 1000
Set Height 600
Set Framerate 30

# Launch TUI-mode verification
Type "nightjar verify --tui demo/payment.card.md" Enter
Sleep 500ms

# Stages animate live: waiting → running → PASS
Wait /Stage 0.*PASS/
Sleep 300ms
Wait /Stage 1.*PASS/
Sleep 300ms
Wait /Stage 2.*PASS/
Sleep 300ms
Wait /Stage 3.*PASS/
Sleep 300ms

# Formal verification — takes longer, show confidence bar climbing
Wait /Stage 4/
Sleep 1.5s
Wait /VERIFIED\|PROVED/
Sleep 3s

# Quit TUI
Type "q"
Sleep 500ms
