#!/usr/bin/env python3
"""Shared helpers for longform-vs-video-script: config, number-to-words, timeline.

Everything that turns the source file into numbers (word counts, durations,
timestamps, narration text) lives here so build_exports.py and lint.py can
never disagree.
"""
import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BEAT = "[BEAT]"


# ----------------------------------------------------------------- json/config
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def deep_merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(workspace=None):
    cfg = load_json(SKILL_DIR / "config.json")
    if workspace:
        local = Path(workspace) / "config.local.json"
        if local.exists():
            cfg = deep_merge(cfg, load_json(local))
    return cfg


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def video_slug(src):
    v = src["video"]
    return v.get("slug") or f"{slugify(v['product_a'])}-vs-{slugify(v['product_b'])}"


# ------------------------------------------------------------------ time utils
def mmss(t, decimals=0):
    t = max(0.0, float(t))
    if decimals == 0:
        total = int(round(t))
        m, s = divmod(total, 60)
        return f"{m}:{s:02d}"
    tenths = int(round(t * 10))
    m, rem = divmod(tenths, 600)
    return f"{m}:{rem / 10:04.1f}"


# -------------------------------------------------------------- number to words
_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
         "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def int_to_words(n):
    n = int(n)
    if n < 0:
        return "minus " + int_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + ("-" + _ONES[o] if o else "")
    if n < 1000:
        h, r = divmod(n, 100)
        return _ONES[h] + " hundred" + (" " + int_to_words(r) if r else "")
    for div, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= div:
            q, r = divmod(n, div)
            return int_to_words(q) + " " + name + (" " + int_to_words(r) if r else "")
    return str(n)


# a number token: optional $, digits (with commas), optional decimals, optional k, %, /unit
NUM_RE = re.compile(
    r"(?<![A-Za-z0-9.])(\$)?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?([kK])?(%)?(?:/(mo|month|yr|year|user|seat))?(?![A-Za-z0-9])"
)
RANGE_RE = re.compile(r"(?<![A-Za-z0-9.])(\d+)-(\d+)(?![A-Za-z0-9])")
_UNIT = {"mo": " a month", "month": " a month", "yr": " a year", "year": " a year",
         "user": " per user", "seat": " per seat"}


def _convert(m):
    dollar, whole, frac, k, pct, unit = m.groups()
    whole = whole.replace(",", "")
    if k:
        val = float(whole + ("." + frac if frac else "")) * 1000
        n, frac_words = int(round(val)), ""
    else:
        n = int(whole)
        frac_words = ""
        if frac and not dollar:
            frac_words = " point " + " ".join(_ONES[int(d)] for d in frac)
    if dollar:
        words = int_to_words(n) + (" dollar" if n == 1 else " dollars")
        if frac and not k:
            cents = int((frac + "0")[:2])
            if cents:
                words += " and " + int_to_words(cents) + (" cent" if cents == 1 else " cents")
    else:
        words = int_to_words(n) + frac_words
    if pct:
        words += " percent"
    if unit:
        words += _UNIT[unit]
    return words


def number_tokens(text):
    """Every numeric token in a source LINE or on-screen string, as written."""
    t = RANGE_RE.sub(lambda m: f"{m.group(1)} to {m.group(2)}", text)
    return [m.group(0) for m in NUM_RE.finditer(t)]


def digits_of(token):
    """Normalize a numeric token for proof matching: '$1,297/mo' -> '1297'."""
    return re.sub(r"[^0-9.]", "", token.replace(",", "")).rstrip(".")


def count_words(text):
    return len([w for w in text.replace(BEAT, " ").split() if re.search(r"[A-Za-z0-9]", w)])


def to_narration(line, cfg):
    """Return (narration_text, pronunciation_names_used, number_positions).

    number_positions are fractional positions (0..1) of numeric tokens, used to
    keep the avatar off screen while a number is spoken.
    """
    text = RANGE_RE.sub(lambda m: f"{m.group(1)} to {m.group(2)}", line)
    out, pos, starts = "", 0, []
    for m in NUM_RE.finditer(text):
        out += text[pos:m.start()]
        starts.append(count_words(out))
        out += _convert(m)
        pos = m.end()
    out += text[pos:]
    total = max(1, count_words(out))
    positions = [s / total for s in starts]
    used = []
    for name, p in cfg.get("pronunciations", {}).items():
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])")
        if pattern.search(out):
            used.append(name)
            out = pattern.sub(p["spell"], out)
    out = re.sub(r"\s+", " ", out).strip()
    return out, used, positions


