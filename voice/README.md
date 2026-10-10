# Voice

Barney's recordings for every MeeMee World game: one WAV file per line, named by the line's id (for example `num-mid-3.wav`).

- The lines themselves are listed in `kit/lines.json` (the world's: the map and the crew) and each game's `games/<id>/lines.json`. The build gathers them into `script.json`, which the game and the recording page read; don't edit `script.json` by hand, and don't rename the WAV files.
- The recording page shows each game's lines under the game's name. A newer game's line ids start with its id (`words-…`); MeeMee Rescue's don't, being older.
- Record with the recording page: https://barneyfin.github.io/mimi-world/record/ in Chrome on the PC. Choose this folder when it asks. It trims silence, makes every clip the same loudness (peaks never above −1 dB) and saves WAV, mono, 44.1 kHz.
- The game builds sentences from these pieces, so each number is recorded twice: `num-mid-` with a lift ("three…") and `num-end-` with a fall ("…seven.").
- The WAVs here are the originals. The build (`tools/make_audio.py`) makes the web copies in `docs/audio/voice/`, evens out their loudness and turns them into MP3. To redo a clip, record over it and ask Claude to rebuild.
- A line marked `"pending": true` in a `lines.json` is on the recording page but not in the game yet. Once it's recorded, take the mark off and the next full build uses it.
- No recording says the child's name: the website is public.
