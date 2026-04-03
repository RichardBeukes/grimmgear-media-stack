"""
GrimmGear Media Stack — Playwright End-to-End Tests
Tests every endpoint, module toggle, database operations, and UI.
"""

import asyncio
import json
import subprocess
import time
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:7777"
RESULTS = {"passed": 0, "failed": 0, "errors": []}


def test(name, condition, detail=""):
    if condition:
        RESULTS["passed"] += 1
        print(f"  PASS  {name}")
    else:
        RESULTS["failed"] += 1
        RESULTS["errors"].append(f"{name}: {detail}")
        print(f"  FAIL  {name} — {detail}")


def get(path, expect_status=200):
    try:
        req = urllib.request.Request(f"{BASE}{path}")
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read().decode()
        status = resp.status
        return status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode() if hasattr(e, "read") else ""
    except Exception as e:
        return 0, str(e)


def post(path, data=None):
    try:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            f"{BASE}{path}",
            data=body,
            headers={"Content-Type": "application/json"} if body else {},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode() if hasattr(e, "read") else ""
    except Exception as e:
        return 0, str(e)


def get_json(path):
    status, body = get(path)
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body


def post_json(path, data=None):
    status, body = post(path, data)
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body


# ============================================================
# TEST SUITE
# ============================================================

def test_server_alive():
    print("\n--- Server Connectivity ---")
    status, body = get("/")
    test("Root URL returns 200", status == 200, f"got {status}")
    test("Root contains GrimmGear", "GrimmGear" in body, "missing title")
    test("Root contains module badges", "Movies" in body, "missing module")


def test_landing_page():
    print("\n--- Landing Page Content ---")
    status, body = get("/")
    test("Shows enabled modules", "Enabled Modules" in body or "ENABLED" in body, "missing section")
    test("Shows available modules", "Available Modules" in body or "AVAILABLE" in body, "missing section")
    test("Links to API docs", "/api/docs" in body, "missing docs link")
    test("Links to system status", "/api/system/status" in body, "missing status link")
    test("Links to health check", "/api/system/health" in body, "missing health link")
    test("Shows version", "v0.1.0" in body, "missing version")
    test("Shows tagline", "arr community" in body.lower() or "30+" in body, "missing tagline")
    test("Dark theme background", "#202020" in body, "missing dark bg")


def test_api_docs():
    print("\n--- API Documentation ---")
    status, _ = get("/api/docs")
    test("Swagger docs loads", status == 200, f"got {status}")

    status, _ = get("/api/redoc")
    test("ReDoc loads", status == 200, f"got {status}")

    status, body = get("/api/openapi.json")
    test("OpenAPI spec returns JSON", status == 200, f"got {status}")
    data = json.loads(body)
    test("OpenAPI has title", data.get("info", {}).get("title") == "GrimmGear Media Stack", f"got {data.get('info', {}).get('title')}")
    test("OpenAPI has paths", len(data.get("paths", {})) > 5, f"only {len(data.get('paths', {}))} paths")


def test_system_status():
    print("\n--- System Status ---")
    status, data = get_json("/api/system/status")
    test("Status endpoint returns 200", status == 200, f"got {status}")
    test("Has app_name", data.get("app_name") == "GrimmGear Media Stack", f"got {data.get('app_name')}")
    test("Has version", data.get("version") == "0.1.0", f"got {data.get('version')}")
    test("Has modules dict", isinstance(data.get("modules"), dict), f"type: {type(data.get('modules'))}")
    test("Has 10 modules", len(data.get("modules", {})) == 10, f"got {len(data.get('modules', {}))}")
    test("Database is sqlite", "sqlite" in data.get("database", ""), f"got {data.get('database')}")
    test("Media root is set", len(data.get("media_root", "")) > 0, "empty")
    test("Download dir is set", len(data.get("download_dir", "")) > 0, "empty")
    test("Media server type", data.get("media_server") == "built-in", f"got {data.get('media_server')}")


def test_health_check():
    print("\n--- Health Check ---")
    status, data = get_json("/api/system/health")
    test("Health endpoint returns 200", status == 200, f"got {status}")
    test("Status is healthy", data.get("status") == "healthy", f"got {data.get('status')}")
    test("Has checks dict", isinstance(data.get("checks"), dict), "missing checks")
    test("Database check exists", "database" in data.get("checks", {}), "no db check")
    test("Modules check exists", "modules" in data.get("checks", {}), "no module check")
    modules_check = data.get("checks", {}).get("modules", {})
    test("Total modules = 10", modules_check.get("total") == 10, f"got {modules_check.get('total')}")
    test("Enabled modules >= 4", modules_check.get("enabled", 0) >= 4, f"got {modules_check.get('enabled')}")


