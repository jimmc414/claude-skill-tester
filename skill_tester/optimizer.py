from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .generator import call_claude, generate_tests
from .models import (
    OptimizationResult,
    OptimizationRound,
    ScoreCard,
    SkillInfo,
    TestCase,
)
from .parser import parse_skill, rewrite_frontmatter
from .runner import run_suite
from .scorer import score

_OPTIMIZATION_PROMPT = """\
You are optimizing a Claude Code skill's frontmatter to improve trigger accuracy.

Claude decides whether to invoke a skill based on three frontmatter fields loaded into the system prompt:
  1. name — the skill identifier
  2. description — what it does and when to use it (max 1024 chars)
  3. when_to_use — detailed trigger conditions, phrases, and exclusions

Current frontmatter:
  name: {name}
  description: "{description}"
  when_to_use: "{when_to_use}"

Test results (F1: {f1:.2f}, Precision: {precision:.2f}, Recall: {recall:.2f}):

FALSE NEGATIVES — these queries SHOULD have triggered the skill but DIDN'T:
{fn_list}

FALSE POSITIVES — these queries should NOT have triggered but DID:
{fp_list}

TRUE POSITIVES — these queries correctly triggered (preserve these):
{tp_list}

Write improved frontmatter that:
1. Fixes false negatives by adding trigger phrases that match those queries
2. Fixes false positives by adding "Do NOT use for..." exclusions
3. Preserves whatever currently matches the true positives
4. description: [What it does]. [Core trigger phrases]. [Key exclusions]. MUST be under 1024 characters.
5. when_to_use: Detailed trigger conditions with specific user phrases and exclusions. Be thorough.
6. No XML angle brackets (< >) in either field
7. If the name is hurting trigger accuracy (e.g. misleading or too vague), suggest a better name

Return ONLY valid JSON:
{{"description": "...", "when_to_use": "...", "name_suggestion": null}}
Set name_suggestion to a string only if the current name actively hurts matching. Otherwise null."""


