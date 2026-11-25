#!/usr/bin/env python3
"""Apify budget helpers for the $5.00-per-script hard cap (R-APIFY-CAP).

The main model enforces the cap. This script does the arithmetic so it never
depends on mental math.

  apify_budget.py worst-case  --table apify-cost-table.json
  apify_budget.py plan        --table T --log L --actor ID [--units N | --limits-json '{"k":v}']
  apify_budget.py record      --table T --log L --actor ID --est 0.42 --max-charge 4.58 [--reported 0.40]

Table rows (apify-cost-table.json):
  {"rows": [{"purpose": "...", "actor": "owner/name", "unit_price_usd": 0.0025,
             "unit": "per result", "limits": {"maxItems": 100}, "units": 100,
             "date_read": "2026-10-25"}],
   "worst_case_usd": null, "worst_case_checked": null}

A row with a blank unit_price_usd is not runnable. Never guess a price.
Cost of a run = unit_price_usd x units, where units is what the run will actually
be sent (items, results, minutes). Counted at list price even if plan credits cover it.

Log (apify-run-log.json), one object per video:
  {"video": "slug", "cap_usd": 5.0, "runs": [{"actor": "...", "est_usd": 0.4,
   "max_total_charge_usd": 4.6, "tally_before_usd": 0.0, "reported_usd": null}]}
"""
import argparse
import datetime
import json
import math
import sys
from pathlib import Path

CAP = 5.00


def load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(p, data):
    Path(p).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def row_cost(row):
    price = row.get("unit_price_usd")
    if price in (None, ""):
        return None
    return float(price) * float(row.get("units", 1))


def worst_case(table):
    total, blank = 0.0, []
    for r in table.get("rows", []):
        cost = row_cost(r)
        if cost is None:
            blank.append(r.get("actor"))
        else:
            total += cost
    return round(total, 4), blank


def stale_rows(table, max_age_days=30, today=None):
    today = today or datetime.date.today()
    stale = []
    for r in table.get("rows", []):
        d = r.get("date_read")
        if not d:
            stale.append(r.get("actor"))
            continue
        try:
            age = (today - datetime.date.fromisoformat(d)).days
        except ValueError:
            stale.append(r.get("actor"))
            continue
        if age > max_age_days:
            stale.append(r.get("actor"))
    return stale


def tally(log):
    total = 0.0
    for r in log.get("runs", []):
        total += float(r["reported_usd"]) if r.get("reported_usd") is not None else float(r.get("est_usd", 0))
    return round(total, 4)


def max_charge_for_next(log, cap=CAP):
    """Hard per-run stop to send as maxTotalChargeUsd, rounded down to the cent."""
    return math.floor(max(0.0, cap - tally(log)) * 100 + 1e-9) / 100


def check_run_log(log, cap=CAP):
    """Return a list of problems. Empty means the log respects the cap."""
    problems = []
    running = 0.0
    for i, r in enumerate(log.get("runs", []), 1):
        before = r.get("tally_before_usd")
        allowed = math.floor(max(0.0, cap - (before if before is not None else running)) * 100 + 1e-9) / 100
        mc = r.get("max_total_charge_usd")
        if mc is None:
            problems.append(f"run {i} ({r.get('actor')}): no max_total_charge_usd recorded")
        elif float(mc) > allowed + 0.0001:
            problems.append(f"run {i} ({r.get('actor')}): max_total_charge_usd {mc} exceeds remaining budget {allowed:.2f}")
        spent = float(r["reported_usd"]) if r.get("reported_usd") is not None else float(r.get("est_usd", 0))
        running += spent
    if running > cap + 0.0001:
        problems.append(f"total {running:.2f} exceeds the ${cap:.2f} cap")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["worst-case", "plan", "record", "fill"])
    ap.add_argument("--table")
    ap.add_argument("--log")
    ap.add_argument("--actor")
    ap.add_argument("--units", type=float)
    ap.add_argument("--est", type=float)
    ap.add_argument("--max-charge", type=float)
    ap.add_argument("--reported", type=float)
    ap.add_argument("--video", default="")
    ap.add_argument("--index", type=int)
    a = ap.parse_args()

    if a.cmd == "worst-case":
        table = load(a.table, {"rows": []})
        total, blank = worst_case(table)
        stale = stale_rows(table)
        print(f"worst-case total: ${total:.2f} (rows with blank price, not runnable: {blank or 'none'})")
        print(f"stale or undated rows (refresh before use): {stale or 'none'}")
        stored = table.get("worst_case_usd")
        if stored is None or abs(float(stored) - total) > 0.005:
            print("[VERIFY AT BUILD] stored worst_case_usd does not match the rows; updating it now")
            table["worst_case_usd"] = total
            table["worst_case_checked"] = datetime.date.today().isoformat()
            save(a.table, table)
        return 0

    log = load(a.log, {"video": a.video, "cap_usd": CAP, "runs": []})
    if a.cmd == "plan":
        table = load(a.table, {"rows": []})
        row = next((r for r in table["rows"] if r.get("actor") == a.actor), None)
        if row is None:
            print(f"REFUSE: {a.actor} is not in the cost table. Add its row from the actor's details page first.")
            return 2
        price = row.get("unit_price_usd")
        if price in (None, ""):
            print(f"REFUSE: {a.actor} has a blank price. Not runnable.")
            return 2
        units = a.units if a.units is not None else float(row.get("units", 1))
        est = float(price) * units
        spent = tally(log)
        left = CAP - spent
        stop = max_charge_for_next(log)
        verdict = "OK" if est <= left + 1e-9 else "REFUSE (would pass the cap)"
        print(json.dumps({"verdict": verdict, "est_usd": round(est, 4), "tally_usd": spent,
                          "remaining_usd": round(left, 4), "maxTotalChargeUsd": stop}))
        return 0 if verdict == "OK" else 2

    if a.cmd == "fill":
        runs = log.get("runs", [])
        if a.index is None or not (0 <= a.index < len(runs)) or a.reported is None:
            print("fill needs --index (0-based run) and --reported (billed USD from the run's usageTotalUsd)")
            return 2
        runs[a.index]["reported_usd"] = a.reported
        save(a.log, log)
        missing = [i for i, r in enumerate(runs) if r.get("reported_usd") is None]
        print(f"filled run {a.index}. tally now ${tally(log):.4f} of ${CAP:.2f}; runs still estimated: {missing}")
        return 0

    if a.cmd == "record":
        before = tally(log)
        log.setdefault("runs", []).append({
            "actor": a.actor, "est_usd": a.est, "max_total_charge_usd": a.max_charge,
            "tally_before_usd": before, "reported_usd": a.reported,
        })
        save(a.log, log)
        print(f"recorded. tally now ${tally(log):.2f} of ${CAP:.2f}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
