"""Assert a tunnel URL serves a backend that can actually take a spoken call.

Two failure modes look identical from a single probe and mean opposite things.

A fresh cloudflared quick tunnel hands back a hostname before it resolves, and
probing it immediately makes macOS negative cache the NXDOMAIN, so every later
lookup on this machine keeps failing long after the record exists. That is a
stale local resolver, not a broken tunnel, and a phone on a different resolver
would reach it perfectly. So on a resolution failure this falls back to a public
resolver and connects straight to that address with the right SNI, which tests
the tunnel itself rather than this laptop's cache.

A real answer of "speech unavailable" is never retried. That one is the truth,
and retrying it would only delay finding out.
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 90
PUBLIC_RESOLVER = "1.1.1.1"


def _public_resolve(host: str) -> str | None:
    """Resolve through a public resolver, bypassing the local cache."""
    try:
        out = subprocess.run(
            ["dig", "+short", "-t", "A", host, f"@{PUBLIC_RESOLVER}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.stdout.split():
        parts = line.strip().split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            return line.strip()
    return None


def _fetch_health(base: str) -> dict | None:
    """Return the health document, or None if the host could not be reached."""
    host = base.split("://", 1)[-1].split("/", 1)[0]
    request = urllib.request.Request(base.rstrip("/") + "/api/health", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, socket.gaierror, TimeoutError, OSError):
        pass

    address = _public_resolve(host)
    if address is None:
        return None
    try:
        context = ssl.create_default_context()
        connection = http.client.HTTPSConnection(address, 443, timeout=20, context=context)
        # SNI and Host must carry the tunnel hostname; the address is only how
        # we get there without asking the local resolver.
        connection.sock = None
        connection._create_connection = lambda *a, **k: socket.create_connection(  # type: ignore[method-assign]
            (address, 443), timeout=20
        )
        connection.host = host
        connection.connect()
        connection.request("GET", "/api/health", headers={"Host": host, "User-Agent": "Mozilla/5.0"})
        body = connection.getresponse().read()
        connection.close()
        return json.loads(body)
    except (OSError, ssl.SSLError, ValueError, json.JSONDecodeError):
        return None


def probe(base: str) -> int:
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        health = _fetch_health(base)
        if health is None:
            time.sleep(3)
            continue
        speech = health.get("speech") or {}
        if not speech.get("available"):
            print("tunnel is up but speech is NOT available, so the call would refuse")
            print(f"  reason: {speech.get('reason', 'not reported')}")
            return 1
        print(f"speech available through the tunnel, profile {speech.get('profile')}")
        print(f"  model: {health.get('voice_model')}")
        return 0
    print("tunnel never answered within the window")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: tunnel_probe.py <https://host>")
        raise SystemExit(2)
    raise SystemExit(probe(sys.argv[1]))
