#!/usr/bin/env python3
"""Turn Whisper word timestamps of the final voice track into timing.json.

  retime.py SOURCE.json WHISPER.json --out timing.json [--workspace DIR]

WHISPER.json may be openai-whisper / faster-whisper output with word timestamps
({"segments":[{"words":[{"word","start","end"}]}]}) or {"words":[...]} or a bare list.
Whisper often writes "ninety-seven dollars" as "$97", so digits in the transcript are
spelled out with the same converter the narration uses before the two word lists are
aligned. Scene start = time of its first aligned word; scene end = next scene's start
(so pauses stay inside the scene); the last scene ends at the last word.

Then:  build_exports.py SOURCE --out DIR --timing timing.json
       lint.py SOURCE --out DIR --stage post --timing timing.json
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

MIN_RATIO = 0.85


def load_words(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "words" in data:
            data = data["words"]
        else:
            data = [w for seg in data.get("segments", []) for w in seg.get("words", [])]
    out = []
    for w in data:
        text = str(w.get("word", w.get("text", ""))).strip()
        if text:
            out.append((text, float(w["start"]), float(w["end"])))
    return out


def tokens(text, cfg=None):
    t = c.RANGE_RE.sub(lambda m: f"{m.group(1)} to {m.group(2)}", text.replace("[BEAT]", " "))
    t = c.NUM_RE.sub(c._convert, t)
    return re.findall(r"[a-z0-9]+", t.lower().replace("’", "'").replace("'", ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("whisper")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workspace")
    a = ap.parse_args()

    cfg = c.load_config(a.workspace)
    src = c.load_json(a.source)
    words = load_words(a.whisper)
    if not words:
        print("no words in the Whisper file")
        return 1

    # whisper side: one token per word piece, remembering the source word's time
    w_tok, w_time = [], []
    for text, st, en in words:
        for tk in tokens(text):
            w_tok.append(tk)
            w_time.append((st, en))

    # script side: narration tokens, remembering scene index
    s_tok, s_scene = [], []
    scene_ids = []
    for sc in src["scenes"]:
        narr, _, _ = c.to_narration(sc["line"], cfg)
        scene_ids.append(str(sc["id"]))
        for tk in tokens(narr):
            s_tok.append(tk)
            s_scene.append(len(scene_ids) - 1)

    sm = difflib.SequenceMatcher(None, s_tok, w_tok, autojunk=False)
    matched = {}  # script token index -> whisper token index
    for i, j, n in sm.get_matching_blocks():
        for k in range(n):
            matched[i + k] = j + k
    ratio = len(matched) / max(1, len(s_tok))

    first_idx = {}
    for i, sc_i in enumerate(s_scene):
        first_idx.setdefault(sc_i, i)
    starts, last_seen = [], 0.0
    problems = []
    for sc_i, sid in enumerate(scene_ids):
        i0 = first_idx.get(sc_i)
        t = None
        if i0 is not None:
            # first matched token inside this scene
            for i in range(i0, len(s_tok)):
                if s_scene[i] != sc_i:
                    break
                if i in matched:
                    t = w_time[matched[i]][0]
                    break
        if t is None:
            problems.append(sid)
            t = last_seen
        t = max(t, last_seen)
        starts.append(t)
        last_seen = t
    end_total = words[-1][2]
    last_floor = cfg["limits"]["end_screen_min_s"] if src["scenes"][-1].get("section") == "end_screen" else cfg["limits"]["scene_min_s"]
    end_total = max(end_total, starts[-1] + last_floor)
    scenes = {}
    for k, sid in enumerate(scene_ids):
        en = starts[k + 1] if k + 1 < len(starts) else end_total
        scenes[sid] = {"start": round(starts[k], 3), "end": round(max(en, starts[k]), 3)}

    # real timing can stretch or shrink a scene past what its shots allow; list them so shots can be added or removed
    need_shots = {}
    for sc in src["scenes"]:
        sid = str(sc["id"])
        shots = sc.get("shots") or []
        bounds = [c.shot_bounds(sh) for sh in shots]
        dur = scenes[sid]["end"] - scenes[sid]["start"]
        whole = max(1, int(round(dur)))
        if bounds and c.split_seconds(whole, bounds) is not None:
            continue
        lo, hi = sum(b[0] for b in bounds), sum(b[1] for b in bounds)
        need_shots[sid] = {"has": len(shots), "can_hold_s": f"{lo}-{hi}", "scene_s": round(dur, 1)}
    out = {"scenes": scenes, "scenes_needing_more_shots": need_shots, "match_ratio": round(ratio, 3), "unaligned_scenes": problems,
           "whisper_words": len(words)}
    c.save_json(a.out, out)
    print(f"timing written: {a.out}  match {ratio:.0%}  scenes {len(scenes)}  runtime {c.mmss(end_total)}")
    if need_shots:
        print("SHOTS: real timing does not fit the current shots. Add or remove B-ROLL shots, then re-run:")
        for sid, v in need_shots.items():
            print(f"  scene {sid}: {v['has']} shots hold {v['can_hold_s']}s, the scene is {v['scene_s']}s")
    if ratio < MIN_RATIO or problems:
        print(f"WARNING: weak alignment (need >= {MIN_RATIO:.0%}); unaligned scenes: {problems[:15]}. "
              "Check the voice track was generated from the current narration.txt before using this timing.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
