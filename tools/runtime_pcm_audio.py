"""Frozen-only audio adapter: FFmpeg already provides 16-kHz mono PCM WAV chunks.

Avoids shipping a second FFmpeg build through PyAV. Implements the two audio helpers
used by faster-whisper 1.2.1; decoding any other input fails explicitly.
"""
import sys
import types
import wave
import numpy as np


def decode_audio(input_file, sampling_rate=16000, split_stereo=False):
    if split_stereo:
        raise ValueError("VideoWissen erwartet Mono-Audio.")
    with wave.open(input_file, "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2 or source.getframerate() != sampling_rate:
            raise ValueError("VideoWissen erwartet von FFmpeg erzeugtes Mono-PCM-WAV mit 16 Bit und 16 kHz.")
        frames = source.readframes(source.getnframes())
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def pad_or_trim(array, length=3000, *, axis=-1):
    if array.shape[axis] > length:
        array = array.take(indices=range(length), axis=axis)
    if array.shape[axis] < length:
        widths = [(0, 0)] * array.ndim
        widths[axis] = (0, length - array.shape[axis])
        array = np.pad(array, widths)
    return array


adapter = types.ModuleType("faster_whisper.audio")
adapter.decode_audio = decode_audio
adapter.pad_or_trim = pad_or_trim
sys.modules["faster_whisper.audio"] = adapter
