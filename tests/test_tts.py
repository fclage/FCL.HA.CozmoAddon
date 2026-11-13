from pathlib import Path

import pytest

from companion import tts


def test_model_path_from_name(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COZMO_PIPER_DIR", str(tmp_path))
    monkeypatch.setenv("COZMO_PIPER_VOICE", "en_US-lessac-medium")
    assert tts._piper_model_path() == tmp_path / "en_US-lessac-medium.onnx"


def test_model_path_explicit(monkeypatch, tmp_path) -> None:
    model = tmp_path / "voice.onnx"
    monkeypatch.setenv("COZMO_PIPER_VOICE", str(model))
    assert tts._piper_model_path() == model


def test_pitch_factor_clamped(monkeypatch) -> None:
    monkeypatch.setenv("COZMO_TTS_PITCH", "9")
    assert tts._pitch_factor() == 1.4
    monkeypatch.setenv("COZMO_TTS_PITCH", "bad")
    assert tts._pitch_factor() == tts.DEFAULT_PIPER_PITCH


def test_resample_pitch_shortens() -> None:
    import numpy as np

    frames = (np.arange(1000, dtype=np.int16) % 200).tobytes()
    out = tts._resample_pitch(frames, 1.25)
    assert len(out) // 2 == 800
    assert tts._resample_pitch(frames, 1.0) == frames


def test_falls_back_to_espeak(monkeypatch, tmp_path) -> None:
    def boom(text, out_path):
        raise RuntimeError("no piper")

    calls = []

    def fake_espeak(text, out_path, speed, pitch, amplitude):
        calls.append((text, amplitude))
        return out_path

    monkeypatch.delenv("COZMO_TTS_ENGINE", raising=False)
    monkeypatch.setattr(tts, "_synthesize_piper", boom)
    monkeypatch.setattr(tts, "_synthesize_espeak", fake_espeak)
    out = tts.synthesize("Welcome!", tmp_path / "x.wav")
    assert out == tmp_path / "x.wav"
    assert calls == [("Welcome!", tts.DEFAULT_AMPLITUDE)]


def test_espeak_engine_skips_piper(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COZMO_TTS_ENGINE", "espeak")
    monkeypatch.setattr(tts, "_synthesize_piper", lambda *a: pytest.fail("piper used"))
    monkeypatch.setattr(tts, "_synthesize_espeak", lambda text, out, *a: out)
    assert tts.synthesize("hi", tmp_path / "y.wav") == tmp_path / "y.wav"


def test_empty_text_rejected() -> None:
    with pytest.raises(ValueError):
        tts.synthesize("   ")


def test_no_download_for_explicit_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COZMO_PIPER_VOICE", str(tmp_path / "v.onnx"))
    tts._maybe_download_voice(tmp_path / "v.onnx")  # must not import or fetch anything
    assert not (tmp_path / "v.onnx").exists()


@pytest.fixture(autouse=True)
def _reset_loaded_voice():
    tts._voice = None
    tts._voice_path = None
    yield
    tts._voice = None
    tts._voice_path = None


def test_pitch_factor_low_clamp(monkeypatch) -> None:
    monkeypatch.setenv("COZMO_TTS_PITCH", "0.1")
    assert tts._pitch_factor() == 0.8


def test_resample_pitch_too_short_is_unchanged() -> None:
    import numpy as np

    frames = np.array([1], dtype=np.int16).tobytes()
    assert tts._resample_pitch(frames, 2.0) == frames


def test_auto_download_can_be_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COZMO_PIPER_AUTO_DOWNLOAD", "off")
    monkeypatch.setenv("COZMO_PIPER_VOICE", "en_US-amy-medium")
    model = tmp_path / "en_US-amy-medium.onnx"
    tts._maybe_download_voice(model)
    assert not model.exists()


def test_load_piper_missing_model(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COZMO_PIPER_DIR", str(tmp_path))
    monkeypatch.setenv("COZMO_PIPER_VOICE", "en_US-amy-medium")
    monkeypatch.setenv("COZMO_PIPER_AUTO_DOWNLOAD", "0")
    with pytest.raises(FileNotFoundError):
        tts._load_piper()


def test_load_piper_download_still_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COZMO_PIPER_DIR", str(tmp_path))
    monkeypatch.setenv("COZMO_PIPER_VOICE", "en_US-lessac-medium")
    monkeypatch.setenv("COZMO_PIPER_AUTO_DOWNLOAD", "1")
    import piper.download_voices as download_voices

    monkeypatch.setattr(download_voices, "download_voice", lambda voice, dest: None)
    with pytest.raises(FileNotFoundError):
        tts._load_piper()


def test_load_piper_downloads_then_reuses(monkeypatch, tmp_path) -> None:
    voice_dir = tmp_path / "voices"
    monkeypatch.setenv("COZMO_PIPER_DIR", str(voice_dir))
    monkeypatch.setenv("COZMO_PIPER_VOICE", "en_US-amy-medium")
    monkeypatch.delenv("COZMO_PIPER_AUTO_DOWNLOAD", raising=False)

    def fake_download(voice, dest):
        assert voice == "en_US-amy-medium"
        assert dest == voice_dir
        (dest / f"{voice}.onnx").write_bytes(b"onnx")

    import piper
    import piper.download_voices as download_voices

    monkeypatch.setattr(download_voices, "download_voice", fake_download)
    loaded = []

    class PiperVoice:
        @staticmethod
        def load(path):
            loaded.append(path)
            return {"path": path}

    monkeypatch.setattr(piper, "PiperVoice", PiperVoice)
    first = tts._load_piper()
    second = tts._load_piper()
    assert first is second
    assert loaded == [str(voice_dir / "en_US-amy-medium.onnx")]


def test_load_piper_existing_file_skips_download(monkeypatch, tmp_path) -> None:
    model = tmp_path / "en_US-amy-medium.onnx"
    model.write_bytes(b"onnx")
    monkeypatch.setenv("COZMO_PIPER_DIR", str(tmp_path))
    monkeypatch.setenv("COZMO_PIPER_VOICE", "en_US-amy-medium")
    import piper
    import piper.download_voices as download_voices

    monkeypatch.setattr(download_voices, "download_voice", lambda *_a, **_k: pytest.fail("downloaded"))

    class PiperVoice:
        @staticmethod
        def load(path):
            assert path == str(model)
            return "ready"

    monkeypatch.setattr(piper, "PiperVoice", PiperVoice)
    assert tts._load_piper() == "ready"


class _ImmediateThread:
    def __init__(self, target, name, daemon):
        assert name == "piper-preload"
        assert daemon is True
        self._target = target

    def start(self):
        self._target()


def test_preload_skips_espeak(monkeypatch) -> None:
    monkeypatch.setenv("COZMO_TTS_ENGINE", "espeak")
    monkeypatch.setattr(tts.threading, "Thread", lambda *_a, **_k: pytest.fail("started"))
    tts.preload()


def test_preload_swallows_load_errors(monkeypatch) -> None:
    monkeypatch.delenv("COZMO_TTS_ENGINE", raising=False)

    def boom():
        raise RuntimeError("no model")

    monkeypatch.setattr(tts, "_load_piper", boom)
    monkeypatch.setattr(tts.threading, "Thread", _ImmediateThread)
    tts.preload()


def _voice_writing(rate: int, payload: bytes):
    class Voice:
        def synthesize_wav(self, text, wf):
            assert text
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(payload)

    return Voice()


def _loaded(rate: int, payload: bytes, model: Path):
    def load():
        tts._voice_path = model
        return _voice_writing(rate, payload)

    return load


def test_piper_writes_natural_pitch_wav(monkeypatch, tmp_path) -> None:
    import wave

    monkeypatch.delenv("COZMO_TTS_ENGINE", raising=False)
    monkeypatch.setenv("COZMO_TTS_PITCH", "1")
    payload = b"\x01\x00" * 200
    model = tmp_path / "en_US-amy-medium.onnx"
    monkeypatch.setattr(tts, "_load_piper", _loaded(tts.COZMO_RATE, payload, model))
    out = tmp_path / "out.wav"
    assert tts.synthesize("Hello", out) == out
    with wave.open(str(out), "rb") as rf:
        assert rf.getframerate() == tts.COZMO_RATE
        assert rf.getnchannels() == 1
        assert rf.getsampwidth() == 2
        assert rf.readframes(rf.getnframes()) == payload


def test_piper_default_pitch_shortens(monkeypatch, tmp_path) -> None:
    import wave

    monkeypatch.delenv("COZMO_TTS_ENGINE", raising=False)
    monkeypatch.delenv("COZMO_TTS_PITCH", raising=False)
    payload = b"\x00\x00" * 1000
    model = tmp_path / "en_US-amy-medium.onnx"
    monkeypatch.setattr(tts, "_load_piper", _loaded(tts.COZMO_RATE, payload, model))
    out = tmp_path / "out.wav"
    tts.synthesize("Hello", out)
    with wave.open(str(out), "rb") as rf:
        assert rf.getnframes() == int(1000 / tts.DEFAULT_PIPER_PITCH)


def test_piper_keeps_other_sample_rates(monkeypatch, tmp_path) -> None:
    import wave

    monkeypatch.delenv("COZMO_TTS_ENGINE", raising=False)
    payload = b"\x02\x00" * 50
    model = tmp_path / "en_US-amy-medium.onnx"
    monkeypatch.setattr(tts, "_load_piper", _loaded(16000, payload, model))
    out = tmp_path / "out.wav"
    tts.synthesize("Hello", out)
    with wave.open(str(out), "rb") as rf:
        assert rf.getframerate() == 16000
        assert rf.readframes(rf.getnframes()) == payload


def test_truncates_long_text(monkeypatch, tmp_path) -> None:
    seen = []

    def fake_espeak(text, out_path, speed, pitch, amplitude):
        seen.append((text, speed, pitch, amplitude))
        return out_path

    monkeypatch.setenv("COZMO_TTS_ENGINE", "espeak")
    monkeypatch.setattr(tts, "_synthesize_espeak", fake_espeak)
    out = tmp_path / "z.wav"
    assert tts.synthesize("x" * 500, out) == out
    assert seen == [("x" * 400, tts.DEFAULT_SPEED, tts.DEFAULT_PITCH, tts.DEFAULT_AMPLITUDE)]


def test_synthesize_creates_a_wav_path(monkeypatch) -> None:
    monkeypatch.setenv("COZMO_TTS_ENGINE", "espeak")
    monkeypatch.setattr(tts, "_synthesize_espeak", lambda text, out, *_a: out)
    out = tts.synthesize("hi")
    assert out.suffix == ".wav"
    assert out.is_file()
    out.unlink()


def test_espeak_command_uses_amplitude(monkeypatch, tmp_path) -> None:
    cmds = []
    monkeypatch.setattr(tts, "find_espeak", lambda: "espeak-ng")

    def fake_run(cmd, check, capture_output):
        assert check is True
        assert capture_output is True
        cmds.append(cmd)

    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    out = tmp_path / "o.wav"
    assert tts._synthesize_espeak("hi", out, 155, 92, 100) == out
    cmd = cmds[0]
    assert cmd[0] == "espeak-ng"
    assert cmd[cmd.index("-a") + 1] == "100"
    assert cmd[-1] == "hi"


def test_espeak_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tts, "find_espeak", lambda: None)
    with pytest.raises(RuntimeError):
        tts._synthesize_espeak("hi", tmp_path / "a.wav", 155, 92, 100)
