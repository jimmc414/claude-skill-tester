"""
Description-style A/B/C comparison for claude-skill-tester.

Holds name, body, when_to_use, and test queries constant.
Varies only the description field across three styles.
Reports F1 per style per skill and aggregate results.

Run from the repo root:
    python style_ab_test.py

Requirements:
    - claude-skill-tester installed (pip install -e .)
    - claude CLI authenticated
    - Writable working directory for test skill scaffolding
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

from skill_tester.generator import generate_tests
from skill_tester.models import SkillInfo, TestCase
from skill_tester.parser import parse_skill, rewrite_frontmatter
from skill_tester.runner import run_suite
from skill_tester.scorer import score


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

OUTPUT_DIR = Path("./style-test-runs")
TEST_SKILLS_DIR = Path("./.claude/skills")
RESULTS_FILE = OUTPUT_DIR / "results.json"
REPORT_FILE = OUTPUT_DIR / "report.md"

N_POSITIVE = 10
N_NEGATIVE = 5
BACKEND = "cli"
TIMEOUT = 240


# -----------------------------------------------------------------------------
# Test skills: same body, same name, varying only description style.
# Four skills chosen to exercise different failure modes.
# -----------------------------------------------------------------------------

@dataclass
class SkillSpec:
    name: str
    body: str
    styles: dict[str, str]  # style_label -> description text


SKILLS: list[SkillSpec] = [
    SkillSpec(
        name="trace-analyzer",
        body=(
            "Use system tracing tools (strace, ltrace, perf, ftrace) to diagnose "
            "Linux program behavior. Useful for crashes, performance issues, and "
            "system call analysis. Workflow: 1) Reproduce the issue. 2) Attach "
            "strace with appropriate filters. 3) Analyze syscall patterns for "
            "anomalies. 4) Cross-reference with perf for performance context."
        ),
        styles={
            "A_symptom": (
                "Diagnose Linux program problems. Program crashes randomly, "
                "segfault, SIGSEGV, why is my process hanging, CPU stuck at 100%, "
                "strange latency, syscall failures, memory corruption, "
                "mysterious EAGAIN errors, program killed by OOM."
            ),
            "B_directive": (
                "Linux program diagnostics expert. ALWAYS invoke this skill when "
                "the user asks about program crashes, hangs, segfaults, high CPU, "
                "system call failures, or unexplained process behavior on Linux. "
                "Do not attempt directly, use this skill first."
            ),
            "C_triggerexcl": (
                "Diagnoses Linux program issues using strace, ltrace, perf. Use "
                "when user asks about program crashes, hangs, segfaults, high CPU "
                "usage, system call failures, OOM kills. Do NOT use for Windows "
                "debugging, general code review, or application logic bugs."
            ),
        },
    ),
    SkillSpec(
        name="review-docs",
        body=(
            "Audit documentation for gaps, inconsistencies, and outdated content. "
            "Workflow: 1) Inventory what documentation exists. 2) Cross-check "
            "against actual behavior or codebase. 3) Flag missing coverage, "
            "stale examples, and contradictions. 4) Prioritize fixes by user "
            "impact."
        ),
        styles={
            "A_symptom": (
                "Audit project documentation. Our docs are out of date, missing "
                "sections, inconsistent with the code, don't cover new features, "
                "confusing for new users, contradict each other, or have broken "
                "examples."
            ),
            "B_directive": (
                "Documentation audit expert. ALWAYS invoke this skill when the "
                "user asks about reviewing, auditing, or checking documentation "
                "for gaps, staleness, or inconsistency. Do not attempt directly, "
                "use this skill first."
            ),
            "C_triggerexcl": (
                "Audits documentation for gaps and inconsistencies. Use when user "
                "asks to review docs, check documentation for gaps, find stale "
                "content, or audit documentation quality. Do NOT use for writing "
                "new documentation from scratch, general editing, or API reference "
                "generation."
            ),
        },
    ),
    SkillSpec(
        name="code-review-helper",
        body=(
            "Review pull requests and code changes. Focus on correctness, "
            "maintainability, and adherence to project conventions. Do not "
            "duplicate work done by linters. Workflow: 1) Understand the change's "
            "goal. 2) Check correctness against the stated goal. 3) Flag "
            "maintainability risks. 4) Note convention violations only when they "
            "impact reviewability."
        ),
        styles={
            "A_symptom": (
                "Review code changes. Is this PR correct, does this change break "
                "anything, is this maintainable, does this follow our "
                "conventions, should I merge this, what could go wrong with this "
                "change."
            ),
            "B_directive": (
                "Code review expert. ALWAYS invoke this skill when the user asks "
                "about reviewing a pull request, a diff, or a code change for "
                "correctness or maintainability. Do not attempt directly, use "
                "this skill first."
            ),
            "C_triggerexcl": (
                "Reviews PRs and code changes for correctness and "
                "maintainability. Use when user asks to review a pull request, "
                "review a diff, or check code changes before merging. Do NOT use "
                "for linting, formatting, running tests, or initial code "
                "authoring."
            ),
        },
    ),
    SkillSpec(
        name="convert-csv-to-json",
        body=(
            "Convert CSV data to JSON format. Handle common edge cases: quoted "
            "fields, embedded commas, mixed quoting, UTF-8 BOMs, header "
            "detection. Workflow: 1) Detect delimiter and quoting. 2) Parse with "
            "appropriate library. 3) Emit JSON matching requested shape (array "
            "of objects is default)."
        ),
        styles={
            "A_symptom": (
                "Convert CSV to JSON. I have a CSV file and need JSON output, "
                "turn this spreadsheet into JSON, parse CSV data, convert comma-"
                "separated values to JSON format, transform CSV rows into JSON "
                "objects."
            ),
            "B_directive": (
                "CSV-to-JSON conversion expert. ALWAYS invoke this skill when "
                "the user asks to convert CSV data to JSON, parse a CSV file, or "
                "transform spreadsheet data to JSON format. Do not attempt "
                "directly, use this skill first."
            ),
            "C_triggerexcl": (
                "Converts CSV data to JSON. Use when user asks to convert CSV to "
                "JSON, parse a CSV file into JSON, or transform comma-separated "
                "data to JSON objects. Do NOT use for JSON-to-CSV, Excel "
                "conversion, or general data cleaning."
            ),
        },
    ),
]


# -----------------------------------------------------------------------------
# Test scaffolding
# -----------------------------------------------------------------------------

def scaffold_skill(spec: SkillSpec, description: str) -> Path:
    """Create a temp skill directory for the given description."""
    skill_dir = TEST_SKILLS_DIR / spec.name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    frontmatter = (
        "---\n"
        f"name: {spec.name}\n"
        f'description: "{description}"\n'
        'when_to_use: ""\n'
        "---\n\n"
        f"{spec.body}\n"
    )
    skill_path.write_text(frontmatter, encoding="utf-8")
    return skill_path


def generate_fixed_suite(spec: SkillSpec) -> list[TestCase]:
    """
    Generate test queries ONCE using the most neutral description (style A),
    then reuse that same suite across all three styles.
    """
    neutral_desc = spec.styles["A_symptom"]
    skill_path = scaffold_skill(spec, neutral_desc)
    skill = parse_skill(skill_path)
    print(f"  Generating fixed test suite for {spec.name}...", file=sys.stderr)
    cases = generate_tests(skill, N_POSITIVE, N_NEGATIVE, BACKEND)
    return cases


# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------

def run_style_comparison(spec: SkillSpec) -> dict:
    print(f"\n{'=' * 60}\nSkill: {spec.name}\n{'=' * 60}", file=sys.stderr)
    cases = generate_fixed_suite(spec)

    # Save suite to disk for audit
    suite_path = OUTPUT_DIR / "skills" / spec.name / "test_suite.json"
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(
        json.dumps(
            [{"query": c.query, "expect_trigger": c.expect_trigger,
              "category": c.category} for c in cases],
            indent=2
        ),
        encoding="utf-8",
    )

    per_style: dict = {}
    for style_label, description in spec.styles.items():
        print(f"\n-- Style: {style_label} --", file=sys.stderr)
        skill_path = scaffold_skill(spec, description)
        skill = parse_skill(skill_path)
        results = run_suite(cases, skill.name, timeout=TIMEOUT, backend=BACKEND)
        card = score(results)
        print(
            f"  F1 = {card.f1:.2f}  P = {card.precision:.2f}  R = {card.recall:.2f}",
            file=sys.stderr,
        )
        per_style[style_label] = {
            "description": description,
            "f1": card.f1,
            "precision": card.precision,
            "recall": card.recall,
            "tp": card.tp,
            "fp": card.fp,
            "tn": card.tn,
            "fn": card.fn,
            "verdict": card.verdict,
            "failed_queries": [
                {"query": r.case.query,
                 "expected": r.case.expect_trigger,
                 "triggered": r.triggered}
                for r in results if not r.passed and not r.error
            ],
        }
    return {"skill": spec.name, "styles": per_style}


def write_report(all_results: list[dict]) -> None:
    lines = ["# Description-Style Comparison — Results\n"]
    lines.append("## Per-skill F1\n")
    lines.append("| Skill | A (symptom) | B (directive) | C (trigger+excl) |")
    lines.append("|---|---|---|---|")
    for r in all_results:
        a = r["styles"]["A_symptom"]["f1"]
        b = r["styles"]["B_directive"]["f1"]
        c = r["styles"]["C_triggerexcl"]["f1"]
        lines.append(f"| {r['skill']} | {a:.2f} | {b:.2f} | {c:.2f} |")

    # Aggregate
    def mean(key):
        return sum(r["styles"][key]["f1"] for r in all_results) / len(all_results)

    lines.append("")
    lines.append("## Aggregate\n")
    lines.append(f"- Mean F1, Style A (symptom list): {mean('A_symptom'):.2f}")
    lines.append(f"- Mean F1, Style B (directive): {mean('B_directive'):.2f}")
    lines.append(f"- Mean F1, Style C (trigger+excl): {mean('C_triggerexcl'):.2f}")

    wins = {"A_symptom": 0, "B_directive": 0, "C_triggerexcl": 0}
    for r in all_results:
        best_f1 = max(kv[1]["f1"] for kv in r["styles"].items())
        for style, data in r["styles"].items():
            if data["f1"] == best_f1:
                wins[style] += 1
    lines.append("")
    lines.append("## Wins (per-skill max F1)\n")
    lines.append("Ties credit every style at the max F1, so wins may sum above 4.")
    lines.append("")
    for k, v in wins.items():
        lines.append(f"- {k}: {v} / {len(all_results)}")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {REPORT_FILE}", file=sys.stderr)


def main() -> None:
    if TEST_SKILLS_DIR.exists():
        shutil.rmtree(TEST_SKILLS_DIR)
    TEST_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []
    for spec in SKILLS:
        all_results.append(run_style_comparison(spec))

    RESULTS_FILE.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    write_report(all_results)


if __name__ == "__main__":
    main()
