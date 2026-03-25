from __future__ import annotations

from pathlib import Path

import yaml

from .models import SkillInfo, TestCase


def parse_skill(path: Path) -> SkillInfo:
    path = Path(path).expanduser().resolve()
    if path.is_dir():
        skill_file = path / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"No SKILL.md in {path}")
        path = skill_file

    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)

    meta = yaml.safe_load(frontmatter) or {}
    name = meta.get("name")
    if not name:
        raise ValueError(f"SKILL.md missing required 'name' field: {path}")
    description = meta.get("description", "")

    when_to_use = meta.get("when_to_use", "")

    return SkillInfo(
        name=name,
        description=description,
        path=path,
        body=body.strip(),
        when_to_use=when_to_use,
        trigger_phrases=_extract_trigger_phrases(description),
    )


def load_test_suite(yaml_path: Path) -> tuple[SkillInfo, list[TestCase]]:
    yaml_path = Path(yaml_path).expanduser().resolve()
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    skill_data = data.get("skill", {})
    skill_path = skill_data.get("path")
    if skill_path:
        skill = parse_skill(Path(skill_path))
    else:
        skill = SkillInfo(
            name=skill_data["name"],
            description=skill_data.get("description", ""),
            path=yaml_path,
        )

    cases = [
        TestCase(
            query=c["query"],
            expect_trigger=c["expect_trigger"],
            category=c.get("category", "positive"),
        )
        for c in data.get("cases", [])
    ]
    return skill, cases


def discover_skills(skills_dir: Path | None = None) -> list[SkillInfo]:
    if skills_dir is None:
        skills_dir = Path.home() / ".claude" / "skills"
    skills_dir = Path(skills_dir).expanduser().resolve()
    if not skills_dir.is_dir():
        return []

    found = []
    for entry in sorted(skills_dir.iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").exists():
            try:
                found.append(parse_skill(entry))
            except (ValueError, FileNotFoundError):
                continue
    return found


def rewrite_frontmatter(path: Path, description: str, when_to_use: str) -> None:
    path = Path(path).expanduser().resolve()
    text = path.read_text(encoding="utf-8")
    fm_str, body = _split_frontmatter(text)

    meta = yaml.safe_load(fm_str) or {}
    meta["description"] = description
    meta["when_to_use"] = when_to_use

    new_fm = yaml.dump(meta, default_flow_style=False, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{new_fm}\n---{body}", encoding="utf-8")


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("SKILL.md missing YAML frontmatter (no opening ---)")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md missing closing --- for frontmatter")
    return parts[1], parts[2]


def _extract_trigger_phrases(description: str) -> list[str]:
    phrases = []
    for marker in ["Use when", "Use for", "Use if", "Trigger when"]:
        if marker.lower() in description.lower():
            idx = description.lower().index(marker.lower())
            tail = description[idx + len(marker) :].strip().rstrip(".")
            for part in tail.split(","):
                part = part.strip().strip('"').strip("'")
                if part:
                    phrases.append(part)
    if not phrases:
        phrases = [s.strip() for s in description.split(".") if s.strip()]
    return phrases
