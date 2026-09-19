"""Open a public HTTPS tunnel AND point the Freshdesk webhook at it.

    make tunnel          (or: python -m scripts.tunnel)

A cloudflared quick tunnel gets a new random address every time it starts,
and the Freshdesk "Push status to portal" rule must always point at the
current one. Doing that by hand is exactly the step that gets forgotten
five minutes before presenting, so this script does both:

  1. starts `cloudflared tunnel --url http://localhost:8000`
  2. reads the https://....trycloudflare.com address it prints
  3. updates the webhook rule through the Freshdesk API
  4. keeps the tunnel running until you press Ctrl-C

Start the portal first (make run), in another terminal.
"""
import re
import shutil
import subprocess
import sys
import time

from app.freshdesk import FreshdeskError, from_env
from scripts.setup_freshdesk import set_webhook

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def find_tunnel_url(line: str) -> str | None:
    m = URL_RE.search(line)
    return m.group(0) if m else None


def main(port: int = 8000) -> int:
    if not shutil.which("cloudflared"):
        print("cloudflared is not installed. On a Mac:  brew install cloudflared")
        return 1

    proc = subprocess.Popen(["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url, deadline = None, time.monotonic() + 60
    try:
        for line in proc.stdout:
            url = url or find_tunnel_url(line)
            if url and "Registered tunnel connection" in line:
                break
            if time.monotonic() > deadline:
                break
        if not url:
            print("cloudflared did not print a tunnel address. Is the internet up?")
            proc.terminate()
            return 1

        print(f"Tunnel: {url}  ->  http://localhost:{port}")
        try:
            set_webhook(from_env(), url)
        except (ValueError, FreshdeskError) as exc:
            print(f"Tunnel is up, but the Freshdesk webhook was NOT updated: {exc}")
        print("\nStatus changes in Freshdesk now reach the portal. "
              "Leave this running; Ctrl-C to stop.")
        for _ in proc.stdout:          # keep reading so cloudflared never blocks
            pass
    except KeyboardInterrupt:
        print("\nStopping tunnel.")
    finally:
        proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
