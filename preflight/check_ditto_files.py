#!/usr/bin/env python3
# Fails in seconds if any file the Ditto run needs is missing. Usage: check_ditto_files.py DATA_ROOT CFG_PKL AUDIO PHOTO
import os, pickle, sys, shutil
data_root, cfg_pkl, audio, photo = sys.argv[1:5]
bad = []
for label, p in (("DATA_ROOT", data_root), ("CFG_PKL", cfg_pkl), ("AUDIO", audio), ("PHOTO", photo)):
    ok = os.path.exists(p) and (os.path.isdir(p) or os.path.getsize(p) > 0)
    print(f"{'OK  ' if ok else 'MISSING'} {label} {p}")
    if not ok: bad.append(label)
for tool in ("ffmpeg",):
    path = shutil.which(tool)
    print(f"{'OK  ' if path else 'MISSING'} {tool} {path or ''}")
    if not path: bad.append(tool)
if os.path.exists(cfg_pkl):
    cfg = pickle.load(open(cfg_pkl, "rb"))
    exts = (".pt", ".pth", ".onnx", ".task", ".npy", ".pkl", ".engine", ".trt")
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): yield from walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o: yield from walk(v)
        elif isinstance(o, str) and o.endswith(exts):
            yield o
    seen = set()
    for s in walk(cfg):
        if s in seen: continue
        seen.add(s)
        full = s if os.path.isabs(s) else os.path.join(data_root, s)
        ok = os.path.exists(full)
        print(f"{'OK  ' if ok else 'MISSING'} model {s}")
        if not ok: bad.append(s)
if bad:
    print("DITTO_FILES_FAIL", bad); sys.exit(1)
print("DITTO_FILES_OK")
