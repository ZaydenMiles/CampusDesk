import argparse
import sys

from app import categories as c
from app import config
from app.freshdesk import FreshdeskClient, FreshdeskError, from_env

CREATION, HOURLY, UPDATES = 1, 3, 4
WEBHOOK_RULE = "Push status to portal"
SLA_NAME = "CampusDesk SLA"
H = 3600

GROUP_DESCRIPTIONS = {
    "Maintenance": "Facilities: toilets, leaks, lights, electricity, furniture",
    "Security": "Campus security: locked rooms, keys, key cards, theft",
    "IT Support": "IT services: Wi-Fi, email, passwords, accounts, printers",
    "Service Desk": "General triage for reports no rule could categorise",
}


def _contains(op: str, words) -> list[dict]:
    return [{"name": "condition_set_1", "match_type": "all", "properties": [
        {"resource_type": "ticket", "field_name": "subject_or_description",
         "operator": op, "value": list(words)}]}]


def creation_rules(group_ids: dict[str, int], assigned_status: int) -> list[dict]:
    rules = [{
        "name": f"Route {cat.ticket_type}", "active": True,
        "conditions": _contains("contains", cat.keywords),
        "actions": [{"field_name": "ticket_type", "value": cat.ticket_type},
                    {"field_name": "group_id", "value": group_ids[cat.group]},
                    {"field_name": "status", "value": assigned_status}],
    } for cat in c.RULE_ORDER]
    rules.append({
        "name": "Fallback to Service Desk", "active": True,
        "conditions": _contains("does_not_contain", c.ALL_CATEGORY_KEYWORDS),
        "actions": [{"field_name": "ticket_type", "value": c.FALLBACK_TYPE},
                    {"field_name": "group_id", "value": group_ids[c.FALLBACK_GROUP]}],
    })
    rules.append({
        "name": "Urgent hazards", "active": True,
        "conditions": _contains("contains", c.URGENT_KEYWORDS),
        "actions": [{"field_name": "priority", "value": config.PRIORITY_ID["Urgent"]},
                    {"field_name": "add_tag", "value": ["urgent-hazard"]}],
    })
    return rules


def sla_policy(group_ids: list[int], escalate_to: int) -> dict:
    def target(respond, resolve, business_hours):
        return {"respond_within": respond, "resolve_within": resolve,
                "next_respond_within": respond, "business_hours": business_hours,
                "escalation_enabled": True}
    return {
        "name": SLA_NAME,
        "description": "Urgent hazards: respond 15 min, resolve 1 h, 24/7. "
                       "Missed targets escalate to the service desk lead.",
        "applicable_to": {"group_ids": group_ids},
        "sla_target": {
            "priority_4": target(15 * 60, 1 * H, False),
            "priority_3": target(1 * H, 4 * H, False),
            "priority_2": target(4 * H, 24 * H, True),
            "priority_1": target(24 * H, 72 * H, True),
        },
        "escalation": {
            "response": {"escalation_time": 0, "agent_ids": [escalate_to]},
            "resolution": {"level_1": {"escalation_time": 0, "agent_ids": [escalate_to]}},
        },
    }


def escalation_rule(escalate_to: int) -> dict:
    return {
        "name": "Escalate stale urgent reports", "active": True,
        "conditions": [{"name": "condition_set_1", "match_type": "all", "properties": [
            {"resource_type": "ticket", "field_name": "hours_since_created",
             "operator": "greater_than", "value": 2},
            {"resource_type": "ticket", "field_name": "hours_since_created",
             "operator": "less_than", "value": 3},
            {"resource_type": "ticket", "field_name": "priority", "operator": "in", "value": [4]},
            {"resource_type": "ticket", "field_name": "status", "operator": "not_in", "value": [4, 5]}]}],
        "actions": [
            {"field_name": "add_tag", "value": ["escalated"]},
            {"field_name": "send_email_to_agent", "email_to": escalate_to,
             "email_subject": "ESCALATED: urgent report #{{ticket.id}} unresolved for 2 hours",
             "email_body": "<p>Urgent report \"{{ticket.subject}}\" ({{ticket.group.name}}) "
                           "has been unresolved for more than 2 hours.<br/>"
                           "Status: {{ticket.status}}<br/>Open it: {{ticket.url}}</p>"}],
    }


def webhook_url(base: str) -> str:
    return base.rstrip("/") + "/webhooks/freshdesk"


def webhook_action(base_url: str, secret: str) -> dict:
    return {
        "field_name": "trigger_webhook", "request_type": "POST",
        "url": webhook_url(base_url), "content_type": "JSON",
        "content_layout": "advanced",
        "custom_headers": {"X-Webhook-Secret": secret},
        "content": {"ticket_id": "{{ticket.id}}", "status": "{{ticket.status}}",
                    "priority": "{{ticket.priority}}", "group": "{{ticket.group.name}}",
                    "agent": "{{ticket.agent.name}}"},
    }


def webhook_rule(base_url: str, secret: str) -> dict:
    return {
        "name": WEBHOOK_RULE, "active": True,
        "performer": {"type": 3},
        "events": [{"field_name": "status", "from": "--", "to": "--"}],
        "conditions": [{"name": "condition_set_1", "match_type": "all", "properties": [
            {"resource_type": "ticket", "field_name": "priority", "operator": "in",
             "value": [1, 2, 3, 4]}]}],
        "actions": [webhook_action(base_url, secret)],
    }


def say(done: bool, text: str) -> None:
    print(f"  {'exists ' if done else 'created'}  {text}")


