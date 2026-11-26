# Contributing to ytmaxxing 🚀

Thanks for helping. The most valuable contributions are better guides, new modes, and reports of videos where ytmaxxing did badly.

## Set up

```bash
git clone https://github.com/Oal36ar/ytmaxxing && cd ytmaxxing
uv sync                      # add --extra whisper to work on local transcription
uv run pytest
```

Try your changes against a real MCP client by pointing it at your checkout:

```bash
claude mcp add ytmaxxing-dev -- uv --directory "$(pwd)" run ytmaxxing serve
```

## Improve a guide (no code needed)

Each mode is a markdown file in [`src/ytmaxxing/guides/`](src/ytmaxxing/guides). The AI reads it word for word, so small wording changes have real effects. When you change one:

1. Run the mode on two or three different videos before and after.
2. In your pull request, link the videos and paste a short before/after excerpt.

## Add a mode

1. Write `src/ytmaxxing/guides/<mode>.md`: the goal in one line, then the exact output template.
2. Register it in `MODES` in [`src/ytmaxxing/modes.py`](src/ytmaxxing/modes.py) (emoji, title, one-line description).
3. If it saves a new kind of file, add it to `OUTPUT_MODES` in [`src/ytmaxxing/library.py`](src/ytmaxxing/library.py).
4. Add it to the modes table in the README and run `uv run pytest`.

## Ground rules

- **Never print to stdout** in server code. MCP talks over stdout, and stray output breaks the connection. Use stderr or nothing.
- Keep outputs cited: every claim links to its timestamp.
- Keep dependencies few. ytmaxxing should install in seconds.

## Report a bad output

Open an issue with the video link, the mode, the client and model you used, and what was wrong. Those reports improve the guides fastest.
