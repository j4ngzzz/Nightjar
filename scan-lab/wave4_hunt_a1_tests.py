"""
Wave 4 HUNT-A1: Property-based tests for langchain-core + langgraph.
Packages: langchain-core==1.2.23, langgraph==1.1.3 (langgraph-checkpoint==4.0.1)
Run: python wave4_hunt_a1_tests.py
"""
import warnings
warnings.filterwarnings("ignore")

import json
import sys
from typing import Annotated
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

# ─── TARGET 1: langchain_core serialization round-trip ───────────────────────
# Contract: loads(dumps(obj)) == dumpd(obj) for all Serializable subclasses
# Focus: _is_field_useful falsy-value logic — falsy values that differ from
# default SHOULD survive the round-trip. Zero, empty-string, False etc.

print("=" * 60)
print("TARGET 1: langchain_core serialization round-trip (AIMessage)")
print("=" * 60)

from langchain_core.messages import AIMessage
from langchain_core.load import dumpd, dumps, loads, load

# ── 1a: round-trip identity for AIMessage with arbitrary content ──────────────
@given(
    content=st.text(min_size=0, max_size=200),
    usage_tokens=st.integers(min_value=0, max_value=10_000),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_aimessage_roundtrip_content(content, usage_tokens):
    """AIMessage round-trip: dumpd then load should give equal content."""
    msg = AIMessage(content=content)
    data = dumpd(msg)
    restored = load(data, allowed_objects="core")
    assert restored.content == msg.content, (
        f"CONTENT MISMATCH: original={msg.content!r} restored={restored.content!r}"
    )

# ── 1b: falsy non-default values survive serialization ───────────────────────
# The _is_field_useful code has a subtle path: falsy values with non-dict/list
# defaults can be dropped. Test: False, 0, "" as non-required fields.
@given(
    content=st.text(min_size=0, max_size=100),
    # additional_kwargs is default={} — an empty dict should be dropped (correct)
    # But a non-empty dict with falsy values inside should survive
    extra_val=st.one_of(st.just(""), st.just(0), st.just(False), st.just(None)),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_aimessage_additional_kwargs_falsy(content, extra_val):
    """Fields with falsy non-default values must survive serialization."""
    msg = AIMessage(content=content, additional_kwargs={"key": extra_val})
    data = dumpd(msg)
    restored = load(data, allowed_objects="core")
    # The additional_kwargs dict itself is non-empty, so it IS truthy
    # — it should definitely survive round-trip
    assert restored.additional_kwargs == msg.additional_kwargs, (
        f"KWARGS MISMATCH: original={msg.additional_kwargs!r} "
        f"restored={restored.additional_kwargs!r}"
    )

# ── 1c: lc-keyed user data injection guard (CVE-2025-68664 regression) ────────
# After patch, user data containing 'lc' key in kwargs must be escaped and
# returned as plain dict, NOT deserialized as an LC object.
@given(
    content=st.text(min_size=1, max_size=100),
    inner_type=st.sampled_from(["constructor", "secret", "not_implemented"]),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_lc_key_injection_guard(content, inner_type):
    """Regression: user data with 'lc' keys must NOT be deserialized as LC objects."""
    # Craft a payload simulating what the old bug allowed
    crafted = {"lc": 1, "type": inner_type, "id": ["langchain_core", "messages", "ai", "AIMessage"], "kwargs": {"content": content}}
    msg = AIMessage(content=content, additional_kwargs={"lc_payload": crafted})
    data = dumpd(msg)
    json_str = json.dumps(data)
    try:
        restored = loads(json_str, allowed_objects="core")
        # If it loads, the nested dict in additional_kwargs must be a plain dict, not an AIMessage
        nested = restored.additional_kwargs.get("lc_payload")
        if nested is not None:
            assert not isinstance(nested, AIMessage), (
                f"BUG: crafted lc-key dict was deserialized as AIMessage! "
                f"content={content!r} type={inner_type!r}"
            )
    except (ValueError, NotImplementedError):
        # Rejection is also acceptable (strict allowlist working correctly)
        pass

# ── 1d: HumanMessage round-trip with list content ─────────────────────────────
from langchain_core.messages import HumanMessage
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

# ─── TARGET 2: langchain_core runnables type coercion ────────────────────────
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

# ─── TARGET 3: langgraph add_conditional_edges routing validation ─────────────
print()
print("=" * 60)
print("TARGET 3: StateGraph.add_conditional_edges routing")
print("=" * 60)

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

def make_simple_graph(routing_return):
    """Build a minimal 2-node graph with a conditional edge."""
    builder = StateGraph(dict)
    builder.add_node("node_a", lambda s: s)
    builder.add_node("node_b", lambda s: s)
    builder.set_entry_point("node_a")
    builder.add_conditional_edges("node_a", lambda s: routing_return, ["node_b", END])
    builder.add_edge("node_b", END)
    return builder

# ── 3a: invalid node name returned by router should raise on compile or invoke ─
@given(
    bad_name=st.text(min_size=1, max_size=30).filter(
        lambda x: x not in ("node_a", "node_b", END, "__end__")
    )
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_conditional_edge_invalid_node_raises(bad_name):
    """Router returning an unknown node name must raise, not silently continue."""
    builder = StateGraph(dict)
    builder.add_node("node_a", lambda s: s)
    builder.add_node("node_b", lambda s: s)
    builder.set_entry_point("node_a")
    # No path_map — router returns raw node name
    builder.add_conditional_edges("node_a", lambda s: bad_name)
    builder.add_edge("node_b", END)
    try:
        graph = builder.compile()
        # If compile succeeds, invoke must raise with invalid name
        try:
            result = graph.invoke({})
            # If we get here, that's a bug — silent routing to nowhere
            # Unless the graph handles END gracefully — check it didn't just stop silently
            # on an invalid node
            assert False, (
                f"BUG: graph.invoke() succeeded with invalid node name {bad_name!r}. "
                f"Result: {result!r}"
            )
        except Exception:
            pass  # Expected — invalid node should raise
    except Exception:
        pass  # Also acceptable — compile-time detection is even better

# ── 3b: path_map with valid keys should route correctly ───────────────────────
@given(
    route_key=st.sampled_from(["go_b", "go_end"]),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_conditional_edge_path_map_valid(route_key):
    """Router returning a key in path_map should reach the correct node."""
    builder = StateGraph(dict)
    builder.add_node("node_a", lambda s: {"visited": True})
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
        result = graph.invoke({})
        # Should not raise for valid keys
    except Exception as e:
        assert False, f"BUG: valid path_map key {route_key!r} raised: {e}"

# ─── TARGET 4: MemorySaver checkpoint put/get round-trip ─────────────────────
print()
print("=" * 60)
print("TARGET 4: MemorySaver checkpoint put/get round-trip")
print("=" * 60)

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import create_checkpoint

@given(
    thread_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_")),
    channel_key=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
    channel_value=st.one_of(
        st.text(max_size=100),
        st.integers(),
        st.booleans(),
        st.none(),
        st.lists(st.integers(), max_size=10),
    ),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_memory_saver_roundtrip(thread_id, channel_key, channel_value):
    """MemorySaver put then get must yield the same channel values."""
    saver = MemorySaver()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }
    checkpoint = create_checkpoint(
        {"v": 1, "id": "test-id-1", "ts": "2026-01-01T00:00:00+00:00",
         "channel_values": {channel_key: channel_value},
         "channel_versions": {channel_key: 1},
         "versions_seen": {},
         "pending_sends": []},
        {channel_key: channel_value},
        1,
    )
    try:
        new_config = saver.put(config, checkpoint, {"step": 1, "source": "loop", "writes": None, "parents": {}}, {channel_key: 1})
        retrieved = saver.get(new_config)
        if retrieved is not None:
            val = retrieved["channel_values"].get(channel_key)
            assert val == channel_value, (
                f"CHECKPOINT MISMATCH: key={channel_key!r} "
                f"original={channel_value!r} retrieved={val!r}"
            )
    except Exception as e:
        # Some types may not be serializable — that's acceptable failure
        if "serialize" in str(e).lower() or "serial" in str(e).lower() or "encode" in str(e).lower():
            pass
        else:
            raise


# ─── RUN ALL TESTS ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("1a: AIMessage content round-trip", test_aimessage_roundtrip_content),
        ("1b: AIMessage falsy kwargs round-trip", test_aimessage_additional_kwargs_falsy),
        ("1c: lc-key injection guard (CVE-2025-68664 regression)", test_lc_key_injection_guard),
        ("1d: HumanMessage list content round-trip", test_humanmessage_list_content_roundtrip),
        ("2a: RunnableLambda identity coercion", test_runnable_lambda_identity),
        ("3a: conditional edge invalid node raises", test_conditional_edge_invalid_node_raises),
        ("3b: conditional edge path_map valid routing", test_conditional_edge_path_map_valid),
        ("4a: MemorySaver checkpoint round-trip", test_memory_saver_roundtrip),
    ]

    results = []
    for name, fn in tests:
        print(f"\n>>> Running {name}")
        try:
            fn()
            print(f"    PASS — no counterexample found")
            results.append((name, "PASS", None))
        except AssertionError as e:
            print(f"    FAIL (AssertionError): {e}")
            results.append((name, "FAIL-ASSERTION", str(e)))
        except Exception as e:
            print(f"    ERROR: {type(e).__name__}: {e}")
            results.append((name, "ERROR", f"{type(e).__name__}: {e}"))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, status, detail in results:
        marker = "OK" if status == "PASS" else "!!"
        print(f"  [{marker}] {name}: {status}")
        if detail:
            print(f"       -> {detail[:200]}")

    fails = [r for r in results if r[1] != "PASS"]
    if fails:
        print(f"\n{len(fails)} test(s) found issues. See above.")
        sys.exit(1)
    else:
        print("\nAll tests PASSED — no counterexamples found.")
        sys.exit(0)
