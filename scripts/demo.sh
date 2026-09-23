#!/usr/bin/env bash
set -u

SITE="${SITE:-${1:-http://localhost:8000}}"
EMAIL="${DEMO_EMAIL:-student@example.com}"

BOLD=$'\033[1m'; DIM=$'\033[2m'; BLUE=$'\033[38;5;75m'; GREEN=$'\033[38;5;71m'
RED=$'\033[38;5;167m'; RESET=$'\033[0m'; Q=$'\047'

pretty() {
  if command -v jq >/dev/null 2>&1; then jq .; else python3 -m json.tool; fi
}

summary() {
  if command -v jq >/dev/null 2>&1; then
    jq '{total, summary, by_department, by_status}'
  else
    python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({k: d[k] for k in ("total","summary","by_department","by_status")}, indent=2))'
  fi
}

title() {
  printf '\n%s%s%s\n' "$BOLD" "$1" "$RESET"
  printf '%s%s%s\n' "$DIM" "$(printf '%.0s-' $(seq 1 ${#1}))" "$RESET"
}

pause() {
  printf '\n%s[Enter]%s ' "$DIM" "$RESET"
  read -r _
}

run() {
  printf '\n%s$ %s%s\n\n' "$BLUE" "$1" "$RESET"
  eval "$1"
}

post() {
  curl -s -X POST "$1" -H 'Content-Type: application/json' -d "$2"
}

clear 2>/dev/null || true
printf '%sCampusDesk%s  %s%s%s\n' "$BOLD" "$RESET" "$DIM" "$SITE" "$RESET"

title "1. Is the portal up, and can it reach Freshdesk?"
pause
run "curl -s $SITE/health | pretty"

title "2. A student reports a blocked toilet"
printf '%sThe request never says which department.%s\n' "$DIM" "$RESET"
pause
REPORT='{"name":"Lwin Pyae Aung","email":"'"$EMAIL"'","location":"VMS Building, 3rd floor restroom","subject":"Toilet blocked on 3rd floor","description":"The toilet in the third floor restroom is blocked and water is not draining."}'
CREATED="$(post "$SITE/api/reports" "$REPORT")"
printf '\n%s$ curl -s -X POST %s/api/reports -d @toilet.json%s\n\n' "$BLUE" "$SITE" "$RESET"
printf '%s' "$CREATED" | pretty

TICKET="$(printf '%s' "$CREATED" | sed -n 's/.*"ticket_id"[: ]*\([0-9]*\).*/\1/p')"
if [ -z "$TICKET" ]; then
  printf '\n%sNo ticket was created. Check the server and try again.%s\n' "$RED" "$RESET"
  exit 1
fi
printf '\n%sFreshdesk chose the department. Ticket %s.%s\n' "$GREEN" "$TICKET" "$RESET"

title "3. An urgent one: same command, different words"
pause
LEAK='{"name":"Lwin Pyae Aung","email":"'"$EMAIL"'","location":"CL Building, room 201","subject":"Water leak from ceiling","description":"Water is dripping from the ceiling next to the whiteboard. There is a puddle on the floor."}'
printf '\n%s$ curl -s -X POST %s/api/reports -d @leak.json%s\n\n' "$BLUE" "$SITE" "$RESET"
post "$SITE/api/reports" "$LEAK" | pretty

title "4. Now change ticket $TICKET to In Progress in Freshdesk"
printf '%sOpen the ticket, set the status, then come back.%s\n' "$DIM" "$RESET"
pause

title "5. The student follows the report"
pause
printf '\n%s$ curl -s -X POST %s/api/reports/%s/track -d %s{"email":"%s"}%s%s\n\n' "$BLUE" "$SITE" "$TICKET" "$Q" "$EMAIL" "$Q" "$RESET"
post "$SITE/api/reports/$TICKET/track" "{\"email\":\"$EMAIL\"}" | pretty

title "6. What the staff see"
pause
run "curl -s $SITE/api/dashboard | summary"

printf '\n%sThat is CampusDesk.%s\n\n' "$BOLD" "$RESET"
