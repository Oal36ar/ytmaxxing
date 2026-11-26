# Skill mode

**Goal:** the user's AI learns how to do what the video teaches, as an Agent Skill (a `SKILL.md` file that Claude and other agents load when the task comes up).

## Step 1: decide honestly whether there is a skill

A skill exists only if the video teaches a **repeatable procedure**: steps someone can follow to get a result (a tutorial, a walkthrough, "here's exactly how I do X"). Interviews, opinions, news and stories usually don't contain one.

- If there is **no** procedure: don't invent one. Tell the user plainly, suggest `knowledge` or `outcomes` mode instead, and stop.
- If there are **several** distinct procedures: make one skill per procedure, each saved separately.

## Step 2: write the skill

```markdown
---
name: <lowercase-hyphenated-name, max 64 chars, says what it does>
description: <What the skill does AND when to use it, in one or two sentences. This is how the agent decides to load it, so name the situations and keywords that should trigger it. Max 1024 characters.>
---

# <Skill title>

<One paragraph: what this produces and when it's the right approach (and when it isn't).>

## Before you start
<Inputs, accounts, tools and versions required. What the agent should ask the user if missing.>

## Steps
1. <Imperative step the agent can carry out.> ([mm:ss](link))
2. …

## Check your work
<How to tell it worked: expected output, tests, signs of success.>

## Pitfalls
<Mistakes the speaker warns about or that are visible in the video, and how to avoid them.>

## Source
- Video: <title> by <channel>, <link>
- Published <YYYY-MM-DD>. Tools and versions shown: <list>. <If older than a year or tied to fast-moving tools, tell the agent to verify against current docs before relying on version-specific steps.>
```

## Step 3: rules for good skills

- Write steps for an **agent to execute**, not a person to read: imperative, specific, with exact commands, settings and values from the video.
- Keep the speaker's *reasons* for non-obvious steps, in one short clause. Agents follow steps better when they know why.
- Don't pad. If the video skips a step that's needed, add it and mark it `(not in video)`.
- Keep it under ~400 lines. Split into several skills rather than one giant one.
- Save each skill with `save_output(mode="skill", skill_name=<name>)`. Then offer to install it with `install_skill` (into `~/.claude/skills` or the current project). Don't install without the user's yes.
