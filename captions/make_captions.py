"""Word-timed captions from the narration track with faster-whisper (base model).
Output: CaptionWord[] JSON (word, startMs, endMs) and an SRT for upload.
Usage: python3 captions/make_captions.py NARRATION.wav OUT_DIR
Uses CUDA when a GPU is visible (pod), otherwise CPU int8 (local tests).
"""
import json, os, sys
import ctranslate2
from faster_whisper import WhisperModel

wav, outdir = sys.argv[1:3]
os.makedirs(outdir, exist_ok=True)
ROOT = "/workspace-global/models/whisper" if os.path.isdir("/workspace-global/models/whisper") else None

def run(device, compute):
    model = WhisperModel("base", device=device, compute_type=compute, download_root=ROOT)
    seg_iter, info = model.transcribe(wav, word_timestamps=True, language="en")
    return list(seg_iter)  # the generator must be consumed before the words exist

segments = None
if ctranslate2.get_cuda_device_count() > 0:
    try:
        segments = run("cuda", "float16"); print("CAPTIONS_DEVICE cuda", flush=True)
    except Exception as e:  # missing cuDNN or similar: fall back, and say so
        print(f"CAPTIONS_CUDA_FAILED {type(e).__name__}: {e}", flush=True)
if segments is None:
    segments = run("cpu", "int8"); print("CAPTIONS_DEVICE cpu", flush=True)

words = []
for seg in segments:
    for w in seg.words or []:
        text = w.word.strip()
        if not text:
            continue
        words.append({"word": text, "startMs": int(w.start * 1000), "endMs": int(w.end * 1000)})

with open(os.path.join(outdir, "captions.json"), "w", encoding="utf-8") as f:
    json.dump(words, f, ensure_ascii=False, indent=1)

def ts(ms):
    h, rem = divmod(ms, 3600000); m, rem = divmod(rem, 60000); s, ms2 = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms2:03}"

with open(os.path.join(outdir, "captions.srt"), "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        f.write(f"{i}\n{ts(int(seg.start*1000))} --> {ts(int(seg.end*1000))}\n{seg.text.strip()}\n\n")

print(f"CAPTIONS_DONE words={len(words)} segments={len(segments)}", flush=True)
