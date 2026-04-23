
Optimization: code-review-helper (DID NOT CONVERGE)
Target: F1 >= 0.90
==================================================

Round 1: F1 = 0.00 NEEDS_WORK
  FN (10): "Can you take a look at my changes before I subm...", "I just finished the auth module - any issues yo...", "Review this function for bugs and performance p..." (+7 more)

Round 2: F1 = 0.86 GOOD
  FN (5): "What do you think of the new caching logic in c...", "Audit the user input handling in this PR for se...", "Give me feedback on the function I just wrote —..." (+2 more)
  Regression cases: 10

Round 3: F1 = 0.86 GOOD  [+0.00]
  FN (6): "Give me feedback on the patch I pasted above", "Check if there are any security issues in the c...", "Give me a thorough critique of the changes in s..." (+3 more)
  Regression cases: 14

Frontmatter changes:
  name: code-review-helper
  description:
    BEFORE: "Reviews code for quality, style, bugs, performance, security, and best practices across all programming languages."
    AFTER:  "Code review expert. ALWAYS invoke this skill when the user asks about reviewing, checking, auditing, inspecting, crit..."
  when_to_use:
    BEFORE: "When a user wants any form of code review."
    AFTER:  "Trigger on any request for code feedback, critique, review, audit, inspection, or analysis - whether formal ('code re..."

