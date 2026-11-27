"""Local whisper.cpp fallback: detection, model choice, output parsing and the fetch path."""

import json

import pytest

from ytmaxxing import youtube as yt


@pytest.fixture
def no_env(monkeypatch):
    for k in ("YTMAXXING_WHISPER_CPP", "YTMAXXING_WHISPER_CPP_MODEL", "YTMAXXING_WHISPER_CPP_DIR"):
        monkeypatch.delenv(k, raising=False)


def test_model_prefers_large_turbo_then_falls_back(tmp_path, monkeypatch, no_env):
    monkeypatch.setenv("YTMAXXING_WHISPER_CPP_DIR", str(tmp_path))
    assert yt._whisper_cpp_model() is None
    (tmp_path / "ggml-tiny.bin").write_bytes(b"x")
    assert yt._whisper_cpp_model().name == "ggml-tiny.bin"
    (tmp_path / "ggml-small.bin").write_bytes(b"x")
    assert yt._whisper_cpp_model().name == "ggml-small.bin"
    (tmp_path / "ggml-large-v3-turbo.bin").write_bytes(b"x")
    assert yt._whisper_cpp_model().name == "ggml-large-v3-turbo.bin"


def test_explicit_model_must_exist(tmp_path, monkeypatch, no_env):
    monkeypatch.setenv("YTMAXXING_WHISPER_CPP_MODEL", str(tmp_path / "missing.bin"))
    assert yt._whisper_cpp_model() is None
    (tmp_path / "mine.bin").write_bytes(b"x")
    monkeypatch.setenv("YTMAXXING_WHISPER_CPP_MODEL", str(tmp_path / "mine.bin"))
    assert yt._whisper_cpp_model().name == "mine.bin"


def test_available_needs_binary_model_and_ffmpeg(tmp_path, monkeypatch, no_env):
    (tmp_path / "ggml-small.bin").write_bytes(b"x")
    monkeypatch.setenv("YTMAXXING_WHISPER_CPP_DIR", str(tmp_path))
    found = {"whisper-cli": "/bin/whisper-cli", "ffmpeg": "/bin/ffmpeg"}
    monkeypatch.setattr(yt.shutil, "which", lambda name: found.get(name))
    assert yt.whisper_cpp_available()
    found.pop("ffmpeg")
    assert not yt.whisper_cpp_available()


def test_parse_whisper_cpp_json():
    data = {"result": {"language": "en"},
            "transcription": [{"offsets": {"from": 0, "to": 5000}, "text": " this is a magic wand"},
                              {"offsets": {"from": 5000, "to": 9000}, "text": "   "},
                              {"offsets": {"from": 13250, "to": 20000}, "text": " fintech  app\n"}]}
    tr = yt._parse_whisper_cpp_json(data)
    assert tr.source == "whisper" and tr.language == "en"
    assert [(l.start, l.text) for l in tr.lines] == [(0.0, "this is a magic wand"), (13.25, "fintech app")]


def test_blocked_captions_fall_back_to_whisper_cpp(tmp_path, monkeypatch):
    def blocked(vid, languages=None):
        raise RuntimeError("IpBlocked: YouTube is blocking requests from your IP")

    def fake_download(vid, folder):
        p = tmp_path / "a.webm"
        p.write_bytes(b"audio")
        return str(p)

    def fake_cpp(path, folder):
        return yt._parse_whisper_cpp_json({"result": {"language": "en"},
                                          "transcription": [{"offsets": {"from": 1000}, "text": "hello"}]})

    monkeypatch.setattr(yt, "fetch_captions", blocked)
    monkeypatch.setattr(yt, "faster_whisper_available", lambda: False)
    monkeypatch.setattr(yt, "whisper_cpp_available", lambda: True)
    monkeypatch.setattr(yt, "_download_audio", fake_download)
    monkeypatch.setattr(yt, "_transcribe_whisper_cpp", fake_cpp)
    tr = yt.fetch_transcript("-X4L9vnpl3Q")
    assert tr.source == "whisper" and tr.lines[0].text == "hello"


def test_blocked_without_any_whisper_names_both_options(monkeypatch):
    def blocked(vid, languages=None):
        raise RuntimeError("429 Too Many Requests")

    monkeypatch.setattr(yt, "fetch_captions", blocked)
    monkeypatch.setattr(yt, "faster_whisper_available", lambda: False)
    monkeypatch.setattr(yt, "whisper_cpp_available", lambda: False)
    with pytest.raises(yt.YtmaxxingError) as e:
        yt.fetch_transcript("-X4L9vnpl3Q")
    msg = str(e.value)
    assert "YTMAXXING_PROXY" in msg and "ytmaxxing[whisper]" in msg and "whisper.cpp" in msg


def test_engine_choice(monkeypatch):
    monkeypatch.setattr(yt, "faster_whisper_available", lambda: True)
    monkeypatch.setattr(yt, "whisper_cpp_available", lambda: True)
    monkeypatch.delenv("YTMAXXING_WHISPER_ENGINE", raising=False)
    assert yt._whisper_engine() == "faster-whisper"
    monkeypatch.setenv("YTMAXXING_WHISPER_ENGINE", "whisper.cpp")
    assert yt._whisper_engine() == "whisper.cpp"
    monkeypatch.setattr(yt, "whisper_cpp_available", lambda: False)
    with pytest.raises(yt.YtmaxxingError):
        yt._whisper_engine()
