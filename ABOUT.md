# About

## What this is

An eval harness for Claude Code skill trigger accuracy with a closed-loop optimizer that rewrites skill frontmatter until the skill fires reliably. All inference -- test generation, trigger detection, and optimization rewrites -- runs through `claude -p` (CLI) or the Claude Agent SDK. No direct Anthropic API key required.

## Why it exists

Claude Code skills are essentially prompts that get conditionally loaded into context. The loading decision is made by matching a user's query against three YAML frontmatter fields: `name`, `description`, and `when_to_use`. This is prompt routing, and like all prompt engineering, it's trial-and-error without measurement.

The [Anthropic skill guide](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf) recommends testing trigger accuracy manually: "Run 10-20 test queries that should trigger your skill. Track how many times it loads automatically." Nobody does this. And if they did, the feedback loop from "this query failed" to "here's a better description" requires understanding how Claude interprets skill metadata -- which is opaque.

This tool makes it mechanical. Point it at a SKILL.md and get an F1 score. If the score is bad, the optimizer rewrites the frontmatter and retries until it converges.

## How it actually works

Every step uses Claude for inference via one of two backends (`--backend cli` or `--backend sdk`):

- **`cli`**: shells out to `claude -p "query" --output-format json`. Authenticates via your existing Claude CLI session (OAuth, subscription). Default.
- **`sdk`**: calls `claude_agent_sdk.query()` directly. Authenticates via Claude Code session tokens. Useful for programmatic integration.

No raw Anthropic API key is needed for either path. The same backend choice applies to test generation, trigger detection, and optimization rewrites.

**Detection.** Send a query via the chosen backend. Parse the response event stream. Look for `{"type": "tool_use", "name": "Skill", "input": {"skill": "target-name"}}`. Binary. No heuristics, no content matching, no vibes.

**Test generation.** Feed the skill's `description` and `body` to Claude (via the same backend) and ask for N queries that should trigger it and M that shouldn't. The queries are diverse (paraphrased, indirect, domain-specific) because the generation prompt explicitly asks for variation. Save to YAML for review.

**Scoring.** Standard information retrieval metrics. Precision (when it triggers, is it right?), recall (of things that should trigger, how many did?), F1 (harmonic mean). Verdict thresholds: OPTIMAL >= 0.90, GOOD >= 0.75, NEEDS_WORK < 0.75.

**Optimization.** This is the interesting part. The optimizer runs the test battery, collects false negatives (should have triggered, didn't) and false positives (shouldn't have triggered, did), then asks Claude to rewrite `description` and `when_to_use` to fix them. The rewritten frontmatter is applied to SKILL.md and the battery runs again. Failed queries from prior rounds accumulate as regression tests, so the optimizer can't overfit by narrowing the description to dodge old failures.

The three fields that matter are `name` (analyzed but not auto-renamed), `description` (rewritten each round, max 1024 chars), and `when_to_use` (rewritten each round, no hard limit). Together they form the prompt that Claude reads in its system prompt to decide "should I invoke this skill?"

## What's novel

Most prompt optimization frameworks (DSPy, TextGrad, etc.) optimize prompts against task accuracy. This optimizes a routing decision -- not "does the skill produce good output" but "does the skill get loaded at all." It's the difference between optimizing a function's implementation and optimizing its dispatch.

The regression protection is important. Without it, the optimizer can improve recall by broadening the description (matching more queries) at the cost of precision (triggering on irrelevant queries). Carrying forward all prior false positives and false negatives as mandatory regression cases forces monotonic improvement across the full test surface.

The tool is also fully generic. It reads the SKILL.md, generates test cases from whatever description it finds, and optimizes from there. No per-skill configuration. No hardcoded test cases. You can point it at any skill you've never seen before and get a score.

## Architecture in 30 seconds

~1100 lines of Python. No frameworks. `pyyaml` for parsing, subprocess for `claude -p`, optional `claude-agent-sdk` for the SDK backend. Seven modules: parser, generator, runner, scorer, reporter, optimizer, CLI. Dataclasses for types. `pytest` for tests. The core detection is 6 lines of JSON traversal. The optimization loop is the only complex part and it's a straightforward generate-test-analyze-rewrite cycle.

## Limitations

- Each test query requires a full `claude -p` invocation (~30-90s, ~$0.02-0.15). A 15-query suite takes 5-15 minutes and costs $0.50-2.00. The optimizer multiplies this by the number of rounds.
- The optimizer rewrites frontmatter but cannot restructure the skill body. If the skill's instructions are bad, triggering correctly won't help.
- Test generation uses Claude, so the test queries are only as creative as the model. Edge cases you'd think of as a domain expert may not be generated.
- Detection only works for Skill-tool skills (directory-based, with `name:` in frontmatter). File-based skills loaded via context injection are not detectable by this method.
- The optimizer can't control what other skills are active simultaneously. Cross-skill interference (two skills competing for the same query) is not tested.
