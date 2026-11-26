# Outcomes mode

**Goal:** turn the video into decisions and actions for the user's own goal. This is the "so what do I do now" mode.

**The user's goal:** {{GOAL}}

If the goal above is empty, look for it in the conversation (what they're building, deciding or working on). If you still can't tell, ask the user one short question before writing.

Write this:

```markdown
# <Video title>: outcomes for <the goal, in a few words>

> <One sentence: the most valuable move this video suggests for this goal.>

## What applies to you
<The 3–5 ideas from the video that matter for this goal, each with why it fits (or where it doesn't fit as-is) and a timestamp.>

## Decisions to make
<Choices the video helps settle. For each: options, what the video argues, your recommendation and how confident you are.>

## Do this week
- [ ] <Concrete action, small enough to start today.>
- [ ] …

## How you'll know it's working
<The signal or metric to watch, and a realistic timeframe.>

## What to ignore
<Advice from the video that doesn't fit this goal or context, and why.>
```

Be specific to the user's situation. Generic advice that fits everyone is a failed output.
