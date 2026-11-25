# Phases 5-7: verification, gate, exports

## Phase 5: verification

1. `python3 scripts/lint.py SOURCE --out OUT --stage pre` (add `--workspace DIR` if a workspace holds the variation log or Apify run log). Exit 0 = pass; 1 = critical failure (blocks delivery); 2 = standard failure(s) only. Fix every failure by editing the source file, then rerun. Warnings are reported at the gate, not blocked.
2. Manual checks (code cannot do these):
   - Narration file: numbers in words, every likely-mangled product name has a pronunciation entry.
   - Rhythm, hook and close feel, held-reveal timing, variation choices differ from the last log entry.
   - R-NOFAKE (manual review): no still, clip, B-roll brief or backdrop resembles a named product's interface, logo or pricing page. Review stills and clips as a contact sheet per batch. Also check for banned props (R-NOPROPS: coins, clocks, piggy banks, money) and faces that look wrong.
   - R-GENLIMIT: Wan clips only in the named scenes (hook, ending, up to two call-to-action backdrops), none showing text or a product UI.
   - R-HONESTY: numbers identical across scenes and on screen; tier-gated features carry tier and price; first-person claims map to listed components; both products win at least one segment; no scene contradicts the recommendation.
   - Conversion beats present: reveal totals, ratings with counts, risk reversal, cost of inaction, objection beat, use-my-link-first. Offers and guarantees match the VS page.
   - R-SKIP / R-APIFY-CAP: each item ran or carries a "confirm skip"; keyword labeled validated or assumed; the brief visibly changed the script; spend at or under cap by actor.
   - R-FACTS: every `locked_facts` field is filled from evidence, with ratings naming their source.
   - Asset licenses recorded (config `licenses`; Ditto is unset until its license is checked).
3. Confirm the script file parses the way the pipeline reads it. If `pipeline/parse_script.py` is available, run `python3 parse_script.py SCRIPT.md OUT.json` on the exported `script.md`; it must print `SCRIPT_OK`. If it is not available, say so in the final message.

## Phase 6: gate

`python3 scripts/build_exports.py SOURCE --out OUT --gate` writes `gate-preview.md` from the source file: badges, hook A and B, scene preview, held-reveal number and why, open flags, keyword/competitor findings, Apify spend, AI flags and paid-promo toggle, variation entry, totals (words, runtime and its source, longest shot, lint result, shots by tag, B-roll share, stills used of cap, clips used of cap, avatar minutes). Show it and ask: pick Hook A or B and give changes to hooks, verdicts or pacing. With `gate_mode: approve` stop and wait. With `gate_mode: auto` say at the top of the result that Hook A was used without approval.

## Phase 7: exports

1. Apply the reply to the source file. Rerun lint.
2. Once the real voice track exists: Whisper word timestamps, then `python3 scripts/retime.py SOURCE WHISPER.json --out timing.json`. If it lists scenes whose shots no longer fit, add or remove `B-ROLL` shots in the source and rerun. Then build and lint with `--timing timing.json`; the runtime source changes from "wpm estimate" to "whisper".
3. `python3 scripts/build_exports.py SOURCE --out OUT [--timing timing.json] [--workspace DIR] --append-variation-log`, then `python3 scripts/lint.py SOURCE --out OUT --stage post`. Post stage checks the written files and stamps `LINT RESULT` in locked-facts.
4. Files written, every one prefixed `[slug]-`: `script.md`, `narration.txt`, `pronunciation-notes.txt`, `scene-manifest.json`, `generation-prompts.md`, `asset-checklist.md`, `upload-checklist.md`, `locked-facts.md`, plus the lint report. Save them to `inputs/[slug]/` in the `workflowdynamic` R2 bucket through the Cloudflare connection and keep the source file and variation log in the same folder. Overwrite any existing file of the same name without asking (Brody's standing decision); say in the result which files were replaced. The teasers and packaging skills read `[slug]-locked-facts.md` and `[slug]-script.md` from that folder.
5. Open `[VERIFY AT PUBLISH]`, `[VERIFY AT BUILD]` flags live only in the script, asset checklist and upload checklist, never in narration, pronunciation notes, manifest, prompt files or captions. Restate them in the message that presents the files.
6. Output the locked-facts block verbatim in chat. The generator writes every field it can compute; fields that need research (pricing, ratings, segments) come from the source file's `locked_facts` and `research_summary`.
