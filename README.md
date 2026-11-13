# Assessing LLM-Generated Updates in Multi-Agent Systems: A Stock-Trading Case Study

Research artifact for a **developer-assisted preliminary feasibility study**.
This title is proposed manuscript metadata, not an accepted-publication claim.

## Recorded evidence

A conversational coding assistant authored six restricted Python policies in
one session. Three configurations reuse those policies to update two, two and
four agents together. The assistant previously developed and inspected the
simulator, references and tests. This is **not an independent or blind LLM benchmark**.

| Observation | Recorded result |
|---|---:|
| Authored policies / derived bundles | 6 / 3 |
| Candidate development / final scenario executions | 1,220 / 3,020 |
| Total candidate scenario executions | 4,240 |
| Observed candidate failures | 0 |
| Baseline + candidate scenario executions | 8,480 |
| Independent LLM sampling trials | 0 |
| Observed repair attempts | 0 |

These are scenario counts, not LLM trials. The bundles are not independent
generations. The final suite was known to the generating assistant. Incomplete
baselines deliberately lack requested capabilities; their rejection is not a
comparative-effectiveness result. No API generation/repair experiment was run.
No inference about repair success, unseen-task generalization or profitability
is supported by this artifact.

## System

Market Data, Analysis, Portfolio, Risk, Execution and Reconciliation agents
exchange messages through a FIFO queue in one process. The exchange and quotes
are synthetic; buy-side only, with no fees, short selling or live trading.
Tasks: retry, quote freshness, pending cash reservation, partial fills,
notification deduplication and late-fill reconciliation. Three bundles combine
Market Data + Execution, Risk + Execution and four agent policies.

Candidate functions receive copied inputs and return structured commands.
The tool uses AST restrictions, schema validation and scenario tests. It is
**testing and validation, not formal verification**. Resource-limited workers
are not an OS security sandbox for arbitrary Python.

## Reproduce

Linux, Python 3.10+, standard library only. Recorded environment: Linux x86_64,
Python 3.12.14. No API key, third-party package or GPU is required.

```sh
python run.py --out results/reproduced
python verify_reproduction.py
```

Candidate hashes are checked before execution. The script replays frozen code;
it does not regenerate it. The verifier compares behavioral counts and outcomes,
excluding timing. Archived evidence in `results/reported` remains unchanged.

## Contents

- `candidates/`: six policies and three derived JSON bundles.
- `prompts/`: task descriptions, not full independent generation contexts.
- `tool_source/`: simulator, evaluator and future API-study scaffolding.
- `results/reported/`: original CSV/JSON evidence and baseline failure traces.
- `provenance.json`: generation context, evaluator awareness and excluded claims.
- `frozen_candidates_sha256.json`: frozen candidate hashes.
- `docs/RESULTS_VI.md`: Vietnamese results and limitations.
- `docs/preliminary_evaluation.tex`: manuscript preliminary-evaluation text.
- `MANIFEST_SHA256.json`: artifact checksums.

The optional API-study scaffolding and its mock self-tests are not reported as
real model-generation results. The replay commands above support the numbers.

## Limitations

Small handcrafted policies and one simulator; overlapping tasks; three tasks
share a reconciliation implementation; bundles reuse component policies. Seeds
vary test inputs and selected schedules, not model samples. The exact backend
model snapshot and isolated generation context are unavailable. Execution can
be reproduced; identical regeneration has not been established. This provides
feasibility evidence for these artifacts, not a safety theorem or production
exchange guarantee. Retain these limitations when citing the results.

## Post-freeze integration assessment

Run `python run_integration.py` to reproduce the supplemental assessment.
The runner verifies the frozen artifact hashes, then evaluates the frozen
four-agent configuration and nine single-edit policy variants against four
new scenario families with 30 seeds each. Compare the generated
`results/integration_reproduced/runs.csv` with
`results/integration/runs.csv`. The archived results also include the first
failure trace per variant and scenario family.

See [the integration assessment](docs/integration_assessment.md) for the
protocol, results, limitations, and corrections for the manuscript.

### Comparison with the original extended suite

Run `python compare_suites.py` to reproduce the comparison using 30 seeds
per family. Archived per-run and per-variant results are in
`results/comparison/`. The original suite has 23 families and the post-freeze
suite has four. Both detect all nine variants. See
[the protocol and interpretation](docs/integration_assessment.md).

## Future work

Independent model sampling and feedback-based repair remain planned experiments.
