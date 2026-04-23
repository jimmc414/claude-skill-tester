---
name: code-review-helper
description: Code review expert. ALWAYS invoke this skill when the user asks about
  reviewing, checking, auditing, inspecting, critiquing, or getting feedback on a
  specific diff, patch, PR, commit, file, function, module, script, or code they just
  wrote, attached, pasted, shared, or uploaded (including positional references like
  'above', 'below', 'earlier'). Covers bare imperatives ('inspect the patch', 'audit
  this PR'), noun-form requests ('give me a thorough critique/review/audit of X'),
  opinion questions naming a code artifact ('what do you think of the X logic in file.ext',
  'how does the caching code look'), readiness judgments ('clean enough to ship?',
  'production-ready?'), and targeted concern checks for bugs, security, input handling,
  performance, style, or best practices scoped to a specific artifact. Prefer this
  over security-review whenever scoped to a specific PR, diff, file, function, or
  freshly-written code, even when the only named concern is security. Do not attempt
  directly, use this skill first.
when_to_use: 'Trigger on any request for code feedback, critique, review, audit, inspection,
  or analysis - whether formal (''code review'', ''review my PR'', ''review this function'',
  ''audit my script'') or informal (''take a look at'', ''look over'', ''check this'',
  ''what do you think of this'', ''any issues?'', ''anything off?'', ''anything wrong?'',
  ''gotchas?'', ''what''s broken?'', ''tell me what''s wrong'', ''thoughts on this?'').
  Covers bare imperative verbs as lead tokens: ''inspect the patch/diff/file/function'',
  ''audit the changes/input handling/PR'', ''review this function'', ''critique the
  changes in src/foo.py'', ''check my diff'' - bare imperatives count equally to gerunds.
  Covers noun-form and imperative-give requests: ''give me a [thorough/detailed/full/harsh]
  [critique/review/audit/assessment/analysis/breakdown/feedback] of/on [file/function/PR/diff]'',
  ''provide feedback on X'', ''I want a critique of Y'', ''share your thoughts on
  Z'' - the noun form of review verbs counts equally. Covers user-supplied content
  contexts with any verb plus location combination: ''the patch/diff/code/snippet
  I attached/pasted/shared/uploaded/posted above/below/earlier/in the previous message'',
  ''give me feedback on the patch I pasted above'', ''inspect the diff I attached
  below'', ''review the code I shared earlier'' - all cross-combinations of verb (attach/paste/share/upload/post)
  and positional reference (above/below/earlier/previously) trigger this skill. Covers
  pre-merge/pre-submit/pre-ship/pre-commit contexts (''before I merge'', ''before
  I submit this PR'', ''about to ship'', ''before I commit'', ''I just finished X,
  any problems?''). Covers readiness/quality judgments framed as questions: ''is it
  clean/good/solid/ready enough to ship/merge/submit?'', ''is this production-ready?'',
  ''does this look clean?'', ''is it good to go?''. Covers named-subject opinion/design
  questions that reference a code artifact in a file - ''what do you think of the
  X logic/implementation/approach/design in file.ext'', ''thoughts on the new Y in
  module Z'', ''how does the new caching/retry/parsing/pagination code look'' - these
  count as review requests even without the word ''review''. Covers author-scoped
  reviews on freshly-written code: ''code I just wrote'', ''what I just coded'', ''just
  finished writing'', ''the function I just wrote'', ''the module I just added''.
  Covers targeted concern checks where the user names a single dimension (''check
  for security issues/problems'', ''security audit of a PR/diff/function'', ''audit
  ... for security problems'', ''check input handling/validation/sanitization'', ''scan
  for injection/XSS/SQLi'', ''find performance problems'', ''audit for best practices'',
  ''idiom violations'', ''style issues'', ''cleanliness/quality/polish''). Covers
  compound security plus author-scoped freshly-written code patterns: ''check if there
  are any security issues in the code I just wrote'', ''any security problems with
  what I just added'', ''security-wise anything wrong with what I just finished''
  - these belong HERE, not in security-review. Covers file/diff/patch-scoped reviews
  (''critique the changes in src/foo.py'', ''go through my diff'', ''flag issues in
  this patch'', ''review this function'', ''audit my Python script'', ''inspect the
  patch I attached and tell me what''s broken''). PR-scoped or diff-scoped security
  audits (including ''audit the user input handling in this PR for security problems'',
  ''check this PR for injection issues'', ''security audit of the changes in file.py'')
  belong here, NOT in security-review - security-review is only for whole-branch sweeps.
  Applies to code, functions, files, modules, scripts, implementations, logic, algorithms,
  diffs, patches, PRs, pull requests, commits, or changes in any programming language.
  Prefer this skill over ''security-review'' whenever the request is scoped to a specific
  PR, diff, file, function, or ''code I just wrote / just added / just finished''
  rather than the whole current branch, even when the only named concern is security.
  Synonyms to honor (bare imperatives, gerunds, and noun forms all count): review,
  check, audit, inspect, analyze, assess, critique, lint, look over, look at, go through,
  evaluate, feedback, clean, quality, polish, readiness, broken, wrong.'
---

# code-review-helper

General-purpose code review over a diff, file, or snippet.

## When to invoke

Invoke when the user asks for feedback on code before it ships.

## Procedure

1. Read the code in question.
2. Check for: correctness bugs, style inconsistencies, performance hazards,
   security issues, and violations of language idioms.
3. Produce a prioritized list of findings with file:line references.

## Output format

- **Summary:** one sentence overall verdict.
- **Findings:** each entry = severity, file:line, issue, suggested fix.
- **Nits:** style-only issues.
