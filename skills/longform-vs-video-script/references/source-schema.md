# Source file schema: `{slug}-source.json`

The single source of truth. Write the script once here; every export is generated from it. `python3 tests/make_fixture.py OUT.json` writes a complete, lint-clean example (fictional products and numbers, never publish it). Copy its structure.

## Top level

`video`, `scenes`, `prompts`, `research_summary`, `manual_checks`, `locked_facts`.

## video

| Field | Meaning |
|---|---|
| product_a, product_b | Names. Product A is the left column on every card and the first product in the script. |
| link_a, link_b, vs_page_url | Affiliate and VS page links (placeholders allowed, listed in link_placeholders). |
| slug | Optional. Default `a-vs-b` slugified. |
| primary_keyword, primary_keyword_status | `validated` or `assumed`. |
| secondary_keywords | List. |
| tiers | `{"a": {"tier": "hands-on", "tested_components": [...]}, "b": {"tier": "research"}}`. |
| disclosure_type | unsponsored, sponsored or free_access. |
| avatar | `{"mode": "generated" | "footage" | "none"}`. |
| gen_video_cap | 0 to `gen_video_cap_max`. |
| wpm | Measured words per minute, else omit (default 182 from config). |
| segments | Exactly 3 segment names. |
| single_winner_reason | Required only if one product wins every segment. |
| render_composition | Remotion composition id (`Long16x9`). |
| style_families | Optional. One look shared by all stills. |
| variation | category_order, micro_authority_device, hook_device, hook_type, opener_device, visual_motif. |
| held_reveal | `{number, flips, segment}`. The number must not appear before the reveal. |
| hook_options | `A: {line, type}`, `B: {scene_lines, type}`. |
| packaging | titles (3), description_body, tags (5). |
| verify_flags | `[{tag, item, in_table}]`. |

## scenes (ordered list)

Required: `id`, `name`, `section`, `line`, `shots`. A scene that sits under a `span` from an earlier scene has an empty `shots` list. Optional: `on_screen_text` (list of `{text, at_s, dur_s}`; negative `at_s` counts from scene end), `chapter` (chapter title; at least 3, 10 s apart), `category`, `avatar_block` (1-3), `retention_beat`, `addresses_objection`, `names_cost_of_inaction`, `verdict_product` ("a" or "b"), `cta_button` (`{wording, at_s, dur_s}`), `end_screen_start`, `first_person` (`{product, component}` for hands-on claims).

Each shot has a `tag` and the fields that tag needs. Do not write shot times: code places whole-second windows on one continuous timeline.

| Tag | Fields |
|---|---|
| `GEN-VIDEO` | `role`, `prompt_id` (a key in `prompts.wan`) |
| `GEN-STILL` | `prompt_id` (a key in `prompts.flux`), optional `span` |
| `B-ROLL` | `text` (the "Means: ... Picture: ..." brief, 10-35 words), `search` (one or two plain nouns) |
| `STAT` | `stat: {value, label, source}`, optional `span`. A side-by-side comparison card also has `stat.compare: {kind, a, b, rows: [{label, a, b}]}`; `kind` is one of `config.json` `limits.compare_kinds` (reviews, pricing, monthly_cost, features, pros_cons, pain_points) and `a`/`b` are the two product names, product A first; for `pain_points` each row `label` is the viewer pain phrase and `a`/`b` say how each product handles it (R-COMPARE) |
| `ASSET-SHOT`, `ASSET-CLIP` | `product` ("a", "b", or "ab" for both side by side, A on the left), `detail` (the exact screen) |
| `ASSET-BRAND` | `product` |

Any shot may also carry `avatar: true` (inside a block only, per R-AVATAR).

## prompts

`flux`: id to `{text, ken_burns, style, purpose}`. `wan`: id to `{text}`. Ids are referenced by shots.

## locked_facts

Holds every field in `config.json` `intake_required_fields` (R-FACTS). Pricing and ratings carry a date and a named source. Also holds COMPETITOR BRIEF, PATTERNS TO AVOID and TRANSCRIPT BRIEF as plain text (`not run` if that research did not run). `build_exports.py` writes them into the locked-facts file with the other fields.

## Computed by code (never write by hand)

Word counts, scene and shot timestamps, narration text (numbers in words, pronunciations), pronunciation notes, AI flags, chapter list, capture counts, runtime, locked-facts fields, gate preview.
