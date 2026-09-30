"""Regenerate DSU accuracy tables, paired comparisons, and a figure from CSV."""
from __future__ import annotations

import argparse
import csv

import matplotlib.pyplot as plt

from analysis.stats import holm, mcnemar_exact, paired_bootstrap
from eval.prompts import CONDITIONS
from visdsr import ROOT, config

plt.switch_backend("Agg")

COMPARISONS = [
    ("modality effect", "T-dir", "R-dir"),
    ("diagram/representation effect", "R-dir", "G-dir"),
    ("total visual-presentation effect", "T-dir", "G-dir"),
    ("transcription effect", "G-str", "G-dir"),
    ("scaffolding effect", "T-str", "T-dir"),
]


def write_csv(path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(models: list[str], split: str, allow_partial: bool) -> None:
    summary = []
    comparisons = []
    primary_indices = []
    resamples = config()["bootstrap_resamples"]
    for model in models:
        filename = f"scores_{model}.csv" if split == "main" else f"scores_{split}_{model}.csv"
        path = ROOT / "results" / filename
        if not path.exists():
            raise FileNotFoundError(f"missing {path}; run or score the model first")
        with path.open(newline="") as source:
            rows = [row for row in csv.DictReader(source) if row["split"] == split and row["structure"] == "dsu"]
        by_condition = {condition: {} for condition in CONDITIONS}
        for row in rows:
            condition = row["condition"]
            if row["task_id"] in by_condition[condition]:
                raise ValueError(f"duplicate result for {row['task_id']}/{condition}")
            by_condition[condition][row["task_id"]] = row
        ids = set.intersection(*(set(by_condition[condition]) for condition in CONDITIONS))
        if not ids or (split == "main" and len(ids) != 80 and not allow_partial):
            raise ValueError(f"{model}: expected 80 complete paired main tasks; found {len(ids)}")
        if any(set(by_condition[condition]) != ids for condition in CONDITIONS):
            raise ValueError(f"{model}: incomplete condition pairs")
        ids = sorted(ids)
        outcomes = {condition: [int(by_condition[condition][id]["final_correct"]) for id in ids]
                    for condition in CONDITIONS}
        for condition in CONDITIONS:
            mean, low, high = paired_bootstrap(outcomes[condition], resamples)
            summary.append({"model": model, "split": split, "condition": condition,
                            "tasks": len(ids), "accuracy": mean, "ci_low": low, "ci_high": high,
                            "format_error_rate": sum(int(by_condition[condition][id]["format_error"])
                                                     for id in ids) / len(ids)})
        secondary_indices = []
        for name, left, right in COMPARISONS:
            values = [a - b for a, b in zip(outcomes[left], outcomes[right], strict=True)]
            mean, low, high = paired_bootstrap(values, resamples)
            b, c, p_value = mcnemar_exact(outcomes[left], outcomes[right])
            comparisons.append({"model": model, "split": split, "comparison": name,
                                "left": left, "right": right, "tasks": len(ids),
                                "difference_pp": 100 * mean, "ci_low_pp": 100 * low,
                                "ci_high_pp": 100 * high, "left_only_correct": b,
                                "right_only_correct": c, "mcnemar_p": p_value,
                                "holm_p": ""})
            index = len(comparisons) - 1
            (primary_indices if name == "total visual-presentation effect" else secondary_indices).append(index)
        secondary_p = [comparisons[i]["mcnemar_p"] for i in secondary_indices]
        for index, adjusted in zip(secondary_indices, holm(secondary_p), strict=True):
            comparisons[index]["holm_p"] = adjusted
        net = [gstr - gdir - tstr + tdir for gstr, gdir, tstr, tdir in zip(
            outcomes["G-str"], outcomes["G-dir"], outcomes["T-str"], outcomes["T-dir"], strict=True)]
        mean, low, high = paired_bootstrap(net, resamples)
        comparisons.append({"model": model, "split": split,
                            "comparison": "net transcription recovery/effect", "left": "", "right": "",
                            "tasks": len(ids), "difference_pp": 100 * mean,
                            "ci_low_pp": 100 * low, "ci_high_pp": 100 * high,
                            "left_only_correct": "", "right_only_correct": "",
                            "mcnemar_p": "", "holm_p": ""})
    primary_p = [comparisons[i]["mcnemar_p"] for i in primary_indices]
    for index, adjusted in zip(primary_indices, holm(primary_p), strict=True):
        comparisons[index]["holm_p"] = adjusted
    result = ROOT / "results"
    result.mkdir(exist_ok=True)
    write_csv(result / "summary.csv", summary)
    write_csv(result / "comparisons.csv", comparisons)
    figure_dir = result / "figures"
    figure_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    width = 0.75 / len(models)
    for i, model in enumerate(models):
        values = [next(row for row in summary if row["model"] == model and row["condition"] == condition)
                  for condition in CONDITIONS]
        x = [j - 0.375 + width * (i + 0.5) for j in range(len(CONDITIONS))]
        y = [100 * row["accuracy"] for row in values]
        errors = [[100 * (row["accuracy"] - row["ci_low"]) for row in values],
                  [100 * (row["ci_high"] - row["accuracy"]) for row in values]]
        ax.bar(x, y, width, label=model, yerr=errors, capsize=3)
    ax.set_xticks(range(len(CONDITIONS)), CONDITIONS)
    ax.set_ylabel("Final-state exact match (%)")
    ax.set_ylim(0, 105)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "accuracy.png", dpi=160)
    plt.close(fig)
    print(f"wrote {result / 'summary.csv'}, {result / 'comparisons.csv'}, and accuracy.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["pilot", "main"], default="main")
    parser.add_argument("--models", nargs="+", default=["model1"])
    parser.add_argument("--allow-partial", action="store_true", help="for development only")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(f"would analyze {args.split} CSVs for {', '.join(args.models)}")
    else:
        analyze(args.models, args.split, args.allow_partial)


if __name__ == "__main__":
    main()
