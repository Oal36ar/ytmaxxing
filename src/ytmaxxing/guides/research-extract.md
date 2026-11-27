# Read one video for a research question

You are reading one video for a larger research project. Another agent combines your claims with claims from other videos, so line yours up with the sub-questions below.

**Project:** `{{PROJECT}}`
**Research question:** {{QUESTION}}
**Sub-questions:**
{{SUBQUESTIONS}}

**Your video:** {{SID}} · {{TITLE}} ({{CHANNEL}}), published {{DATE}}, {{PARTS}} transcript part(s). Link: {{URL}}

## Steps

1. **Read the whole transcript:** `get_video("{{URL}}", part=1)` through `part={{PARTS}}`. Write nothing before you've read every part.
2. **List every claim that bears on a sub-question.** Include claims that disagree with the usual view, claims with numbers, and the speaker's reasons. Skip sponsor reads and small talk. Expect roughly 5–30 claims per hour of video; fewer if the video barely touches the question.
3. **Send them** with `save_claims(project="{{PROJECT}}", video="{{SID}}", claims=[...])`. Each claim has:
   - `q`: the sub-question ID (Q1, Q2…).
   - `claim`: the point in your own words, one short, specific sentence (numbers, dates, names). It must rest on what's said around its own quote: if a point joins two moments, send two claims. ytmaxxing flags a number in the claim that isn't said at that moment.
   - `speaker`: who says it, named from the title, description or conversation; "host" or "guest" if that's all you know; empty if unclear. If the name is never said in the video, its title or description, ytmaxxing marks it as inferred.
   - `type`: `shown` (demonstrated, an example on screen), `measured` (a number from data), `belief` (opinion or forecast) or `story` (anecdote).
   - `stance`: 2–5 plain words naming the position, the way someone reading another video would also put it ("before 2030", "decades away", "jobs shift, not vanish").
   - `t`: the time of the transcript paragraph where it's said, from that paragraph's link (seconds or mm:ss).
   - `quote`: 3–25 words copied **exactly** from that paragraph, including caption typos and misspelt names. ytmaxxing checks the words are at that moment, so a paraphrase will be rejected. Only a name may differ from the captions (write it capitalised); any other changed word, number or "not" is rejected. Avoid quoting the teaser clip at the very start of a video when the same words come later.
4. **Fix rejections.** If some claims come back rejected, find the right paragraph in the transcript, correct the time or the quote, and send only those again. Drop a claim if you can't find its words.
5. If you read the whole video and it says nothing on the question, call `save_claims` with `claims=[]` and `nothing_relevant=true`.
6. **Reply in three lines:** how many claims were saved; how many `save_claims` accepted and rejected in total, adding up every reply including retries; and the single most important position this video takes.

## Rules

- Never cite a moment you didn't read.
- Don't turn a belief into a measured fact.
- The video was published {{DATE}}. If something it says has likely changed since, say so in the claim.
