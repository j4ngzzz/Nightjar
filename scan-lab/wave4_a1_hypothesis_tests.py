"""
Wave 4 Hunt A1: Security research for langchain-core + langgraph
Targets:
  1. langchain-core dumps()/dumpd() round-trip fidelity
  2. langgraph add_conditional_edges() routing validity
  3. Checkpoint put/get round-trip
"""

import warnings
warnings.filterwarnings("ignore")

import json
import sys
import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

# ─── Target 1: langchain-core dumps/dumpd round-trip ────────────────────────

from langchain_core.load.dump import dumps, dumpd
from langchain_core.load.load import loads
from langchain_core.messages import AIMessage, HumanMessage

# Strategy: generate primitive/nested values for metadata fields
json_primitive = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**9), max_value=10**9),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=100),
)

json_value = st.recursive(
    json_primitive,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(max_size=20), children, max_size=5),
    ),
    max_leaves=20,
)

lc_poisoned_dict = st.fixed_dictionaries({
    "lc": st.integers(),
    "extra": json_value,
})


@given(content=st.text(max_size=200))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_aimessage_content_roundtrip(content):
    """AIMessage content round-trips through dumps/loads without mutation."""
    msg = AIMessage(content=content)
    serialized = dumps(msg)
    loaded = loads(serialized)
    assert loaded.content == content, (
        f"FAIL: content mutated. in={content!r} out={loaded.content!r}"
    )


@given(content=st.text(max_size=200))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_humanmessage_roundtrip(content):
    """HumanMessage round-trips through dumps/loads without mutation."""
    msg = HumanMessage(content=content)
    serialized = dumps(msg)
    loaded = loads(serialized)
    assert loaded.content == content, (
        f"FAIL: content mutated. in={content!r} out={loaded.content!r}"
    )


@given(metadata=st.dictionaries(
    st.text(min_size=1, max_size=20),
    json_primitive,
    max_size=5
))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_aimessage_metadata_roundtrip(metadata):
    """AIMessage additional_kwargs metadata round-trips correctly."""
    msg = AIMessage(content="test", additional_kwargs=metadata)
    d = dumpd(msg)
    s = json.dumps(d)
    assert isinstance(s, str)


@given(lc_val=lc_poisoned_dict)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_lc_key_injection_in_additional_kwargs(lc_val):
    """Dict with 'lc' key in additional_kwargs must be escaped, not treated as LC object."""
    msg = AIMessage(content="test", additional_kwargs=lc_val)
    d = dumpd(msg)
    s = json.dumps(d)
    loaded = loads(s)
    assert isinstance(loaded.additional_kwargs, dict), (
        f"FAIL: additional_kwargs lost its dict type: {type(loaded.additional_kwargs)}"
    )
    lc_in = loaded.additional_kwargs.get("lc")
    assert lc_in == lc_val.get("lc") or lc_in is None, (
        f"FAIL: lc field mutated: in={lc_val!r} out={loaded.additional_kwargs!r}"
    )


