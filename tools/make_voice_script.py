"""Write voice/script.json: every clip MeeMee Rescue needs (option A: pieces)."""
import json
import pathlib

WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]

clips = []


def add(group, cid, words, how, pending=False):
    """pending: on the recording page, but not used by the game until it has been recorded (the build skips it till then)."""
    clip = {"id": cid, "group": group, "words": words, "how": how}
    if pending:
        clip["pending"] = True
    clips.append(clip)


for n, w in enumerate(WORDS):
    add("Numbers, mid-sentence", f"num-mid-{n}", w,
        "Lift at the end, as if more is coming: counting, or the first number in \"three and four\".")
for n, w in enumerate(WORDS):
    add("Numbers, end of sentence", f"num-end-{n}", w,
        "Fall at the end, as the last word of a sentence: \"…make seven.\"")

add("Joining words", "and", "and", "As in \"three and four\". Short and light.")
add("Joining words", "make", "make", "As in \"…make seven\". Keep the voice up: a number follows.")

add("Questions", "q-lets-make", "Let's make…", "Keep the voice up: a number follows (\"Let's make… seven\").")
add("Questions", "q-weve-got", "We've got…", "Keep the voice up: a number follows (\"We've got… three\").")
add("Questions", "q-how-many-more", "How many more?", "A real question, curious and warm.")
add("Questions", "q-how-many-altogether", "How many altogether?", "A real question, curious and warm.")
add("Questions", "q-count-on-from", "Let's count on from…", "Keep the voice up: a number follows.")

add("Praise", "praise-found-it", "You found it!", "Pleased and warm. Not too loud.")
add("Praise", "praise-thats-right", "That's right!", "Pleased and warm.")
add("Praise", "praise-super-counting", "Super counting!", "Pleased and warm.")
add("Praise", "praise-brilliant-rescuing", "Brilliant rescuing!", "Pleased and warm.")
add("Praise", "praise-well-done", "Well done!", "Pleased and warm.")

add("Try again", "again-try-again", "Let's try again.", "Cheerful and calm, never disappointed.")
add("Try again", "again-look-again", "Let's look again.", "Cheerful and calm.")
add("Try again", "again-count-with-me", "Count them with me.", "Inviting, as if counting side by side.")

add("Checking", "tap-scruffles", "Tap Scruffles when you're ready.",
    "Friendly and clear, like showing someone a new button. Warm, not bossy.")

add("Too many", "too-many", "That's too many. Take one back.", "Light, a little playful.")

add("Rounds", "round-ready", "Ready for a rescue?", "Excited, inviting.")
add("Rounds", "round-rescued-all", "You rescued all the MeeMee!", "Big finish: proud and happy.")
add("Rounds", "round-another", "Another rescue?", "Inviting.")

add("Map", "map-welcome", "Welcome to MeeMee World!", "Warm welcome.")
add("Map", "map-mimi-rescue", "MeeMee Rescue!", "Announcing the game's name.")
add("Map", "map-not-ready", "That planet isn't ready yet.", "Gentle, no disappointment.")

# The crew screen (phase 4, 0.4.1; recorded 9 October). The game builds "Moggles is the lookout." from pieces, like the numbers.
add("Crew", "crew-jobs", "Let's give the crew their jobs!", "Excited, inviting.")
add("Crew", "crew-ready", "The crew are ready!", "Pleased, a big finish.")
add("Crew", "name-moggles", "Moggles…", "Keep the voice up: more follows (\"Moggles… is the… lookout.\").")
add("Crew", "name-snuffles", "Snuffles…", "Keep the voice up: more follows.")
add("Crew", "is-the", "is the…", "Short and light, voice up: a job follows.")
add("Crew", "job-lookout", "lookout.", "Fall at the end: the last word of the sentence.")
add("Crew", "job-engineer", "engineer.", "Fall at the end: the last word of the sentence.")
add("Crew", "job-navigator", "navigator.", "Fall at the end: the last word of the sentence.")
add("Crew", "job-cook", "cook.", "Fall at the end: the last word of the sentence.")

assert len(clips) == 54, len(clips)
assert len({c["id"] for c in clips}) == 54

script = {
    "game": "MeeMee Rescue",
    "version": 1,
    "format": "WAV, mono, 44.1 kHz, 16-bit; silence trimmed; loudness normalised; peaks at most -1 dB",
    "clips": clips,
}
out = pathlib.Path(__file__).resolve().parent.parent / "voice" / "script.json"
out.write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(len(clips), "clips ->", out)
