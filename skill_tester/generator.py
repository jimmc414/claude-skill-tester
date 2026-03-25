from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import yaml

from .models import SkillInfo, TestCase

_GENERATION_PROMPT = """\
You are generating test queries for a Claude Code skill trigger evaluation.

The skill under test:
  Name: {name}
  Description: {description}

{body_section}

Generate exactly {n_positive} POSITIVE queries and {n_negative} NEGATIVE queries.

POSITIVE queries should:
- Be natural user requests that SHOULD trigger this skill
- Vary in phrasing, specificity, and directness
- Include paraphrases, indirect requests, and domain-specific language
- NOT mention the skill by name

NEGATIVE queries should:
- Be plausible user requests that should NOT trigger this skill
- Be from adjacent domains (close enough to seem related, but out of scope)
- Include some that are superficially similar but clearly different tasks

Return a JSON array of objects with "query", "expect_trigger" (boolean), and "category" ("positive" or "negative").

Return ONLY the JSON array, no other text."""


def generate_tests(
    skill: SkillInfo,
    n_positive: int = 10,
    n_negative: int = 5,
    backend: str = "cli",
) -> list[TestCase]:
    body_section = ""
    if skill.body:
        truncated = skill.body[:2000]
        body_section = f"Skill body (for context):\n{truncated}"

    prompt = _GENERATION_PROMPT.format(
        name=skill.name,
        description=skill.description,
        body_section=body_section,
        n_positive=n_positive,
        n_negative=n_negative,
    )

    text = call_claude(prompt, backend)
    return _parse_response(text)


def call_claude(prompt: str, backend: str) -> str:
    if backend == "sdk":
        return _generate_via_sdk(prompt)
    if backend == "api":
        return _generate_via_api(prompt)
    return _generate_via_cli(prompt)


def _generate_via_cli(prompt: str) -> str:
    proc = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    events = json.loads(proc.stdout)
    for event in events:
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    return block["text"]
    raise RuntimeError("No text response from claude CLI")


def _generate_via_sdk(prompt: str) -> str:
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, TextBlock

    async def _run() -> str:
        options = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            max_turns=1,
        )
        text_parts = []
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
        if not text_parts:
            raise RuntimeError("No text response from Agent SDK")
        return "\n".join(text_parts)

    return asyncio.run(_run())


def _generate_via_api(prompt: str, model: str = "claude-sonnet-4-20250514") -> str:
    from anthropic import Anthropic

    client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _parse_response(text: str) -> list[TestCase]:
    # Strip markdown code fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        stripped = "\n".join(lines)

    cases_data = json.loads(stripped)
    return [
        TestCase(
            query=c["query"],
            expect_trigger=c["expect_trigger"],
            category=c.get("category", "positive" if c["expect_trigger"] else "negative"),
        )
        for c in cases_data
    ]


def save_test_suite(
    skill: SkillInfo,
    cases: list[TestCase],
    output_path: Path,
) -> None:
    data = {
        "skill": {
            "name": skill.name,
            "path": str(skill.path),
            "description": skill.description,
        },
        "cases": [
            {
                "query": c.query,
                "expect_trigger": c.expect_trigger,
                "category": c.category,
            }
            for c in cases
        ],
    }
    Path(output_path).write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
