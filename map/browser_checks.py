"""Run browser integration checks with real Leaflet, an in-memory DB, and a temporary Chrome profile.

Run from the project root: python -B map/browser_checks.py
Requires Chrome/Chromium and network access to the pinned Leaflet assets.
Geolocation and map tiles are simulated; no development database is changed.
"""


def main():
    import base64, hashlib, html, json, os, re, shutil, subprocess, sys, tempfile, threading, urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path
    from urllib.parse import parse_qs, unquote, urlsplit

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    import django
    from django.conf import settings
    settings.DATABASES["default"]["NAME"] = "file:map_browser_checks?mode=memory&cache=shared"
    settings.DATABASES["default"]["OPTIONS"] = {"uri": True}
    # Only the test harness embeds the page in a same-origin iframe.
    # Django regression tests verify that production still sends X-Frame-Options: DENY.
    settings.X_FRAME_OPTIONS = "SAMEORIGIN"
    django.setup()
    from django.contrib.staticfiles import finders
    from django.core.management import call_command
    from django.test import Client
    from food.models import Restaurant, SurpriseBox
    from map.models import RestaurantMapProfile

    call_command("migrate", verbosity=0)
    for number, name, lng, stock, _ in [
        (1, "A Available", 0, 3, False),
        (2, "B Sold Out", .005, 0, False),
        (3, "C Nearby", .005, 2, False),
        (4, "D Distant", .02, 1, False),
    ]:
        restaurant = Restaurant.objects.create(id=number, nama=name, alamat="Audit address", lat=0, lng=lng)
        SurpriseBox.objects.create(
            restaurant=restaurant, nama_paket="Test", stok=stock,
            harga_normal=40000, harga_diskon=12000,
        )
    RestaurantMapProfile.objects.create(restaurant_id=1, image_url="https://example.invalid/photo.jpg")
    assets = {}
    for name, checksum in [
        ("leaflet.js", "20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="),
        ("leaflet.css", "p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="),
    ]:
        with urllib.request.urlopen("https://unpkg.com/leaflet@1.9.4/dist/" + name, timeout=20) as response:
            assets[name] = response.read()
        assert base64.b64encode(hashlib.sha256(assets[name]).digest()).decode() == checksum
    checks = Path(__file__).with_suffix(".js").read_text(encoding="utf-8")
    setup = """
    window.geoRequests = [];
    window.jsErrors = [];
    window.addEventListener('error', event => { if (event.message) window.jsErrors.push(event.message); });
    const mode = new URLSearchParams(location.search).get('case');
    Object.defineProperty(navigator, 'geolocation', {value: mode === 'no_geo' ? undefined : {
        getCurrentPosition(success, error, options) {
            if (mode === 'geo_throw') throw new Error('Geolocation blocked');
            window.geoRequests.push({success, error, options});
        }
    }});
    if (mode === 'insecure') Object.defineProperty(window, 'isSecureContext', {value: false});
    const originalFetch = window.fetch.bind(window);
    window.fetch = (url, options) => window.failRefresh && String(url).includes('/map/restaurants/')
        ? Promise.reject(new Error('Simulated network failure')) : originalFetch(url, options);
    """
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")

    tile_requests = []

    class TileHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            tile_requests.append({
                "path": self.path,
                "referer": self.headers.get("Referer"),
                "user_agent": self.headers.get("User-Agent"),
                "cache_control": self.headers.get("Cache-Control"),
                "pragma": self.headers.get("Pragma"),
            })
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "public, max-age=604800")
            self.send_header("Content-Length", str(len(pixel)))
            self.end_headers()
            self.wfile.write(pixel)

    # A different port makes the tile server cross-origin, as OSM is in production.
    # Browser tests never request or prefetch any tiles from OSM's public servers.
    tile_server = ThreadingHTTPServer(("127.0.0.1", 0), TileHandler)
    threading.Thread(target=tile_server.serve_forever, daemon=True).start()
    tile_origin = "http://127.0.0.1:%d" % tile_server.server_port
    tile_override = (
        "window.tileTestOrigin=" + json.dumps(tile_origin) + ";"
        "const realTileLayer=L.tileLayer;"
        "L.tileLayer=(url,options)=>{window.tileConfiguration={url,options};"
        "return realTileLayer(window.tileTestOrigin+'/__tile/{z}/{x}/{y}',options);};"
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            status, content_type = 200, "text/html; charset=utf-8"
            response_headers = {}
            if path == "/__checks/":
                body = ('<!doctype html><meta charset="utf-8"><pre id="result" data-state="running"></pre>'
                        '<script>' + checks + '</script>').encode()
            elif path == "/__tile_requests/":
                body, content_type = json.dumps(tile_requests).encode(), "application/json"
            elif path == "/__tile_override.js":
                body, content_type = tile_override.encode(), "text/javascript"
            elif path in ("/__leaflet.js", "/__leaflet.css"):
                name = path.removeprefix("/__")
                body = assets[name]
                content_type = "text/javascript" if name.endswith(".js") else "text/css"
            elif path.startswith("/static/"):
                source = finders.find(path.removeprefix("/static/"))
                if source:
                    body = Path(source).read_bytes()
                    content_type = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}.get(Path(source).suffix, "application/octet-stream")
                else:
                    body, status = b"", 404
            elif path == "/__sold_out/":
                SurpriseBox.objects.filter(restaurant_id=1).update(stok=0)
                body, content_type = b"{}", "application/json"
            else:
                response = Client().get(path)
                status = response.status_code
                response_headers = dict(response.headers)
                content_type = response.get("Content-Type", content_type)
                body = response.content
                if path == "/map/":
                    page = body.decode()
                    page = re.sub(r'<link[^>]*href="https://fonts\.[^"]*"[^>]*>', "", page)
                    page = page.replace("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js", "/__leaflet.js")
                    page = page.replace("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", "/__leaflet.css")
                    page = page.replace("</head>", "<script>" + setup + "</script></head>")
                    page = page.replace('<script src="/static/map/map.js"', '<script src="/__tile_override.js" defer></script><script src="/static/map/map.js"')
                    if parse_qs(parsed.query).get("case") == ["no_leaflet"]:
                        page = re.sub(r'<script src="/__leaflet.js"[\s\S]*?</script>', "", page)
                        page = page.replace('<script src="/__tile_override.js" defer></script>', "")
                    body = page.encode()
            self.send_response(status)
            # Keep the real Django security headers; dropping them masks referrer bugs.
            for header, value in response_headers.items():
                if header.lower() not in ("content-type", "content-length"):
                    self.send_header(header, value)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    chrome = (os.environ.get("CHROME_BINARY") or shutil.which("google-chrome")
              or shutil.which("chromium") or r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not Path(chrome).exists():
        raise SystemExit("Set CHROME_BINARY to an installed Chrome/Chromium executable.")
    try:
        with tempfile.TemporaryDirectory(prefix="dibuang-map-browser-", ignore_cleanup_errors=True) as profile:
            assert Path(profile).resolve().parent == Path(tempfile.gettempdir()).resolve()
            process = subprocess.run([
                str(chrome), "--headless=new", "--disable-gpu", "--no-first-run",
                "--no-default-browser-check", "--disable-background-networking",
                "--disable-extensions", "--user-data-dir=" + profile,
                "--host-resolver-rules=MAP example.invalid 127.0.0.1",
                "--dump-dom", "--virtual-time-budget=20000",
                "http://127.0.0.1:%d/__checks/" % server.server_port,
            ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            match = re.search(r'<pre id="result" data-state="([^"]+)">(.*?)</pre>', process.stdout, re.S)
            if not match:
                print(process.stdout[:2000])
                print(process.stderr[-2000:])
                raise SystemExit("Browser did not produce a test result")
            print(match.group(1), html.unescape(match.group(2)))
            if match.group(1) != "passed":
                raise SystemExit(1)
    finally:
        server.shutdown()
        server.server_close()
        tile_server.shutdown()
        tile_server.server_close()


if __name__ == "__main__":
    main()