def sentence_count(line):
    t = line.replace(BEAT, " ")
    parts = [p for p in re.split(r"(?<=[.!?])\s+", t.strip()) if p.strip()]
    return len(parts)


# -------------------------------------------------------------------- timeline
# Pipeline shot tags (parse_script.py in the video pipeline reads exactly these).
TAGS = ["GEN-VIDEO", "GEN-STILL", "B-ROLL", "STAT", "ASSET-SHOT", "ASSET-CLIP", "ASSET-BRAND"]
LONG_TAGS = ("GEN-STILL", "STAT")          # 9-16 s
SHOT_MIN_S, SHOT_MAX_S = 2, 5        # generated Wan clips (about 5 s) and brand logos run 2-5 s
HOLD_MAX_S = 10                      # B-roll and real captures (screenshots, recordings) run 2-10 s
HOLD_TAGS = ("B-ROLL", "ASSET-SHOT", "ASSET-CLIP")
LONG_MIN_S, LONG_MAX_S = 9, 16
FULLSCREEN_TAGS = ("STAT", "ASSET-SHOT", "ASSET-CLIP", "ASSET-BRAND")   # the avatar is never over these


def shot_tag(shot):
    return shot.get("tag", "NONE")


def shot_bounds(shot):
    tag = shot_tag(shot)
    if tag in LONG_TAGS:
        return (LONG_MIN_S, LONG_MAX_S)
    return (SHOT_MIN_S, HOLD_MAX_S if tag in HOLD_TAGS else SHOT_MAX_S)


def gen_video_of(shot):
    """Return {'role','prompt_id'} when a shot is a generated Wan clip, else None."""
    if shot_tag(shot) == "GEN-VIDEO":
        return {"role": shot.get("role"), "prompt_id": shot.get("prompt_id")}
    return None


