"""Demo mode: the whole portal works for anyone who clones the repo."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.demo import DEMO_EMAIL
from app.main import create_app


@pytest.fixture
def demo():
    return TestClient(create_app(demo=True))


def test_demo_starts_with_the_twelve_samples(demo):
    d = demo.get("/api/dashboard").json()
    assert d["total"] == 12
    assert set(d["by_department"]) == {"Maintenance", "Security", "IT Support", "Service Desk"}
    assert demo.get("/api/mode").json()["demo"] is True


def test_demo_has_an_escalated_urgent_report_to_show(demo):
    overdue = demo.get("/api/dashboard").json()["overdue"]
    assert [o["subject"] for o in overdue] == ["Water leak from ceiling"]


def test_demo_routes_a_new_report(demo):
    r = demo.post("/api/reports", json={
        "name": "Visitor", "email": "visitor@example.com", "location": "Library",
        "subject": "Wi-Fi down", "description": "No wifi on the second floor at all"})
    assert r.status_code == 201
    assert (r.json()["department"], r.json()["status"]) == ("IT Support", "Assigned")


def test_demo_agent_walks_a_ticket_to_closed(demo):
    tid = demo.post("/api/reports", json={
        "name": "Visitor", "email": "visitor@example.com", "location": "VMS",
        "subject": "Toilet blocked", "description": "The toilet is blocked again"}).json()["ticket_id"]
    seen = [demo.post(f"/api/demo/reports/{tid}/advance").json()["status"] for _ in range(4)]
    assert seen == ["In Progress", "Resolved", "Closed", "Closed"]
    timeline = demo.post(f"/api/reports/{tid}/track", json={"email": "visitor@example.com"}).json()["timeline"]
    assert [e["status"] for e in timeline] == ["Assigned", "In Progress", "Resolved", "Closed"]


def test_seeded_reports_can_be_tracked(demo):
    r = demo.post("/api/reports/1001/track", json={"email": DEMO_EMAIL})
    assert r.status_code == 200 and r.json()["timeline"]


def test_demo_endpoint_does_not_exist_in_real_mode(client):
    assert client.post("/api/demo/reports/1001/advance").status_code == 404


def test_real_mode_without_credentials_explains_itself(monkeypatch):
    monkeypatch.setattr(config, "FRESHDESK_DOMAIN", "")
    monkeypatch.setattr(config, "FRESHDESK_API_KEY", "")
    app = TestClient(create_app(demo=False))
    r = app.get("/api/dashboard")
    assert r.status_code == 503 and "make demo" in r.json()["detail"]
