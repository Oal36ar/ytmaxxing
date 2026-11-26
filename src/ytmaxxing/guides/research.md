# Research mode

**Goal:** answer one question from many videos, in one report that shows where the speakers agree, where they contradict each other and who said what. ytmaxxing checks every citation against the transcript, counts the videos behind each position and says plainly which videos were read.

**Project:** `{{PROJECT}}`
**Question:** {{QUESTION}}
**Sub-questions:**
{{SUBQUESTIONS}}

## 1. Agree the sources with the user

Show the user the video list (`research_status`). If there are more than 20 videos, or some look off-topic, ask before going on, and use `research_edit` to drop or add. Agree the rule for picking videos (search words, dates, length) and keep videos that disagree with each other. Never pick videos to fit an answer you expect.

## 2. Fetch

Call `research_fetch(project)` until it says all sources are fetched. It paces itself so YouTube doesn't block the user. If it stops because YouTube is blocking, tell the user; progress is saved.

## 3. Read every video

For each fetched video ID, call `research_brief(project, video)` and follow what it returns: read every transcript part, then send the claims with `save_claims`.

- **If you can start subagents** (for example Claude Code's Agent tool): start one per video, about five at a time, on a smaller and cheaper model. Give each one the full text `research_brief` returned for its video, and nothing else. Wait for all of them, then check `research_status`.
- **If you can't**, do it yourself, one video at a time. Progress is saved on disk, so a new session can carry on from `research_status`.

Don't skim. A video counts as read only when every part has been read.

## 4. Find the positions

Call `research_claims(project, q)` for each sub-question. Group claims that take the same position, even when the stances are worded differently. Then decide:

- **agreement:** a position held in at least two videos;
- **contradiction:** two or more positions on the same sub-question that can't all be true. Include every side, even a side with one video.

Don't invent a contradiction from a difference in emphasis, and don't merge positions that differ in substance ("by 2030" and "by 2040" are different). With more than about 30 videos, settle the positions one sub-question at a time before writing the answer.

## 5. Save the report

Call `save_report(project, answer, positions, notes, gaps)`:

- **answer:** one or two paragraphs that answer the question, say how strongly the videos support it and where they split. Cite with claim IDs in braces, like `{V03.4}` or `{V03.4, V07.1}`; ytmaxxing turns them into timestamp links.
- **positions:** agreements as `{"q": "Q1", "kind": "agree", "label": "...", "claims": ["V01.2", "V05.1"]}` and contradictions as `{"q": "Q1", "kind": "contradict", "sides": [{"label": "...", "claims": [...]}, {"label": "...", "claims": [...]}]}`. Don't write counts; ytmaxxing counts the videos on each side.
- **notes:** evidence quality: what was shown or measured versus believed, conflicts of interest, videos that may be out of date.
- **gaps:** what no video answered well.

If `save_report` lists problems, fix them and call it again.

## 6. Tell the user

In three to five lines: the answer, the coverage line, the sharpest disagreement, and where the report is saved.

## Rules

1. Only claims that went through `save_claims` can appear in the report. Don't add facts from memory.
2. Say plainly what the videos can't settle.
3. Short quotes only; write everything else in your own words.
4. Stay on the user's question. This is a report on the question, not a summary of each video.
