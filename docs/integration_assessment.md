# Post-freeze integration assessment

The study reuses the archived four-agent configuration and verifies SHA-256
hashes for all nine frozen artifacts. The four bundle entries are byte-for-byte
copies of the individual freshness, reservation, retry, and partial policies.
The partial policy handles Reconciliation by ignoring seen notification IDs
and applying the reported execution quantity regardless of cancellation status.
This implements deduplication and late-fill handling within the same policy.

## Protocol

Four scenario families add checkpoints to the original simulator.

| Scenario | Scripted expectations |
|---|---|
| Retry with a second order | Recover from loss before acceptance. Retry an already accepted order without creating a duplicate. Reconcile both orders. |
| Late fill with a delayed duplicate | Reconcile partial fills across cancellation, ignore a replay after accounting for another order, and preserve the expected ledger. |
| Pending orders at the exact cash boundary | After a partial fill, reject an order that exceeds available cash and accept one that exactly consumes it. |
| Freshness and quantity boundaries | Reject an age-six quote, accept an age-five quote, and preserve the ten-unit order limit. |

Thirty seeds per family vary prices or quantities within fixed operation
sequences. The runner compares syntax and command-schema checks with those
same checks plus the runtime observer and scenario checkpoints. Each condition
uses the same execution. A runtime exception aborts the run. Detection is
counted per variant if at least one scenario–seed pair reports a violation.

## Results

| Artifact | Runs | Behavioral failures |
|---|---:|---:|
| Frozen four-agent configuration | 120 | 0 |
| Nine single-edit variants | 1,080 | 330 |

All nine variants compiled and emitted schema-valid commands. Behavioral
checks detected nine of nine variants. Seven variants failed 30 runs each.
The duplicate-reapplication and order-quantity variants failed 60 runs each.
The CSV contains verdicts and violation identifiers for every run. The JSON
contains the first witness per failing variant and scenario family.

## Manuscript changes

- Sections 3.2 and 4.4: identify the four exact source policies reused in the
  pipeline. Describe the Reconciliation entry as reuse of the partial policy,
  whose behavior already includes deduplication and late-fill reconciliation.
- Algorithm 2: the original implementation checks the expected exchange order
  count before residual fills, then checks ledger conservation after them.
  Rename the early check to make its checkpoint explicit. The added protocol
  defines both intermediate ledger checkpoints and a final ledger check.
- Section 4: distinguish the original extended scenario suite, which was
  visible to the policy author, from this post-freeze scenario suite. Keep
  the original 4,240 candidate executions separate from these 1,200 runs.
- Supplementary material: describe the Python simulator, evaluator, frozen
  policies, scripts, and archived execution evidence. Reference the release
  that contains this experiment.

## Scope

The additional scenarios were designed after the policies were frozen and
with access to their source. They combine existing fault models and add
explicit checkpoints. The nine variants are hand-designed and the results
characterize this simulator and fault set. The experiment uses one
configuration and one FIFO process. It provides evidence about behavioral
fault detection rather than independent LLM generation, repair efficacy,
or production failure rates.

## Comparison with the original extended suite

The frozen bundle and the same nine policy variants were executed on the
23 original extended families and the four post-freeze families, using
30 seed indices per family. Each suite retained its own input generation
and scenario assertions. Both used the same simulator and command checks.
The original suite retained its original final-mode seed offset.

| Suite | Families | Frozen bundle failures | Variant executions flagged | Variants detected |
|---|---:|---:|---:|---:|
| Original extended | 23 | 0/690 | 1290/6210 | 9/9 |
| Post-freeze | 4 | 0/120 | 330/1080 | 9/9 |

No variant was detected exclusively by either suite. The additional
scenarios exercise alternative event sequences and explicit checkpoints.
The four selected families cover this fault set in fewer executions, but
the suites differ in scenario count, inputs, and assertions. This comparison
does not establish detection superiority, equivalence on other faults, or a
speedup at equal execution budgets.
