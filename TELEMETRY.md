# Nightjar Telemetry Policy

**Current status: Nightjar collects zero telemetry.** No data is sent anywhere when you run `nightjar` commands.

---

## Future Telemetry (not yet implemented)

If telemetry is added in a future version, it will follow these rules without exception:

### What would be collected (aggregate, anonymous)
- Command invoked (`verify`, `auto`, `build`, etc.) — not arguments
- Stage pass/fail bitmap (e.g. `[1,1,0,0,0]`) — not content
- Stage duration in ms per stage
- Python version, OS platform
- Nightjar version

### What will never be collected
- Spec content (`.card.md` file contents)
- Source code content
- File names or paths
- Error messages (which may contain code snippets)
- Any personally identifiable information
- IP addresses or device identifiers

### How opt-out will work
```bash
# Permanent opt-out
export NIGHTJAR_TELEMETRY=0

# Or in nightjar.toml
[telemetry]
enabled = false
```

The first run after telemetry is added will display a notice and require acknowledgment before any data is sent. There will be no silent opt-in.

### Source transparency
When telemetry is implemented, the exact events sent will be visible by running:
```bash
nightjar --debug-telemetry verify --spec your.card.md
```
This prints every telemetry event to stderr before transmission.

---

## Why document this before it exists

The AWS CDK telemetry incident (December 2025) and the Audacity fork (2021) both happened because telemetry was shipped without prior documentation. Community trust, once lost, is hard to rebuild.

Nightjar documents its telemetry policy before implementing it so that when it arrives, the community knows exactly what to expect.
