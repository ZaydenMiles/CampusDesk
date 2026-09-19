import time
from typing import Callable, Iterator

import httpx

from app import config, logs

log = logs.setup("freshdesk")


class FreshdeskError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Freshdesk API error {status}: {body[:500]}")
        self.status = status
        self.body = body


class FreshdeskClient:
    def __init__(self, domain: str, api_key: str, *,
                 transport: httpx.BaseTransport | None = None,
                 max_retries: int = 3,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        if not domain or not api_key:
            raise ValueError("FRESHDESK_DOMAIN and FRESHDESK_API_KEY must be set")
        self._http = httpx.Client(
            base_url=f"https://{domain}.freshdesk.com/api/v2",
            auth=(api_key, "X"),
            timeout=15.0,
            transport=transport,
        )
        self._max_retries = max_retries
        self._sleep = sleep
        self._groups: dict[int, str] | None = None
        self._statuses: dict[int, str] | None = None

    def _request(self, method: str, path: str, **kwargs):
        for attempt in range(self._max_retries + 1):
            resp = self._http.request(method, path, **kwargs)
            if resp.status_code == 429 and attempt < self._max_retries:
                wait = float(resp.headers.get("Retry-After", "5"))
                log.warning("rate limited, waiting %ss", wait)
                self._sleep(wait)
                continue
            if resp.status_code >= 400:
                raise FreshdeskError(resp.status_code, resp.text)
            return resp.json() if resp.content else None
        raise FreshdeskError(429, "still rate limited after retries")

    def close(self) -> None:
        self._http.close()

    def create_ticket(self, *, name: str, email: str, subject: str,
                      description: str, location: str | None = None,
                      tags: list[str] | None = None) -> dict:
        body = {
            "name": name,
            "email": email,
            "subject": subject,
            "description": description,
            "status": config.STATUS_OPEN,
            "priority": config.PRIORITY_ID["Medium"],
            "source": config.SOURCE_PORTAL,
            "tags": tags or [],
        }
        if location:
            body["custom_fields"] = {config.LOCATION_FIELD: location}
        return self._request("POST", "/tickets", json=body)

    def get_ticket(self, ticket_id: int, include: str = "requester,stats") -> dict:
        return self._request("GET", f"/tickets/{ticket_id}",
                             params={"include": include})

    def update_ticket(self, ticket_id: int, **fields) -> dict:
        return self._request("PUT", f"/tickets/{ticket_id}", json=fields)

    def add_note(self, ticket_id: int, body: str, private: bool = True) -> dict:
        return self._request("POST", f"/tickets/{ticket_id}/notes",
                             json={"body": body, "private": private})

    def wait_for_routing(self, ticket_id: int, timeout: float,
                         interval: float) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            ticket = self.get_ticket(ticket_id)
            if ticket.get("group_id") or time.monotonic() >= deadline:
                return ticket
            self._sleep(interval)

    def list_tickets(self, max_pages: int = 5) -> Iterator[dict]:
        for page in range(1, max_pages + 1):
            batch = self._request("GET", "/tickets", params={
                "per_page": 100, "page": page, "include": "stats",
                "order_by": "created_at", "order_type": "desc",
            })
            yield from batch
            if len(batch) < 100:
                return

    def me(self) -> dict:
        return self._request("GET", "/agents/me")

    def ticket_fields(self) -> list[dict]:
        return self._request("GET", "/ticket_fields")

    def groups(self, refresh: bool = False) -> dict[int, str]:
        if self._groups is None or refresh:
            self._groups = {g["id"]: g["name"]
                            for g in self._request("GET", "/groups")}
        return self._groups

    def statuses(self, refresh: bool = False) -> dict[int, str]:
        if self._statuses is None or refresh:
            self._statuses = parse_statuses(self.ticket_fields())
        return self._statuses

    def status_id(self, name: str) -> int:
        for sid, sname in self.statuses().items():
            if sname.lower() == name.lower():
                return sid
        raise KeyError(f"no status called {name!r} in this helpdesk")


def parse_statuses(fields: list[dict]) -> dict[int, str]:
    for field in fields:
        if field.get("name") == "status":
            return {int(k): (v[0] if isinstance(v, list) else v)
                    for k, v in field["choices"].items()}
    raise FreshdeskError(500, "ticket_fields has no status field")


def field_choices(fields: list[dict], name: str) -> list[str]:
    for field in fields:
        if field.get("name") == name:
            choices = field.get("choices") or []
            return list(choices.keys()) if isinstance(choices, dict) else list(choices)
    return []


def from_env() -> FreshdeskClient:
    return FreshdeskClient(config.FRESHDESK_DOMAIN, config.FRESHDESK_API_KEY)
