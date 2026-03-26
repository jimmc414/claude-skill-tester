from __future__ import annotations

import asyncio
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

from .generator import call_claude
from .models import CollisionQuery, CollisionReport, CollisionResult, SkillInfo
from .parser import parse_skill
from .runner import _extract_result_meta

_COLLISION_PROMPT = """\
You are generating test queries to detect trigger collisions between two Claude Code skills.

Skill A:
  Name: {name_a}
  Description: {desc_a}
  When to use: {wtu_a}

Skill B:
  Name: {name_b}
  Description: {desc_b}
  When to use: {wtu_b}

Generate exactly {n_clear} CLEAR-A queries, {n_clear} CLEAR-B queries, and {n_boundary} BOUNDARY queries.

CLEAR-A queries: Should obviously trigger Skill A and NOT Skill B. Use language specific to A.
CLEAR-B queries: Should obviously trigger Skill B and NOT Skill A. Use language specific to B.
BOUNDARY queries: Ambiguous queries that could reasonably trigger either skill. Set "intended_for" to whichever skill is the slightly better fit.

Return a JSON array of objects with:
- "query": the user prompt
- "intended_for": "{name_a}" or "{name_b}"
- "query_type": "clear-a", "clear-b", or "boundary"

Return ONLY the JSON array, no other text."""


def generate_collision_queries(
    skill_a: SkillInfo,
    skill_b: SkillInfo,
    n_clear: int = 5,
    n_boundary: int = 5,
    backend: str = "cli",
) -> list[CollisionQuery]:
    prompt = _COLLISION_PROMPT.format(
        name_a=skill_a.name,
        desc_a=skill_a.description,
        wtu_a=skill_a.when_to_use or "(not set)",
        name_b=skill_b.name,
        desc_b=skill_b.description,
        wtu_b=skill_b.when_to_use or "(not set)",
        n_clear=n_clear,
        n_boundary=n_boundary,
    )
    text = call_claude(prompt, backend)
    return _parse_collision_response(text)


def _parse_collision_response(text: str) -> list[CollisionQuery]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        stripped = "\n".join(lines)

    data = json.loads(stripped)
    return [
        CollisionQuery(
            query=item["query"],
            intended_for=item["intended_for"],
            query_type=item["query_type"],
        )
        for item in data
    ]


def _detect_all_skills_in_events(events: list[dict]) -> list[str]:
    """Return all unique skill names invoked in the events, preserving first-seen order."""
    seen = set()
    result = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") != "tool_use" or block.get("name") != "Skill":
                continue
            skill_name = block.get("input", {}).get("skill")
            if skill_name and skill_name not in seen:
                seen.add(skill_name)
                result.append(skill_name)
    return result


def _run_collision_cli(query: CollisionQuery, timeout: int) -> CollisionResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["claude", "-p", query.query, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CollisionResult(
            query=query,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=f"Timed out after {timeout}s",
        )
    except FileNotFoundError:
        return CollisionResult(
            query=query,
            error="'claude' CLI not found on PATH",
        )

    duration_ms = int((time.monotonic() - start) * 1000)

    try:
        events = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return CollisionResult(
            query=query,
            duration_ms=duration_ms,
            error=f"Failed to parse CLI JSON: {proc.stdout[:200]}",
        )

    skills_fired = _detect_all_skills_in_events(events)
    cost_usd, api_duration = _extract_result_meta(events)

    return CollisionResult(
        query=query,
        skills_fired=skills_fired,
        duration_ms=api_duration or duration_ms,
        cost_usd=cost_usd,
    )


def _run_collision_sdk(query: CollisionQuery, timeout: int) -> CollisionResult:
    start = time.monotonic()
    try:
        skills_fired, cost_usd, duration_ms = asyncio.run(
            _run_query_sdk(query.query, timeout)
        )
    except Exception as e:
        return CollisionResult(
            query=query,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(e),
        )

    return CollisionResult(
        query=query,
        skills_fired=skills_fired,
        duration_ms=duration_ms or int((time.monotonic() - start) * 1000),
        cost_usd=cost_usd,
    )


async def _run_query_sdk(prompt: str, timeout: int) -> tuple[list[str], float, int]:
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage, ToolUseBlock

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=3,
    )

    seen = set()
    skills_fired: list[str] = []
    cost_usd = 0.0
    duration_ms = 0

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name == "Skill":
                    skill_name = block.input.get("skill")
                    if skill_name and skill_name not in seen:
                        seen.add(skill_name)
                        skills_fired.append(skill_name)
        elif isinstance(message, ResultMessage):
            cost_usd = message.total_cost_usd or 0.0
            duration_ms = message.duration_api_ms

    return skills_fired, cost_usd, duration_ms


def run_collision_test(
    query: CollisionQuery,
    timeout: int = 120,
    backend: str = "cli",
) -> CollisionResult:
    if backend == "sdk":
        return _run_collision_sdk(query, timeout)
    return _run_collision_cli(query, timeout)


def run_collision_suite(
    queries: list[CollisionQuery],
    timeout: int = 120,
    backend: str = "cli",
) -> list[CollisionResult]:
    results = []
    total = len(queries)
    for i, q in enumerate(queries, 1):
        print(
            f"  [{i}/{total}] {q.query_type} (for {q.intended_for}): {q.query[:60]}",
            file=sys.stderr,
            flush=True,
        )
        result = run_collision_test(q, timeout, backend)
        fired = ", ".join(result.skills_fired) if result.skills_fired else "(none)"
        tag = "ERR" if result.error else ("STOLEN" if result.stolen else "OK")
        print(f"           -> {tag} fired=[{fired}]", file=sys.stderr, flush=True)
        results.append(result)
    return results


def collide(
    skill_paths: list[Path],
    n_clear: int = 5,
    n_boundary: int = 5,
    timeout: int = 120,
    backend: str = "cli",
) -> list[CollisionReport]:
    skills = [parse_skill(p) for p in skill_paths]

    # Trigger detection needs Claude Code runtime
    run_backend = "cli" if backend == "api" else backend
    if backend == "api":
        print("  Note: using API for inference, CLI for trigger detection", file=sys.stderr)

    reports = []
    pairs = list(itertools.combinations(skills, 2))
    for pair_idx, (skill_a, skill_b) in enumerate(pairs, 1):
        print(
            f"\nPair {pair_idx}/{len(pairs)}: {skill_a.name} vs {skill_b.name}",
            file=sys.stderr,
            flush=True,
        )

        print("  Generating collision queries...", file=sys.stderr, flush=True)
        queries = generate_collision_queries(
            skill_a, skill_b, n_clear=n_clear, n_boundary=n_boundary, backend=backend
        )

        print(f"  Running {len(queries)} queries...", file=sys.stderr, flush=True)
        results = run_collision_suite(queries, timeout=timeout, backend=run_backend)

        reports.append(CollisionReport(
            skill_a=skill_a,
            skill_b=skill_b,
            results=results,
        ))

    return reports
