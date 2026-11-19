#!/usr/bin/env python3
# Fetch stock B-roll from Pixabay, check each clip with ffprobe, write a source and licence manifest.
# Usage: fetch_broll.py OUTDIR TERM [TERM ...]      Env: PIXABAY_API_KEY (pod secret)
# Prints BROLL_CLIP lines and BROLL_DONE clips=N; exits 1 if any term gives no usable clip.
import json, os, subprocess, sys, time, urllib.parse, urllib.request

API = "https://pixabay.com/api/videos/"
LICENSE = "Pixabay Content License"
LICENSE_URL = "https://pixabay.com/service/license-summary/"

def pick(hit):
    """Choose the largest rendition of a hit; return (size_name, rendition) or None."""
    for name in ("large", "medium", "small", "tiny"):
        r = (hit.get("videos") or {}).get(name) or {}
        if r.get("url"):
            return name, r
    return None

def search(key, term):
    q = urllib.parse.urlencode({"key": key, "q": term, "per_page": 5, "safesearch": "true"})
    with urllib.request.urlopen(f"{API}?{q}", timeout=30) as resp:
        return json.load(resp).get("hits", [])

def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"width": s["width"], "height": s["height"], "fps": round(int(num) / int(den), 2),
            "duration_s": round(float(j["format"]["duration"]), 2)}

def main():
    outdir, terms = sys.argv[1], sys.argv[2:]
    key = os.environ["PIXABAY_API_KEY"]
    os.makedirs(outdir, exist_ok=True)
    manifest, bad = [], 0
    for term in terms:
        got = None
        for hit in search(key, term):
            p = pick(hit)
            if not p:
                continue
            size, r = p
            path = os.path.join(outdir, f"pixabay_{hit['id']}.mp4")
            urllib.request.urlretrieve(r["url"], path)
            info = probe(path)
            got = {"term": term, "source": "pixabay", "id": hit["id"], "page_url": hit.get("pageURL"),
                   "author": hit.get("user"), "rendition": size, "file": os.path.basename(path),
                   "bytes": os.path.getsize(path), "license": LICENSE, "license_url": LICENSE_URL,
                   "downloaded": time.strftime("%Y-%m-%d"), **info}
            break
        if got:
            manifest.append(got)
            print("BROLL_CLIP", json.dumps(got), flush=True)
        else:
            bad += 1
            print(f"BROLL_NO_CLIP term={term!r}", flush=True)
    with open(os.path.join(outdir, "broll_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"BROLL_DONE clips={len(manifest)} missing={bad}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
