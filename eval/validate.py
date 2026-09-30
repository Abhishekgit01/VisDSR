"""Strict content validation; invalid responses never trigger model retries."""
from __future__ import annotations

import json
import re


class FormatError(ValueError):
    pass


def parse(raw: str, task: dict, condition: str) -> dict:
    value = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", value, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        value = fenced.group(1).strip()
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise FormatError(f"invalid JSON: {exc.msg}") from exc
    structured = condition.endswith("str")
    expected_top = {"steps", "transcription"} if structured else {"steps"}
    if not isinstance(data, dict) or set(data) != expected_top:
        raise FormatError("top-level fields do not match the condition")
    labels = set(task["initial"])

    def check_state(state: object) -> None:
        if not isinstance(state, dict) or set(state) != labels or any(v not in labels for v in state.values()):
            raise FormatError("state must contain exactly the task labels and valid parents")

    if structured:
        check_state(data["transcription"])
    steps = data["steps"]
    if not isinstance(steps, list) or len(steps) != len(task["operations"]):
        raise FormatError("wrong number of steps")
    for number, (step, operation) in enumerate(zip(steps, task["operations"], strict=True), 1):
        expected = {"op", "state"}
        if operation["kind"] == "find":
            expected.add("find_result")
        if not isinstance(step, dict) or set(step) != expected or type(step["op"]) is not int or step["op"] != number:
            raise FormatError(f"step {number} fields or order are invalid")
        check_state(step["state"])
        if "find_result" in expected and step["find_result"] not in labels:
            raise FormatError(f"step {number} find_result is invalid")
    return data
