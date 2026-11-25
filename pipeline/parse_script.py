"""Parse a package script into shots.json and stat/B-roll lists.
Shot line format (from the script): [0:00-0:05] Shot 1a [GEN-VIDEO] (...)
Stat blocks: Value:, Label:, Source: on the lines after the shot line.
Usage: python3 pipeline/parse_script.py SCRIPT.md OUT_shots.json
Fails on any missing stat source, unknown tag, or non-still shot over 5.0 s (B-roll over 8.0 s), or a still/stat outside 9-16 s.
"""
import json, re, sys

KIND = {"GEN-VIDEO": "wan", "GEN-STILL": "still", "B-ROLL": "broll", "STAT": "stat",
        "ASSET-SHOT": "screen", "ASSET-CLIP": "clip", "ASSET-BRAND": "picture"}
LINE = re.compile(r"^\[(\d+):(\d\d)-(\d+):(\d\d)\]\s+Shot\s+(\w+)\s+\[([A-Z\- ]+)\]")

def secs(m, s): return int(m) * 60 + int(s)

script, out = sys.argv[1:3]
lines = open(script, encoding="utf-8").read().splitlines()
shots, errors = [], []
for i, line in enumerate(lines):
    m = LINE.match(line.strip())
    if not m:
        continue
    start, end = secs(m.group(1), m.group(2)), secs(m.group(3), m.group(4))
    sid, tag = m.group(5), m.group(6).strip()
    if tag not in KIND:
        errors.append(f"{sid}: unknown tag [{tag}]"); continue
    kind = KIND[tag]
    dur = end - start
    cap = 8 if kind == "broll" else 5  # B-roll clips run 2-8 s; every other non-still shot stays 5 s or less
    if kind not in ("still", "stat") and dur > cap:
        errors.append(f"{sid}: {dur}s {kind} shot is over {cap}.0 s")
    if kind in ("still", "stat") and not (9 <= dur <= 16):
        errors.append(f"{sid}: {dur}s still/stat must be 9-16 s")
    shot = {"id": sid, "startSec": start, "endSec": end, "kind": kind, "src": ""}
    if kind == "stat":
        block = " ".join(lines[i+1:i+4])
        vals = dict(re.findall(r"(Value|Label|Source):\s*([^\n]+?)(?=\s+(?:Value|Label|Source):|$)", block))
        if not vals.get("Source"):
            errors.append(f"{sid}: stat has no source (block)")
        shot["stat"] = {"value": vals.get("Value", ""), "label": vals.get("Label", ""), "source": vals.get("Source", "")}
    shots.append(shot)

if errors:
    print("SCRIPT_CHECK_FAILED"); [print(" -", e) for e in errors]; sys.exit(1)
json.dump(shots, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"SCRIPT_OK shots={len(shots)}")
