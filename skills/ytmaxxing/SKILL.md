---
name: ytmaxxing
description: Turn YouTube videos, playlists and channels into skills, knowledge, summaries, study guides, outcomes and upgrade checks using the ytmaxxing MCP tools. Use whenever the user shares a YouTube link, asks to learn from, summarize, take notes on, extract a skill from, or apply a video to their project or goal, or asks about videos they saved before.
---

# ytmaxxing

Turn any YouTube video into something the user keeps: a skill their agent can follow, cited knowledge, a summary, a study guide, a plan for their goal, or upgrades to an existing skill or project.

## Pick the mode from what the user wants

| The user says something like… | Mode |
|---|---|
| "max this", "get everything from this video", just a bare link | `max` |
| "teach my agent this", "make a skill from this", a tutorial link | `skill` |
| "take notes", "save this for later", "what does it say about…" | `knowledge` |
| "summarize", "is this worth watching", "tl;dr" | `summary` |
| "help me learn this", "quiz me", "study guide" | `learn` |
| "how do I use this for my business / project / goal" | `outcomes` (pass their goal) |
| "compare with my skill / project / plan", "what should I change" | `check` (pass the path or description) |

If it's unclear, use `max`, or ask one short question.

## Steps

1. Call `maxx(url, mode, goal, target)`. It fetches the video into the library and returns the guide for that mode.
2. Read **every** transcript part with `get_video(url, part=N)` before writing.
3. Write the output exactly as the guide says: cite moments with the timestamp links from the transcript, never invent.
4. Save with `save_output`. For skills, offer `install_skill` and install only on the user's yes.
5. Reply briefly: what you made and the single most useful thing in it.

## Playlists and channels

Call `list_playlist(url, limit)` first, show the user the list, and agree which videos to process before starting. Process them one at a time. For several videos on the same topic, offer a final merged knowledge note or skill that says where the creators agree and disagree.

## Questions about saved videos

Before answering a question about something the user watched or saved, call `search_library` (and `list_library` for an overview). Answer from what's saved, with timestamp links.

## When fetching fails

The error says why. Common fixes: the video has no captions (install the `whisper` extra for local transcription), or YouTube is blocking the network (set `YTMAXXING_PROXY`). Tell the user the fix in one line.
