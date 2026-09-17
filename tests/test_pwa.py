"""The phone surface.

CALIPER is demonstrated on a phone: a judge scans a code on the table, the page
opens without browser chrome, and the practice call runs there. Everything that
makes that work lives in files no Python test would otherwise look at, and every
one of them fails silently.

The three failure shapes these tests exist to catch, all of which are invisible
on a developer laptop:

  the manifest promises an icon that is not there, or is not the size it claims
  the safe area CSS is present but the meta tag that activates it is not
  a client route 404s, or worse, everything 404s into the shell
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from caliper.api.main import _SPAFiles

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
INDEX = ROOT / "frontend" / "index.html"
APP_CSS = ROOT / "frontend" / "src" / "styles" / "app.css"


def test_manifest_parses_and_describes_the_product() -> None:
    manifest = json.loads((PUBLIC / "manifest.webmanifest").read_text())

    assert manifest["display"] == "standalone", "without standalone it opens in browser chrome"
    assert manifest["short_name"] == "CALIPER"
    assert manifest["scope"] == "/"
    assert manifest["start_url"].startswith("/")

    # A maskable icon is what stops Android cropping the mark to a stump.
    purposes = {i.get("purpose") for i in manifest["icons"]}
    assert "any" in purposes and "maskable" in purposes, purposes


def test_every_icon_the_manifest_promises_exists_at_the_size_it_claims() -> None:
    """The filename is not evidence. The pixels are.

    A manifest entry saying 512x512 beside a file that is 192x192 installs a
    blurry icon and reports nothing.
    """
    manifest = json.loads((PUBLIC / "manifest.webmanifest").read_text())
    assert manifest["icons"], "a manifest with no icons is not installable"

    for entry in manifest["icons"]:
        path = PUBLIC / entry["src"].lstrip("/")
        assert path.is_file(), f"{entry['src']} is promised by the manifest and is not on disk"

        declared = tuple(int(n) for n in entry["sizes"].split("x"))
        with Image.open(path) as im:
            assert im.size == declared, f"{entry['src']} is {im.size}, manifest says {declared}"

    # iOS ignores the manifest entirely and reads this one from the markup.
    with Image.open(PUBLIC / "apple-touch-icon.png") as im:
        assert im.size == (180, 180), im.size
        # iOS composites a transparent icon onto black and rounds it itself, so
        # a transparent mark loses its ground.
        assert im.getpixel((2, 2))[3] == 255, "the apple touch icon must be opaque"


def test_every_shortcut_points_at_a_route_the_app_actually_serves() -> None:
    """A shortcut to a path nothing handles is a dead tile on a home screen."""
    manifest = json.loads((PUBLIC / "manifest.webmanifest").read_text())
    app_tsx = (ROOT / "frontend" / "src" / "App.tsx").read_text()

    for shortcut in manifest.get("shortcuts", []):
        url = shortcut["url"]
        path = url.split("?", 1)[0]
        query = url.split("?", 1)[1] if "?" in url else ""

        if path == "/judge":
            continue  # server rendered, covered by tests/test_judge_door.py
        if path == "/":
            assert "screen=practice" not in query or 'params.get("screen")' in app_tsx
            continue

        # Any other path has to be a client route the shell recognises.
        assert f'=== "{path}"' in app_tsx or f'"{path}"' in app_tsx, (
            f"shortcut {url} points at {path}, which App.tsx does not recognise"
        )


def test_the_safe_area_css_and_the_meta_tag_that_activates_it_ship_together() -> None:
    """One is useless without the other, and neither failing is visible.

    env(safe-area-inset-*) resolves to zero unless the viewport meta carries
    viewport-fit=cover. Shipping the CSS alone looks like the notch was handled
    and does nothing at all.
    """
    css = APP_CSS.read_text()
    html = INDEX.read_text()

    uses_insets = "env(safe-area-inset-" in css
    activates = "viewport-fit=cover" in html

    assert uses_insets, "no safe area insets: the home indicator will sit on the content"
    assert activates, "safe area CSS is present but viewport-fit=cover is not, so it does nothing"

    # The bottom inset is the one that matters in portrait, which is how a phone
    # is held for a call.
    assert "env(safe-area-inset-bottom)" in css


def test_index_html_declares_what_a_phone_needs() -> None:
    html = INDEX.read_text()

    assert "<title>CALIPER" in html, "the tab and the home screen tile read this"
    assert "frontend</title>" not in html, "the scaffold title must not reach a judge"
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    assert 'name="theme-color"' in html
    # iOS reads the vendor prefixed name; everybody else reads the standard one.
    assert 'name="apple-mobile-web-app-capable"' in html
    assert 'name="mobile-web-app-capable"' in html


def test_the_service_worker_never_caches_the_api_or_the_socket() -> None:
    """The product's claim is that nothing on screen is stale or mocked.

    A cached API response makes that claim false, and it would be invisible:
    the page renders, the numbers look plausible, and they are yesterday's.
    """
    sw = (PUBLIC / "sw.js").read_text()

    assert "NEVER_CACHE" in sw
    for prefix in ('"/api/"', '"/ws"', '"/judge"'):
        assert prefix in sw, f"{prefix} is not excluded from the cache"

    # A worker that waits for every tab to close can serve the previous build
    # alongside a new backend.
    assert "skipWaiting" in sw
    assert "clients.claim" in sw


def _fallback_client(tmp_path: Path) -> TestClient:
    """Mount the real fallback class over a throwaway dist.

    Building the interface is not a precondition for testing the routing rule,
    and making it one would mean this test skips wherever the build has not run,
    which is a false green rather than a pass.
    """
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>shell</title>")
    (tmp_path / "icon-192.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    app = FastAPI()

    @app.get("/api/real")
    def real() -> dict:
        return {"ok": True}

    app.mount("/", _SPAFiles(directory=str(tmp_path), html=True), name="interface")
    return TestClient(app)


def test_a_client_route_gets_the_shell(tmp_path: Path) -> None:
    c = _fallback_client(tmp_path)
    r = c.get("/practice")
    assert r.status_code == 200
    assert "shell" in r.text


def test_a_real_file_is_still_served_normally(tmp_path: Path) -> None:
    c = _fallback_client(tmp_path)
    assert c.get("/icon-192.png").status_code == 200
    assert c.get("/api/real").json() == {"ok": True}


@pytest.mark.parametrize("path", ["/api/nope", "/api/runs/does-not-exist"])
def test_a_bogus_api_path_keeps_its_404(tmp_path: Path, path: str) -> None:
    """Serving the shell here would turn a 404 into an HTML 200.

    A caller checking the status code would then conclude the endpoint exists.
    """
    c = _fallback_client(tmp_path)
    r = c.get(path)
    assert r.status_code == 404, f"{path} was rescued into the shell"
    assert "shell" not in r.text


@pytest.mark.parametrize("path", ["/missing.png", "/assets/gone.js", "/nested/thing.css"])
def test_a_missing_file_keeps_its_404(tmp_path: Path, path: str) -> None:
    """Otherwise the service worker caches a page under an image URL and the
    failure becomes sticky across reloads."""
    c = _fallback_client(tmp_path)
    r = c.get(path)
    assert r.status_code == 404, f"{path} was rescued into the shell"
