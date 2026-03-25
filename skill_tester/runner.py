from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time

from .models import TestCase, TestResult


def run_test(
    case: TestCase,
    target_skill: str,
    timeout: int = 120,
    backend: str = "cli",
) -> TestResult:
    if backend == "sdk":
        return _run_test_sdk(case, target_skill, timeout)
    # "api" falls back to "cli" — trigger detection requires the Claude Code runtime
    return _run_test_cli(case, target_skill, timeout)


def run_suite(
    cases: list[TestCase],
    target_skill: str,
    timeout: int = 120,
    backend: str = "cli",
) -> list[TestResult]:
    results = []
    total = len(cases)
    for i, case in enumerate(cases, 1):
        expect = "should trigger" if case.expect_trigger else "should NOT trigger"
        print(
            f"  [{i}/{total}] {expect}: {case.query[:70]}",
            file=sys.stderr,
            flush=True,
        )
        result = run_test(case, target_skill, timeout, backend)
        status = "PASS" if result.passed else ("ERR" if result.error else "FAIL")
        print(f"           -> {status}", file=sys.stderr, flush=True)
        results.append(result)
    return results


# --- CLI backend ---


def _run_test_cli(case: TestCase, target_skill: str, timeout: int) -> TestResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            ["claude", "-p", case.query, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TestResult(
            case=case,
            triggered=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=f"Timed out after {timeout}s",
        )
    except FileNotFoundError:
        return TestResult(
            case=case,
            triggered=False,
            error="'claude' CLI not found on PATH",
        )

    duration_ms = int((time.monotonic() - start) * 1000)

    try:
        events = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return TestResult(
            case=case,
            triggered=False,
            duration_ms=duration_ms,
            error=f"Failed to parse CLI JSON: {proc.stdout[:200]}",
        )

    triggered = _detect_skill_in_events(events, target_skill)
    cost_usd, api_duration = _extract_result_meta(events)

    return TestResult(
        case=case,
        triggered=triggered,
        duration_ms=api_duration or duration_ms,
        cost_usd=cost_usd,
        raw_output=events,
    )


def _detect_skill_in_events(events: list[dict], target_skill: str) -> bool:
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") != "tool_use":
                continue
            if block.get("name") != "Skill":
                continue
            if block.get("input", {}).get("skill") == target_skill:
                return True
    return False


def _extract_result_meta(events: list[dict]) -> tuple[float, int]:
    for event in events:
        if event.get("type") == "result":
            cost = event.get("total_cost_usd", 0.0)
            duration = event.get("duration_api_ms", 0)
            return cost, duration
    return 0.0, 0


# --- Agent SDK backend ---


def _run_test_sdk(case: TestCase, target_skill: str, timeout: int) -> TestResult:
    start = time.monotonic()
    try:
        triggered, cost_usd, duration_ms = asyncio.run(
            _run_query_sdk(case.query, target_skill, timeout)
        )
    except Exception as e:
        return TestResult(
            case=case,
            triggered=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            error=str(e),
        )

    return TestResult(
        case=case,
        triggered=triggered,
        duration_ms=duration_ms or int((time.monotonic() - start) * 1000),
        cost_usd=cost_usd,
    )


async def _run_query_sdk(
    prompt: str, target_skill: str, timeout: int
) -> tuple[bool, float, int]:
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage, ToolUseBlock

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=3,
    )

    triggered = False
    cost_usd = 0.0
    duration_ms = 0

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if (
                    isinstance(block, ToolUseBlock)
                    and block.name == "Skill"
                    and block.input.get("skill") == target_skill
                ):
                    triggered = True
        elif isinstance(message, ResultMessage):
            cost_usd = message.total_cost_usd or 0.0
            duration_ms = message.duration_api_ms

    return triggered, cost_usd, duration_ms
