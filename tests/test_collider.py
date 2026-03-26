import io
from pathlib import Path

from skill_tester.collider import _detect_all_skills_in_events, _parse_collision_response
from skill_tester.models import CollisionQuery, CollisionReport, CollisionResult, SkillInfo
from skill_tester.reporter import print_collision_report


# --- Helpers ---

def _make_skill(name="skill-a", description="Does A things."):
    return SkillInfo(name=name, description=description, path=Path(f"/fake/{name}/SKILL.md"))


def _make_query(intended="skill-a", query_type="clear-a", query="do A stuff"):
    return CollisionQuery(query=query, intended_for=intended, query_type=query_type)


def _make_result(intended="skill-a", query_type="clear-a", fired=None, error=None):
    q = _make_query(intended=intended, query_type=query_type)
    return CollisionResult(query=q, skills_fired=fired or [], error=error)


def _make_events(*skill_names):
    blocks = [
        {"type": "tool_use", "name": "Skill", "input": {"skill": name}}
        for name in skill_names
    ]
    return [{"type": "assistant", "message": {"content": blocks}}]


# --- _detect_all_skills_in_events ---

def test_detect_all_single_skill():
    events = _make_events("my-skill")
    assert _detect_all_skills_in_events(events) == ["my-skill"]


def test_detect_all_multiple_skills():
    events = _make_events("skill-a", "skill-b")
    assert _detect_all_skills_in_events(events) == ["skill-a", "skill-b"]


def test_detect_all_dedup():
    events = _make_events("skill-a", "skill-a", "skill-b")
    assert _detect_all_skills_in_events(events) == ["skill-a", "skill-b"]


def test_detect_all_empty():
    assert _detect_all_skills_in_events([]) == []


def test_detect_all_non_skill_tools():
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/tmp/x"}},
    ]}}]
    assert _detect_all_skills_in_events(events) == []


def test_detect_all_mixed_tools_and_skills():
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
        {"type": "tool_use", "name": "Skill", "input": {"skill": "my-skill"}},
        {"type": "text", "text": "hello"},
    ]}}]
    assert _detect_all_skills_in_events(events) == ["my-skill"]


# --- CollisionResult properties ---

def test_sole_winner_single():
    r = _make_result(fired=["skill-a"])
    assert r.sole_winner == "skill-a"


def test_sole_winner_multiple():
    r = _make_result(fired=["skill-a", "skill-b"])
    assert r.sole_winner is None


def test_sole_winner_none():
    r = _make_result(fired=[])
    assert r.sole_winner is None


def test_stolen_true():
    r = _make_result(intended="skill-a", query_type="clear-a", fired=["skill-b"])
    assert r.stolen is True


def test_stolen_false_correct():
    r = _make_result(intended="skill-a", query_type="clear-a", fired=["skill-a"])
    assert r.stolen is False


def test_stolen_false_no_fire():
    r = _make_result(intended="skill-a", query_type="clear-a", fired=[])
    assert r.stolen is False


def test_stolen_false_boundary():
    r = _make_result(intended="skill-a", query_type="boundary", fired=["skill-b"])
    assert r.stolen is False


def test_stolen_false_error():
    r = _make_result(intended="skill-a", query_type="clear-a", fired=["skill-b"], error="timeout")
    assert r.stolen is False


def test_leaked_true():
    r = _make_result(intended="skill-a", query_type="clear-a", fired=[])
    assert r.leaked is True


def test_leaked_false_fired():
    r = _make_result(intended="skill-a", query_type="clear-a", fired=["skill-a"])
    assert r.leaked is False


def test_leaked_false_boundary():
    r = _make_result(intended="skill-a", query_type="boundary", fired=[])
    assert r.leaked is False


def test_leaked_false_error():
    r = _make_result(intended="skill-a", query_type="clear-a", fired=[], error="timeout")
    assert r.leaked is False


# --- CollisionReport properties ---

def test_theft_rate_clean():
    report = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[
            _make_result(intended="a", query_type="clear-a", fired=["a"]),
            _make_result(intended="b", query_type="clear-b", fired=["b"]),
        ],
    )
    assert report.theft_rate == 0.0


def test_theft_rate_all_stolen():
    report = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[
            _make_result(intended="a", query_type="clear-a", fired=["b"]),
            _make_result(intended="b", query_type="clear-b", fired=["a"]),
        ],
    )
    assert report.theft_rate == 1.0


def test_theft_rate_excludes_boundary():
    report = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[
            _make_result(intended="a", query_type="clear-a", fired=["a"]),
            _make_result(intended="a", query_type="boundary", fired=["b"]),  # not counted
        ],
    )
    assert report.theft_rate == 0.0


