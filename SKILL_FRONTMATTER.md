# Skill Frontmatter: What Claude Actually Sees

Empirical findings on which SKILL.md frontmatter fields are loaded into Claude's
context window for skill matching and auto-invocation. Tested on Claude Code 2.1.83
(March 2025).

## Key Finding

Exactly **three** frontmatter fields are loaded into context at session start:

| Field | Loaded | Format in context |
|-------|--------|-------------------|
| `name` | Yes | Prefix before `:` |
| `description` | Yes | After the `:` |
| `when_to_use` | Yes | Appended with ` - ` separator |

All other fields — including `when-to-use` (hyphenated), `trigger_phrases`,
`keywords`, `tags`, `category`, `aliases` — are **invisible** to Claude and
cannot influence skill selection.

## Context Format

Claude sees each skill as a single line in a system-reminder block:

```
- skill-name: {description} - {when_to_use}
```

When `when_to_use` is absent:

```
- skill-name: {description}
```

## `when_to_use` vs `when-to-use`

Only the **underscore** variant works:

| Field name | Loaded? |
|------------|---------|
| `when_to_use` | Yes |
| `when-to-use` | No — silently ignored |

This is inconsistent with standard Claude Code frontmatter fields (which use
hyphens: `disable-model-invocation`, `user-invocable`, `allowed-tools`), but
`when_to_use` is itself undocumented, so there is no official convention to
follow.

## `when_to_use` Drives Triggering Independently

`when_to_use` is not merely supplementary — it can trigger a skill entirely on
its own. In testing, a skill with a generic `description` ("A generic utility
skill with no specific trigger words") triggered correctly when the query matched
only the `when_to_use` text.

This means `description` and `when_to_use` function as **two independent trigger
surfaces**. A query matching either one can cause Claude to invoke the skill.

## Implications for Skill Authors

1. **Use both fields.** `description` for what the skill does; `when_to_use` for
   specific trigger phrases, user intent patterns, and exclusions.

2. **Don't rely on undocumented fields.** Fields like `keywords`,
   `trigger_phrases`, or `tags` are never loaded — putting trigger words there
   has zero effect.

3. **Use underscores, not hyphens** for `when_to_use`. The hyphenated form is
   silently dropped.

4. **Budget awareness.** Both `description` and `when_to_use` consume space in
   the skill description budget (~2% of context window, ~16K chars fallback).
   Longer `when_to_use` text competes with other skills for this budget.

## Implications for This Tool

The optimizer correctly targets both `description` and `when_to_use` since both
are loaded and influence matching. The context format
(`name: description - when_to_use`) means the two fields are concatenated — there
is no structural boundary between them from Claude's perspective, just a ` - `
separator.

## Documentation Gap

The official Claude Code documentation ([skills page](https://code.claude.com/docs/skills))
does not list `when_to_use` in the frontmatter reference table. The documented
fields are: `name`, `description`, `argument-hint`, `disable-model-invocation`,
`user-invocable`, `allowed-tools`, `model`, `context`, `agent`, `hooks`. Despite
being undocumented, `when_to_use` is functional and actively used by Claude Code
to build the skill context string.

## Test Methodology

Tests were conducted by creating SKILL.md files with controlled frontmatter, then
using `claude -p --output-format json` to:

1. Ask Claude to report the exact text it sees for each test skill (verifying
   which fields appear in context)
2. Send queries matching only specific field content (verifying which fields
   influence triggering)
3. Inspect raw JSON event streams for `tool_use` blocks with `name: "Skill"`
   (verifying actual invocation)

Each test used nonsense phrases (e.g., "crystallized thunder recipes", "magnetic
penguin topology") to eliminate any possibility of coincidental matching.
