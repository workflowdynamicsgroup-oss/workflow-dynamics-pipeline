#!/usr/bin/env bash
# Pod self-delete through the RunPod API. Needs RUN_POD_API_KEY (pod secret) and RUNPOD_POD_ID (set by RunPod).
# Usage: bash scripts/self_delete.sh check      (first minute: confirm the pod can read its own record)
#        bash scripts/self_delete.sh terminate  (at the end of every run, success or failure)
set -uo pipefail
: "${RUN_POD_API_KEY:?missing RUN_POD_API_KEY}"
: "${RUNPOD_POD_ID:?missing RUNPOD_POD_ID}"
if [ "${1:-}" = check ]; then
  code=$(curl -s -o /tmp/self_check.json -w '%{http_code}' -H "Authorization: Bearer $RUN_POD_API_KEY" "https://api.runpod.io/v2/pods/$RUNPOD_POD_ID")
  echo "SELF_CHECK_HTTP $code"
  [ "$code" = 200 ]
  exit $?
fi
body=$(python3 -c 'import json, os; print(json.dumps({"query": "mutation($id: String!) { podTerminate(input: {podId: $id}) }", "variables": {"id": os.environ["RUNPOD_POD_ID"]}}))')
code=$(curl -s -o /tmp/self_term.json -w '%{http_code}' -X POST https://api.runpod.io/graphql -H 'Content-Type: application/json' -H "Authorization: Bearer $RUN_POD_API_KEY" -d "$body")
echo "SELF_DELETE_HTTP $code $(cat /tmp/self_term.json 2>/dev/null)"
[ "$code" = 200 ]
