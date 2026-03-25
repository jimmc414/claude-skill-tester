from skill_tester.models import TestCase, TestResult, ScoreCard
from skill_tester.scorer import score


def _make_result(expect: bool, triggered: bool, error: str | None = None) -> TestResult:
    return TestResult(
        case=TestCase(query="test", expect_trigger=expect),
        triggered=triggered,
        error=error,
    )


def test_all_correct():
    results = [
        _make_result(True, True),
        _make_result(True, True),
        _make_result(False, False),
    ]
    card = score(results)
    assert card.tp == 2
    assert card.tn == 1
    assert card.fp == 0
    assert card.fn == 0
    assert card.f1 == 1.0
    assert card.verdict == "OPTIMAL"


def test_all_wrong():
    results = [
        _make_result(True, False),
        _make_result(False, True),
    ]
    card = score(results)
    assert card.fn == 1
    assert card.fp == 1
    assert card.f1 == 0.0
    assert card.verdict == "NEEDS_WORK"


def test_mixed():
    results = [
        _make_result(True, True),   # TP
        _make_result(True, True),   # TP
        _make_result(True, False),  # FN
        _make_result(False, False), # TN
        _make_result(False, True),  # FP
    ]
    card = score(results)
    assert card.tp == 2
    assert card.fn == 1
    assert card.tn == 1
    assert card.fp == 1
    assert card.precision == 2 / 3
    assert card.recall == 2 / 3


def test_errors_skipped():
    results = [
        _make_result(True, True),
        _make_result(True, False, error="timeout"),
    ]
    card = score(results)
    assert card.total == 1
    assert card.tp == 1


def test_empty():
    card = score([])
    assert card.f1 == 0.0
    assert card.total == 0


def test_verdict_thresholds():
    # F1 = 1.0 -> OPTIMAL
    assert ScoreCard(tp=10, fp=0, tn=5, fn=0).verdict == "OPTIMAL"
    # F1 ~ 0.8 -> GOOD
    assert ScoreCard(tp=8, fp=1, tn=4, fn=2).verdict == "GOOD"
    # F1 ~ 0.5 -> NEEDS_WORK
    assert ScoreCard(tp=5, fp=3, tn=2, fn=5).verdict == "NEEDS_WORK"
