import sys

from app import config
from app.freshdesk import FreshdeskError, field_choices, from_env, parse_statuses


def mark(ok: bool, text: str) -> bool:
    print(f"  {'OK ' if ok else 'XX '} {text}")
    return ok


def main() -> int:
    try:
        fd = from_env()
        me = fd.me()
    except (ValueError, FreshdeskError) as exc:
        print(f"Cannot talk to Freshdesk: {exc}")
        print("Check FRESHDESK_DOMAIN and FRESHDESK_API_KEY in .env")
        return 1
    print(f"Connected to {config.FRESHDESK_DOMAIN}.freshdesk.com as "
          f"{me['contact']['name']} <{me['contact']['email']}>\n")

    ok = True
    fields = fd.ticket_fields()

    print("Groups (Admin -> Team -> Groups)")
    have = set(fd.groups().values())
    for g in config.GROUPS:
        ok &= mark(g in have, g)

    print("\nTicket types (Admin -> Workflows -> Ticket Fields -> Type)")
    types = set(field_choices(fields, "ticket_type"))
    for t in config.TICKET_TYPES:
        ok &= mark(t in types, t)

    print("\nStatuses (Admin -> Workflows -> Ticket Fields -> Status)")
    statuses = {v.lower(): k for k, v in parse_statuses(fields).items()}
    for s in ["Open", *config.CUSTOM_STATUSES, "Resolved", "Closed"]:
        ok &= mark(s.lower() in statuses, f"{s} (id {statuses.get(s.lower(), '?')})")

    print("\nCustom field")
    names = {f["name"] for f in fields}
    ok &= mark(config.LOCATION_FIELD in names,
               f"{config.LOCATION_FIELD} (a single-line text field labelled Location)")

    print("\nLocal settings")
    ok &= mark(len(config.WEBHOOK_SECRET) >= 16 and config.WEBHOOK_SECRET != "change-me",
               "WEBHOOK_SECRET is set to something long")
    ok &= mark("@" in config.DEMO_REQUESTER_EMAIL, "DEMO_REQUESTER_EMAIL is set")

    print("\nReady." if ok else "\nFix the XX lines above, then run this again.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
