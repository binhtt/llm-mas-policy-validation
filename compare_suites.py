"""Compare the original extended suite and the post-freeze integration suite."""
import argparse
import csv
import json
import random
from pathlib import Path

from run_integration import ROOT, SCENARIOS, SEEDS, load_frozen, variants
from evaluator import DEV, FINAL_EXTRA, MAS, scenario
from policy_runtime import policy

TASK = "bundle_pipeline"
OLD_FAMILIES = tuple(dict.fromkeys(DEV[TASK] + FINAL_EXTRA))


def assess(suite, functions):
    if suite == "original":
        for family in OLD_FAMILIES:
            for seed in SEEDS:
                result = scenario(functions, TASK, family, seed, final=True)
                yield family, seed, result["violations"]
    else:
        for family in SCENARIOS:
            for seed in SEEDS:
                system = MAS(functions, TASK)
                family(system, random.Random(seed))
                yield family.__name__, seed, system.final_check()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "comparison_reproduced")
    out = parser.parse_args().out.resolve()
    archived = ROOT / "results" / "comparison"
    if out == archived or archived in out.parents:
        parser.error("Choose a separate reproduction output directory.")
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    counts = []
    for name, sources in variants(load_frozen()):
        functions = {key: policy(source) for key, source in sources.items()}
        for suite in ("original", "post_freeze"):
            failed_families = set()
            failed = 0
            runs = 0
            for family, seed, violations in assess(suite, functions):
                runs += 1
                if violations:
                    failed += 1
                    failed_families.add(family)
                rows.append(dict(variant=name, suite=suite, family=family, seed=seed,
                                 violations="|".join(sorted(violations))))
            counts.append(dict(variant=name, suite=suite, runs=runs, failures=failed,
                               detecting_families="|".join(sorted(failed_families))))

    summary = {}
    for suite in ("original", "post_freeze"):
        selected = [row for row in counts if row["suite"] == suite]
        summary[suite] = {
            "runs_per_variant": selected[0]["runs"],
            "frozen_failures": selected[0]["failures"],
            "detected_mutants": [
                row["variant"] for row in selected[1:] if row["failures"]
            ],
        }
    old = summary["original"]["detected_mutants"]
    new = summary["post_freeze"]["detected_mutants"]
    summary["post_freeze_only"] = [name for name in new if name not in old]
    summary["original_only"] = [name for name in old if name not in new]

    for filename, records in (("runs.csv", rows), ("by_variant.csv", counts)):
        with (out / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=records[0])
            writer.writeheader()
            writer.writerows(records)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
