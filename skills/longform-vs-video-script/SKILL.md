---
name: "longform-vs-video-script"
description: "Builds a YouTube Product A vs Product B affiliate comparison video package, at least 8:00 long and about 10:00 at most, with side-by-side comparison cards, in seven phases with one approval gate."
---

# Long-Form VS Video Script

Writes one "Product A vs Product B" affiliate comparison video as a single structured source file, then generates every deliverable from it with scripts. Each product wins for a different type of viewer. Do not call either product the overall winner. The output feeds `vs-video-pipeline` (which renders it), `vs-packaging` and `vs-teasers` (which read its locked facts and script from R2).

Read this file fully, then read the reference for each phase when you reach it. Do not preload them all.

**Numbers live in `config.json`.** Every limit, window, cap, word count, runtime, wpm, disclosure string, CTA wording, banned phrase and pronunciation is read from `config.json` (a workspace `config.local.json` overrides it). This file names the limits and does not restate their values. If a number is not in config, it is not a rule.

## Run order

Output "PHASE n: name. Starting." and "PHASE n COMPLETE." for each phase.

1. **Intake** — `references/phases-1-3.md`. One message, then wait. Defaults in `config.json`.
2. **Research** — same file, with the five Apify pulls and how they feed the script in "Apify research" below. Budget arithmetic is `scripts/apify_budget.py`. Ends by filling every LOCKED_FACTS field (R-FACTS).
3. **Hooks and variation** — same file. Two hook candidates (A, B).
4. **Script** — `references/script-rules.md`. Write LINEs and shots into `{slug}-source.json` (format in `references/source-schema.md`). Never write timestamps, word counts or narration numbers by hand. Put a `[BEAT]` pause cue only between two sentences, and only as a cue for the script file: the export strips every `[BEAT]` from the narration file, because the voice reads them aloud or splits the sentence.
5. **Verification** — run `python3 scripts/lint.py SOURCE --out OUT --stage pre`, fix every failure, then the manual checks in `references/phases-5-7.md`.
6. **Gate** — `python3 scripts/build_exports.py SOURCE --out OUT --gate` writes `gate-preview.md`. Show it. With `gate_mode: approve` (default) stop and wait for A or B plus changes. With `gate_mode: auto` (unattended runs) go on with Hook A and say so at the top of the result.
7. **Exports** — apply the reply to the source file, run `build_exports.py` (no `--gate`), then `lint.py --stage post`. Save the files to `inputs/[slug]/` in R2, overwriting any file of the same name without asking. See `references/phases-5-7.md`.

Allowed stops: intake answers, one retry on a vague tier, one ask for data you cannot pull (R-SKIP), one ask for a locked fact you cannot find (R-FACTS), and the gate. Nothing else.

## Apify research

The keyword check, competitor brief, comments and transcripts run through Apify unless intake says drop. Run the pulls yourself with `call-actor`. Never ask Brody to supply data the pulls can get, except under R-SKIP when Apify is dropped or not connected. The cap is `limits.apify_cap_usd` in config and covers Apify only.

**Setup.** Read `apify-cost-table.json` and `apify-runs.json` from the series Drive folder (ID 15R_XV4kH2flgqwENGfhM6olODkB4eCiI), read only, and copy them into the workspace. A missing cost table blocks every run until Brody supplies it. The Drive table uses `actor_id`, `events` and `worst_case_usd`, but `scripts/apify_budget.py` reads `actor`, `unit_price_usd`, `units` and `date_read`. Convert in code before the first run: `actor_id` to `actor`, the per-result event price to `unit_price_usd`, `units` from the row's `estimate_basis`, `price_read_on` to `date_read`. Recompute the total and compare it with the table's `total_worst_case_usd`. Refresh any row older than `apify_cost_row_max_age_days` from the actor's details page before using it. An actor that is not in the table is not run.

**The five pulls, in spend order** (the least valuable data hits the cap first):

| Key | Actor | Limits sent |
|---|---|---|
| keyword_fanout | `aitorsm/keyword-fanout` | 3 seeds, Google and YouTube, US, quick, 25 per seed, People Also Ask on, volume off |
| google_trends | `apify/google-trends-scraper` | 3 terms, 5 years, US, 10 items |
| youtube_search | `streamers/youtube-scraper` | 3 queries, 25 each, shorts and streams 0, transcripts none, AI add-ons off |
| youtube_comments | `solidcode/youtube-comments-scraper` | 8 video URLs (top performers and flops), top comments, replies off, 100 each |
| youtube_transcripts | `johnvc/YoutubeTranscripts` | the 5 picked URLs, English, metadata on, extended metadata off |

