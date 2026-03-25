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
- At least one backend available (see Backends below)
- The skill under test must be installed in `~/.claude/skills/` as a directory containing `SKILL.md` with a `name:` field in frontmatter

## Installation

```bash
pip install -e .            # core (CLI backend only)
pip install -e ".[sdk]"     # + Claude Agent SDK backend
pip install -e ".[api]"     # + Anthropic API key backend
pip install -e ".[all]"     # all backends
```

## Backends

All commands that call Claude accept `--backend auto|sdk|cli|api`:

| Backend | How it works | Auth |
|---------|-------------|------|
| `auto` (default) | Tries sdk -> cli -> api in order | Uses first available |
| `sdk` | `claude_agent_sdk.query()` async API | Claude Code session token |
| `cli` | `claude -p "query" --output-format json` subprocess | Claude CLI auth (OAuth, subscription) |
| `api` | Anthropic Python SDK directly | `ANTHROPIC_API_KEY` env var |

Trigger detection (the "did the skill fire?" check) requires the Claude Code runtime. When `--backend api` is selected, inference (test generation, optimization) uses the API, but test runs fall back to `cli`.

When using `--backend sdk`, trigger detection uses `ToolUseBlock` objects in `AssistantMessage.content`.

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
Name:         repo-retrospective
Path:         /home/user/.claude/skills/repo-retrospective/SKILL.md
Description:  Quality assurance for AI onboarding documentation. Analyzes ONBOARD documents...
Triggers:     Quality assurance for AI onboarding documentation, Analyzes ONBOARD documents...

Frontmatter health: IMPROVABLE  (194 chars, 1.2% of budget)
  WARN: [W1] No when_to_use field. Adding trigger phrases and exclusions...
```

Health checks run automatically with no API calls. See [Frontmatter Health Checks](#frontmatter-health-checks) for details.

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
| `--backend` | `auto` | `auto`, `sdk`, `cli`, or `api` |

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
| `--backend` | `auto` | `auto`, `sdk`, `cli`, or `api` |
| `--diagnose` | off | Diagnose failures: identify rival skills and explain semantic gaps |

**Example:**
```bash
skill-test run my-skill-tests.yaml --timeout 120 --output report.md
skill-test run my-skill-tests.yaml --diagnose  # includes failure explanations
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
| `--backend` | `auto` | `auto`, `sdk`, `cli`, or `api` |
| `--diagnose` | off | Diagnose failures: identify rival skills and explain semantic gaps |

**Example:**
```bash
skill-test quick ~/.claude/skills/repo-retrospective/ --positive 5 --negative 3
skill-test quick ~/.claude/skills/my-skill/ --diagnose  # includes failure explanations
```

### `skill-test optimize <skill_path> [options]`

Closed-loop optimizer. Tests the skill, analyzes failures, rewrites the `description` and `when_to_use` frontmatter fields, retests, and iterates until the target F1 is reached or rounds are exhausted.

Three frontmatter fields together determine whether Claude invokes a skill:
- `name` — the skill identifier
- `description` — what it does and when to use it (max 1024 chars)
- `when_to_use` — detailed trigger conditions, phrases, and exclusions

The optimizer rewrites `description` and `when_to_use` each round. It analyzes the `name` but does not auto-rename (suggests only).

**Arguments:**
- `skill_path` — Path to skill directory or SKILL.md

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--target-f1` | `0.90` | F1 score to reach before stopping |
| `--max-rounds` | `5` | Maximum optimization rounds |
| `--positive` | `10` | Positive queries generated per round |
| `--negative` | `5` | Negative queries generated per round |
| `--timeout` | `120` | Timeout per query in seconds |
| `--backend` | `auto` | `auto`, `sdk`, `cli`, or `api` |
| `--dry-run` | off | Show proposed changes without writing to SKILL.md |
| `--output` | (none) | Write optimization report to file |
| `--no-diagnose` | off | Disable failure diagnostics (on by default for optimize) |

**Example:**
```bash
# Dry run — see what would change
skill-test optimize ~/.claude/skills/my-skill/ --dry-run

# Live optimization
skill-test optimize ~/.claude/skills/my-skill/ --max-rounds 3 --target-f1 0.90
```

**How each round works:**
1. Generate fresh test queries from the current description
2. Merge in regression cases (all false negatives/positives from prior rounds)
3. Run the suite, compute F1
4. If F1 >= target: stop (converged)
5. Analyze failures: collect FN queries (should trigger but didn't) and FP queries (shouldn't trigger but did)
6. Call Claude with the full trigger surface (name + description + when_to_use) plus failure analysis
7. Claude proposes improved `description` + `when_to_use` (and optionally a name suggestion)
8. Write the updated frontmatter to SKILL.md (backup created on first round as `SKILL.md.bak`)
9. Re-parse and loop

**Anti-overfitting:** Fresh test cases are generated each round from the new description, but all previous failures are carried forward as mandatory regression tests. The optimizer can't narrow the description to dodge old failures.

**Output:**
```
Optimization: my-skill (CONVERGED)
Target: F1 >= 0.90
==================================================

Round 1: F1 = 0.67 NEEDS_WORK
  FN (3): "Review our AI documentation", "Check docs for gaps", ...
  FP (1): "Do a sprint retrospective"

Round 2: F1 = 0.87 GOOD  [+0.20]
  FN (1): "Verify onboard accuracy against code"
  FP (0): none
  Regression cases: 4

Round 3: F1 = 0.93 OPTIMAL  [+0.06]

