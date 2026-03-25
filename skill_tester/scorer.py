from __future__ import annotations

from .models import ScoreCard, TestResult


def score(results: list[TestResult]) -> ScoreCard:
    card = ScoreCard()
    for r in results:
        if r.error:
            continue
        if r.case.expect_trigger and r.triggered:
            card.tp += 1
        elif r.case.expect_trigger and not r.triggered:
            card.fn += 1
        elif not r.case.expect_trigger and r.triggered:
            card.fp += 1
        else:
            card.tn += 1
    return card
