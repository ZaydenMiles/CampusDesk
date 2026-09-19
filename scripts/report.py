from collections import Counter
from datetime import datetime, timezone
from statistics import median

from app import config
from app.freshdesk import from_env


def parse(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def table(title: str, counter: Counter) -> None:
    print(f"\n{title}")
    for key, n in counter.most_common():
        print(f"  {str(key):<16} {n:>4}  {'#' * n}")


def main() -> None:
    fd = from_env()
    groups, statuses = fd.groups(), fd.statuses()
    tickets = list(fd.list_tickets())
    now = datetime.now(timezone.utc)

    print(f"{len(tickets)} tickets in the last 30 days "
          f"({config.FRESHDESK_DOMAIN}.freshdesk.com)")
    table("By department", Counter(groups.get(t.get("group_id"), "Unassigned")
                                   for t in tickets))
    table("By status", Counter(statuses.get(t["status"], t["status"]) for t in tickets))
    table("By priority", Counter(config.PRIORITY[t["priority"]] for t in tickets))

    hours = []
    for t in tickets:
        resolved = parse((t.get("stats") or {}).get("resolved_at"))
        if resolved:
            hours.append((resolved - parse(t["created_at"])).total_seconds() / 3600)
    escalated = sum(1 for t in tickets if t.get("is_escalated"))
    overdue = sum(1 for t in tickets
                  if statuses.get(t["status"]) not in ("Resolved", "Closed")
                  and t.get("due_by") and parse(t["due_by"]) < now)
    unrouted = sum(1 for t in tickets if not t.get("group_id"))

    print("\nService levels")
    print(f"  resolved              {len(hours)}")
    if hours:
        print(f"  median time to resolve {median(hours):.1f} h")
    print(f"  escalated (SLA)       {escalated}")
    print(f"  open and overdue      {overdue}")
    print(f"  never routed          {unrouted}")


if __name__ == "__main__":
    main()