def test_theft_rate_excludes_errors():
    report = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[
            _make_result(intended="a", query_type="clear-a", fired=["b"]),
            _make_result(intended="b", query_type="clear-b", fired=[], error="timeout"),
        ],
    )
    assert report.theft_rate == 1.0  # 1 stolen / 1 valid clear


def test_theft_rate_empty():
    report = CollisionReport(skill_a=_make_skill("a"), skill_b=_make_skill("b"), results=[])
    assert report.theft_rate == 0.0


def test_boundary_agreement():
    report = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[
            _make_result(intended="a", query_type="boundary", fired=["a", "b"]),
            _make_result(intended="a", query_type="boundary", fired=["a"]),
        ],
    )
    assert report.boundary_agreement == 0.5


def test_boundary_agreement_empty():
    report = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[
            _make_result(intended="a", query_type="clear-a", fired=["a"]),
        ],
    )
    assert report.boundary_agreement == 0.0


def test_verdict_clean():
    report = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[_make_result(intended="a", query_type="clear-a", fired=["a"])],
    )
    assert report.verdict == "CLEAN"


def test_verdict_low():
    # 1 stolen out of 10 clear = 10%
    results = [_make_result(intended="a", query_type="clear-a", fired=["a"])] * 9
    results.append(_make_result(intended="b", query_type="clear-b", fired=["a"]))
    report = CollisionReport(skill_a=_make_skill("a"), skill_b=_make_skill("b"), results=results)
    assert report.verdict == "LOW"


def test_verdict_moderate():
    # 3 stolen out of 10 clear = 30%
    results = [_make_result(intended="a", query_type="clear-a", fired=["a"])] * 7
    results += [_make_result(intended="b", query_type="clear-b", fired=["a"])] * 3
    report = CollisionReport(skill_a=_make_skill("a"), skill_b=_make_skill("b"), results=results)
    assert report.verdict == "MODERATE"


def test_verdict_high():
    # 4 stolen out of 10 clear = 40%
    results = [_make_result(intended="a", query_type="clear-a", fired=["a"])] * 6
    results += [_make_result(intended="b", query_type="clear-b", fired=["a"])] * 4
    report = CollisionReport(skill_a=_make_skill("a"), skill_b=_make_skill("b"), results=results)
    assert report.verdict == "HIGH_COLLISION"


# --- _parse_collision_response ---

def test_parse_basic_json():
    text = '[{"query": "do A", "intended_for": "skill-a", "query_type": "clear-a"}]'
    result = _parse_collision_response(text)
    assert len(result) == 1
    assert result[0].query == "do A"
    assert result[0].intended_for == "skill-a"
    assert result[0].query_type == "clear-a"


def test_parse_markdown_fences():
    text = '```json\n[{"query": "do B", "intended_for": "skill-b", "query_type": "clear-b"}]\n```'
    result = _parse_collision_response(text)
    assert len(result) == 1
    assert result[0].query == "do B"


def test_parse_multiple_queries():
    text = """[
        {"query": "q1", "intended_for": "a", "query_type": "clear-a"},
        {"query": "q2", "intended_for": "b", "query_type": "clear-b"},
        {"query": "q3", "intended_for": "a", "query_type": "boundary"}
    ]"""
    result = _parse_collision_response(text)
    assert len(result) == 3
    assert result[2].query_type == "boundary"


# --- Reporter output ---

def test_reporter_contains_key_strings():
    report = CollisionReport(
        skill_a=_make_skill("alpha"),
        skill_b=_make_skill("beta"),
        results=[
            _make_result(intended="alpha", query_type="clear-a", fired=["alpha"]),
            _make_result(intended="beta", query_type="clear-b", fired=["alpha"]),  # stolen
            _make_result(intended="alpha", query_type="boundary", fired=["alpha", "beta"]),
        ],
    )
    buf = io.StringIO()
    print_collision_report([report], file=buf)
    output = buf.getvalue()

    assert "alpha vs beta" in output
    assert "CORRECT" in output
    assert "STOLEN" in output
    assert "SHARED" in output
    assert "Theft rate:" in output
    assert "Verdict:" in output
    assert "Stolen queries:" in output
    assert "Cost:" in output


def test_reporter_multi_pair_summary():
    r1 = CollisionReport(
        skill_a=_make_skill("a"), skill_b=_make_skill("b"),
        results=[_make_result(intended="a", query_type="clear-a", fired=["a"])],
    )
    r2 = CollisionReport(
        skill_a=_make_skill("c"), skill_b=_make_skill("d"),
        results=[_make_result(intended="c", query_type="clear-a", fired=["d"])],
    )
    buf = io.StringIO()
    print_collision_report([r1, r2], file=buf)
    output = buf.getvalue()

    assert "Summary" in output
    assert "a vs b" in output
    assert "c vs d" in output
