#!/usr/bin/env python3
# Fetch stock B-roll from Pixabay, check each clip with ffprobe, write a source and licence manifest.
# Usage: fetch_broll.py OUTDIR TERM [TERM ...]
# Env: PIXABAY_API_KEY (pod secret, required); RENDITION (default medium = 1080p; large is often 4K or empty);
#      MIN_WIDTH (default 1280), MIN_SECONDS (default 4); PIXABAY_API (test override of the API URL).
# Output lines: BROLL_PREFLIGHT_OK, BROLL_CLIP (short), BROLL_NO_CLIP, BROLL_DONE clips=N missing=M.
# Exit codes: 0 all terms got a clip, 1 some term got none, 2 preflight failed (key or network), nothing downloaded.
import json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

API = os.environ.get("PIXABAY_API", "https://pixabay.com/api/videos/")
LICENSE = "Pixabay Content License"
LICENSE_URL = "https://pixabay.com/service/license-summary/"
# From the licence summary page read 2026-11-19; the full Terms of Service is the binding text (AI training, Content ID and YouTube claims are not covered by the summary).
LICENSE_NOTES = "Commercial use and modification allowed, no attribution required. Not allowed: standalone resale, recognizable brands or logos used commercially, misleading or illegal use. Third-party consent is your responsibility."
UA = "Mozilla/5.0 (X11; Linux x86_64) workflow-dynamics-broll/1.0"
RENDITION = os.environ.get("RENDITION", "medium")
MIN_WIDTH = int(os.environ.get("MIN_WIDTH", "1280"))
MIN_SECONDS = float(os.environ.get("MIN_SECONDS", "4"))
SLEEP = float(os.environ.get("RETRY_SLEEP", "5"))
PER_TERM = int(os.environ.get("PER_TERM", "1"))

def order(first):
    return [first] + [n for n in ("medium", "large", "small", "tiny") if n != first]

def pick(hit, first=RENDITION):
    """First rendition with a real url, preferring `first` (large can have an empty url and size 0)."""
    for name in order(first):
        r = (hit.get("videos") or {}).get(name) or {}
        if r.get("url"):
            return name, r
    return None

def http(url, tries=4):
    """GET with User-Agent, timeout and retries on 429, 5xx and network errors. Returns the open response."""
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(SLEEP * (i + 1) * (4 if e.code == 429 else 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i == tries - 1:
                raise
            time.sleep(SLEEP * (i + 1))

def search(key, term, per_page=10):
    q = urllib.parse.urlencode({"key": key, "q": term, "per_page": per_page, "safesearch": "true",
                                "min_width": MIN_WIDTH, "order": "popular"})
    with http(f"{API}?{q}") as resp:
        return json.load(resp).get("hits", [])

def download(url, path):
    with http(url) as resp, open(path, "wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)

def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    w, h = s["width"], s["height"]
    return {"width": w, "height": h, "orientation": "landscape" if w >= h else "portrait",
            "fps": round(int(num) / int(den), 2), "duration_s": round(float(j["format"]["duration"]), 2)}

def preflight(key):
    try:
        hits = search(key, "nature", per_page=3)
    except urllib.error.HTTPError as e:
        print(f"BROLL_PREFLIGHT_FAIL http={e.code} body={e.read()[:200]!r}", flush=True)
        return False
    except Exception as e:
        print(f"BROLL_PREFLIGHT_FAIL {type(e).__name__}: {e}", flush=True)
        return False
    if not hits:
        print("BROLL_PREFLIGHT_FAIL api answered but returned no hits", flush=True)
        return False
    print(f"BROLL_PREFLIGHT_OK hits={len(hits)}", flush=True)
    return True

def main():
    outdir, terms = sys.argv[1], sys.argv[2:]
    key = os.environ.get("PIXABAY_API_KEY", "")
    if not key:
        print("BROLL_PREFLIGHT_FAIL PIXABAY_API_KEY is empty", flush=True)
        sys.exit(2)
    if not preflight(key):
        sys.exit(2)
    os.makedirs(outdir, exist_ok=True)
    manifest, bad, seen = [], 0, set()
    for term in terms:
        found = 0
        try:
            hits = search(key, term)
        except Exception as e:
            print(f"BROLL_SEARCH_FAIL term={term!r} {type(e).__name__}: {e}", flush=True)
            hits = []
        for hit in hits:
            if hit["id"] in seen:
                continue
            p = pick(hit)
            if not p:
                continue
            size, r = p
            path = os.path.join(outdir, f"pixabay_{hit['id']}.mp4")
            try:
                download(r["url"], path)
                info = probe(path)
                if info["width"] < MIN_WIDTH or info["duration_s"] < MIN_SECONDS:
                    raise ValueError(f"too small or short: {info}")
            except Exception as e:
                print(f"BROLL_SKIP id={hit['id']} {type(e).__name__}: {str(e)[:120]}", flush=True)
                if os.path.exists(path):
                    os.remove(path)
                continue
            seen.add(hit["id"])
            got = {"term": term, "source": "pixabay", "id": hit["id"], "page_url": hit.get("pageURL"),
                   "author": hit.get("user"), "rendition": size, "file": os.path.basename(path),
                   "bytes": os.path.getsize(path), "license": LICENSE, "license_url": LICENSE_URL, "license_notes": LICENSE_NOTES,
                   "needs_visual_review": True,
                   "downloaded": time.strftime("%Y-%m-%d"), **info}
            manifest.append(got)
            print(f"BROLL_CLIP id={got['id']} {got['width']}x{got['height']} {got['fps']}fps "
                  f"{got['duration_s']}s {got['bytes']//1024}KB author={got['author']} term={term!r}", flush=True)
            found += 1
            if found >= PER_TERM:
                break
        if not found:
            bad += 1
            print(f"BROLL_NO_CLIP term={term!r}", flush=True)
    with open(os.path.join(outdir, "broll_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"BROLL_DONE clips={len(manifest)} missing={bad}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
