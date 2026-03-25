from pathlib import Path
from textwrap import dedent

import pytest

from skill_tester.parser import parse_skill, load_test_suite, _split_frontmatter, _extract_trigger_phrases


def test_split_frontmatter():
    text = "---\nname: foo\n---\n# Body"
    fm, body = _split_frontmatter(text)
    assert "name: foo" in fm
    assert "# Body" in body


def test_split_frontmatter_missing_opening():
    with pytest.raises(ValueError, match="missing YAML frontmatter"):
        _split_frontmatter("no frontmatter here")


def test_extract_trigger_phrases_with_use_when():
    desc = 'Analyzes code. Use when user asks to "review code", "check quality", or "audit".'
    phrases = _extract_trigger_phrases(desc)
    assert len(phrases) >= 2
    assert any("review code" in p for p in phrases)


def test_extract_trigger_phrases_fallback():
    desc = "Generates PDF reports from data. Handles charts and tables."
    phrases = _extract_trigger_phrases(desc)
    assert len(phrases) >= 1


def test_parse_skill_from_directory(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: my-skill
        description: Does things. Use when user says "do the thing".
        ---
        # My Skill
        Instructions here.
    """))

    skill = parse_skill(skill_dir)
    assert skill.name == "my-skill"
    assert "Does things" in skill.description
    assert "# My Skill" in skill.body


def test_parse_skill_from_file(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(dedent("""\
        ---
        name: direct-skill
        description: A direct skill file.
        ---
        Body content.
    """))

    skill = parse_skill(skill_file)
    assert skill.name == "direct-skill"


def test_parse_skill_missing_name(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\ndescription: no name\n---\nbody")

    with pytest.raises(ValueError, match="missing required 'name'"):
        parse_skill(skill_file)


def test_load_test_suite(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(dedent("""\
        ---
        name: test-skill
        description: A test skill.
        ---
        Body.
    """))

    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(dedent(f"""\
        skill:
          path: {skill_dir}
        cases:
          - query: "trigger this"
            expect_trigger: true
            category: positive
          - query: "ignore this"
            expect_trigger: false
            category: negative
    """))

    skill, cases = load_test_suite(suite_file)
    assert skill.name == "test-skill"
    assert len(cases) == 2
    assert cases[0].expect_trigger is True
    assert cases[1].expect_trigger is False
