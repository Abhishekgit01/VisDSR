"""The five preregistered presentation and transcription conditions."""
from __future__ import annotations

from visdsr import canonical

CONDITIONS = ("T-dir", "R-dir", "G-dir", "T-str", "G-str")
SYSTEM = "You solve deterministic data-structure operations. Follow the stated rules and return only JSON."


def prompt(task: dict, condition: str) -> str:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    if task["structure"] != "dsu":
        raise NotImplementedError("only DSU tasks are supported")
    labels = list(task["initial"])
    structured = condition.endswith("str")
    lines = [
        f"Disjoint-set union over labels {', '.join(labels)}.",
        "A root is its own parent. find(x) follows parents to a root, fully compresses the traversed path, and returns the root.",
        "union(a,b) first runs find(a) and find(b), including their path compression. If roots differ, attach the smaller set's root under the larger set's root. If sizes tie, attach b's root under a's root. If roots are equal, do not merge.",
        "The initial state is a parent map. In a diagram, each arrow points from child to parent; roots have no outgoing arrow.",
    ]
    if condition.startswith("T"):
        lines.append("Initial state: " + canonical(task["initial"]))
    else:
        lines.append("Initial state: see the attached PNG.")
    operations = []
    for i, op in enumerate(task["operations"], 1):
        operations.append(f"{i}. {op['kind']}({op['a']}{',' + op['b'] if op['kind'] == 'union' else ''})")
    lines += ["Operations:", *operations]
    if structured:
        lines.append("First restate the initial parent map exactly in a transcription field.")
    lines += [
        "Return a JSON object with " + ("transcription and steps" if structured else "steps") + ".",
        "steps must be an array with one object per operation in order. Each object has op (1-based operation number) and state (the full parent map after that operation). For find operations only, include find_result (the returned root label).",
        "Use every label exactly once as a state key. Return no prose or Markdown.",
    ]
    return "\n".join(lines)
