"""FLUX.1-schnell stills, 1024x1024, 4 steps, guidance 0, CPU offload.
Verified 2026-11-16 on A40 (peak VRAM 23,133 MB). Needs HF_TOKEN (gated repo).
Usage: python3 flux/run_flux.py PROMPTS.txt OUTDIR
Env FLUX_WEIGHTS: path of the local copy of flux1-schnell.safetensors (default: the volume path; copy it to pod disk first).
PROMPTS.txt holds one prompt per line.
"""
import os, sys, time, torch
from diffusers import FluxPipeline, FluxTransformer2DModel

prompts_path, outdir = sys.argv[1:3]
WEIGHTS = os.environ.get("FLUX_WEIGHTS", "/workspace-global/models/flux1-schnell/flux1-schnell.safetensors")
t0 = time.time()
os.makedirs(outdir, exist_ok=True)
prompts = [l.strip() for l in open(prompts_path, encoding="utf-8") if l.strip()]
tr = FluxTransformer2DModel.from_single_file(
    WEIGHTS, torch_dtype=torch.bfloat16)
pipe = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", transformer=tr, torch_dtype=torch.bfloat16)
pipe.enable_model_cpu_offload()
print(f"FLUX_LOADED seconds={time.time()-t0:.0f}", flush=True)
for i, p in enumerate(prompts, 1):
    t1 = time.time()
    img = pipe(p, num_inference_steps=4, guidance_scale=0.0, height=1024, width=1024).images[0]
    path = os.path.join(outdir, f"photo_{i}.png")
    img.save(path)
    print(f"IMG_DONE {i} {path} seconds={time.time()-t1:.0f} peak_vram_mb={torch.cuda.max_memory_allocated()//2**20}", flush=True)
