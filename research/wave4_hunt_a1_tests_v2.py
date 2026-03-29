"""
Wave 4 HUNT-A1 v2: Fixed property-based tests for langchain-core + langgraph.
Packages: langchain-core==1.2.23, langgraph==1.1.3 (langgraph-checkpoint==4.0.1)
Run: python wave4_hunt_a1_tests_v2.py
"""
import warnings
warnings.filterwarnings("ignore")

import json
import sys
import uuid
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ─── TARGET 1: langchain_core serialization round-trip ───────────────────────
print("=" * 60)
print("TARGET 1: langchain_core serialization round-trip (AIMessage)")
print("=" * 60)

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.load import dumpd, dumps, loads, load

@given(
    content=st.text(min_size=0, max_size=200),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_aimessage_roundtrip_content(content):
    """AIMessage round-trip: dumpd then load should give equal content."""
    msg = AIMessage(content=content)
    data = dumpd(msg)
    restored = load(data, allowed_objects="core")
    assert restored.content == msg.content, (
        f"CONTENT MISMATCH: original={msg.content!r} restored={restored.content!r}"
    )

@given(
    content=st.text(min_size=0, max_size=100),
    extra_val=st.one_of(st.just(""), st.just(0), st.just(False), st.just(None)),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_aimessage_additional_kwargs_falsy(content, extra_val):
    """Falsy values in additional_kwargs must survive serialization round-trip."""
    msg = AIMessage(content=content, additional_kwargs={"key": extra_val})
    data = dumpd(msg)
    restored = load(data, allowed_objects="core")
    assert restored.additional_kwargs == msg.additional_kwargs, (
        f"KWARGS MISMATCH: original={msg.additional_kwargs!r} "
        f"restored={restored.additional_kwargs!r}"
    )

@given(
    content=st.text(min_size=1, max_size=100),
    inner_type=st.sampled_from(["constructor", "secret", "not_implemented"]),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_lc_key_injection_guard(content, inner_type):
    """Regression CVE-2025-68664: user data with 'lc' keys must NOT be
    deserialized as LC objects after the fix."""
    crafted = {
        "lc": 1,
        "type": inner_type,
        "id": ["langchain_core", "messages", "ai", "AIMessage"],
        "kwargs": {"content": content},
    }
    msg = AIMessage(content=content, additional_kwargs={"lc_payload": crafted})
    data = dumpd(msg)
    json_str = json.dumps(data)
    try:
        restored = loads(json_str, allowed_objects="core")
        nested = restored.additional_kwargs.get("lc_payload")
        if nested is not None:
            assert not isinstance(nested, AIMessage), (
                f"REGRESSION BUG CVE-2025-68664: crafted lc-key dict was "
                f"deserialized as AIMessage! content={content!r} type={inner_type!r}"
            )
    except (ValueError, NotImplementedError):
        pass  # Rejection is also correct

@given(
    content=st.lists(
        st.one_of(
            st.text(min_size=0, max_size=50),
            st.fixed_dictionaries({"type": st.just("text"), "text": st.text(max_size=50)}),
        ),
        min_size=0, max_size=5,
    )
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_humanmessage_list_content_roundtrip(content):
    """HumanMessage with list content must survive round-trip."""
    msg = HumanMessage(content=content)
    data = dumpd(msg)
    restored = load(data, allowed_objects="core")
    assert restored.content == msg.content, (
        f"LIST CONTENT MISMATCH: original={msg.content!r} restored={restored.content!r}"
    )

# ─── TARGET 2: RunnableLambda type coercion ───────────────────────────────────
print()
print("=" * 60)
print("TARGET 2: RunnableLambda type coercion edge cases")
print("=" * 60)

from langchain_core.runnables import RunnableLambda

@given(
    input_val=st.one_of(
        st.integers(),
        st.text(),
        st.booleans(),
        st.none(),
        st.lists(st.integers()),
        st.dictionaries(st.text(min_size=1, max_size=10), st.integers()),
    )
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_runnable_lambda_identity(input_val):
    """RunnableLambda(identity) must return the same value for any input."""
    r = RunnableLambda(lambda x: x)
    result = r.invoke(input_val)
    assert result == input_val, (
        f"IDENTITY MISMATCH: input={input_val!r} output={result!r}"
    )

# ─── TARGET 3: StateGraph.add_conditional_edges routing validation ─────────────
print()
print("=" * 60)
print("TARGET 3: StateGraph.add_conditional_edges routing")
print("=" * 60)

from langgraph.graph import StateGraph, END

@given(
    bad_name=st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    ).filter(lambda x: x not in ("node_a", "node_b", END, "__end__", ""))
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_conditional_edge_no_pathmap_invalid_node_silent(bad_name):
    """
    BUG PROBE: When no path_map is given, router returning an unknown node name
    should raise (or warn), but instead graph.invoke() silently returns
    without routing anywhere. Only a WARNING log is emitted.

    Expected contract: raise ValueError or GraphBuildException on invalid node.
    Actual behavior: silent no-op — graph terminates without routing.
    """
    visited_b = []

    def track_b(s):
        visited_b.append(True)
        return s

    builder = StateGraph(dict)
    builder.add_node("node_a", lambda s: s)
    builder.add_node("node_b", track_b)
    builder.set_entry_point("node_a")
    builder.add_conditional_edges("node_a", lambda s: bad_name)
    builder.add_edge("node_b", END)

    try:
        graph = builder.compile()
        graph.invoke({"sentinel": True})
        # If we reach here: node_b should have been visited. If not — silent routing failure.
        if not visited_b:
            # This is the actual bug: routing silently dropped to nowhere
            # We record it but do NOT raise here — the test is probing, not asserting
            # (the assert below will surface it as a confirmed finding)
            assert False, (
                f"SILENT ROUTING FAILURE: router returned {bad_name!r} (not a valid node), "
                f"graph.invoke() returned without error and without routing to node_b. "
                f"A WARNING log was emitted but no exception was raised to the caller."
            )
    except AssertionError:
        raise
    except Exception:
        pass  # Raising is the CORRECT behavior — not a bug

@given(
    route_key=st.sampled_from(["go_b", "go_end"]),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_conditional_edge_path_map_valid(route_key):
    """Router returning a valid key in path_map must not raise."""
    builder = StateGraph(dict)
    builder.add_node("node_a", lambda s: s)
    builder.add_node("node_b", lambda s: {"visited_b": True})
    builder.set_entry_point("node_a")
    builder.add_conditional_edges(
        "node_a",
        lambda s: route_key,
        {"go_b": "node_b", "go_end": END},
    )
    builder.add_edge("node_b", END)
    graph = builder.compile()
    try:
        graph.invoke({})
    except Exception as e:
        assert False, f"BUG: valid path_map key {route_key!r} raised: {e}"

# ─── TARGET 4: MemorySaver checkpoint put/get round-trip ─────────────────────
print()
print("=" * 60)
print("TARGET 4: MemorySaver checkpoint put/get round-trip")
print("=" * 60)

from langgraph.checkpoint.memory import MemorySaver

@given(
    thread_id=st.text(
        min_size=1, max_size=50,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    ),
    channel_key=st.text(
        min_size=1, max_size=20,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
    ),
    channel_value=st.one_of(
        st.text(max_size=100),
        st.integers(min_value=-10**9, max_value=10**9),
        st.booleans(),
        st.lists(st.integers(min_value=-100, max_value=100), max_size=10),
    ),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_memory_saver_roundtrip(thread_id, channel_key, channel_value):
    """MemorySaver put then get must yield the same channel values (identity)."""
    saver = MemorySaver()
    checkpoint_id = str(uuid.uuid4())
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }
    checkpoint = {
        "v": 1,
        "id": checkpoint_id,
        "ts": "2026-01-01T00:00:00+00:00",
        "channel_values": {channel_key: channel_value},
        "channel_versions": {channel_key: 1},
        "versions_seen": {},
        "pending_sends": [],
        "updated_channels": [channel_key],
    }
    metadata = {"step": 1, "source": "input", "writes": None, "parents": {}}
    new_versions = {channel_key: 1}

    try:
        new_cfg = saver.put(config, checkpoint, metadata, new_versions)
        retrieved = saver.get(new_cfg)
        assert retrieved is not None, "get() returned None after successful put()"
        val = retrieved["channel_values"].get(channel_key)
        assert val == channel_value, (
            f"CHECKPOINT MISMATCH: key={channel_key!r} "
            f"original={channel_value!r} retrieved={val!r}"
        )
    except (TypeError, ValueError) as e:
        if "serial" in str(e).lower() or "encode" in str(e).lower():
            pass  # non-serializable type: expected
        else:
            raise


# ─── RUN ALL TESTS ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("1a: AIMessage content round-trip (200 examples)", test_aimessage_roundtrip_content),
        ("1b: AIMessage falsy kwargs round-trip (200 examples)", test_aimessage_additional_kwargs_falsy),
        ("1c: lc-key injection guard CVE-2025-68664 regression (200 examples)", test_lc_key_injection_guard),
        ("1d: HumanMessage list content round-trip (200 examples)", test_humanmessage_list_content_roundtrip),
        ("2a: RunnableLambda identity coercion (200 examples)", test_runnable_lambda_identity),
        ("3a: conditional edge no-pathmap invalid node silent failure (200 examples)", test_conditional_edge_no_pathmap_invalid_node_silent),
        ("3b: conditional edge path_map valid routing (50 examples)", test_conditional_edge_path_map_valid),
        ("4a: MemorySaver checkpoint round-trip (200 examples)", test_memory_saver_roundtrip),
    ]

    results = []
    for name, fn in tests:
        print(f"\n>>> Running {name}")
        try:
            fn()
            print(f"    PASS -- no counterexample found")
            results.append((name, "PASS", None))
        except AssertionError as e:
            # Hypothesis wraps the failing example in its own AssertionError
            print(f"    FAIL (counterexample found): {e}")
            results.append((name, "CONFIRMED-BUG", str(e)))
        except Exception as e:
            print(f"    ERROR: {type(e).__name__}: {e}")
            results.append((name, "ERROR", f"{type(e).__name__}: {e}"))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, status, detail in results:
        if status == "PASS":
            marker = "OK"
        elif status == "CONFIRMED-BUG":
            marker = "BUG"
        else:
            marker = "ERR"
        print(f"  [{marker}] {name}: {status}")
        if detail:
            print(f"       -> {detail[:300]}")

    bugs = [r for r in results if r[1] == "CONFIRMED-BUG"]
    errors = [r for r in results if r[1] == "ERROR"]
    print(f"\nTotal: {len(results)} tests | Bugs: {len(bugs)} | Errors: {len(errors)} | Clean: {len(results)-len(bugs)-len(errors)}")
    sys.exit(1 if bugs or errors else 0)
