"""Text-to-speech for Cozmo (22 kHz mono 16-bit WAV via espeak-ng).

PyCozmo has no off-board TTS; this is the local hook Home Assistant
`ha_cozmo.speak` uses.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("ha_cozmo.tts")

DEFAULT_SPEED = 155
DEFAULT_PITCH = 92
DEFAULT_AMPLITUDE = 140


def find_espeak() -> Optional[str]:
    return shutil.which("espeak-ng") or shutil.which("espeak")


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

    espeak = find_espeak()
    if not espeak:
        raise RuntimeError("espeak-ng not found. Install with: sudo apt install espeak-ng")

    if out_path is None:
        fd, name = tempfile.mkstemp(prefix="cozmo_tts_", suffix=".wav")
        os.close(fd)
        out_path = Path(name)

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
