"""A pretend Freshdesk, so anyone can run CampusDesk without an account.

    make demo            (or: DEMO_MODE=1 uvicorn app.main:app --port 8000)

DemoFreshdesk has the same methods as FreshdeskClient, and it routes new
tickets with app.categories.classify(), which is exactly what the real
Freshdesk automation rules were configured to do. Deadlines follow the
CampusDesk SLA policy. Everything lives in memory and resets on restart.

The tests use it too (tests/conftest.py), so the demo and the tests can
never disagree about how a report is routed.
"""
import itertools
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import categories, config
from app.freshdesk import FreshdeskError

GROUPS = {101: "Maintenance", 102: "IT Support", 103: "Security", 104: "Service Desk"}
STATUSES = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed",
            8: "Assigned", 9: "In Progress"}
STATUS_ID = {v: k for k, v in STATUSES.items()}

# CampusDesk SLA policy: resolve within N hours, by priority id.
RESOLVE_HOURS = {4: 1, 3: 4, 2: 24, 1: 72}

# What an agent does next, one click at a time.
NEXT_STATUS = {"Open": "Assigned", "Assigned": "In Progress",
               "In Progress": "Resolved", "Resolved": "Closed"}

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples.json"
DEMO_EMAIL = "student@campusdesk.demo"


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class DemoFreshdesk:
    def __init__(self) -> None:
        self.tickets: dict[int, dict] = {}
        self._ids = itertools.count(1001)
        self._lock = threading.Lock()

    # ------------------------------------------------ same API as the client
    def create_ticket(self, *, name, email, subject, description,
                      location=None, tags=None) -> dict:
        c = categories.classify(subject, description)
        priority = config.PRIORITY_ID[c.priority]
        now = datetime.now(timezone.utc)
        with self._lock:
            tid = next(self._ids)
            self.tickets[tid] = {
                "id": tid, "subject": subject, "description": description,
                "type": c.ticket_type,
                "group_id": {v: k for k, v in GROUPS.items()}[c.group],
                "priority": priority,
                "status": STATUS_ID["Assigned"] if c.routed else STATUS_ID["Open"],
                "requester": {"name": name, "email": email},
                "custom_fields": {config.LOCATION_FIELD: location},
                "created_at": _iso(now), "updated_at": _iso(now),
                "due_by": _iso(now + timedelta(hours=RESOLVE_HOURS[priority])),
                "is_escalated": False, "tags": list(tags or []),
                "stats": {"resolved_at": None},
            }
        return {"id": tid}

    def get_ticket(self, ticket_id, include="requester,stats") -> dict:
        if ticket_id not in self.tickets:
            raise FreshdeskError(404, "not found")
        return self.tickets[ticket_id]

    def wait_for_routing(self, ticket_id, timeout, interval) -> dict:
        return self.get_ticket(ticket_id)            # routing is instant here

    def update_ticket(self, ticket_id, **fields) -> dict:
        ticket = self.get_ticket(ticket_id)
        with self._lock:
            ticket.update(fields)
            now = _iso(datetime.now(timezone.utc))
            ticket["updated_at"] = now
            if STATUSES.get(ticket["status"]) == "Resolved":
                ticket["stats"]["resolved_at"] = now
        return ticket

    def list_tickets(self, max_pages=5) -> list[dict]:
        return sorted(self.tickets.values(), key=lambda t: t["id"], reverse=True)

    def me(self) -> dict:
        return {"id": 1, "contact": {"name": "Demo admin", "email": "admin@campusdesk.demo"}}

    def groups(self, refresh=False) -> dict[int, str]:
        return GROUPS

    def statuses(self, refresh=False) -> dict[int, str]:
        return STATUSES

    def status_id(self, name: str) -> int:
        return STATUS_ID[name]

    # ------------------------------------------------------- demo helpers
    def advance(self, ticket_id: int) -> str | None:
        """Play the department agent: move the ticket one step along."""
        current = STATUSES[self.get_ticket(ticket_id)["status"]]
        nxt = NEXT_STATUS.get(current)
        if nxt:
            self.update_ticket(ticket_id, status=STATUS_ID[nxt])
        return nxt

    def seed(self, store) -> None:
        """Fill the helpdesk with the 12 sample reports, at different stages,
        so the dashboard has something to show the moment it opens."""
        samples = json.loads(SAMPLES.read_text())
        for s in samples:
            created = self.create_ticket(
                name="Sample Student", email=DEMO_EMAIL, subject=s["subject"],
                description=s["description"], location=s["location"],
                tags=[config.DEMO_TAG])
            t = self.get_ticket(created["id"])
            store.record(t["id"], status=STATUSES[t["status"]],
                         priority=config.PRIORITY[t["priority"]],
                         group_name=GROUPS[t["group_id"]], agent=None, source="portal")

        ids = sorted(self.tickets)
        for tid, steps in zip(ids, [1, 2, 0, 0, 1, 2, 3, 1, 0, 2]):
            for _ in range(steps):
                status = self.advance(tid)
                store.record(tid, status=status, priority=None, group_name=None,
                             agent="Demo agent", source="demo")

        # One urgent hazard reported two hours ago and never fixed: escalated.
        leak = next(t for t in self.tickets.values() if t["subject"].startswith("Water leak"))
        two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        leak.update(created_at=_iso(two_hours_ago),
                    due_by=_iso(two_hours_ago + timedelta(hours=1)),
                    is_escalated=True, tags=leak["tags"] + ["escalated"])
