import hmac
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, logs
from app.demo import DemoFreshdesk
from app.events import EventStore
from app.freshdesk import FreshdeskClient, FreshdeskError, from_env
from app.models import Health, ReportAccepted, ReportIn, TicketView, TrackIn, WebhookIn

log = logs.setup("portal")
STATIC = Path(__file__).parent / "static"


def create_app(client: FreshdeskClient | None = None,
               store: EventStore | None = None,
               demo: bool | None = None) -> FastAPI:
    demo = config.DEMO_MODE if demo is None else demo
    app = FastAPI(title="CampusDesk" + (" (demo mode)" if demo else ""),
                  description="Campus problem reports, routed by Freshdesk",
                  version="1.1.0")

    if demo and client is None:
        client, store = DemoFreshdesk(), store or EventStore(":memory:")
        client.seed(store)
        log.info("DEMO MODE: pretend Freshdesk in memory, nothing leaves this laptop")
    state = {"client": client, "store": store}
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def fd() -> FreshdeskClient:
        if state["client"] is None:
            try:
                state["client"] = from_env()
            except ValueError:
                raise HTTPException(503, "Freshdesk is not configured. Fill in .env, "
                                         "or try it without an account: make demo")
        return state["client"]

    def events() -> EventStore:
        if state["store"] is None:
            state["store"] = EventStore(config.EVENTS_DB)
        return state["store"]

    def names(fdc: FreshdeskClient, ticket: dict) -> dict:
        return {
            "status": fdc.statuses().get(ticket["status"], str(ticket["status"])),
            "priority": config.PRIORITY.get(ticket["priority"], str(ticket["priority"])),
            "department": fdc.groups().get(ticket.get("group_id")),
            "category": ticket.get("type"),
        }

    @app.get("/", include_in_schema=False)
    def portal_page():
        return FileResponse(STATIC / "index.html")

    @app.get("/track", include_in_schema=False)
    def track_page():
        return FileResponse(STATIC / "track.html")

    @app.get("/dashboard", include_in_schema=False)
    def dashboard_page():
        return FileResponse(STATIC / "dashboard.html")

    @app.get("/health", response_model=Health)
    def health():
        try:
            fd().me()
            fd_ok = True
        except Exception as exc:
            log.warning("health: freshdesk unreachable (%s)", exc)
            fd_ok = False
        db_ok = events().healthy()
        return Health(ok=fd_ok and db_ok, freshdesk=fd_ok, events_db=db_ok)

    @app.post("/api/reports", status_code=201, response_model=ReportAccepted)
    def submit_report(report: ReportIn, fdc: FreshdeskClient = Depends(fd),
                      store: EventStore = Depends(events)):
        started = time.perf_counter()
        try:
            created = fdc.create_ticket(
                name=report.name, email=report.email, subject=report.subject,
                description=report.description, location=report.location,
                tags=[config.DEMO_TAG],
            )
            ticket = fdc.wait_for_routing(created["id"], config.ROUTING_TIMEOUT,
                                          config.ROUTING_POLL)
        except FreshdeskError as exc:
            log.error("could not create ticket: %s", exc)
            raise HTTPException(502, "The service desk is unavailable. "
                                     "Please try again in a minute.")
        n = names(fdc, ticket)
        store.record(ticket["id"], status=n["status"], priority=n["priority"],
                     group_name=n["department"], agent=None, source="portal")
        routed_ms = round((time.perf_counter() - started) * 1000, 1)
        log.info("#%s -> %s / %s / %s in %s ms", ticket["id"], n["category"],
                 n["department"], n["priority"], routed_ms)
        return ReportAccepted(ticket_id=ticket["id"], status=n["status"],
                              department=n["department"], category=n["category"],
                              priority=n["priority"], routed_in_ms=routed_ms,
                              track=f"/track?id={ticket['id']}")

    @app.post("/api/reports/{ticket_id}/track", response_model=TicketView)
    def track_report(ticket_id: int, body: TrackIn,
                     fdc: FreshdeskClient = Depends(fd),
                     store: EventStore = Depends(events)):
        email = body.email
        try:
            ticket = fdc.get_ticket(ticket_id)
        except FreshdeskError as exc:
            if exc.status == 404:
                raise HTTPException(404, "No report with that number and email.")
            raise HTTPException(502, "The service desk is unavailable.")
        requester = (ticket.get("requester") or {}).get("email") or ""
        if requester.lower() != email.strip().lower():
            raise HTTPException(404, "No report with that number and email.")
        n = names(fdc, ticket)
        return TicketView(
            ticket_id=ticket["id"], subject=ticket["subject"], status=n["status"],
            priority=n["priority"], department=n["department"],
            category=n["category"], created_at=ticket["created_at"],
            updated_at=ticket["updated_at"], due_by=ticket.get("due_by"),
            is_escalated=bool(ticket.get("is_escalated")),
            timeline=store.timeline(ticket_id),
        )

    @app.get("/api/dashboard")
    def dashboard(fdc: FreshdeskClient = Depends(fd)):
        tickets = list(fdc.list_tickets())
        statuses, groups = fdc.statuses(), fdc.groups()
        now = datetime.now(timezone.utc)
        overdue, open_count, urgent_open = [], 0, 0
        for t in tickets:
            done = statuses.get(t["status"]) in ("Resolved", "Closed")
            open_count += not done
            urgent_open += (not done) and t["priority"] == config.PRIORITY_ID["Urgent"]
            due = t.get("due_by")
            late = bool(due) and not done and \
                datetime.fromisoformat(due.replace("Z", "+00:00")) < now
            if t.get("is_escalated") or late:
                overdue.append({
                    "ticket_id": t["id"], "subject": t["subject"],
                    "department": groups.get(t.get("group_id")),
                    "priority": config.PRIORITY.get(t["priority"]),
                    "status": statuses.get(t["status"]), "due_by": due,
                })
        return {
            "total": len(tickets),
            "summary": {"open": open_count, "urgent_open": urgent_open,
                        "overdue": len(overdue)},
            "by_department": Counter(groups.get(t.get("group_id"), "Unassigned")
                                     for t in tickets),
            "by_status": Counter(statuses.get(t["status"], str(t["status"]))
                                 for t in tickets),
            "by_priority": Counter(config.PRIORITY.get(t["priority"], "?")
                                   for t in tickets),
            "overdue": overdue,
            "recent": [{
                "ticket_id": t["id"], "subject": t["subject"],
                "category": t.get("type"),
                "department": groups.get(t.get("group_id"), "Unassigned"),
                "priority": config.PRIORITY.get(t["priority"]),
                "status": statuses.get(t["status"], str(t["status"])),
                "created_at": t["created_at"],
            } for t in tickets[:15]],
        }

    @app.post("/webhooks/freshdesk", status_code=204)
    def freshdesk_webhook(event: WebhookIn,
                          x_webhook_secret: str = Header(default=""),
                          store: EventStore = Depends(events)):
        if not config.WEBHOOK_SECRET or not hmac.compare_digest(
                x_webhook_secret, config.WEBHOOK_SECRET):
            raise HTTPException(401, "bad webhook secret")
        store.record(event.ticket_id, status=event.status, priority=event.priority,
                     group_name=event.group, agent=event.agent, source="webhook")
        log.info("webhook #%s -> %s (%s)", event.ticket_id, event.status,
                 event.agent or "no agent")

    @app.get("/api/mode")
    def mode():
        return {"demo": demo,
                "helpdesk": "demo (in memory)" if demo
                else f"{config.FRESHDESK_DOMAIN}.freshdesk.com"}

    if demo:
        @app.post("/api/demo/reports/{ticket_id}/advance")
        def demo_advance(ticket_id: int, fdc: DemoFreshdesk = Depends(fd),
                         store: EventStore = Depends(events)):
            try:
                status = fdc.advance(ticket_id)
            except FreshdeskError:
                raise HTTPException(404, "No report with that number.")
            if status:
                ticket = fdc.get_ticket(ticket_id)
                store.record(ticket_id, status=status,
                             priority=config.PRIORITY[ticket["priority"]],
                             group_name=fdc.groups().get(ticket["group_id"]),
                             agent="Demo agent", source="demo")
            return {"ticket_id": ticket_id, "status": status or "Closed"}

    return app


app = create_app()
