# skill-test Command Reference

Tool for testing whether Claude Code skills automatically trigger on relevant queries. Measures trigger precision, recall, and F1 score.

## What This Tool Does

Given any skill with a `SKILL.md` file (containing a `name:` field in YAML frontmatter), this tool:

1. Parses the skill's name and description
2. Auto-generates positive queries (should trigger the skill) and negative queries (should not)
3. Runs each query through Claude and inspects whether the Skill tool was invoked
4. Scores results as precision/recall/F1 and reports a verdict: OPTIMAL, GOOD, or NEEDS_WORK

## Prerequisites

- Python >= 3.11
- `claude` CLI installed and authenticated (for `--backend cli`, the default)
- `claude-agent-sdk` package installed (for `--backend sdk`)
- The skill under test must be installed in `~/.claude/skills/` as a directory containing `SKILL.md` with a `name:` field in frontmatter

## Installation

```bash
pip install -e .            # core (CLI backend only)
pip install -e ".[sdk]"     # with Agent SDK backend support
```

## Backends

All commands that call Claude accept `--backend cli|sdk`:

| Backend | How it works | Auth | When to use |
|---------|-------------|------|-------------|
| `cli` (default) | Runs `claude -p "query" --output-format json` as a subprocess | Uses existing `claude` CLI auth (OAuth, subscription) | Default. No extra setup needed if `claude` works. |
| `sdk` | Uses `claude_agent_sdk.query()` async API | Uses Claude Code session token or CLI auth | When you want programmatic control or are building on the Agent SDK. |

## Commands

### `skill-test parse <skill_path>`

Parse a SKILL.md and display extracted metadata. No API calls. Use this to verify the tool can read your skill correctly.

**Arguments:**
- `skill_path` — Path to a skill directory (containing `SKILL.md`) or directly to a `.md` file

**Example:**
```bash
skill-test parse ~/.claude/skills/repo-retrospective/
```

**Output:**
```
Name:        repo-retrospective
Path:        /home/user/.claude/skills/repo-retrospective/SKILL.md
Description: Quality assurance for AI onboarding documentation. Analyzes ONBOARD documents...
Triggers:    Quality assurance for AI onboarding documentation, Analyzes ONBOARD documents...
```

### `skill-test generate <skill_path> [options]`

Auto-generate a test suite for a skill by calling Claude to produce diverse positive and negative queries. Saves results to a YAML file for review and editing before running.

**Arguments:**
- `skill_path` — Path to skill directory or SKILL.md

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `tests.yaml` | Output YAML file path |
| `--positive` | `10` | Number of positive queries (should trigger) |
| `--negative` | `5` | Number of negative queries (should not trigger) |
| `--backend` | `cli` | `cli` or `sdk` |

**Example:**
```bash
skill-test generate ~/.claude/skills/my-skill/ -o my-skill-tests.yaml --positive 10 --negative 5
```

**What it does:**
1. Parses the skill's name, description, and body
2. Sends a prompt to Claude asking for N positive and N negative test queries
3. Positive queries: natural user requests that should trigger the skill, varied in phrasing
4. Negative queries: adjacent-domain requests that should NOT trigger it
5. Saves all queries to YAML with `expect_trigger: true|false`

**Output YAML format:**
```yaml
skill:
  name: my-skill
  path: /home/user/.claude/skills/my-skill/SKILL.md
  description: What the skill does...
cases:
- query: "A natural request that should trigger this skill"
  expect_trigger: true
  category: positive
- query: "An adjacent request that should NOT trigger"
  expect_trigger: false
  category: negative
```

You can edit this YAML before running — add cases, remove cases, change expectations.

### `skill-test run <test_suite> [options]`

Execute a saved test suite. Each query is sent to Claude and the output is inspected for Skill tool invocation.

