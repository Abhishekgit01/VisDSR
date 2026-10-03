"""The five preregistered presentation and transcription conditions."""
from __future__ import annotations

from visdsr import canonical

CONDITIONS = ("T-dir", "R-dir", "G-dir", "T-str", "G-str")
SYSTEM = ("Simulate the DSU operations exactly. Return one JSON object only. "
          "Do not include explanations, reasoning text, tags, Markdown, or code fences. "
          "The response must begin with { and end with }.")


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
        "union(a,b) first runs find(a) and find(b), including their path compression. A set's size counts all elements whose root is that set's root, not just direct children. If roots differ, attach the smaller set's root under the larger set's root. If sizes tie, attach b's root under a's root. If roots are equal, do not merge.",
        "The initial state is a parent map. In a diagram, each arrow points from child to parent; roots have no outgoing arrow.",
    ]
    lines += [
        "Worked examples below are separate from this task; do not copy their states into your answer.",
        'Example 1: start {"A":"A","B":"A","C":"C","D":"C"}; union(B,D) finds roots A and C, each of size 2, so C attaches under A. The resulting state is {"A":"A","B":"A","C":"A","D":"C"}. The step is {"op":1,"state":{"A":"A","B":"A","C":"A","D":"C"}}.',
        'Example 2: start {"A":"A","B":"A","C":"A","D":"C"}; find(D) returns A and changes the parent of D to A. The resulting state is {"A":"A","B":"A","C":"A","D":"A"}. The step is {"op":1,"state":{"A":"A","B":"A","C":"A","D":"A"},"find_result":"A"}.',
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
        lines.append("First restate the initial parent map exactly in transcription. transcription must be a JSON object mapping each label to its parent, not a string.")
    lines += [
        "Return a JSON object with " + ("transcription and steps" if structured else "steps") + ".",
        "steps must be an array with one object per operation in order. Each object has op (1-based operation number) and state (the full parent map after that operation). For find operations only, include find_result (the returned root label).",
        "Use every label exactly once as a state key. Start your response with { and end it with }. Return no prose, reasoning text, tags, or Markdown.",
    ]
    return "\n".join(lines)
