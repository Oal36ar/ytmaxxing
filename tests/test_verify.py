import time

import pytest

from ytmaxxing.library import Library
from ytmaxxing.verify import check, check_output, normalise, parse_paragraphs, parse_time
from ytmaxxing.youtube import Line, Transcript, Video, render_transcript

VID = "_g4l7YkDQwA"

SPEECH = [
    (0.0, "Welcome back to the show."),
    (4.0, "Today my guest is Daniel Cocatello, who left OpenAI."),
    (30.0, "He thinks superintelligence arrives probably by the end of the decade."),
    (52.0, "That is his median, around twenty twenty nine."),
    (95.0, "Some people say it's decades away, and I don't think that's right."),
    (150.0, "Let's talk about jobs and what happens to them."),
    (200.0, "Whether jobs remain is a political question, not a technical question."),
]


def _transcript(tmp_path):
    video = Video(id=VID, title="Whistleblower", channel="DOAC", duration=260,
                  chapters=[{"start": 0, "title": "Intro"}, {"start": 150, "title": "Jobs"}])
    lib = Library(tmp_path)
    lib.save_transcript(video, Transcript([Line(s, t) for s, t in SPEECH], "en", "auto-captions"))
    md = (lib.find_video_dir(VID) / "transcript.md").read_text()
    return md, parse_paragraphs(md)


@pytest.mark.parametrize("value,secs", [(754, 754), (754.9, 754), ("754", 754), ("12:34", 754),
                                        ("1:02:34", 3754), ("12:34s", 754),
                                        (f"https://youtu.be/{VID}?t=99", 99), ("[02:05]", 125)])
def test_parse_time(value, secs):
    assert parse_time(value) == secs


def test_parse_time_rejects_junk():
    with pytest.raises(ValueError):
        parse_time("soon")


def test_paragraphs_parsed_with_times(tmp_path):
    md, paras = _transcript(tmp_path)
    assert paras[0].start == 0  # a paragraph at 0 s has no ?t= in its link
    assert [p.start for p in paras] == sorted(p.start for p in paras)
    assert any(p.start == 150 for p in paras)  # chapter boundary starts a new paragraph


def test_exact_quote(tmp_path):
    _, paras = _transcript(tmp_path)
    c = check(paras, "00:40", "probably by the end of the decade")
    assert c.status == "quote" and c.t is not None and c.t <= 40


def test_quote_punctuation_and_case_ignored(tmp_path):
    _, paras = _transcript(tmp_path)
    assert check(paras, 205, "Whether jobs remain is a POLITICAL question, not a technical question!").status == "quote"


def test_garbled_caption_name_is_a_close_match(tmp_path):
    _, paras = _transcript(tmp_path)
    c = check(paras, 10, "my guest is Daniel Kokotajlo who left OpenAI")
    assert c.status == "quote-close" and c.score >= 0.85


def test_quote_from_the_wrong_minute_is_rejected(tmp_path):
    _, paras = _transcript(tmp_path)
    c = check(paras, 205, "probably by the end of the decade")
    assert c.status == "rejected" and "not found" in c.reason


def test_invented_quote_is_rejected(tmp_path):
    _, paras = _transcript(tmp_path)
    assert check(paras, 40, "AI will definitely kill us all next year").status == "rejected"


def test_time_past_the_end_is_rejected(tmp_path):
    _, paras = _transcript(tmp_path)
    c = check(paras, "45:00", duration=260)
    assert c.status == "rejected" and "past the end" in c.reason


def test_time_only_citation_snaps_to_paragraph(tmp_path):
    _, paras = _transcript(tmp_path)
    c = check(paras, 210, duration=260)
    assert c.status == "time" and c.t == 200


def test_too_short_or_too_long_quotes(tmp_path):
    _, paras = _transcript(tmp_path)
    assert check(paras, 40, "the decade").status == "rejected"
    assert check(paras, 40, " ".join(["word"] * 40)).status == "rejected"


def test_normalise():
    assert normalise("Don’t STOP — now!") == "dont stop now"


