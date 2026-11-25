"""Caption words from the script, timed by Whisper (Whisper alone mishears: "comment" for "commit", "4 .8" for "4.8").
Usage: python3 render/align_captions.py SOURCE.json TIMING.json WHISPER_CAPTIONS.json OUT.json
Whisper tokens that are only punctuation or a contraction tail are merged into the previous word, then the Whisper
tokens and the script words (source lines in scene order, [BEAT] removed) are aligned with difflib on lowercase
letters and digits. Matched script words take Whisper's start and end; unmatched ones (for example GoHighLevel, which
Whisper hears as three words) are spread evenly between their neighbours. Prints the match count.
"""
import json, re, sys, difflib
src, timing, cap = (json.load(open(p)) for p in sys.argv[1:4])
t = timing["scenes"]
m = []
for w in cap:
    tx = w["word"]
    if m and (tx[0] in ".,;:!?%" or re.fullmatch(r"'\w+", tx)):
        m[-1]["word"] += tx; m[-1]["endMs"] = w["endMs"]
    else:
        m.append(dict(w))
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
scenes = sorted(src["scenes"], key=lambda s: t[str(s["id"])]["start"])
script = [w for s in scenes for w in re.sub(r"\[BEAT\]", "", s["line"]).split()]
sm = difflib.SequenceMatcher(None, [norm(w["word"]) for w in m], [norm(w) for w in script], autojunk=False)
n = len(script); start = [None] * n; end = [None] * n
for i, j, k in sm.get_matching_blocks():
    for x in range(k):
        start[j + x] = m[i + x]["startMs"]; end[j + x] = m[i + x]["endMs"]
matched = sum(s is not None for s in start)
i = 0
while i < n:
    if start[i] is not None: i += 1; continue
    j = i
    while j < n and start[j] is None: j += 1
    lo = end[i - 1] if i > 0 else 0
    hi = start[j] if j < n else lo + 300 * (j - i)
    for x in range(i, j):
        start[x] = int(lo + (hi - lo) / (j - i) * (x - i)); end[x] = int(lo + (hi - lo) / (j - i) * (x - i + 1))
    i = j
out = [{"word": script[x], "startMs": start[x], "endMs": max(end[x], start[x] + 50)} for x in range(n)]
for x in range(1, n):
    out[x]["startMs"] = max(out[x]["startMs"], out[x - 1]["startMs"])
json.dump(out, open(sys.argv[4], "w"), ensure_ascii=False)
print(f"ALIGN_OK script_words={n} whisper_tokens={len(m)} matched={matched}")