def test_module_registry():
    print("\n--- Module Registry ---")
    status, data = get_json("/api/modules")
    test("Modules endpoint returns 200", status == 200, f"got {status}")
    test("Returns dict", isinstance(data, dict), f"type: {type(data)}")

    expected = ["movies", "tv", "music", "books", "comics", "subtitles", "transcode", "requests", "indexers", "streaming"]
    for mod in expected:
        test(f"Module '{mod}' registered", mod in data, f"missing from registry")

    # Check default states
    test("Movies enabled by default", data.get("movies", {}).get("enabled") is True, "not enabled")
    test("TV enabled by default", data.get("tv", {}).get("enabled") is True, "not enabled")
    test("Indexers enabled by default", data.get("indexers", {}).get("enabled") is True, "not enabled")
    test("Streaming enabled by default", data.get("streaming", {}).get("enabled") is True, "not enabled")
    test("Music disabled by default", data.get("music", {}).get("enabled") is False, "enabled")
    test("Books disabled by default", data.get("books", {}).get("enabled") is False, "enabled")
    test("Comics disabled by default", data.get("comics", {}).get("enabled") is False, "enabled")

    # Check module metadata
    for mod_name, mod_data in data.items():
        test(f"Module '{mod_name}' has display_name", "display_name" in mod_data, "missing")
        test(f"Module '{mod_name}' has description", "description" in mod_data, "missing")
        test(f"Module '{mod_name}' has version", "version" in mod_data, "missing")


def test_module_toggle():
    print("\n--- Module Toggle ---")

    # Enable music
    status, data = post_json("/api/modules/music/enable")
    test("Enable music returns 200", status == 200, f"got {status}")
    test("Music enable success", data.get("enabled") is True, f"got {data}")

    # Verify it's on
    _, modules = get_json("/api/modules")
    test("Music now enabled", modules.get("music", {}).get("enabled") is True, "still disabled")

    # Enable books
    status, data = post_json("/api/modules/books/enable")
    test("Enable books returns 200", status == 200, f"got {status}")
    test("Books enable success", data.get("enabled") is True, f"got {data}")

    # Enable subtitles (depends on movies + tv which are ON)
    status, data = post_json("/api/modules/subtitles/enable")
    test("Enable subtitles (deps met)", data.get("enabled") is True, f"got {data}")

    # Disable music
    status, data = post_json("/api/modules/music/disable")
    test("Disable music returns 200", status == 200, f"got {status}")
    test("Music disable success", data.get("disabled") is True, f"got {data}")

    # Verify it's off
    _, modules = get_json("/api/modules")
    test("Music now disabled", modules.get("music", {}).get("enabled") is False, "still enabled")

    # Try enabling non-existent module
    status, data = post_json("/api/modules/fakename/enable")
    test("Fake module returns false", data.get("enabled") is False, f"got {data}")

    # Clean up - disable books and subtitles
    post_json("/api/modules/subtitles/disable")
    post_json("/api/modules/books/disable")


def test_movies_endpoint():
    print("\n--- Movies Endpoint ---")
    status, data = get_json("/api/movies")
    test("Movies returns 200", status == 200, f"got {status}")
    test("Movies returns list", isinstance(data, list), f"type: {type(data)}")
    test("Empty on fresh DB", len(data) == 0, f"got {len(data)} items")


def test_series_endpoint():
    print("\n--- Series Endpoint ---")
    status, data = get_json("/api/series")
    test("Series returns 200", status == 200, f"got {status}")
    test("Series returns list", isinstance(data, list), f"type: {type(data)}")
    test("Empty on fresh DB", len(data) == 0, f"got {len(data)} items")


def test_queue_endpoint():
    print("\n--- Download Queue ---")
    status, data = get_json("/api/queue")
    test("Queue returns 200", status == 200, f"got {status}")
    test("Queue returns list", isinstance(data, list), f"type: {type(data)}")
    test("Empty on fresh DB", len(data) == 0, f"got {len(data)} items")


