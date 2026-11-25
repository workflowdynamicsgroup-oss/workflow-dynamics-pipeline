"""Fetch every file in a manifest from R2 (or from a local mirror in SIM mode) into the package folder.
Usage: python3 render/fetch_package.py MANIFEST.json PKG_DIR [EXTRA_PREFIX]
EXTRA_PREFIX (R2 folder) files named in extra.json inside the manifest list as {"dest","key"} too; there is no special case.
SIM_SRC=<dir> reads <dir>/<key> instead of R2. Sizes are summed from the real objects, never hard-coded.
Prints FETCH_OK files=N bytes=B, or FETCH_FAIL with the first missing key and exits 1.
"""
import json, os, sys, shutil
from concurrent.futures import ThreadPoolExecutor
man, pkg = json.load(open(sys.argv[1])), sys.argv[2]
sim = os.environ.get("SIM_SRC")
if not sim:
    import boto3
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
def get(item):
    dest = os.path.join(pkg, item["dest"]); os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        if sim: shutil.copyfile(os.path.join(sim, item["key"]), dest)
        else: s3.download_file("workflowdynamic", item["key"], dest)
        return item["key"], os.path.getsize(dest), None
    except Exception as e:
        return item["key"], 0, f"{type(e).__name__}: {e}"
with ThreadPoolExecutor(8) as ex: res = list(ex.map(get, man))
bad = [r for r in res if r[2] or r[1] == 0]
if bad:
    print(f"FETCH_FAIL {len(bad)} of {len(res)}: first {bad[0][0]} {bad[0][2]}"); sys.exit(1)
print(f"FETCH_OK files={len(res)} bytes={sum(r[1] for r in res)}")
