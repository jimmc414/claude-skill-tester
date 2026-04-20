# F1 Scoring in claude-skill-tester

This document explains how the F1 score is calculated, why it's used to measure skill trigger accuracy, and where it appears in the tool.

## What F1 Measures

F1 is the harmonic mean of precision and recall. In this tool, it answers a single question:

> When I send queries to Claude, does the target skill fire on the queries that should trigger it, and stay silent on the queries that shouldn't?

A high F1 means both: the skill fires when it should, and doesn't fire when it shouldn't.

## The Confusion Matrix

Every test query lands in one of four buckets based on two facts: what we expected, and what happened.

| | Skill triggered | Skill did NOT trigger |
|---|---|---|
| **Should trigger** (positive query) | True Positive (TP) | False Negative (FN) |
| **Should NOT trigger** (negative query) | False Positive (FP) | True Negative (TN) |

- **TP** — correct fire. The skill triggered on a query it should have.
- **FN** — missed fire. The skill stayed silent when it should have triggered. This is an undertriggering failure — users won't get help they need.
- **FP** — spurious fire. The skill triggered on an unrelated query. This is an overtriggering failure — the skill hijacks conversations it doesn't belong in.
- **TN** — correct silence. The skill stayed out of an unrelated query.

## The Formulas

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * (Precision * Recall) / (Precision + Recall)
```

Equivalently, F1 can be written directly in terms of counts:

```
F1 = 2 * TP / (2 * TP + FP + FN)
```

Range: **0.0** (worst) to **1.0** (perfect). Notice TN is tracked for reporting but never factors into F1 — a skill that never fires at all would get F1 = 0, even though its TN count could be large.

## What Each Metric Means in Plain English

- **Precision** — "When the skill fires, is it correct?" High precision means few false alarms.
- **Recall** — "Of the queries that should have triggered, how many did?" High recall means few misses.
- **F1** — "Is the skill both accurate AND complete?" High F1 requires both precision and recall to be high.

## Why the Harmonic Mean

The arithmetic mean of 1.0 and 0.0 is 0.5 — it would say a skill that fires on everything (or nothing) is "half good." The harmonic mean of 1.0 and 0.0 is 0.0. It punishes imbalance:

| Precision | Recall | Arithmetic Mean | F1 (Harmonic Mean) |
|-----------|--------|-----------------|---------------------|
| 1.00 | 1.00 | 1.00 | 1.00 |
| 0.90 | 0.90 | 0.90 | 0.90 |
| 1.00 | 0.50 | 0.75 | 0.67 |
| 1.00 | 0.10 | 0.55 | 0.18 |
| 1.00 | 0.00 | 0.50 | 0.00 |

This makes F1 hard to game. You can't maximize it by over-firing (crushes precision) or by under-firing (crushes recall). You must balance both.

## Worked Example

Suppose we run 15 test queries for a skill: 10 positive (should trigger) and 5 negative (should not).

Results:
- 8 of the 10 positive queries correctly triggered the skill → TP = 8
- 2 of the 10 positive queries were missed → FN = 2
- 1 of the 5 negative queries incorrectly triggered the skill → FP = 1
- 4 of the 5 negative queries correctly did not trigger → TN = 4

Calculation:

```
Precision = 8 / (8 + 1)  = 8/9  ≈ 0.89
Recall    = 8 / (8 + 2)  = 8/10 = 0.80
F1        = 2 * (0.89 * 0.80) / (0.89 + 0.80) ≈ 0.84
```

Verdict: `GOOD` (F1 >= 0.75 but < 0.90).

## Verdict Thresholds

The tool maps F1 onto three human-readable verdicts:

| Verdict | F1 Score | What it means |
|---------|----------|---------------|
| OPTIMAL | >= 0.90 | Skill triggers reliably and cleanly |
| GOOD | >= 0.75 | Usable, but has some misses or spurious fires |
| NEEDS_WORK | < 0.75 | Trigger behavior is unreliable |

These thresholds are implemented in `ScoreCard.verdict` in `skill_tester/models.py`.

## Where F1 Is Used in This Tool

F1 is computed and reported by several commands:

### `skill-test run <tests.yaml>`
Executes a saved test suite, scores the results, and prints the F1 along with precision, recall, and the TP/FP/TN/FN breakdown.

### `skill-test quick <skill_path>`
Generates test queries and runs them in one step. Output ends with the F1 score and verdict.

### `skill-test optimize <skill_path>`
Uses F1 as the optimization target. Each round:
1. Generate fresh test queries
2. Run the suite
3. Compute F1
4. If F1 >= `--target-f1` (default 0.90): converged, stop
5. Otherwise: analyze the FN and FP queries, rewrite the frontmatter, repeat

The optimizer's stopping criterion is F1 — it keeps iterating until F1 crosses the target or `--max-rounds` is exhausted.

## How Errored Tests Are Handled

Queries that error out (timeout, CLI failure, JSON parse failure) are **excluded from scoring**. They appear as `ERR` in the results table and don't count as TP, FP, TN, or FN. This is implemented in `skill_tester/scorer.py`:

```python
def score(results: list[TestResult]) -> ScoreCard:
    card = ScoreCard()
    for r in results:
        if r.error:
            continue  # errored tests skipped
        ...
```

The rationale: an errored test says nothing about whether the skill's frontmatter is correct — it only says the infrastructure failed.

## F1 vs. Accuracy

Accuracy (`(TP + TN) / total`) is *not* used in this tool. Here's why.

If you test a narrow skill with 100 queries (5 positive, 95 negative) and the skill never fires:
- Accuracy = 95/100 = 0.95 — looks great
- Precision = 0/0 (undefined) — misleading
- Recall = 0/5 = 0.0 — the truth
- F1 = 0.0 — the truth

Accuracy rewards a skill for correctly doing nothing on the 95 unrelated queries, which is the easy part. F1 focuses on the harder question: does the skill actually do its job when its job is called for?

## F1 vs. Collision Testing

F1 measures a skill in isolation. The `collide` command (see COMMAND_REFERENCE.md) measures whether two skills steal each other's queries when both are active. A skill can have F1 = 0.95 in isolation but get 40% of its queries stolen by a neighboring skill in production. The two metrics answer different questions:

| Metric | Question | Command |
|--------|----------|---------|
| F1 | Does this skill trigger correctly on its own queries? | `run`, `quick`, `optimize` |
| Theft rate | Do these skills' trigger surfaces overlap and steal from each other? | `collide` |

Use F1 first to get each skill to OPTIMAL individually, then use `collide` to check whether they still behave when deployed together.

## Where to Find the Code

- `skill_tester/models.py` — `ScoreCard` dataclass, `precision` / `recall` / `f1` / `verdict` properties
- `skill_tester/scorer.py` — `score()` builds a `ScoreCard` from a list of `TestResult`
- `skill_tester/reporter.py` — `print_report()` formats the output
- `skill_tester/optimizer.py` — uses F1 as the convergence criterion
- `tests/test_scorer.py` — unit tests covering the confusion matrix, thresholds, and edge cases
