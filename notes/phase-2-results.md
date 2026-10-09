# Phase 2 results: voice script and recordings

Recorded 8–9 October 2026 on Barney's headset microphone with the recording page (docs/record/), in Chrome on the PC. 44 clips, as pieces (option A).

**Status:** all 44 recorded and checked by machine. The gate (a few lines sound clear on the Fire's speaker) is checked on the tablet with phase 3's Sound panel: grown-ups area › Sound.

## What was checked

| Check | Result |
| --- | --- |
| Every clip in the script recorded | 44 of 44 |
| Format | All WAV, mono, 44.1 kHz, 16-bit |
| Clipping | None: every peak at −1 dB or below |
| Silence trimmed | 0–60 ms before the voice, 10–120 ms after: tight enough for joining |
| Loudness | 42 of 44 between −19.0 and −22.9 LUFS (middle −20.4). "six" (both versions) was 4.5–5.7 LU below the middle, because the word is mostly hiss. |
| Right word in each number clip | Each "num-end" clip matched its own "num-mid" twin by sound (11 of 11). A basic offline speech recogniser named the expected number in 18 of 22; the four it missed (six twice, zero and four at the end of a sentence) are ones it handles badly, and each matched its twin. |
| Lift and fall | Not measurable: the voice drops into a low creak at the end of most words, which defeats the pitch tracker. Judge it by ear (see below). |

## What the build does with them

- The WAVs in `voice/` stay as recorded. `tools/make_audio.py` makes the web copies in `docs/audio/voice/`: each clip brought to the same loudness (−20 LUFS; "six" raised by 5–6 dB, with a gentle peak limiter so nothing passes −1 dB), then MP3 at 64 kbps mono. After that, all 44 sit within 1.1 LU of each other.
- The game joins pieces with 30 ms between them and 350 ms between sentences.

## To check on the Fire (the phase 2 gate)

Grown-ups area (hold the lock, bottom left, for 3 seconds) › **Sound**:
- "Three and four make seven": does it sound like one sentence, or a list of words?
- "Missing part question" and "Missing whole question": clear over the music?
- The six clips: "six" is the quietest word.

If a sentence sounds choppy, the fix is to re-record the num-mid pieces with more lift; nothing else changes.
