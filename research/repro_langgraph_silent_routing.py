"""
Standalone repro for HUNT-A1 Finding:
  langgraph==1.1.3 — StateGraph.add_conditional_edges() silently drops
  execution when router returns a name not registered as a node (no path_map).

  Expected: ValueError or InvalidNodeException raised to caller.
  Actual:   graph.invoke() returns successfully, WARNING log only (not raised).

Run: python repro_langgraph_silent_routing.py
Expected output: REPRODUCED x3
"""
import warnings
warnings.filterwarnings("ignore")
import logging
logging.disable(logging.CRITICAL)  # suppress the warning so output is clean

from langgraph.graph import StateGraph, END

PASS = 0
FAIL = 0

def run_once(run_num):
    global PASS, FAIL
    visited_b = []

    def process_payment(state):
        visited_b.append(True)
        state["payment_processed"] = True
        return state

    builder = StateGraph(dict)
    builder.add_node("validate", lambda s: s)
    builder.add_node("process", process_payment)
    builder.set_entry_point("validate")

    # Simulates a routing bug: router returns a misspelled/unknown node name.
    # No path_map provided — router is expected to return a valid node name.
    builder.add_conditional_edges(
        "validate",
        lambda s: "typo_or_unknown_node",   # <-- invalid: not registered
    )
    builder.add_edge("process", END)

    graph = builder.compile()

    try:
        result = graph.invoke({"amount": 100})
        if not visited_b:
            print(f"  Run {run_num}: REPRODUCED — invoke() returned {result!r} "
                  f"without error, 'process' node never ran")
            PASS += 1
        else:
            print(f"  Run {run_num}: NOT reproduced — process node ran")
            FAIL += 1
    except Exception as e:
        print(f"  Run {run_num}: NOT reproduced — raised {type(e).__name__}: {e}")
        FAIL += 1

print("=" * 60)
print("Repro: langgraph silent routing failure on invalid node name")
print("Package: langgraph==1.1.3, langgraph-checkpoint==4.0.1")
print("=" * 60)
run_once(1)
run_once(2)
run_once(3)

print()
if PASS == 3 and FAIL == 0:
    print("VERDICT: REPRODUCED 3/3 times — confirmed bug")
elif PASS > 0:
    print(f"VERDICT: Reproduced {PASS}/3 times — intermittent")
else:
    print("VERDICT: Could not reproduce — may be fixed or environment-specific")
