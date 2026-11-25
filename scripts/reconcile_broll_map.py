#!/usr/bin/env python3
"""Reconcile a B-roll map with a rebuilt scene manifest.

Shot ids are the key. For every B-ROLL shot in the new manifest:
  KEEP   id and search noun match the old map entry: clip kept, start_s and
         duration_s taken from the new manifest.
  NEEDS  id is not in the map, or its search noun changed: no clip yet.
Map entries whose shot is no longer a B-ROLL shot are DROPPED.
Also flagged: a clip shorter than its shot, a clip used more than 3 times,
a clip used in back-to-back shots.
Writes --out (new map, NEEDS entries have clip_id null) and prints a report.
Reads files only; never touches R2.
"""
import argparse, json, sys
from collections import Counter

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def broll(man):
    return [s for s in man["shots"] if s.get("tag") == "B-ROLL"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-manifest", required=True)
    ap.add_argument("--new-manifest", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-uses", type=int, default=3)
    a = ap.parse_args()

    old_m, new_m, mp = load(a.old_manifest), load(a.new_manifest), load(a.map)
    by_id = {m["shot"]: m for m in mp}
    old_ids = {s["shot"] for s in broll(old_m)}
    stale = [i for i in by_id if i not in old_ids]
    if stale:
        print("WARNING: map entries not in old manifest:", stale, file=sys.stderr)

    new_map, keep, needs, flags = [], [], [], []
    for s in broll(new_m):
        sid, noun = s["shot"], s.get("broll_search", "")
        old = by_id.get(sid)
        if old and old.get("search") == noun and old.get("clip_id"):
            e = dict(old, start_s=s["start"], duration_s=s["duration_s"])
            keep.append(sid)
            if old.get("clip_seconds") is not None and old["clip_seconds"] < s["duration_s"]:
                flags.append((sid, f"clip {old['clip_seconds']}s shorter than shot {s['duration_s']}s"))
        else:
            why = "new shot" if not old else f"noun changed {old.get('search')!r} -> {noun!r}"
            e = {"shot": sid, "start_s": s["start"], "duration_s": s["duration_s"],
                 "search": noun, "clip_id": None, "clip_file": None, "clip_seconds": None,
                 "page_url": None, "author": None, "license": None,
                 "visual_review": None, "needs_clip": why}
            needs.append((sid, noun, s["duration_s"], why))
        new_map.append(e)

    new_ids = {s["shot"] for s in broll(new_m)}
    dropped = [i for i in by_id if i not in new_ids]
    uses = Counter(e["clip_id"] for e in new_map if e["clip_id"])
    for c, n in uses.items():
        if n > a.max_uses:
            flags.append((c, f"clip used {n} times (max {a.max_uses})"))
    for p, q in zip(new_map, new_map[1:]):
        if p["clip_id"] and p["clip_id"] == q["clip_id"]:
            flags.append((q["shot"], f"same clip {q['clip_id']} as previous B-roll shot {p['shot']}"))

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(new_map, f, indent=2)
    print(f"B-roll shots in new manifest: {len(new_map)}")
    print(f"KEEP {len(keep)} | NEEDS CLIP {len(needs)} | DROPPED {len(dropped)}")
    for sid, noun, d, why in needs:
        print(f"  needs clip: {sid} ({d}s) search={noun!r} [{why}]")
    for i in dropped:
        print(f"  dropped: {i}")
    for k, why in flags:
        print(f"  flag: {k}: {why}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
