## What does this PR do?

<!-- One or two sentences. Link the issue it closes if there is one. Closes #XXX -->

## Why?

<!-- What problem does this solve, and why this approach? -->

## Testing

<!-- How was this tested? Check all that apply. -->

- [ ] `pytest tests/ -v -m "not integration"` passes
- [ ] `pytest tests/ -v` passes (requires Dafny + LLM API key)
- [ ] Manually tested with `nightjar verify`
- [ ] New tests added for the changed behavior

## Checklist

- [ ] No classes added unless state management requires it
- [ ] All LLM calls go through litellm, not provider APIs directly
- [ ] No hardcoded model names — `NIGHTJAR_MODEL` env var used
- [ ] No edits to `.card/audit/` (that's generated code, read-only)
- [ ] If a new dependency was added, `nightjar lock` was run to update `deps.lock`
- [ ] If this implements a pattern from a paper, the commit is tagged `ref: [REF-XXX]`

## Notes for reviewer

<!-- Anything tricky, context that helps review, or things you're unsure about. -->
