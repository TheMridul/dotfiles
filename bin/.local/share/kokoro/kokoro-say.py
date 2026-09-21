#!/usr/bin/env python3
"""Read stdin with Kokoro-82M and stream raw 24kHz s16le PCM to stdout.

Shaped to be a drop-in for `piper-tts --output_raw` inside read-aloud.

Two things matter for latency. The fp32 model is ~4.6x faster than the int8
one on this CPU (RTF 0.21 vs 1.00; ConvInteger kernels are slow), and text is
synthesised a sentence at a time so playback starts before the whole passage
is done.
"""
import os
import re
import sys

import numpy as np
import onnxruntime as ort
from kokoro_onnx import Kokoro

HERE = os.path.expanduser("~/.local/share/kokoro")
MODEL = os.environ.get("KOKORO_MODEL", os.path.join(HERE, "kokoro-v1.0.onnx"))
VOICE = os.environ.get("KOKORO_VOICE", "af_heart")
SPEED = float(os.environ.get("KOKORO_SPEED", "1.0"))
# 8 beats both 4 and 16 here; 16 oversubscribes and doubles the time.
THREADS = int(os.environ.get("KOKORO_THREADS", "8"))
MAX_CHUNK = 350

text = sys.stdin.read().strip()
if not text:
    sys.exit(0)


def chunks(s):
    """Sentences, with over-long ones split on commas then hard-wrapped."""
    for sentence in re.split(r"(?<=[.!?])\s+", s):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= MAX_CHUNK:
            yield sentence
            continue
        piece = ""
        for part in re.split(r"(?<=,)\s+", sentence):
            if len(piece) + len(part) + 1 > MAX_CHUNK and piece:
                yield piece
                piece = part
            else:
                piece = f"{piece} {part}".strip()
        while len(piece) > MAX_CHUNK:
            yield piece[:MAX_CHUNK]
            piece = piece[MAX_CHUNK:]
        if piece:
            yield piece


options = ort.SessionOptions()
options.intra_op_num_threads = THREADS
options.inter_op_num_threads = 1
options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
session = ort.InferenceSession(MODEL, options, providers=["CPUExecutionProvider"])
kokoro = Kokoro.from_session(session, os.path.join(HERE, "voices-v1.0.bin"))

out = sys.stdout.buffer
for chunk in chunks(text):
    samples, _ = kokoro.create(chunk, voice=VOICE, speed=SPEED, lang="en-us")
    pcm = np.clip(samples, -1.0, 1.0)
    try:
        out.write((pcm * 32767).astype("<i2").tobytes())
        out.flush()
    except BrokenPipeError:
        # aplay was killed by a second keypress.
        break
