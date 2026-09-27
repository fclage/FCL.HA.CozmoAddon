"""WAV → Cozmo OutputAudio with a Python 3.13+ safe u-law encoder.

pycozmo's u_law_encoding can return values outside 0..255; assigning those
to a bytearray raises ValueError on modern Python. Mask to 8 bits.
"""

from __future__ import annotations

import struct
import wave
from typing import List

import pycozmo
from pycozmo import protocol_encoder

MULAW_MAX = 0x7FFF
MULAW_BIAS = 132


def u_law_encoding(sample: int) -> int:
    mask = 0x4000
    position = 14
    sign = 0
    if sample < 0:
        sample = -sample
        sign = 0x80
    sample += MULAW_BIAS
    if sample > MULAW_MAX:
        sample = MULAW_MAX
    while (sample & mask) != mask and position >= 7:
        mask >>= 1
        position -= 1
    lsb = (sample >> (position - 4)) & 0x0F
    return (-(~(sign | ((position - 7) << 4) | lsb))) & 0xFF


def bytes_to_cozmo(byte_string: bytes, rate_correction: int, channels: int) -> bytearray:
    out = bytearray(744)
    n = channels * rate_correction
    samples = struct.unpack(f"{len(byte_string) // 2}h", byte_string)[0::n]
    for i, s in enumerate(samples):
        if i >= 744:
            break
        out[i] = u_law_encoding(s)
    return out


def load_wav(filename: str) -> List[protocol_encoder.OutputAudio]:
    with wave.open(filename, "r") as w:
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        if sampwidth != 2 or framerate not in (22050, 48000):
            raise ValueError("Invalid audio format: need 16-bit PCM at 22050 or 48000 Hz")
        ratediv = 2 if framerate == 48000 else 1
        channels = w.getnchannels()
        pkts: List[protocol_encoder.OutputAudio] = []
        while True:
            frame_in = w.readframes(744 * ratediv)
            if not frame_in:
                break
            frame_out = bytes_to_cozmo(frame_in, ratediv, channels)
            pkts.append(protocol_encoder.OutputAudio(samples=frame_out))
        return pkts


def play_wav_on_client(cli: pycozmo.Client, filename: str) -> None:
    pkts = load_wav(filename)
    cli.anim_controller.play_audio(pkts)
