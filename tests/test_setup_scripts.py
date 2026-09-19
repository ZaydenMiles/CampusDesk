from app import categories
from scripts.setup_freshdesk import (creation_rules, escalation_rule, sla_policy,
                                     webhook_action, webhook_rule)
from scripts.tunnel import find_tunnel_url

GROUP_IDS = {"Maintenance": 1, "Security": 2, "IT Support": 3, "Service Desk": 4}


def test_creation_rules_follow_the_rule_order():
    names = [r["name"] for r in creation_rules(GROUP_IDS, assigned_status=8)]
    assert names == ["Route Maintenance", "Route Security", "Route IT",
                     "Fallback to Service Desk", "Urgent hazards"]


def test_category_rules_set_type_group_and_assigned():
    rule = creation_rules(GROUP_IDS, assigned_status=8)[2]
    assert rule["actions"] == [{"field_name": "ticket_type", "value": "IT"},
                               {"field_name": "group_id", "value": 3},
                               {"field_name": "status", "value": 8}]
    assert rule["conditions"][0]["properties"][0]["value"] == list(categories.IT.keywords)


def test_fallback_excludes_every_category_keyword_and_stays_open():
    rule = creation_rules(GROUP_IDS, assigned_status=8)[3]
    prop = rule["conditions"][0]["properties"][0]
    assert prop["operator"] == "does_not_contain"
    assert prop["value"] == list(categories.ALL_CATEGORY_KEYWORDS)
    assert all(a["field_name"] != "status" for a in rule["actions"])


def test_urgent_sla_is_fifteen_minutes_and_one_hour_around_the_clock():
    urgent = sla_policy([1, 2, 3, 4], escalate_to=99)["sla_target"]["priority_4"]
    assert (urgent["respond_within"], urgent["resolve_within"]) == (900, 3600)
    assert urgent["business_hours"] is False


def test_escalation_fires_once_not_every_hour():
    props = escalation_rule(escalate_to=99)["conditions"][0]["properties"]
    age = {p["operator"]: p["value"] for p in props if p["field_name"] == "hours_since_created"}
    assert age == {"greater_than": 2, "less_than": 3}


def test_webhook_sends_the_secret_and_the_placeholders():
    action = webhook_action("https://abc.trycloudflare.com/", "s3cret")
    assert action["url"] == "https://abc.trycloudflare.com/webhooks/freshdesk"
    assert action["custom_headers"] == {"X-Webhook-Secret": "s3cret"}
    assert action["content"]["ticket_id"] == "{{ticket.id}}"
    assert webhook_rule("https://x.trycloudflare.com", "s")["events"][0]["field_name"] == "status"


def test_tunnel_address_is_found_in_cloudflared_output():
    line = "INF |  https://thesis-saints-analytical.trycloudflare.com  |"
    assert find_tunnel_url(line) == "https://thesis-saints-analytical.trycloudflare.com"
    assert find_tunnel_url("INF Registered tunnel connection") is None
