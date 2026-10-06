"""Execute operations on the model's predicted forest, without gold correction."""
from __future__ import annotations

from collections import Counter


def execute(predicted: dict, labels: list[str], operations: list[dict]) -> dict:
    if set(predicted) != set(labels) or any(value not in labels for value in predicted.values()):
        raise ValueError("predicted forest labels differ from the supplied task labels")
    parents = dict(predicted)

    def root(node: str) -> str:
        seen = set()
        while parents[node] != node:
            if node in seen:
                raise ValueError("predicted parent map contains a non-root cycle")
            seen.add(node)
            node = parents[node]
        return node

    sizes = Counter(root(node) for node in labels)

    def find(node: str) -> str:
        representative = root(node)
        while parents[node] != node:
            following = parents[node]
            parents[node] = representative
            node = following
        return representative

    steps = []
    for number, operation in enumerate(operations, 1):
        if operation["kind"] == "find":
            result = find(operation["a"])
            steps.append({"op": number, "state": dict(parents), "find_result": result})
        elif operation["kind"] == "union":
            a, b = find(operation["a"]), find(operation["b"])
            if a != b:
                if sizes[a] < sizes[b]:
                    a, b = b, a
                parents[b] = a
                sizes[a] += sizes[b]
                sizes[b] = 0
            steps.append({"op": number, "state": dict(parents)})
        else:
            raise ValueError("unknown operation kind")
    return {"steps": steps}
