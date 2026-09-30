"""Exact, task-level scoring."""
from __future__ import annotations

from eval.validate import FormatError, parse


def score(task: dict, condition: str, raw: str) -> dict:
    base = {"task_id": task["id"], "split": task["split"], "structure": task["structure"],
            "condition": condition, "size": task["size"], "length": len(task["operations"])}
    try:
        response = parse(raw, task, condition)
    except FormatError as exc:
        return {**base, "format_error": 1, "error": str(exc), "final_correct": 0,
                "per_step_accuracy": 0.0, "full_sequence_correct": 0,
                "first_error_step": 1, "transcription_correct": "", "recovery": 0,
                "failure_type": "format_error"}
    matches = []
    state_matches = []
    for answer, truth, operation in zip(response["steps"], task["steps"], task["operations"], strict=True):
        state_match = answer["state"] == truth["state"]
        state_matches.append(state_match)
        match = state_match
        if operation["kind"] == "find":
            match &= answer["find_result"] == truth["find_result"]
        matches.append(bool(match))
    transcribed = response.get("transcription")
    transcription_correct = "" if transcribed is None else int(transcribed == task["initial"])
    final_correct = int(response["steps"][-1]["state"] == task["steps"][-1]["state"])
    recovery = int(any(not earlier and later for i, earlier in enumerate(state_matches)
                       for later in state_matches[i + 1:]))
    if transcribed is not None and not transcription_correct:
        failure_type = "wrong_transcription_final_correct" if final_correct else "structure_extraction_failure"
    elif not all(matches):
        failure_type = "state_transition_failure"
    else:
        failure_type = "correct"
    return {**base, "format_error": 0, "error": "", "final_correct": final_correct,
            "per_step_accuracy": sum(matches) / len(matches),
            "full_sequence_correct": int(all(matches)),
            "first_error_step": next((i for i, correct in enumerate(matches, 1) if not correct), ""),
            "transcription_correct": transcription_correct, "recovery": recovery,
            "failure_type": failure_type}
