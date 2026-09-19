"""The keyword rules. Every trap listed here was a real misroute."""
import json
from pathlib import Path

import pytest

from app.categories import ALL_CATEGORY_KEYWORDS, RULE_ORDER, URGENT_KEYWORDS, classify

SAMPLES = json.loads((Path(__file__).parent.parent / "data" / "samples.json").read_text())


@pytest.mark.parametrize("s", SAMPLES, ids=[s["subject"] for s in SAMPLES])
def test_samples_match_the_rules(s):
    """data/samples.json and app/categories.py must agree, or
    verify_routing would be checking Freshdesk against the wrong answer."""
    c = classify(s["subject"], s["description"])
    assert (c.ticket_type, c.group, c.priority) == (
        s["expect"]["type"], s["expect"]["group"], s["expect"]["priority"])


@pytest.mark.parametrize("text,expected_group", [
    # "blocked" contains "locked": a blocked toilet is not a security issue
    ("The drain is blocked in the restroom", "Maintenance"),
    # "Design Innovation" contains "sign in"
    ("Light bulb broken in the Design Innovation building, lights flicker", "Maintenance"),
    # "locked out" of an ACCOUNT is IT, not Security: IT is the last rule
    ("I am locked out of my email", "IT Support"),
    # keyboard is not a key
    ("Some keys on my laptop keyboard are stuck", "IT Support"),
])
def test_substring_traps(text, expected_group):
    assert classify("Report", text).group == expected_group


def test_matching_is_case_insensitive():
    assert classify("WIFI DOWN", "NO INTERNET").group == "IT Support"


def test_last_matching_rule_wins():
    # Maintenance (toilet) and Security (door is locked) both match.
    c = classify("Toilet door is locked", "The toilet door is locked from inside")
    assert c.group == "Security"
    assert c.priority == "Urgent"


def test_unmatched_reports_fall_back_to_the_service_desk():
    c = classify("Question", "When does the cafeteria open on Sunday?")
    assert (c.group, c.routed, c.priority) == ("Service Desk", False, "Medium")


def test_firewall_is_not_a_fire():
    assert classify("VPN", "The firewall blocks the VPN").priority == "Medium"


def test_keywords_are_lowercase_and_unique_per_rule():
    for cat in RULE_ORDER:
        assert all(k == k.lower() and k == k.strip() for k in cat.keywords)
        assert len(set(cat.keywords)) == len(cat.keywords), cat.key
    assert all(k == k.lower() for k in URGENT_KEYWORDS)
    assert len(ALL_CATEGORY_KEYWORDS) == sum(len(c.keywords) for c in RULE_ORDER)
