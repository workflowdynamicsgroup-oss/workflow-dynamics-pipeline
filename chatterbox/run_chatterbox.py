"""Chatterbox narration with the cloned voice.
Settings verified 2026-11-16: exaggeration 0.5, cfg_weight 0.45.
Usage: python3 chatterbox/run_chatterbox.py SCRIPT.txt OUT.wav REFERENCE.wav
"""
import sys
import torch
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

script_path, out_path, ref_path = sys.argv[1:4]
text = open(script_path, encoding="utf-8").read().strip()
model = ChatterboxTTS.from_local("/workspace-global/chatterbox", "cuda")
# Split into pieces; the 35.5 s test ran as 3 pieces. Keep each piece short.
pieces = [p.strip() for p in text.split("\n\n") if p.strip()]
wavs = []
for p in pieces:
    wav = model.generate(p, audio_prompt_path=ref_path, exaggeration=0.5, cfg_weight=0.45)
    wavs.append(wav)
ta.save(out_path, torch.cat(wavs, dim=1), model.sr)
print(f"CB_DONE pieces={len(pieces)} out={out_path}", flush=True)
