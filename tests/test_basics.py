import pytest

from ytmaxxing.library import Library, skill_slug, slugify
from ytmaxxing.modes import MODES, build_guide
from ytmaxxing.youtube import (Line, Transcript, Video, YtmaxxingError, _normalise_list_url,
                               render_transcript, split_parts, timestamp, video_id)

ID = "QGzgsSXdPjo"


@pytest.mark.parametrize("url", [
    ID,
    f"https://www.youtube.com/watch?v={ID}",
    f"https://youtube.com/watch?v={ID}&t=42s",
    f"https://m.youtube.com/watch?v={ID}",
    f"https://music.youtube.com/watch?v={ID}&list=x",
    f"https://youtu.be/{ID}?si=abc",
    f"https://www.youtube.com/shorts/{ID}?feature=share",
    f"https://www.youtube.com/live/{ID}",
    f"https://www.youtube.com/embed/{ID}",
    f"youtube.com/watch?v={ID}",
])
def test_video_id(url):
    assert video_id(url) == ID


def test_video_id_rejects_junk():
    with pytest.raises(YtmaxxingError):
        video_id("https://example.com/watch?v=nope")


def test_timestamp():
    assert timestamp(65) == "01:05"
    assert timestamp(3725) == "1:02:05"


def test_channel_urls_get_videos_tab():
    assert _normalise_list_url("https://www.youtube.com/@veritasium") == "https://www.youtube.com/@veritasium/videos"
    assert _normalise_list_url("https://www.youtube.com/playlist?list=PL1") == "https://www.youtube.com/playlist?list=PL1"


def _sample():
    video = Video(id=ID, title="How to Test: A Guide!", channel="Chan", upload_date="2025-01-02",
                  duration=300, chapters=[{"start": 0, "title": "Intro"}, {"start": 60, "title": "Main"}])
    lines = [Line(i * 5.0, f"sentence {i}.") for i in range(40)]
    return video, Transcript(lines, "en", "captions")


def test_render_has_chapters_and_links():
    video, tr = _sample()
    blocks = render_transcript(video, tr)
    assert blocks[0] == "## Intro (00:00)"
    assert any(b.startswith("## Main (01:00)") for b in blocks)
    assert any(f"(https://youtu.be/{ID}?t=60)" in b for b in blocks)


def test_split_parts():
    parts = split_parts(["word " * 100] * 10, max_words=250)
    assert len(parts) == 5


def test_library_roundtrip(tmp_path):
    lib = Library(tmp_path)
    video, tr = _sample()
    lib.save_transcript(video, tr)
    assert lib.find_video_dir(ID).name == f"how-to-test-a-guide-{ID}"
    assert lib.transcript_parts(ID)
    lib.save_output(ID, "summary", "# Summary\nTesting is good.")
    skill = "---\nname: Write Good Tests\ndescription: x\n---\n# Steps"
    path = lib.save_output(ID, "skill", skill)
    assert path == tmp_path / "skills" / "write-good-tests" / "SKILL.md"
    entry = lib.entries()[0]
    assert set(entry["outputs"]) == {"summary", "skill"}
    assert "write-good-tests" in (tmp_path / "index.md").read_text()
    assert lib.search("testing good")[0]["file"].endswith("summary.md")
    installed = lib.install_skill("write-good-tests", tmp_path / "agent-skills")
    assert installed.read_text().startswith("---\nname: Write Good Tests")


def test_save_requires_fetched_video(tmp_path):
    with pytest.raises(YtmaxxingError):
        Library(tmp_path).save_output(ID, "summary", "x")


def test_slugs():
    assert slugify("Hello, World! — 2025") == "hello-world-2025"
    assert skill_slug("Deploy to Fly.io") == "deploy-to-fly-io"


@pytest.mark.parametrize("mode", list(MODES))
def test_guides_render(mode):
    g = build_guide(mode, video_id=ID, title="T", date="2025-01-02", parts=3, goal="grow", target="./skills")
    assert "{{" not in g
    assert "get_video" in g and "save_output" in g
