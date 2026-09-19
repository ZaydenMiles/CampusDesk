"""Shared fixtures. No test here talks to the real Freshdesk.

FakeFreshdesk is the demo-mode helpdesk (app/demo.py) plus a switch to
simulate an outage. It routes each new ticket with app.categories.classify(),
which is what we configured Freshdesk to do. The live check against the real
thing is scripts/verify_routing.py.
"""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.demo import DemoFreshdesk
from app.events import EventStore
from app.freshdesk import FreshdeskError
from app.main import create_app


class FakeFreshdesk(DemoFreshdesk):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next = False

    def create_ticket(self, **kwargs):
        if self.fail_next:
            raise FreshdeskError(503, "maintenance")
        return super().create_ticket(**kwargs)


@pytest.fixture
def fake() -> FakeFreshdesk:
    return FakeFreshdesk()


@pytest.fixture
def store() -> EventStore:
    return EventStore(":memory:")


@pytest.fixture
def client(fake, store, monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "WEBHOOK_SECRET", "test-secret-0123456789")
    return TestClient(create_app(client=fake, store=store, demo=False))


@pytest.fixture
def report() -> dict:
    return {
        "name": "Lwin", "email": "student@example.com",
        "location": "VMS Building, 3rd floor",
        "subject": "Toilet blocked on 3rd floor",
        "description": "The toilet in the men's restroom is blocked.",
    }
