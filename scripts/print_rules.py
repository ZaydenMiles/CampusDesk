"""Print the Freshdesk automation rules exactly as you should type them.

    python -m scripts.print_rules

Admin -> Workflows -> Automations -> Ticket Creation. Create the rules in
the order printed; the order matters (see app/categories.py).
"""
from app import categories as c


def block(title: str, lines: list[str]) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))
    for line in lines:
        print(line)


def main() -> None:
    print("Rule execution mode: 'Execute all matching rules'")
    for n, cat in enumerate(c.RULE_ORDER, start=1):
        block(f"Rule {n}: Route {cat.ticket_type}", [
            "CONDITION  Subject or Description  contains any of:",
            "           " + " | ".join(cat.keywords),
            f"ACTIONS    Set Type as {cat.ticket_type}",
            f"           Assign to Group {cat.group}",
            "           Set Status as Assigned",
        ])
    n = len(c.RULE_ORDER) + 1
    block(f"Rule {n}: Everything else -> Service Desk", [
        "CONDITION  Subject or Description  does not contain any of:",
        "           " + " | ".join(c.ALL_CATEGORY_KEYWORDS),
        f"ACTIONS    Set Type as {c.FALLBACK_TYPE}",
        f"           Assign to Group {c.FALLBACK_GROUP}",
        "           (status stays Open: a human triages it)",
    ])
    block(f"Rule {n + 1}: Urgent hazards", [
        "CONDITION  Subject or Description  contains any of:",
        "           " + " | ".join(c.URGENT_KEYWORDS),
        "ACTIONS    Set Priority as Urgent",
        "           Add Tag urgent-hazard",
    ])
    print(f"\n{len(c.ALL_CATEGORY_KEYWORDS)} category keywords, "
          f"{len(c.URGENT_KEYWORDS)} urgent keywords.")


if __name__ == "__main__":
    main()
