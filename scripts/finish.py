#!/usr/bin/env python3
# End-of-run: print a summary and upload the run log and outputs to R2 (bucket workflowdynamic).
# Usage: finish.py RUN_NAME EXIT_CODE [OUTPUT_FILE ...]
# Needs env R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT. Upload failure is reported, never hidden.
import os, sys, pathlib
run, rc, outs = sys.argv[1], sys.argv[2], sys.argv[3:]
log = pathlib.Path(os.environ.get("LOG_DIR", f"/workspace-global/logs/{run}")) / "run.log"
lines = log.read_text(errors="replace").splitlines() if log.exists() else []
marks = ("CODE_OK", "SETUP_DONE", "PREFLIGHT_OK", "CB_DONE", "DITTO_FILES_OK", "DITTO_DONE", "WAN_DONE", "CAPTIONS_DONE", "CAPTIONS_CHECK", "WATCHDOG", "FAIL", "MISSING", "MISMATCH", "ERROR", "Traceback")
print(f"===== SUMMARY run={run} exit={rc} log_lines={len(lines)} =====")
for l in lines:
    if any(m in l for m in marks): print("  " + l[:200])
print("----- last 40 log lines -----")
for l in lines[-40:]: print(l[:200])
status = "UPLOAD_SKIPPED"
try:
    import boto3
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
    sent = []
    if log.exists():
        s3.upload_file(str(log), "workflowdynamic", f"logs/{run}/run.log"); sent.append(f"logs/{run}/run.log")
    for o in outs:
        p = pathlib.Path(o)
        if p.exists() and p.stat().st_size > 0:
            s3.upload_file(str(p), "workflowdynamic", f"outputs/{run}/{p.name}"); sent.append(f"outputs/{run}/{p.name}")
    status = "UPLOAD_OK " + " ".join(sent)
    for key in sent:
        if key.startswith("outputs/"):
            url = s3.generate_presigned_url("get_object", Params={"Bucket": "workflowdynamic", "Key": key}, ExpiresIn=86400)
            print(f"DOWNLOAD_24H {key} {url}")
except Exception as e:
    status = f"UPLOAD_FAIL {type(e).__name__}: {e}"
print(status)
print(f"===== END SUMMARY run={run} =====")
