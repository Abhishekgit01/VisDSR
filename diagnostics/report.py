"""Descriptive pilot scores and complete-panel gates; no model inference."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from diagnostics.protocol import CONTROLS, PROTOCOL_ID, write_json

FIELDS = ("model", "task_id", "control", "elements", "operations", "valid", "correct",
          "final_correct", "full_sequence_correct", "changed_parent_accuracy",
          "error", "cap_hit", "latency_s", "output_tokens")


def summarize(rows: list[dict]) -> dict:
    models = {}
    for name in ("model1", "model2"):
        selected = [row for row in rows if row["model"] == name]
        controls = {}
        for control in CONTROLS:
            items = [row for row in selected if row["control"] == control]
            controls[control] = {"scored": len(items), "planned": 8,
                                 "valid": sum(row["valid"] for row in items),
                                 "correct": sum(row["correct"] for row in items),
                                 "cap_hits": sum(row["cap_hit"] for row in items)}
        updates = [row for row in selected if row["control"] == "update_text"]
        cells = []
        for n, length in ((8, 1), (8, 4), (16, 1), (16, 4)):
            items = [row for row in updates if row["elements"] == n and row["operations"] == length]
            cells.append({"elements": n, "operations": length, "scored": len(items),
                          "planned": 2, "final_correct": sum(row["final_correct"] for row in items)})
        complete = len(selected) == 48
        gate = None
        if complete:
            gate = all((controls["extract_text"]["correct"] >= 7,
                        controls["copy_solution"]["correct"] >= 7,
                        controls["update_text"]["correct"] >= 4,
                        all(cell["final_correct"] >= 1 for cell in cells)))
        models[name] = {"scored": len(selected), "planned": 48, "complete": complete,
                        "gate_passed": gate, "controls": controls, "update_text_cells": cells}
    complete = all(model["complete"] for model in models.values())
    gate = "incomplete" if not complete else ("pass" if all(m["gate_passed"] for m in models.values()) else "fail")
    return {"protocol_id": PROTOCOL_ID, "scope": "descriptive diagnostic pilot; separate from main-study scores",
            "scored": len(rows), "planned": 96, "models": models, "gate": gate,
            "next_step": ("Keep collecting the fixed panel; no confirmation decision yet." if not complete
                          else "Prepare a separately frozen, powered confirmation protocol." if gate == "pass"
                          else "Report both pilots and defer confirmation; later interventions need a separate proposal.")}


def write_report(folder: Path, rows: list[dict]) -> dict:
    ordered = sorted(rows, key=lambda row: (row["model"], row["task_id"], row["control"]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(ordered)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / "scores.csv.tmp"
    temporary.write_text(stream.getvalue())
    temporary.replace(folder / "scores.csv")
    result = summarize(ordered)
    write_json(folder / "summary.json", result)
    temporary = folder / "REPORT.md.tmp"
    temporary.write_text(markdown_report(result))
    temporary.replace(folder / "REPORT.md")
    return result


def markdown_report(summary: dict) -> str:
    """Render the saved counts and interpretation limits without inferring causes."""
    lines = ["# VisDSR diagnostic pilot", "",
             f"**Collection: {summary['scored']}/96; accuracy gate: {summary['gate']}.**", "",
             "These descriptive controls are separate from the completed main study.", ""]
    for name, label in (("model1", "Qwen"), ("model2", "InternVL")):
        model = summary["models"][name]
        lines.extend([f"## {label}: {model['scored']}/48", "",
                      "| Control | Saved / planned | Valid JSON/schema | Correct | Output-cap hits |",
                      "| --- | --- | --- | --- | --- |"])
        for control, counts in model["controls"].items():
            lines.append(f"| {control} | {counts['scored']}/8 | {counts['valid']} | "
                         f"{counts['correct']} | {counts['cap_hits']} |")
        lines.extend(["", "Text-update final-map correctness by difficulty:", ""])
        for cell in model["update_text_cells"]:
            lines.append(f"- {cell['elements']} elements, {cell['operations']} operations: "
                         f"{cell['final_correct']} correct / {cell['scored']} saved (2 planned).")
        lines.append("")
    lines.extend(["## Interpretation", "",
                  "Extraction measures initial-map reading; copy-solution measures response compliance; "
                  "updates require reading, DSU calculation, and response compliance together. "
                  "Compare the matched controls before attributing update failures to a particular stage.", "",
                  "Eight forests provide diagnostic evidence, not a powered estimate of an intervention's benefit. "
                  "Invalid answers count as incorrect; no answer repair or content retries were used.", "",
                  summary["next_step"], ""])
    return "\n".join(lines)
