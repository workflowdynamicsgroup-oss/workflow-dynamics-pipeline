# Phases 1-3: intake, research, hooks and variation

## Phase 1: Intake

Send one message with the items below, then wait. Items 1 to 6 must be answered ("none" is valid for 4 and 5). Every other item has a default from `config.json` and may be left blank. Skip any item already answered in saved facts for this series and say so in one line.

Required:
1. Product A: name and affiliate link (GoHighLevel goes here if it is one of the two). Note if the VS page has separate anchors per product.
2. Product B: name and affiliate link.
3. Authority tier per product: research, demo, or hands-on. If hands-on: every component actually used and for how long. Unlisted components cannot carry first-person language. If vague, ask once more.
4. Screen recordings already owned: product, exact screen, length. Plan only around these.
5. Screenshots or photos available or capturable, and whether there is paid access to each product.
6. Cost-calculator page URL (the live address, or the address it will have). The teasers and packaging read it, and the gate will not pass with it blank.

Also ask once, in the same message: (a) keyword evidence you already have (volume, autocomplete); (b) a series tag; (c) whether a page for this comparison already exists on the site (read-only lookup, report its URL, never edit it). Items that depend on the production stack (RunPod time, voice reference path, Wan test clip) are expected open items: list them in the final message and do not ask about them.

Optional (defaults in brackets): avatar mode [generated]; exactly 3 audience segments [research them]; disclosure type [unsponsored]; tone; prior hook LINEs [read variation-log.json]; legitimate discount or trial [look up]; Apify keep or drop [keep]; measured wpm [`defaults.wpm`; run `retime.py` on the real audio for exact timing]; existing videos to link; generated-clip cap 0 to `gen_video_cap_max` [`defaults.gen_video_cap`]; helper agents on or off [on].

Disclosure framing: do not assume both products are sold as affiliate offers. Disclose exactly the relationship that exists. If a product has no affiliate link, say so at intake; its button is dropped and the honest-segments rule below still applies.

If a skipped item leaves a gap, state the default in one line and continue. Never re-ask, except under R-SKIP.

## Phase 2: Research

Run without stopping. Outputs: keyword result, Competitor Pattern Brief, Transcript Pattern Brief, Pain-Point Map, verification table, draft LOCKED_FACTS.

### R-SKIP (keyword check, competitor research, transcript pull)

These three run by default and are never skipped silently. If Apify is connected, run them within the cap. If not, ask once for the data. If the user says "skip" or leaves one blank, answer in two lines what it protects and what the script loses, then ask for "confirm skip". Only an explicit confirmation skips. On a confirmed skip: list it under SKIPS CONFIRMED, label the primary keyword "assumed", label the hook angle "best practice, unvalidated", never present skipped analysis as data. A thin sample is flagged plainly, not treated as evidence.

### R-APIFY-CAP (per-script cap, hard)

Total Apify spend for one script never exceeds the cap in `config.json` (`limits.apify_cap_usd`). Use `scripts/apify_budget.py` for all arithmetic. Never do cost math in your head.

- Prices come from `apify-cost-table.json` in the workspace (blank template in `templates/`). An actor not in the table is not run until its row is added from the actor's details page. Blank price = not runnable. Never guess a price. Refresh rows older than `apify_cost_row_max_age_days`.
- Before every run: `apify_budget.py plan --table T --log L --actor ID`. Refuse if it says REFUSE. Send its `maxTotalChargeUsd` as the per-run hard stop.
- After every run: `apify_budget.py record ...`. When the run finishes, read its billed cost (`usageTotalUsd` from the run details) and store it with `apify_budget.py fill --log L --index N --reported X`. Before the gate, no run may still be an estimate; if one is, say so in the APIFY SPEND line.
- Spend order (least valuable data hits the cap first): keyword and autocomplete, competitor list and ratios, comments for top and flop videos, transcripts last.
- If the cap stops a pull, do not ask to exceed it. Report what was not pulled, treat it as a thin sample, flag it at the gate.
- Before the first run, `apify_budget.py worst-case --table T` and store the figure; flag `[VERIFY AT BUILD]` until it matches the rows.
- The cap covers Apify only, not model usage or RunPod time. Report both, separately.

### Absence claims and counts (verify before the gate)
Any script line that says a product lacks something ("no texting", "no refund", "no trial") must be checked against the vendor's own feature page, pricing page and help center first. If the vendor offers it through an add-on or integration, say that instead (for example, "texting runs through a Twilio account you pay separately"). Use "I didn't find" only after those pages were read, and list it in verify flags. Re-read G2 ratings and counts from the live product page before the gate (search the product's G2 name, which can differ from its brand name) and put the read date in the flag.

### Helper agents (R-MODEL)

Only when the user allows and an agent tool exists. Helpers (cheapest model) do mechanical work only: run the actors the main model picked, fetch raw pages, save raw data, move files. All judgment (actor choice, ranking, keyword intent, verification, script, narration, exports) stays with the main model. Give each helper a self-contained brief with the exact table rows, limits and budget; helpers report raw data and run costs only.

