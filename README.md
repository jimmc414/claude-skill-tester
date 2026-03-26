# claude-skill-tester

Automated trigger testing and closed-loop optimization for Claude Code skills. Uses `claude -p` (CLI) or the Claude Agent SDK for all inference -- test generation, skill invocation detection, and frontmatter optimization.

Point it at any SKILL.md. It generates test queries, runs them through Claude, measures whether the skill actually fires, and reports precision/recall/F1. If the score is low, the optimizer rewrites the frontmatter and retests until it converges.

## The problem

Claude Code skills have a cold start problem. You write a SKILL.md with a description, deploy it, and then hope Claude invokes it at the right time. There's no feedback loop. You discover undertriggering when users complain, and overtriggering when the skill hijacks unrelated conversations. Both are invisible until they happen in production.

Anthropic's own guidance is: "Run 10-20 test queries that should trigger your skill. Track how many times it loads automatically vs. requires explicit invocation." This tool automates that test and takes it further -- when failures are found, it fixes them.

## How it works

Three YAML frontmatter fields determine whether Claude invokes a skill:

```yaml
name: my-skill                    # identity, contributes to semantic matching
description: What it does...      # primary trigger text (max 1024 chars)
when_to_use: Trigger conditions...# additional trigger phrases and exclusions
```

All inference runs through one of three backends. The default (`auto`) tries them in order:

1. **`sdk`** -- Claude Agent SDK (`claude_agent_sdk.query()`). Preferred when available.
2. **`cli`** -- `claude -p "query" --output-format json`. Uses existing CLI auth (OAuth/subscription).
3. **`api`** -- Anthropic Python SDK with `ANTHROPIC_API_KEY` env var. No CLI or OAuth required.

Override with `--backend sdk|cli|api` to force a specific one.

All three backends are used for test query generation and optimization rewrites. Trigger detection (the actual "did the skill fire?" check) requires the Claude Code runtime, so `run` and the test phase of `quick`/`optimize` always use `sdk` or `cli` -- even when `api` is selected for inference.

The optimizer treats `description` + `when_to_use` as a prompt to be optimized against a test suite with regression protection. It reads the skill body (up to 2000 chars) so rewrites stay grounded in what the skill actually does. When failures occur, it captures which rival skill intercepted the query and runs diagnostic queries to explain the semantic gap — transforming optimization from blind hill climbing to informed correction.

## Quick start

```bash
git clone https://github.com/jimmc414/claude-skill-tester.git
cd claude-skill-tester
pip install -e .            # CLI backend (default)
pip install -e ".[sdk]"     # + Agent SDK backend
pip install -e ".[api]"     # + Anthropic API key backend
pip install -e ".[all]"     # all backends

# Test a skill
skill-test quick ~/.claude/skills/my-skill/

# Optimize a skill
skill-test optimize ~/.claude/skills/my-skill/ --target-f1 0.90
```

Requires Python 3.11+ and the `claude` CLI installed and authenticated.

## Commands

| Command | What it does |
|---------|-------------|
| `skill-test parse <path>` | Parse SKILL.md, display name/description/when_to_use + health check |
| `skill-test generate <path>` | Auto-generate positive + negative test queries to YAML |
| `skill-test run <tests.yaml>` | Execute a test suite, report precision/recall/F1 |
| `skill-test quick <path>` | Generate + run in one step (with health preamble) |
| `skill-test optimize <path>` | Closed-loop: test, diagnose failures, rewrite frontmatter, retest |
| `skill-test discover` | List all installed Skill-tool skills with health grades |
| `skill-test landscape` | Analyze skill ecosystem: budget consumption, health checks |

All commands that call Claude accept `--backend auto|sdk|cli|api` (default: `auto`, which tries sdk -> cli -> api).

## Optimizer

```bash
skill-test optimize ~/.claude/skills/my-skill/ --max-rounds 3 --dry-run
```

Each round:
1. Generates fresh test queries from the current description
2. Merges in regression cases from prior round failures
3. Runs the suite, scores F1
4. If below target: analyzes false negatives/positives, reads the skill body for grounding, calls Claude to rewrite `description` + `when_to_use`, writes to SKILL.md, loops

Failed queries carry forward as mandatory regression tests. The optimizer can't narrow the description to dodge old failures -- it must generalize.

Backup is created on first round (`SKILL.md.bak`). Use `--dry-run` to preview changes without writing.

```
Round 1: F1 = 0.67 NEEDS_WORK
  FN (3): "Review our AI documentation", "Check docs for gaps", ...
  FP (1): "Do a sprint retrospective"

Round 2: F1 = 0.87 GOOD  [+0.20]
  Regressions: 4/4 passing

Round 3: F1 = 0.93 OPTIMAL  [+0.06]
  Converged.
```

## Scoring

Standard confusion matrix. Verdicts:

| Verdict | F1 |
|---------|----|
| OPTIMAL | >= 0.90 |
| GOOD | >= 0.75 |
| NEEDS_WORK | < 0.75 |

## Test suite format

Auto-generated by `skill-test generate`, or write by hand:

```yaml
skill:
  path: ~/.claude/skills/my-skill/

cases:
  - query: "Analyze my onboarding docs for gaps"
    expect_trigger: true
    category: positive

  - query: "Help me write a Python web scraper"
    expect_trigger: false
    category: negative
```

## Frontmatter health checks

`parse`, `quick`, `optimize`, and `landscape` run static analysis on skill frontmatter (no API calls). This catches structural issues that F1 scoring cannot detect.

| Grade | Meaning |
|-------|---------|
| HEALTHY | No structural issues |
| IMPROVABLE | Warnings — functional but suboptimal |
| BROKEN | Errors — frontmatter won't work as intended |

Checks include: missing `when_to_use`, hyphenated `when-to-use` (silently ignored by Claude), description exceeding 1024 chars, high redundancy between fields, and budget pressure. See [SKILL_FRONTMATTER.md](SKILL_FRONTMATTER.md) for empirical findings on which fields Claude loads.

## Project structure

```
skill_tester/
  models.py      # SkillInfo, TestCase, TestResult, ScoreCard, HealthCheck, FrontmatterHealth
  parser.py      # SKILL.md parsing, frontmatter rewriting, skill discovery
  generator.py   # test query generation via CLI or Agent SDK
  runner.py      # query execution + Skill tool_use detection + rival capture
  scorer.py      # precision/recall/F1 from results
  health.py      # static frontmatter analysis (budget, redundancy, field checks)
  diagnose.py    # failure diagnostics (rival identification, semantic gap analysis)
  reporter.py    # terminal and markdown reporting
  optimizer.py   # closed-loop frontmatter optimizer with body-grounded rewrites and diagnostic context
  __main__.py    # CLI entry point
```

See [COMMAND_REFERENCE.md](COMMAND_REFERENCE.md) for full API documentation.

## License

MIT
