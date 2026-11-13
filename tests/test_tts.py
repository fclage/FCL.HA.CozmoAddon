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
