"""Compare the C++ simulator against a separate Python test oracle."""
from __future__ import annotations

import argparse
import json
import random

from gen.generate import run_sim
from tests.naive import simulate
from visdsr import ROOT


def verify_examples() -> None:
    for example in json.loads((ROOT / "tests/examples.json").read_text()):
        oracle = simulate(example["n"], example["prelude"], example["operations"])
        if oracle != example["expected"]:
            raise AssertionError(f"test fixture is wrong: {example['name']}")
        actual = run_sim(example["n"], example["prelude"], example["operations"])
        if actual != example["expected"]:
            raise AssertionError(f"C++ mismatch: {example['name']}\n{actual}\n{example['expected']}")
    print("worked examples pass")


def random_operation(n: int, rng: random.Random) -> dict:
    a = chr(65 + rng.randrange(n))
    if rng.random() < 0.5:
        return {"kind": "find", "a": a}
    return {"kind": "union", "a": a, "b": chr(65 + rng.randrange(n))}


def stress(cases: int, seed: int) -> None:
    rng = random.Random(seed)
    consecutive = 0
    for index in range(cases):
        n = rng.choice((8, 16, 24))
        prelude = [random_operation(n, rng) for _ in range(rng.randint(1, 25))]
        operations = [random_operation(n, rng) for _ in range(rng.randint(1, 12))]
        expected = simulate(n, prelude, operations)
        actual = run_sim(n, prelude, operations)
        if actual != expected:
            raise AssertionError(f"case {index + 1} mismatch after {consecutive} consecutive passes")
        consecutive += 1
    print(f"{consecutive} consecutive random cases match")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026092601)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.cases <= 0:
        parser.error("--cases must be positive")
    if args.dry_run:
        print(f"would verify worked examples and {args.cases} random cases")
    else:
        try:
            verify_examples()
            stress(args.cases, args.seed)
        except RuntimeError as exc:
            parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
