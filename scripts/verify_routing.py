"""Prove the categorisation works: submit sample reports, check each one.

    python -m scripts.verify_routing                 # all samples, check routing
    python -m scripts.verify_routing --limit 4
    python -m scripts.verify_routing --create-only   # rules OFF: the "before"

For every report in data/samples.json it creates a real Freshdesk ticket
through the API (with no category), waits for the automation rules, then
compares type, group, priority and status with what app/categories.py
predicts. Exit code 1 if anything was routed wrongly.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from app import categories, config
from app.freshdesk import from_env

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--create-only", action="store_true",
                    help="just create the tickets (use with automations off)")
    args = ap.parse_args()

    if "@" not in config.DEMO_REQUESTER_EMAIL:
        print("Set DEMO_REQUESTER_EMAIL in .env first.")
        return 1

    fd = from_env()
    groups, statuses = fd.groups(), fd.statuses()
    samples = json.loads(SAMPLES.read_text())[: args.limit]

    header = f"{'#':>6}  {'subject':<44} {'type':<12} {'group':<13} {'priority':<9} {'status':<9} {'ms':>6}  result"
    print(header)
    print("-" * len(header))
    wrong, timings = 0, []
    for s in samples:
        started = time.perf_counter()
        created = fd.create_ticket(
            name="Verify Script", email=config.DEMO_REQUESTER_EMAIL,
            subject=s["subject"], description=s["description"],
            location=s["location"], tags=[config.DEMO_TAG, "verify"],
        )
        if args.create_only:
            print(f"{created['id']:>6}  {s['subject'][:44]:<44} created")
            continue
        t = fd.wait_for_routing(created["id"], config.ROUTING_TIMEOUT,
                                config.ROUTING_POLL)
        ms = (time.perf_counter() - started) * 1000
        timings.append(ms)

        actual = {
            "type": t.get("type"),
            "group": groups.get(t.get("group_id")),
            "priority": config.PRIORITY.get(t["priority"]),
            "status": statuses.get(t["status"]),
        }
        predicted = categories.classify(s["subject"], s["description"])
        expected = {
            "type": predicted.ticket_type,
            "group": predicted.group,
            "priority": predicted.priority,
            "status": "Assigned" if predicted.routed else "Open",
        }
        ok = actual == expected
        wrong += not ok
        print(f"{t['id']:>6}  {s['subject'][:44]:<44} {str(actual['type']):<12} "
              f"{str(actual['group']):<13} {str(actual['priority']):<9} "
              f"{str(actual['status']):<9} {ms:>6.0f}  {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"        expected {expected}")

    if args.create_only:
        return 0
    print("-" * len(header))
    print(f"{len(samples) - wrong}/{len(samples)} routed correctly · "
          f"mean {sum(timings) / len(timings):.0f} ms from submit to routed "
          f"· slowest {max(timings):.0f} ms")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
