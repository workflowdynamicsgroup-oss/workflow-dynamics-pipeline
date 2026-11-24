"""Fetch a narration text from R2 onto the pod and prepare it for Chatterbox.
Usage: python3 scripts/fetch_text.py KEY DEST [EXPECT_MD5]
Checks the md5 when given. Turns each [BEAT] marker into a paragraph break
(the R2 original is not changed). Needs boto3 and the R2_* env secrets.
"""
import hashlib, os, re, sys
import boto3

key, dest = sys.argv[1], sys.argv[2]
expect = sys.argv[3] if len(sys.argv) > 3 else None
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)
raw = s3.get_object(Bucket="workflowdynamic", Key=key)["Body"].read()
md5 = hashlib.md5(raw).hexdigest()
print(f"FETCH_TEXT key={key} bytes={len(raw)} md5={md5}", flush=True)
if expect and md5 != expect:
    print(f"FETCH_TEXT_MD5_MISMATCH expected={expect}", flush=True)
    sys.exit(2)
text = raw.decode("utf-8")
text = re.sub(r"[ \t]*\[BEAT\][ \t]*", "\n\n", text)
os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
open(dest, "w", encoding="utf-8").write(text.strip() + "\n")
pieces = [p for p in text.split("\n\n") if p.strip()]
print(f"FETCH_TEXT_OK words={len(text.split())} pieces={len(pieces)} dest={dest}", flush=True)
