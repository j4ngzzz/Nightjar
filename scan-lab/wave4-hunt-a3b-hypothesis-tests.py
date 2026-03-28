"""
Hypothesis property-based tests for google-adk v1.28.0
Targets: session/event management, tool execution, input validation/serialization
Run: python scan-lab/wave4-hunt-a3b-hypothesis-tests.py
"""
import asyncio
import sys

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ============================================================
# TARGET 1: extract_state_delta — key routing correctness
# ============================================================

from google.adk.sessions._session_util import extract_state_delta
from google.adk.sessions.state import State


@given(
    keys=st.lists(
        st.text(min_size=0, max_size=50,
                alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'))),
        min_size=0, max_size=20
    ),
    values=st.lists(st.integers() | st.text(max_size=20), min_size=0, max_size=20)
)
@settings(max_examples=200)
def test_extract_state_delta_routing(keys, values):
    """State keys must be routed to correct bucket. Temp keys must not leak."""
    pairs = dict(zip(keys, values))
    result = extract_state_delta(pairs)

    for key in pairs:
        if key.startswith(State.TEMP_PREFIX):
            stripped = key.removeprefix(State.TEMP_PREFIX)
            assert stripped not in result.get("app", {}), \
                f"temp key leaked to app: {key}"
            assert stripped not in result.get("user", {}), \
                f"temp key leaked to user: {key}"
            assert key not in result.get("session", {}), \
                f"temp key leaked to session: {key}"
        elif key.startswith(State.APP_PREFIX):
            stripped = key.removeprefix(State.APP_PREFIX)
            assert stripped in result["app"], f"app key '{key}' not in app bucket"
        elif key.startswith(State.USER_PREFIX):
            stripped = key.removeprefix(State.USER_PREFIX)
            assert stripped in result["user"], f"user key '{key}' not in user bucket"
        else:
            assert key in result["session"], f"session key '{key}' not in session bucket"


# ============================================================
# TARGET 2: Session ID whitespace bypass — silent overwrite bug
# ============================================================

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.errors.already_exists_error import AlreadyExistsError


@given(
    base_id=st.text(min_size=1, max_size=30,
                    alphabet=st.characters(whitelist_categories=('L', 'N'))),
    leading=st.text(min_size=1, max_size=5, alphabet=st.just(" ")),
    trailing=st.text(min_size=0, max_size=5, alphabet=st.just(" "))
)
@settings(max_examples=200)
def test_session_id_whitespace_no_duplicate(base_id, leading, trailing):
    """
    BUG: If session 'abc' exists, creating with '  abc  ' should raise AlreadyExistsError.
    ACTUAL: The duplicate check uses the raw (un-stripped) ID while storage uses the
    stripped ID, allowing silent session overwrites.
    """
    padded_id = leading + base_id + trailing

    async def run():
        svc = InMemorySessionService()
        await svc.create_session(app_name="app", user_id="u1",
                                 session_id=base_id,
                                 state={"version": "first"})
        try:
            s2 = await svc.create_session(app_name="app", user_id="u1",
                                           session_id=padded_id,
                                           state={"version": "second"})
            return False, f"Overwrote session '{base_id}' via padded_id '{padded_id}', got id='{s2.id}'"
        except AlreadyExistsError:
            return True, None

    ok, msg = asyncio.run(run())
    assert ok, f"DUPLICATE BYPASS (session silently overwritten): {msg}"


# ============================================================
# TARGET 3: State class — __contains__ vs __getitem__ consistency
# ============================================================


@given(
    value_keys=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10),
    delta_keys=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10),
    value_vals=st.lists(st.integers(), min_size=0, max_size=10),
    delta_vals=st.lists(st.integers(), min_size=0, max_size=10),
)
@settings(max_examples=200)
def test_state_contains_vs_getitem(value_keys, delta_keys, value_vals, delta_vals):
    """If __contains__ returns True for a key, __getitem__ must not raise KeyError."""
    value = dict(zip(value_keys, value_vals))
    delta = dict(zip(delta_keys, delta_vals))
    s = State(value, delta)

    all_keys = set(value.keys()) | set(delta.keys())
    for k in all_keys:
        assert k in s, f"key '{k}' in value/delta but __contains__ returned False"
        try:
            _ = s[k]
        except KeyError:
            assert False, f"__contains__=True for '{k}' but __getitem__ raised KeyError"

    for k in delta:
        assert s[k] == delta[k], f"Delta must override value for key '{k}'"


# ============================================================
# TARGET 4: State.to_dict() completeness
# ============================================================


@given(
    value_data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.integers(),
        max_size=10
    ),
    delta_data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.integers(),
        max_size=10
    ),
)
@settings(max_examples=200)
def test_state_to_dict_completeness(value_data, delta_data):
    """to_dict() must contain all keys, with delta winning on conflicts."""
    s = State(value_data.copy(), delta_data.copy())
    d = s.to_dict()

    all_keys = set(value_data.keys()) | set(delta_data.keys())
    for k in all_keys:
        assert k in d, f"Key '{k}' missing from to_dict() result"

    for k in delta_data:
        assert d[k] == delta_data[k], \
            f"Delta value not preserved in to_dict() for key '{k}'"


