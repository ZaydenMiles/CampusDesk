"""The API client, against a fake HTTP transport: no network, no API key."""
import base64
import json

import httpx
import pytest

from app.freshdesk import FreshdeskClient, FreshdeskError, parse_statuses


def make(handler, **kw) -> FreshdeskClient:
    return FreshdeskClient("unitest", "KEY123", transport=httpx.MockTransport(handler),
                           sleep=kw.pop("sleep", lambda s: None), **kw)


def test_uses_api_key_as_basic_auth_username():
    seen = {}

    def handler(req):
        seen["auth"] = req.headers["authorization"]
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"contact": {"name": "x", "email": "y"}})

    make(handler).me()
    assert seen["auth"] == "Basic " + base64.b64encode(b"KEY123:X").decode()
    assert seen["url"] == "https://unitest.freshdesk.com/api/v2/agents/me"


def test_create_ticket_sends_no_category():
    sent = {}

    def handler(req):
        sent.update(json.loads(req.content))
        return httpx.Response(201, json={"id": 7})

    out = make(handler).create_ticket(name="A", email="a@b.co", subject="S",
                                      description="D", location="Room 1", tags=["t"])
    assert out == {"id": 7}
    assert sent["status"] == 2 and sent["priority"] == 2 and sent["source"] == 2
    assert sent["custom_fields"] == {"cf_location": "Room 1"}
    assert "type" not in sent and "group_id" not in sent


def test_waits_out_a_rate_limit():
    calls, slept = [], []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, json=[])

    make(handler, sleep=slept.append).ticket_fields()
    assert len(calls) == 2 and slept == [3.0]


def test_errors_carry_the_response_body():
    def handler(req):
        return httpx.Response(400, json={"errors": [{"field": "email"}]})

    with pytest.raises(FreshdeskError) as exc:
        make(handler).create_ticket(name="A", email="bad", subject="S", description="D")
    assert exc.value.status == 400 and "email" in exc.value.body


def test_wait_for_routing_polls_until_a_group_is_set():
    answers = iter([{"id": 1, "group_id": None}, {"id": 1, "group_id": None},
                    {"id": 1, "group_id": 55}])

    def handler(req):
        return httpx.Response(200, json=next(answers))

    t = make(handler).wait_for_routing(1, timeout=30, interval=0)
    assert t["group_id"] == 55


def test_custom_status_ids_are_looked_up_not_hard_coded():
    fields = [{"name": "status", "choices": {
        "2": ["Open", "Being Processed"], "4": ["Resolved", "Resolved"],
        "12": ["Assigned", "Assigned to a department"],
        "13": ["In Progress", "Being worked on"]}}]

    def handler(req):
        return httpx.Response(200, json=fields)

    fd = make(handler)
    assert parse_statuses(fields)[12] == "Assigned"
    assert fd.status_id("in progress") == 13
    with pytest.raises(KeyError):
        fd.status_id("Teleported")


def test_list_tickets_follows_pages():
    def handler(req):
        page = int(req.url.params["page"])
        n = 100 if page == 1 else 3
        return httpx.Response(200, json=[{"id": page * 1000 + i} for i in range(n)])

    assert len(list(make(handler).list_tickets())) == 103