**Arguments:**
- `test_suite` — Path to a YAML test suite file (from `generate` or hand-written)

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--timeout` | `120` | Timeout per query in seconds |
| `--output` | (none) | Write a markdown report to this file path |
| `--backend` | `cli` | `cli` or `sdk` |

**Example:**
```bash
skill-test run my-skill-tests.yaml --timeout 120 --output report.md
```

**What it does per query:**
1. Sends the query to Claude via the chosen backend
2. Inspects the response for a `Skill` tool_use event matching the target skill name
3. Records: triggered (bool), duration, cost, any errors

**Terminal output:**
```
Skill Trigger Test: my-skill
==============================

    # | Expect | Actual |      | Query
  ----+--------+--------+------+------------------------------------------
    1 |  TRIG  |  TRIG  | PASS | Help me review my onboarding docs
    2 |  TRIG  |  SKIP  | FAIL | Check our documentation for gaps
    3 |  SKIP  |  SKIP  | PASS | Write a Python web scraper

  Precision: 0.88  Recall: 0.80  F1: 0.84
  TP: 8  FP: 1  TN: 5  FN: 2
  Verdict: GOOD (target F1 >= 0.90 for OPTIMAL)

  Cost: $0.5823  Time: 300.4s  Errors: 0

  Failures:
    #2 Expected TRIG but SKIP -- "Check our documentation for gaps"
```

### `skill-test quick <skill_path> [options]`

Generate test queries and run them in one step. No intermediate YAML file. Use this for fast evaluation of a skill.

**Arguments:**
- `skill_path` — Path to skill directory or SKILL.md

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--positive` | `10` | Number of positive queries |
| `--negative` | `5` | Number of negative queries |
| `--timeout` | `120` | Timeout per query in seconds |
| `--output` | (none) | Write markdown report to file |
| `--backend` | `cli` | `cli` or `sdk` |

**Example:**
```bash
skill-test quick ~/.claude/skills/repo-retrospective/ --positive 5 --negative 3
```

### `skill-test discover [options]`

List all installed Skill-tool skills (directories containing `SKILL.md` with a `name:` field).

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--skills-dir` | `~/.claude/skills` | Directory to scan |

**Example:**
```bash
skill-test discover
```

**Output:**
```
Found 2 skill(s):

  repo-retrospective
    Quality assurance for AI onboarding documentation...
    /home/user/.claude/skills/repo-retrospective/SKILL.md

  code-review
    Automated code review for pull requests...
    /home/user/.claude/skills/code-review/SKILL.md
```

## Detection Mechanism

When Claude auto-triggers a skill, the JSON output from `claude -p --output-format json` contains an event with this structure inside an `assistant` message:

```json
{
  "type": "tool_use",
  "name": "Skill",
  "input": {
    "skill": "skill-name"
  }
}
```

The runner scans all `assistant` events for a `tool_use` block where `name == "Skill"` and `input.skill` matches the target skill name. This is a binary check — the skill either invoked or it didn't.

When using `--backend sdk`, the same detection applies via `ToolUseBlock` objects in `AssistantMessage.content`.

## Scoring

Results are classified into a standard confusion matrix:

| | Skill triggered | Skill did NOT trigger |
|---|---|---|
| **Should trigger** (positive query) | True Positive (TP) | False Negative (FN) |
| **Should NOT trigger** (negative query) | False Positive (FP) | True Negative (TN) |

Metrics computed:
- **Precision** = TP / (TP + FP) — when it triggers, is it correct?
- **Recall** = TP / (TP + FN) — of queries that should trigger, how many did?
- **F1** = harmonic mean of precision and recall

Verdict thresholds:
| Verdict | F1 Score |
|---------|----------|
| OPTIMAL | >= 0.90 |
| GOOD | >= 0.75 |
| NEEDS_WORK | < 0.75 |

Errored test cases (timeouts, CLI failures) are excluded from scoring.

## Test Suite YAML Format

```yaml
skill:
  name: my-skill                              # required
  path: ~/.claude/skills/my-skill/            # optional (resolves SKILL.md from here)
  description: What the skill does            # optional (read from SKILL.md if path given)

