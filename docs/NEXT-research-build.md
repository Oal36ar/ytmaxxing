# ytmaxxing `research`: build plan

> 26 Nov 2026. Follows [NEXT-research-plan.md](NEXT-research-plan.md), which Omar approved for build planning. Nothing is built yet. Building, committing and pushing each wait for Omar's yes.

## In one paragraph

Build it in three milestones. **M1** is the `research` mode itself: question plus up to ~50 videos in, a checked and cited agree / contradict / who-said-what report out. **M2** extends it to one six-hour stream by splitting it into segments. **M3** brings the same citation check to the existing `knowledge` and `skill` modes. M1 is the large one and the only one the film needs. It adds two new files of logic (`research.py`, `verify.py`), two guides, eight MCP tools and offline tests, and it changes no existing behaviour. Work happens on a local `feat/research` branch in a separate git worktree, so the `main` checkout used for the launch stays untouched. Nothing is pushed until Omar says so.

## What changes the design since the first plan

The VidLens check showed that agree / disagree answers already exist, written by the agent from snippet search. So the build puts its effort where ytmaxxing is actually different: **the code, not the model, checks every citation, counts every position and writes the coverage line.** The model writes only the parts that need judgement: the sub-questions, the claims, how claims group into positions, and the answer paragraph. Everything that can be wrong in a checkable way is done by code.

---

## M1: `research` across many videos

### Files

