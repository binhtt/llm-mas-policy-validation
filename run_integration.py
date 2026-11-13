"""Run post-freeze integration scenarios and a behavioral-check ablation."""
import argparse
import csv
import hashlib
import json
import platform
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tool_source"))

from evaluator import MAS
from policy_runtime import policy

SEEDS = range(30)
BUNDLE = "bundle_pipeline.json"

# Each variant makes one schema-valid change to a frozen policy.
MUTANTS = {
    "reject_age_five": ("freshness", '> 5', '>= 5'),
    "accept_age_six": ("freshness", '> 5', '> 6'),
    "ignore_reservations": ("reservation", ' - event["reserved"]', ''),
    "reject_exact_budget": ("reservation", 'cost > available', 'cost >= available'),
    "drop_timeout_retry": ("retry", '("submit", "timeout")', '("submit",)'),
    "change_retry_identifier": (
        "retry", '"client_order_id": order["order_id"]',
        '"client_order_id": order["order_id"] + event["kind"]',
    ),
    "ignore_late_fills": ("partial", 'if event["seen"]:', 'if event["seen"] or order["status"] == "cancelled":'),
    "reapply_duplicate_fill": ("partial", 'if event["seen"]:', 'if False:'),
    "apply_order_quantity": ("partial", 'executed_quantity = event["qty"]', 'executed_quantity = order["qty"]'),
}


def quote(system, price, qty, age=0):
    system.quote(price, qty, age)
    system.run()


def notify(system, kind, order):
    if order in system.orders:
        system.send("execution", kind, oid=order)
        system.run()


def fill(system, order, qty, fill_id, duplicate=False):
    exchange_id = next(
        (key for key, entry in system.exchange_orders.items() if entry["oid"] == order),
        None,
    )
    if exchange_id is not None:
        system.fill(exchange_id, qty, fill_id, duplicate=duplicate)


def expect(system, condition, name):
    if not condition:
        system.error(name)


def expect_orders(system, *expected):
    actual = sorted(entry["oid"] for entry in system.exchange_orders.values())
    expect(system, actual == sorted(expected), "expected_exchange_orders")


def expect_ledger(system, quantity, spending):
    expect(
        system,
        (system.position, system.cash) == (quantity, system.initial_cash - spending),
        "expected_checkpoint_ledger",
    )


def retry_with_second_order(system, rng):
    price = rng.randint(45, 80)
    system.drop_remaining = 1
    quote(system, price, 3)
    expect_orders(system)
    quote(system, price, 2)
    expect_orders(system, "o2")
    notify(system, "timeout", "o2")
    expect_orders(system, "o2")
    notify(system, "timeout", "o1")
    expect_orders(system, "o1", "o2")
    # Inject a timeout after exchange acceptance to exercise stable IDs.
    notify(system, "timeout", "o1")
    expect_orders(system, "o1", "o2")
    fill(system, "o1", 3, "retry-a")
    fill(system, "o2", 2, "retry-b")
    expect_ledger(system, 5, 5 * price)


def late_fill_with_delayed_duplicate(system, rng):
    price = rng.randint(45, 80)
    quote(system, price, 4)
    fill(system, "o1", 1, "early")
    expect_ledger(system, 1, price)
    notify(system, "cancel", "o1")
    fill(system, "o1", 2, "late")
    expect_ledger(system, 3, 3 * price)
    notify(system, "timeout", "o1")
    quote(system, price, 2)
    fill(system, "o2", 2, "other")
    # Replay a notification without adding a new legitimate exchange fill.
    early = next((entry for entry in system.fills if entry["fid"] == "early"), None)
    if early is not None:
        system.send("reconciliation", "fill", **early)
        system.run()
    fill(system, "o1", 1, "last")
    expect_orders(system, "o1", "o2")
    expect_ledger(system, 6, 6 * price)


def pending_exact_cash(system, rng):
    price = rng.choice((100, 125, 200))
    total = system.initial_cash // price
    first = rng.randint(max(2, total - 9), min(10, total - 2))
    second = total - first
    quote(system, price, first)
    fill(system, "o1", 1, "partial", duplicate=True)
    quote(system, price, second + 1)
    quote(system, price, second)
    expect_orders(system, "o1", "o3")
    fill(system, "o1", first - 1, "finish-first")
    fill(system, "o3", second, "finish-second")
    expect_ledger(system, total, system.initial_cash)


def freshness_and_quantity_boundaries(system, rng):
    price = rng.randint(30, 45)
    quote(system, price, 2, age=6)
    expect_orders(system)
    expect(system, not system.orders, "stale_quote_not_forwarded")
    quote(system, price, 11, age=5)
    expect_orders(system)
    quote(system, price, 10, age=5)
    expect_orders(system, "o2")
    fill(system, "o2", 10, "boundary")
    expect_ledger(system, 10, 10 * price)


SCENARIOS = (
    retry_with_second_order,
    late_fill_with_delayed_duplicate,
    pending_exact_cash,
    freshness_and_quantity_boundaries,
)


def load_frozen():
    hashes = json.loads((ROOT / "frozen_candidates_sha256.json").read_text())
    for name, expected in hashes.items():
        actual = hashlib.sha256((ROOT / "candidates" / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Frozen artifact hash mismatch: {name}")
    return json.loads((ROOT / "candidates" / BUNDLE).read_text())


def variants(frozen):
    yield "frozen_pipeline", frozen
    for name, (key, original, replacement) in MUTANTS.items():
        if frozen[key].count(original) != 1:
            raise ValueError(f"Expected exactly one mutation site: {name}")
        yield name, {**frozen, key: frozen[key].replace(original, replacement, 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "integration_reproduced")
    args = parser.parse_args()
    out = args.out.resolve()
    for protected in (ROOT / "results" / "reported", ROOT / "results" / "integration"):
        if out == protected or protected in out.parents:
            parser.error("Choose a new output directory for reproduction.")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    witnesses = {}
    for name, sources in variants(load_frozen()):
        functions = {key: policy(source) for key, source in sources.items()}
        for scenario in SCENARIOS:
            for seed in SEEDS:
                system = MAS(functions, "bundle_pipeline")
                # Identical executions for both assessment conditions. A
                # runtime exception aborts the study and cannot count as a kill.
                scenario(system, random.Random(seed))
                violations = sorted(system.final_check())
                rows.append({
                    "variant": name, "scenario": scenario.__name__, "seed": seed,
                    "schema_pass": True, "behavioral_pass": not violations,
                    "violations": "|".join(violations),
                })
                if violations and (name, scenario.__name__) not in witnesses:
                    witnesses[name, scenario.__name__] = {
                        **rows[-1], "trace": system.trace, "policy_calls": system.commands,
                    }

    frozen_rows = [row for row in rows if row["variant"] == "frozen_pipeline"]
    summary = {
        "python": platform.python_version(),
        "scenario_families": len(SCENARIOS), "seeds_per_family": len(SEEDS),
        "total_runs": len(rows), "frozen_runs": len(frozen_rows),
        "frozen_failures": sum(not row["behavioral_pass"] for row in frozen_rows),
        "mutants": len(MUTANTS), "schema_detected_mutants": 0,
        "behavior_detected_mutants": sum(
            any(row["variant"] == mutant and not row["behavioral_pass"] for row in rows)
            for mutant in MUTANTS
        ),
        "mutant_failed_runs": sum(
            row["variant"] != "frozen_pipeline" and not row["behavioral_pass"] for row in rows
        ),
    }
    with (out / "runs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    (out / "witnesses.json").write_text(json.dumps(list(witnesses.values()), indent=2) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
