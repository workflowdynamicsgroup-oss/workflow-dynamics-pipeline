"""Backdrop removal for the Ditto avatar video: u2net_human_seg run directly with onnxruntime (same pre/post steps as rembg).
Usage: python3 cutout/make_cutout.py IN.mp4 OUTDIR   (env MODEL=path to u2net_human_seg.onnx, BATCH=16)
Writes OUTDIR/alpha.mp4 (gray mask video, same size/fps/frames as the input). Prints CUTOUT_PROVIDER, CUTOUT_PROGRESS and CUTOUT_DONE frames=N seconds=S fps=F.
"""
import json, os, subprocess, sys, time
import numpy as np, cv2, onnxruntime as ort

src, outdir = sys.argv[1:3]
os.makedirs(outdir, exist_ok=True)
MODEL = os.environ.get("MODEL", "/root/.u2net/u2net_human_seg.onnx")
BATCH = int(os.environ.get("BATCH", "16"))
pr = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
    "stream=width,height,r_frame_rate,nb_read_packets", "-of", "json", src]))["streams"][0]
W, H = int(pr["width"]), int(pr["height"]); num, den = pr["r_frame_rate"].split("/"); FPS = float(num) / float(den)
TOTAL = int(pr["nb_read_packets"])
sess = ort.InferenceSession(MODEL, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
print("CUTOUT_PROVIDER", sess.get_providers()[0], f"size={W}x{H} fps={FPS:g} frames={TOTAL} batch={BATCH}", flush=True)
if os.environ.get("REQUIRE_CUDA") == "1" and sess.get_providers()[0] != "CUDAExecutionProvider":
    print("CUTOUT_FAIL CUDAExecutionProvider is not active (CPU would take about an hour per 140 s of video)", flush=True); sys.exit(3)
inp = sess.get_inputs()[0].name
MEAN = np.array([0.485, 0.456, 0.406], np.float32); STD = np.array([0.229, 0.224, 0.225], np.float32)

def prep(fr):  # same steps as rembg's u2net: 320x320, divide by max, normalise, CHW
    im = cv2.resize(fr, (320, 320), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    im = im / max(float(im.max()), 1e-6)
    return ((im - MEAN) / STD).transpose(2, 0, 1)

def infer(frames):
    x = np.stack([prep(f) for f in frames]).astype(np.float32)
    try:
        pred = sess.run(None, {inp: x})[0]
    except Exception:  # model with a fixed batch of 1
        pred = np.concatenate([sess.run(None, {inp: x[i:i+1]})[0] for i in range(len(x))])
    out = []
    for p in pred[:, 0]:
        p = (p - p.min()) / max(float(p.max() - p.min()), 1e-6)
        m = cv2.resize((p * 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_LANCZOS4)
        out.append(m)
    return out

dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", f"{FPS:g}", "-i", "-",
    "-c:v", "libx264", "-crf", "10", "-preset", "veryfast", "-pix_fmt", "yuv420p", os.path.join(outdir, "alpha.mp4")], stdin=subprocess.PIPE)
t0 = time.time(); n = 0; buf = []
def flush():
    global n, buf
    if not buf: return
    for m in infer(buf): enc.stdin.write(m.tobytes())
    n += len(buf); buf = []
    if (n // BATCH) % 20 == 0: print(f"CUTOUT_PROGRESS {n}/{TOTAL} {time.time()-t0:.0f}s", flush=True)
fsz = W * H * 3
while True:
    raw = dec.stdout.read(fsz)
    if len(raw) < fsz: break
    buf.append(np.frombuffer(raw, np.uint8).reshape(H, W, 3))
    if len(buf) == BATCH: flush()
flush()
enc.stdin.close(); enc.wait(); dec.wait()
dt = time.time() - t0
print(f"CUTOUT_DONE frames={n} seconds={dt:.0f} fps={n/dt:.1f}", flush=True)
sys.exit(0 if n == TOTAL and enc.returncode == 0 else 1)
