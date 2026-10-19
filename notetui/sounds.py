"""Reminder sounds, one per importance level, played through PipeWire (pw-play).

If a Piper voice model is installed, each reminder instead says its
importance out loud ("Note-tea, ui. Importance: 0.") in that voice. Put the
model at ~/.local/share/notetui/voices/en_GB-alan-medium.onnx (or point
NOTETUI_VOICE_MODEL at another one); Piper runs from this Python, or from
NOTETUI_PIPER_PYTHON. The phrases are made once and kept. Without a voice,
or if it can't be made, the marimba sound below plays instead.

All sounds are a soft wooden marimba, with phrases that fall in pitch.
More urgent = more notes, higher and faster:

    !0      fast four-note falling run, twice
    !1      three notes falling
    !2      two notes falling onto a low chord
    !3      one soft chord
    !4      one low, soft note (also points without importance)
    !5      two quick wooden knocks (daily items)

Made in plain Python the first time they're needed and kept in
~/.local/share/notetui/sounds/.

    notetui-reminders --demo     # hear every sound once
"""

import math
import os
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

RATE = 44100
VERSION = "2"  # bump after changing a sound, so the files are made again
LEAD_IN = 0.5
"""Seconds of silence before every sound: PipeWire wakes a sleeping output on
play and swallows the first moment, which cut the start of the voice off."""
SOUND_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "notetui" / "sounds"

# The Python that has Piper installed, and the voice; override with these env vars
PIPER_PYTHON = Path(os.environ.get("NOTETUI_PIPER_PYTHON", sys.executable))
VOICE_MODEL = Path(os.environ.get(
    "NOTETUI_VOICE_MODEL", SOUND_DIR.parent / "voices" / "en_GB-alan-medium.onnx"
))
VOICE_VERSION = "6"  # bump after changing the phrase, so the files are made again


def phrase(priority: int | None) -> str:
    # Spelled the way it should sound: "NoteTUI" written as one word comes out garbled
    if priority is None:
        return "Note-tea, ui. No importance."
    return f"Note-tea, ui. Importance: {priority}."

# Note frequencies (Hz)
D3, F3, C4, E4, G4, A4, C5, D5, E5, F5, G5, A5, C6 = (
    146.83, 174.61, 261.63, 329.63, 392.00, 440.00, 523.25, 587.33, 659.25, 698.46, 783.99, 880.00, 1046.50,
)


def _marimba(freq: float, seconds: float = 1.2, level: float = 1.0, ring: float = 0.45) -> list[float]:
    """One marimba strike: a warm fundamental plus the bar's tuned overtones
    (about 4x and 10x), which die away fast so nothing stays bright or metallic."""
    partials = ((1.0, 1.0, ring), (3.93, 0.30, ring * 0.16), (9.2, 0.07, ring * 0.04))
    samples = []
    for i in range(int(seconds * RATE)):
        t = i / RATE
        attack = 0.5 - 0.5 * math.cos(math.pi * t / 0.003) if t < 0.003 else 1.0  # 3 ms, no click
        value = sum(a * math.sin(2 * math.pi * freq * r * t) * math.exp(-t / d) for r, a, d in partials)
        samples.append(level * attack * value)
    return samples


def _mix(events: list[tuple[float, list[float]]]) -> list[float]:
    """Lay (start time, samples) events on one track."""
    length = max(int(at * RATE) + len(s) for at, s in events)
    out = [0.0] * length
    for at, s in events:
        start = int(at * RATE)
        for i, v in enumerate(s):
            out[start + i] += v
    return out


def _level0() -> list[float]:
    run = (C6, A5, F5, D5)
    events = []
    for repeat in (0.0, 0.62):
        for n, f in enumerate(run):
            events.append((repeat + n * 0.085, _marimba(f, 0.9, 0.9 if n else 1.0, ring=0.3)))
    return _mix(events)


def _level1() -> list[float]:
    return _mix([(n * 0.15, _marimba(f, 1.2, 1.0 - n * 0.1)) for n, f in enumerate((G5, E5, C5))])