Frontmatter changes:
  name: my-skill
  description:
    BEFORE: "Original description text..."
    AFTER:  "Improved description with trigger phrases..."
  when_to_use:
    BEFORE: (not set)
    AFTER:  "Triggers: 'review docs', 'audit files'. Do NOT use for: ..."
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

  repo-retrospective [IMPROVABLE]
    Quality assurance for AI onboarding documentation...
    /home/user/.claude/skills/repo-retrospective/SKILL.md

  code-review [HEALTHY]
    Automated code review for pull requests...
    /home/user/.claude/skills/code-review/SKILL.md
```

### `skill-test landscape [options]`

Analyze the full skill ecosystem: context budget consumption, frontmatter health, and structural issues. No API calls. Use this to understand how your skills compete for Claude's context budget.

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--skills-dir` | `~/.claude/skills` | Directory to scan |
| `--budget` | `16000` | Context budget in chars (override if context window differs) |

**Example:**
```bash
skill-test landscape
```

**Output:**
```
Skill Landscape (12 skills, 4,832 / 16,000 chars = 30.2%)
======================================================================

    # | Name                           | Chars | Budget | Health
  ----+--------------------------------+-------+--------+--------
    1 | repo-retrospective             |   194 |  1.2%  | IMPROVABLE
    2 | code-review                    |   312 |  2.0%  | HEALTHY
   ...

Health issues:
  repo-retrospective:
    WARN: [W1] No when_to_use field. Adding trigger phrases and exclusions...

Budget: 4,832 / 16,000 chars (30.2%)
  Largest: code-review (312 chars, 2.0%)
  Grades: 10 healthy, 2 improvable, 0 broken
```

## Frontmatter Health Checks

Static analysis of skill frontmatter quality. Runs automatically during `parse`, `quick`, `optimize`, and `landscape` with no API calls. This is separate from the F1-based trigger verdict — a skill can score OPTIMAL on F1 while having broken frontmatter.

### Health Grades

| Grade | Meaning |
|-------|---------|
| HEALTHY | No structural issues found |
| IMPROVABLE | Warnings — functional but suboptimal |
| BROKEN | Errors — frontmatter won't work as intended |

### Checks

| Code | Level | What it detects |
|------|-------|-----------------|
| E1 | ERROR | `when-to-use` (hyphenated) — silently ignored by Claude. Must use `when_to_use` (underscore) |
| E2 | ERROR | `description` exceeds 1024 characters — may be truncated |
| W1 | WARN | Missing `when_to_use` — leaves a second independent trigger surface unused |
| W2 | WARN | High redundancy (>60%) between `description` and `when_to_use` — wastes budget |
| W3 | WARN | Skill consumes >5% of ~16K context budget — budget pressure risk |
| I1 | INFO | `description` and `when_to_use` are complementary (<30% overlap) — optimal |

See [SKILL_FRONTMATTER.md](SKILL_FRONTMATTER.md) for the empirical research on which frontmatter fields Claude loads and how they influence skill selection.

## Failure Diagnostics

When `--diagnose` is enabled (or by default during `optimize`), the tool runs a post-test diagnostic pass on failures:

**Rival capture (free — no API calls):** When a test query fails, the tool checks the existing event stream for which other skill (if any) fired instead. This transforms "query didn't trigger" into "query was intercepted by `explain-code`."

**Diagnostic queries (one API call per failure):** For each false negative and false positive, the tool asks Claude to explain the semantic gap between the query and the skill's frontmatter. The explanation identifies missing keywords, overly broad terms, or rival skill conflicts.

**Output format:**
```
  Failures:
    #2 Expected TRIG but SKIP -- "Check our documentation for gaps"
         Rival: explain-code
         Reason: Description focuses on "onboarding" but query is about "documentation"...
    #7 Expected SKIP but TRIG -- "Do a sprint retrospective"
         Reason: Description contains "retrospective" which matched too broadly...
```

During optimization, diagnostic context is fed directly into the improvement prompt, enabling the optimizer to make targeted fixes rather than guessing.

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

### Auto-optimize a skill's trigger accuracy
```bash
# Preview what the optimizer would change
skill-test optimize path/to/my-skill/ --dry-run

# Run live optimization (rewrites SKILL.md, creates .bak backup)
skill-test optimize path/to/my-skill/ --max-rounds 3 --target-f1 0.90
```

### Find all testable skills
```bash
skill-test discover
```

## Architecture

```
skill_tester/
├── models.py      # SkillInfo, TestCase, TestResult, ScoreCard, HealthCheck, FrontmatterHealth
├── parser.py      # parse_skill(), load_test_suite(), discover_skills(), rewrite_frontmatter()
├── generator.py   # generate_tests() via CLI or SDK, save_test_suite()
├── runner.py      # run_test(), run_suite() via CLI or SDK, rival capture
├── scorer.py      # score() — confusion matrix from results
├── health.py      # check_frontmatter() — static frontmatter analysis
├── diagnose.py    # diagnose_failures() — post-run semantic gap analysis
├── reporter.py    # print_report(), write_markdown(), print_health(), print_landscape()
├── optimizer.py   # optimize_skill() — closed-loop optimizer with diagnostic context
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
- `when_to_use: str` — trigger conditions from frontmatter `when_to_use` field
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

**FrontmatterHealth** — static frontmatter analysis:
- `skill_name: str` — the skill being analyzed
- `context_cost: int` — characters consumed in Claude's context budget
- `budget_pct: float` — percentage of ~16K budget
- `has_when_to_use: bool` — whether `when_to_use` field is present
- `has_hyphenated_when_to_use: bool` — whether broken `when-to-use` is present
- `redundancy_score: float` — Jaccard similarity between description and when_to_use
- `checks: list[HealthCheck]` — individual check results
- `grade: str` (property) — "HEALTHY", "IMPROVABLE", or "BROKEN"

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
