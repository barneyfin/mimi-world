# Voice

Barney's recordings for MeeMee Rescue: one WAV file per clip, named by the clip's id (for example `num-mid-3.wav`).

- `script.json` lists every clip: its id, the words, and how to say them. The game and the recording page both read it. Don't rename the WAV files. (`tools/make_voice_script.py` writes `script.json`.)
- Record with the recording page: https://barneyfin.github.io/mimi-world/record/ in Chrome on the PC. Choose this folder when it asks. It trims silence, makes every clip the same loudness (peaks never above −1 dB) and saves WAV, mono, 44.1 kHz.
- The game builds sentences from these pieces, so each number is recorded twice: `num-mid-` with a lift ("three…") and `num-end-` with a fall ("…seven.").
- The WAVs here are the originals. The build (`tools/make_audio.py`) makes the web copies in `docs/audio/voice/`, evens out their loudness and turns them into MP3. To redo a clip, record over it and ask Claude to rebuild.
- A clip marked `"pending": true` in `script.json` is on the recording page but not in the game yet. Once it's recorded, the next build can use it.
- No recording says the child's name: the website is public.
