# claude-skill-tester

Automated trigger testing and closed-loop optimization for Claude Code skills. Uses `claude -p` (CLI) or the Claude Agent SDK for all inference -- test generation, skill invocation detection, and frontmatter optimization.

Point it at any SKILL.md. It generates test queries, runs them through Claude, measures whether the skill actually fires, and reports precision/recall/F1. If the score is low, the optimizer rewrites the frontmatter and retests until it converges.

## The mental model

**This is a unit test framework for the fuzzy prompt layer between a user's words and Claude's decision to invoke a skill — with a built-in optimizer that rewrites that prompt until the tests pass.**

Claude picks a skill by semantically matching a user's query against a short paragraph of text (the skill's `description` and `when_to_use` fields). That paragraph is the only lever you have. This tool treats it like code: generate tests, run them, score the results, and if the score is low, rewrite the paragraph and try again.

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
| `skill-test collide <paths...>` | Test for trigger collisions between 2+ skills |

### Which command to reach for

- **Just want a score?** → `quick`
- **Want to edit tests before running?** → `generate`, then `run`
- **Score is low and you want it fixed automatically?** → `optimize`
- **Something feels off with the frontmatter and you want a sanity check?** → `parse`
- **Want to see all your skills at a glance?** → `discover` (list) or `landscape` (list + budget + health)
- **Two skills you suspect are stealing each other's queries?** → `collide`

All commands that call Claude accept `--backend auto|sdk|cli|api` (default: `auto`, which tries sdk -> cli -> api).

> **Heads up on `--backend api`:** Detecting "did the skill fire?" requires the Claude Code runtime. The `api` backend can generate queries and propose rewrites, but test runs silently fall back to `cli` for the actual trigger detection step. If you want to run fully headless from an API key alone, you can't — you need either the CLI or the SDK available for the detection step.

## Optimizer

```bash
skill-test optimize ~/.claude/skills/my-skill/ --max-rounds 3 --dry-run
```

Each round:
1. Generates fresh test queries from the current description
2. Merges in regression cases from prior round failures
3. Runs the suite, scores F1
4. If below target: analyzes false negatives/positives, reads the skill body for grounding, calls Claude to rewrite `description` + `when_to_use`, writes to SKILL.md, loops

Two anti-cheating tricks make this loop honest rather than just a hill climb:

- **Failed queries carry forward as mandatory regression tests.** The optimizer can't narrow the description to dodge old failures — it must *generalize* to handle them alongside new ones. Without this, the easiest way to pass a test is to redefine the skill to match it; with this, every past failure stays in the suite permanently.
- **Rewrites are grounded in the skill body.** The optimizer reads up to 2000 chars of what the skill actually does before rewriting, so it can't promise capabilities the skill doesn't have. You don't get a polished description for a skill that can't back it up.

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

## Collision Testing

F1 measures a skill in isolation. But in production, skills aren't alone — they compete for every query. A skill can score OPTIMAL on its own and still lose 40% of its queries to a neighboring skill whose trigger surface overlaps.

That's the gap `collide` fills. Use F1 first to get each skill working individually, then use `collide` to check whether they still behave when deployed together.

```bash
skill-test collide ~/.claude/skills/skill-a/ ~/.claude/skills/skill-b/ --clear 5 --boundary 5
```

For each pair, it generates clear queries (obviously for one skill) and boundary queries (ambiguous), then runs them and checks which skills fire.

```
Collision Test: skill-a vs skill-b
==========================================

    # |   Type    | Intended             | Fired                     | Result
  ----+-----------+----------------------+---------------------------+--------
    1 |  clear-a  | skill-a              | skill-a                   | CORRECT
    2 |  clear-b  | skill-b              | skill-a                   | STOLEN
    3 | boundary  | skill-a              | skill-a, skill-b          | SHARED

  Theft rate: 10%  Boundary agreement: 50%  Verdict: LOW
```

Verdicts: CLEAN (0% theft), LOW (<=15%), MODERATE (<=35%), HIGH_COLLISION (>35%).

## Scoring

Standard confusion matrix. Verdicts:

| Verdict | F1 |
|---------|----|
| OPTIMAL | >= 0.90 |
| GOOD | >= 0.75 |
| NEEDS_WORK | < 0.75 |

See [F1_SCORING.md](F1_SCORING.md) for a full walkthrough: the formulas, a worked example, why F1 is preferred over accuracy for this problem, and how it differs from collision testing.

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
  models.py      # SkillInfo, TestCase, TestResult, ScoreCard, HealthCheck, FrontmatterHealth, Collision*
  parser.py      # SKILL.md parsing, frontmatter rewriting, skill discovery
  generator.py   # test query generation via CLI or Agent SDK
  runner.py      # query execution + Skill tool_use detection + rival capture
  scorer.py      # precision/recall/F1 from results
  health.py      # static frontmatter analysis (budget, redundancy, field checks)
  diagnose.py    # failure diagnostics (rival identification, semantic gap analysis)
  reporter.py    # terminal and markdown reporting
  optimizer.py   # closed-loop frontmatter optimizer with body-grounded rewrites and diagnostic context
  collider.py    # cross-skill collision testing
  __main__.py    # CLI entry point
```

See [COMMAND_REFERENCE.md](COMMAND_REFERENCE.md) for full API documentation.

## License

MIT
