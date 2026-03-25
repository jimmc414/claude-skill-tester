# Ecosystem-Aware Competitive Analysis

## Core Insight

Skills don't exist in isolation, but the tool tests them as if they do. In a real
Claude Code session, ALL skill descriptions are loaded simultaneously and compete
for a shared context budget (~2% of context window, ~16K chars). The optimizer
doesn't know WHY a query fails — rival interception vs budget exclusion vs
genuine mismatch require different fixes.

## Resolved: What Claude Sees

Empirically confirmed (March 2025, Claude Code 2.1.83). See SKILL_FRONTMATTER.md
for full test methodology.

**Three fields are loaded into context for skill matching:**

| Field | Format in context |
|-------|-------------------|
| `name` | Prefix before `:` |
| `description` | After the `:` |
| `when_to_use` | Appended with ` - ` separator |

**Context string per skill:**
```
skill-name: {description} - {when_to_use}
```
Or `skill-name: {description}` when `when_to_use` is absent.

**Budget formula per skill:**
```
cost = len(name) + 2 + len(description) + (3 + len(when_to_use) if when_to_use else 0)
```

**Critical:** Only `when_to_use` (underscore) works. `when-to-use` (hyphen) is
silently ignored. All other arbitrary fields (`keywords`, `tags`,
`trigger_phrases`, etc.) are invisible.

## Proposed Additions

### 1. Frontmatter Health Checks (static analysis, no API calls)

Assess whether a skill's frontmatter is structurally well-formed before running
any tests. This catches problems that F1 scoring cannot — a skill can have
perfect trigger accuracy while having broken or suboptimal frontmatter.

**ERROR-level (broken — will not work as intended):**
- E1: Uses `when-to-use` (hyphen) which is silently ignored
- E2: `description` exceeds 1024 character limit

**WARN-level (suboptimal — reduced effectiveness):**
- W1: Missing `when_to_use` — leaves a second independent trigger surface unused
- W2: High content redundancy between `description` and `when_to_use` (Jaccard > 0.60) — wastes budget
- W3: Skill exceeds 5% of ~16K budget (800+ chars) — budget pressure risk

**INFO-level (observations):**
- I1: `description` and `when_to_use` are complementary (Jaccard < 0.30) — good

**Grades** (separate vocabulary from F1 verdict to avoid confusion):
- BROKEN — has ERROR-level checks
- IMPROVABLE — has WARN-level checks
- HEALTHY — no issues

### 2. Budget Analysis (`skill-test landscape`)

- Discover all skills in the environment (personal + project + plugin)
- Compute per-skill context cost using the confirmed formula
- Sum total budget consumption, show % of ~16K
- Flag skills at risk of exclusion
- Show health grade for each skill

### 3. Rival Capture During Test Runs

- `_detect_skill_in_events` already scans for target Skill tool_use blocks
- Extend to capture ANY Skill invocation on false-negative cases
- Transform "query X didn't trigger" into "query X triggered `explain-code` instead"
- Implementation delta is small: event loop already sees all tool_use blocks

### 4. Rivalry-Aware Optimization

- Feed rival skill name + description into optimization prompt on FN cases
- Instead of "these didn't trigger," optimizer sees "intercepted by skill Y (description Z)"
- Shifts optimizer from blindly strengthening keywords to carving semantic territory

### 5. Overlap Detection

- Use Claude to identify skill description pairs with semantic overlap
- Surface as landscape report: conflicts, budget pressure, recommendations

## Why This Is High-Leverage

- Solves a hidden problem users can't diagnose manually
- Small implementation delta (infrastructure mostly exists)
- Transforms scope from "test one skill" to "optimize skill portfolio"
- Health checks are free (no API calls) and provide immediate value
- Addresses the description-as-semantic-territory insight