| File | Change |
|---|---|
| `src/ytmaxxing/verify.py` | **New.** Parse a saved `transcript.md` into timed paragraphs; check a claim's timestamp and quote; snap the time to the paragraph start |
| `src/ytmaxxing/research.py` | **New.** The `Project` class: create, resolve sources, paced fetch, status, store and check claims, list claims, render the report |
| `src/ytmaxxing/youtube.py` | Add `search_videos(query, limit)` using yt-dlp's `ytsearchN:` (flat, no download). Add `classify_error(e)` to tell "no captions" from "blocked" from other failures |
| `src/ytmaxxing/server.py` | Eight new tools (below) and a `research` MCP prompt |
| `src/ytmaxxing/guides/research.md` | **New.** For the main agent: frame, fetch, fan out, synthesise, save |
| `src/ytmaxxing/guides/research-extract.md` | **New.** For each subagent: read the whole video, write claims against the sub-questions |
| `src/ytmaxxing/modes.py`, `library.py` | Register `research`; teach `entries()` and `index.md` to list research projects |
| `src/ytmaxxing/cli.py` | `ytmaxxing research fetch <project>` and `research status <project>`, for long fetches outside a chat |
| `skills/ytmaxxing/SKILL.md`, `README.md` | Describe the mode, tools and honest limits; roadmap updated (`merge` folded into `research`) |
| `tests/test_verify.py`, `tests/test_research.py` | **New.** Offline tests (below) |
| `pyproject.toml` | Version 0.2.0. **No new dependencies** (fuzzy matching uses the standard library's `difflib`) |

### Tools

| Tool | Input | What it does |
|---|---|---|
| `search_videos` | query, limit | YouTube search, returns id, title, channel, length |
| `research_start` | question, sub_questions (3–7), sources (links, a playlist or channel link, or `search:<query>`), limit | Creates `research/<slug>/`, writes `brief.md` and `sources.json` (each video gets a short ID: V01, V02…), returns the plan and the next step |
| `research_fetch` | project, batch (default 5) | Fetches the next queued transcripts with pacing; returns progress. Call until it says done |
| `research_status` | project | The coverage ledger: fetched, extracted, skipped and why |
| `research_brief` | project, video ID | The extraction guide for one video with the sub-questions filled in; this is what the main agent hands to each subagent |
| `save_claims` | project, video ID, claims (structured list) | Checks each claim, stores the ones that pass, returns rejections with reasons |
| `research_claims` | project, sub_question?, offset | Checked claims as compact one-line rows for synthesis |
| `save_report` | project, answer, positions (structured), notes | Renders and saves `report.md`, with counts, links, coverage and a who-said-what grid all done by code |

### A claim, as the subagent sends it

```json
{"q": "Q2", "claim": "Superintelligence likely by about 2029", "speaker": "Daniel Kokotajlo",
 "type": "belief", "stance": "before 2030", "t": "02:34",
 "quote": "probably by the end of the decade"}
```

`save_claims` gives it an ID (`V07.12`), checks it, and stores it in `cards/V07.json`, plus a readable `cards/V07.md`.

### How the check works (`verify.py`)

1. Read `transcript.md` into paragraphs, each with its start second (taken from the `?t=` in its link; a paragraph starting at exactly 0 s has no `?t=`, because `watch_url` drops it, so treat a missing `?t=` as 0).
2. Find the paragraph that contains the claim's time, plus one paragraph on each side, because a caption paragraph is about 45 seconds long.
3. Normalise text (lower case, no punctuation, single spaces). Then:
   - exact match of the quote → **quote-checked**;
   - otherwise a sliding word window scored with `difflib`, with a ratio of 0.85 or more → **quote-checked (close match)**. This catches auto-caption garbling such as "Cocatello";
   - no quote given, but the time falls inside the video → **time-checked**;
   - anything else → **rejected**, with the reason sent back to the subagent.
4. Snap the time to the start of the matching paragraph, so the link lands where the words begin.

What it can't check, and the README says so: whether the paraphrase is fair (the quote sits next to it in the report), and who is speaking (captions have no speaker labels).

### How the report is built (`save_report`)

The agent sends structured positions, not finished prose for the counted parts:

```json
{"q": "Q2", "kind": "contradict",
 "sides": [{"label": "Superhuman AI before 2030", "claims": ["V07.12", "V03.4"]},
           {"label": "Decades away or never", "claims": ["V11.2", "V05.9", "V14.1"]}]}
```

Code then:
- rejects any claim ID that doesn't exist;
- counts distinct videos per side ("3 of 15 videos");
- renders each claim as `[Speaker, 12:34](https://youtu.be/ID?t=754)` with its quote;
- builds the speaker × sub-question grid from the claims;
- writes the coverage line from `sources.json` ("Read 14 of 15 videos, 31 h 20 min. Skipped 1: no captions");
- puts the agent's answer paragraph and evidence notes in place, expanding any `{V07.12}` references into links.

Report order: answer, coverage, where they agree, where they contradict each other, who said what, evidence quality, gaps, sources list.

### Fetching without getting blocked (`research_fetch`)

- Videos already in the shared `videos/` cache cost nothing and are skipped instantly.
- Between new fetches it waits 2–5 seconds (random). Each video currently takes about three YouTube requests (metadata, caption list, caption fetch).
- If YouTube rate-limits or blocks, it waits longer and retries once. After two blocked videos in a row it stops the batch, keeps progress and tells the user their options (later, a proxy, or Whisper).
- No captions → marked skipped with the reason. **Whisper is off by default in research**, because transcribing 50 long videos on a laptop takes hours. The user can turn it on per project.
- Duplicates are caught by video ID, and re-uploads by matching title plus length within 5%.
- A batch of 5 stays well inside MCP tool-call time limits. For 50 videos, the CLI `research fetch` runs the whole queue in a terminal.

### The fan-out, as the guide tells the main agent

1. Write 3–7 sub-questions. Show the user the source list and confirm before reading more than 20 videos.
2. Call `research_fetch` until done, then `research_status`.
3. **If you can start subagents** (Claude Code can): start one per fetched video, about 5 at a time, on a smaller, cheaper model. Give each the text from `research_brief`. Each subagent reads every part with `get_video`, then calls `save_claims` and fixes what it rejects. **If you can't**, do the same yourself, one video at a time. Progress is on disk, so a new session can carry on.
4. Call `research_claims` for each sub-question and group the claims into positions.
5. Call `save_report`. Tell the user the answer, the coverage, and the sharpest disagreement.

For more than about 30 videos, the guide has the agent group positions one sub-question at a time before writing the answer, so no single step has to hold all the claims.

### Tests (offline, no network)

- `verify`: exact quote; garbled caption (close match passes); quote from the wrong minute (rejected); time past the end (rejected); first paragraph with no `?t=`; time snapping.
- Source resolution: a list of links, a mocked playlist, mocked `search:`; V01… numbering; duplicates.
- `research_fetch` with a mocked fetch that raises "no captions", then "blocked" twice: the statuses are right, the batch stops, and `sleep` is patched out so tests run instantly.
- `save_claims`: mixed pass and reject; a claim for an unknown video; the ID sequence continues across calls.
- `save_report`: counts done by code; unknown ID rejected; the coverage line matches `sources.json`; the grid is right.
- Existing tests still pass.

### Before M1 is called done

1. `uv run pytest` passes.
2. **Smoke run:** three short videos on one topic, in Claude Code against the dev checkout. Read every rejected claim to tune the match threshold.
3. **The 15-video test** from the first plan, run on the topic Omar approves, with the video list he approves. Pass bar: at least 95% of claims pass the check; at least 19 of 20 randomly clicked citations land on the right moment; at least three real contradictions; counts match.
4. Measure real time, tokens and skips, and replace the estimates in the README with the measured numbers.

---

## M2: one six-hour stream

- When `research_start` gets a single video longer than about 3 parts (~18k words), it plans **segments** instead of videos: S01 = parts 1–3, S02 = parts 4–6, and so on. Each segment is extracted like a video. The report says "Read 9 of 9 parts (6 h 02 min)".
- `research_brief` tells a segment's subagent which parts to read. Each segment also reads the last paragraph of the part before it, so a claim split across a boundary isn't lost.
- The who-said-what grid labels speakers "uncertain" unless the context names them. Streams often have many voices and captions don't separate them.
- Tests: segment planning for a 9-part video, and IDs and coverage for segments.
- Proof: one public long stream that Omar chooses.

## M3: checked citations in `knowledge` and `skill`

- Add a short "Quote" column to the knowledge template and an optional quote per skill step.
- `save_output` runs the same check on every timestamp link and quote and returns "41 of 42 citations checked; 1 rejected: [reason]", so the agent can fix it before the user reads it.
- Re-run the DOAC knowledge note under M3. Publish its check result only if it's true.

## Later, not in this build

`claim_check` (feature 4) and re-running a research to show what changed (feature 5) both read the stored claim cards, so they are small once M1 exists. The skill self-test stays on the roadmap.

---

## Order and size

| Step | Size | Depends on |
|---|---|---|
| Worktree + branch `feat/research` | Tiny | Omar's yes |
| `verify.py` + tests | Small | — |
| `research.py` (sources, fetch, claims, report) + tests | Large | verify |
| Server tools, guides, CLI | Medium | research.py |
| Smoke run on 3 videos | Small | all above |
| 15-video test | Medium (mostly reading time) | Omar approves topic and list |
| README, skill, version 0.2.0 | Small | test results |
| M2 segments | Small | M1 |
| M3 citations in other modes | Small–medium | M1 |

Sizes are relative, not promises. The 15-video test is the gate for both the film and the public release.

## What needs Omar

1. **Start M1** on a local branch in a separate worktree (no push)?
2. **Test topic:** AI timelines and jobs (recommended; continues the DOAC thread in the film) or SaaS pricing.
3. Later, once the 15-video list is built: approve the list before extraction starts.
