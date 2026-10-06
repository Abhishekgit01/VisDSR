"""Matched prompt/grammar arms on the unchanged diagnostic development panel."""
from __future__ import annotations

import json
import random
from pathlib import Path

from diagnostics.protocol import PILOT, SOURCES, load_panel
from visdsr import ROOT, canonical, digest

PROTOCOL_ID = "visdsr-dsu-interventions-20261007"
FOLDER = ROOT / "interventions"
RESULTS = ROOT / "results/followup" / PROTOCOL_ID
SOURCE_FILES = (*SOURCES, "diagnostics/pilot/FREEZE.json", "interventions/__init__.py",
                "interventions/protocol.py", "interventions/provider.py", "interventions/executor.py",
                "interventions/run.py", "interventions/report.py", "interventions/transfer.py",
                "interventions/overnight.py", "interventions/__main__.py",
                "interventions/requirements.txt", "docs/INTERVENTIONS.md",
                "notebooks/dsu_improvements_overnight.ipynb")
ARMS = {"baseline": (False, False), "grammar": (False, True),
        "procedure": (True, False), "combined": (True, True)}
PROCEDURE = """
Execution procedure (apply internally; return only the requested JSON):
1. For find(x), follow parent pointers to a node r with parent[r] = r.
   Save r, then set every node on the traversed path to parent r. Return r.
   Do not compress paths from nodes that were not traversed.
2. For union(a,b), find(a), then find(b) using the updated map. Preserve both
   path compressions, including when the roots coincide and no merge occurs.
3. Count each component's members by read-only root traversal. Counting does
   not alter any parent. Compare whole-component sizes, not child counts.
4. Attach the smaller component root under the larger. On equal sizes attach
   b's root under a's root. Change that root pointer only; do not flatten the
   entire merged component. Keep all other parents from the updated map.
5. Carry this complete map forward between operations. Emit every label's
   immediate parent after each operation. Include find_result only for finds.
""".strip()


def cases() -> list[dict]:
    _, _, original = load_panel()
    result = []
    for case in original:
        if not case["control"].startswith("update_"):
            continue
        for arm in ("grammar", "procedure", "combined"):
            procedural, constrained = ARMS[arm]
            prompt = case["user_prompt"] + ("\n\n" + PROCEDURE if procedural else "")
            result.append({**case, "case_id": case["case_id"] + "__" + arm,
                           "arm": arm, "grammar": constrained, "user_prompt": prompt})
    random.Random(2026100705).shuffle(result)
    return result


def load_protocol() -> tuple[dict, list[dict], list[dict]]:
    frozen = json.loads((FOLDER / "FREEZE.json").read_text())
    actual = {name: digest((ROOT / name).read_bytes()) for name in SOURCE_FILES}
    if frozen["protocol_id"] != PROTOCOL_ID or frozen["source_hashes"] != actual:
        raise RuntimeError("intervention source freeze changed")
    diagnostic, tasks, _ = load_panel()
    if frozen["diagnostic_freeze_sha256"] != digest(canonical(diagnostic).encode()):
        raise RuntimeError("intervention panel belongs to a different diagnostic freeze")
    planned = cases()
    if json.loads((FOLDER / "requests.json").read_text()) != planned:
        raise RuntimeError("intervention requests changed")
    if frozen["requests_sha256"] != digest((FOLDER / "requests.json").read_bytes()):
        raise RuntimeError("intervention request checksum mismatch")
    return frozen, tasks, planned


def provenance(frozen: dict, task: dict, case: dict, model: dict) -> dict:
    value = {"protocol_id": PROTOCOL_ID, "freeze_sha256": digest(canonical(frozen).encode()),
             "case": case, "task_sha256": digest(canonical(task).encode()),
             "image_sha256": digest((PILOT / case["image"]).read_bytes()) if case["image"] else "",
             "model": model, "grammar_ebnf": grammar(task) if case["grammar"] else None}
    return {"cache_key": digest(canonical(value).encode()), **value}


def grammar(task: dict) -> str:
    """Allow every parent assignment; constrain fields/order, not correct values."""
    labels = list(task["initial"])

    def terminal(value: str) -> str:
        return json.dumps(value)
    label = " | ".join(terminal(json.dumps(name)) for name in labels)
    fields = [terminal(json.dumps(name) + ":") + " label" for name in labels]
    state = terminal("{") + " " + (" " + terminal(",") + " ").join(fields) + " " + terminal("}")
    rules = ["label ::= " + label, "state ::= " + state]
    names = []
    for number, operation in enumerate(task["operations"], 1):
        name = f"step{number}"
        suffix = ' ' + terminal(',"find_result":') + " label" if operation["kind"] == "find" else ""
        rules.append(name + " ::= " + terminal('{"op":' + str(number) + ',"state":') + " state" + suffix + " " + terminal("}"))
        names.append(name)
    root = terminal('{"steps":[') + " " + (" " + terminal(",") + " ").join(names) + " " + terminal("]}")
    return "root ::= " + root + "\n" + "\n".join(rules) + "\n"
