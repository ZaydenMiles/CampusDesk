def test_report_is_routed_by_freshdesk(client, report):
    r = client.post("/api/reports", json=report)
    assert r.status_code == 201
    body = r.json()
    assert body["department"] == "Maintenance"
    assert body["category"] == "Maintenance"
    assert body["status"] == "Assigned"
    assert body["track"] == f"/track?id={body['ticket_id']}"


def test_urgent_report_gets_urgent_priority(client, report):
    report |= {"subject": "Water leak", "description": "Water leak from the ceiling in room 201"}
    assert client.post("/api/reports", json=report).json()["priority"] == "Urgent"


def test_bad_report_is_rejected_before_freshdesk(client, fake, report):
    report["email"] = "not-an-email"
    assert client.post("/api/reports", json=report).status_code == 422
    assert fake.tickets == {}


def test_freshdesk_outage_is_a_clear_502(client, fake, report):
    fake.fail_next = True
    r = client.post("/api/reports", json=report)
    assert r.status_code == 502 and "unavailable" in r.json()["detail"]


def test_tracking_needs_the_matching_email(client, report):
    tid = client.post("/api/reports", json=report).json()["ticket_id"]
    ok = client.post(f"/api/reports/{tid}/track", json={"email": "STUDENT@example.com"})
    assert ok.status_code == 200 and ok.json()["status"] == "Assigned"
    stranger = client.post(f"/api/reports/{tid}/track", json={"email": "other@example.com"})
    missing = client.post("/api/reports/999999/track", json={"email": "student@example.com"})
    assert stranger.status_code == missing.status_code == 404
    assert stranger.json() == missing.json()


def test_webhook_rejects_a_wrong_secret(client):
    r = client.post("/webhooks/freshdesk", json={"ticket_id": 1, "status": "Closed"},
                    headers={"X-Webhook-Secret": "guess"})
    assert r.status_code == 401


def test_webhooks_build_the_timeline(client, report):
    tid = client.post("/api/reports", json=report).json()["ticket_id"]
    headers = {"X-Webhook-Secret": "test-secret-0123456789"}
    for status, agent in [("In Progress", "Somchai"), ("Resolved", "Somchai")]:
        r = client.post("/webhooks/freshdesk", headers=headers, json={
            "ticket_id": str(tid), "status": status, "priority": "Medium",
            "group": "Maintenance", "agent": agent})
        assert r.status_code == 204
    timeline = client.post(f"/api/reports/{tid}/track", json={"email": report["email"]}).json()["timeline"]
    assert [e["status"] for e in timeline] == ["Assigned", "In Progress", "Resolved"]
    assert [e["source"] for e in timeline] == ["portal", "webhook", "webhook"]


def test_webhook_tolerates_empty_placeholders(client):
    r = client.post("/webhooks/freshdesk", headers={"X-Webhook-Secret": "test-secret-0123456789"},
                    json={"ticket_id": "5", "status": "Open", "agent": "", "group": ""})
    assert r.status_code == 204


def test_dashboard_counts_by_department(client, report):
    client.post("/api/reports", json=report)
    report |= {"subject": "Wi-Fi down", "description": "No wifi in the library at all"}
    client.post("/api/reports", json=report)
    d = client.get("/api/dashboard").json()
    assert d["total"] == 2
    assert d["by_department"] == {"Maintenance": 1, "IT Support": 1}
    assert d["by_status"] == {"Assigned": 2}


def test_health_reports_both_dependencies(client):
    assert client.get("/health").json() == {"ok": True, "freshdesk": True, "events_db": True}


def test_pages_and_assets_are_served(client):
    assert "Report a campus problem" in client.get("/").text
    assert "Track a report" in client.get("/track").text
    assert "Staff dashboard" in client.get("/dashboard").text
    for asset in ("styles.css", "common.js", "report.js", "track.js", "dashboard.js"):
        assert client.get(f"/static/{asset}").status_code == 200, asset


def test_tracking_is_a_post_so_the_email_never_sits_in_a_url(client, report):
    tid = client.post("/api/reports", json=report).json()["ticket_id"]
    assert client.get(f"/api/reports/{tid}/track").status_code == 405


def test_dashboard_summary_counts_open_and_urgent(client, report):
    client.post("/api/reports", json=report)
    report |= {"subject": "Water leak", "description": "Water leak from the ceiling in room 201"}
    client.post("/api/reports", json=report)
    assert client.get("/api/dashboard").json()["summary"] == {"open": 2, "urgent_open": 1, "overdue": 0}
