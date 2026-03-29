---
card-version: "1.0"
id: flask-login
title: Flask-Login Session Management — Community Spec
status: active
module:
  owns:
    - login_user()
    - logout_user()
    - load_user()
    - configure_login_manager()
  depends-on:
    Flask-Login: ">=0.6.3"
    Flask: ">=3.0.0"
  excludes:
    - "OAuth2 / OIDC provider integration"
    - "Two-factor authentication"
    - "JWT-based stateless sessions (use Flask-JWT-Extended for that)"
contract:
  inputs:
    - name: user
      type: object
      constraints: "user.is_active == True AND user.get_id() is not None AND str(user.get_id()) != ''"
    - name: remember
      type: bool
      constraints: "bool type — True enables remember-me cookie"
    - name: user_id
      type: string
      constraints: "len(user_id) > 0"
  outputs:
    - name: LoginResult
      type: object
      schema:
        success: bool
        session_regenerated: bool
        user_id: string
  errors:
    - UserNotFoundError
    - InactiveUserError
    - SessionFixationError
    - InvalidUserIDError
constraints:
  security: "OWASP Session Management Cheat Sheet — session regeneration on privilege change required"
  cookie: "remember-me cookie must set Secure and HttpOnly flags in non-debug environments"
invariants:
  - id: FLOG-INV-001
    tier: property
    statement: "login_user() succeeds when user.get_id() returns '0' (string) or 0 (integer) — zero is a valid user ID"
    rationale: "Flask-Login calls get_id() and stores the result. The user loader then receives this ID. Common wrapper code does `if not user_id: return None`, which treats '0' as falsy and returns None (anonymous user) for the user with ID 0. The correct guard is `if user_id is None:`. This is a real bug in Flask-Login tutorials and scaffolded code — any user whose DB primary key is 0 (or mapped to '0') is permanently locked out."
  - id: FLOG-INV-002
    tier: formal
    statement: "the Flask session ID changes between the pre-login and post-login requests — session regeneration must occur at login_user() time"
    rationale: "Session fixation attack: an attacker loads a page (getting a session ID), then tricks the victim into authenticating with that same session ID. After login, the server now associates the attacker's known session ID with the victim's account. Flask-Login does not automatically regenerate the session ID. Application code must call `session.clear()` or use Flask's `login_manager.session_protection='strong'` before calling login_user(). This invariant formalizes that the session ID at t=1 (after login) differs from the session ID at t=0 (before login)."
  - id: FLOG-INV-003
    tier: property
    statement: "current_user.is_authenticated returns exactly True (bool) — not 1, not 'yes', not a truthy object, exactly the bool True"
    rationale: "Flask-Login's UserMixin returns True from is_authenticated. However, custom user models frequently return `self.active` (an int) or override with `return self.role != 'anon'` (a string). Template code like `{% if current_user.is_authenticated %}` evaluates truthiness, hiding the bug. But code doing `assert user.is_authenticated is True` or using strict equality in test assertions will fail. The invariant requires the exact bool True to prevent subtle downstream type bugs."
  - id: FLOG-INV-004
    tier: property
    statement: "when remember=True, the remember-me cookie has Secure=True and HttpOnly=True in any environment where FLASK_ENV != 'development'"
    rationale: "The remember-me cookie is a long-lived credential (default 365 days). Without Secure flag, it is transmitted over HTTP and can be intercepted via network sniffing. Without HttpOnly, it can be stolen via XSS. Flask-Login sets these flags only when SESSION_COOKIE_SECURE and SESSION_COOKIE_HTTPONLY are configured. Applications deployed without these settings in production have a 365-day credential sitting in plaintext."
  - id: FLOG-INV-005
    tier: property
    statement: "load_user() returns None when user_id does not match any database record — it must never raise an unhandled exception"
    rationale: "Flask-Login calls the @login_manager.user_loader callback for every request. If the callback raises (e.g., database connection error, ORM exception), Flask-Login surfaces a 500 error and leaks stack traces. The callback contract is: return a User object or None. Exceptions must be caught and converted to None return (with appropriate logging)."
  - id: FLOG-INV-006
    tier: example
    statement: "login_user(user_with_id='user-99') followed by current_user.get_id() returns 'user-99'"
    rationale: "Smoke test: the identity round-trip. The user ID stored at login must be exactly retrievable from current_user. If get_id() returns a different type or representation, the user loader will fail to retrieve the user on subsequent requests."
---

## Intent

Wrap Flask-Login's session management with safe, explicit defaults. Flask-Login
is actively maintained but the documentation examples contain two well-known traps:
the user_id=0 falsy check in user loaders, and missing session regeneration on
login (session fixation vulnerability).

The session regeneration issue is particularly important: Flask-Login's
`session_protection='strong'` setting helps but is not a complete substitute
for explicit session regeneration. This spec formalizes what "correct" Flask-Login
usage looks like so Nightjar can verify it at generation time.

## Acceptance Criteria

### Story 1 — User Login (P1)

**As a** user, **I want** to log in, **so that** I can access my account.

1. **Given** a valid active user with id=1, **When** login_user(user) is called, **Then** current_user.is_authenticated returns True and current_user.get_id() returns '1'
2. **Given** a valid active user with id=0, **When** login_user(user) is called, **Then** login succeeds — id=0 is not treated as anonymous
3. **Given** a valid active user with id='0' (string), **When** login_user(user) is called, **Then** login succeeds — '0' is not falsy-checked
4. **Given** any login attempt, **When** login_user() completes successfully, **Then** the Flask session ID in the response differs from the session ID in the request

### Story 2 — User Logout (P2)

**As a** user, **I want** to log out, **so that** my session is terminated.

1. **Given** a logged-in user, **When** logout_user() is called, **Then** current_user.is_authenticated returns False
2. **Given** a logged-in user, **When** logout_user() is called, **Then** the session is cleared (no session data persists)
3. **Given** a logged-in user with a remember-me cookie, **When** logout_user() is called, **Then** the remember-me cookie is deleted (not just expired)

### Story 3 — User Loader (P3)

**As a** Flask-Login request cycle, **I want** to load the current user, **so that** current_user is populated on every request.

1. **Given** user_id='42' in the session, **When** load_user('42') is called, **Then** the User object with id=42 is returned
2. **Given** user_id='999' (no such user), **When** load_user('999') is called, **Then** None is returned (no exception)
3. **Given** user_id='0', **When** load_user('0') is called, **Then** the User object with id=0 is returned (not None)

### Edge Cases

- What if user.is_active returns False? → login_user() returns False without logging in
- What if the database is down during load_user()? → Exception caught, returns None, 401 response
- What if remember=True in a development environment? → Secure flag may be False, HttpOnly still True

## Functional Requirements

- **FR-FLOG-001**: System MUST regenerate the session ID on every call to login_user()
- **FR-FLOG-002**: System MUST guard user_id with `if user_id is None:` (not `if not user_id:`) in the user loader
- **FR-FLOG-003**: System MUST configure SESSION_COOKIE_SECURE=True and SESSION_COOKIE_HTTPONLY=True in production
- **FR-FLOG-004**: System MUST ensure is_authenticated, is_active, is_anonymous each return exact bool values (True/False)
- **FR-FLOG-005**: System MUST catch all exceptions in the user_loader callback and return None
- **FR-FLOG-006**: System MUST set login_manager.session_protection = 'strong' as a minimum baseline
