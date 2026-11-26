"""End to end through the MCP layer, with no network: transcripts are saved into the library first."""

import asyncio

import pytest

from ytmaxxing import research
from ytmaxxing.library import Library
from ytmaxxing.youtube import Line, Transcript, Video

A, B = "AAAAAAAAAAA", "BBBBBBBBBBB"


def call(name, args):
    from mcp.server.mcpserver.exceptions import ToolError

    from ytmaxxing.server import mcp

    try:
        res = asyncio.run(mcp.call_tool(name, args))
    except ToolError as e:  # the server turns these into error results for the client
        return str(e), True
    return res.content[0].text, res.is_error


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("YTMAXXING_HOME", str(tmp_path))
    monkeypatch.setattr(research, "_sleep", lambda s: None)
    lib = Library(tmp_path)
    lib.save_transcript(Video(id=A, title="Optimist", channel="P1", duration=200),
                        Transcript([Line(0.0, "Hello there."), Line(60.0, "I expect superhuman AI before twenty thirty.")],
                                   "en", "captions"))
    lib.save_transcript(Video(id=B, title="Sceptic", channel="P2", duration=200),
                        Transcript([Line(0.0, "Hi."), Line(60.0, "Human level AI is decades away, in my view.")],
                                   "en", "captions"))
    return tmp_path


def test_research_flow_over_mcp(home):
    text, err = call("research_start", {"question": "How soon will AI match human experts?",
                                         "sub_questions": ["When?"], "sources": [A, f"https://youtu.be/{B}"]})
    assert not err and "created with 2 video(s)" in text and "# Research mode" in text
    slug = text.split("`")[1]
    text, err = call("research_fetch", {"project": slug})
    assert "All sources fetched" in text
    text, err = call("research_brief", {"project": slug, "video": "V01"})
    assert "Read one video" in text
    text, err = call("save_claims", {"project": slug, "video": "V01", "claims": [
        {"q": "Q1", "claim": "Superhuman AI before 2030", "speaker": "Guest", "type": "belief",
         "stance": "before 2030", "t": "01:00", "quote": "superhuman AI before twenty thirty"}]})
    assert "Saved 1 claim(s)" in text
    text, err = call("save_claims", {"project": slug, "video": "V02", "claims": [
        {"q": "Q1", "claim": "Decades away", "speaker": "Lecturer", "type": "belief", "stance": "decades away",
         "t": 60, "quote": "human level AI is decades away"},
        {"q": "Q1", "claim": "Made up", "type": "belief", "stance": "x", "t": 60, "quote": "robots run every office"}]})
    assert "Saved 1 claim(s)" in text and "Rejected 1" in text
    text, err = call("research_claims", {"project": slug})
    assert "V01.1" in text and "V02.1" in text
    text, err = call("save_report", {"project": slug, "answer": "They split {V01.1, V02.1}.", "positions": [
        {"q": "Q1", "kind": "contradict", "sides": [{"label": "Soon", "claims": ["V01.1"]},
                                                    {"label": "Decades", "claims": ["V02.1"]}]}]})
    assert not err and "Read 2 of 2 videos" in text
    bad, err = call("save_report", {"project": slug, "answer": "x", "positions": [
        {"q": "Q1", "kind": "agree", "claims": ["V01.1", "V07.3"]}]})
    assert err and "V07.3" in bad
    text, _ = call("research_status", {"project": ""})
    assert slug in text and "report saved" in text


def test_save_output_reports_citation_check(home):
    md = (f"| Claim | Quote | Moment |\n|---|---|---|\n"
          f'| Soon | "superhuman AI before twenty thirty" | [01:00](https://youtu.be/{A}?t=60) |\n'
          f"| Wrong | | [50:00](https://youtu.be/{A}?t=3000) |")
    text, err = call("save_output", {"url": A, "mode": "knowledge", "markdown": md})
    assert not err and "Saved to" in text
    assert "1 of 2 timestamp links" in text and "1 of 1 quoted phrases" in text and "past the end" in text
