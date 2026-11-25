"""Write render/manifest-<slug>.json: package-relative destination -> R2 key, for every shot in shots.json.
Usage: python3 render/make_manifest.py SHOTS_JSON BROLL_MAP_JSON OUT_JSON
Wan clips: newest good run per shot (WAN_KEYS below). Stills: flux-ghl-a3 (a4 redos were copied over a3 photos 5, 9, 13, 15).
Screens and pictures come from inputs/gohighlevel-vs-systeme-io/. Shot 62a (both pricing pages) is composed on the pod from the two screenshots.
"""
import json, sys
shots = json.load(open(sys.argv[1])); bmap = {b["shot"]: b["clip_file"] for b in json.load(open(sys.argv[2]))}
IN = "inputs/gohighlevel-vs-systeme-io/gohighlevel-vs-systeme-io-"
WAN = {"1a": "wan-ghl-a2/wan_w1_1a", "63a": "wan-ghl-a2/wan_w2_63a", "87a": "wan-ghl-a2/wan_w3_87a", "88a": "wan-ghl-a2/wan_w4_88a",
       "37b": "wan-ghl-b3/wan_w5_37b", "40a": "wan-ghl-a2/wan_w6_40a", "42a": "wan-ghl-b3/wan_w7_42a", "44a": "wan-ghl-b3/wan_w8_44a",
       "3b": "wan-ghl-b1/wan_w9_3b", "28b": "wan-ghl-b1/wan_w10_28b", "53a": "wan-ghl-b1/wan_w11_53a", "30b": "wan-ghl-b1/wan_w12_30b",
       "21a": "wan-ghl-b1/wan_w13_21a"}
STILL = {sid: f"photo_{i}" for i, sid in enumerate("7a 11a 13a 18a 22a 26a 32a 36a 39a 41a 43a 46a 54a 60a 64a 71a".split(), 1)}
PIC = {"2a": "brand-gohighlevel-on-light.png", "3a": "brand-systeme-io.png", "10a": "brand-gohighlevel-on-light.png"}
SCR = {"29a": "asset-gohighlevel-pricing.png", "37a": "asset-systeme-io-pricing.png"}
out, missing = [], []
for s in shots:
    sid, k = s["id"], s["kind"]
    if k == "wan": out.append({"dest": f"clips/{sid}.mp4", "key": f"outputs/{WAN[sid]}.mp4"} if sid in WAN else None)
    elif k == "still": out.append({"dest": f"stills/{sid}.png", "key": f"outputs/flux-ghl-a3/{STILL[sid]}.png"})
    elif k == "broll": out.append({"dest": f"broll/{sid}.mp4", "key": bmap[sid]} if sid in bmap else None)
    elif k == "picture": out.append({"dest": f"assets/{sid}.png", "key": IN + PIC[sid]})
    elif k == "screen":
        if sid in SCR: out.append({"dest": f"assets/{sid}.png", "key": IN + SCR[sid]})
    if out and out[-1] is None: missing.append(sid); out.pop()
out += [{"dest": "assets/_gohighlevel-pricing.png", "key": IN + SCR["29a"]}, {"dest": "assets/_systeme-pricing.png", "key": IN + SCR["37a"]}]
json.dump(out, open(sys.argv[3], "w"), indent=1)
print(f"MANIFEST_OK files={len(out)} missing={missing}")