def test_check_output_counts_links_and_quotes(tmp_path):
    _, paras = _transcript(tmp_path)
    md = "\n".join([
        "| Claim | Quote | Moment |",
        "|---|---|---|",
        f'| Superintelligence soon | "probably by the end of the decade" | [00:30](https://youtu.be/{VID}?t=30) |',
        f'| Jobs are political | "a political question, not a technical question" | [03:20](https://youtu.be/{VID}?t=200) |',
        f'| Made up | "robots will run every office by June" | [01:35](https://youtu.be/{VID}?t=95) |',
        f"| Past the end | | [45:00](https://youtu.be/{VID}?t=2700) |",
        "| Other video | | [01:00](https://youtu.be/AAAAAAAAAAA?t=60) |",
    ])
    rep = check_output(md, VID, paras, duration=260)
    assert (rep.links, rep.links_ok) == (5, 3)
    assert (rep.quotes, rep.quotes_ok) == (3, 2)
    assert len(rep.problems) == 3
    s = rep.summary()
    assert "3 of 5" in s and "2 of 3 quoted phrases" in s and "Check these" in s


def test_check_output_without_links_says_so(tmp_path):
    _, paras = _transcript(tmp_path)
    assert "no timestamp links" in check_output("# Notes\nNothing cited.", VID, paras).summary()


def test_long_transcript_check_is_fast():
    words = " ".join(f"w{i}" for i in range(150))
    paras = parse_paragraphs("\n---\n\n" + "\n\n".join(
        f"[{i}:00](https://youtu.be/{VID}?t={i * 60}) {words}" for i in range(1, 200)))
    t0 = time.perf_counter()
    for _ in range(30):
        check(paras, 6000, "this sentence appears nowhere in the whole transcript at all")
    assert time.perf_counter() - t0 < 5


# ---------------------------------------------------------------- fixes from the 2026-11-26 real run

def test_close_match_that_changes_the_meaning_is_rejected(tmp_path):
    """Run notes problem 2: "decade" -> "year" passed at 95%. Only a name may differ now."""
    _, paras = _transcript(tmp_path)
    for quote, why in [("superintelligence arrives probably by the end of the year", "a word differs"),
                       ("That is his median around twenty twenty eight", "a number differs"),
                       ("Some people say it's decades away and I do think that's right", "a negation differs")]:
        c = check(paras, 40 if "superintelligence" in quote else 60 if "median" in quote else 100, quote)
        assert c.status == "rejected" and "changes the meaning" in c.reason and why in c.reason, (quote, c)
    assert check(paras, 10, "my guest is Daniel Kokotajlo who left OpenAI").status == "quote-close"
    # dropping any real word is rejected; dropping an article is fine
    assert check(paras, 100, "Some people say it's decades away and I don't think right").status == "rejected"
    assert check(paras, 30, "He thinks superintelligence arrives by the end of the decade").status == "rejected"
    assert check(paras, 30, "superintelligence arrives probably by end of the decade").status == "quote-close"


def test_link_lands_near_the_quote_not_the_paragraph_start(tmp_path):
    """Run notes problem 7: links pointed at the paragraph start, up to 45 s before the words."""
    video = Video(id=VID, title="Long paragraph", channel="X", duration=120)
    lines = [(float(s), f"filler sentence number {s} with several more ordinary words in it") for s in range(0, 41, 8)]
    lines[-1] = (40.0, "and here is the important closing point about jobs")
    lib = Library(tmp_path)
    lib.save_transcript(video, Transcript([Line(s, t) for s, t in lines] + [(Line(60.0, "next paragraph"))],
                                          "en", "captions"))
    paras = parse_paragraphs((lib.find_video_dir(VID) / "transcript.md").read_text())
    c = check(paras, 0, "the important closing point about jobs")
    assert c.status == "quote" and c.t == 0
    assert 10 <= c.at < 40  # later than the paragraph start, and never after the words (errs early)
    assert check(paras, 0, "filler sentence number 0").at == 0
