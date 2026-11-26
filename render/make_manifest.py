"""Write the render manifest: package-relative destination -> R2 key, for every shot in shots.json.
Usage: python3 render/make_manifest.py SHOTS_JSON BROLL_MAP_JSON ASSETS_JSON OUT_JSON
ASSETS_JSON (render/assets-<slug>.json) names the keys per video: {"wan": {shotId: key}, "still": {shotId: key},
  "picture": {shotId: key}, "screen": {shotId: key}, "extra": [{"dest","key"}]}.
BROLL_MAP_JSON entries: an entry with "key" (a Wan clip used as B-roll) uses that key; otherwise the key is
  outputs/<run>/<file>, with run defaulting to "broll-ghl-b1" when the entry has no "run".
Every shot of kind wan, still, picture, screen and broll must have a key; a missing one is listed and the script exits 1.
"""
import json, sys
shots, bmap_list, assets, out_p = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), sys.argv[4]
bmap = {b["shot"]: b.get("key") or f"outputs/{b.get('run', 'broll-ghl-b1')}/{b['file']}" for b in bmap_list}
SRC = {"wan": ("clips", "mp4", assets.get("wan", {})), "still": ("stills", "png", assets.get("still", {})),
       "picture": ("assets", "png", assets.get("picture", {})), "screen": ("assets", "png", assets.get("screen", {})),
       "broll": ("broll", "mp4", bmap)}
out, missing = [], []
for s in shots:
    k = s["kind"]
    if k in SRC:
        folder, ext, table = SRC[k]
        if s["id"] in table: out.append({"dest": f"{folder}/{s['id']}.{ext}", "key": table[s["id"]]})
        else: missing.append(s["id"])
    elif k == "stat": pass
    else: missing.append(s["id"])
out += assets.get("extra", [])
json.dump(out, open(out_p, "w"), indent=1)
print(f"MANIFEST_OK files={len(out)} missing={missing}")
sys.exit(1 if missing else 0)
