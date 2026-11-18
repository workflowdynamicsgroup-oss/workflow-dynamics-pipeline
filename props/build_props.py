"""Build props-16x9.json and props-9x16.json for the Remotion renders.
Inputs: shots.json (from parse_script.py), captions.json (from make_captions.py),
the package folder with clips/ and stills/, and the narration duration.
Usage: python3 props/build_props.py PACKAGE_DIR SHOTS_JSON CAPTIONS_JSON NARRATION_SEC
Writes PACKAGE_DIR/props-16x9.json and PACKAGE_DIR/props-9x16.json.
"""
import json, os, sys

pkg, shots_p, caps_p, dur = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
shots = json.load(open(shots_p, encoding="utf-8"))
caps = json.load(open(caps_p, encoding="utf-8"))
DISCLOSURE = "Some links here are affiliate links. I may earn a commission."

def src_for(shot):
    k, sid = shot["kind"], shot["id"]
    if k == "still":  return f"stills/{sid}.png"
    if k == "picture": return f"assets/{sid}.png"
    if k == "stat":   return ""
    if k == "wan":    return f"clips/{sid}.mp4"
    if k == "broll":  return f"broll/{sid}.mp4"
    return f"assets/{sid}.mp4"  # screen, clip

def props(fmt, avatar):
    sh = []
    for s in shots:
        item = {"id": s["id"], "startSec": s["startSec"], "endSec": s["endSec"], "kind": s["kind"], "src": src_for(s)}
        if "stat" in s: item["stat"] = s["stat"]
        sh.append(item)
    return {
        "format": fmt, "fps": 30, "durationSec": dur, "avatarSrc": avatar, "shots": sh,
        "captions": caps, "disclosure": DISCLOSURE,
        "disclosureWindowsSec": [[0, 5], [max(0, dur - 5), dur]],
        "cornerTag": "Affiliate links",
    }

for fmt, avatar in (("16x9", "avatar/avatar-16x9.mp4"), ("9x16", "avatar/avatar-9x16.mp4")):
    p = props(fmt, avatar)
    path = os.path.join(pkg, f"props-{fmt}.json")
    json.dump(p, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"PROPS_OK {path} shots={len(p['shots'])}")
