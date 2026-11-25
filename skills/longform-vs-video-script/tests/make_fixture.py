#!/usr/bin/env python3
"""Generate a synthetic, rule-clean source file for testing build_exports.py and lint.py.

The products ("Alpha CRM", "Beta Funnels") and every number are FICTIONAL. This file
exists only to prove the scripts work; it is not research and must never be published.

  make_fixture.py OUT.json [--ghl]    --ghl swaps in GoHighLevel as Product A
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import common as c  # noqa: E402

CFG = c.load_config()
SUBJ = ["A plain silver laptop seen from behind on a clean desk", "A brass key turning slowly in an old lock",
        "Paper airplanes gliding across a bright blue sky", "Colorful puzzle pieces sliding together on a wooden table",
        "A compass needle spinning and settling on a map", "Blue light streaks racing along a glowing grid",
        "A hand placing a final domino into a long chain", "Calendar pages flipping through the months",
        "A plain white signpost with two blank arrows", "Cubes snapping together into a tidy glowing wall",
        "Balance scales settling level with two glowing orbs", "Ripples spreading across still water from one drop",
        "Gears meshing smoothly inside a clear glass case", "A lighthouse beam sweeping across calm evening water",
        "Blank paper slips fluttering into a neat pile", "A magnifying glass drifting over a blank sheet of paper",
        "Tangled cables untwisting into one straight line", "A ladder of light steps climbing into a bright sky",
        "Dominoes toppling in a smooth chain", "A toolbox opening to show neatly arranged tools"]
CAM = ["slow push-in", "gentle overhead glide", "steady side tracking move", "slow rack focus", "smooth orbit around the subject",
       "slow upward tilt", "quick dolly forward", "soft handheld drift"]
LIGHT = ["soft morning daylight", "crisp studio lighting", "warm even glow", "bright even lighting", "clean high-contrast light", "golden late sun"]
MOOD = ["calm confident", "curious", "focused", "optimistic", "steady and reassuring"]


CFG_KINDS = ["reviews", "pricing", "monthly_cost", "features", "pros_cons", "pain_points"]


def broll_text(i):
    return (f"{SUBJ[i % len(SUBJ)]}, {CAM[(i * 3) % len(CAM)]}, {LIGHT[(i * 5) % len(LIGHT)]}, {MOOD[(i * 7) % len(MOOD)]} mood, "
            "framed for 16:9 with the main subject near the center and open space on both sides.")


def make(ghl=False):
    A = "GoHighLevel" if ghl else "Alpha CRM"
    B = "Beta Funnels"
    disc = CFG["disclosure_strings"]["unsponsored"]
    scenes = []
    def est(line):
        n, _, _ = c.to_narration(line, CFG)
        words = c.count_words(n)
        return max(4.0, words / 182 * 60 + n.count("[BEAT]") * 0.4)

    def add(section, name, line, osd=None, plan=None, prefer=None, **extra):
        sc = {"id": len(scenes) + 1, "name": name, "section": section, "line": line,
              "on_screen_text": osd or [], "shots": []}
        sc.update(extra)
        sc["_plan"] = plan or []
        sc["_prefer"] = prefer
        scenes.append(sc)
        return sc

    # --- hook (avatar block 1)
    add("hook", "Hook", "One costs $97. One costs triple.", chapter="Intro",
        osd=[{"text": disc, "at_s": 0, "dur_s": 5}, {"text": "$97", "at_s": 0.6, "dur_s": 2}, {"text": "TRIPLE", "at_s": 2.2, "dur_s": 1.5}],
        plan=[{"tag": "GEN-VIDEO", "role": "hook", "prompt_id": "w1"}, None])
    add("hook", "Stakes 1", "Pick the wrong one and you'll pay for it all year, in money and in hours you never get back.", avatar_block=1)
    add("hook", "Stakes 2", "Most people compare sticker prices. [BEAT] That's the mistake, and it's the one this video fixes.", avatar_block=1)
    add("hook", "Stakes 3", f"So here's the real version of {A} vs {B}, with every bill included and nothing left vague.", avatar_block=1)
    add("hook", "Stakes 4", "Both landing pages promise the same thing. The results look very different once you're inside the dashboards.", avatar_block=1)
    add("hook", "Stakes 5", "Which one wins depends entirely on who you are. So let's sort that out first, in plain language.", avatar_block=1)
    add("hook", "Stakes 5b", "The same buying mistake shows up in the comments every single week, and it's almost always about the sticker price.", avatar_block=1)
    add("hook", "Stakes 5c", "This one is built to be checked, not just believed. Every figure comes from a dated source, and anything unconfirmed gets flagged on screen.", avatar_block=1)
    add("hook", "Stakes 6", "No hype and no guessing. Only what the pricing pages, the docs, and real reviews actually show.", avatar_block=1)

    # --- segment map
    add("segment_map", "Segment map intro", "Both are strong products. Each one wins for a different person, and here's the quick map.", chapter="Who wins where",
        plan=[{"tag": "ASSET-BRAND", "product": "a"}, {"tag": "ASSET-BRAND", "product": "b"}])
    add("segment_map", "Segment solo", f"Solo operators? {B} fits best, because one simple funnel is all you need.")
    add("segment_map", "Segment agency", f"Agency owners? {A} fits best, because client work needs depth and clean handoffs.")
    add("segment_map", "Segment startup", f"Scaling startups? {A} again, because growth punishes tools that need constant patching.")
    add("segment_map", "Segment freelancer", f"Freelancers? It depends on how many clients you run at once, and I'll show exactly where the line sits.")
    add("segment_map", "Segment ecommerce", "Small online stores? The answer changes with how many products you sell, and I'll point out exactly where it flips.")
    add("segment_map", "Roadmap", "Stay for one number that flips two of those answers. [BEAT] It lands near the end, and most reviews skip it.")

    # --- micro authority
    add("micro_authority", "Micro authority", f"I ran {A}'s pipelines for six months. {B} I researched from its docs and reviews.",
        chapter="How I checked", first_person={"product": "a", "component": "pipelines"},
        _stat={"value": "6 months", "label": "Hands-on time with Go High Level pipelines", "source": "Creator's own use (fixture)"})
    add("micro_authority", "Micro authority 3", "I also read the official docs end to end and checked each claim against a dated pricing page. Where pages disagreed, I say so.")
    add("micro_authority", "Micro authority 2", "So every claim here carries a source, a number, or a named limit. Anything I couldn't confirm gets flagged on screen.")

    # --- problem
    add("problem", "Problem 1", "You're choosing the system your business runs on, not just another tool you can drop next month. Pick badly and you'll feel it in every launch, every follow-up, and every invoice for a year.", chapter="The real decision",
        plan=[{"tag": "GEN-STILL", "prompt_id": "f1"}])
    add("problem", "Problem 2", "A wrong pick costs five hours a week.", _stat={"value": "5 hrs / week", "label": "Time lost to a poor fit", "source": "Fixture estimate, not a measured figure"})
    add("problem", "Problem 3", "And the bill grows quietly, [BEAT] one add-on at a time, until the cheap plan isn't cheap anymore.")
    add("problem", "Problem 4", "The question isn't which tool is better. It's which tool fits the way you actually work, day after day.")
    add("problem", "Problem 5", "Think about your week. Where do leads come in, who follows up, and what happens when you're offline for two days?")
    add("problem", "Problem 6", "A good system answers all three without you touching it. A bad one quietly adds a new chore every month.")
    add("problem", "Problem 6b", "Most buyers also forget the handoff. When a helper joins, can they find the pipeline, the pages, and the follow-ups in under an hour?")
    add("problem", "Problem 6c", "Then there's reporting. If you can't see which page or message brought a customer in, you can't tell what's working, and you end up guessing with your budget.")
    add("problem", "Problem 6d", "Good tools make that visible without a spreadsheet. Weak ones leave you exporting files every Friday and hoping the numbers match.")
    add("problem", "Problem 7", "That's why a quick feature checklist misleads people. The checklist never shows you the chores hiding underneath.")

    # --- agitation
    add("agitation", "Agitation 1", "Here's where buyers stall. They fear picking wrong, paying twice, and rebuilding everything from scratch, so they delay the decision for weeks and let the manual work pile up in the meantime.", chapter="Where buyers stall",
        plan=[{"tag": "GEN-STILL", "prompt_id": "f2"}])
    add("agitation", "Objection", "The biggest worry I see in comments? [BEAT] \"What if I outgrow it?\"", addresses_objection="outgrowing the tool")
    add("agitation", "Objection answer", "Fair worry. Both tools scale, but in very different directions, and that's what the next few minutes show.")
    add("agitation", "Agitation 2", "I've watched people switch tools halfway through a launch. It always costs a week, and it always costs momentum.")
    add("agitation", "Agitation 3", "Moving contacts, rebuilding pages, retraining a helper. Nothing in that list is hard, but all of it adds up fast.")
    add("agitation", "Agitation 3b", "And there's the quiet fear nobody says out loud. What if the tool I pick is the reason the launch stalls?")
    add("agitation", "Agitation 4", "So the goal today is simple. Pick once, pick well, and don't think about this decision again for a long while.")
    add("agitation", "Cost of inaction", "And every week you wait, the manual work keeps piling up, and the leads keep slipping through.", names_cost_of_inaction=True)

    # --- categories
    cats = [
        ("setup", f"{A} takes an afternoon to set up. Pipelines come ready-made, so you edit instead of build, and that saves real time.",
         f"{B} launches simple pages fast, so this one favors {B}. But the setup story changes after the first page, and that's coming up.",
         {"tag": "ASSET-SHOT", "product": "a", "detail": "pipeline template picker"},
         {"tag": "ASSET-SHOT", "product": "b", "detail": "funnel template list"}),
        ("features", f"{A} goes deep on automations and lead tracking. You can chain follow-ups across email and text without extra tools.",
         f"For {A}, depth wins once your list grows, while {B} keeps features narrow and focused. Now, what about connections?",
         {"tag": "ASSET-CLIP", "product": "a", "detail": "build one automation"},
         {"tag": "ASSET-CLIP", "product": "b", "detail": "edit one funnel step"}),
        ("integrations", f"{A} connects to most payment and calendar tools. Native connections save you glue work and a few extra logins.",
         f"This favors {A}, because {B} relies on add-ons for the same jobs. Every add-on is another login and another bill.",
         {"tag": "ASSET-SHOT", "product": "a", "detail": "integrations list"},
         {"tag": "ASSET-SHOT", "product": "b", "detail": "integrations list"}),
        ("ease", f"{A} has a steeper first week. Menus are crowded, but once you learn the layout, daily work gets quick and predictable.",
         f"{B} feels clean from the first login, which favors {B} for beginners. The tradeoff is fewer places to grow into later.",
         None,
         None),
        ("support", f"{A} answers in chat during business hours. The docs are thorough, though a little dense for first-time users.",
         f"{B} is quick and friendly on basic questions, which favors {B}. But does it stay that simple?",
         {"tag": "ASSET-SHOT", "product": "a", "detail": "help center home"},
         None),
    ]
    for i, (cat, la, lb, ia, ib) in enumerate(cats):
        add("category", f"{cat} A", la, category=cat, chapter=("Head to head" if i == 0 else None), plan=[ia])
        add("category", f"{cat} B", lb, category=cat, plan=[ib])
        if i == 0:
            add("soft_cta", "Soft CTA", "If you already know your situation, both are linked below. If not, keep watching.")

    # --- proof / interrupt / pricing
    add("third_party_proof", "Proof intro", "Opinions are cheap, so here's what thousands of paying users say on a review site.", chapter="What reviewers say")
    add("third_party_proof", "Proof ratings", "On G2, 4.6 versus 4.2.",
        osd=[{"text": f"{A}  4.6 on G2  |  1,204 reviews", "at_s": 0, "dur_s": 4}, {"text": f"{B}  4.2 on G2  |  873 reviews", "at_s": 4, "dur_s": 4}],
        _stat={"value": "4.6 vs 4.2", "label": "G2 rating, Go High Level vs Beta Funnels", "source": "G2 listings, checked 2026-11-19 (fixture)"})
    add("third_party_proof", "Proof read", "Both score well and the gap is small, so ratings alone won't pick your tool. Price and fit will, and that's next.")
    add("third_party_proof", "Proof themes", "Reading the written reviews, the praise and complaints repeat. That repetition is more useful than the stars.")
    add("third_party_proof", "Proof themes 1b", "I grouped what reviewers said into setup, support, and cost surprises. Cost surprises came up more often than any other complaint.")
    add("third_party_proof", "Proof themes 2", f"Users of {A} praise power and complain about learning time. Users of {B} praise speed and complain about limits.")
    add("pattern_interrupt", "Interrupt", "Here's where people get this wrong. [BEAT] They compare features, not total cost, and then regret it months later, when the first real bill lands and the add-ons start stacking up.",
        plan=[{"tag": "GEN-STILL", "prompt_id": "f3"}])
    add("switching_cost", "Switching cost", "Here's the part reviews skip. Switching tools later has a price too, and it's paid in hours, not just dollars.", chapter="Cost of switching")
    add("switching_cost", "Switching cost 2", "Most people lose two to three weeks.", _stat={"value": "2-3 weeks", "label": "Typical time lost when switching tools", "source": "Fixture estimate, not a measured figure"})
    add("switching_cost", "Switching cost 3", "That's why the first choice matters more than any discount. Picking right once beats saving twenty dollars twice.")
    add("pricing", "Price intro", "Start with sticker prices, because that's what everyone compares first.", chapter="Sticker prices")
    add("pricing", "Price both", "Entry plans: $97 a month versus $67.",
        osd=[{"text": "$97/mo", "at_s": 0.3, "dur_s": 3}, {"text": "$67/mo", "at_s": 3.5, "dur_s": 3}],
        _stat={"value": "$97 vs $67", "label": "Entry plan, per month", "source": "Official pricing pages, checked 2026-11-19 (fixture)"})
    add("pricing", "Price add-ons", "Now look at what the entry plans leave out. Email sending, extra users, and payment tools often sit behind upgrades.")
    add("pricing", "Price add-ons 1b", "So the sticker price is really a starting line. The honest question is what each plan costs once it can do your actual job.")
    add("pricing", "Price add-ons 1c", "Think about the tools you'd bolt on, like an email sender, a scheduler, and a payment add-on. Each is small, but together they aren't.")
    add("pricing", "Price add-ons 1d", "I priced each add-on from its own public page, then added them to the base plan, so you can check every line yourself.")
    add("pricing", "Price add-ons 1e", "Add-ons also hide in usage limits. Contacts, emails per month, and team seats all have a ceiling, and the next tier up costs more.")
    add("pricing", "Price add-ons 1f", "Priced for a ten-person agency, line by line.", _stat={"value": "10 seats", "label": "Agency stack priced on both sides", "source": "Public pricing pages, checked 2026-11-19 (fixture)"})
    add("pricing", "Price add-ons 1g", "A solo operator with one funnel needs far less, and that's exactly why the answer changes by person.")
    add("pricing", "Price add-ons 2", "No secrets here. It's all on the pricing pages, but almost nobody adds it up before they buy.")
    add("pricing", "Price loop", "On paper, that's a clear win for one side, and plenty of reviews stop right there. But the sticker price isn't the number that matters, and the next section shows why.",
        plan=[{"tag": "GEN-STILL", "prompt_id": "f4"}])

    # --- reveal (avatar block 2)
    add("reveal_bridge", "Reveal bridge", "Now the number that changes everything.", avatar_block=2, chapter="The number that matters",
        plan=[None])
    add("held_reveal", "Reveal 1", "Add the tools each one actually needs to do the job you bought it for. [BEAT] Here are the real totals.", avatar_block=2)
    add("held_reveal", "Reveal totals", "All in: $140 a month versus $354.", avatar_block=2,
        osd=[{"text": "$140/mo all in", "at_s": 0.2, "dur_s": 3}, {"text": "$354/mo all in", "at_s": 3.2, "dur_s": 3}, {"text": "$214 / month", "at_s": 7.0, "dur_s": 3}],
        retention_beat=True,
        _stat={"value": "$214 / month", "label": "Monthly gap, all tools included", "source": "Official pricing pages plus required add-ons, checked 2026-11-19 (fixture)"})
    add("held_reveal", "Reveal gap", "That's a $214 gap every single month.", avatar_block=2, osd=[{"text": "$214 gap", "at_s": 0.3, "dur_s": 3}])
    add("held_reveal", "Reveal year", "Over a year, that's $2,568.", avatar_block=2, osd=[{"text": "$2,568 / year", "at_s": 0.3, "dur_s": 3}],
        _stat={"value": "$2,568 / year", "label": "The monthly gap over 12 months", "source": "$214 x 12, from the totals above (fixture)"})
    add("held_reveal", "Reveal meaning", "That gap decides it for anyone running more than one funnel, and it shows up on the budget as a real line item.", avatar_block=2)
    add("held_reveal", "Reveal meaning 2", "Solo operators with one page can ignore it. Everyone else shouldn't, and that's the flip I promised.", avatar_block=2)

    # --- close (avatar block 3)
    seg = [("Solo operators", B, "b", "One funnel, fast launch, simple help. That's your match, and you won't pay for depth you'll never use."),
           ("Agency owners", A, "a", "Depth, integrations, and a lower all-in bill. Client work rewards a system that handles the whole job, with fewer logins and fewer things to explain."),
           ("Scaling startups", A, "a", "It grows with you without piling on new add-ons, so your costs stay predictable while your list climbs.")]
    if ghl:
        seg = [seg[1], seg[0], seg[2]]
    for i, (name, prod, key, reason) in enumerate(seg):
        add("verdict", f"Verdict {name}", f"{name}? {prod}.", verdict_product=key, avatar_block=3,
            chapter=("Verdicts" if i == 0 else None))
        add("verdict_reason", f"Verdict reason {name}", reason, verdict_product=key, avatar_block=3,
            cta_button={"wording": CFG["cta"]["verdict"].format(product=prod), "at_s": 0, "dur_s": 5},
            osd=[{"text": disc, "at_s": 0, "dur_s": 5}])
    add("recap", "Recap", "Pick by your situation, not by the sticker price. Comment A or B and tell me which way you're leaning.", avatar_block=3)
    add("risk_reversal", "Risk intro", "Before you commit, here's how each one lets you walk away.", avatar_block=3, chapter="Risk check")
    add("risk_reversal", "Risk both", "Trial: 14 days versus 30.", avatar_block=3,
        osd=[{"text": f"{A}: 14-day trial | no card", "at_s": 0.2, "dur_s": 4}, {"text": f"{B}: 30-day guarantee | card required", "at_s": 4.2, "dur_s": 4}],
        _stat={"value": "14 vs 30 days", "label": "Trial or guarantee period", "source": "Official signup pages, checked 2026-11-19 (fixture)"})
    add("cost_of_inaction", "Inaction", "Every month you wait costs you leads, and those don't come back.", avatar_block=3)
    add("offer", "Offer", "Use my link first, before you create an account, so your attribution isn't lost.", avatar_block=3,
        end_screen_start=True, chapter="Use my link first",
        cta_button={"wording": CFG["cta"]["offer"], "at_s": 0, "dur_s": 5},
        osd=[{"text": disc, "at_s": 0, "dur_s": 5}],
        plan=[{"tag": "GEN-VIDEO", "role": "cta_backdrop", "prompt_id": "w3"}])
    add("end_screen", "End screen", "Pick yours. The link's below.",
        osd=[{"text": disc, "at_s": -5, "dur_s": 5}],
        plan=[{"tag": "GEN-VIDEO", "role": "ending_backdrop", "prompt_id": "w4"}])

    # --- assign shots (pipeline tags; whole seconds are placed later by common.build_timeline)
    counter = {"b": 0}
    avatar_idx = {}
    for sc in scenes:
        plan = [p for p in sc.pop("_plan") if p]
        sc.pop("_prefer")
        stat = sc.pop("_stat", None)
        has_num = bool(c.number_tokens(sc["line"]))
        dur = est(sc["line"])
        if sc["section"] == "end_screen":
            dur = max(dur, 5)
        if sc.get("cta_button"):
            dur = max(dur, 5)
        shots = []
        if stat:
            shots.append({"tag": "STAT", "stat": dict(stat)})
            rest = max(0.0, dur - 15)
        elif any(p["tag"] == "GEN-STILL" for p in plan):
            shots.append(dict(next(p for p in plan if p["tag"] == "GEN-STILL")))
            plan = [p for p in plan if p["tag"] != "GEN-STILL"]
            rest = max(0.0, dur - 15)
        else:
            rest = dur
        n = 0 if rest <= 0 else max(len(plan), math.ceil(rest / 5))
        for j in range(n):
            if j < len(plan):
                shots.append(dict(plan[j]))
            else:
                counter["b"] += 1
                shots.append({"tag": "B-ROLL", "text": broll_text(counter["b"])})
        sc["shots"] = shots

    # extra stills so B-roll stays under 40% of runtime (the pipeline cap); each says what it shows and why
    STYLES = ["isometric 3D", "macro photoreal object", "paper-cut editorial collage"]
    TOPIC = {"pricing": ["a tiered staircase of blocks", "a plain brass key beside a blank card", "a plain white signpost with two blank arrows", "a plain closed laptop with a blank lid", "a ladder leaning on a wall of blocks", "a set of plain headphones on a desk", "a tidy bundle of plain cables"],
             "category": ["a toolbox with one drawer open", "a set of connected gears", "a dial set between two settings", "a tidy control panel of switches", "a row of puzzle pieces", "a plain keyboard with blank keys"],
             "switching_cost": ["a moving box beside a tangled cable", "a bridge with a missing plank"],
             "other": ["a signpost with two arrows", "a balance scale holding two weights", "a compass on a folded map", "a lighthouse over calm water", "a paper boat on a clean desk", "a chess piece beside a plain white cube", "a key resting on an open notebook", "a ladder leaning on a wall of blocks", "a magnifying glass over a checklist", "a gate with two open paths"]}
    WHY = {"pricing": "makes the cost point visible while the plan prices are spoken",
           "category": "gives the feature comparison one concrete picture to hold on to",
           "switching_cost": "shows what changing tools later really costs you",
           "other": "gives the choice between the two tools a simple symbol"}
    extra_prompts = {}
    fixed_stills = sum(1 for sc in scenes for sh in (sc.get("shots") or []) if sh["tag"] == "GEN-STILL")
    budget = 14
    n_extra = 0

    def free(sc):
        shs = sc.get("shots") or []
        return bool(shs) and all(s["tag"] == "B-ROLL" for s in shs) and not sc.get("cta_button") and sc["section"] != "end_screen"

    # long shots (STAT, GEN-STILL) run 9-16 s, so they sit under this scene and the next ones (span)
    i = 0
    while i < len(scenes):
        sh0 = (scenes[i].get("shots") or [None])[0]
        if sh0 and sh0.get("_planned"):
            i += max(1, sh0["span"])
            continue
        if sh0 and sh0["tag"] in ("STAT", "GEN-STILL"):
            acc, k = est(scenes[i]["line"]), i
            while acc < 14.2 and k + 1 < len(scenes) and acc + est(scenes[k + 1]["line"]) <= 14.6 and not scenes[k + 1].get("cta_button") and not any(s["tag"] in ("STAT", "GEN-STILL", "ASSET-SHOT", "ASSET-CLIP", "GEN-VIDEO") for s in (scenes[k + 1].get("shots") or [])) and scenes[k + 1]["section"] != "end_screen":
                k += 1
                acc += est(scenes[k]["line"])
            if acc < 10:
                nb = max(1, math.ceil(acc / 5))
                fill = []
                for _ in range(nb):
                    counter["b"] += 1
                    fill.append({"tag": "B-ROLL", "text": broll_text(counter["b"])})
                scenes[i]["shots"] = fill
                i += 1
                continue
            sh0["span"] = k - i + 1
            over = acc - 14.8
            tail = []
            while over > 1.5:
                counter["b"] += 1
                tail.append({"tag": "B-ROLL", "text": broll_text(counter["b"])})
                over -= 4
            sh_tail = tail
            for j in range(i + 1, k + 1):
                scenes[j]["shots"] = []
                scenes[j].pop("avatar_block", None) if False else None
            scenes[i]["shots"] = [sh0] + sh_tail
            i = k + 1
        else:
            i += 1

    TOPICAL = {"pricing", "category", "switching_cost", "held_reveal"}
    fixed_stills_topical = 1
    for allowed, cap_n in ((TOPICAL, 9 - fixed_stills_topical), (None, budget)):
      i = 0
      streak = 0
      while i < len(scenes):
        if not (free(scenes[i]) and n_extra < min(budget, cap_n) and i >= 6 and (allowed is None or scenes[i]["section"] in allowed)):
            i += 1
            streak = 0
            continue
        if streak >= 2:          # every third free group stays B-roll
            streak = 0
            i += 1
            continue
        acc, k = est(scenes[i]["line"]), i
        while acc < 14.2 and k + 1 < len(scenes) and free(scenes[k + 1]) and acc + est(scenes[k + 1]["line"]) <= 14.6:
            k += 1
            acc += est(scenes[k]["line"])
        if acc < 10.3:
            i = k + 1
            continue
        sec = scenes[i]["section"]
        grp = sec if sec in ("pricing", "category", "switching_cost") else "other"
        if not TOPIC[grp]:
            grp = "other"
        if not TOPIC["other"] and grp == "other":
            TOPIC["other"] = ["a lantern on a stone path", "a paper plane over a desk", "a spirit level on a plank", "a weathervane in clear sky", "an open door with warm light"]
        obj = TOPIC[grp].pop(0)
        pid = f"x{n_extra + 1}"
        extra_prompts[pid] = {"text": f"A blurred plain paper plane in the foreground, {obj} in the midground on a rule-of-thirds point, a bright electric blue background, bright even key light, 16:9.",
                              "ken_burns": ["slow zoom in", "slow pan left to right", "slow zoom out", "slow pan right to left"][n_extra % 4], "style": STYLES[n_extra % 3], "purpose": WHY[grp]}
        tail = []
        over = acc - 14.8
        while over > 1.5:
            counter["b"] += 1
            tail.append({"tag": "B-ROLL", "text": broll_text(counter["b"])})
            over -= 4
        extra_prompts.pop(pid, None)
        scenes[i]["shots"] = [{"tag": "STAT", "stat": {"value": f"Card {n_extra + 1}", "label": "Fixture comparison card", "source": "Fixture source, checked 2026-11-19"}, "span": k - i + 1, "_planned": True}] + tail
        for j in range(i + 1, k + 1):
            scenes[j]["shots"] = []
        n_extra += 1
        streak += 1
        i = k + 1

    # avatar on every other short non-number shot inside the three blocks, never over long or full-screen shots
    avatar_idx = {}
    for sc in scenes:
        blk = sc.get("avatar_block")
        if not blk:
            continue
        has_num = bool(c.number_tokens(sc["line"]))
        for sh in sc.get("shots") or []:
            k = avatar_idx.get(blk, 0)
            avatar_idx[blk] = k + 1
            if sc["section"] != "end_screen" and not has_num and sh["tag"] in ("B-ROLL", "GEN-VIDEO") and k % 2 == 0 and sh["tag"] != "GEN-VIDEO":
                sh["avatar"] = True
    order = [sh["prompt_id"] for sc in scenes for sh in (sc.get("shots") or []) if sh["tag"] == "GEN-STILL"]
    restyle = {pid: ["isometric 3D", "macro photoreal object", "paper-cut editorial collage"][n % 3] for n, pid in enumerate(order)}
    # retention beats about every 75 seconds
    probe = {"video": {"product_a": A, "product_b": B, "wpm": 182}, "scenes": scenes}
    tl = c.build_timeline(probe, CFG)
    next_mark = 70
    for s in tl:
        if s["start"] >= next_mark:
            s["scene"]["retention_beat"] = True
            next_mark = s["start"] + 70

    A_ = A
    prompts = {
        "flux": {
            "f1": {"purpose": "shows the cost-versus-value idea behind the hook", "text": "A blurred plain white signpost in the foreground, a balance scale on a rule-of-thirds point in the midground, a bright electric blue gradient background, bright even key light, saturated contrast, 16:9.", "ken_burns": "slow zoom in toward the scale", "style": "isometric 3D"},
            "f2": {"purpose": "puts a picture to the pain of a stalled launch", "text": "Blurred cracked tiles in the foreground, a stalled gear tangled in cables in the midground on a rule-of-thirds point, a bright electric blue background, bright even key light, 16:9.", "ken_burns": "slow pan left to right", "style": "macro photoreal object"},
            "f3": {"purpose": "stands for the trap of comparing features and not total cost", "text": "Blurred paper-cut arrows in the foreground, a bold magnifying glass over a blank checklist in the midground on a rule-of-thirds point, a bright electric blue background, bright even key light, 16:9.", "ken_burns": "slow zoom out", "style": "paper-cut editorial collage"},
            "f4": {"purpose": "puts the sticker plan against the full set of tools", "text": "A blurred plain white signpost in the foreground, a plain closed laptop with a blank lid in the midground on a rule-of-thirds point, a bright electric blue background, bright even key light, 16:9.", "ken_burns": "slow pan right to left", "style": "isometric 3D"},
        },
        "wan": {
            "w1": {"text": "Bright electric blue light ribbons sweep across a luminous white space while glowing particles burst outward in rhythmic pulses, with a dramatic camera push forward, saturated cyan highlights, crisp motion and strong contrast."},
            "w3": {"text": "Soft bright blue gradient waves roll slowly across a clean luminous field, leaving generous open space in the lower center, with gentle sparkles drifting upward and calm, polished, high contrast lighting."},
            "w4": {"text": "A glowing electric blue orb sits centered in a bright luminous field, pulsing gently while quiet light trails drift along the far left and right edges, calm motion, polished high contrast glow, steady and centered."},
        },
    }
    for sc in scenes:
        for sh in sc.get('shots') or []:
            sh.pop('_planned', None)
    prompts['flux'].update(extra_prompts)
    for pid, st in restyle.items():
        prompts['flux'][pid]['style'] = st
    source = {
        "video": {
            "product_a": A, "product_b": B, "link_a": "https://example.com/a", "link_b": "https://example.com/b",
            "vs_page_url": "https://example.com/vs", "slug": "ghl-vs-beta-fixture" if ghl else "alpha-vs-beta-fixture",
            "primary_keyword": f"{A} vs {B}", "primary_keyword_status": "assumed", "secondary_keywords": ["fixture keyword"],
            "tiers": {"a": {"tier": "hands-on", "tested_components": ["pipelines", "automations"]}, "b": {"tier": "research"}},
            "disclosure_type": "unsponsored", "avatar": {"mode": "generated"}, "gen_video_cap": 4, "wpm": 182,
            "segments": ["Solo operators", "Agency owners", "Scaling startups"],
            "render_composition": "Long16x9",
            "style_families": ["isometric 3D", "macro photoreal object", "paper-cut editorial collage"],
            "variation": {"category_order": ["setup", "features", "integrations", "ease", "support"], "micro_authority_device": "timed setup",
                          "hook_device": "price contrast", "hook_type": "number-led claim", "opener_device": "slam word",
                          "visual_motif": "signpost"},
            "held_reveal": {"number": "$214", "flips": "the solo operator answer when running more than one funnel", "segment": "Solo operators"},
            "hook_options": {"A": {"line": scenes[0]["line"], "type": "number-led claim"},
                             "B": {"scene_lines": ["Two plans. One bill surprises you.", "Which one is it?"], "type": "pain-first"}},
            "packaging": {"titles": [f"{A} vs {B}: the real cost", f"{A} or {B}? Pick by situation", f"{A} vs {B} total cost compared"],
                          "description_body": f"{A} vs {B} compared on setup, features, integrations, support, and total monthly cost. FIXTURE ONLY.",
                          "tags": [f"{A} vs {B}", f"{A} review", f"{B} review", "crm comparison", "funnel software"]},
            "verify_flags": [{"tag": "VERIFY AT PUBLISH", "item": "fixture figures are fictional", "in_table": True}],
            "link_placeholders": ["VS page URL placeholder"],
        },
        "scenes": scenes,
        "prompts": prompts,
        "research_summary": {"gap": "fixture", "objections": ["fixture"], "script_changes": "fixture", "apify_spend": {}},
        "manual_checks": {"R-NOFAKE contact sheet": "fixture, n/a"},
        "locked_facts": {
            "CORE USE CASE": "fixture", "KEYWORD EVIDENCE": "FICTIONAL TEST DATA",
            "PRICING A / B (USD, verified [date], source URLs)": f"{A}: $97/mo (verified 2026-11-19, https://example.com/a/pricing); {B}: $67/mo (verified 2026-11-19, https://example.com/b/pricing) [FICTIONAL]",
            "FEATURE COMPARISON": f"{A}: CRM, pipelines, automations; {B}: funnel pages, email [FICTIONAL]",
            "TCO A / B": f"{A}: $140/mo; {B}: $354/mo [FICTIONAL]",
            "THIRD-PARTY RATINGS A / B": f"{A}: 4.6 on G2 (1,204 reviews); {B}: 4.2 on G2 (873 reviews) [FICTIONAL]",
            "WHO SHOULD PICK A / B": f"{A}: agency owners and scaling startups; {B}: solo operators [FICTIONAL]",
            "LOCKED OBJECTION": "What if I outgrow it? [FICTIONAL]",
            "PAIN-POINT MAP": "\"I am paying for four tools and none of them talk\" [FICTIONAL]",
            "CALCULATOR URL": "https://example.com/calculator"},
    }
    # R-BROLL: every B-roll shot carries a Means / Picture brief and a one- or two-noun search
    nouns = ["gears", "key", "compass", "laptop", "toolbox", "domino", "calendar", "headphones", "cubes", "scales", "ripples", "lighthouse",
             "paper", "magnifier", "cables", "ladder", "keyboard", "door", "signpost", "umbrella", "bulb", "rocket", "puzzle", "notebook",
             "map", "lock", "anchor", "bridge", "kite", "lantern", "feather", "bell", "telescope", "mirror", "ribbon", "bucket"]
    k = 0
    for sc in source["scenes"]:
        for sh in sc.get("shots") or []:
            if sh["tag"] == "B-ROLL":
                sh["text"] = f"Means: the point of this scene. Picture: {SUBJ[k % len(SUBJ)].lower()}, centered and evenly lit."
                sh["search"] = nouns[k % len(nouns)]
                k += 1
    # R-COMPARE: the baseline carries one side-by-side comparison card of each required kind
    kinds = list(CFG_KINDS)
    for sc in source["scenes"]:
        for sh in sc.get("shots") or []:
            if sh["tag"] == "STAT":
                if not kinds:
                    kinds = list(CFG_KINDS)
                sh["stat"]["compare"] = {"kind": kinds.pop(0), "a": A, "b": B,
                                          "rows": [{"label": "Row one", "a": "1", "b": "2"}, {"label": "Row two", "a": "3", "b": "4"}]}
    return source


if __name__ == "__main__":
    out = sys.argv[1]
    ghl = "--ghl" in sys.argv
    src = make(ghl)
    Path(out).write_text(json.dumps(src, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tl = c.build_timeline(src, c.load_config())
    print(f"wrote {out}: {len(src['scenes'])} scenes, {sum(s['words'] for s in tl)} words, {c.mmss(tl[-1]['end'])}")
