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
        for _ in proc.stdout:
            pass
    except KeyboardInterrupt:
        print("\nStopping tunnel.")
    finally:
        proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
