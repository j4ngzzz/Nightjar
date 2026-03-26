---
card-version: "1.0"
id: user-auth
title: User Authentication
status: draft
module:
  owns: [login(), logout(), validate_token()]
  depends-on:
    postgres: "approved"
    bcrypt: "^4.0"
  excludes:
    - "OAuth2 social login"
contract:
  inputs:
    - name: email
      type: string
    - name: password
      type: string
  outputs:
    - name: session_token
      type: string
  errors:
    - AuthError
  events-emitted:
    - user.login
invariants:
  - id: INV-001
    tier: property
    statement: "A valid token always corresponds to exactly one active user session"
    rationale: "Prevents session hijacking and token reuse"
---

## Intent

Let users log in with email/password and get a session token.

## Acceptance Criteria

### Story 1 — Login (P1)

**As a** user, **I want** to log in with my email and password, **so that** I can access my account.

1. **Given** valid credentials, **When** login() is called, **Then** a JWT is returned
2. **Given** invalid password, **When** login() is called, **Then** AuthError is raised
