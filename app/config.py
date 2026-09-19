"""Central configuration.

Every setting comes from the environment (or .env) so the API key never
appears in code and the same code runs on your laptop and in CI.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# DEMO_MODE=1 runs the whole portal against app/demo.py, a pretend Freshdesk
# in memory, so anyone who clones the repo can try it without an account.
DEMO_MODE = os.getenv("DEMO_MODE", "0").lower() in ("1", "true", "yes")

FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN", "")
FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
DEMO_REQUESTER_EMAIL = os.getenv("DEMO_REQUESTER_EMAIL", "")

EVENTS_DB = os.getenv("EVENTS_DB", "data/events.db")
DEMO_TAG = os.getenv("DEMO_TAG", "usd-demo")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# How long the portal waits for Freshdesk's automation rules to route a new
# ticket before answering the student anyway.
ROUTING_TIMEOUT = float(os.getenv("ROUTING_TIMEOUT", "8"))
ROUTING_POLL = float(os.getenv("ROUTING_POLL", "0.5"))

# --------------------------------------------------------------------------
# Names that must match what you create in the Freshdesk admin UI exactly.
# scripts/check_setup.py compares these against your real helpdesk.
# --------------------------------------------------------------------------
GROUPS = ["Maintenance", "IT Support", "Security", "Service Desk"]
TICKET_TYPES = ["Maintenance", "IT", "Security", "General"]
CUSTOM_STATUSES = ["Assigned", "In Progress"]
LOCATION_FIELD = "cf_location"

# Freshdesk's fixed numeric codes (API v2).
PRIORITY = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
PRIORITY_ID = {v: k for k, v in PRIORITY.items()}
STATUS_OPEN = 2
SOURCE_PORTAL = 2
