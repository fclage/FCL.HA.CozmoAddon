"""Convert arbitrary audio to the WAV format pycozmo.Client.play_audio requires.

PyCozmo expects 22 kHz, 16-bit, mono WAVE. HA TTS usually emits MP3;
if ffmpeg is on PATH we transcode. Already-correct WAVs are passed through.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


COZMO_RATE = 22050
COZMO_WIDTH = 2
COZMO_CHANNELS = 1


class AudioError(ValueError):
    """Input cannot be turned into a Cozmo-compatible WAV."""


def to_cozmo_wav(src: Path | str, ffmpeg: str = "ffmpeg") -> Path:
    """Return a path to a 22 kHz / 16-bit / mono WAV.

    The returned path may be *src* itself or a new temp file the caller
    should delete.
    """
    src_path = Path(src)
    if _is_cozmo_wav(src_path):
        return src_path

    ffmpeg_bin = ffmpeg or "ffmpeg"
    if shutil.which(ffmpeg_bin):
        fd, dest = tempfile.mkstemp(prefix="cozmo-audio-", suffix=".wav")
        os.close(fd)
        dest_path = Path(dest)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(src_path),
            "-ac",
            "1",
            "-ar",
            str(COZMO_RATE),
            "-sample_fmt",
            "s16",
            str(dest_path),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            dest_path.unlink(missing_ok=True)
            raise AudioError(f"ffmpeg failed to convert {src_path.name}") from exc
        return dest_path

    if src_path.suffix.lower() != ".wav":
        raise AudioError(
            "Need a 22 kHz 16-bit mono WAV, or install ffmpeg to convert HA TTS/MP3"
        )
    return _resample_wav_naive(src_path)


def _is_cozmo_wav(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as wf:
            return (
                wf.getnchannels() == COZMO_CHANNELS
                and wf.getsampwidth() == COZMO_WIDTH
                and wf.getframerate() == COZMO_RATE
            )
    except wave.Error:
        return False


def _resample_wav_naive(src: Path) -> Path:
    """Linear-interpolate a PCM WAV to 22 kHz 16-bit mono (no ffmpeg)."""
    with wave.open(str(src), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)
    if width != 2:
        raise AudioError("Only 16-bit PCM WAV can be resampled without ffmpeg")

    samples = list(struct.unpack("<" + "h" * (len(raw) // 2), raw))
    if channels == 2:
        samples = [
            int((samples[i] + samples[i + 1]) / 2) for i in range(0, len(samples) - 1, 2)
        ]
    elif channels != 1:
        raise AudioError(f"Unsupported channel count {channels}")

    if rate != COZMO_RATE and samples:
        ratio = COZMO_RATE / float(rate)
        out_len = max(1, int(len(samples) * ratio))
        resampled = []
        for i in range(out_len):
            src_pos = i / ratio
            i0 = int(src_pos)
            i1 = min(i0 + 1, len(samples) - 1)
            frac = src_pos - i0
            resampled.append(int(samples[i0] * (1 - frac) + samples[i1] * frac))
        samples = resampled

    fd, dest = tempfile.mkstemp(prefix="cozmo-audio-", suffix=".wav")
    os.close(fd)
    dest_path = Path(dest)
    with wave.open(str(dest_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(COZMO_RATE)
        out.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return dest_path
