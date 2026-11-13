"""Text-to-speech for Cozmo (22 kHz mono 16-bit WAV).

PyCozmo has no off-board TTS; this is the local hook Home Assistant
`ha_cozmo.speak` uses.

Engine: Piper (local neural TTS, no cloud) with the voice kept loaded in
memory, so synthesis takes tens of milliseconds. espeak-ng is the automatic
fallback when Piper or its voice model is not available or fails.

Environment overrides (all optional):
  COZMO_TTS_ENGINE   "piper" (default) or "espeak"
  COZMO_PIPER_VOICE  voice name (looked up in COZMO_PIPER_DIR) or a path to
                     an .onnx model; default en_US-amy-medium
  COZMO_PIPER_DIR    default ~/.local/share/piper
  COZMO_TTS_PITCH    pitch/tempo factor for Piper output, 1.0 = natural;
                     default 1.10 (a little higher, more Cozmo-like)
  COZMO_PIPER_AUTO_DOWNLOAD
                     "1" (default) downloads a named voice from the official
                     rhasspy/piper-voices repository into COZMO_PIPER_DIR the
                     first time it is needed; "0" disables that
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Optional

log = logging.getLogger("ha_cozmo.tts")

DEFAULT_SPEED = 155
DEFAULT_PITCH = 92
DEFAULT_AMPLITUDE = 100

COZMO_RATE = 22050
DEFAULT_PIPER_VOICE = "en_US-amy-medium"
DEFAULT_PIPER_DIR = Path.home() / ".local" / "share" / "piper"
DEFAULT_PIPER_PITCH = 1.10

_voice_lock = threading.Lock()
_voice = None
_voice_path: Optional[Path] = None


def find_espeak() -> Optional[str]:
    return shutil.which("espeak-ng") or shutil.which("espeak")


def _piper_model_path() -> Path:
    voice = os.environ.get("COZMO_PIPER_VOICE", "").strip() or DEFAULT_PIPER_VOICE
    if voice.endswith(".onnx") or "/" in voice:
        return Path(voice).expanduser()
    base = Path(os.environ.get("COZMO_PIPER_DIR", "").strip() or DEFAULT_PIPER_DIR).expanduser()
    return base / f"{voice}.onnx"


def _pitch_factor() -> float:
    try:
        f = float(os.environ.get("COZMO_TTS_PITCH", "") or DEFAULT_PIPER_PITCH)
    except ValueError:
        f = DEFAULT_PIPER_PITCH
    return min(max(f, 0.8), 1.4)


def _maybe_download_voice(path: Path) -> None:
    """Fetch a named voice (e.g. en_US-amy-medium) into its directory once."""
    if os.environ.get("COZMO_PIPER_AUTO_DOWNLOAD", "1").strip().lower() in {"0", "false", "no", "off"}:
        return
    voice = os.environ.get("COZMO_PIPER_VOICE", "").strip() or DEFAULT_PIPER_VOICE
    if voice.endswith(".onnx") or "/" in voice:
        return  # explicit model path: never download
    from piper.download_voices import download_voice

    path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading Piper voice %s to %s", voice, path.parent)
    t0 = time.perf_counter()
    download_voice(voice, path.parent)
    log.info("Piper voice %s downloaded in %.1f s", voice, time.perf_counter() - t0)


def _load_piper():
    """Load (once) and return the Piper voice. Raises on failure."""
    global _voice, _voice_path
    path = _piper_model_path()
    with _voice_lock:
        if _voice is not None and _voice_path == path:
            return _voice
        from piper import PiperVoice  # imported lazily; optional dependency

        if not path.is_file():
            _maybe_download_voice(path)
        if not path.is_file():
            raise FileNotFoundError(f"Piper voice model not found: {path}")
        t0 = time.perf_counter()
        _voice = PiperVoice.load(str(path))
        _voice_path = path
        log.info("Piper voice %s loaded in %.0f ms", path.name, (time.perf_counter() - t0) * 1000)
        return _voice


def preload() -> None:
    """Best-effort background load so the first speak is fast."""
    if os.environ.get("COZMO_TTS_ENGINE", "piper").strip().lower() == "espeak":
        return

    def _run() -> None:
        try:
            _load_piper()
        except Exception as exc:  # noqa: BLE001
            log.warning("Piper preload failed (espeak-ng fallback stays available): %s", exc)

    threading.Thread(target=_run, name="piper-preload", daemon=True).start()


def _resample_pitch(frames: bytes, factor: float) -> bytes:
    """Raise pitch (and tempo) by *factor* via resampling at 22050 Hz."""
    if abs(factor - 1.0) < 1e-3:
        return frames
    import numpy as np

    x = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    n = int(len(x) / factor)
    if n <= 1:
        return frames
    y = np.interp(np.arange(n, dtype=np.float32) * factor, np.arange(len(x), dtype=np.float32), x)
    return np.clip(y, -32768, 32767).astype(np.int16).tobytes()


def _synthesize_piper(text: str, out_path: Path) -> Path:
    voice = _load_piper()
    t0 = time.perf_counter()
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="cozmo_piper_raw_", suffix=".wav")
    os.close(tmp_fd)
    tmp = Path(tmp_name)
    try:
        with wave.open(str(tmp), "wb") as wf:
            voice.synthesize_wav(text, wf)
        with wave.open(str(tmp), "rb") as rf:
            rate, width, channels = rf.getframerate(), rf.getsampwidth(), rf.getnchannels()
            frames = rf.readframes(rf.getnframes())
        if rate != COZMO_RATE or width != 2 or channels != 1:
            # Non-22 kHz voice: let the audio path's ffmpeg converter handle it.
            shutil.move(str(tmp), str(out_path))
            log.info("TTS (piper %s, %d Hz, needs conversion): %r", _voice_path.name, rate, text)
            return out_path
        frames = _resample_pitch(frames, _pitch_factor())
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(COZMO_RATE)
            wf.writeframes(frames)
    finally:
        tmp.unlink(missing_ok=True)
    log.info(
        "TTS (piper %s, pitch %.2f) %.0f ms: %r",
        _voice_path.name,
        _pitch_factor(),
        (time.perf_counter() - t0) * 1000,
        text,
    )
    return out_path


def _synthesize_espeak(text: str, out_path: Path, speed: int, pitch: int, amplitude: int) -> Path:
    espeak = find_espeak()
    if not espeak:
        raise RuntimeError("espeak-ng not found. Install with: sudo apt install espeak-ng")
    cmd = [
        espeak,
        "-v",
        "en",
        "-s",
        str(int(speed)),
        "-p",
        str(int(pitch)),
        "-a",
        str(int(amplitude)),
        "-w",
        str(out_path),
        text,
    ]
    log.info("TTS: %s", " ".join(cmd[:-1] + [repr(text)]))
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def synthesize(
    text: str,
    out_path: Optional[Path] = None,
    *,
    speed: int = DEFAULT_SPEED,
    pitch: int = DEFAULT_PITCH,
    amplitude: int = DEFAULT_AMPLITUDE,
) -> Path:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty text")
    if len(text) > 400:
        text = text[:400]

    if out_path is None:
        fd, name = tempfile.mkstemp(prefix="cozmo_tts_", suffix=".wav")
        os.close(fd)
        out_path = Path(name)

    if os.environ.get("COZMO_TTS_ENGINE", "piper").strip().lower() != "espeak":
        try:
            return _synthesize_piper(text, out_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Piper TTS failed, falling back to espeak-ng: %s", exc)

    return _synthesize_espeak(text, out_path, speed, pitch, amplitude)