def ensure_groups(fd: FreshdeskClient) -> dict[str, int]:
    have = {name: gid for gid, name in fd.groups(refresh=True).items()}
    for name in config.GROUPS:
        existed = name in have
        if not existed:
            g = fd._request("POST", "/groups", json={
                "name": name, "description": GROUP_DESCRIPTIONS[name]})
            have[name] = g["id"]
        say(existed, f"group {name}")
    return have


def admin_field(fd: FreshdeskClient, name: str) -> dict | None:
    for f in fd._request("GET", "/admin/ticket_fields"):
        if f["name"] == name:
            return fd._request("GET", f"/admin/ticket_fields/{f['id']}")
    return None


def ensure_types(fd: FreshdeskClient) -> None:
    field = admin_field(fd, "ticket_type")
    have = {ch["value"] for ch in field["choices"]}
    missing = [t for t in config.TICKET_TYPES if t not in have]
    if missing:
        fd._request("PUT", f"/admin/ticket_fields/{field['id']}", json={"choices": [
            {"value": t, "position": len(have) + i + 1} for i, t in enumerate(missing)]})
    for t in config.TICKET_TYPES:
        say(t not in missing, f"ticket type {t}")


def ensure_statuses(fd: FreshdeskClient) -> None:
    field = admin_field(fd, "status")
    have = {ch["value"] for ch in field["choices"] if not ch.get("deleted")}
    last = max(ch["position"] for ch in field["choices"] if ch["position"] < 9000)
    labels = {"Assigned": "Assigned to a department", "In Progress": "Being worked on"}
    missing = [s for s in config.CUSTOM_STATUSES if s not in have]
    if missing:
        fd._request("PUT", f"/admin/ticket_fields/{field['id']}", json={"choices": [
            {"value": s, "label_for_customers": labels[s], "stop_sla_timer": False,
             "position": last + i + 1} for i, s in enumerate(missing)]})
    fd.statuses(refresh=True)
    for s in config.CUSTOM_STATUSES:
        say(s not in missing, f"status {s} (id {fd.status_id(s)})")


def ensure_location_field(fd: FreshdeskClient) -> None:
    exists = admin_field(fd, config.LOCATION_FIELD) is not None
    if not exists:
        fd._request("POST", "/admin/ticket_fields", json={
            "label": "Location", "label_for_customers": "Where is the problem?",
            "type": "custom_text", "customers_can_edit": True,
            "displayed_to_customers": True})
    say(exists, f"custom field {config.LOCATION_FIELD}")


def ensure_rules(fd: FreshdeskClient, automation_type: int, rules: list[dict]) -> None:
    have = {r["name"] for r in fd._request("GET", f"/automations/{automation_type}/rules")}
    for rule in rules:
        if rule["name"] not in have:
            fd._request("POST", f"/automations/{automation_type}/rules", json=rule)
        say(rule["name"] in have, f"rule {rule['name']}")


def ensure_sla(fd: FreshdeskClient, group_ids: list[int], escalate_to: int) -> None:
    body = sla_policy(group_ids, escalate_to)
    existing = [p for p in fd._request("GET", "/sla_policies") if p["name"] == SLA_NAME]
    if existing:
        fd._request("PUT", f"/sla_policies/{existing[0]['id']}",
                    json={**{k: v for k, v in body.items() if k != "name"}, "active": True})
    else:
        fd._request("POST", "/sla_policies", json=body)
    say(bool(existing), f"SLA policy {SLA_NAME} (targets refreshed)")


def set_webhook(fd: FreshdeskClient, base_url: str) -> None:
    if not config.WEBHOOK_SECRET:
        raise SystemExit("WEBHOOK_SECRET is empty in .env")
    rules = {r["name"]: r for r in fd._request("GET", f"/automations/{UPDATES}/rules")}
    if WEBHOOK_RULE in rules:
        fd._request("PUT", f"/automations/{UPDATES}/rules/{rules[WEBHOOK_RULE]['id']}",
                    json={"actions": [webhook_action(base_url, config.WEBHOOK_SECRET)]})
    else:
        fd._request("POST", f"/automations/{UPDATES}/rules",
                    json=webhook_rule(base_url, config.WEBHOOK_SECRET))
    say(WEBHOOK_RULE in rules, f"webhook -> {webhook_url(base_url)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Configure a Freshdesk helpdesk for CampusDesk through the admin API.")
    ap.add_argument("--webhook-url", help="public base URL of the portal, e.g. from make tunnel")
    args = ap.parse_args()
    try:
        fd = from_env()
        me = fd.me()
        print(f"Configuring {config.FRESHDESK_DOMAIN}.freshdesk.com "
              f"(escalations go to {me['contact']['name']})\n")
        groups = ensure_groups(fd)
        ensure_types(fd)
        ensure_statuses(fd)
        ensure_location_field(fd)
        ensure_rules(fd, CREATION, creation_rules(groups, fd.status_id("Assigned")))
        ensure_sla(fd, [groups[g] for g in config.GROUPS], me["id"])
        ensure_rules(fd, HOURLY, [escalation_rule(me["id"])])
        if args.webhook_url:
            set_webhook(fd, args.webhook_url)
    except (ValueError, FreshdeskError) as exc:
        print(f"\nStopped: {exc}")
        return 1

    order = [r["name"] for r in fd._request("GET", f"/automations/{CREATION}/rules")]
    wanted = [r["name"] for r in creation_rules(groups, 0)]
    in_order = [n for n in order if n in wanted] == wanted
    print(f"\nCreation rule order {'OK' if in_order else 'WRONG: drag them into this order'}: "
          + " > ".join(wanted))
    print("\nOne click left if you have not done it: Admin > Automations > Ticket Creation >"
          " 'Execute all matching rules'.\nThen check it:  python -m scripts.verify_routing")
    return 0 if in_order else 1


if __name__ == "__main__":
    sys.exit(main())