def split_seconds(total, bounds):
    """Split `total` whole seconds across shots with (lo, hi) bounds. Returns a list of ints,
    or None when the bounds cannot hold `total` (too many shots for the time, or too few)."""
    n = len(bounds)
    if n == 0:
        return None
    base = [max(lo, min(hi, int(total // n))) for lo, hi in bounds]
    diff = total - sum(base)
    guard = 0
    while diff != 0 and guard < 10000:
        guard += 1
        step = 1 if diff > 0 else -1
        order = range(n - 1, -1, -1) if step > 0 else range(n)
        moved = False
        for i in order:
            lo, hi = bounds[i]
            if lo <= base[i] + step <= hi:
                base[i] += step
                diff -= step
                moved = True
                break
        if not moved:
            return None
    return base if diff == 0 else None


def build_timeline(src, cfg, timing=None):
    """Narration timing per scene comes from word counts (or Whisper timing). Shots are placed on
    a continuous timeline in whole seconds, as the pipeline parser requires.

    A first shot with "span": N covers its own scene and the next N-1 scenes (the covered scenes
    carry no shots of their own). That is how a 9-16 s still or stat card sits under 2-3 short
    scenes. A scene whose shots cannot fit its narration time pushes the timeline later (drift),
    and lint reports it."""
    v = src["video"]
    wpm = float(v.get("wpm") or cfg["defaults"]["wpm"])
    beat_s = cfg["voice"]["beat_seconds"]
    lim = cfg["limits"]
    scenes = src["scenes"]
    nar = []
    t = 0.0
    for sc in scenes:
        sid = str(sc["id"])
        narr, used, positions = to_narration(sc["line"], cfg)
        words = count_words(narr)
        beats = narr.count(BEAT)
        if timing and sid in timing.get("scenes", {}):
            st, en = timing["scenes"][sid]["start"], timing["scenes"][sid]["end"]
        else:
            floor = lim["end_screen_min_s"] if sc.get("section") == "end_screen" else lim["scene_min_s"]
            if sc.get("cta_button"):
                floor = max(floor, float(sc["cta_button"].get("dur_s", cfg["cta"]["duration_s"])))
            dur = max(words / wpm * 60.0 + beats * beat_s, floor)
            st, en = t, t + dur
        t = en
        nar.append({"narr": narr, "used": used, "positions": positions, "words": words, "beats": beats, "st": st, "en": en})
    out = [None] * len(scenes)
    cursor = 0
    i = 0
    while i < len(scenes):
        sc = scenes[i]
        shots_in = sc.get("shots") or []
        span = int(shots_in[0].get("span", 1)) if shots_in else 1
        span = max(1, min(span, len(scenes) - i))
        last = i + span - 1
        bounds = [shot_bounds(sh) for sh in shots_in]
        target = max(int(round(nar[last]["en"])) - cursor, 1)
        sizes = split_seconds(target, bounds) if bounds else None
        fit = sizes is not None
        if not fit and bounds:
            lo_sum, hi_sum = sum(b[0] for b in bounds), sum(b[1] for b in bounds)
            sizes = [b[0] for b in bounds] if target < lo_sum else [b[1] for b in bounds]
        start_g = cursor
        shots = []
        for j, sh in enumerate(shots_in):
            d = sizes[j]
            shots.append({"id": sh.get("id") or f"{sc['id']}{chr(97 + j)}",
                          "start": float(cursor), "end": float(cursor + d), "dur": float(d), "src": sh})
            cursor += d
        end_g = cursor if shots else start_g
        n_st, n_en = nar[i]["st"], nar[last]["en"]
        scale = (end_g - start_g) / (n_en - n_st) if (n_en - n_st) > 0 and shots else 1.0
        for k in range(i, last + 1):
            nn = nar[k]
            if k == i:
                s_start = float(start_g)
            else:
                s_start = start_g + (nn["st"] - n_st) * scale
            s_end = float(end_g) if k == last else start_g + (nn["en"] - n_st) * scale
            if k > i and not shots:
                s_start, s_end = nn["st"], nn["en"]
            out[k] = {
                "scene": scenes[k], "id": str(scenes[k]["id"]), "start": s_start, "end": s_end, "dur": s_end - s_start,
                "narr_start": nn["st"], "narr_end": nn["en"], "fit": fit if k == i else True,
                "words": nn["words"], "beats": nn["beats"], "narration": nn["narr"], "pron": nn["used"],
                "number_positions": nn["positions"],
                "shots": shots if k == i else [],
                "cover": shots[0] if (k > i and shots) else None,
                "group_end": last,
            }
        i = last + 1
    return out


def shot_at_time(tl_scene, time_s):
    for sh in tl_scene["shots"]:
        if sh["start"] <= time_s < sh["end"]:
            return sh
    if tl_scene["shots"]:
        return tl_scene["shots"][-1]
    return tl_scene.get("cover")


def shot_at(tl_scene, frac):
    """The shot that is on screen at a fractional position (0..1) in the scene."""
    return shot_at_time(tl_scene, tl_scene["start"] + frac * tl_scene["dur"])


def compute_ai_flags(src, tl):
    avatar_mode = (src["video"].get("avatar") or {}).get("mode", "none")
    flux_or_clip = False
    shots_ai = []
    for s in tl:
        for sh in s["shots"]:
            tag = shot_tag(sh["src"])
            if tag in ("GEN-STILL", "GEN-VIDEO"):
                flux_or_clip = True
                shots_ai.append(sh["id"])
    if avatar_mode == "generated":
        flux_or_clip = True
    return {
        "synthetic_voice": True,
        "realistic_ai_visuals": flux_or_clip,
        "ai_person_visible": avatar_mode == "generated",
        "_realistic_ai_visuals_shots": sorted(set(shots_ai)),
    }


def disclosure_string(src, cfg):
    t = src["video"].get("disclosure_type") or cfg["defaults"]["disclosure_type"]
    return cfg["disclosure_strings"][t]


def abs_text_start(entry, scene_start, scene_dur):
    """Absolute start time of an on-screen text entry. Negative at_s counts from scene end."""
    at = entry.get("at_s", 0)
    if isinstance(at, str):
        at = float(at)
    if at < 0:
        return scene_start + scene_dur + at
    return scene_start + at
