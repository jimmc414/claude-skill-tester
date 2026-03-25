"""Static analysis of skill frontmatter quality."""
from __future__ import annotations

import re

import yaml

from .models import FrontmatterHealth, HealthCheck, SkillInfo

BUDGET_TOTAL = 16_000
_BUDGET_WARN_PCT = 0.05  # 5% of total = 800 chars
_REDUNDANCY_WARN = 0.60
_REDUNDANCY_GOOD = 0.30
_DESCRIPTION_MAX = 1024


def check_frontmatter(skill: SkillInfo) -> FrontmatterHealth:
    """Run all health checks on a single skill."""
    raw_meta = _read_raw_meta(skill.path)
    cost = _compute_context_cost(skill)
    budget_pct = cost / BUDGET_TOTAL
    has_wtu = bool(skill.when_to_use)
    has_hyphen = "when-to-use" in raw_meta
    redundancy = _jaccard_similarity(skill.description, skill.when_to_use) if has_wtu else 0.0

    checks: list[HealthCheck] = []

    # E1: Hyphenated when-to-use
    if has_hyphen:
        checks.append(HealthCheck(
            level="ERROR", code="E1",
            message="Uses 'when-to-use' (hyphenated) which is silently ignored. Rename to 'when_to_use' (underscore).",
            field="when-to-use",
        ))

    # E2: Description too long
    if len(skill.description) > _DESCRIPTION_MAX:
        checks.append(HealthCheck(
            level="ERROR", code="E2",
            message=f"description is {len(skill.description)} chars (max {_DESCRIPTION_MAX}). Content beyond {_DESCRIPTION_MAX} may be truncated.",
            field="description",
        ))

    # W1: Missing when_to_use
    if not has_wtu:
        checks.append(HealthCheck(
            level="WARN", code="W1",
            message="No when_to_use field. Adding trigger phrases and exclusions in when_to_use provides a second independent trigger surface.",
            field="when_to_use",
        ))

    # W2: High redundancy
    if has_wtu and redundancy > _REDUNDANCY_WARN:
        pct = int(redundancy * 100)
        checks.append(HealthCheck(
            level="WARN", code="W2",
            message=f"High overlap ({pct}%) between description and when_to_use. Use when_to_use for different trigger phrases and exclusions to maximize coverage.",
            field="when_to_use",
        ))

    # W3: Budget pressure
    if budget_pct > _BUDGET_WARN_PCT:
        checks.append(HealthCheck(
            level="WARN", code="W3",
            message=f"Context footprint is {cost} chars ({budget_pct:.1%} of ~{BUDGET_TOTAL:,} budget). Consider trimming for budget headroom.",
            field="description",
        ))

    # I1: Complementary content
    if has_wtu and redundancy < _REDUNDANCY_GOOD:
        checks.append(HealthCheck(
            level="INFO", code="I1",
            message="description and when_to_use are complementary (maximizes trigger surface).",
            field="when_to_use",
        ))

    return FrontmatterHealth(
        skill_name=skill.name,
        context_cost=cost,
        budget_pct=budget_pct,
        has_when_to_use=has_wtu,
        has_hyphenated_when_to_use=has_hyphen,
        redundancy_score=redundancy,
        checks=checks,
    )


def _compute_context_cost(skill: SkillInfo) -> int:
    """Compute chars consumed in context: 'name: description - when_to_use'."""
    cost = len(skill.name) + 2 + len(skill.description)  # "name: description"
    if skill.when_to_use:
        cost += 3 + len(skill.when_to_use)  # " - when_to_use"
    return cost


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    words_a = set(_tokenize(text_a))
    words_b = set(_tokenize(text_b))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase words, stripping punctuation."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _read_raw_meta(path) -> dict:
    """Read raw YAML frontmatter keys from a SKILL.md file."""
    try:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}
        return yaml.safe_load(parts[1]) or {}
    except (OSError, yaml.YAMLError):
        return {}
