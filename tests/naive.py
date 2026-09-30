"""Independent test oracle only. Never import this in gen/ or eval/."""
from __future__ import annotations


def simulate(n: int, prelude: list[dict], operations: list[dict]) -> dict:
    parent = list(range(n))
    size = [1] * n

    def find(x: int) -> int:
        path = []
        while parent[x] != x:
            path.append(x)
            x = parent[x]
        for node in path:
            parent[node] = x
        return x

    def state() -> dict[str, str]:
        return {chr(65 + i): chr(65 + value) for i, value in enumerate(parent)}

    def execute(operation: dict) -> str | None:
        a = ord(operation["a"]) - 65
        if operation["kind"] == "find":
            return chr(65 + find(a))
        b = ord(operation["b"]) - 65
        ra, rb = find(a), find(b)
        if ra != rb:
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]
        return None

    for operation in prelude:
        execute(operation)
    initial = state()
    steps = []
    for operation in operations:
        result = execute(operation)
        step = {"state": state()}
        if result is not None:
            step["find_result"] = result
        steps.append(step)
    return {"initial": initial, "steps": steps}
