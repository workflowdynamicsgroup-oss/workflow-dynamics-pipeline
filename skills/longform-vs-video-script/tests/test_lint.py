#!/usr/bin/env python3
"""Negative tests: break the clean fixture one way at a time and assert lint catches it.

  python3 -I tests/test_lint.py          (exit 0 = every case behaved)
"""
import copy
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import common as c  # noqa: E402
import lint  # noqa: E402
import make_fixture  # noqa: E402

CFG = c.load_config()


def lint_src(src):
    with tempfile.TemporaryDirectory() as d:
        R, _ = lint.run(src, CFG, d, None, None, "pre")
    return R


def scene(src, name):
    return next(s for s in src["scenes"] if s["name"] == name)


def with_tag(src, tag, min_shots=1, section=None):
    """First scene whose own first shot has this tag (and at least min_shots shots)."""
    return next(s for s in src["scenes"] if s["shots"] and s["shots"][0]["tag"] == tag and len(s["shots"]) >= min_shots
                and (section is None or s["section"] == section))


def fails(R, rule=None):
    return [r for r in R.failures() if rule is None or r["rule"] == rule]


CASES = []


def case(rule, severity=None):
    def deco(fn):
        CASES.append((fn.__name__, rule, severity, fn))
        return fn
    return deco


@case("R-DISC")
def no_disclosure(src):
    disc = CFG["disclosure_strings"]["unsponsored"]
    for s in src["scenes"]:
        s["on_screen_text"] = [e for e in s["on_screen_text"] if e["text"] != disc]


@case("R-NOSPOKEN")
def spoken_tag(src):
    scene(src, "Recap")["line"] += " " + CFG["corner_tag"] + "."


@case("R-GENLIMIT", "critical")
def too_many_clips(src):
    sc = with_tag(src, "B-ROLL", section="problem")
    sc["shots"].append({"tag": "GEN-VIDEO", "role": "bridge", "prompt_id": "w9"})


@case("R-LENGTH")
def too_short(src):
    src["scenes"] = src["scenes"][:30]


@case("R-LINE")
def three_sentences(src):
    scene(src, "Problem 1")["line"] = "One thing. Two things. Three things happen here."


@case("R-VOICE")
def uncontracted(src):
    scene(src, "Problem 2")["line"] = "A wrong pick costs hours every week and you do not get them back."


@case("R-GHL-FIRST")
def ghl_second(src):
    a, b = src["video"]["product_a"], src["video"]["product_b"]
    src["video"]["product_a"], src["video"]["product_b"] = "Beta Funnels", "GoHighLevel"


@case("R-CTA")
def offer_without_link(src):
    scene(src, "Offer")["line"] = "Pick one today and get started."


@case("R-SECRET")
def reveal_number_early(src):
    scene(src, "Problem 2")["line"] = "A wrong pick costs about $214 a month, and that adds up."


@case("R-AVATAR")
def avatar_on_number(src):
    sc = with_tag(src, "STAT", section="held_reveal")
    sc["shots"][0]["avatar"] = True


@case("R-INSERT")
def screenshot_overload(src):
    for s in src["scenes"]:
        if s["section"] == "problem" and s["shots"] and s["shots"][0]["tag"] == "B-ROLL":
            s["shots"] = [{"tag": "ASSET-SHOT", "product": "a", "detail": "x"}]


@case("R-SHOTS", "critical")
def broll_over_share(src):
    for s in src["scenes"]:
        if s["shots"] and s["shots"][0]["tag"] in ("GEN-STILL", "STAT"):
            s["shots"][0].pop("span", None)
            s["shots"] = [{"tag": "B-ROLL", "text": "Means: the point of the scene. Picture: a calm blue light sweeping across a bright open field.", "search": "light"}]


@case("R-SHOTS")
def shot_too_long(src):
    # B-roll runs up to 8 s, so cut every multi-shot B-roll scene down to one shot: the long ones then break the cap
    for sc in src["scenes"]:
        if len(sc["shots"]) >= 2 and all(sh["tag"] == "B-ROLL" for sh in sc["shots"]):
            sc["shots"] = sc["shots"][:1]


@case("R-SHOTS")
def stat_without_source(src):
    sc = with_tag(src, "STAT")
    sc["shots"][0]["stat"].pop("source", None)


@case("R-BROLL")
def broll_without_search(src):
    sc = with_tag(src, "B-ROLL")
    sc["shots"][0].pop("search", None)


@case("R-BROLL")
def broll_not_means_picture(src):
    sc = with_tag(src, "B-ROLL")
    sc["shots"][0]["text"] = "Gold coins stacking into a tall tower on a clean white desk in soft morning daylight."


@case("R-COMPARE")
def compare_card_missing(src):
    for s in src["scenes"]:
        for sh in s["shots"]:
            if sh["tag"] == "STAT" and (sh["stat"].get("compare") or {}).get("kind") == "features":
                sh["stat"].pop("compare")


@case("R-COMPARE")
def pain_points_card_missing(src):
    for s in src["scenes"]:
        for sh in s["shots"]:
            if sh["tag"] == "STAT" and (sh["stat"].get("compare") or {}).get("kind") == "pain_points":
                sh["stat"].pop("compare")


@case("R-COMPARE")
def comparison_cards_too_few(src):
    seen = set()
    for s in src["scenes"]:
        for sh in s["shots"]:
            cmp_ = sh.get("stat", {}).get("compare") if sh["tag"] == "STAT" else None
            if cmp_:
                if cmp_["kind"] in seen:
                    sh["stat"].pop("compare")
                else:
                    seen.add(cmp_["kind"])


@case("R-COMPARE")
def compare_product_b_first(src):
    for s in src["scenes"]:
        for sh in s["shots"]:
            cmp_ = sh.get("stat", {}).get("compare") if sh["tag"] == "STAT" else None
            if cmp_:
                cmp_["a"], cmp_["b"] = cmp_["b"], cmp_["a"]
                return


@case("R-FACTS")
def facts_left_tbd(src):
    src["locked_facts"]["PAIN-POINT MAP"] = "TBD"


@case("R-STILL")
def still_without_ken_burns(src):
    next(iter(src["prompts"]["flux"].values())).pop("ken_burns", None)


@case("R-BROLL")
def broll_negation(src):
    sc = with_tag(src, "B-ROLL")
    sc["shots"][0]["text"] = "Means: the point of the scene. Picture: a calm overhead desk with no people in view and soft light."


def banned(src):
    scene(src, "Problem 1")["line"] = "In a world where tools multiply, you're choosing the system your business runs on, not just another tool you can drop next month. Pick badly and you'll feel it in every launch, every follow-up, and every invoice for a year."


CASES.append(("banned_phrase", "R-VOICE", None, banned))


def main():
    base = make_fixture.make()
    R0 = lint_src(base)
    if R0.failures():
        print("BASELINE FIXTURE IS NOT CLEAN:", [(r["rule"], r["detail"]) for r in R0.failures()])
        return 1
    bad = 0
    for name, rule, sev, fn in CASES:
        src = copy.deepcopy(base)
        fn(src)
        R = lint_src(src)
        got = fails(R, rule) if rule else R.failures()
        ok = bool(got) and (sev is None or any(r["severity"] == sev for r in got))
        print(("ok   " if ok else "FAIL ") + f"{name}: " + (got[0]["rule"] + " " + got[0]["detail"][:70] if got else "NOT CAUGHT"))
        if not ok:
            bad += 1
    print(f"{len(CASES) - bad}/{len(CASES)} negative cases caught")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
