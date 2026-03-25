from __future__ import annotations

import sys
from pathlib import Path

from .models import OptimizationResult, ScoreCard, SkillInfo, TestResult


def print_report(
    skill: SkillInfo,
    results: list[TestResult],
    card: ScoreCard,
    file=sys.stdout,
) -> None:
    w = file.write

    w(f"\nSkill Trigger Test: {skill.name}\n")
    w("=" * (22 + len(skill.name)) + "\n\n")

    # Results table
    w(f"  {'#':>3} | {'Expect':^6} | {'Actual':^6} | {'':^4} | Query\n")
    w(f"  {'---':>3}-+-{'------':^6}-+-{'------':^6}-+-{'----':^4}-+-----\n")

    for i, r in enumerate(results, 1):
        expect = "TRIG" if r.case.expect_trigger else "SKIP"
        actual = "TRIG" if r.triggered else "SKIP"
        if r.error:
            status = "ERR "
        elif r.passed:
            status = "PASS"
        else:
            status = "FAIL"
        query = _truncate(r.case.query, 60)
        w(f"  {i:>3} | {expect:^6} | {actual:^6} | {status:^4} | {query}\n")

    w("\n")

    # Scores
    w(f"  Precision: {card.precision:.2f}  Recall: {card.recall:.2f}  F1: {card.f1:.2f}\n")
    w(f"  TP: {card.tp}  FP: {card.fp}  TN: {card.tn}  FN: {card.fn}\n")
    w(f"  Verdict: {card.verdict}")
    if card.verdict != "OPTIMAL":
        w(" (target F1 >= 0.90 for OPTIMAL)")
    w("\n")

    # Cost summary
    total_cost = sum(r.cost_usd for r in results)
    total_time = sum(r.duration_ms for r in results)
    errors = sum(1 for r in results if r.error)
    w(f"\n  Cost: ${total_cost:.4f}  Time: {total_time / 1000:.1f}s  Errors: {errors}\n")

    # Failures
    failures = [r for r in results if not r.passed and not r.error]
    if failures:
        w("\n  Failures:\n")
        for r in failures:
            idx = results.index(r) + 1
            direction = "Expected TRIG but SKIP" if r.case.expect_trigger else "Expected SKIP but TRIG"
            w(f"    #{idx} {direction} -- \"{r.case.query}\"\n")

    w("\n")


def write_markdown(
    path: Path,
    skill: SkillInfo,
    results: list[TestResult],
    card: ScoreCard,
) -> None:
    lines = []
    a = lines.append

    a(f"# Skill Trigger Test: {skill.name}\n")
    a(f"**Description:** {skill.description}\n")
    a(f"**Verdict:** {card.verdict} (F1: {card.f1:.2f})\n")

    a("| # | Expect | Actual | Result | Query |")
    a("|---|--------|--------|--------|-------|")
    for i, r in enumerate(results, 1):
        expect = "TRIG" if r.case.expect_trigger else "SKIP"
        actual = "TRIG" if r.triggered else "SKIP"
        status = "ERR" if r.error else ("PASS" if r.passed else "FAIL")
        a(f"| {i} | {expect} | {actual} | {status} | {r.case.query} |")

    a(f"\n**Precision:** {card.precision:.2f} | **Recall:** {card.recall:.2f} | **F1:** {card.f1:.2f}")
    a(f"\nTP: {card.tp} | FP: {card.fp} | TN: {card.tn} | FN: {card.fn}")

    total_cost = sum(r.cost_usd for r in results)
    a(f"\n**Total cost:** ${total_cost:.4f}")

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_optimization_report(result: OptimizationResult, file=sys.stdout) -> None:
    w = file.write

    status = "CONVERGED" if result.converged else "DID NOT CONVERGE"
    w(f"\nOptimization: {result.skill_name} ({status})\n")
    w(f"Target: F1 >= {result.target_f1:.2f}\n")
    w("=" * 50 + "\n\n")

    prev_f1 = 0.0
    for rd in result.rounds:
        delta = f"  [+{rd.score.f1 - prev_f1:.2f}]" if prev_f1 > 0 else ""
        w(f"Round {rd.round_num}: F1 = {rd.score.f1:.2f} {rd.score.verdict}{delta}\n")
        if rd.false_negatives:
            fn_str = ", ".join(f'"{_truncate(q, 50)}"' for q in rd.false_negatives[:3])
            more = f" (+{len(rd.false_negatives) - 3} more)" if len(rd.false_negatives) > 3 else ""
            w(f"  FN ({len(rd.false_negatives)}): {fn_str}{more}\n")
        if rd.false_positives:
            fp_str = ", ".join(f'"{_truncate(q, 50)}"' for q in rd.false_positives[:3])
            more = f" (+{len(rd.false_positives) - 3} more)" if len(rd.false_positives) > 3 else ""
            w(f"  FP ({len(rd.false_positives)}): {fp_str}{more}\n")
        if rd.num_regression_cases > 0:
            w(f"  Regression cases: {rd.num_regression_cases}\n")
        if rd.name_suggestion:
            w(f"  Name suggestion: {rd.name_suggestion}\n")
        prev_f1 = rd.score.f1
        w("\n")

    w("Frontmatter changes:\n")
    w(f"  name: {result.skill_name}\n")

    if result.original_description != result.final_description:
        w(f"  description:\n")
        w(f"    BEFORE: \"{_truncate(result.original_description, 120)}\"\n")
        w(f"    AFTER:  \"{_truncate(result.final_description, 120)}\"\n")
    else:
        w(f"  description: (unchanged)\n")

    if result.original_when_to_use != result.final_when_to_use:
        before = result.original_when_to_use or "(not set)"
        w(f"  when_to_use:\n")
        w(f"    BEFORE: \"{_truncate(before, 120)}\"\n")
        w(f"    AFTER:  \"{_truncate(result.final_when_to_use, 120)}\"\n")
    else:
        w(f"  when_to_use: (unchanged)\n")

    w("\n")


def _truncate(s: str, maxlen: int) -> str:
    return s if len(s) <= maxlen else s[: maxlen - 3] + "..."
