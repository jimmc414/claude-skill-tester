from __future__ import annotations

import sys
from pathlib import Path

from .models import ScoreCard, SkillInfo, TestResult


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


def _truncate(s: str, maxlen: int) -> str:
    return s if len(s) <= maxlen else s[: maxlen - 3] + "..."
