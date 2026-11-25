#!/usr/bin/env python3
"""Lint a source file (and, after export, the exported files) against every rule.

Usage:
  lint.py SOURCE.json --out DIR [--workspace DIR] [--timing TIMING.json] [--stage pre|post]

Stages
  pre   checks the source file only (Phase 5, before the gate)
  post  also checks the exported files in DIR (Phase 7, after build_exports.py)

Exit code: 0 pass, 1 a critical rule failed, 2 only standard rules failed.
Writes lint-report.txt into DIR. In post stage it also stamps LINT RESULT in
the locked-facts file.
"""
import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402
import apify_budget as ab  # noqa: E402

CRITICAL_RULES = {"R-HONESTY", "R-DISC", "R-NOFAKE", "R-NOSPOKEN", "R-AIFLAG", "R-SPEC", "R-GENLIMIT", "R-SHOTS", "R-COMPARE"}
FLAG_TOKENS = ["[VERIFY AT PUBLISH]", "[VERIFY AT BUILD]", "[TBD AT INSTALL]"]


class Report:
    def __init__(self):
        self.rows = []

    def add(self, rule, ok, detail, severity=None):
        sev = severity or ("critical" if rule in CRITICAL_RULES else "standard")
        self.rows.append({"rule": rule, "ok": bool(ok), "detail": detail, "severity": sev})

    def failures(self, sev=None):
        return [r for r in self.rows if not r["ok"] and r["severity"] != "warn" and (sev is None or r["severity"] == sev)]

    def warnings(self):
        return [r for r in self.rows if not r["ok"] and r["severity"] == "warn"]


def words_re(phrase):
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")


def norm(t):
    return t.lower().replace("’", "'")


def scene_texts(sc):
    texts = [e["text"] for e in sc.get("on_screen_text", [])]
    for sh in sc.get("shots", []):
        st = sh.get("stat") or {}
        if sh.get("tag") == "STAT" and st.get("value"):
            texts.append(str(st["value"]))
    return texts


def is_ghl(name):
    n = re.sub(r"[^a-z]", "", name.lower())
    return n in ("gohighlevel", "ghl")