def _level2() -> list[float]:
    return _mix([
        (0.0, _marimba(E5, 1.0, 0.9)),
        (0.22, _marimba(C5, 1.5, 0.8, ring=0.55)),
        (0.22, _marimba(G4, 1.5, 0.6, ring=0.55)),
    ])


def _level3() -> list[float]:
    return _mix([(0.0, _marimba(A4, 1.6, 0.7, ring=0.6)), (0.0, _marimba(E4, 1.6, 0.6, ring=0.6))])


def _level4() -> list[float]:
    return _marimba(C4, 1.6, 0.6, ring=0.6)


def _level5() -> list[float]:
    # Short, damped low strikes: a knock more than a note
    return _mix([(0.0, _marimba(F3, 0.25, 1.0, ring=0.05)), (0.17, _marimba(D3, 0.3, 0.9, ring=0.06))])


SOUNDS = {0: _level0, 1: _level1, 2: _level2, 3: _level3, 4: _level4, 5: _level5}


def _write(path: Path, samples: list[float]) -> None:
    peak = max(abs(s) for s in samples) or 1.0
    fade = int(0.05 * RATE)  # end in silence
    frames = bytearray(b"\x00\x00" * int(LEAD_IN * RATE))
    for i, s in enumerate(samples):
        gain = min(1.0, (len(samples) - i) / fade)
        frames += struct.pack("<h", int(s / peak * 0.7 * 32767 * gain))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    tmp.replace(path)


def sound_file(priority: int | None) -> Path:
    """The wav for an importance level (made the first time)."""
    level = 4 if priority is None else priority
    path = SOUND_DIR / f"level{level}-v{VERSION}.wav"
    if not path.exists():
        _write(path, SOUNDS[level]())
    return path


def _add_lead_in(source: Path, path: Path) -> None:
    """Copy a wav to path with LEAD_IN seconds of silence in front."""
    with wave.open(str(source)) as w:
        params, frames = w.getparams(), w.readframes(w.getnframes())
    silence = b"\x00" * (int(LEAD_IN * params.framerate) * params.sampwidth * params.nchannels)
    out = path.with_suffix(".pad.tmp")
    with wave.open(str(out), "wb") as w:
        w.setparams(params)
        w.writeframes(silence + frames)
    out.replace(path)
    source.unlink(missing_ok=True)


def voice_file(priority: int | None) -> Path | None:
    """The spoken phrase for an importance level, made with Piper the first time.
    None if Piper or the voice model isn't available."""
    name = "none" if priority is None else str(priority)
    path = SOUND_DIR / f"voice-{name}-v{VOICE_VERSION}.wav"
    if path.exists():
        return path
    if not PIPER_PYTHON.exists() or not VOICE_MODEL.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.wav")
    try:
        subprocess.run(
            [str(PIPER_PYTHON), "-m", "piper", "-m", str(VOICE_MODEL), "-f", str(tmp), "--sentence-silence", "0.3"],
            input=phrase(priority).encode(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
            check=True,
        )
        _add_lead_in(tmp, path)
        return path
    except (OSError, subprocess.SubprocessError) as e:
        print(f"voice failed: {e}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return None


def prepare() -> None:
    """Make every spoken phrase ahead of time, so a reminder never waits on Piper."""
    for level in (*SOUNDS, None):
        voice_file(level)


def play(priority: int | None) -> None:
    """Say a level's phrase in the background (the marimba sound if the voice isn't
    available; silently nothing if neither plays)."""
    try:
        subprocess.Popen(
            ["pw-play", str(voice_file(priority) or sound_file(priority))],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as e:
        print(f"sound failed: {e}", file=sys.stderr)


def demo() -> None:
    """Play every level's sound once, with a pause between them."""
    names = {0: "mega important", 1: "very important", 2: "important",
             3: "not so important", 4: "not important / no importance", 5: "daily item"}
    for level in SOUNDS:
        print(f"!{level}  {names[level]}", flush=True)
        subprocess.run(["pw-play", str(voice_file(level) or sound_file(level))], check=False)
        time.sleep(1.0)
