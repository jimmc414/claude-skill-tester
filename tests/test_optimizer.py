from textwrap import dedent

from skill_tester.parser import parse_skill, rewrite_frontmatter


def test_rewrite_frontmatter_adds_when_to_use(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(dedent("""\
        ---
        name: my-skill
        description: Original description.
        ---
        # Body
        Content here.
    """))

    rewrite_frontmatter(skill_file, "New description.", "Use when X happens.")

    skill = parse_skill(skill_dir)
    assert skill.description == "New description."
    assert skill.when_to_use == "Use when X happens."
    assert skill.name == "my-skill"
    assert "# Body" in skill.body


def test_rewrite_frontmatter_preserves_other_fields(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(dedent("""\
        ---
        name: test-skill
        description: Old.
        version: 1.0.0
        license: MIT
        ---
        Body.
    """))

    rewrite_frontmatter(skill_file, "New.", "Triggers here.")

    text = skill_file.read_text()
    assert "version: 1.0.0" in text
    assert "license: MIT" in text
    assert "name: test-skill" in text


def test_rewrite_frontmatter_updates_existing_when_to_use(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(dedent("""\
        ---
        name: test-skill
        description: Desc.
        when_to_use: Old triggers.
        ---
        Body.
    """))

    rewrite_frontmatter(skill_file, "Desc.", "New triggers.")

    skill = parse_skill(skill_file)
    assert skill.when_to_use == "New triggers."


def test_parse_skill_extracts_when_to_use(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(dedent("""\
        ---
        name: my-skill
        description: Does things.
        when_to_use: "Use when user says X or Y."
        ---
        Body.
    """))

    skill = parse_skill(skill_file)
    assert skill.when_to_use == "Use when user says X or Y."


def test_parse_skill_when_to_use_defaults_empty(tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text(dedent("""\
        ---
        name: my-skill
        description: Does things.
        ---
        Body.
    """))

    skill = parse_skill(skill_file)
    assert skill.when_to_use == ""