### Steps

- **2.1 Live lookup, both products.** Official pricing page and docs: every tier, price, gating, limit, fee, integration count, trial, guarantee, cancel policy, card required. Prefer the vendor's page over third parties. Stamp each item with fetch date and source URL. No web access: say so, use last-known figures, flag all.
- **2.2 Also research.** Core use case; exactly 3 audience segments with evidence; honest differentiators; total cost of ownership (add-ons a buyer realistically needs, with typical monthly cost; main candidate for the held reveal); third-party ratings (G2, Capterra, Trustpilot) with review counts; switching cost; the biggest reason a viewer would stall, in real objection language.
- **2.3 Keyword check** (autocomplete, People Also Ask, Trends, YouTube autocomplete for "[A] vs [B]", "[A] alternative", "[A] pricing"). Say which intent the evidence favors. Output primary keyword (validated or assumed), secondaries, angle.
- **2.4 Competitor Pattern Brief.** Rank by engagement ratio and view-to-sub ratio, normalized for video age; a true overperformer is about 3x its channel baseline; hearted and pinned comments outrank generic ones; tag flop causes. Fill the template: DOMINANT TITLE PATTERN, DOMINANT HOOK TYPE, PAYOFF TIMING, RETENTION DEVICES OBSERVED, KEYWORDS CONFIRMED, UNANSWERED VIEWER OBJECTIONS, PATTERNS TO AVOID, CATEGORY ORDER OBSERVED, THE GAP THIS SCRIPT SHOULD EXPLOIT. The brief must change the script: hook exploits the gap; each unanswered objection is answered in a scene with `addresses_objection`; the category order differs from the variation log and the observed pattern unless data favors it. The brief also goes into `locked_facts` (see 2.8), because the packaging skill reads its title pattern and keywords.
- **2.5 Transcript pull.** Five videos (two or three true overperformers, one near 8:30-10:00, one flop). Pull transcripts with the cost-table actor, last in spend order. Extract patterns only (first-30-second structure, hook type, verdict position, category order, pacing, minute-6 moves, CTA placement, why the flop lost). Never let transcript wording reach a deliverable.
- **2.6 Pain-Point Map.** Combine comments, review sites and Reddit. Rank by frequency; tag type (pre-purchase doubt, onboarding, pricing shock, missing feature, support, switching fear) and segment; keep 1-2 verbatim phrases. A pain becomes a con only if evidence supports it. The map and each product's researched pros and cons are the source for the `pain_points` and `pros_cons` comparison cards (R-COMPARE), so keep the verbatim phrase and where it was heard for every pain you rank.
- **2.7 Verification table.** Claim, what the source says, source, status (confirmed / corrected / still-open), grouped by product. Correct anything contradicted before it reaches the script. Unresolvable items become one `[VERIFY AT PUBLISH]` flag each.

- **2.8 Fill LOCKED_FACTS.** Before leaving research, write every field in `config.json` `intake_required_fields` into `locked_facts` from the outputs above: AUDIENCE SEGMENTS (the 3 segments), CORE USE CASE, PRICING A / B (USD, verified date, source URLs), FEATURE COMPARISON, TCO A / B, THIRD-PARTY RATINGS A / B (each rating with the review site, count and read date), WHO SHOULD PICK A / B, LOCKED OBJECTION, PAIN-POINT MAP (verbatim phrases), CALCULATOR URL (from intake). The teaser and packaging skills read these fields and add no facts of their own, so a field left TBD, or a rating with no named source, fails R-FACTS and blocks the gate. If a field cannot be filled from evidence, ask once or flag it `[VERIFY AT PUBLISH]` with what is known; never leave it blank. Also write the three research fields the packaging and teaser skills can use: COMPETITOR BRIEF (DOMINANT TITLE PATTERN, KEYWORDS CONFIRMED and THE GAP, one line each), PATTERNS TO AVOID, and TRANSCRIPT BRIEF (patterns only, never transcript wording). These are not R-FACTS fields, so they do not block the gate, but if the research for one did not run, write `not run` in it. Never leave it as the default TBD line, which tells the next skill to ask the owner.

## Phase 3: Hooks and variation

- **3.1** Read `variation-log.json` (or intake item). State both badges (`config.json` badges); say plainly if tiers differ. Never soften or upgrade a badge later.
- **3.2 R-VARY.** Choose per video: head-to-head category order, micro-authority device (a receipt, a timed setup, a screenshot of a limit), hook device, opener device, visual motif for the stills and Wan clips. Do not repeat the latest log entry. Fixed across videos: disclosure strings and placement, CTA wording, end screen, held-reveal rule.
- **3.3 Hooks.** Pool: cost-of-wrong-choice, confession/reversal, direct callout, number-led claim, pain-first, cost reveal, contrarian. Score against the evidence. The chosen hook differs in wording and angle from prior hooks and the last videos' hook type. Pick two candidates, A and B. Hook claims follow tier. The hook is the promise the thumbnail makes and is paid off within 15 seconds.