**Run mechanics.** Before each run: `apify_budget.py plan --table T --log L --actor ID`, and refuse the run if it says REFUSE. Send the row's limits and `callOptions.maxTotalChargeUsd` set to the plan's figure (the smaller of the budget left, rounded down to the cent, and two times the row's worst case). The charge stop limits billing, not work, so the limits are always sent too. `maxTotalChargeUsd` applies to pay-per-event actors only. For a pay-per-result actor send `callOptions.maxItems` instead, and a row whose pricing model does not match the option sent is not run. After each run: `record`, then `fill` with the billed `usageTotalUsd`. No run may still be an estimate at the gate. If the cap or a charge stop cuts a pull short, report what was and was not pulled, treat it as a thin sample under R-SKIP, and never ask to exceed the cap.

**How each pull feeds the script.**

- **Keyword check (pulls 1 and 2).** Seeds are "[A] vs [B]", "[A] alternative" and "[A] pricing". They are different buyer intents, so say which one the evidence favors and why. Output the primary keyword (validated or assumed), secondaries and the angle, and feed them into the hook, the spoken search phrase, the provisional title and description, and the LOCKED_FACTS keyword fields. The Trends terms are the same three phrases.
- **Competitor Pattern Brief (pull 3).** Use the same three phrases as YouTube queries. Rank by engagement ratio and view-to-sub ratio, not raw views, normalized for video age. Require a minimum sample and say plainly if it is too thin. A true overperformer is about 3x its own channel's baseline. For videos below baseline, tag the likely cause (hook, title or thumbnail, length, verdict position, topic). Fill DOMINANT TITLE PATTERN, DOMINANT HOOK TYPE, PAYOFF TIMING, RETENTION DEVICES OBSERVED, KEYWORDS CONFIRMED, UNANSWERED VIEWER OBJECTIONS, PATTERNS TO AVOID, CATEGORY ORDER OBSERVED and THE GAP THIS SCRIPT SHOULD EXPLOIT. The brief must change the script: the hook exploits the gap, each unanswered objection gets a scene with `addresses_objection`, confirmed keywords go into LOCKED_FACTS, a retention device every competitor uses at the same beat gets varied, and the category order differs from the variation log and the observed pattern unless the data clearly favors it. If competitors bury their segment answer past about half the runtime, the segment map is the edge. If one gives its full verdict early, tighten the held-reveal tease.
- **Comments (pull 4).** Hearted and pinned comments outrank generic top comments. Combine them with review sites and Reddit into the Pain-Point Map, ranked by frequency, with 1 or 2 verbatim phrases each.
- **Transcripts (pull 5, last).** From the ranked data pick five videos: two or three true overperformers, one closest to the target runtime, and one flop on a similar comparison (a different-angle pick if none exists). List each with title, channel, URL and a one-line reason, then pull the transcripts yourself without stopping to ask. Extract patterns only, never wording: first-30-second structure and hook type, verdict position, category order, pacing, what happens near minute 6, CTA placement, and why the flop lost. Transcript wording never reaches a deliverable.

Report Apify spend by actor at the gate and in LOCKED_FACTS. Firecrawl credits and RunPod time are reported separately, not capped.

## Critical rules (never bend; lint blocks delivery)

- **R-HONESTY** — Judge both products situationally with real numbers and named limits. Each product clearly wins at least one segment. Never invent a con or imply a secret that does not exist. Unverified claims are fixed or flagged `[VERIFY AT PUBLISH]`. Per-product tier (research / demo / hands-on) limits first-person language.
- **R-DISC** — Fixed disclosure strings from `config.json`, on screen only (opening seconds, final seconds, and every CTA button for the configured CTA duration) plus a low-opacity corner tag. Never reworded.
- **R-NOSPOKEN** — Disclosure and corner tag never appear in narration, narration file, or captions. `[BEAT]` cues never appear in the narration file either. No subscribe cue in the hook.
- **R-NOFAKE** — No generated visual, B-roll brief or stat card that looks like a named product's UI, pricing page or logo, or copies a vendor's layout. Real product visuals are `ASSET-SHOT`, `ASSET-CLIP` or `ASSET-BRAND` shots only. Generated motion is abstract or generic, and no text is rendered inside a generated image.
- **R-AIFLAG** — Three AI flags are computed once into the manifest by code. Never set by hand anywhere else. Synthetic-voice disclosure is always on, because the voice is a clone.
- **R-SPEC** — One Remotion render per format, never one master: 16:9 at 1920x1080 (long-form and LinkedIn) and 9:16 at 1080x1920 (Shorts, TikTok, Reels). H.264 MP4 at 25 fps, matching the Ditto avatar clip. Wan output size and fps come from config and are conformed to 25.
- **R-SHOTS** — Every shot is one of the pipeline's seven tags (`GEN-VIDEO`, `GEN-STILL`, `B-ROLL`, `STAT`, `ASSET-SHOT`, `ASSET-CLIP`, `ASSET-BRAND`), in whole seconds. Non-still shots run 2-5 s (`B-ROLL` 2-8 s); `GEN-STILL` and `STAT` run 9-16 s and sit under one or more scenes with `span`. `B-ROLL` stays within `broll_max_share` of runtime, and each B-roll shot carries a short Means/Picture sentence plus a 1-2 noun `search` field (see references/script-rules.md R-BROLL), so plan stills, stat cards, Wan clips and real captures to fill the rest. Stat cards carry Value, Label and Source. A real-capture `ASSET-SHOT` may take `product: "ab"` to show both products' pages side by side, product A on the left. Stills are mood backdrops, never fact carriers (R-STILL): each states a purpose and a Ken Burns direction, stays within `still_cap`, and at least a quarter sit in pricing, feature, switching-cost or reveal scenes. The exported `script.md` must pass the pipeline's `parse_script.py`.
- **R-GENLIMIT** — Wan clips only in the scenes and fill order `config.json` names (`gen_fill_order`), up to `gen_video_cap`. Never on a product, price, screen, face, verdict or the reveal scene itself.
- **R-COMPARE** — Statics sell products, abstract pictures do not. Comparison cards carry the visual weight of every video: side by side, product A on the left, real text built in Remotion and never generated. One card for each kind in `compare_kinds` (reviews, pricing, monthly_cost, features, pros_cons, pain_points), at least `compare_cards_min` cards in all, filling at least `compare_share_min` of the runtime. A card is a `STAT` shot whose `stat` also holds `compare: {kind, a, b, rows}`, with 2 to `compare_rows_max` rows of `label`, `a` and `b`, built from the same locked facts and dated sources as the narration. `pros_cons` rows pair each product's own pro or con; `pain_points` rows take the viewer's pain phrase from the Pain-Point Map as the label (close to verbatim, with where it was heard) and show how each product handles it. Plan them while writing the scenes: the review-sites scene, the sticker-price scene, add-on and monthly-bill scenes, every segment's feature and pros-and-cons beat, each pain the audience raised, and the held-reveal bill. Repeat a kind when a scene has its own numbers. When the time budget is tight, cut B-roll, stills or Wan clips, never a card. Lint blocks a video without them.
- **R-AVATAR** — Ditto avatar only (see Layouts). Blocks 1 (hook and stakes), 2 (held reveal) and 3 (close, first verdict to end screen) total between `avatar_min_s` and `avatar_max_s`. Cut to a base visual every 8-10 s inside a block. Direct-to-camera wording only inside blocks. The avatar is never on a full-screen shot, never on the end screen and never on screen while a number is spoken; each spoken number gets its own full-screen shot, and narration keeps playing across the cut. If runtime passes `runtime_max_s` and you choose to trim, shorten Block 3 first (the ceiling is rough, so this is a choice, not a block).
- **R-CLOSE** — Two windows. The end-screen window starts at the one scene marked `end_screen_start`, `end_screen_lead_s` before the end; left and right thirds stay quiet for YouTube end-screen elements from there. The final scene is section `end_screen`, runs at least `end_screen_min_s`, and is a Remotion composition built from `GEN-VIDEO` or `B-ROLL` shots. Peak in the final second, focal point centered. One spoken line within `closing_line_max_words`, one ask, echoing the hook.
- **R-FACTS** — Every field in `config.json` `intake_required_fields` is filled in `locked_facts` with no TBD, exactly 3 audience segments, and every rating names its review site. The teaser and packaging skills add no facts of their own, so this blocks the gate.

Everything else (length, voice, rhythm, captures, B-roll briefs, CTA wording, GoHighLevel first whenever it is one of the two products) is a standard rule; `lint.py` reports it and you fix it before the gate. The full wording is in `references/script-rules.md`.

## Layouts (match the pipeline's `vs-video-pipeline` skill)

- **Avatar:** Ditto cutout from a 720x540 render, shown only in the three scripted blocks.
- **16:9 (1920x1080):** avatar 384x288, flush with the bottom edge, 40 px from the left. Captions start at x=464, text bottom edge 70 px up, 54 px, seven words per group.
- **9:16 (1080x1920):** avatar 216x162, 40 px from the left, top edge at 380 px. Captions start at y=640, 66 px, four words per group, 65 px side margins. Disclosure sits 700 px from the bottom, above the bottom 35%.
- **Captions:** full transcript, word-timed, current word highlighted. Whisper runs on the final narration audio. Words need a real space between them so they can wrap.
- **Comparison card (every kind):** full-screen STAT card on a bright background, product A column on the left and product B on the right, one row revealed at a time across the card, source line on screen throughout. In 9:16 each row stacks (label above, A and B side by side) inside the platform safe zones below.
- **Base layer:** whatever sits behind the avatar and captions keeps the avatar corner and the caption zone free of faces, text, logos and key action.
- **Platform safe zones (research 2026-11-18, strictest rule):** for 9:16, nothing that must be seen goes in the top 380 px, below y=1250 (the bottom 35%), or the outer 65 px on the right. Meta publishes ad percentages; TikTok, Shorts and LinkedIn publish no official pixel margins, so this rule covers them. Check TikTok's Ad Preview Tool before the first upload.

## Defaults

All defaults, limits, banned phrases, disclosure strings, CTA wording, pronunciation map and stack numbers live in `config.json`. A workspace `config.local.json` overrides it. Never restate those numbers in prose; read them from config. The target runtime, word band and wpm (with the date it was measured) come from there too. The runtime floor (`runtime_min_s`) is the only hard line: a video under it is blocked. The ceiling (`runtime_max_s`) and the target are rough: running over the ceiling is a lint warning to weigh, never a reason to cut a verdict, the held reveal or a comparison card. The wpm is the rate measured on the real cloned voice, paragraph pauses included, not an estimate. After every full voicing, re-measure it and update config, because an optimistic rate lets an over-length script pass the length check. Items still unset are listed under `unset_items`; list them in the final message, do not guess them.

Style direction for generated clips and stills is `visual_style` in config: bright, high contrast, electric blue lead color, one clear focal point. Avoid dark green and dark moody looks.

## Stack

Remotion renders on a RunPod CPU pod through `vs-video-pipeline` (about $0.10 per full render; free under the Free License for individuals and for-profit organisations of up to 3 people, a paid Company License is required at 4+ people). Chatterbox cloned voice. Ditto avatar, FLUX.1-schnell stills and Wan 2.2 TI2V-5B clips on RunPod, using only the verified cards named in config (RTX 4090 and A40). Pixabay B-roll (verified; Pexels untested). Whisper captions. FFmpeg. Apify research. Recurring costs are RunPod GPU and CPU pod time and the 150 GB network volume (about $10.50 a month). Versions, sizes and licenses are in `config.json` `stack` and `licenses`.

Packages live in Cloudflare R2, bucket `workflowdynamic`, folder `inputs/[slug]/`; the workspace reaches it through the Cloudflare connection (`mcp__cloudflare__execute`: list, read, write and delete objects), never with boto3, aws or rclone, because the workspace `AWS_*` values are placeholders. Large files go through the `wd-r2-gateway` Worker, whose address and password Brody supplies and which are never written down. This skill writes scripts, not renders; running the pods and renders belongs to `vs-video-pipeline` and `media-pipeline-runner`.

## Scripts

- `scripts/build_exports.py` — source file to every export.
- `scripts/lint.py` — all checks, exit 0 pass, 1 critical failure, 2 standard failure only.
- `scripts/retime.py` — Whisper word timestamps of the real voice track to `timing.json`, so exports and lint use real timing instead of the wpm estimate.
- `scripts/apify_budget.py` — per-script Apify cap arithmetic (cap in config).
- `tests/` — fixture generator and negative tests (`python3 -I tests/test_lint.py`).

## Honesty about what is measured

State the runtime source in the result: "wpm estimate" until `retime.py` has run on the real audio. The scene floors can make the manifest runtime longer than the real audio, so state both figures when they differ. Report unconfirmed items (Wan output size, pronunciations, official Shorts and LinkedIn margins, the Ditto license) as open, not as done. If the pipeline parser was not available to check `script.md`, say so.