from skill_tester.models import TestCase, TestResult
from skill_tester.runner import _detect_skill_in_events


# --- Rival capture from events ---

def _make_events(*skill_names):
    """Build mock events with Skill tool_use blocks."""
    blocks = [
        {"type": "tool_use", "name": "Skill", "input": {"skill": name}}
        for name in skill_names
    ]
    return [{"type": "assistant", "message": {"content": blocks}}]


def test_detect_target_only():
    events = _make_events("my-skill")
    triggered, rival = _detect_skill_in_events(events, "my-skill")
    assert triggered is True
    assert rival is None


def test_detect_rival_only():
    events = _make_events("other-skill")
    triggered, rival = _detect_skill_in_events(events, "my-skill")
    assert triggered is False
    assert rival == "other-skill"


def test_detect_no_skill():
    events = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}}]
    triggered, rival = _detect_skill_in_events(events, "my-skill")
    assert triggered is False
    assert rival is None


def test_detect_target_and_rival():
    events = _make_events("other-skill", "my-skill")
    triggered, rival = _detect_skill_in_events(events, "my-skill")
    assert triggered is True
    assert rival == "other-skill"


def test_detect_multiple_rivals_captures_first():
    events = _make_events("rival-a", "rival-b")
    triggered, rival = _detect_skill_in_events(events, "my-skill")
    assert triggered is False
    assert rival == "rival-a"


def test_detect_empty_events():
    triggered, rival = _detect_skill_in_events([], "my-skill")
    assert triggered is False
    assert rival is None


def test_detect_non_skill_tool_use():
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
    ]}}]
    triggered, rival = _detect_skill_in_events(events, "my-skill")
    assert triggered is False
    assert rival is None


# --- TestResult with new fields ---

def test_result_defaults():
    r = TestResult(case=TestCase(query="test", expect_trigger=True), triggered=True)
    assert r.rival_skill is None
    assert r.diagnosis is None
    assert r.passed is True


def test_result_with_rival():
    r = TestResult(
        case=TestCase(query="test", expect_trigger=True),
        triggered=False,
        rival_skill="other-skill",
    )
    assert r.rival_skill == "other-skill"
    assert r.passed is False


def test_result_with_diagnosis():
    r = TestResult(
        case=TestCase(query="test", expect_trigger=True),
        triggered=False,
        diagnosis="Query mentions X but description lacks X.",
    )
    assert r.diagnosis == "Query mentions X but description lacks X."


# --- Diagnostics formatting in optimizer ---

def test_format_diagnostics_empty():
    from skill_tester.optimizer import _format_diagnostics
    assert _format_diagnostics([], []) == ""


def test_format_diagnostics_with_data():
    from skill_tester.optimizer import _format_diagnostics
    fn = TestResult(
        case=TestCase(query="check my docs", expect_trigger=True),
        triggered=False,
        rival_skill="explain-code",
        diagnosis="Description lacks 'docs' keyword.",
    )
    fp = TestResult(
        case=TestCase(query="write a script", expect_trigger=False),
        triggered=True,
        diagnosis="Description is too broad.",
    )
    text = _format_diagnostics([fn], [fp])
    assert "DIAGNOSTIC DETAILS" in text
    assert "RIVAL: explain-code" in text
    assert "Description lacks" in text
    assert "FN:" in text
    assert "FP:" in text


def test_format_diagnostics_no_diagnosed():
    from skill_tester.optimizer import _format_diagnostics
    r = TestResult(
        case=TestCase(query="test", expect_trigger=True),
        triggered=False,
    )
    assert _format_diagnostics([r], []) == ""
