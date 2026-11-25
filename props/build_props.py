"""Build props-16x9.json and props-9x16.json for the Remotion renders.
Inputs: shots.json (from parse_script.py), captions.json (from make_captions.py),
the package folder with clips/ and stills/, and the narration duration.
Usage: python3 props/build_props.py PACKAGE_DIR SHOTS_JSON CAPTIONS_JSON NARRATION_SEC
           [--source SOURCE_JSON] [--timing TIMING_JSON] [--blocks BLOCKS_JSON]
           [--narration REL_PATH]
Writes PACKAGE_DIR/props-16x9.json and PACKAGE_DIR/props-9x16.json.

--source   adds comparison rows (R-COMPARE) to STAT shots, matched on the card's value and label.
--timing   timing.json (scene start/end) and --blocks (avatar/blocks_*/blocks.json) give the avatar
           segments. A scene missing from a block (a spoken number) leaves a gap, so each run of
           consecutive block scenes is one segment, with the offset into the block's avatar file.
--narration  path of the narration track inside the package folder, for the Remotion Audio layer.
"""
import json, os, sys

FPS = 25  # R-SPEC: 25 fps, matching the Ditto avatar clip

args = sys.argv[1:]
opts = {}
pos = []
i = 0
while i < len(args):
    if args[i].startswith("--"):
        opts[args[i][2:]] = args[i + 1]; i += 2
    else:
        pos.append(args[i]); i += 1
pkg, shots_p, caps_p, dur = pos[0], pos[1], pos[2], float(pos[3])
shots = json.load(open(shots_p, encoding="utf-8"))
caps = json.load(open(caps_p, encoding="utf-8"))
DISCLOSURE = "Some links here are affiliate links. I may earn a commission."

compare = {}
if "source" in opts:
    src_doc = json.load(open(opts["source"], encoding="utf-8"))
    for sc in src_doc["scenes"]:
        for sh in sc.get("shots", []):
            st = sh.get("stat")
            if st and st.get("compare"):
                compare[(st["value"].strip(), st["label"].strip())] = st["compare"]

def src_for(shot):
    k, sid = shot["kind"], shot["id"]
    if k == "still":  return f"stills/{sid}.png"
    if k == "picture": return f"assets/{sid}.png"
    if k == "stat":   return ""
    if k == "wan":    return f"clips/{sid}.mp4"
    if k == "broll":  return f"broll/{sid}.mp4"
    return f"assets/{sid}.mp4"  # screen, clip

def avatar_segments(fmt):
    if "timing" not in opts or "blocks" not in opts:
        return []
    scenes = json.load(open(opts["timing"], encoding="utf-8"))["scenes"]
    blocks = json.load(open(opts["blocks"], encoding="utf-8"))
    segs = []
    for name in sorted(k for k in blocks if k.startswith("block")):
        ids = [str(x) for x in blocks[name]]
        offset, run = 0.0, None
        for sid in sorted(scenes, key=lambda x: scenes[x]["start"]):
            s = scenes[sid]
            if sid in ids:
                if run is None:
                    run = {"src": f"avatar/avatar-{name}.webm", "startSec": s["start"], "endSec": s["end"], "offsetSec": round(offset, 3)}
                else:
                    run["endSec"] = s["end"]
                offset += s["end"] - s["start"]
            elif run is not None:
                segs.append(run); run = None
        if run is not None:
            segs.append(run)
    return segs

def props(fmt):
    sh = []
    for s in shots:
        item = {"id": s["id"], "startSec": s["startSec"], "endSec": s["endSec"], "kind": s["kind"], "src": src_for(s)}
        if "stat" in s:
            item["stat"] = dict(s["stat"])
            cmp_ = compare.get((s["stat"]["value"].strip(), s["stat"]["label"].strip()))
            if cmp_:
                item["stat"]["compare"] = cmp_
        sh.append(item)
    out = {
        "format": fmt, "fps": FPS, "durationSec": dur, "shots": sh,
        "captions": caps, "disclosure": DISCLOSURE,
        "disclosureWindowsSec": [[0, 5], [max(0, dur - 5), dur]],
        "cornerTag": "Affiliate links",
        "avatarBlocks": avatar_segments(fmt),
    }
    if "narration" in opts:
        out["narrationSrc"] = opts["narration"]
    return out

for fmt in ("16x9", "9x16"):
    p = props(fmt)
    path = os.path.join(pkg, f"props-{fmt}.json")
    json.dump(p, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    n_cmp = sum(1 for s in p["shots"] if s.get("stat", {}).get("compare"))
    print(f"PROPS_OK {path} shots={len(p['shots'])} compare_cards={n_cmp} avatar_segments={len(p['avatarBlocks'])} fps={FPS}")
