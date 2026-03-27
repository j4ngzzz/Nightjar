# Changelog

All notable changes to Nightjar are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-03-27

### Added

**Core Verification Pipeline**
- 5-stage pipeline: preflight, dependency audit, schema validation (Pydantic v2), property-based testing (Hypothesis), formal verification (Dafny + CrossHair)
- Stage 2.5: Negation-proof spec validation
- Verification confidence score 0-100
- Behavioral safety gate

**Advanced Verification Engine**
- Spec preprocessing with 19 Proven rewrite rules
- CEGIS counterexample-guided retry loop
- LP dual root-cause diagnosis with shadow prices
- Complexity-discriminated routing (CrossHair for simple, Dafny for complex)
- DafnyPro structured error extraction

**Immune System — Runtime Invariant Mining**
- Clean-room Daikon trace mining via sys.monitoring
- Houdini fixed-point filter
- MINES web API pattern mining
- Wonda quality scoring (4-criteria filter)
- Test oracle lifting from existing assertions
- Adversarial debate for invariant validation
- Temporal fact supersession with exponential decay

**Developer Experience**
- `nightjar auto`: generate .card.md specs from natural language intent
- `nightjar watch`: file-watching daemon with tiered verification
- `nightjar badge`: shields.io badge generation
- Textual TUI dashboard
- Rich streaming DisplayCallback interface
- VHS declarative demo tapes

**Observability & Compliance**
- Sentry error tracking with immune system feed
- Blast radius analysis hooks
- Playwright browser end-to-end tests
- EU CRA compliance report generation
- OWASP security pack
- Shadow CI GitHub Actions integration
