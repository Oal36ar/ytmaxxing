# ytmaxxing next: cited research across many videos

> Proposal, 26 Nov 2026. Nothing is built, committed or pushed. Every build step waits for Omar's yes.

## The answer

Build **`research`** next. You give your AI a question and a set of videos (a list, a playlist, a channel, a YouTube search, or one six-hour stream). It comes back with one report: where the speakers agree, where they contradict each other, and who said what, with every point linked to the second it was said in its own video, plus a plain line saying which videos were read and which were skipped.

The earlier read was right about the direction and needs one correction. Working through many videos is not new on its own. NotebookLM takes up to 50 YouTube sources per notebook, and at least three open-source MCP servers already fetch several videos at once (coyaSONG's `research-videos` for 2–5 videos with timestamped evidence, youtube-research-mcp for up to 8, VidLens for indexed sets). A plain "summarise these videos" mode would be one more copy. What none of them document, as far as we could check from their READMEs, is the combination ytmaxxing is already built for:

1. **Citations the server checks, not the model.** The agent cites claim IDs; ytmaxxing turns them into timestamp links only after confirming the quoted words are really at that moment in that transcript. A made-up timestamp can't reach the report.
2. **Disagreement as the main output, read in full.** The report is organised around positions and who holds them, and each video is read end to end by its own subagent rather than searched in snippets. (VidLens also offers agree / disagree answers, built by the agent from snippet search; see section 3.)
3. **A library that compounds.** Every claim is kept, so the 51st video is checked against the first 50, and a report can be re-run when new videos come out to show what changed.

That last point is the leverage point from the systems map below: the product's unit stops being "a video" and becomes "a question".

---

## 1. Systems map

**Behaviour over time.** No usage data yet: v0.1.0 went public on 26 Nov 2026. What we do know is the pattern around it. In the last few weeks several free tools shipped the same core feature (video, playlist or channel to skill). The shape is commoditisation: the novelty of "YouTube → skill" is a stock that drains every time someone else ships it, and it does not refill.

**Boundary.** Inside: users and their questions, their AI agents, the ytmaxxing server and library, YouTube as the source, competing tools, and the channels people discover tools through (GitHub, Instagram and X AI pages). Left as clouds: model quality and pricing (we inherit whatever the user's AI is), and creators' content (we only link to it). Time horizon: the next two to three months, while the launch window is open.

**Stocks and flows.**

| Stock | Fills with | Drains with |
|---|---|---|
| Attention (stars, shares) | Something new to show | Novelty fading, copies appearing |
| Each user's library (videos, claims) | Every run | Nothing (it's local markdown) |
| Trust in outputs | Citations that check out | One wrong timestamp in a shared report |
| YouTube's tolerance of this IP | Time between requests | Bursts of fetches (429s, blocks) |
| Agent context per run | Fresh subagents | Long transcripts (one 2-hour episode is roughly 18–20k words, an estimate at ~150 words a minute) |
| Omar's maintenance time | Fixed | Every mode and platform added |

**Loops.**

- **R1 Novelty → attention.** A new idea gets shared, shares bring stars, stars bring more shares. Strong at launch, then fades as the idea becomes common.
- **B1 Copying.** Video → skill is a transcript fetch plus a good prompt: a weekend build. Each new copy lowers the novelty that R1 runs on. This loop is dominant right now.
- **R2 Library compounding.** More videos in the library should make the next video more valuable (it can be compared with what's already there), which should keep people running videos through ytmaxxing rather than elsewhere. **Today this loop is almost open:** outputs are filed per video and `search_library` is a word search, so video 20 knows nothing about video 1. The missing piece is an information link, not a feature count.
- **R3 Trust.** Outputs that check out get used in real work (a thesis, a memo, a client brief), and people who use it seriously recommend it to others who do. One fabricated citation in a shared report breaks this loop quickly.
- **B2 YouTube limits.** More fetches in a burst lead to blocks, which lead to failed runs and lost trust. There is a delay: blocks show up after the burst, not during it. The current code fetches with no pacing or retry (`fetch_transcript` tries once, then falls back to Whisper or raises), which is fine for one video and fragile for fifty.
- **B3 The context ceiling.** More videos in one agent's context push it past what it can read, so it skims and breaks ytmaxxing's own rule 1 ("read the whole video first"). Quality falls silently. Past a few long videos, one context can't hold the job at all.

```mermaid
flowchart LR
    N["Novelty"] -->|R1 +| A["Attention / stars"]
    A -->|+| U["Users"]
    C["Copies by other tools"] -->|B1 −| N
    U -->|+| L["Library of claims"]
    L -->|R2 + (missing link today)| V["Value of the next video"]
    V -->|+| U
    T["Verified citations"] -->|R3 +| TR["Trust"]
    TR -->|+| U
    F["Fetch bursts"] -->|B2 − after a delay| TR
    X["Videos per agent context"] -->|B3 − skimming| TR
```

**Actors and what they see.**

- *Users* want an answer to a question; a pile of per-video files is work, not an answer.
- *Their agents* follow written rules but skim when context is full, and will write a plausible timestamp if nothing stops them.
- *Competing builders* see the same easy feature and ship it fast; they are rewarded for "it works on a playlist".
- *YouTube* sees bursts from one IP and blocks them.
- *AI pages on Instagram and X* reward a new idea with a visible result, not a repeat.
- *Omar* is the only maintainer, with little time; every extra mode is a cost forever.

**The trap: escalation, plus seeking the wrong goal.** Competing on "video → skill" means matching each copy's next feature (channels, playlists, more formats). That is an escalation race that a solo maintainer loses to whoever has more distribution. The quieter trap is counting what's easy (number of modes, stars) instead of what matters (people trusting the output enough to use it in real work).

**Leverage points, strongest first.**

| Level (Meadows) | Move | Direction | Cost | Who resists |
|---|---|---|---|---|
| 3 · Goal | Make the unit of value **a question answered from many videos**, not a video summarised | Weakens B1 (harder to copy), strengthens R2 and R3 | Medium: new mode and tools | Nobody outside; inside, the pull to keep adding modes |
| 5 · Rules | **No citation reaches a report unless the server has checked it** | Strengthens R3, protects against the one failure that kills trust | Small: string matching on files we already have | The agent (it will want to paraphrase freely) |
| 6 · Information flow | **Claims link across videos**: each new video is compared with what the library already holds | Closes R2 | Small once claims are stored as data | None |
| 9 · Delays | Paced, resumable fetching with a visible coverage ledger | Weakens B2 | Small | YouTube's limits stay; we just stop tripping them |
| 12 · Numbers | More modes, more platforms (podcasts, other video sites) | Feeds the escalation race | Ongoing | Omar's time |

**Two steps ahead (for `research`).**

1. *First:* one real report on 10–20 videos with a disagreement table. The visible change is in attention (a new idea to show) and in trust (anyone can click any citation).
2. *Then:* copies follow. A multi-video summary is easy to copy; server-checked citations, a claim index and re-runs that show what changed are slower to copy because they need the library underneath. The race moves to ground where ytmaxxing already has a head start.
3. *If it succeeds too well:* the next limit is YouTube blocking heavy users (B2) and slow Whisper fallback for videos with no captions. The plan below builds pacing and an honest coverage line in from day one, so a report with gaps says so rather than hiding them.

**Cheapest test.** Run the test plan in section 4 on 15 videos before any public claim. If fewer than 19 of 20 random citations check out when a person clicks them, or the report finds no real contradictions on a topic that clearly has them, the idea isn't working yet. Review the result before the film is cut.

**Confidence.** Competitor facts: web check on 26 Nov (see section 3), marked where unverified. Code facts (no pacing, per-video library, word search, ~6,000-word parts): read from the repo. Word and token counts: estimates, labelled. User demand: one friend's feedback, not data.

---

## 2. Technical architecture

**Principle kept from v0.1.0:** the server fetches, checks and stores; the user's own AI does the thinking. Still no API key, still plain markdown on the user's disk.

### Who does what

| Step | Who | What happens |
|---|---|---|
| 1. Frame | Main agent + server | The agent turns the user's question into 3–7 sub-questions. `research_start` saves them in `brief.md`, resolves the sources (list, playlist, channel or `ytsearch`), and writes `sources.json` with one row per video. |
| 2. Fetch | Server | `research_fetch` pulls transcripts in small batches, paced (a few seconds between requests, backoff on 429, stop after repeated blocks). Each row gets a status: fetched, no captions, blocked, too short, duplicate. Transcripts go into the shared `videos/` cache, so a video is never fetched twice across projects. |
| 3. Extract (fan out) | One subagent per video, or per segment of a long stream | Each reads its whole transcript and writes a **claim card**: every claim that bears on a sub-question, with speaker, type (shown / measured / belief / story), stance, seconds, and a short verbatim quote. Saved with `save_claims`. |
| 4. Check | Server | `save_claims` checks each claim: the timestamp falls inside the transcript, and the quote is found in that paragraph or its neighbours (fuzzy match, because auto-captions garble names; the DOAC run spells Kokotajlo "Cocatello"). Passing claims get an ID like `V07.12` and a level: *quote-checked* or *time-checked*. Failing claims go back to the subagent to fix or drop. |
| 5. Synthesise (fan in) | Main agent | `research_claims` returns all checked claims grouped by sub-question, as one compact line each (about 40 tokens), not the transcripts. The agent groups them into positions and writes the report, citing claim IDs only. |
| 6. Render | Server | `save_report` checks every ID exists, turns IDs into `[Speaker, 12:34](link)`, **counts** how many videos hold each position (so "7 of 15" comes from code, not the model), and adds the coverage line. Unknown IDs are rejected. |
| 7. Keep | Server | Cards and reports stay in the library. Later runs and `claim_check` read them. |

### New tools (server side)

| Tool | Purpose |
|---|---|
| `research_start(question, sub_questions, sources, limit)` | Create a project, resolve sources, return the plan and the extraction guide |
| `search_videos(query, limit)` | YouTube search through yt-dlp's `ytsearch`, so a topic can be the source |
| `research_fetch(project, batch=5)` | Fetch the next batch, paced; returns progress. Call until done. Resumable. |
| `research_status(project)` | The coverage ledger: what's read, skipped and why |
| `save_claims(project, video, card)` | Check and store one claim card |
| `research_claims(project, sub_question?)` | Compact checked claims for synthesis |
| `save_report(project, markdown)` | Check IDs, render links, compute counts, save |
| `claim_check(claim)` (feature 4) | Find support and contradiction for one statement across everything in the library |

Plus a `research` guide in `src/ytmaxxing/guides/` and an MCP prompt, like the other modes.

### Library layout

```
~/ytmaxxing/
├── videos/<title>-<id>/transcript.md      ← shared cache (unchanged)
└── research/<slug>/
    ├── brief.md          question, sub-questions, source rule, date
    ├── sources.json      one row per video: status and reason
    ├── cards/<id>.md     checked claim cards
    ├── report.src.md     what the agent wrote (claim IDs)
    └── report.md         what the user reads (rendered links, counts, coverage)
```

### The report

1. The answer in a paragraph, with how strongly the videos support it.
2. Coverage: "Read 14 of 15 videos (31 hours). Skipped 1: no captions."
3. **Where they agree:** each position, the videos that hold it (count from code), best citation for each.
4. **Where they contradict each other:** each disagreement as two or more sides, each side cited in its own video.
5. **Who said what:** a speaker × sub-question grid.
6. Evidence quality: what was shown or measured versus believed or told as a story.
7. Gaps: sub-questions nobody answered well.

### Scaling to about 50 videos (estimates)

| Scale | Transcript text | How it runs |
|---|---|---|
| 1 long video | ~20k words, 3–4 parts | One agent, as today |
| 10–20 videos | 150–350k words | One subagent per video, about 5 at a time; one synthesis pass |
| ~50 videos | ~0.5–1M words | Same, plus a two-level fan-in: synthesise per sub-question first, then the whole report |
| One six-hour stream | ~50–55k words, ~9 parts | Split into segments of about 3 parts with a short overlap; each segment is treated like a video |

Tokens: roughly 1.3 per word, so 15 one-to-two-hour videos come to about 0.4–0.6M tokens of reading, almost all inside subagents, and the synthesis pass reads only the claim lines (well under 100k). The guide recommends a cheaper model for extraction and the user's strongest model for synthesis. These are planning numbers; the test in section 4 will measure the real ones.

### Failure handling

- **Blocked or rate-limited:** pace, back off, stop after repeated blocks, keep progress, tell the user to try later, use a proxy, or enable Whisper.
- **No captions:** Whisper fallback if installed (slow on long videos); otherwise the video is marked skipped with the reason. The report always says what was skipped.
- **Subagent fails or times out:** its row stays "fetched, not extracted"; re-running picks up only the missing ones.
- **Bad citations:** rejected at `save_claims`, never reach the report.
- **Duplicates and re-uploads:** detected by ID and by title and length.
- **Context overflow in synthesis:** the two-level fan-in.

### Clients without subagents

Claude Desktop, Cursor and the rest run the same loop one video at a time. All state is on disk, so the run is resumable across sessions. MCP sampling could let the server drive the loop itself, but client support is uneven, so the design doesn't depend on it.

### What stays local

Transcripts, claim cards and reports never leave the machine. ytmaxxing only talks to YouTube. The user's AI reads the transcripts under its own terms, as today.

### Honest limits to state in the README

- Captions don't say who is speaking. In interviews the speaker comes from context (host versus guest); in panels and streams the report marks the speaker as uncertain when it is.
- A checked quote proves the words were said at that moment. It does not prove the agent's paraphrase is fair; the report keeps the quote next to the paraphrase so a reader can judge.
- Coverage depends on captions and YouTube's limits.

---

## 3. First features to build, ranked

**Competitor check, 26 Nov 2026** (web, from READMEs and product pages, not their code; one Sonnet subagent):

| Tool | What it does | Many videos? | Timestamp citations | Agree / contradict | Keeps current |
|---|---|---|---|---|---|
| back1ply/youtube-to-skill | **Not found** (GitHub returns 404). Nearest match: yfe404/youtube-to-skill, a video or playlist to one SKILL.md | Playlist in, one skill out | Not stated | No | No (warns old videos need checking) |
| yt2skill (qazaqninja, SkillsMP listing) | One video to an installable skill | No | Unverified | No | No |
| claude-video `/watch` (bradautomates) | One video or file: frames plus transcript, or a timestamped answer via Gemini | No | Yes, within one video | No | No |
| coyaSONG/youtube-mcp-server | `research-videos`: 2–5 videos and one query, evidence per video | 2–5 | Yes | Side by side only, no verdict | No |
| youtube-research-mcp (lee-s-dev) | Search, bulk transcripts, channel analysis; the model does the comparing | Up to 8 | Not documented | Not documented | No |
| VidLens (thatsrajan) | Indexes transcripts and frames, compares video sets | Yes | Frames, yes | Claimed in one README example, no documented tool | No |
| NotebookLM | Notebook of up to 50 sources, cited answers | Up to 50 | Passage citations; seconds not confirmed | Not found | No auto-refresh (unverified) |

**VidLens code check (26 Nov, after Omar's yes).** VidLens (TypeScript, 36 stars, last push 10 Oct 2026) does advertise this: its first README example asks reviewers' videos "what do reviewers agree on, and where do they disagree?" and says it answers "with sources and timestamps". In the code, that answer is composed by the agent from transcript search over an indexed collection (`importPlaylist`, `searchTranscripts`, local TF-IDF or Gemini embeddings). There is no disagreement tool, no check that a cited timestamp or quote is real, and no counting by code (grep of the README, `analysis.ts` and `knowledge-base.ts`; `analyzeVideoSet` compares views, not claims). Its demo GIF also compares three Diary of a CEO episodes (views and sentiment), so the film should not lead with a DOAC comparison that looks like theirs.

**So the honest "new" is narrower than the first draft said.** Agree / disagree synthesis exists. What's new is the evidence standard: every video read in full by its own subagent (not retrieved in snippets), every citation checked by code, counts done by code, and a coverage line. In one line for the film: *"Every citation is checked. Click any one and it lands on the moment."*

The specific back1ply repo the friend named couldn't be found; ask for the link.

| # | Feature | Why it's new | Scope | How we show it for real |
|---|---|---|---|---|
| 1 | **`research`**: question + many videos → cited agree / contradict / who-said-what report with coverage | Others stop at side-by-side evidence for up to 8 videos. This adds a structured disagreement report, server-checked citations, counts done by code, an honest coverage line and up to ~50 videos |  Steps 1–7 above, the guide, tests on saved transcripts | The test in section 4; the report and its coverage line go in the film |
| 2 | **Checked citations everywhere** (claim IDs rendered by the server) | Turns "every claim linked to the second" from a promise into a check. Also applied to `knowledge` and `skill` outputs. | Matching code shared with feature 1; `save_output` reports how many links checked out | Re-run the DOAC knowledge note and publish the check result (e.g. "58 of 58 links checked") only if true |
| 3 | **Long streams** (six hours, segmented) | Users asked for it directly; one context can't hold it, and most tools either truncate or summarise the start | Segment logic on top of feature 1 | One public long stream, report with segment coverage |
| 4 | **`claim_check`**: "does anything I've read contradict this?" | Uses the claim index, so it gets better with every video; a single-video tool can't do it | One tool over stored claim cards | Check three claims from the DOAC episode against the 15-video test set |
| 5 | **Update a research**: add new videos, show what changed since the last run | Keeps notes current when newer videos contradict older ones | Diff of positions between two report runs | Re-run the test topic in a month |
| 6 | Skill self-test; `merge` becomes "research → one skill" | Useful, but not what researchers asked for | Later | Later |

The roadmap's `merge` item ("several videos on one topic become one stronger skill, with disagreements marked") becomes a special case of feature 1, so it doesn't need its own engine.

---

## 4. Real test plan (for the film's second half)

**Proposed topic:** "How soon will AI match top human experts, and what happens to jobs?" It continues the DOAC episode already in the film (Kokotajlo's 2029 median and 70% estimate), and it has real, named disagreement across forecasters, researchers and sceptics, so contradictions should appear if the tool works. A calmer fallback, if Omar prefers: "How should an early SaaS company set its prices?"

**Picking the videos fairly (decided before running).**
1. Fix the search terms and the rules first: long-form (30 minutes or more), published 2025–2026, captions available, a mix of guests who are known to disagree, at most two videos per channel.
2. ytmaxxing's own `search_videos` builds a longlist of about 30; Omar approves the final 15, including the DOAC episode.
3. Save the list and the rules in `brief.md` before extraction starts, so nobody can tune the sample to the result.

**Run.** Claude Code, the released build of the feature branch, extraction on a cheaper model, synthesis on the strongest. Record wall-clock time, tokens and how many videos were skipped and why.

**Pass criteria (set now).**
- At least 95% of claims pass the server check.
- A person clicks 20 random citations in the final report: at least 19 land on the moment where that point is made.
- At least three genuine contradictions, each with both sides cited.
- Counts in the report match the cards (checked by code).
- The coverage line is accurate.

**What the film can then show, and only if it's true:** the real question typed, the real tool calls, the coverage line ("Read 15 videos, 2 days of talk"), one contradiction row with both speakers and their timestamps, and the count of checked citations. Show text, links and thumbnails as the doac-thumb `RIGHTS.md` allows; no clips of creators' footage without permission. Exact numbers come from the run, not this plan.

---

## Decisions for Omar

1. Build `research` as the next feature (features 1 and 2 together, then 3)?
2. Test topic: AI timelines and jobs, or the SaaS pricing fallback?
3. When building starts: a feature branch in the repo, with this plan copied to `docs/` there (no push until you say)?
