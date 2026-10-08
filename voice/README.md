# Voice

Barney's recordings for Mimi Rescue: one WAV file per clip, named by the clip's id (for example `num-mid-3.wav`).

- `script.json` lists every clip: its id, the words, and how to say them. The game and the recording page both read it. Don't rename the WAV files.
- Record with the recording page: https://barneyfin.github.io/mimi-world/record/ in Chrome on the PC. Choose this folder when it asks. It trims silence, makes every clip the same loudness (peaks never above −1 dB) and saves WAV, mono, 44.1 kHz.
- The game builds sentences from these pieces, so each number is recorded twice: `num-mid-` with a lift ("three…") and `num-end-` with a fall ("…seven.").
- No recording says Eli's name: the website is public.