# ============================================================
# TARGET 5: BashToolPolicy prefix bypass — shell injection via chaining
# ============================================================

from google.adk.tools.bash_tool import _validate_command, BashToolPolicy


@given(
    allowed_prefix=st.text(
        min_size=2, max_size=10,
        alphabet=st.characters(whitelist_categories=('L', 'N'))
    ),
    separator=st.sampled_from([";", "\n", " && ", " | ", " & ", "$(", "`"])
)
@settings(max_examples=200)
def test_bash_policy_prefix_bypass_documents_flaw(allowed_prefix, separator):
    """
    BUG DOCUMENTATION: BashToolPolicy prefix validation uses startswith() only.
    Any command 'allowed_prefix<sep>dangerous' passes validation.
    This is a design flaw: prefix-only checks cannot prevent shell injection chaining.
    """
    policy = BashToolPolicy(allowed_command_prefixes=(allowed_prefix,))
    injected = allowed_prefix + separator + "cat /etc/shadow"

    error = _validate_command(injected, policy)
    # Document: these ALL return None (allowed) despite containing injection
    assert error is None, \
        f"Unexpected block for command starting with allowed prefix: {injected!r}"
    # The assertion passes — confirming the bypass works every time.


# ============================================================
# TARGET 6: Event ID uniqueness
# ============================================================

from google.adk.events.event import Event


@given(n=st.integers(min_value=2, max_value=100))
@settings(max_examples=200)
def test_event_id_uniqueness(n):
    """All events created in sequence must have unique IDs."""
    events = [Event(author="user") for _ in range(n)]
    ids = [e.id for e in events]
    assert len(ids) == len(set(ids)), \
        f"Duplicate event IDs found among {n} events"


# ============================================================
# TARGET 7: extract_state_delta with None/empty input
# ============================================================


def test_extract_state_delta_none_input():
    """extract_state_delta(None) should return empty buckets without exception."""
    result = extract_state_delta(None)
    assert result == {"app": {}, "user": {}, "session": {}}, \
        f"Unexpected result for None input: {result}"


def test_extract_state_delta_empty_input():
    """extract_state_delta({}) should return empty buckets."""
    result = extract_state_delta({})
    assert result == {"app": {}, "user": {}, "session": {}}, \
        f"Unexpected result for empty dict: {result}"


# ============================================================
# TARGET 8: Session event ordering — monotonicity preserved
# ============================================================


@given(n=st.integers(min_value=2, max_value=50))
@settings(max_examples=200)
def test_session_event_append_order_preserved(n):
    """Events appended to a session must be stored in append order (index-stable)."""
    async def run():
        svc = InMemorySessionService()
        session = await svc.create_session(app_name="app", user_id="u1")
        event_ids_in = []
        for _ in range(n):
            e = Event(author="user")
            event_ids_in.append(e.id)
            await svc.append_event(session, e)
        stored = await svc.get_session(app_name="app", user_id="u1",
                                        session_id=session.id)
        event_ids_out = [e.id for e in stored.events]
        return event_ids_in, event_ids_out

    ids_in, ids_out = asyncio.run(run())
    assert ids_in == ids_out, \
        f"Event order not preserved: in={ids_in[:3]}... out={ids_out[:3]}..."


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    import traceback

    PASS = "PASS"
    FAIL = "FAIL"

    tests = [
        ("1. extract_state_delta routing", test_extract_state_delta_routing),
        ("2. Session ID whitespace bypass (BUG)", test_session_id_whitespace_no_duplicate),
        ("3. State __contains__ vs __getitem__", test_state_contains_vs_getitem),
        ("4. State to_dict completeness", test_state_to_dict_completeness),
        ("5. BashTool prefix bypass (FLAW)", test_bash_policy_prefix_bypass_documents_flaw),
        ("6. Event ID uniqueness", test_event_id_uniqueness),
        ("7. extract_state_delta None input", test_extract_state_delta_none_input),
        ("8. extract_state_delta empty input", test_extract_state_delta_empty_input),
        ("9. Session event append order preserved", test_session_event_append_order_preserved),
    ]

    results = {}
    for name, test_fn in tests:
        print(f"Running: {name} ...", end=" ", flush=True)
        try:
            test_fn()
            results[name] = PASS
            print("PASS")
        except Exception as e:
            results[name] = f"FAIL: {e}"
            print(f"FAIL: {e}")

    print("\n=== FINAL SUMMARY ===")
    pass_count = sum(1 for v in results.values() if v == PASS)
    fail_count = len(results) - pass_count
    for name, status in results.items():
        marker = "[OK]  " if status == PASS else "[BUG] "
        print(f"  {marker} {name}: {status}")
    print(f"\nTotal: {pass_count} pass, {fail_count} fail")
