---
name: dev-pipeline
description: |
  Full-cycle development pipeline: brainstorming → spec review by agent team → plan writing → execution.
  Use when the user wants to develop a new feature, debug, or do research using a structured spec-first workflow.
  Trigger phrases: "do a full pipeline", "full cycle dev", "dev pipeline", "spec and plan for", "start pipeline".
---

# Dev Pipeline — Spec → Plan → Execute

Run the full structured development workflow for the task: `$ARGUMENTS`

---

## Overview

This pipeline guides you through 7 steps:

1. **Brainstorm** — Write an initial spec (outputs `specs/*.md`)
2. **Human review** — You review the spec and give feedback
3. **Agent team refinement** — Two agents (spec reviewer + spec writer) iterate until consensus
4. **Main agent review** — Auto-fix small issues, surface big decisions for your input
5. **Human final check** — Optional: review the plan before execution
6. **Write plan** — Convert refined spec into executable plan (outputs `plans/*.md`)
7. **Execute plan** — Run the plan

---

## Step 1 — Brainstorm: Write Initial Spec

Use `/superpowers:brainstorming` to produce an initial spec based on the user-provided context.

**Before invoking**, ask the user to confirm or provide:
- The task description / goal
- Any relevant files, logs, or code snippets
- How to test / validate the result
- Any constraints or preferences

Then invoke:
```
/superpowers:brainstorming <task description and all context above>
```

Output the spec to `specs/<task-slug>.md` where `<task-slug>` is a short kebab-case name for the task.

---

## Step 2 — Human Review of Spec

**Pause and show the user the generated spec.**

Ask:
> "Please review `specs/<task-slug>.md`. Does the direction look correct? Are there missing requirements or constraints I should add?"

Wait for the user's response before continuing.
Apply any corrections or additions they request directly to the spec file.

---

## Step 3 — Agent Team Refinement

Launch two sub-agents in parallel to collaborate on the spec. Continue until they reach consensus (no new issues raised).

### Agent A: Spec Reviewer
Role: kernel developer / kernel tester / researcher (match to the task domain)

Prompt:
```
You are a <domain expert> reviewing a spec for: <task>.

Your job is to:
1. Read the spec in specs/<task-slug>.md
2. Identify missing requirements, edge cases, unclear assumptions, or wrong directions
3. Give concrete, numbered feedback points
4. Be critical — your role is to find problems, not to agree

Read the spec and respond with your review.
```

### Agent B: Spec Writer
Role: technical writer who owns the spec document

Prompt:
```
You are the spec writer for: <task>.

The current spec is at specs/<task-slug>.md.
The spec reviewer has given the following feedback:

<feedback from Agent A>

Your job is to:
1. Update the spec to address all valid feedback
2. Explain which feedback you accepted and why, and which you rejected and why
3. Output the full updated spec

Update specs/<task-slug>.md with your final version.
```

Repeat this loop (reviewer → writer → reviewer) until the reviewer raises no new issues (or at most 3 rounds).

---

## Step 4 — Main Agent Review

After the agent team finishes:

1. **Auto-fix** any formatting issues, broken cross-references, or obvious inconsistencies in the spec
2. **List any open questions** that require a human decision (e.g., API design choices, performance trade-offs, scope cuts)
3. **Present the list to the user** and ask for their input

Example format:
```
The agent team has finalized the spec. I auto-fixed the following minor issues:
- [list]

There are X decisions that need your input:
1. [decision A] — Option 1: ... / Option 2: ...
2. [decision B] — ...

Please tell me your preferences and I'll update the spec accordingly.
```

Apply the user's answers to the spec.

---

## Step 5 — Human Final Check (Optional)

**Show the user the final spec and ask:**
> "The spec is ready at `specs/<task-slug>.md`. Would you like to review it before I generate the plan? (yes to review / no to proceed)"

If the user wants to review: wait for feedback and apply it.
If not: proceed to Step 6.

---

## Step 6 — Write Plan

Convert the finalized spec into an executable plan:

```
/superpowers:writing-plans specs/<task-slug>.md
```

Output to `plans/<task-slug>.md`.

Show the user the generated plan and confirm they are ready to execute.

---

## Step 7 — Execute Plan

Run the plan:

```
/superpowers:executing-plans plans/<task-slug>.md
```

Or if the plan is large or involves parallel work:

```
/subagent-driven-development plans/<task-slug>.md
```

Report progress and final results to the user.

---

## Tips

- You can run this pipeline end-to-end before going offline: give all context upfront in `$ARGUMENTS`, set preferences in Step 2 promptly, and let Steps 3–7 run overnight.
- You can run multiple pipelines in parallel for independent tasks.
- If at any step the spec or plan looks wrong, stop and ask the user rather than guessing.
- The agent team in Step 3 should be launched with the `Agent` tool using `subagent_type: general-purpose`, running in parallel for the first reviewer pass.
