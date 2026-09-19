import argparse
import sys
import time

from app.freshdesk import FreshdeskError, from_env

WALK = ["In Progress", "Resolved", "Closed"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticket_id", type=int)
    ap.add_argument("--to", default="In Progress")
    ap.add_argument("--walk", action="store_true")
    ap.add_argument("--pause", type=float, default=4.0)
    args = ap.parse_args()

    fd = from_env()
    targets = WALK if args.walk else [args.to]
    for i, name in enumerate(targets):
        try:
            fd.update_ticket(args.ticket_id, status=fd.status_id(name))
        except (KeyError, FreshdeskError) as exc:
            print(f"#{args.ticket_id}: could not set {name}: {exc}")
            return 1
        print(f"#{args.ticket_id} -> {name}")
        if i < len(targets) - 1:
            time.sleep(args.pause)
    return 0


if __name__ == "__main__":
    sys.exit(main())