def test_quality_profiles():
    print("\n--- Quality Profiles ---")
    status, data = get_json("/api/qualityprofiles")
    test("Profiles returns 200", status == 200, f"got {status}")
    test("Profiles returns list", isinstance(data, list), f"type: {type(data)}")


def test_indexers():
    print("\n--- Indexers ---")
    status, data = get_json("/api/indexers")
    test("Indexers returns 200", status == 200, f"got {status}")
    test("Indexers returns list", isinstance(data, list), f"type: {type(data)}")


def test_404_handling():
    print("\n--- Error Handling ---")
    status, _ = get("/api/nonexistent")
    test("Unknown API path returns 404", status == 404, f"got {status}")

    status, _ = get("/api/movies/99999")
    test("Unknown movie ID returns 404", status == 404, f"got {status}")


def test_cors_headers():
    print("\n--- CORS ---")
    try:
        req = urllib.request.Request(f"{BASE}/api/system/status")
        req.add_header("Origin", "http://example.com")
        resp = urllib.request.urlopen(req, timeout=10)
        cors = resp.headers.get("access-control-allow-origin", "")
        # FastAPI echoes the requesting origin when allow_credentials=True (per CORS spec)
        test("CORS allows requesting origin", cors in ("*", "http://example.com"), f"got '{cors}'")
    except Exception as e:
        test("CORS request succeeds", False, str(e))


# ============================================================
# PLAYWRIGHT BROWSER TESTS
# ============================================================

def test_browser():
    print("\n--- Playwright Browser Tests ---")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        test("Playwright available", False, "not installed — run: pip install playwright")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Landing page
        page.goto(f"{BASE}/")
        page.wait_for_timeout(2000)
        test("Page title contains GrimmGear", "GrimmGear" in page.title(), f"got '{page.title()}'")
        test("Page has content", page.locator("body").inner_text() != "", "empty body")
        test("Shows Movies badge", page.locator("text=Movies").count() > 0, "not found")
        test("Shows TV Shows badge", page.locator("text=TV Shows").count() > 0, "not found")
        test("Shows Streaming badge", page.locator("text=Streaming").count() > 0, "not found")
        test("Shows API Docs link", page.locator("text=API Docs").count() > 0, "not found")

        # Click API Docs link
        page.click("text=API Docs")
        page.wait_for_timeout(3000)
        test("Swagger UI loads", "swagger" in page.url or "docs" in page.url, f"url: {page.url}")
        test("Swagger has content", len(page.content()) > 1000, "too short")

        # Navigate to system status
        page.goto(f"{BASE}/api/system/status")
        page.wait_for_timeout(1000)
        content = page.inner_text("body")
        test("Status JSON visible", "GrimmGear" in content, "missing app name")
        test("Modules in status", "movies" in content, "missing movies")

        # Navigate to modules
        page.goto(f"{BASE}/api/modules")
        page.wait_for_timeout(1000)
        content = page.inner_text("body")
        test("Modules JSON visible", "display_name" in content, "missing display_name")
        test("All 10 modules listed", content.count("display_name") >= 10, f"found {content.count('display_name')}")

        # Screenshot
        page.goto(f"{BASE}/")
        page.wait_for_timeout(2000)
        page.screenshot(path="test-screenshot.png", full_page=True)
        test("Screenshot captured", True, "")

        browser.close()


# ============================================================
# RUN ALL TESTS
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  GrimmGear Media Stack — Test Suite")
    print("=" * 60)

    # Check server is running
    try:
        urllib.request.urlopen(f"{BASE}/", timeout=5)
    except Exception:
        print(f"\n  Server not running at {BASE}")
        print("  Start it with: cd backend && python run.py")
        sys.exit(1)

    # Run all test groups
    test_server_alive()
    test_landing_page()
    test_api_docs()
    test_system_status()
    test_health_check()
    test_module_registry()
    test_module_toggle()
    test_movies_endpoint()
    test_series_endpoint()
    test_queue_endpoint()
    test_quality_profiles()
    test_indexers()
    test_404_handling()
    test_cors_headers()
    test_browser()

    # Summary
    total = RESULTS["passed"] + RESULTS["failed"]
    print("\n" + "=" * 60)
    print(f"  Results: {RESULTS['passed']}/{total} passed, {RESULTS['failed']} failed")
    print("=" * 60)

    if RESULTS["errors"]:
        print("\n  Failures:")
        for err in RESULTS["errors"]:
            print(f"    - {err}")

    sys.exit(0 if RESULTS["failed"] == 0 else 1)
