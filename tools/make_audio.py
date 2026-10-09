"""Make the web audio for Mimi World: voice clips, music and sound effects, into docs/audio/.

Everything is brought to one loudness reference (-20 LUFS) so the game can mix by simple gains:
voice plays at full level, effects a little under it, and music well under it (see kit/audio.js).

Needs: ffmpeg on PATH, numpy, scipy, pyloudnorm.
Run from anywhere:  python tools/make_audio.py
"""
import io
import json
import pathlib
import subprocess
import sys

import numpy as np
import pyloudnorm as pyln
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import butter, sosfilt

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOICE = ROOT / "voice"
OUT = ROOT / "docs" / "audio"
RATE = 44100
REFERENCE = -20.0          # LUFS: every voice clip, and the music file, sit here
CEILING_DB = -1.0          # no sample above -1 dBFS
EFFECT_LEVELS = {          # LUFS for each effect: a little under the voice
    "chime": -21.0, "pop": -25.0, "whoosh": -27.0, "twinkle": -23.0, "tune": -21.0,
}
MUSIC_SOURCE = ROOT / "music" / "paws-in-the-milky-way.mp3"
MUSIC_END = 159.85         # the track stops abruptly at 159.9 s; end just before it
MUSIC_FADE = 1.5           # the end fades over 1.5 s into the restart (the player overlaps the copies)

METER = pyln.Meter(RATE, block_size=0.2)


def loudness(x):
    """Integrated loudness of a mono clip; short clips are padded so the meter can read them."""
    if len(x) < RATE * 0.6:
        x = np.concatenate([x, np.zeros(int(RATE * 0.6) - len(x))])
    return METER.integrated_loudness(x)


def limit(x, ceiling_db=CEILING_DB):
    """Look-ahead peak limiter: turns down only the few milliseconds around a peak."""
    ceiling = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(x), 1e-9))
    w = int(RATE * 0.005)
    g = minimum_filter1d(need, size=2 * w + 1)
    g = uniform_filter1d(g, size=w + 1)
    return np.clip(x * g, -ceiling, ceiling)


def to_level(x, target):
    gain_db = target - loudness(x)
    y = limit(x * 10 ** (gain_db / 20))
    return y, gain_db


