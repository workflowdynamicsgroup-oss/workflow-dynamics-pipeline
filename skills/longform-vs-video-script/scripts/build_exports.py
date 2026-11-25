#!/usr/bin/env python3
"""Build every export from the single source file.

Usage:
  build_exports.py SOURCE.json --out DIR [--workspace DIR] [--timing TIMING.json]
                   [--gate] [--append-variation-log]

--gate   writes only gate-preview.md (Phase 6). No final exports.
Without it, writes the full Phase 7 export set. The script is deterministic and
never hand-copies script text: narration, manifest, prompts, checklists and
LOCKED_FACTS are all rendered from the source file.
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

INSTALL_KEYS = {"RUNPOD TIME"}

LOCKED_KEYS = [
    "PRODUCT A", "PRODUCT B", "VS PAGE URL / ANCHORS", "PRIMARY KEYWORD", "SECONDARY KEYWORDS",
    "KEYWORD EVIDENCE", "SERIES TAG", "RENDER COMPOSITION", "AUTHORITY TIER A / B",
    "TESTED COMPONENTS A / B", "BADGE A / B", "DISCLOSURE TYPE", "DISCLOSURE TEXT",
    "YT PAID-PROMO TOGGLE", "AI FLAGS", "AUDIENCE SEGMENTS", "CORE USE CASE",
    "PRICING A / B (USD, verified [date], source URLs)", "DISCOUNT / OFFER", "FEATURE COMPARISON",
    "TCO A / B", "HELD REVEAL NUMBER", "THIRD-PARTY RATINGS A / B", "WHO SHOULD PICK A / B",
    "LOCKED OBJECTION", "RISK-REVERSAL A / B", "SWITCHING COST NOTE", "PAIN-POINT MAP",
    "COMPETITOR BRIEF", "PATTERNS TO AVOID", "TRANSCRIPT BRIEF", "SKIPS CONFIRMED", "APIFY SPEND",
    "RUNPOD TIME", "VARIATION LOG", "LINT RESULT", "TONE", "WPM USED", "FINAL RUNTIME / WORD COUNT",
    "AVATAR", "CAPTURES AND STILLS USED", "GEN-VIDEO USED", "CHAPTERS", "HOOK TYPE USED / HOOK LINE",
    "PRIOR HOOK LINES", "OPENER DEVICE", "END SCREEN START",
    "PROVISIONAL TITLES / DESCRIPTION / TAGS", "CALCULATOR URL", "EXISTING LINKABLE VIDEOS",
    "VERIFY FLAGS OPEN",
]


# ------------------------------------------------------------------ helpers
def products(src):
    v = src["video"]
    return {"a": v["product_a"], "b": v["product_b"]}


def pname(src, key):
    ps = products(src)
    if str(key).lower() == "ab":   # both products side by side, product A on the left
        return f"{ps.get('a', 'a')} and {ps.get('b', 'b')}"
    return ps.get(str(key).lower(), str(key))


TAG_KIND = {"GEN-VIDEO": "wan", "GEN-STILL": "still", "B-ROLL": "broll", "STAT": "stat",
            "ASSET-SHOT": "screen", "ASSET-CLIP": "clip", "ASSET-BRAND": "picture"}


def tag_of(shot):
    return c.shot_tag(shot["src"])


def chapters(tl):
    out = []
    for s in tl:
        ch = s["scene"].get("chapter")
        if ch:
            out.append((s["start"], ch))
    return out


def avatar_seconds(tl):
    return sum(s["dur"] for s in tl if s["scene"].get("avatar_block"))


def insert_counts(tl):
    counts = {"ASSET-SHOT": {"a": 0, "b": 0}, "ASSET-CLIP": {"a": 0, "b": 0}, "GEN-STILL": 0, "STAT": 0, "B-ROLL": 0}
    for s in tl:
        for sh in s["shots"]:
            tag = tag_of(sh)
            if tag in ("ASSET-SHOT", "ASSET-CLIP"):
                pr = str(sh["src"].get("product", "a")).lower()
                for q in (["a", "b"] if pr == "ab" else [pr]):
                    counts[tag][q] += 1
            elif tag in ("GEN-STILL", "STAT", "B-ROLL"):
                counts[tag] += 1
    total = sum(counts["ASSET-SHOT"].values()) + sum(counts["ASSET-CLIP"].values()) + counts["GEN-STILL"]
    return counts, total


def gen_used(tl):
    used = []
    for s in tl:
        for sh in s["shots"]:
            g = c.gen_video_of(sh["src"])
            if g:
                used.append((sh["id"], g["role"], s["scene"]["name"]))
    return used


def load_variation_log(workspace):
    if workspace:
        p = Path(workspace) / "variation-log.json"
        if p.exists():
            data = c.load_json(p)
            return data if isinstance(data, list) else data.get("entries", [])
    return []


def flag_lines(src, cfg):
    lines = []
    for f in src["video"].get("verify_flags", []):
        lines.append(f"[{f['tag']}] {f['item']}")
    unset = []
    if not cfg["wan"].get("confirmed"):
        unset.append("Wan 2.2 output size and fps unconfirmed on a test clip (assumed 1280x704 at 24fps, conformed to 25fps)")
    if not cfg["defaults"].get("wpm_measured") and not src["video"].get("wpm"):
        unset.append(f"Words per minute is the assumed {cfg['defaults']['wpm']}, not measured (Chatterbox measured about {cfg['defaults'].get('wpm_chatterbox', 182)} on 2026-11-18)")
    for p, entry in cfg.get("pronunciations", {}).items():
        if p in (src["video"]["product_a"], src["video"]["product_b"]) and not entry.get("verified"):
            unset.append(f"Pronunciation of {p} not yet tested in Chatterbox")
    unset.append("Platform safe zones for Shorts, TikTok, Reels and LinkedIn not yet checked against current platform docs")
    for u in unset:
        lines.append(f"[TBD AT INSTALL] {u}")
    return lines


# ----------------------------------------------------------------- exporters
def shot_label(src, sh):
    raw = sh["src"]
    tag = tag_of(sh)
    prompts = src.get("prompts", {})
    if tag == "B-ROLL":
        return raw.get("text", "")
    if tag == "GEN-VIDEO":
        return f"Wan clip, role {raw.get('role')}, prompt {raw.get('prompt_id')}"
    if tag == "GEN-STILL":
        return f"FLUX still, prompt {raw.get('prompt_id')}"
    if tag == "STAT":
        return "stat card"
    if tag in ("ASSET-SHOT", "ASSET-CLIP"):
        return f"{pname(src, raw.get('product', 'a'))}: {raw.get('detail', '')}"
    if tag == "ASSET-BRAND":
        return f"{pname(src, raw.get('product', 'a'))} logo from the brand asset set"
    return ""


def build_manifest(src, cfg, tl, flags, slug, timing_source):
    runtime = tl[-1]["end"]
    words = sum(s["words"] for s in tl)
    clean_flags = {k: v for k, v in flags.items() if not k.startswith("_")}
    narr_path = f"{slug}-narration.wav"
    shots = []
    for s in tl:
        sc = s["scene"]
        cta = sc.get("cta_button")
        cta_start = cta_end = None
        if cta:
            cta_start = c.abs_text_start(cta, s["start"], s["dur"])
            cta_end = cta_start + float(cta.get("dur_s", cfg["cta"]["duration_s"]))
        for sh in s["shots"]:
            raw = sh["src"]
            tag = tag_of(sh)
            texts = []
            for e in sc.get("on_screen_text", []):
                a = c.abs_text_start(e, s["start"], s["dur"])
                b = a + float(e.get("dur_s", 3))
                if a < sh["end"] and b > sh["start"]:
                    texts.append({"text": e["text"], "start": round(a, 2), "end": round(b, 2)})
            entry = {
                "scene": s["id"], "shot": sh["id"],
                "start": int(sh["start"]), "end": int(sh["end"]), "duration_s": int(sh["dur"]),
                "tag": tag, "kind": TAG_KIND.get(tag, "plain"),
                "avatar": bool(raw.get("avatar")),
                "asset_path": "",
                "narration_audio_path": narr_path,
                "on_screen_text": texts,
                "cta_button": bool(cta and cta_start < sh["end"] and cta_end > sh["start"]),
                "aspect": "16:9", "fps": 25,
            }
            if tag == "GEN-STILL":
                entry["flux_prompt_id"] = raw.get("prompt_id")
            if tag == "GEN-VIDEO":
                entry["wan_prompt_id"] = raw.get("prompt_id")
                entry["wan_role"] = raw.get("role")
            if tag == "B-ROLL":
                entry["broll_brief"] = raw.get("text", "")
                entry["broll_search"] = raw.get("search", "")
            if tag == "STAT":
                entry["stat"] = raw.get("stat", {})
            if tag in ("ASSET-SHOT", "ASSET-CLIP", "ASSET-BRAND"):
                entry["product"] = pname(src, raw.get("product", "a"))
                entry["asset_detail"] = raw.get("detail", "")
            shots.append(entry)
    blocks = []
    for n in (1, 2, 3):
        ss = [s for s in tl if s["scene"].get("avatar_block") == n]
        if ss:
            blocks.append({"block": n, "start": int(ss[0]["start"]), "end": int(ss[-1]["end"])})
    return {
        "video": f"{src['video']['product_a']} vs {src['video']['product_b']}",
        "runtime_target": c.mmss(runtime),
        "word_count": words,
        "ai_flags": clean_flags,
        "render_composition": src["video"].get("render_composition", "Long16x9"),
        "frame": {"width": 1920, "height": 1080, "fps": 25, "aspect": "16:9", "codec": "H.264 MP4"},
        "timing_source": timing_source,
        "avatar_blocks": blocks,
        "overlays": [{
            "type": "corner_tag", "text": cfg["corner_tag"], "from_s": 0,
            "to_s": int(round(runtime)), "opacity": 0.35,
        }],
        "shots": shots,
    }


def write_script_md(src, cfg, tl, flags, slug, out):
    v = src["video"]
    disc = c.disclosure_string(src, cfg)
    pk = v.get("packaging", {})
    chs = chapters(tl)
    L = []
    L.append(f"# {v['product_a']} vs {v['product_b']}: full script\n")
    L.append("## PROVISIONAL PACKAGING [FINAL IN PACKAGING]\n")
    L.append("**Title options**")
    for i, t in enumerate(pk.get("titles", []), 1):
        L.append(f"{i}. {t}")
    L.append("\n**Description**\n")
    L.append(disc)
    if pk.get("description_body"):
        L.append("\n" + pk["description_body"])
    if chs:
        L.append("\nChapters:")
        for t, name in chs:
            L.append(f"{c.mmss(t)} {name}")
    L.append("\n**Tags**: " + ", ".join(pk.get("tags", [])))
    open_flags = flag_lines(src, cfg)
    L.append("\n## OPEN FLAGS\n")
    L.extend(f"- {f}" for f in open_flags) if open_flags else L.append("- none")
    allowed = sorted({sec for secs in cfg["gen_role_sections"].values() for sec in secs})
    L.append("\n## DO NOT USE THE VIDEO GENERATOR\n")
    L.append("Wan clips only in scenes whose section is one of: " + ", ".join(allowed) + ", up to the cap, in the fill order. "
             "Never on a product, a price, a screen, a face, a verdict or the held reveal itself. No Wan clip in any other scene.")
    L.append("\n## AVATAR BLOCKS\n")
    for n in (1, 2, 3):
        ss = [s for s in tl if s["scene"].get("avatar_block") == n]
        if ss:
            L.append(f"AVATAR BLOCK {n}: {c.mmss(ss[0]['start'])}-{c.mmss(ss[-1]['end'])} (scenes {ss[0]['id']}-{ss[-1]['id']}). The avatar shows only on shots marked AVATAR: on.")
    L.append("\n## SCRIPT\n")
    for s in tl:
        sc = s["scene"]
        L.append(f"SCENE {s['id']} {sc['name']} | {c.mmss(s['start'])}-{c.mmss(s['end'])}")
        L.append(f'LINE: "{sc["line"]}"')
        for sh in s["shots"]:
            raw = sh["src"]
            tag = tag_of(sh)
            L.append(f"[{c.mmss(sh['start'])}-{c.mmss(sh['end'])}] Shot {sh['id']} [{tag}] ({shot_label(src, sh)})")
            if tag == "STAT":
                st = raw.get("stat", {})
                L.append(f"Value: {st.get('value', '')}")
                L.append(f"Label: {st.get('label', '')}")
                L.append(f"Source: {st.get('source', '')}")
            L.append(f"AVATAR: {'on' if raw.get('avatar') else 'off'}")
            if raw.get("finish"):
                L.append(f"FINISH: {raw['finish']}")
        for e in sc.get("on_screen_text", []):
            a = c.abs_text_start(e, s["start"], s["dur"])
            L.append(f"ON-SCREEN TEXT: {e['text']} @ {c.mmss(a)} for {e.get('dur_s', 3)}s")
        if sc.get("cta_button"):
            cta = sc["cta_button"]
            a = c.abs_text_start(cta, s["start"], s["dur"])
            L.append(f"CTA BUTTON: {cta['wording']} @ {c.mmss(a)} for {cta.get('dur_s', cfg['cta']['duration_s'])}s")
        if sc.get("retention_beat"):
            L.append("RETENTION BEAT: yes")
        if sc.get("addresses_objection"):
            L.append(f"ADDRESSES OBJECTION: {sc['addresses_objection']}")
        if sc.get("end_screen_start"):
            L.append(f"END SCREEN START: {c.mmss(s['start'])}")
        L.append("")
    (out / f"{slug}-script.md").write_text("\n".join(L), encoding="utf-8")


def write_narration(src, cfg, tl, slug, out):
    lines = [s["narration"] for s in tl]
    (out / f"{slug}-narration.txt").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    notes, seen = [], set()
    for s in tl:
        for name in s["pron"]:
            if name in seen:
                continue
            seen.add(name)
            p = cfg["pronunciations"][name]
            status = "tested" if p.get("verified") else "not yet tested in the 60-second Chatterbox pass"
            notes.append(f"{name} -> written as \"{p['spell']}\". {p.get('note', '')} ({status})".strip())
    if not notes:
        notes = ["No product names flagged for this script."]
    (out / f"{slug}-pronunciation-notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")


def write_prompts(src, cfg, tl, slug, out):
    """One file: FLUX stills first, then Wan clips, one entry per shot id."""
    prompts = src.get("prompts", {})
    flux = prompts.get("flux", {})
    wan = prompts.get("wan", {})
    L = [f"# Generation prompts: {src['video']['product_a']} vs {src['video']['product_b']}\n",
         "One entry per generated shot id. The pipeline reads this file for every [GEN-STILL] and [GEN-VIDEO] shot.\n",
         "## FLUX.1-schnell stills (1024x1024, shown 9-16 seconds with a slow push)\n"]
    n_flux = 0
    for s in tl:
        for sh in s["shots"]:
            if tag_of(sh) != "GEN-STILL":
                continue
            pid = sh["src"].get("prompt_id")
            p = flux.get(pid, {"text": "[MISSING PROMPT]"})
            n_flux += 1
            L.append(f"### {sh['id']} | FLUX.1-schnell | {int(sh['dur'])}s | 16:9 | prompt {pid}")
            text = p["text"].rstrip()
            L.append(text + " " + cfg["flux_attach"] + ".")
            L.append("")
    if not n_flux:
        L.append("No generated stills for this video.\n")
    L.append("## Wan 2.2 TI2V-5B clips (1280x704 at 24 fps, 5 seconds, conformed to 25 fps in the render)\n")
    n_wan = 0
    for s in tl:
        for sh in s["shots"]:
            g = c.gen_video_of(sh["src"])
            if not g:
                continue
            p = wan.get(g["prompt_id"], {"text": "[MISSING PROMPT]"})
            n_wan += 1
            L.append(f"### {sh['id']} | {s['scene']['name']} | {int(sh['dur'])}s | role {g['role']} | prompt {g['prompt_id']}")
            L.append(p["text"].strip())
            L.append("Review each clip for motion judder after conforming. Reject any clip that shows a face, text or product UI.")
            L.append("")
    if not n_wan:
        L.append("No generated clips for this video (cap is 0).\n")
    (out / f"{slug}-generation-prompts.md").write_text("\n".join(L), encoding="utf-8")


def write_assets(src, cfg, tl, slug, out):
    rows = []
    for s in tl:
        for sh in s["shots"]:
            if tag_of(sh) in ("ASSET-SHOT", "ASSET-CLIP", "ASSET-BRAND"):
                rows.append((sh, s))
    cap = src["video"].get("overlay_cap_override") or cfg["limits"]["overlay_cap"]
    counts, total = insert_counts(tl)
    L = [f"# Asset checklist: {src['video']['product_a']} vs {src['video']['product_b']}\n",
         "Real assets only, in timestamp order. Each is imported as supplied. There is no fallback: a missing asset stops the render and is reported as [NEED ASSET]. "
         "Put the files in R2 inputs/[slug]/ or attach them.\n"]
    for sh, s in rows:
        raw = sh["src"]
        tag = tag_of(sh)
        if tag == "ASSET-BRAND":
            L.append(f"- {c.mmss(sh['start'])} | {sh['id']} | ASSET-BRAND | {pname(src, raw.get('product', 'a'))} | logo from the brand asset set | {int(sh['dur'])}s on screen")
            continue
        paid = "needs a paid account" if raw.get("needs_paid_access") else "obtainable without a paid account"
        L.append(f"- {c.mmss(sh['start'])} | {sh['id']} | {tag} | {pname(src, raw.get('product', 'a'))} | {raw.get('detail', '')} | "
                 f"{int(sh['dur'])}s on screen | blur: {raw.get('blur', 'account emails, client names, API keys, billing details')} | {paid}")
    if not rows:
        L.append("- No real assets planned.")
    sa, sb = counts["ASSET-SHOT"]["a"], counts["ASSET-SHOT"]["b"]
    ra, rb = counts["ASSET-CLIP"]["a"], counts["ASSET-CLIP"]["b"]
    L.append("\n## Running totals")
    L.append(f"- Captures and stills: {total} of {cap} (ASSET-SHOT {sa + sb}, ASSET-CLIP {ra + rb}, GEN-STILL {counts['GEN-STILL']})")
    L.append(f"- {pname(src, 'a')}: {sa} screenshots, {ra} screen recordings")
    L.append(f"- {pname(src, 'b')}: {sb} screenshots, {rb} screen recordings")
    L.append("\n## Open verify flags")
    for f in flag_lines(src, cfg):
        L.append(f"- {f}")
    L.append("\n## Link placeholders")
    for p in src["video"].get("link_placeholders", ["none"]):
        L.append(f"- {p}")
    (out / f"{slug}-asset-checklist.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_upload(src, cfg, tl, flags, slug, out):
    disc = c.disclosure_string(src, cfg)
    chs = chapters(tl)
    es = next((s for s in tl if s["scene"].get("end_screen_start")), None)
    L = [f"# Upload checklist: {src['video']['product_a']} vs {src['video']['product_b']}\n", "## YouTube\n"]
    L.append("- Title: choose one of the three options in the script file.")
    L.append(f"- Description, first line exactly: {disc}")
    L.append(f"- Paid-promotion toggle: {cfg['platform']['paid_promo_toggle']}. "
             "The on-screen disclosure does not replace it. [VERIFY AT PUBLISH] confirm the requirement on the current platform policy page.")
    L.append("- AI flags (copied from the scene manifest, never set here):")
    L.append(f"  - synthetic_voice: {str(flags['synthetic_voice']).lower()}")
    shots = ", ".join(flags["_realistic_ai_visuals_shots"]) or "none"
    L.append(f"  - realistic_ai_visuals: {str(flags['realistic_ai_visuals']).lower()} (shots: {shots})")
    L.append(f"  - ai_person_visible: {str(flags['ai_person_visible']).lower()}")
    L.append("- Platform setting for each true flag: see references/platform-flags.md. "
             "[VERIFY AT PUBLISH] wording on the current YouTube altered-or-synthetic-content disclosure.")
    if flags["ai_person_visible"]:
        L.append("- AI-generated profile or avatar setting: turn on if the platform asks. [VERIFY AT PUBLISH]")
    L.append("- Chatterbox note: the voice carries a watermark (accepted).")
    if es:
        L.append(f"- End screen starts at {c.mmss(es['start'])}. Place YouTube elements in the left and right thirds; "
                 "keep the center third for the focal point, button, and disclosure.")
    L.append("- Chapters:")
    for t, name in chs:
        L.append(f"  - {c.mmss(t)} {name}")
    (out / f"{slug}-upload-checklist.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def locked_facts_values(src, cfg, tl, flags, workspace, lint_result="pending"):
    v = src["video"]
    base = dict(src.get("locked_facts", {}))
    log = load_variation_log(workspace)
    runtime = tl[-1]["end"]
    words = sum(s["words"] for s in tl)
    wpm = v.get("wpm") or cfg["defaults"]["wpm"]
    counts, total = insert_counts(tl)
    cap = v.get("overlay_cap_override") or cfg["limits"]["overlay_cap"]
    gens = gen_used(tl)
    gen_cap = v.get("gen_video_cap", cfg["defaults"]["gen_video_cap"])
    chs = chapters(tl)
    es = next((s for s in tl if s["scene"].get("end_screen_start")), None)
    tiers = v.get("tiers", {})
    ta, tb = tiers.get("a", {}), tiers.get("b", {})
    var = v.get("variation", {})
    hook_line = tl[0]["scene"]["line"] if tl else ""
    avatar = v.get("avatar", {}).get("mode", "none")
    blocks = []
    for n in (1, 2, 3):
        ss = [x for x in tl if x["scene"].get("avatar_block") == n]
        if ss:
            blocks.append(f"block {n} {c.mmss(ss[0]['start'])}-{c.mmss(ss[-1]['end'])}")
    shots_line = ", ".join(flags["_realistic_ai_visuals_shots"]) or "none"
    pk = v.get("packaging", {})
    computed = {
        "PRODUCT A": f"{v['product_a']} {v.get('link_a', '')}".strip(),
        "PRODUCT B": f"{v['product_b']} {v.get('link_b', '')}".strip(),
        "VS PAGE URL / ANCHORS": v.get("vs_page_url", "TBD"),
        "PRIMARY KEYWORD": f"{v.get('primary_keyword', '')} ({v.get('primary_keyword_status', 'assumed')})",
        "SECONDARY KEYWORDS": ", ".join(v.get("secondary_keywords", [])),
        "RENDER COMPOSITION": v.get("render_composition", "LongFormVS"),
        "AUTHORITY TIER A / B": f"{ta.get('tier', '?')} / {tb.get('tier', '?')}",
        "TESTED COMPONENTS A / B": f"{'; '.join(ta.get('tested_components', [])) or 'N/A'} / {'; '.join(tb.get('tested_components', [])) or 'N/A'}",
        "BADGE A / B": f"{cfg['badges'].get(ta.get('tier'), '?')} / {cfg['badges'].get(tb.get('tier'), '?')}",
        "DISCLOSURE TYPE": v.get("disclosure_type", cfg["defaults"]["disclosure_type"]),
        "DISCLOSURE TEXT": c.disclosure_string(src, cfg),
        "YT PAID-PROMO TOGGLE": cfg["platform"]["paid_promo_toggle"],
        "AI FLAGS": (f"synthetic_voice: {str(flags['synthetic_voice']).lower()}; "
                     f"realistic_ai_visuals: {str(flags['realistic_ai_visuals']).lower()} (shots: {shots_line}); "
                     f"ai_person_visible: {str(flags['ai_person_visible']).lower()} "
                     f"({'generated avatar' if avatar == 'generated' else ('footage' if avatar == 'footage' else 'no avatar')})"),
        "VARIATION LOG": (f"category order {var.get('category_order')}; micro-authority {var.get('micro_authority_device')}; "
                          f"hook device {var.get('hook_device')}; opener {var.get('opener_device')}; visual motif {var.get('visual_motif')}"),
        "LINT RESULT": lint_result,
        "TONE": v.get("tone", cfg["defaults"]["tone"]),
        "WPM USED": str(wpm),
        "FINAL RUNTIME / WORD COUNT": f"{c.mmss(runtime)} / {words} words",
        "AVATAR": ("not used" if avatar == "none" else
                   f"{avatar}; {', '.join(blocks)}; total {c.mmss(avatar_seconds(tl))}"),
        "CAPTURES AND STILLS USED": (f"real captures {sum(counts['ASSET-SHOT'].values()) + sum(counts['ASSET-CLIP'].values())} of {cap}; ASSET-SHOT {sum(counts['ASSET-SHOT'].values())} "
                                     f"({v['product_a']} {counts['ASSET-SHOT']['a']}, {v['product_b']} {counts['ASSET-SHOT']['b']}); "
                                     f"ASSET-CLIP {sum(counts['ASSET-CLIP'].values())}; GEN-STILL {counts['GEN-STILL']} of {cfg['limits']['still_cap']}; STAT {counts['STAT']}"),
        "GEN-VIDEO USED": f"{len(gens)} of cap {gen_cap}: " + ", ".join(f"{r} ({sid})" for sid, r, _ in gens),
        "CHAPTERS": "; ".join(f"{c.mmss(t)} {n}" for t, n in chs),
        "HOOK TYPE USED / HOOK LINE": f"{var.get('hook_type', '')} / {hook_line}",
        "PRIOR HOOK LINES": " | ".join(e.get("hook_line", "") for e in log[-5:]) or "none on file",
        "OPENER DEVICE": var.get("opener_device", ""),
        "END SCREEN START": c.mmss(es["start"]) if es else "not set",
        "PROVISIONAL TITLES / DESCRIPTION / TAGS": ("[FINAL IN PACKAGING] titles: " + " | ".join(pk.get("titles", []))
                                                     + "; tags: " + ", ".join(pk.get("tags", []))),
        "VERIFY FLAGS OPEN": "; ".join(flag_lines(src, cfg)) or "none",
    }
    if v.get("segments"):
        computed["AUDIENCE SEGMENTS"] = "; ".join(f"{i}) {name}" for i, name in enumerate(v["segments"], 1))
    held = v.get("held_reveal")
    if held:
        computed["HELD REVEAL NUMBER"] = f"{held.get('number')}: flips {held.get('flips')} for {held.get('segment')}"
    computed.update({k: val for k, val in base.items() if k not in computed or k in ("KEYWORD EVIDENCE",)})
    for k, val in base.items():
        computed.setdefault(k, val)
    return computed


def write_locked_facts(src, cfg, tl, flags, workspace, slug, out, lint_result="pending"):
    vals = locked_facts_values(src, cfg, tl, flags, workspace, lint_result)
    L = ["---LOCKED_FACTS---"]
    alias = {"PRICING A / B (USD, verified [date], source URLs)": "PRICING A / B"}
    for k in LOCKED_KEYS:
        if not vals.get(k) and vals.get(alias.get(k, "")):
            vals[k] = vals[alias[k]]
        L.append(f"{k}: {vals.get(k) or ('TBD AT INSTALL (stack not running yet)' if k in INSTALL_KEYS else 'TBD (needs input from the owner, ask at intake)')}")
    L.append("---END_LOCKED_FACTS---")
    (out / f"{slug}-locked-facts.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_gate_preview(src, cfg, tl, flags, workspace, out, lint_report=None):
    v = src["video"]
    tiers = v.get("tiers", {})
    ta, tb = tiers.get("a", {}), tiers.get("b", {})
    runtime = tl[-1]["end"]
    words = sum(s["words"] for s in tl)
    wpm = float(v.get("wpm") or cfg["defaults"]["wpm"])
    longest = max((sh for s in tl for sh in s["shots"]), key=lambda x: x["dur"])
    drifts = [abs(s["start"] - s["narr_start"]) for s in tl]
    counts, total = insert_counts(tl)
    cap = v.get("overlay_cap_override") or cfg["limits"]["overlay_cap"]
    gens = gen_used(tl)
    gen_cap = v.get("gen_video_cap", cfg["defaults"]["gen_video_cap"])
    ho = v.get("hook_options", {})
    L = ["# GATE PREVIEW\n"]
    L.append(f"**Badges**: {pname(src, 'a')}: {cfg['badges'].get(ta.get('tier'))}. {pname(src, 'b')}: {cfg['badges'].get(tb.get('tier'))}.")
    if ta.get("tier") != tb.get("tier"):
        L.append("The two tiers differ. The script uses first-person language only where the badge allows it.")
    L.append(f"**Hook A**: {ho.get('A', {}).get('line', tl[0]['scene']['line'])} ({ho.get('A', {}).get('type', '')})")
    L.append(f"**Hook B**: {' / '.join(ho.get('B', {}).get('scene_lines', []))} ({ho.get('B', {}).get('type', '')})\n")
    L.append("## Script (Hook A)")
    for s in tl:
        tags = []
        for sh in s["shots"]:
            tags.append(tag_of(sh))
        if not tags and s.get("cover"):
            tags = ["under the long shot above"]
        L.append(f"- {c.mmss(s['start'])} {s['scene']['line']}  _[{', '.join(tags)}]_")
    L.append("\n## Hook B drop-in (first two scenes)")
    for i, line in enumerate(ho.get("B", {}).get("scene_lines", [])[:2], 1):
        L.append(f"{i}. {line}")
    held = v.get("held_reveal", {})
    L.append("\n## Held reveal")
    L.append(f"{held.get('number', 'not set')}: flips {held.get('flips', '')} for {held.get('segment', '')}"
             + (" (fallback finding: no number flips a verdict)" if held.get("fallback") else ""))
    flags_list = [f for f in v.get("verify_flags", [])]
    not_in_table = [f for f in flags_list if not f.get("in_table")]
    L.append(f"\n## Open flags: {len(flags_list) + 0} total")
    for f in not_in_table:
        L.append(f"- [{f['tag']}] {f['item']}")
    cfg_flags = [f for f in flag_lines(src, cfg) if f.startswith("[TBD AT INSTALL]")]
    for f in cfg_flags:
        L.append(f"- {f}")
    corr = src.get("verification_corrections", [])
    L.append(f"Verification table corrections: {len(corr)}")
    for x in corr:
        L.append(f"- {x}")
    rs = src.get("research_summary", {})
    L.append("\n## Research findings")
    L.append(f"- Primary keyword: {v.get('primary_keyword')} ({v.get('primary_keyword_status', 'assumed')})")
    L.append(f"- Gap: {rs.get('gap', 'n/a')}")
    L.append(f"- Top unanswered objections: {'; '.join(rs.get('objections', [])) or 'n/a'}")
    L.append(f"- Script changes because of them: {rs.get('script_changes', 'n/a')}")
    if rs.get("skips_confirmed"):
        L.append(f"- Confirmed skips: {', '.join(rs['skips_confirmed'])}")
    spend = rs.get("apify_spend", {})
    L.append(f"- Apify spend: ${sum(spend.values()):.2f} of ${cfg['limits']['apify_cap_usd']:.2f} cap "
             f"({', '.join(f'{k} ${val:.2f}' for k, val in spend.items()) or 'no runs'}). {rs.get('cap_stopped', '')}".strip())
    L.append("\n## AI flags and toggle")
    L.append(f"synthetic_voice {str(flags['synthetic_voice']).lower()}, realistic_ai_visuals {str(flags['realistic_ai_visuals']).lower()}, "
             f"ai_person_visible {str(flags['ai_person_visible']).lower()}. Paid-promotion toggle: {cfg['platform']['paid_promo_toggle']}.")
    var = v.get("variation", {})
    L.append("\n## Variation log for this video")
    for k in ("category_order", "micro_authority_device", "hook_device", "hook_type", "opener_device", "visual_motif"):
        L.append(f"- {k}: {var.get(k)}")
    L.append("\n## Totals")
    L.append(f"- Words {words}, runtime {c.mmss(runtime)}, wpm {wpm:.0f}, longest shot {longest['id']} at {longest['dur']:.1f}s")
    L.append(f"- Lint: {lint_report or 'run lint.py --stage pre and paste the result'}")
    mc = src.get("manual_checks", {})
    L.append("- Manual checks: " + ("; ".join(f"{k}: {val}" for k, val in mc.items()) if mc else "not recorded"))
    L.append(f"- Captures and stills {total} of {cap}: ASSET-SHOT {sum(counts['ASSET-SHOT'].values())}, "
             f"ASSET-CLIP {sum(counts['ASSET-CLIP'].values())}, GEN-STILL {counts['GEN-STILL']}, STAT {counts['STAT']}, B-ROLL {counts['B-ROLL']}")
    needs_paid = []
    for s in tl:
        for sh in s["shots"]:
            if tag_of(sh) in ("ASSET-SHOT", "ASSET-CLIP") and sh["src"].get("needs_paid_access"):
                needs_paid.append(sh["id"])
    L.append(f"- Captures needing a paid account: {', '.join(needs_paid) or 'none'}")
    L.append(f"- GEN-VIDEO {len(gens)} of cap {gen_cap}")
    if v.get("avatar", {}).get("mode", "none") != "none":
        L.append(f"- Avatar minutes: {c.mmss(avatar_seconds(tl))}")
    if v.get("overlay_cap_override"):
        L.append(f"- Overlay cap raised to {v['overlay_cap_override']}: {v.get('overlay_override_reason', 'reason not recorded')}")
    L.append("\nHere's the full script preview with two hook options. Pick A or B, and tell me any changes to hooks, verdicts, or pacing before I build the files.")
    (out / "gate-preview.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def append_variation_log(src, workspace):
    p = Path(workspace) / "variation-log.json"
    data = c.load_json(p) if p.exists() else []
    if isinstance(data, dict):
        data = data.get("entries", [])
    v = src["video"]
    var = v.get("variation", {})
    entry = {
        "video": c.video_slug(src),
        "date": datetime.date.today().isoformat(),
        "category_order": var.get("category_order"),
        "micro_authority_device": var.get("micro_authority_device"),
        "hook_device": var.get("hook_device"),
        "hook_type": var.get("hook_type"),
        "opener_device": var.get("opener_device"),
        "visual_motif": var.get("visual_motif"),
        "hook_line": src["scenes"][0]["line"],
    }
    if any(e.get("video") == entry["video"] for e in data):
        data = [e for e in data if e.get("video") != entry["video"]]
    data.append(entry)
    c.save_json(p, data)
    return p


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--timing")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--lint-report")
    ap.add_argument("--append-variation-log", action="store_true")
    a = ap.parse_args()

    cfg = c.load_config(a.workspace)
    src = c.load_json(a.source)
    timing = c.load_json(a.timing) if a.timing else None
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tl = c.build_timeline(src, cfg, timing)
    flags = c.compute_ai_flags(src, tl)
    slug = c.video_slug(src)

    if a.gate:
        write_gate_preview(src, cfg, tl, flags, a.workspace, out, a.lint_report)
        print(f"gate preview written: {out / 'gate-preview.md'}")
        return 0

    timing_source = "whisper" if timing else "wpm_estimate"
    manifest = build_manifest(src, cfg, tl, flags, slug, timing_source)
    c.save_json(out / f"{slug}-scene-manifest.json", manifest)
    write_script_md(src, cfg, tl, flags, slug, out)
    write_narration(src, cfg, tl, slug, out)
    write_prompts(src, cfg, tl, slug, out)
    write_assets(src, cfg, tl, slug, out)
    write_upload(src, cfg, tl, flags, slug, out)
    lint_result = "pending (run lint.py --stage post)"
    write_locked_facts(src, cfg, tl, flags, a.workspace, slug, out, lint_result)
    if a.append_variation_log and a.workspace:
        append_variation_log(src, a.workspace)
    words = sum(s["words"] for s in tl)
    print(f"exports written to {out}: {slug}, {words} words, runtime {c.mmss(tl[-1]['end'])}, timing {timing_source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