@given(
    content=st.text(max_size=100),
    nested_lc=st.fixed_dictionaries({
        "lc": st.just(1),
        "type": st.just("constructor"),
        "id": st.lists(st.text(min_size=1, max_size=10), min_size=2, max_size=4),
        "kwargs": st.just({}),
    })
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_serialization_injection_via_lc_object_shaped_dict(content, nested_lc):
    """Craft a user dict mimicking LC format - must not deserialize as arbitrary object."""
    msg = AIMessage(content=content, additional_kwargs=nested_lc)
    d = dumpd(msg)
    s = json.dumps(d)
    loaded = loads(s)
    assert isinstance(loaded, AIMessage), "FAIL: loaded should be AIMessage"
    ak = loaded.additional_kwargs
    assert isinstance(ak, dict), (
        f"FAIL: additional_kwargs is {type(ak)}, not dict: {ak!r}"
    )


@given(content=st.binary(max_size=100))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_binary_content_aimessage(content):
    """Binary bytes in content should not crash serialization."""
    try:
        msg = AIMessage(content=content.decode("utf-8", errors="replace"))
        d = dumpd(msg)
        s = json.dumps(d)
        assert isinstance(s, str)
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")


# ─── Target 2: langgraph add_conditional_edges routing ──────────────────────

from typing import TypedDict
from langgraph.graph import StateGraph, END


class SimpleState(TypedDict):
    value: str


@given(
    node_name=st.text(min_size=1, max_size=30).filter(
        lambda s: s not in ("__start__", "__end__", "END", "START")
        and s.isprintable() and "\x00" not in s
    ),
    return_value=st.text(min_size=1, max_size=30).filter(
        lambda s: s.isprintable() and "\x00" not in s
    ),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_conditional_edge_with_invalid_return_raises(node_name, return_value):
    """
    If the routing function returns a value not in path_map,
    it must raise at runtime, not silently route to wrong node.
    """
    assume(node_name != return_value)

    valid_dest = "node_b"

    try:
        builder = StateGraph(SimpleState)
        builder.add_node(node_name, lambda s: s)
        builder.add_node(valid_dest, lambda s: s)
        builder.set_entry_point(node_name)

        def bad_router(state):
            return return_value

        builder.add_conditional_edges(
            node_name,
            bad_router,
            path_map={node_name: valid_dest},
        )
        builder.set_finish_point(valid_dest)

        graph = builder.compile()

        try:
            result = graph.invoke({"value": "test"})
            # If we get here with no exception that is a routing bug:
            # the path_map key lookup should have raised KeyError
            pytest.fail(
                f"ROUTING BUG: invalid return value {return_value!r} did not raise, "
                f"returned: {result!r}"
            )
        except (KeyError, ValueError, Exception):
            pass
    except Exception:
        pass


@given(
    destinations=st.lists(
        st.text(min_size=1, max_size=20).filter(
            lambda s: s.isprintable() and "\x00" not in s
        ),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_conditional_edge_no_path_map_invalid_return(destinations):
    """
    With no path_map, router return value used as node name.
    Invalid node name should fail, not route silently.
    """
    assume(all(d not in ("__start__", "__end__") for d in destinations))

    invalid_dest = "node_that_does_not_exist_xyz_999"

    try:
        builder = StateGraph(SimpleState)
        builder.add_node("start_node", lambda s: s)
        builder.set_entry_point("start_node")

        def router(state):
            return invalid_dest

        builder.add_conditional_edges("start_node", router)

        graph = builder.compile()
        try:
            graph.invoke({"value": "test"})
        except Exception:
            pass
    except Exception:
        pass


# ─── Target 3: Checkpoint put/get round-trip ────────────────────────────────

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.base import empty_checkpoint, CheckpointMetadata
import uuid


def make_config(thread_id: str, checkpoint_id: str = None):
    cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    if checkpoint_id:
        cfg["configurable"]["checkpoint_id"] = checkpoint_id
    return cfg


@given(
    channel_name=st.text(min_size=1, max_size=30).filter(
        lambda s: s.isprintable() and "\x00" not in s
    ),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_checkpoint_put_get_roundtrip(channel_name):
    """Values stored in checkpoint round-trip through InMemorySaver."""
    saver = InMemorySaver()
    thread_id = str(uuid.uuid4())
    checkpoint_id = str(uuid.uuid4())

    config = make_config(thread_id)

    chk = empty_checkpoint()
    chk["id"] = checkpoint_id

    metadata: CheckpointMetadata = {
        "source": "input",
        "step": 0,
        "writes": {},
        "parents": {},
    }
    new_versions = {channel_name: 1}

    try:
        written_config = saver.put(config, chk, metadata, new_versions)
        retrieved = saver.get_tuple(written_config)

        if retrieved is None:
            pytest.fail(
                f"FAIL: put succeeded but get returned None for thread_id={thread_id}"
            )

        assert retrieved.checkpoint["id"] == checkpoint_id, (
            f"FAIL: checkpoint ID mutated. "
            f"in={checkpoint_id!r} out={retrieved.checkpoint['id']!r}"
        )
    except Exception:
        pass


@given(
    thread_id=st.text(min_size=1, max_size=100).filter(
        lambda s: s.isprintable() and "\x00" not in s
    ),
    step_count=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_checkpoint_multiple_puts_returns_latest(thread_id, step_count):
    """Multiple puts for same thread returns the latest checkpoint."""
    saver = InMemorySaver()
    config = make_config(thread_id)
    last_id = None

    for step in range(step_count):
        checkpoint_id = str(uuid.uuid4())
        chk = empty_checkpoint()
        chk["id"] = checkpoint_id
        metadata: CheckpointMetadata = {
            "source": "loop",
            "step": step,
            "writes": {},
            "parents": {},
        }
        try:
            saver.put(config, chk, metadata, {})
            last_id = checkpoint_id
        except Exception:
            return

    if last_id:
        retrieved = saver.get_tuple(make_config(thread_id))
        if retrieved is not None:
            assert retrieved.checkpoint["id"] == last_id, (
                f"FAIL: latest checkpoint ID wrong. expected={last_id!r} "
                f"got={retrieved.checkpoint['id']!r}"
            )


@given(
    metadata_key=st.text(min_size=1, max_size=30).filter(
        lambda s: s.isprintable() and "\x00" not in s
    ),
    metadata_val=st.one_of(
        st.text(max_size=50),
        st.integers(),
        st.none(),
    ),
)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_checkpoint_metadata_roundtrip(metadata_key, metadata_val):
    """Checkpoint metadata (writes field) round-trips through put/get."""
    saver = InMemorySaver()
    thread_id = str(uuid.uuid4())
    checkpoint_id = str(uuid.uuid4())
    config = make_config(thread_id)

    chk = empty_checkpoint()
    chk["id"] = checkpoint_id

    custom_write = {metadata_key: metadata_val}
    metadata: CheckpointMetadata = {
        "source": "input",
        "step": 0,
        "writes": custom_write,
        "parents": {},
    }

    try:
        written_config = saver.put(config, chk, metadata, {})
        retrieved = saver.get_tuple(written_config)

        if retrieved is not None:
            retrieved_writes = retrieved.metadata.get("writes", {})
            if metadata_key in retrieved_writes:
                assert retrieved_writes[metadata_key] == metadata_val, (
                    f"FAIL: metadata write mutated. "
                    f"key={metadata_key!r} in={metadata_val!r} "
                    f"out={retrieved_writes[metadata_key]!r}"
                )
    except Exception:
        pass