# ---------------------------------------------------------------------- checks
def check_structure(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    v = src["video"]
    scenes = src["scenes"]
    ids = [str(s["id"]) for s in scenes]
    R.add("STRUCTURE", len(ids) == len(set(ids)), "scene ids are unique" if len(ids) == len(set(ids)) else "duplicate scene ids")
    bad = []
    for i, s in enumerate(scenes):
        covered = bool(tl[i].get("cover")) if i < len(tl) else False
        for k in ("id", "name", "section", "line", "shots"):
            if k not in s or (k == "shots" and not s["shots"] and not covered):
                bad.append(f"scene {s.get('id')} missing {k}")
    R.add("STRUCTURE", not bad, "every scene has id, name, section, line, shots" if not bad else "; ".join(bad))
    rank = cfg["section_rank"]
    unknown = [s["section"] for s in scenes if s["section"] not in rank]
    R.add("STRUCTURE", not unknown, "all sections valid" if not unknown else f"unknown sections: {sorted(set(unknown))}")
    if not unknown:
        ranks = [rank[s["section"]] for s in scenes]
        ordered = all(a <= b for a, b in zip(ranks, ranks[1:]))
        R.add("STRUCTURE", ordered, "sections follow the fixed sequence" if ordered else "sections are out of sequence")
    present = Counter(s["section"] for s in scenes)
    need = ["hook", "segment_map", "micro_authority", "problem", "agitation", "third_party_proof", "pricing",
            "held_reveal", "verdict", "recap", "risk_reversal", "cost_of_inaction", "offer", "end_screen"]
    missing = [n for n in need if present[n] == 0]
    R.add("STRUCTURE", not missing, "all required sections present" if not missing else f"missing sections: {missing}")
    R.add("STRUCTURE", scenes[-1]["section"] == "end_screen" and present["end_screen"] == 1,
          "end_screen is the single final scene" if scenes[-1]["section"] == "end_screen" and present["end_screen"] == 1
          else "end_screen must be the single final scene")
    segs = v.get("segments", [])
    R.add("STRUCTURE", 1 <= len(segs) <= 3 and present["verdict"] == len(segs),
          f"{present['verdict']} verdict scenes for {len(segs)} segments",)
    lo, hi = cfg["limits"]["category_scenes"]
    n = present["category"]
    R.add("STRUCTURE", lo <= n <= hi and n % 2 == 0, f"{n} category scenes (4-5 categories, 2 scenes each)")
    R.add("R-OPEN", scenes[0]["section"] == "hook", "scene 1 is the hook")


def check_disclosure(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    disc = c.disclosure_string(src, cfg)
    allowed = set(cfg["disclosure_strings"].values())
    runtime = tl[-1]["end"]
    first = tl[0]
    ok_first = any(e["text"] == disc and c.abs_text_start(e, first["start"], first["dur"]) <= 0.5 and float(e.get("dur_s", 3)) >= 4.9
                   for e in first["scene"].get("on_screen_text", []))
    R.add("R-DISC", ok_first, "disclosure on screen 0:00-0:05" if ok_first else "scene 1 needs the exact disclosure string at 0:00 for 5s")
    last = tl[-1]
    ok_last = any(e["text"] == disc and c.abs_text_start(e, last["start"], last["dur"]) >= runtime - 5.05
                  for e in last["scene"].get("on_screen_text", []))
    R.add("R-DISC", ok_last, "disclosure in the final 5 seconds" if ok_last else "final scene needs the disclosure string in the last 5s (at_s -5)")
    bad_cta = []
    for s in tl:
        cta = s["scene"].get("cta_button")
        if not cta:
            continue
        a = c.abs_text_start(cta, s["start"], s["dur"])
        b = a + float(cta.get("dur_s", cfg["cta"]["duration_s"]))
        okd = any(e["text"] == disc and float(e.get("dur_s", 3)) >= 4.9 and
                  c.abs_text_start(e, s["start"], s["dur"]) < b and c.abs_text_start(e, s["start"], s["dur"]) + float(e.get("dur_s", 3)) > a
                  for e in s["scene"].get("on_screen_text", []))
        if not okd:
            bad_cta.append(s["id"])
    R.add("R-DISC", not bad_cta, "disclosure shown for 5s at every CTA button" if not bad_cta else f"scenes without disclosure at CTA: {bad_cta}")
    stray = []
    for s in tl:
        for t in scene_texts(s["scene"]):
            if "affiliate link" in norm(t) and t not in allowed:
                stray.append(s["id"])
    R.add("R-DISC", not stray, "no reworded disclosure strings" if not stray else f"reworded disclosure in scenes {stray}")
    pk = src["video"].get("packaging", {})
    body = pk.get("description_body", "")
    kw = src["video"].get("primary_keyword", "")
    first_sentence = re.split(r"(?<=[.!?])\s+", body.strip())[0] if body.strip() else ""
    R.add("R-DISC", bool(kw) and norm(kw) in norm(first_sentence),
          "primary search phrase is in the first description sentence" if kw and norm(kw) in norm(first_sentence)
          else "primary search phrase missing from the first sentence of description_body", severity="standard")
    R.add("R-DISC", len(pk.get("titles", [])) == 3 and len(pk.get("tags", [])) == 5,
          "three titles and five tags" if len(pk.get("titles", [])) == 3 and len(pk.get("tags", [])) == 5
          else "packaging needs exactly 3 titles and 5 tags")


def check_nospoken(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    allowed = list(cfg["disclosure_strings"].values()) + [cfg["corner_tag"]]
    hits = []
    for s in tl:
        n = norm(s["narration"])
        if "affiliate link" in n or any(norm(a) in n for a in allowed):
            hits.append(s["id"])
    R.add("R-NOSPOKEN", not hits, "no disclosure or corner-tag text in narration" if not hits else f"disclosure text in narration of scenes {hits}")
    hook_hits = []
    for s in tl:
        if s["scene"]["section"] == "hook":
            blob = norm(s["scene"]["line"] + " " + " ".join(scene_texts(s["scene"])))
            if "subscribe" in blob:
                hook_hits.append(s["id"])
    R.add("R-NOSPOKEN", not hook_hits, "no subscribe cue in the hook" if not hook_hits else f"subscribe cue in hook scenes {hook_hits}")
    if ctx["stage"] == "post":
        out = ctx["out"]
        p = out / f"{ctx['slug']}-narration.txt"
        if p.exists():
            txt = norm(p.read_text(encoding="utf-8"))
            bad = "affiliate link" in txt or any(norm(a) in txt for a in allowed)
            R.add("R-NOSPOKEN", not bad, "narration file is clear of disclosure text" if not bad else "narration file contains disclosure text")


def check_length(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    runtime = tl[-1]["end"]
    wpm = float(src["video"].get("wpm") or cfg["defaults"]["wpm"])
    words = sum(s["words"] for s in tl)
    lo, hi = lim["runtime_min_s"] * wpm / 60, lim["runtime_max_s"] * wpm / 60
    # The floor is the hard line. The ceiling is a rough target: over it is a warning, never a block.
    R.add("R-LENGTH", runtime >= lim["runtime_min_s"], f"runtime {c.mmss(runtime)} (hard floor {c.mmss(lim['runtime_min_s'])})")
    R.add("R-LENGTH", runtime <= lim["runtime_max_s"], f"runtime {c.mmss(runtime)} (rough ceiling {c.mmss(lim['runtime_max_s'])})", severity="warn")
    R.add("R-LENGTH", words >= lo, f"{words} words (floor {lo:.0f} at {wpm:.0f} wpm)")
    R.add("R-LENGTH", words <= hi, f"{words} words (rough ceiling {hi:.0f} at {wpm:.0f} wpm)", severity="warn")


def check_lines(R, ctx):
    cfg, tl = ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    long_, sent, brackets, greet = [], [], [], []
    for s in tl:
        line = s["scene"]["line"]
        if s["words"] > lim["line_max_words"]:
            long_.append(f"{s['id']} ({s['words']}w)")
        if c.sentence_count(line) > lim["line_max_sentences"]:
            sent.append(s["id"])
        if re.search(r"[\[\]]", line.replace(c.BEAT, "")):
            brackets.append(s["id"])
        if re.match(r"\s*(hey|hi|hello|welcome|what's up|greetings|good (morning|evening))\b", norm(line)):
            greet.append(s["id"])
    R.add("R-LINE", not long_, "every LINE is 40 words or fewer" if not long_ else f"LINEs over 40 words: {long_}")
    R.add("R-LINE", not sent, "every LINE is 2 sentences or fewer" if not sent else f"LINEs over 2 sentences: {sent}")
    R.add("R-NARRATION", not brackets, "no stage notes or brackets in LINEs" if not brackets else f"brackets other than [BEAT] in scenes {brackets}")
    R.add("R-VOICE", not greet, "no greetings or channel welcomes" if not greet else f"greeting openers in scenes {greet}")


def check_voice(R, ctx):
    cfg, tl = ctx["cfg"], ctx["tl"]
    banned = [(p, words_re(p)) for p in cfg["banned_phrases"]]
    hits, semis, dashes, contr = [], [], [], []
    for s in tl:
        sc = s["scene"]
        blob = norm(sc["line"] + " " + " ".join(scene_texts(sc)))
        for p, rx in banned:
            if rx.search(blob):
                hits.append(f"{s['id']}: {p}")
        for rx in cfg.get("banned_regex", []):
            if re.search(rx, blob):
                hits.append(f"{s['id']}: pattern {rx}")
        if ";" in sc["line"] or any(";" in t for t in scene_texts(sc)):
            semis.append(s["id"])
        if len(re.findall(r"[—–]", sc["line"])) > 1 or "--" in sc["line"]:
            dashes.append(s["id"])
        line = norm(sc["line"].replace(c.BEAT, " "))
        for ph in cfg["uncontracted"]:
            # only flag when a word follows: 'who you are.' cannot be contracted, 'you are ready' can
            if re.search(r"(?<![a-z0-9])" + re.escape(ph) + r"(?=\s+[a-z0-9])", line):
                contr.append(f"{s['id']}: '{ph}'")
    R.add("R-VOICE", not hits, "no banned phrases" if not hits else f"banned phrases: {hits}")
    R.add("R-VOICE", not semis, "no semicolons" if not semis else f"semicolons in scenes {semis}")
    R.add("R-VOICE", not dashes, "no em-dash chains" if not dashes else f"dash chains in scenes {dashes}")
    R.add("R-VOICE", not contr, "contractions used throughout" if not contr else f"uncontracted phrases: {contr[:8]}")


def check_rhythm(R, ctx):
    cfg, tl = ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    bad = []
    for s in tl:
        sc = s["scene"]
        if s["id"] == tl[0]["id"]:
            continue
        has_num = bool(c.number_tokens(sc["line"]))
        if has_num or sc["section"] == "verdict":
            written = c.count_words(sc["line"])
            if not (lim["short_line_min_words"] <= written <= lim["short_line_max_words"]):
                bad.append(f"{s['id']} ({written}w)")
    R.add("R-VOICE", not bad, "stat, price, and verdict LINEs are 3-8 words" if not bad else f"stat/price/verdict LINEs outside 3-8 words: {bad}")
    long_run = []
    for a, b in zip(tl, tl[1:]):
        if a["words"] > lim["short_line_max_words"] * 2 and b["words"] > lim["short_line_max_words"] * 2:
            long_run.append(f"{a['id']}-{b['id']}")
    R.add("R-VOICE", len(long_run) <= 1, "no long explanatory LINEs back to back" if len(long_run) <= 1
          else f"back-to-back long LINEs: {long_run[:6]}", severity="warn")


def check_open_close(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    v = src["video"]
    h = tl[0]
    hw = c.count_words(h["scene"]["line"])
    R.add("R-OPEN", hw <= lim["hook_line_max_words"], f"hook LINE is {hw} words as written (max {lim['hook_line_max_words']})")
    feat = v.get("hook_named_feature")
    has_concrete = bool(c.number_tokens(h["scene"]["line"])) or (feat and norm(feat) in norm(h["scene"]["line"]))
    R.add("R-OPEN", has_concrete, "hook LINE carries a number, price, or named feature" if has_concrete
          else "hook LINE needs one concrete number, price, or named feature")
    slam = [e for e in h["scene"].get("on_screen_text", []) if c.abs_text_start(e, h["start"], h["dur"]) <= lim["hook_slam_window_s"]]
    R.add("R-OPEN", len(slam) >= 1, "hook word slams on screen in the first 3s" if slam else "no slam-in text within 3s")
    changes = len([sh for sh in h["shots"] if 0 < sh["start"] < lim["hook_slam_window_s"]]) + len(slam)
    R.add("R-OPEN", changes >= lim["hook_min_visual_changes"], f"{changes} visual changes in the first 3s (need {lim['hook_min_visual_changes']})")
    cap = v.get("gen_video_cap", cfg["defaults"]["gen_video_cap"])
    first_gen = c.gen_video_of(h["shots"][0]["src"]) if h["shots"] else None
    if cap > 0:
        ok = bool(first_gen and first_gen.get("role") == "hook")
        R.add("R-OPEN", ok, "first shot is the generated hook clip" if ok else "shot 1a must be the generated hook clip (role hook) when the cap is above 0")
    last = tl[-1]
    R.add("R-CLOSE", last["words"] <= lim["closing_line_max_words"], f"closing LINE is {last['words']} words (max {lim['closing_line_max_words']})")
    R.add("R-CLOSE", last["dur"] >= lim["end_screen_min_s"] - 0.01, f"end screen runs {last['dur']:.1f}s (min {lim['end_screen_min_s']})")
    ok_end = last["scene"].get("section") == "end_screen" and all(c.shot_tag(sh["src"]) in ("GEN-VIDEO", "B-ROLL") for sh in last["shots"])
    R.add("R-CLOSE", ok_end, "final scene is the end-screen backdrop (the pipeline renders the end-screen composition on it)" if ok_end
          else "final scene must be section end_screen with GEN-VIDEO or B-ROLL shots as its backdrop")
    es = [s for s in tl if s["scene"].get("end_screen_start")]
    lead_lo, lead_hi = lim["end_screen_lead_s"]
    ok = len(es) == 1 and lead_lo - 0.5 <= tl[-1]["end"] - es[0]["start"] <= lead_hi + 0.5
    R.add("R-CLOSE", ok, f"END SCREEN START is {lead_lo}-{lead_hi}s before the end" if ok
          else f"exactly one scene needs end_screen_start, starting {lead_lo}-{lead_hi}s before the end (found {len(es)})")


def check_secret(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    by = {}
    for s in tl:
        by.setdefault(s["scene"]["section"], []).append(s)
    sm = by.get("segment_map", [])
    lo, hi = lim["segment_map_window_s"]
    R.add("R-SECRET", bool(sm) and lo <= sm[0]["start"] <= hi, f"segment map starts at {c.mmss(sm[0]['start']) if sm else 'n/a'} (window 0:45-1:30)")
    hr = by.get("held_reveal", [])
    lo, hi = lim["held_reveal_window_s"]
    R.add("R-SECRET", bool(hr) and lo <= hr[0]["start"] <= hi, f"held reveal starts at {c.mmss(hr[0]['start']) if hr else 'n/a'} (window 6:45-8:00)")
    held = src["video"].get("held_reveal", {})
    num = held.get("number", "")
    R.add("R-SECRET", bool(num), "held reveal number recorded" if num else "video.held_reveal.number is empty")
    if num and hr:
        key = c.digits_of(num)
        early = []
        for s in tl:
            if s["start"] >= hr[0]["start"]:
                break
            toks = c.number_tokens(s["scene"]["line"]) + [t for x in scene_texts(s["scene"]) for t in c.number_tokens(x)]
            if key and any(c.digits_of(t) == key for t in toks):
                early.append(s["id"])
        R.add("R-SECRET", not early, "held number stays hidden until the reveal" if not early else f"held number appears early in scenes {early}")
    soft = by.get("soft_cta", [])
    lo, hi = lim["soft_cta_window_s"]
    ok = bool(soft) and lo <= soft[0]["start"] <= hi and not soft[0]["scene"].get("cta_button")
    R.add("R-SECRET", ok, "soft CTA is spoken at about 4:00 with no button" if ok else "soft_cta scene missing, outside 3:30-4:30, or has a button", severity="standard")
    ag = by.get("agitation", [])
    R.add("R-SECRET", any(s["scene"].get("addresses_objection") for s in ag), "objection beat present in agitation" if any(s["scene"].get("addresses_objection") for s in ag) else "agitation needs a scene with addresses_objection")
    R.add("R-SECRET", any(s["scene"].get("names_cost_of_inaction") for s in ag), "cost of inaction named in agitation" if any(s["scene"].get("names_cost_of_inaction") for s in ag) else "agitation needs a scene with names_cost_of_inaction: true")
    rec = by.get("recap", [])
    R.add("R-SECRET", bool(rec) and "comment" in norm(rec[0]["scene"]["line"]), "recap carries the comment bait" if rec and "comment" in norm(rec[0]["scene"]["line"]) else "recap LINE needs the comment bait ('Comment A or B')")
    off = by.get("offer", [])
    R.add("R-CTA", bool(off) and "link" in norm(off[0]["scene"]["line"]), "offer scene tells viewers to use the link first" if off and "link" in norm(off[0]["scene"]["line"]) else "offer LINE must tell viewers to use the link before creating an account")
    proof = by.get("third_party_proof", [])
    ok = bool(proof) and all(len(c.number_tokens(" ".join(scene_texts(p["scene"])))) >= 2 for p in proof if c.number_tokens(p["scene"]["line"]))
    R.add("R-PROOF", ok, "ratings show a number and a review count on screen" if ok else "third_party_proof scenes need rating and review count in on_screen_text")
    # retention beat gaps
    beats = [0.0] + [s["start"] for s in tl if s["scene"].get("retention_beat")] + [tl[-1]["end"]]
    gaps = [b - a for a, b in zip(beats, beats[1:])]
    R.add("R-RETENTION", max(gaps) <= lim["retention_gap_s"] + 0.5, f"longest stretch without a retention beat: {max(gaps):.0f}s (max 90)", severity="standard")
    chs = [(s["start"], s["scene"]["chapter"]) for s in tl if s["scene"].get("chapter")]
    ok = len(chs) >= lim["chapter_min_count"] and chs and chs[0][0] < 0.5
    if ok:
        pts = [t for t, _ in chs] + [tl[-1]["end"]]
        ok = all(b - a >= lim["chapter_min_len_s"] for a, b in zip(pts, pts[1:]))
    R.add("R-CHAPTERS", ok, f"{len(chs)} chapters, first at 0:00, each 10s or longer" if ok else "chapters need 3+ entries, the first at 0:00, each 10s or longer")


def check_proof(R, ctx):
    tl = ctx["tl"]
    miss = []
    for s in tl:
        toks = c.number_tokens(s["scene"]["line"])
        if not toks:
            continue
        screen = {c.digits_of(t) for x in scene_texts(s["scene"]) for t in c.number_tokens(x)}
        for t in toks:
            if c.digits_of(t) not in screen:
                miss.append(f"{s['id']}: {t}")
    R.add("R-PROOF", not miss, "every spoken number is on screen in the same scene" if not miss else f"numbers missing from on-screen text: {miss[:10]}")


def check_narration(R, ctx):
    tl = ctx["tl"]
    bad = []
    for s in tl:
        if re.search(r"[0-9$%]", s["narration"]):
            bad.append(s["id"])
    R.add("R-NARRATION", not bad, "narration has no digits, $ or % (numbers spelled out)" if not bad else f"unconverted numerals in narration of scenes {bad}")
    names = [ctx["src"]["video"]["product_a"], ctx["src"]["video"]["product_b"]]
    prons = ctx["cfg"].get("pronunciations", {})
    miss = [n for n in names if n not in prons]
    R.add("R-NARRATION", not miss, "both product names have pronunciation entries" if not miss else f"add pronunciation entries for {miss}", severity="warn")
    unv = [n for n in names if n in prons and not prons[n].get("verified")]
    R.add("R-NARRATION", not unv, "pronunciations verified" if not unv else f"run the 60-second Chatterbox test and set verified for {unv}", severity="warn")
    if ctx["stage"] == "post":
        p = ctx["out"] / f"{ctx['slug']}-narration.txt"
        if p.exists():
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            same = lines == [s["narration"] for s in tl]
            R.add("R-NARRATION", same, "narration file matches the source file" if same else "narration file differs from the source file; rebuild")
            total = sum(c.count_words(l) for l in lines)
            R.add("R-NARRATION", total == sum(s["words"] for s in tl), f"narration word count {total} matches the counted total")


def check_shots(R, ctx):
    cfg, tl = ctx["cfg"], ctx["tl"]
    runtime = tl[-1]["end"]
    bad_tag, bad_dur, bad_fields, unfit, drift, bad_stat = [], [], [], [], [], []
    for s in tl:
        if s["shots"] and not s["fit"]:
            unfit.append(f"scene {s['id']} ({len(s['shots'])} shots for {s['narr_end'] - s['narr_start']:.0f}s of narration)")
        if not s["shots"] and not s.get("cover"):
            unfit.append(f"scene {s['id']} has no shots")
        if abs(s["start"] - s["narr_start"]) > 3.0:
            drift.append(f"scene {s['id']} {s['start'] - s['narr_start']:+.0f}s")
        for sh in s["shots"]:
            raw = sh["src"]
            tag = c.shot_tag(raw)
            if tag not in c.TAGS:
                bad_tag.append(f"{sh['id']}: {tag}")
                continue
            lo, hi = c.shot_bounds(raw)
            if not (lo <= sh["dur"] <= hi) or sh["dur"] != int(sh["dur"]):
                bad_dur.append(f"{sh['id']} {sh['dur']:.0f}s ({tag}, needs {lo}-{hi}s)")
            if tag == "B-ROLL" and not raw.get("text"):
                bad_fields.append(f"{sh['id']}: B-ROLL needs text")
            if tag in ("GEN-VIDEO", "GEN-STILL") and not raw.get("prompt_id"):
                bad_fields.append(f"{sh['id']}: {tag} needs prompt_id")
            if tag in ("ASSET-SHOT", "ASSET-CLIP", "ASSET-BRAND") and not raw.get("product"):
                bad_fields.append(f"{sh['id']}: {tag} needs product")
            if tag in ("ASSET-SHOT", "ASSET-CLIP") and not raw.get("detail"):
                bad_fields.append(f"{sh['id']}: {tag} needs detail (the exact screen)")
            if tag == "STAT":
                st = raw.get("stat") or {}
                miss = [k for k in ("value", "label", "source") if not st.get(k)]
                if miss:
                    bad_stat.append(f"{sh['id']}: missing {miss}")
    R.add("R-SHOTS", not bad_tag, "every shot uses a pipeline tag" if not bad_tag else f"unknown shot tags: {bad_tag}")
    R.add("R-SHOTS", not bad_dur, "shots are whole seconds, 5s or less (stills and stat cards 9-16s)" if not bad_dur else f"shot durations the pipeline rejects: {bad_dur[:8]}")
    R.add("R-SHOTS", not unfit, "every scene's shots fill its narration time" if not unfit else f"shots cannot fill the scene (add or remove shots): {unfit[:8]}")
    R.add("R-SHOTS", not bad_fields, "every shot has the fields its tag needs" if not bad_fields else f"missing shot fields: {bad_fields[:8]}")
    R.add("R-SHOTS", not bad_stat, "every stat card has value, label and source" if not bad_stat else f"stat cards without a source or label: {bad_stat}")
    R.add("R-SHOTS", not drift, "shot timeline stays within 3s of the narration estimate" if not drift else f"shot timeline drifts from narration: {drift[:8]}", severity="standard")
    broll = sum(sh["dur"] for s in tl for sh in s["shots"] if c.shot_tag(sh["src"]) == "B-ROLL")
    share = broll / runtime if runtime else 0
    R.add("R-SHOTS", share <= 0.40, f"B-roll is {share * 100:.0f}% of runtime (max 40%)")
    lim = cfg["limits"]
    wlo, whi = lim.get("broll_brief_words", [10, 35])
    texts = [(sh["id"], " ".join(sh["src"].get("text", "").lower().split())) for s in tl for sh in s["shots"] if c.shot_tag(sh["src"]) == "B-ROLL"]
    neg = set(w for w in cfg["negation_words_in_prompts"] if " " not in w)
    bad_len = [f"{i} ({len(t.split())}w)" for i, t in texts if not (wlo <= len(t.split()) <= whi)]
    # The Picture half is what the stock search sees, so it must say what is there. The Means half repeats the line.
    bad_neg = [i for i, t in texts if set(re.findall(r"[a-z']+", t.split("picture:", 1)[-1])) & neg]
    no_form = [i for i, t in texts if "means:" not in t or "picture:" not in t]
    R.add("R-BROLL", not no_form, "every B-roll brief is a Means / Picture sentence pair" if not no_form else f"B-roll briefs missing Means: or Picture: {no_form[:8]}")
    R.add("R-BROLL", not bad_len, f"every B-roll brief is {wlo}-{whi} words" if not bad_len else f"B-roll briefs outside {wlo}-{whi} words: {bad_len[:8]}")
    R.add("R-BROLL", not bad_neg, "B-roll pictures say what is there, not what is missing" if not bad_neg else f"negation words in B-roll pictures: {bad_neg[:8]}")
    flat = [sh for s in tl for sh in s["shots"] if c.shot_tag(sh["src"]) == "B-ROLL"]
    bad_search = [sh["id"] for sh in flat if not (1 <= len(str(sh["src"].get("search", "")).split()) <= 2)]
    R.add("R-BROLL", not bad_search, "every B-roll shot has a one- or two-noun search" if not bad_search else f"B-roll shots need a 1-2 noun search: {bad_search[:8]}")
    nouns = [str(sh["src"].get("search", "")).strip().lower() for sh in flat]
    over = sorted({n for n in nouns if n and nouns.count(n) > lim.get("broll_noun_max_uses", 3)})
    adj = [f"{a['id']}/{b['id']}" for a, b in zip(flat, flat[1:]) if str(a["src"].get("search", "")).strip().lower() and str(a["src"].get("search", "")).strip().lower() == str(b["src"].get("search", "")).strip().lower()]
    R.add("R-BROLL", not over, "no search noun is used more than 3 times" if not over else f"search nouns used too often: {over}")
    R.add("R-BROLL", not adj, "no search noun repeats back to back" if not adj else f"search noun repeats back to back: {adj[:8]}")
    dup = [f"{a['id']}/{b['id']}" for a, b in zip(flat, flat[1:]) if a["src"].get("text") == b["src"].get("text")]
    R.add("R-BROLL", not dup, "no two adjacent B-roll shots share the same brief" if not dup else f"repeated B-roll briefs: {dup[:6]}", severity="warn")


def check_inserts(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    cap = src["video"].get("overlay_cap_override") or lim["overlay_cap"]
    shots_c = {"a": 0, "b": 0}
    recs_c = {"a": 0, "b": 0}
    stills = 0
    for s in tl:
        for sh in s["shots"]:
            tag = c.shot_tag(sh["src"])
            p = str(sh["src"].get("product", "a")).lower()
            ps = ["a", "b"] if p == "ab" else [p]   # "ab" = both products side by side
            if tag == "ASSET-SHOT":
                for q in ps:
                    shots_c[q] = shots_c.get(q, 0) + 1
            elif tag == "ASSET-CLIP":
                for q in ps:
                    recs_c[q] = recs_c.get(q, 0) + 1
            elif tag == "GEN-STILL":
                stills += 1
    total = sum(1 for s in tl for sh in s["shots"] if c.shot_tag(sh["src"]) in ("ASSET-SHOT", "ASSET-CLIP"))
    R.add("R-INSERT", total <= cap, f"{total} real captures (cap {cap})")
    n_shots = sum(1 for s in tl for sh in s["shots"] if c.shot_tag(sh["src"]) == "ASSET-SHOT")
    R.add("R-INSERT", n_shots <= lim["screenshot_cap"], f"{n_shots} ASSET-SHOT screenshots (max {lim['screenshot_cap']})")
    n_recs = sum(1 for s in tl for sh in s["shots"] if c.shot_tag(sh["src"]) == "ASSET-CLIP")
    R.add("R-INSERT", n_recs <= lim["screen_rec_cap"], f"{n_recs} ASSET-CLIP screen recordings (max {lim['screen_rec_cap']})")
    R.add("R-INSERT", stills <= lim["still_cap"], f"{stills} GEN-STILL stills (max {lim['still_cap']})")
    ok = max(shots_c.values()) <= lim["screenshots_per_product"] and max(recs_c.values()) <= lim["screen_rec_per_product"]
    R.add("R-INSERT", ok, "per-product limits respected" if ok else "per-product limit exceeded (3 screenshots, 1 screen recording each)")
    pa, pb = src["video"]["product_a"], src["video"]["product_b"]
    if is_ghl(pb) or is_ghl(pa):
        first = {}
        for s in tl:
            for sh in s["shots"]:
                if c.shot_tag(sh["src"]) in ("ASSET-SHOT", "ASSET-CLIP"):
                    for q in (["a", "b"] if str(sh["src"].get("product", "a")).lower() == "ab" else [str(sh["src"].get("product", "a")).lower()]):
                        first.setdefault(q, sh["start"])
        ok = "a" not in first or "b" not in first or first["a"] <= first["b"]
        R.add("R-GHL-FIRST", ok, "product A's first capture comes before product B's" if ok else "product A's first capture must come first")


def check_compare(R, ctx):
    """R-COMPARE: side-by-side comparison cards are required, product A on the left."""
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    pa, pb = src["video"]["product_a"], src["video"]["product_b"]
    kinds_needed = list(lim.get("compare_kinds", []))
    seen, bad = {}, []
    for s in tl:
        for sh in s["shots"]:
            raw = sh["src"]
            if c.shot_tag(raw) != "STAT":
                continue
            cmpd = (raw.get("stat") or {}).get("compare")
            if cmpd is None:
                continue
            rows = cmpd.get("rows") or []
            kind = cmpd.get("kind")
            if kind not in kinds_needed:
                bad.append(f"{sh['id']}: kind must be one of {kinds_needed}")
            if cmpd.get("a") != pa or cmpd.get("b") != pb:
                bad.append(f"{sh['id']}: columns must be {pa} (left) then {pb}")
            if not (2 <= len(rows) <= lim.get("compare_rows_max", 6)):
                bad.append(f"{sh['id']}: needs 2-{lim.get('compare_rows_max', 6)} rows")
            for r in rows:
                if not all(str(r.get(k, "")).strip() for k in ("label", "a", "b")):
                    bad.append(f"{sh['id']}: every row needs label, a and b")
                    break
            seen[kind] = seen.get(kind, 0) + 1
    R.add("R-COMPARE", not bad, "every comparison card is well formed, product A on the left" if not bad else f"comparison card problems: {bad[:8]}")
    missing = [k for k in kinds_needed if k not in seen]
    total = sum(seen.values())
    R.add("R-COMPARE", not missing and total >= lim.get("compare_cards_min", 0),
          f"{total} side-by-side comparison cards ({', '.join(sorted(seen))})" if not missing else f"add side-by-side STAT comparison cards for: {missing}")
    if total < lim.get("compare_cards_min", 0) and not missing:
        R.add("R-COMPARE", False, f"{total} comparison cards, need at least {lim.get('compare_cards_min')}")
    # Statics sell: comparison cards must hold a real share of the runtime, not just a few seconds.
    runtime = sum(s["dur"] for s in tl) or 1
    card_s = sum(sh["dur"] for s in tl for sh in s["shots"]
                 if c.shot_tag(sh["src"]) == "STAT" and (sh["src"].get("stat") or {}).get("compare"))
    share, need = card_s / runtime, lim.get("compare_share_min", 0)
    R.add("R-COMPARE", share >= need, f"comparison cards fill {share:.0%} of the runtime (min {need:.0%})")


def check_genlimit(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    v = src["video"]
    cap = v.get("gen_video_cap", cfg["defaults"]["gen_video_cap"])
    R.add("R-GENLIMIT", 0 <= cap <= lim["gen_video_cap_max"], f"cap is {cap} (range 0-{lim['gen_video_cap_max']})")
    roles_allowed = Counter(lim["gen_fill_order"][:max(0, cap)])
    used = Counter()
    bad_sec, bad_role = [], []
    for s in tl:
        for sh in s["shots"]:
            g = c.gen_video_of(sh["src"])
            if not g:
                continue
            role = g.get("role")
            used[role] += 1
            if role not in cfg["gen_role_sections"]:
                bad_role.append(f"{sh['id']}: {role}")
            elif s["scene"]["section"] not in cfg["gen_role_sections"][role]:
                bad_sec.append(f"{sh['id']} role {role} in section {s['scene']['section']}")
    total = sum(used.values())
    R.add("R-GENLIMIT", total <= cap, f"{total} generated clips (cap {cap})")
    R.add("R-GENLIMIT", not bad_role, "all clip roles valid" if not bad_role else f"unknown roles: {bad_role}")
    R.add("R-GENLIMIT", not bad_sec, "clips only in the allowed scenes" if not bad_sec else f"clips outside allowed scenes: {bad_sec}")
    over = [f"{r} x{n}" for r, n in used.items() if n > roles_allowed.get(r, 0)]
    R.add("R-GENLIMIT", not over, "clips follow the fill order for this cap" if not over else f"clips outside the fill order for cap {cap}: {over}")
    wan = src.get("prompts", {}).get("wan", {})
    lo, hi = lim["wan_prompt_words"]
    bad_w, bad_neg = [], []
    neg = set(w for w in cfg["negation_words_in_prompts"] if " " not in w)
    for pid, p in wan.items():
        n = len(p["text"].split())
        if not (lo <= n <= hi):
            bad_w.append(f"{pid} ({n}w)")
        toks = set(re.findall(r"[a-z']+", p["text"].lower()))
        if toks & neg or any(ph in p["text"].lower() for ph in cfg["negation_words_in_prompts"] if " " in ph):
            bad_neg.append(pid)
    R.add("R-GENLIMIT", not bad_w, "Wan prompts are 25-45 words" if not bad_w else f"Wan prompts outside 25-45 words: {bad_w}")
    R.add("R-GENLIMIT", not bad_neg, "Wan prompts describe only what is there" if not bad_neg else f"negation words in Wan prompts (describe what is there instead): {bad_neg}")
    refs = {c.gen_video_of(sh["src"])["prompt_id"] for s in tl for sh in s["shots"] if c.gen_video_of(sh["src"])}
    missing = sorted(r for r in refs if r not in wan)
    R.add("R-GENLIMIT", not missing, "every generated clip has a prompt" if not missing else f"clips without a Wan prompt: {missing}")
    style = cfg["visual_style"]
    dark = [pid for pid, p in wan.items() if re.search(r"\bdark\b|\bmoody\b|\bgloomy\b", p["text"].lower())]
    R.add("R-GENLIMIT", not dark, "no dark or moody clip prompts" if not dark else f"prompts drift toward the dark/moody look the channel dropped: {dark}", severity="warn")


def check_nofake(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    terms = [(t, words_re(t)) for t in cfg["forbidden_visual_terms"]]
    hits = []
    for pid, p in list(src.get("prompts", {}).get("flux", {}).items()) + list(src.get("prompts", {}).get("wan", {}).items()):
        for t, rx in terms:
            if rx.search(p["text"].lower()):
                hits.append(f"prompt {pid}: '{t}'")
    for s in tl:
        for sh in s["shots"]:
            if c.shot_tag(sh["src"]) != "B-ROLL":
                continue
            blob = str(sh["src"].get("text", "")).lower()
            for t, rx in terms:
                if rx.search(blob):
                    hits.append(f"B-roll {sh['id']}: '{t}'")
    R.add("R-NOFAKE", not hits, "no visual description resembles a named product's interface, logo, or pricing page" if not hits else f"forbidden visual terms: {hits[:10]}")


def check_stills(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    flux = src.get("prompts", {}).get("flux", {})
    neg = set(w for w in cfg["negation_words_in_prompts"] if " " not in w)
    bad_neg, bad_words, no_kb, bad_ref = [], [], [], []
    refs = []
    for s in tl:
        for sh in s["shots"]:
            if c.shot_tag(sh["src"]) == "GEN-STILL":
                refs.append(sh["src"].get("prompt_id"))
    for r in refs:
        if r not in flux:
            bad_ref.append(r)
    for pid, p in flux.items():
        text = p["text"].lower() + " " + cfg["flux_attach"].lower()
        if set(re.findall(r"[a-z']+", p["text"].lower())) & neg:
            bad_neg.append(pid)
        miss = [w for w in cfg["flux_required_words"] if w not in text]
        if miss:
            bad_words.append(f"{pid}: {miss}")
    R.add("R-STILL", not bad_ref, "every GEN-STILL shot has a FLUX prompt" if not bad_ref else f"missing FLUX prompts: {bad_ref}")
    R.add("R-STILL", not bad_neg, "FLUX prompts describe only what is there" if not bad_neg else f"negation words in FLUX prompts: {bad_neg}")
    used = [flux[r] for r in dict.fromkeys(refs) if r in flux]
    no_kb = [r for r in dict.fromkeys(refs) if r in flux and not str(flux[r].get("ken_burns", "")).strip()]
    no_why = [r for r in dict.fromkeys(refs) if r in flux and len(str(flux[r].get("purpose", "")).split()) < 4]
    R.add("R-STILL", not no_kb, "every still names its Ken Burns move" if not no_kb else f"stills missing a ken_burns move (slow push direction): {no_kb}")
    R.add("R-STILL", not no_why, "every still states what point it supports" if not no_why else f"stills missing a purpose (4+ words, the point it makes for this scene): {no_why}")
    on_topic = sum(1 for s in tl for sh in s["shots"] if c.shot_tag(sh["src"]) == "GEN-STILL" and s["scene"]["section"] in ("pricing", "category", "held_reveal", "switching_cost"))
    n_st = len(refs)
    R.add("R-STILL", n_st == 0 or on_topic * 4 >= n_st, f"{on_topic} of {n_st} stills sit in pricing, feature, switching-cost or reveal scenes (at least a quarter)", severity="standard")
    R.add("R-STILL", not bad_words, "FLUX prompts carry depth layers and 16:9" if not bad_words else f"FLUX prompts missing required words: {bad_words}")
    fam = src["video"].get("style_families", [])
    if flux:
        R.add("R-STILL", 3 <= len(fam) <= 4, f"{len(fam)} style families chosen (3 or 4)")
        seq = [flux[r].get("style") for r in refs if r in flux and not flux[r].get("backdrop")]
        rep = [f"{a}/{b}" for a, b in zip(seq, seq[1:]) if a and a == b]
        R.add("R-STILL", not rep, "no style family repeats in adjacent stills" if not rep else f"adjacent stills share a style family: {rep}")
    unused = sorted(set(flux) - set(refs))
    R.add("R-STILL", not unused, "no unused FLUX prompts" if not unused else f"prompts never used: {unused}", severity="warn")


def check_avatar(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    lim = cfg["limits"]
    mode = (src["video"].get("avatar") or {}).get("mode", "none")
    on = [(s, sh) for s in tl for sh in s["shots"] if sh["src"].get("avatar")]
    if mode == "none":
        R.add("R-AVATAR", not on, "no avatar shots (avatar not used)" if not on else "avatar shots present but avatar mode is none")
        return
    total = sum(s["dur"] for s in tl if s["scene"].get("avatar_block"))
    R.add("R-AVATAR", lim["avatar_min_s"] <= total <= lim["avatar_max_s"],
          f"avatar blocks total {c.mmss(total)} (target 2:15-3:30)", severity="standard")
    out_of_block = [sh["id"] for s, sh in on if not s["scene"].get("avatar_block")]
    R.add("R-AVATAR", not out_of_block, "avatar is on only inside the three blocks" if not out_of_block else f"avatar on outside its blocks: {out_of_block[:8]}")
    full = [sh["id"] for s, sh in on if c.shot_tag(sh["src"]) in c.FULLSCREEN_TAGS]
    R.add("R-AVATAR", not full, "avatar is never over a stat card or real capture" if not full else f"avatar over a full-screen shot: {full[:8]}")
    on_number = []
    for s in tl:
        for frac in s["number_positions"]:
            sh = c.shot_at(s, frac)
            if sh and sh["src"].get("avatar"):
                on_number.append(sh["id"])
    R.add("R-AVATAR", not on_number, "avatar is never on screen while a number is spoken" if not on_number else f"avatar on screen during a spoken number: {sorted(set(on_number))}")
    # longest unbroken avatar run (cut to a base visual every 8-10 s)
    flat = [sh for s in tl for sh in s["shots"]]
    longest, run_len = 0.0, 0.0
    for sh in flat:
        run_len = run_len + sh["dur"] if sh["src"].get("avatar") else 0.0
        longest = max(longest, run_len)
    R.add("R-AVATAR", longest <= 10.0, f"longest unbroken avatar stretch {longest:.0f}s (max 10s)" if longest <= 10.0 else f"avatar stays on {longest:.0f}s without a cut to a base visual (max 10s)", severity="standard")
    blocks = sorted({s["scene"]["avatar_block"] for s in tl if s["scene"].get("avatar_block")})
    R.add("R-AVATAR", blocks == [1, 2, 3], f"avatar blocks present: {blocks} (need 1, 2, 3)", severity="standard")


def check_aiflags(R, ctx):
    flags = ctx["flags"]
    R.add("R-AIFLAG", flags["synthetic_voice"] is True, "synthetic_voice is true (Chatterbox)")
    if ctx["stage"] != "post":
        return
    out, slug = ctx["out"], ctx["slug"]
    mp = out / f"{slug}-scene-manifest.json"
    if not mp.exists():
        R.add("R-AIFLAG", False, "scene manifest missing")
        return
    man = c.load_json(mp)
    mf = man.get("ai_flags", {})
    same = all(mf.get(k) == flags[k] for k in ("synthetic_voice", "realistic_ai_visuals", "ai_person_visible"))
    R.add("R-AIFLAG", same, "manifest flags match the shot list" if same else f"manifest flags {mf} differ from computed flags")
    leaks = [e["shot"] for e in man.get("shots", []) if any(k in e for k in ("ai_flags", "synthetic_voice", "realistic_ai_visuals", "ai_person_visible"))]
    R.add("R-AIFLAG", not leaks, "shot entries carry no AI flag copies" if not leaks else f"AI flag copies in shot entries: {leaks[:5]}")
    for fname, label in ((f"{slug}-locked-facts.md", "LOCKED_FACTS"), (f"{slug}-upload-checklist.md", "upload checklist")):
        p = out / fname
        if not p.exists():
            R.add("R-AIFLAG", False, f"{label} file missing")
            continue
        txt = p.read_text(encoding="utf-8")
        ok = True
        for k in ("synthetic_voice", "realistic_ai_visuals", "ai_person_visible"):
            m = re.search(rf"{k}[:=\s]+(true|false)", txt)
            if not m or (m.group(1) == "true") != flags[k]:
                ok = False
        R.add("R-AIFLAG", ok, f"{label} flags match the manifest" if ok else f"{label} flags differ from the manifest")


def check_spec(R, ctx):
    cfg = ctx["cfg"]
    if not cfg["wan"].get("confirmed"):
        R.add("R-SPEC", False, "Wan output size and fps not confirmed on a test clip (assumed 1280x704 at 24fps, conformed to 25fps)", severity="warn")
    if ctx["stage"] != "post":
        return
    mp = ctx["out"] / f"{ctx['slug']}-scene-manifest.json"
    if not mp.exists():
        return
    man = c.load_json(mp)
    fr = man.get("frame", {})
    ok = fr.get("width") == 1920 and fr.get("height") == 1080 and fr.get("fps") == 25
    R.add("R-SPEC", ok, "frame is 1920x1080 at 25fps" if ok else f"bad frame spec: {fr}")
    bad = [e["shot"] for e in man.get("shots", []) if e.get("aspect") != "16:9" or e.get("fps") != 25]
    R.add("R-SPEC", not bad, "every shot is 16:9 at 25fps" if not bad else f"shots off spec: {bad[:6]}")


def check_cta(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    pa, pb = src["video"]["product_a"], src["video"]["product_b"]
    names = {"a": pa, "b": pb}
    scenes = [s["scene"] for s in tl]
    bad, order = [], []
    verdict_products = []
    for i, sc in enumerate(scenes):
        if sc["section"] != "verdict":
            continue
        group = [sc]
        if i + 1 < len(scenes) and scenes[i + 1]["section"] == "verdict_reason":
            group.append(scenes[i + 1])
        prod = str(sc.get("verdict_product", "")).lower()
        verdict_products.append(prod)
        want = cfg["cta"]["verdict"].format(product=names.get(prod, "?"))
        ctas = [g["cta_button"]["wording"] for g in group if g.get("cta_button")]
        if want not in ctas:
            bad.append(f"scene {sc['id']} needs button '{want}'")
    R.add("R-CTA", not bad, "each verdict has its own CTA button with the fixed wording" if not bad else "; ".join(bad))
    off = [sc for sc in scenes if sc["section"] == "offer"]
    ok = bool(off) and off[0].get("cta_button", {}).get("wording") == cfg["cta"]["offer"]
    R.add("R-CTA", ok, "offer button reads 'Use my link first'" if ok else "offer scene button must read 'Use my link first'")
    stray = [sc["id"] for sc in scenes if sc.get("cta_button") and sc["section"] not in ("verdict", "verdict_reason", "offer")]
    R.add("R-CTA", not stray, "buttons only on verdicts and the offer" if not stray else f"buttons on other scenes: {stray}")
    if len(verdict_products) > 1 and ("a" in verdict_products and "b" in verdict_products):
        first_a = verdict_products.index("a") < verdict_products.index("b")
        R.add("R-GHL-FIRST", first_a or not (is_ghl(pa) or is_ghl(pb)), "product A's verdict comes first" if first_a else "product A's verdict must come first when GoHighLevel is in the video")
    reason = src["video"].get("single_winner_reason", "")
    if verdict_products and len(set(verdict_products)) == 1:
        R.add("R-HONESTY", bool(reason), "one product wins every segment with a recorded reason" if reason
              else "one product wins every segment; set video.single_winner_reason (evidence-based) or find an honest segment for the other")
    else:
        R.add("R-HONESTY", True, "each product wins at least one segment")


def check_ghl_first(R, ctx):
    src, tl = ctx["src"], ctx["tl"]
    pa, pb = src["video"]["product_a"], src["video"]["product_b"]
    if is_ghl(pb) and not is_ghl(pa):
        R.add("R-GHL-FIRST", False, "GoHighLevel must be Product A")
        return
    if not (is_ghl(pa) or is_ghl(pb)):
        return
    other = pb
    bad = []
    for s in tl:
        for t in [s["scene"]["line"]] + scene_texts(s["scene"]):
            tl_ = norm(t)
            ia = min([i for i in (tl_.find(norm(pa)), tl_.find("go high level")) if i >= 0], default=-1)
            ib = tl_.find(norm(other))
            if ia >= 0 and ib >= 0 and ib < ia:
                bad.append(s["id"])
    R.add("R-GHL-FIRST", not bad, "GoHighLevel is named first wherever both products appear" if not bad else f"GoHighLevel not first in scenes {sorted(set(bad))}")


def check_tier(R, ctx):
    src, cfg, tl = ctx["src"], ctx["cfg"], ctx["tl"]
    tiers = src["video"].get("tiers", {})
    ok = all(tiers.get(k, {}).get("tier") in cfg["badges"] for k in ("a", "b"))
    R.add("R-HONESTY", ok, "both products carry a valid tier" if ok else "video.tiers.a/b need a tier of research, demo, or hands-on")
    if not ok:
        return
    for k in ("a", "b"):
        if tiers[k]["tier"] == "hands-on":
            R.add("R-HONESTY", bool(tiers[k].get("tested_components")), f"product {k.upper()} lists its tested components" if tiers[k].get("tested_components") else f"hands-on product {k.upper()} needs tested_components")
    rx = re.compile(cfg["first_person_usage_regex"], re.I)
    bad = []
    for s in tl:
        sc = s["scene"]
        if rx.search(sc["line"]):
            fp = sc.get("first_person") or {}
            p = str(fp.get("product", "")).lower()
            comp = fp.get("component")
            if p not in tiers or tiers[p]["tier"] != "hands-on" or comp not in tiers[p].get("tested_components", []):
                bad.append(f"{s['id']}")
    R.add("R-HONESTY", not bad, "first-person usage claims map to hands-on tested components" if not bad else f"first-person usage language without a matching hands-on component in scenes {bad}")


def check_vary(R, ctx):
    src, tl, log = ctx["src"], ctx["tl"], ctx["log"]
    log = [e for e in (log or []) if e.get("video") != ctx.get("slug")]  # a rebuild must not compare against its own entry
    var = src["video"].get("variation", {})
    need = ["category_order", "micro_authority_device", "hook_device", "hook_type", "opener_device", "visual_motif"]
    miss = [k for k in need if not var.get(k)]
    R.add("R-VARY", not miss, "all six variation choices recorded" if not miss else f"variation fields missing: {miss}")
    if not log:
        R.add("R-VARY", True, "no prior log entries, nothing to compare against")
        return
    last = log[-1]
    same = [k for k in need if var.get(k) and var.get(k) == last.get(k)]
    R.add("R-VARY", not same, "choices differ from the most recent log entry" if not same else f"repeats the last video's choices: {same}")
    recent = [e.get("hook_type") for e in log[-3:]]
    R.add("R-VARY", var.get("hook_type") not in recent, "hook type not used in the last three videos" if var.get("hook_type") not in recent else f"hook type '{var.get('hook_type')}' was used in the last three videos")
    hl = tl[0]["scene"]["line"]
    toks = set(re.findall(r"[a-z0-9']+", norm(hl)))
    close = []
    for e in log:
        pl = e.get("hook_line", "")
        pt = set(re.findall(r"[a-z0-9']+", norm(pl)))
        if pt and len(toks & pt) / max(1, len(toks | pt)) >= 0.7:
            close.append(pl)
    R.add("R-VARY", not close, "hook wording differs from prior hook lines" if not close else f"hook too close to prior lines: {close}")


def check_apify(R, ctx):
    ws = ctx["workspace"]
    cap = ctx["cfg"]["limits"]["apify_cap_usd"]
    if ws:
        p = Path(ws) / "apify-run-log.json"
        if p.exists():
            log = c.load_json(p)
            probs = ab.check_run_log(log, cap)
            R.add("R-APIFY-CAP", not probs, f"{len(log.get('runs', []))} Apify runs, total ${ab.tally(log):.2f} of ${cap:.2f}, per-run stops respected" if not probs else "; ".join(probs), severity="standard")
        else:
            spend = ctx["src"].get("research_summary", {}).get("apify_spend", {})
            R.add("R-APIFY-CAP", not spend, "no Apify run log needed (no spend recorded)" if not spend else "spend recorded but apify-run-log.json not found in the workspace", severity="warn")
        t = Path(ws) / "apify-cost-table.json"
        if t.exists():
            table = c.load_json(t)
            stale = ab.stale_rows(table, ctx["cfg"]["limits"]["apify_cost_row_max_age_days"])
            R.add("R-APIFY-CAP", not stale, "cost table rows are fresh" if not stale else f"refresh price rows older than 30 days: {stale}", severity="warn")
            wc, _ = ab.worst_case(table)
            R.add("R-APIFY-CAP", table.get("worst_case_usd") is not None and abs(float(table["worst_case_usd"]) - wc) < 0.005,
                  "stored worst-case total matches the rows" if table.get("worst_case_usd") is not None and abs(float(table["worst_case_usd"]) - wc) < 0.005 else "[VERIFY AT BUILD] stored worst_case_usd does not match the rows (run apify_budget.py worst-case)", severity="warn")


def check_flag_leaks(R, ctx):
    src, tl = ctx["src"], ctx["tl"]
    leaks = []
    for s in tl:
        blob = s["scene"]["line"] + " ".join(scene_texts(s["scene"]))
        if any(t in blob for t in FLAG_TOKENS):
            leaks.append(s["id"])
    for pid, p in list(src.get("prompts", {}).get("flux", {}).items()) + list(src.get("prompts", {}).get("wan", {}).items()):
        if any(t in p["text"] for t in FLAG_TOKENS):
            leaks.append(pid)
    R.add("R-FLAGS", not leaks, "no open flags inside LINEs, on-screen text, or prompts" if not leaks else f"flag tokens in script text or prompts: {leaks}")
    if ctx["stage"] == "post":
        out, slug = ctx["out"], ctx["slug"]
        bad = []
        for suf in ("narration.txt", "pronunciation-notes.txt", "scene-manifest.json", "generation-prompts.md"):
            p = out / f"{slug}-{suf}"
            if p.exists() and any(t in p.read_text(encoding="utf-8") for t in FLAG_TOKENS):
                bad.append(suf)
        R.add("R-FLAGS", not bad, "open flags stay out of narration, notes, manifest, and prompt files" if not bad else f"flag tokens found in {bad}")


def check_facts(R, ctx):
    """The teasers and packaging skills read LOCKED_FACTS, so every intake field must be filled before the gate."""
    src, cfg = ctx["src"], ctx["cfg"]
    base = dict(src.get("locked_facts", {}))
    if src["video"].get("segments"):
        base.setdefault("AUDIENCE SEGMENTS", "; ".join(src["video"]["segments"]))
    missing = [k for k in cfg.get("intake_required_fields", []) if not str(base.get(k, "")).strip() or "TBD" in str(base.get(k, ""))]
    R.add("R-FACTS", not missing, "all intake fields for LOCKED_FACTS are filled" if not missing else f"fill these intake fields in locked_facts before the gate: {missing}")
    segs = src["video"].get("segments", [])
    R.add("R-FACTS", len(segs) == 3, f"{len(segs)} audience segments (the teasers need exactly 3)", severity="standard")
    rat = str(base.get("THIRD-PARTY RATINGS A / B", ""))
    ok = bool(rat) and ("http" in rat or re.search(r"\b(G2|Capterra|Trustpilot|TrustRadius|Product Hunt|Gartner)\b", rat))
    R.add("R-FACTS", ok, "ratings name their source" if ok else "THIRD-PARTY RATINGS must name the review site or URL for each rating", severity="standard")


def check_packaging_files(R, ctx):
    if ctx["stage"] != "post":
        return
    out, slug, src, cfg = ctx["out"], ctx["slug"], ctx["src"], ctx["cfg"]
    missing = []
    for suf in ("script.md", "narration.txt", "pronunciation-notes.txt", "scene-manifest.json", "generation-prompts.md",
                "asset-checklist.md", "upload-checklist.md", "locked-facts.md"):
        if not (out / f"{slug}-{suf}").exists():
            missing.append(suf)
    R.add("EXPORTS", not missing, "all export files present" if not missing else f"missing exports: {missing}")
    sp = out / f"{slug}-script.md"
    if sp.exists():
        txt = sp.read_text(encoding="utf-8").splitlines()
        disc = c.disclosure_string(src, cfg)
        try:
            i = next(n for n, l in enumerate(txt) if l.strip() == "**Description**")
            first = next(l for l in txt[i + 1:] if l.strip())
            R.add("R-DISC", first.strip() == disc, "description's first line is the disclosure string" if first.strip() == disc else "description first line is not the exact disclosure string")
        except StopIteration:
            R.add("R-DISC", False, "description block not found in the script file")


CHECKS = [check_structure, check_disclosure, check_nospoken, check_length, check_lines, check_voice, check_rhythm,
          check_open_close, check_secret, check_proof, check_narration, check_shots, check_inserts, check_compare, check_genlimit,
          check_nofake, check_stills, check_avatar, check_aiflags, check_spec, check_cta, check_ghl_first,
          check_tier, check_vary, check_apify, check_flag_leaks, check_facts, check_packaging_files]


def run(src, cfg, out, workspace, timing, stage):
    tl = c.build_timeline(src, cfg, timing)
    flags = c.compute_ai_flags(src, tl)
    log = []
    if workspace and (Path(workspace) / "variation-log.json").exists():
        data = c.load_json(Path(workspace) / "variation-log.json")
        log = data if isinstance(data, list) else data.get("entries", [])
    ctx = {"src": src, "cfg": cfg, "tl": tl, "flags": flags, "out": Path(out), "slug": c.video_slug(src),
           "stage": stage, "workspace": workspace, "log": log}
    R = Report()
    for fn in CHECKS:
        try:
            fn(R, ctx)
        except Exception as e:  # a crashing check is a failing check, never a silent pass
            R.add("LINT-ERROR", False, f"{fn.__name__} crashed: {type(e).__name__}: {e}", severity="critical")
    return R, tl


def render(R, tl, stage):
    crit, std, warn = R.failures("critical"), R.failures("standard"), R.warnings()
    passed = len([r for r in R.rows if r["ok"]])
    L = [f"LINT REPORT ({stage} stage)",
         f"runtime {c.mmss(tl[-1]['end'])}, words {sum(s['words'] for s in tl)}, scenes {len(tl)}",
         f"{passed} checks passed, {len(crit)} critical failures, {len(std)} standard failures, {len(warn)} warnings", ""]
    if crit:
        L.append("CRITICAL FAILURES (block delivery)")
        L += [f"- [{r['rule']}] {r['detail']}" for r in crit]
        L.append("")
    if std:
        L.append("STANDARD FAILURES (fix before the gate)")
        L += [f"- [{r['rule']}] {r['detail']}" for r in std]
        L.append("")
    if warn:
        L.append("WARNINGS")
        L += [f"- [{r['rule']}] {r['detail']}" for r in warn]
        L.append("")
    L.append("PASSED")
    L += [f"- [{r['rule']}] {r['detail']}" for r in R.rows if r["ok"]]
    status = "PASS" if not crit and not std else ("FAIL (critical)" if crit else "FAIL (standard)")
    return status, "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--timing")
    ap.add_argument("--stage", choices=["pre", "post"], default="pre")
    a = ap.parse_args()
    cfg = c.load_config(a.workspace)
    src = c.load_json(a.source)
    timing = c.load_json(a.timing) if a.timing else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    R, tl = run(src, cfg, out, a.workspace, timing, a.stage)
    status, text = render(R, tl, a.stage)
    (out / "lint-report.txt").write_text(f"STATUS: {status}\n" + text, encoding="utf-8")
    if a.stage == "post":
        lf = out / f"{c.video_slug(src)}-locked-facts.md"
        if lf.exists():
            t = lf.read_text(encoding="utf-8")
            t = re.sub(r"^LINT RESULT:.*$", f"LINT RESULT: {status}", t, flags=re.M)
            lf.write_text(t, encoding="utf-8")
    print(f"STATUS: {status}\n" + text.split("PASSED")[0])
    if R.failures("critical"):
        return 1
    if R.failures("standard"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