def optimize_skill(
    skill_path: Path,
    target_f1: float = 0.90,
    max_rounds: int = 5,
    n_positive: int = 10,
    n_negative: int = 5,
    timeout: int = 120,
    backend: str = "cli",
    dry_run: bool = False,
) -> OptimizationResult:
    skill_path = Path(skill_path).expanduser().resolve()
    skill = parse_skill(skill_path)

    result = OptimizationResult(
        skill_name=skill.name,
        skill_path=skill.path,
        original_description=skill.description,
        original_when_to_use=skill.when_to_use,
        final_description=skill.description,
        final_when_to_use=skill.when_to_use,
        target_f1=target_f1,
    )

    # Trigger detection requires the Claude Code runtime (cli or sdk).
    # When backend is "api", we use it for inference (generation + proposals)
    # but fall back to "cli" for the actual trigger test runs.
    run_backend = "cli" if backend == "api" else backend
    if backend == "api":
        print("  Note: using API for inference, CLI for trigger detection", file=sys.stderr)

    regression_cases: list[TestCase] = []
    backed_up = False

    for round_num in range(1, max_rounds + 1):
        print(
            f"\n{'=' * 50}\nRound {round_num}/{max_rounds}\n{'=' * 50}",
            file=sys.stderr,
        )

        # Generate fresh tests from current description (uses chosen backend)
        print("  Generating test queries...", file=sys.stderr, flush=True)
        fresh_cases = generate_tests(skill, n_positive, n_negative, backend)

        # Merge with regression cases (dedup by query text)
        seen = {c.query for c in fresh_cases}
        all_cases = list(fresh_cases)
        for rc in regression_cases:
            if rc.query not in seen:
                all_cases.append(rc)
                seen.add(rc.query)

        # Run suite (always cli or sdk — trigger detection needs Claude Code)
        print(f"  Running {len(all_cases)} tests ({len(regression_cases)} regression)...", file=sys.stderr, flush=True)
        results = run_suite(all_cases, skill.name, timeout=timeout, backend=run_backend)
        card = score(results)

        # Collect failures
        fn_queries = [r.case.query for r in results if r.case.expect_trigger and not r.triggered and not r.error]
        fp_queries = [r.case.query for r in results if not r.case.expect_trigger and r.triggered and not r.error]
        tp_queries = [r.case.query for r in results if r.case.expect_trigger and r.triggered and not r.error]

        round_data = OptimizationRound(
            round_num=round_num,
            description=skill.description,
            when_to_use=skill.when_to_use,
            score=card,
            false_negatives=fn_queries,
            false_positives=fp_queries,
            num_regression_cases=len(regression_cases),
        )

        print(
            f"\n  F1: {card.f1:.2f} ({card.verdict})  "
            f"TP:{card.tp} FP:{card.fp} TN:{card.tn} FN:{card.fn}",
            file=sys.stderr,
        )

        # Check convergence
        if card.f1 >= target_f1:
            print(f"  Converged! F1 >= {target_f1}", file=sys.stderr)
            result.rounds.append(round_data)
            result.converged = True
            result.final_description = skill.description
            result.final_when_to_use = skill.when_to_use
            break

        # Add failures to regression set
        for q in fn_queries:
            if not any(c.query == q for c in regression_cases):
                regression_cases.append(TestCase(query=q, expect_trigger=True, category="regression"))
        for q in fp_queries:
            if not any(c.query == q for c in regression_cases):
                regression_cases.append(TestCase(query=q, expect_trigger=False, category="regression"))

        # Propose improvements
        print("  Proposing improved frontmatter...", file=sys.stderr, flush=True)
        new_desc, new_wtu, name_suggestion = _propose_improvements(
            skill, card, fn_queries, fp_queries, tp_queries, backend
        )
        round_data.name_suggestion = name_suggestion
        result.rounds.append(round_data)

        if new_desc == skill.description and new_wtu == skill.when_to_use:
            print("  No changes proposed. Stopping.", file=sys.stderr)
            result.final_description = skill.description
            result.final_when_to_use = skill.when_to_use
            break

        # Backup and write
        if not dry_run:
            if not backed_up:
                _backup_skill(skill.path)
                backed_up = True
            rewrite_frontmatter(skill.path, new_desc, new_wtu)
            skill = parse_skill(skill_path)
            print("  SKILL.md updated.", file=sys.stderr)
        else:
            print("  [dry-run] Would update SKILL.md.", file=sys.stderr)
            # Simulate the update for the next round's reporting
            skill = SkillInfo(
                name=skill.name,
                description=new_desc,
                path=skill.path,
                body=skill.body,
                when_to_use=new_wtu,
            )

        result.final_description = new_desc
        result.final_when_to_use = new_wtu
    else:
        # Exhausted rounds without converging
        result.final_description = skill.description
        result.final_when_to_use = skill.when_to_use

    return result


def _propose_improvements(
    skill: SkillInfo,
    card: ScoreCard,
    fn_queries: list[str],
    fp_queries: list[str],
    tp_queries: list[str],
    backend: str,
) -> tuple[str, str, str | None]:
    fn_list = "\n".join(f'  - "{q}"' for q in fn_queries) if fn_queries else "  (none)"
    fp_list = "\n".join(f'  - "{q}"' for q in fp_queries) if fp_queries else "  (none)"
    tp_list = "\n".join(f'  - "{q}"' for q in tp_queries) if tp_queries else "  (none)"

    prompt = _OPTIMIZATION_PROMPT.format(
        name=skill.name,
        description=skill.description,
        when_to_use=skill.when_to_use or "(not set)",
        f1=card.f1,
        precision=card.precision,
        recall=card.recall,
        fn_list=fn_list,
        fp_list=fp_list,
        tp_list=tp_list,
    )

    text = call_claude(prompt, backend)

    # Strip markdown code fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        stripped = "\n".join(lines)

    data = json.loads(stripped)
    new_desc = data.get("description", skill.description)
    new_wtu = data.get("when_to_use", skill.when_to_use or "")
    name_suggestion = data.get("name_suggestion")

    # Enforce description limit
    if len(new_desc) > 1024:
        new_desc = new_desc[:1021] + "..."

    return new_desc, new_wtu, name_suggestion


def _backup_skill(path: Path) -> Path:
    backup = path.with_suffix(".md.bak")
    shutil.copy2(path, backup)
    print(f"  Backup saved: {backup}", file=sys.stderr)
    return backup
