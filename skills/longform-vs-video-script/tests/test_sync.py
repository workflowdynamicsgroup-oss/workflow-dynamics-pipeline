#!/usr/bin/env python3
"""Drift check: the skill's text, config and lint must describe the same rules.

  python3 -I tests/test_sync.py          (exit 0 = no drift)

Fails when
  - a rule id named in SKILL.md or references/script-rules.md is neither enforced by lint.py nor marked as a manual review,
  - a `config.json` key named in backticks in SKILL.md or script-rules.md does not exist in config.json,
  - a rule that was removed (listed in RETIRED) comes back in any text, config or lint file,
  - SKILL.md restates a number that config.json owns (runtime, caps, windows) differently from config.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXTS = [ROOT / "SKILL.md", ROOT / "references" / "script-rules.md"]
ALL = TEXTS + [ROOT / "references" / n for n in ("phases-1-3.md", "phases-5-7.md", "source-schema.md")] + \
      [ROOT / "config.json", ROOT / "scripts" / "lint.py", ROOT / "scripts" / "common.py"]

# Rules retired on 2026-11-25. They must not reappear anywhere.
RETIRED = {
    "GoHighLevel first": r"GoHighLevel(?:'s)? (?:first|must be (?:Product )?A)|R-GHL-FIRST|is_ghl",
    "retention beat": r"retention_gap_s|R-RETENTION|\bretention_beat\b.{0,40}(?:every|gap|max)",
    "reveal-transition and bridge Wan clips": r"reveal_transition|\"bridge\"\s*:",
    "required shot finish": r"[Ee]ach shot has a finish",
    "forbidden visual word list": r"forbidden_visual_terms",
}
MANUAL = {"R-STAT", "R-HONESTY", "R-NOFAKE", "R-AIFLAG", "R-TIER", "R-VARY", "R-SECRET", "R-SKIP", "R-APIFY-CAP", "R-DISC", "R-AVATAR"}


def main():
    cfg = json.loads((ROOT / "config.json").read_text())
    keys = set()

    def walk(d):
        for k, v in d.items():
            keys.add(k)
            if isinstance(v, dict):
                walk(v)
    walk(cfg)
    lint_src = (ROOT / "scripts" / "lint.py").read_text()
    problems = []
    for t in TEXTS:
        txt = t.read_text()
        for rid in sorted(set(re.findall(r"\bR-[A-Z][A-Z-]+\b", txt))):
            if rid not in lint_src and rid not in MANUAL and rid != "R-VOICE":
                problems.append(f"{t.name}: rule {rid} is not enforced in lint.py and not listed as manual")
        for k in sorted(set(re.findall(r"`([a-z][a-z0-9_]+)`", txt))):
            if re.search(r"_(s|max|min|cap|share|words|uses|order|kinds|rows|cards|pct|sections|subjects|words|phrases)$", k) and k not in keys \
                    and k not in ("start_s", "at_s", "dur_s", "duration_s", "end_screen_start"):
                problems.append(f"{t.name}: `{k}` is not a key in config.json")
    for name, rx in RETIRED.items():
        for f in ALL:
            if f.name == "test_sync.py":
                continue
            m = re.search(rx, f.read_text())
            if m:
                problems.append(f"{f.name}: retired rule '{name}' is back: {m.group(0)[:60]!r}")
    lim = cfg["limits"]
    skill = (ROOT / "SKILL.md").read_text()
    for key in ("still_cap", "gen_video_cap_max", "compare_cards_min"):
        for m in re.finditer(rf"`{key}`\s*(?:=|is|of)\s*(\d+)", skill):
            if int(m.group(1)) != lim[key]:
                problems.append(f"SKILL.md states {key} = {m.group(1)} but config says {lim[key]}")
    if problems:
        print("DRIFT:")
        for p in problems:
            print("  -", p)
        return 1
    print("no drift between SKILL.md, script-rules.md, config.json and lint.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