def encode(x, path, bitrate="64k", channels=1):
    """Float samples (-1..1) -> MP3 via ffmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    buf = io.BytesIO()
    wavfile.write(buf, RATE, pcm)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "wav", "-i", "pipe:0", "-map_metadata", "-1",
                    "-ac", str(channels), "-ar", str(RATE), "-codec:a", "libmp3lame", "-b:a", bitrate, str(path)],
                   input=buf.getvalue(), check=True)


def read_wav(path):
    sr, x = wavfile.read(path)
    if sr != RATE:
        raise SystemExit(f"{path.name}: {sr} Hz, expected {RATE}")
    x = x.astype(np.float64) / 32768.0
    return x.mean(axis=1) if x.ndim > 1 else x


# ---------------------------------------------------------------- voice

def make_voice():
    script = json.loads((VOICE / "script.json").read_text(encoding="utf-8"))
    missing = [c["id"] for c in script["clips"] if not (VOICE / f"{c['id']}.wav").exists()]
    if missing:
        raise SystemExit("Voice recordings missing (record them with docs/record/): " + ", ".join(missing))
    clips = {}
    for c in script["clips"]:
        x = read_wav(VOICE / f"{c['id']}.wav")
        before = loudness(x)
        y, gain = to_level(x, REFERENCE)
        if gain > 8:
            print(f"  warning: {c['id']} needed {gain:+.1f} dB; consider re-recording it")
        encode(y, OUT / "voice" / f"{c['id']}.mp3", "64k")
        clips[c["id"]] = {"dur": round(len(y) / RATE, 3), "lufs_before": round(before, 1), "gain_db": round(gain, 1)}
    return clips


# ---------------------------------------------------------------- music

def make_music():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(MUSIC_SOURCE), "-t", f"{MUSIC_END}",
                          "-af", f"afade=t=out:st={MUSIC_END - MUSIC_FADE}:d={MUSIC_FADE}",
                          "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64)   # mono: half the memory on the tablet
    gain_db = REFERENCE - pyln.Meter(RATE).integrated_loudness(x)
    x = x * 10 ** (gain_db / 20)
    peak = np.abs(x).max()
    if peak > 10 ** (CEILING_DB / 20):
        x = x * (10 ** (CEILING_DB / 20) / peak)
    OUT.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    buf = io.BytesIO()
    wavfile.write(buf, RATE, pcm)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "wav", "-i", "pipe:0", "-map_metadata", "-1",
                    "-ac", "1", "-codec:a", "libmp3lame", "-b:a", "80k", str(OUT / "music.mp3")], input=buf.getvalue(), check=True)
    return {"dur": round(len(x) / RATE, 3), "fade": MUSIC_FADE, "gain_db": round(gain_db, 1)}


# ---------------------------------------------------------------- effects (all synthesised here: nothing borrowed)

def env(n, attack, decay):
    t = np.arange(n) / RATE
    a = np.minimum(1, t / max(attack, 1e-4))
    return a * np.exp(-t / decay)


def bell(freq, dur, decay=0.35, partial=2.76, mix=0.25):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    tone = np.sin(2 * np.pi * freq * t) + mix * np.sin(2 * np.pi * freq * partial * t) * np.exp(-t / (decay * 0.4))
    return tone * env(n, 0.004, decay)


def place(buf, x, at):
    i = int(RATE * at)
    buf[i:i + len(x)] += x[: max(0, len(buf) - i)]
    return buf


def sfx_pop():
    # a soft rising bubble: snaps a Mimi into place
    n = int(RATE * 0.12)
    t = np.arange(n) / RATE
    f = 420 + 380 * (1 - np.exp(-t / 0.02))
    phase = 2 * np.pi * np.cumsum(f) / RATE
    return np.sin(phase) * env(n, 0.003, 0.03)


def sfx_whoosh():
    # filtered noise sweeping down: a Mimi floating home
    n = int(RATE * 0.34)
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    hop = 512
    for i in range(0, n, hop):
        frac = i / n
        centre = 1800 * (1 - frac) + 380 * frac
        sos = butter(2, [centre * 0.7, centre * 1.4], btype="band", fs=RATE, output="sos")
        seg = noise[max(0, i - 2048): i + hop]
        out[i:i + hop] = sosfilt(sos, seg)[-min(hop, n - i):]
    shape = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
    return out * shape


def sfx_twinkle():
    # three high bell notes rising: a star turning peach
    buf = np.zeros(int(RATE * 0.9))
    for k, f in enumerate([1318.5, 1661.2, 1975.5]):
        place(buf, bell(f, 0.7, 0.22, mix=0.18), k * 0.075)
    return buf


def sfx_tune():
    # end-of-round tune: a little rising arpeggio and a held chord
    buf = np.zeros(int(RATE * 2.6))
    notes = [(392.0, 0.0), (523.3, 0.16), (659.3, 0.32), (784.0, 0.48), (659.3, 0.72), (784.0, 0.88), (1046.5, 1.04)]
    for f, at in notes:
        place(buf, bell(f, 0.9, 0.3, partial=2.0, mix=0.3), at)
    for f in (523.3, 659.3, 784.0, 1046.5):
        place(buf, 0.45 * bell(f, 1.5, 0.6, partial=2.0, mix=0.15), 1.04)
    return buf


def make_effects():
    out = {}
    chime_raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ROOT / "kit" / "chime-source.mp3"),
                                "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"], capture_output=True, check=True).stdout
    sources = {
        "chime": np.frombuffer(chime_raw, np.float32).astype(np.float64),
        "pop": sfx_pop(), "whoosh": sfx_whoosh(), "twinkle": sfx_twinkle(), "tune": sfx_tune(),
    }
    for name, x in sources.items():
        x = x / (np.abs(x).max() + 1e-9) * 0.5
        y, gain = to_level(x, EFFECT_LEVELS[name])
        encode(y, OUT / "sfx" / f"{name}.mp3", "96k")
        out[name] = {"dur": round(len(y) / RATE, 3), "lufs": EFFECT_LEVELS[name]}
    return out


def main():
    print("voice...")
    voice = make_voice()
    print("music...")
    music = make_music()
    print("effects...")
    effects = make_effects()
    manifest = {"reference_lufs": REFERENCE, "voice": voice, "music": music, "effects": effects}
    (ROOT / "tools" / "audio-manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8", newline="\n")
    size = sum(f.stat().st_size for f in OUT.rglob("*.mp3"))
    print(f"audio: {len(list(OUT.rglob('*.mp3')))} files, {size / 1e6:.2f} MB")
    return manifest


if __name__ == "__main__":
    sys.exit(main() and 0)
