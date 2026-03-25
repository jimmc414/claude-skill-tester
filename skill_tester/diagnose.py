"""Post-run diagnostics for test failures."""
from __future__ import annotations

import sys

from .generator import call_claude
from .models import SkillInfo, TestResult

_DIAGNOSTIC_PROMPT = """\
A Claude Code skill was expected to trigger but did not.

Target skill:
  name: {name}
  description: "{description}"
  when_to_use: "{when_to_use}"

User query that SHOULD have triggered this skill:
  "{query}"

{rival_section}
In 1-3 sentences, explain:
1. Why this query did not match the skill's description/when_to_use
2. What specific words or concepts in the query are missing from the frontmatter
3. What change to the description or when_to_use would capture this query

Be specific and actionable. Focus on the semantic gap."""

_FP_DIAGNOSTIC_PROMPT = """\
A Claude Code skill triggered when it should NOT have.

Target skill:
  name: {name}
  description: "{description}"
  when_to_use: "{when_to_use}"

User query that should NOT have triggered this skill:
  "{query}"

In 1-3 sentences, explain:
1. What about the description/when_to_use caused this query to match
2. What exclusion or narrowing would prevent this false trigger

Be specific and actionable."""


def diagnose_failures(
    results: list[TestResult],
    skill: SkillInfo,
    backend: str,
) -> None:
    """Diagnose false negatives and false positives in-place."""
    failures = [
        r for r in results
        if not r.passed and not r.error
    ]
    if not failures:
        return

    print(f"\n  Diagnosing {len(failures)} failure(s)...", file=sys.stderr, flush=True)

    for i, r in enumerate(failures, 1):
        print(f"    [{i}/{len(failures)}] diagnosing: {r.case.query[:60]}", file=sys.stderr, flush=True)
        try:
            if r.case.expect_trigger and not r.triggered:
                r.diagnosis = _diagnose_fn(r, skill, backend)
            elif not r.case.expect_trigger and r.triggered:
                r.diagnosis = _diagnose_fp(r, skill, backend)
        except Exception as e:
            r.diagnosis = f"(diagnostic failed: {e})"


def _diagnose_fn(result: TestResult, skill: SkillInfo, backend: str) -> str:
    rival_section = ""
    if result.rival_skill:
        rival_section = f'A different skill "{result.rival_skill}" triggered instead.\n'
    else:
        rival_section = "No skill was triggered at all.\n"

    prompt = _DIAGNOSTIC_PROMPT.format(
        name=skill.name,
        description=skill.description,
        when_to_use=skill.when_to_use or "(not set)",
        query=result.case.query,
        rival_section=rival_section,
    )
    return call_claude(prompt, backend).strip()


def _diagnose_fp(result: TestResult, skill: SkillInfo, backend: str) -> str:
    prompt = _FP_DIAGNOSTIC_PROMPT.format(
        name=skill.name,
        description=skill.description,
        when_to_use=skill.when_to_use or "(not set)",
        query=result.case.query,
    )
    return call_claude(prompt, backend).strip()
