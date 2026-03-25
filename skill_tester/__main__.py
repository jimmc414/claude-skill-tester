from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__

_BACKEND_HELP = 'Backend: "cli" uses claude -p, "sdk" uses Claude Agent SDK (default: cli)'


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="skill-test",
        description="Test battery for Claude skill trigger accuracy",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    # parse
    p_parse = sub.add_parser("parse", help="Display parsed skill info")
    p_parse.add_argument("skill_path", type=Path, help="Path to skill directory or SKILL.md")

    # generate
    p_gen = sub.add_parser("generate", help="Auto-generate test queries")
    p_gen.add_argument("skill_path", type=Path, help="Path to skill directory or SKILL.md")
    p_gen.add_argument("-o", "--output", type=Path, default=Path("tests.yaml"), help="Output YAML path")
    p_gen.add_argument("--positive", type=int, default=10, help="Number of positive queries")
    p_gen.add_argument("--negative", type=int, default=5, help="Number of negative queries")
    p_gen.add_argument("--backend", choices=["cli", "sdk"], default="cli", help=_BACKEND_HELP)

    # run
    p_run = sub.add_parser("run", help="Execute a saved test suite")
    p_run.add_argument("test_suite", type=Path, help="Path to test suite YAML")
    p_run.add_argument("--timeout", type=int, default=120, help="Timeout per query in seconds")
    p_run.add_argument("--output", type=Path, help="Write markdown report to file")
    p_run.add_argument("--backend", choices=["cli", "sdk"], default="cli", help=_BACKEND_HELP)

    # quick
    p_quick = sub.add_parser("quick", help="Generate + run in one step")
    p_quick.add_argument("skill_path", type=Path, help="Path to skill directory or SKILL.md")
    p_quick.add_argument("--positive", type=int, default=10, help="Number of positive queries")
    p_quick.add_argument("--negative", type=int, default=5, help="Number of negative queries")
    p_quick.add_argument("--timeout", type=int, default=120, help="Timeout per query in seconds")
    p_quick.add_argument("--output", type=Path, help="Write markdown report to file")
    p_quick.add_argument("--backend", choices=["cli", "sdk"], default="cli", help=_BACKEND_HELP)

    # optimize
    p_opt = sub.add_parser("optimize", help="Optimize skill frontmatter for trigger accuracy")
    p_opt.add_argument("skill_path", type=Path, help="Path to skill directory or SKILL.md")
    p_opt.add_argument("--target-f1", type=float, default=0.90, help="Target F1 score (default: 0.90)")
    p_opt.add_argument("--max-rounds", type=int, default=5, help="Maximum optimization rounds (default: 5)")
    p_opt.add_argument("--positive", type=int, default=10, help="Positive queries per round")
    p_opt.add_argument("--negative", type=int, default=5, help="Negative queries per round")
    p_opt.add_argument("--timeout", type=int, default=120, help="Timeout per query in seconds")
    p_opt.add_argument("--backend", choices=["cli", "sdk"], default="cli", help=_BACKEND_HELP)
    p_opt.add_argument("--dry-run", action="store_true", help="Show proposed changes without writing")
    p_opt.add_argument("--output", type=Path, help="Write optimization report to markdown file")

    # discover
    p_disc = sub.add_parser("discover", help="List installed Skill-tool skills")
    p_disc.add_argument("--skills-dir", type=Path, help="Skills directory (default: ~/.claude/skills)")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "parse":
        _cmd_parse(args)
    elif args.command == "generate":
        _cmd_generate(args)
    elif args.command == "run":
        _cmd_run(args)
    elif args.command == "quick":
        _cmd_quick(args)
    elif args.command == "optimize":
        _cmd_optimize(args)
    elif args.command == "discover":
        _cmd_discover(args)


def _cmd_parse(args: argparse.Namespace) -> None:
    from .parser import parse_skill

    skill = parse_skill(args.skill_path)
    print(f"Name:        {skill.name}")
    print(f"Path:        {skill.path}")
    print(f"Description: {skill.description}")
    if skill.trigger_phrases:
        print(f"Triggers:    {', '.join(skill.trigger_phrases)}")


def _cmd_generate(args: argparse.Namespace) -> None:
    from .generator import generate_tests, save_test_suite
    from .parser import parse_skill

    skill = parse_skill(args.skill_path)
    print(f"Generating tests for: {skill.name} (backend: {args.backend})", file=sys.stderr)
    print(f"  {args.positive} positive + {args.negative} negative queries", file=sys.stderr)

    cases = generate_tests(skill, n_positive=args.positive, n_negative=args.negative, backend=args.backend)
    save_test_suite(skill, cases, args.output)

    print(f"Saved {len(cases)} test cases to {args.output}", file=sys.stderr)
    for c in cases:
        tag = "+" if c.expect_trigger else "-"
        print(f"  [{tag}] {c.query}")


def _cmd_run(args: argparse.Namespace) -> None:
    from .parser import load_test_suite
    from .reporter import print_report, write_markdown
    from .runner import run_suite
    from .scorer import score

    skill, cases = load_test_suite(args.test_suite)
    print(f"Running {len(cases)} tests for skill: {skill.name} (backend: {args.backend})\n", file=sys.stderr)

    results = run_suite(cases, skill.name, timeout=args.timeout, backend=args.backend)
    card = score(results)
    print_report(skill, results, card)

    if args.output:
        write_markdown(args.output, skill, results, card)
        print(f"Report written to {args.output}", file=sys.stderr)


def _cmd_quick(args: argparse.Namespace) -> None:
    from .generator import generate_tests
    from .parser import parse_skill
    from .reporter import print_report, write_markdown
    from .runner import run_suite
    from .scorer import score

    skill = parse_skill(args.skill_path)
    print(f"Generating tests for: {skill.name} (backend: {args.backend})", file=sys.stderr)
    cases = generate_tests(skill, n_positive=args.positive, n_negative=args.negative, backend=args.backend)

    print(f"\nRunning {len(cases)} tests...\n", file=sys.stderr)
    results = run_suite(cases, skill.name, timeout=args.timeout, backend=args.backend)
    card = score(results)
    print_report(skill, results, card)

    if args.output:
        write_markdown(args.output, skill, results, card)
        print(f"Report written to {args.output}", file=sys.stderr)


def _cmd_optimize(args: argparse.Namespace) -> None:
    from .optimizer import optimize_skill
    from .reporter import print_optimization_report

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"Optimizing skill ({mode}, target F1 >= {args.target_f1}, max {args.max_rounds} rounds)", file=sys.stderr)

    result = optimize_skill(
        skill_path=args.skill_path,
        target_f1=args.target_f1,
        max_rounds=args.max_rounds,
        n_positive=args.positive,
        n_negative=args.negative,
        timeout=args.timeout,
        backend=args.backend,
        dry_run=args.dry_run,
    )
    print_optimization_report(result)

    if args.output:
        from .reporter import write_markdown
        # Write a summary markdown
        with open(args.output, "w") as f:
            print_optimization_report(result, file=f)
        print(f"Report written to {args.output}", file=sys.stderr)


def _cmd_discover(args: argparse.Namespace) -> None:
    from .parser import discover_skills

    skills = discover_skills(args.skills_dir)
    if not skills:
        print("No Skill-tool skills found.")
        return

    print(f"Found {len(skills)} skill(s):\n")
    for s in skills:
        desc = s.description[:80] + "..." if len(s.description) > 80 else s.description
        print(f"  {s.name}")
        print(f"    {desc}")
        print(f"    {s.path}\n")


if __name__ == "__main__":
    main()
