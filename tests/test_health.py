import tempfile
from pathlib import Path

from skill_tester.health import (
    BUDGET_TOTAL,
    _compute_context_cost,
    _jaccard_similarity,
    check_frontmatter,
)
from skill_tester.models import FrontmatterHealth, SkillInfo


def _make_skill(name="test", description="", when_to_use="", body="", path=None):
    if path is None:
        path = Path("/fake/SKILL.md")
    return SkillInfo(
        name=name, description=description, path=path,
        body=body, when_to_use=when_to_use,
    )


def _write_skill(tmp_dir, frontmatter_lines):
    """Write a SKILL.md with exact frontmatter content and return its path."""
    skill_dir = Path(tmp_dir) / "test-skill"
    skill_dir.mkdir(exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text("---\n" + "\n".join(frontmatter_lines) + "\n---\n\nBody.\n")
    return path


# --- Context cost ---

def test_cost_description_only():
    skill = _make_skill(name="foo", description="bar")
    assert _compute_context_cost(skill) == len("foo") + 2 + len("bar")  # "foo: bar"


def test_cost_with_when_to_use():
    skill = _make_skill(name="foo", description="bar", when_to_use="baz")
    # "foo: bar - baz"
    assert _compute_context_cost(skill) == len("foo") + 2 + len("bar") + 3 + len("baz")


def test_cost_empty_when_to_use():
    skill = _make_skill(name="foo", description="bar", when_to_use="")
    assert _compute_context_cost(skill) == len("foo") + 2 + len("bar")


# --- Jaccard similarity ---

def test_jaccard_identical():
    assert _jaccard_similarity("hello world", "hello world") == 1.0


def test_jaccard_disjoint():
    assert _jaccard_similarity("hello world", "foo bar") == 0.0


def test_jaccard_partial():
    # words: {hello, world} vs {hello, there}
    # intersection: {hello}, union: {hello, world, there}
    assert abs(_jaccard_similarity("hello world", "hello there") - 1 / 3) < 0.01


def test_jaccard_empty():
    assert _jaccard_similarity("", "hello") == 0.0
    assert _jaccard_similarity("", "") == 0.0


def test_jaccard_case_insensitive():
    assert _jaccard_similarity("Hello World", "hello world") == 1.0


# --- Grade computation ---

def test_grade_healthy():
    h = FrontmatterHealth(
        skill_name="test", context_cost=50, budget_pct=0.003,
        has_when_to_use=True, has_hyphenated_when_to_use=False,
        redundancy_score=0.1, checks=[],
    )
    assert h.grade == "HEALTHY"


def test_grade_broken_on_error():
    from skill_tester.models import HealthCheck
    h = FrontmatterHealth(
        skill_name="test", context_cost=50, budget_pct=0.003,
        has_when_to_use=True, has_hyphenated_when_to_use=True,
        redundancy_score=0.0,
        checks=[HealthCheck(level="ERROR", code="E1", message="bad", field="when-to-use")],
    )
    assert h.grade == "BROKEN"


def test_grade_improvable_on_warn():
    from skill_tester.models import HealthCheck
    h = FrontmatterHealth(
        skill_name="test", context_cost=50, budget_pct=0.003,
        has_when_to_use=False, has_hyphenated_when_to_use=False,
        redundancy_score=0.0,
        checks=[HealthCheck(level="WARN", code="W1", message="missing", field="when_to_use")],
    )
    assert h.grade == "IMPROVABLE"


# --- Full check_frontmatter ---

def test_check_healthy_skill():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_skill(tmp, [
            "name: my-skill",
            'description: "Handles code review tasks."',
            'when_to_use: "Use when reviewing PRs or analyzing code quality."',
        ])
        skill = _make_skill(
            name="my-skill",
            description="Handles code review tasks.",
            when_to_use="Use when reviewing PRs or analyzing code quality.",
            path=path,
        )
        health = check_frontmatter(skill)
        assert health.grade == "HEALTHY"
        assert health.has_when_to_use
        assert not health.has_hyphenated_when_to_use
        codes = [c.code for c in health.checks]
        assert "I1" in codes  # complementary content


def test_check_detects_hyphenated():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_skill(tmp, [
            "name: my-skill",
            'description: "Does things."',
            'when-to-use: "Use when asked about things."',
        ])
        skill = _make_skill(name="my-skill", description="Does things.", path=path)
        health = check_frontmatter(skill)
        assert health.has_hyphenated_when_to_use
        assert health.grade == "BROKEN"
        codes = [c.code for c in health.checks]
        assert "E1" in codes


def test_check_missing_when_to_use():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_skill(tmp, [
            "name: my-skill",
            'description: "Does things."',
        ])
        skill = _make_skill(name="my-skill", description="Does things.", path=path)
        health = check_frontmatter(skill)
        assert not health.has_when_to_use
        codes = [c.code for c in health.checks]
        assert "W1" in codes
        assert health.grade == "IMPROVABLE"


def test_check_redundant_content():
    with tempfile.TemporaryDirectory() as tmp:
        desc = "Handles code review and quality analysis for pull requests"
        wtu = "Use for code review and quality analysis of pull requests"
        path = _write_skill(tmp, [
            "name: my-skill",
            f'description: "{desc}"',
            f'when_to_use: "{wtu}"',
        ])
        skill = _make_skill(name="my-skill", description=desc, when_to_use=wtu, path=path)
        health = check_frontmatter(skill)
        assert health.redundancy_score > 0.60
        codes = [c.code for c in health.checks]
        assert "W2" in codes


def test_check_description_too_long():
    with tempfile.TemporaryDirectory() as tmp:
        desc = "x" * 1025
        path = _write_skill(tmp, [
            "name: my-skill",
            f"description: '{desc}'",
        ])
        skill = _make_skill(name="my-skill", description=desc, path=path)
        health = check_frontmatter(skill)
        codes = [c.code for c in health.checks]
        assert "E2" in codes
        assert health.grade == "BROKEN"


def test_check_budget_pressure():
    with tempfile.TemporaryDirectory() as tmp:
        desc = "a " * 400  # 800 chars
        path = _write_skill(tmp, [
            "name: my-skill",
            f"description: '{desc.strip()}'",
        ])
        skill = _make_skill(name="my-skill", description=desc.strip(), path=path)
        health = check_frontmatter(skill)
        codes = [c.code for c in health.checks]
        assert "W3" in codes
