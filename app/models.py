from pydantic import BaseModel, EmailStr, Field


class ReportIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, examples=["Lwin"])
    email: EmailStr = Field(..., examples=["student@example.com"])
    location: str = Field(..., min_length=1, max_length=120,
                          examples=["VMS Building, 3rd floor"])
    subject: str = Field(..., min_length=5, max_length=150,
                         examples=["Toilet blocked on 3rd floor"])
    description: str = Field(..., min_length=10, max_length=5000,
                             examples=["The toilet in the men's restroom is blocked."])


class ReportAccepted(BaseModel):
    ticket_id: int
    status: str
    department: str | None
    category: str | None
    priority: str
    routed_in_ms: float
    track: str


class TrackIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class TicketView(BaseModel):
    ticket_id: int
    subject: str
    status: str
    priority: str
    department: str | None
    category: str | None
    created_at: str
    updated_at: str
    due_by: str | None
    is_escalated: bool
    timeline: list[dict]


class WebhookIn(BaseModel):
    ticket_id: int
    status: str | None = None
    priority: str | None = None
    group: str | None = None
    agent: str | None = None


class Health(BaseModel):
    ok: bool
    freshdesk: bool
    events_db: bool
