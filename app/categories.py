"""The categorisation rules, written down once.

Freshdesk does the real routing, using automation rules you type into its
admin UI. This file is the single written source for those rules:

  * scripts/print_rules.py prints exactly what to type into Freshdesk
  * classify() predicts what Freshdesk SHOULD do with a report
  * scripts/verify_routing.py checks that Freshdesk actually did it

Freshdesk's "contains" is a plain substring match, so every keyword here was
chosen to avoid matching inside other words ("blocked" contains "locked",
"design in" contains "sign in"). tests/test_categories.py pins the traps down.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    ticket_type: str       # Freshdesk "Type" field
    group: str             # Freshdesk group = the department
    keywords: tuple[str, ...]


MAINTENANCE = Category(
    key="maintenance",
    ticket_type="Maintenance",
    group="Maintenance",
    keywords=(
        "toilet", "restroom", "bathroom", "blockage", "blocked", "clogged",
        "leak", "flood", "pipe", "sink", "lights", "light bulb", "lamp",
        "no electricity", "power cut", "blackout", "power outlet", "socket",
        "exposed wire", "spark", "air con", "aircon", "ceiling",
        "broken chair", "broken desk", "broken table", "furniture",
        "equipment", "elevator", "whiteboard",
    ),
)

SECURITY = Category(
    key="security",
    ticket_type="Security",
    group="Security",
    keywords=(
        "locked out", "door is locked", "room is locked", "door locked",
        "room locked", "lost my key", "forgot my key", "left my key",
        "room key", "door key", "key card", "keycard", "access card",
        "unlock the door", "unlock the room", "stolen", "theft",
        "suspicious", "trapped", "security guard",
    ),
)

IT = Category(
    key="it",
    ticket_type="IT",
    group="IT Support",
    keywords=(
        "wifi", "wi-fi", "wireless", "internet", "network", "email",
        "e-mail", "outlook", "password", "login", "log in", "can't sign in",
        "cannot sign in", "vpn", "printer", "projector", "laptop",
        "software", "my account", "student account",
    ),
)

# Freshdesk runs ALL matching creation rules from top to bottom, so when a
# report matches two categories the LAST matching rule's group wins.
# IT is last because its words are the most specific: "locked out of my
# email account" is an IT problem, not a security one.
RULE_ORDER: tuple[Category, ...] = (MAINTENANCE, SECURITY, IT)

FALLBACK_TYPE = "General"
FALLBACK_GROUP = "Service Desk"

URGENT_KEYWORDS: tuple[str, ...] = (
    "leak", "flood", "spark", "smoke", "burning", "on fire", "fire alarm",
    "exposed wire", "electric shock", "gas smell", "smell of gas",
    "trapped", "door is locked", "room is locked", "stuck in the elevator",
    "injured",
)

ALL_CATEGORY_KEYWORDS: tuple[str, ...] = tuple(
    kw for cat in RULE_ORDER for kw in cat.keywords
)


@dataclass(frozen=True)
class Classification:
    ticket_type: str
    group: str
    priority: str          # "Urgent" or "Medium"
    routed: bool           # False = no rule matched, left for manual triage
    matched: tuple[str, ...]


def _found(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [kw for kw in keywords if kw in text]


def classify(subject: str, description: str) -> Classification:
    """Predict what the Freshdesk rules will do with a report.

    Mirrors their semantics: case-insensitive substring match, every rule
    runs, the last matching category wins, urgency is checked separately.
    """
    text = f"{subject}\n{description}".lower()
    ticket_type, group, routed = FALLBACK_TYPE, FALLBACK_GROUP, False
    matched: list[str] = []
    for cat in RULE_ORDER:
        hits = _found(text, cat.keywords)
        if hits:
            ticket_type, group, routed = cat.ticket_type, cat.group, True
            matched += hits
    urgent = _found(text, URGENT_KEYWORDS)
    return Classification(
        ticket_type=ticket_type,
        group=group,
        priority="Urgent" if urgent else "Medium",
        routed=routed,
        matched=tuple(matched + urgent),
    )
