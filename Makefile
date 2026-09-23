.DEFAULT_GOAL := help
PY := .venv/bin/python

install:   ## create the virtualenv and install pinned dependencies
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
demo:      ## the whole portal with a pretend Freshdesk: no account needed
	DEMO_MODE=1 .venv/bin/uvicorn app.main:app --reload --port 8000
run:       ## the portal against your real Freshdesk (needs .env)
	.venv/bin/uvicorn app.main:app --reload --port 8000
tunnel:    ## public URL for webhooks + point the Freshdesk rule at it
	$(PY) -m scripts.tunnel
setup:     ## configure a Freshdesk account through the API (safe to rerun)
	$(PY) -m scripts.setup_freshdesk
check:     ## compare your Freshdesk admin setup with what the code expects
	$(PY) -m scripts.check_setup
rules:     ## print the automation rules
	$(PY) -m scripts.print_rules
verify:    ## create the 12 sample tickets and check every one was routed correctly
	$(PY) -m scripts.verify_routing
report:    ## the numbers for the results slide
	$(PY) -m scripts.report
present:   ## step-by-step terminal demo (SITE=https://... to use the deployed server)
	bash scripts/demo.sh
test:      ## all tests (no Freshdesk needed)
	$(PY) -m pytest -v
health:    ## one line: can I present?
	@curl -s localhost:8000/health; echo
reset:     ## wipe the local webhook timeline
	rm -f data/events.db
help:      ## this list
	@grep -E "^[a-z-]+:.*## " Makefile | sed -E "s/:.*## /\t/"

.PHONY: install demo run tunnel setup check rules verify report present test health reset help
