# 🔍 Check mode

**Goal:** see where the video adds up with something the user already has (a skill, a codebase, a plan, a doc, a strategy) and turn the difference into concrete upgrades.

**What to check against:** {{TARGET}}

If that's a file or folder path, read it (for a project, start with the README, docs and the files most related to the video's topic). If it's a description, work from that. If it's empty, ask the user what to compare the video with.

Write this:

```markdown
# <Video title> × <target>: check

> <One sentence: the single most valuable change this video suggests for the target.>

## Already covered
<What the target already does that the video recommends. Keep it short; this is reassurance, not the point.>

## New ideas worth adding
<What the video offers that the target lacks. For each: the idea, why it helps here, the exact change (file and section, or the new paragraph or step), and a timestamp.>

## Conflicts
<Where the video and the target disagree. Say which is more likely right for this user's context and why. Don't assume the video wins.>

## Upgrade plan
1. <Highest-value change first, with effort estimate: small / medium / large.>
2. …

## Leave as is
<Things the video suggests that don't fit here, with the reason.>
```

**Don't edit the target yourself.** Propose the changes; apply them only if the user says so.
