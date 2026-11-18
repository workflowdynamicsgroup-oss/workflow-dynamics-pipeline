"""Word-timed captions from the narration track with Whisper (base model).
Output: CaptionWord[] JSON (word, startMs, endMs) and an SRT for upload.
Usage: python3 captions/make_captions.py NARRATION.wav OUT_DIR
"""
import json, os, sys
import whisper

wav, outdir = sys.argv[1:3]
os.makedirs(outdir, exist_ok=True)
model = whisper.load_model("base")
result = model.transcribe(wav, word_timestamps=True, language="en")

words = []
for seg in result["segments"]:
    for w in seg.get("words", []):
        text = w["word"].strip()
        if not text:
            continue
        words.append({"word": text, "startMs": int(w["start"] * 1000), "endMs": int(w["end"] * 1000)})

with open(os.path.join(outdir, "captions.json"), "w", encoding="utf-8") as f:
    json.dump(words, f, ensure_ascii=False, indent=1)

def ts(ms):
    h, rem = divmod(ms, 3600000); m, rem = divmod(rem, 60000); s, ms2 = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms2:03}"

with open(os.path.join(outdir, "captions.srt"), "w", encoding="utf-8") as f:
    for i, seg in enumerate(result["segments"], 1):
        f.write(f"{i}\n{ts(int(seg['start']*1000))} --> {ts(int(seg['end']*1000))}\n{seg['text'].strip()}\n\n")

print(f"CAPTIONS_DONE words={len(words)} segments={len(result['segments'])}", flush=True)