cases:
  - query: "A user request that should trigger"
    expect_trigger: true
    category: positive                        # positive, negative, or edge

  - query: "An unrelated request"
    expect_trigger: false
    category: negative
```

If `path` is provided, the tool parses the SKILL.md there to fill in `name` and `description`. If only `name` is provided, it is used directly for detection matching.

## Typical Workflows

### Evaluate a new skill quickly
```bash
skill-test quick path/to/my-skill/ --positive 10 --negative 5
```

### Generate, review, then run
```bash
skill-test generate path/to/my-skill/ -o tests.yaml --positive 15 --negative 10
# Edit tests.yaml — adjust queries, add edge cases
skill-test run tests.yaml --output report.md
```

### Iterate on a skill description
```bash
# Run test, note low recall
skill-test quick path/to/my-skill/
# Edit SKILL.md description to add more trigger phrases
# Re-run
skill-test quick path/to/my-skill/
```

### Find all testable skills
```bash
skill-test discover
```

## Architecture

```
skill_tester/
├── models.py      # SkillInfo, TestCase, TestResult, ScoreCard dataclasses
├── parser.py      # parse_skill(), load_test_suite(), discover_skills()
├── generator.py   # generate_tests() via CLI or SDK, save_test_suite()
├── runner.py      # run_test(), run_suite() via CLI or SDK
├── scorer.py      # score() — confusion matrix from results
├── reporter.py    # print_report(), write_markdown()
└── __main__.py    # CLI entry point with argparse subcommands
```

### Data Flow

```
parse_skill(path) -> SkillInfo
    |
    v
generate_tests(skill, n_positive, n_negative, backend) -> list[TestCase]
    |
    v
run_suite(cases, target_skill, timeout, backend) -> list[TestResult]
    |
    v
score(results) -> ScoreCard
    |
    v
print_report(skill, results, card)
```

### Key Types

**SkillInfo** — parsed from SKILL.md:
- `name: str` — skill name from frontmatter (used for detection matching)
- `description: str` — skill description from frontmatter
- `path: Path` — filesystem path to the SKILL.md
- `body: str` — markdown content after frontmatter
- `trigger_phrases: list[str]` — extracted from description text

**TestCase** — a single test query:
- `query: str` — the user prompt to send
- `expect_trigger: bool` — True if this query should trigger the skill
- `category: str` — "positive", "negative", or "edge"

**TestResult** — outcome of running one test:
- `case: TestCase` — the original test case
- `triggered: bool` — whether the Skill tool was invoked
- `passed: bool` (property) — `expect_trigger == triggered`
- `duration_ms: int` — API response time
- `cost_usd: float` — API cost for this query
- `error: str | None` — error message if the test errored

**ScoreCard** — aggregate results:
- `tp, fp, tn, fn: int` — confusion matrix counts
- `precision, recall, f1: float` (properties) — computed metrics
- `verdict: str` (property) — "OPTIMAL", "GOOD", or "NEEDS_WORK"

## Costs and Timing

Each test query makes one `claude -p` call (or one Agent SDK `query()` call). Typical costs:
- ~$0.02-0.15 per query depending on response length
- ~30-90 seconds per query (Claude processes the query fully)
- A 15-query suite: ~$0.50-2.00, ~5-15 minutes

The `generate` step makes one additional Claude call to produce the test queries.

## Error Handling

- **Timeout**: If a query exceeds `--timeout` seconds, it is recorded as an error and excluded from scoring
- **CLI not found**: If `claude` is not on PATH, the error is recorded per-test
- **JSON parse failure**: If CLI output isn't valid JSON, the error is recorded
- **SDK exceptions**: Any exception during SDK `query()` is caught and recorded

Errors appear as `ERR` in the results table. They do not count as passes or failures.
