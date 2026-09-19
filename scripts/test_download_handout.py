"""Opt-in live browser verification of the manual imagery download handout."""

import hashlib
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE_DOWNLOAD_TESTS") != "1",
                                reason="Set RUN_LIVE_DOWNLOAD_TESTS=1 for the 685 MB public download check")


def test_given_download_handout_when_used_then_all_original_files_download(tmp_path):
    from playwright.sync_api import sync_playwright

    report_root = Path(os.environ.get("DOWNLOAD_VERIFICATION_DIR", tmp_path / "verification"))
    report_root.mkdir(parents=True, exist_ok=True)
    report = {"downloads": [], "layouts": [], "retry": None}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900}, color_scheme="light")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto((ROOT / "docs/download-imagery.html").as_uri() + "?scoutTheme=light")
        page.get_by_role("status").filter(has_text="Ready:").wait_for(timeout=60000)
        page.locator("#preview").wait_for(state="visible", timeout=60000)
        buttons = page.get_by_role("button", name="Download", exact=False)
        assert buttons.count() == 6
        for button in buttons.all():
            filename = button.get_attribute("aria-label").removeprefix("Download ")
            with page.expect_download(timeout=60000) as event:
                button.click()
            download = event.value
            destination = tmp_path / filename
            download.save_as(destination)
            assert download.failure() is None
            assert download.suggested_filename == filename
            assert destination.stat().st_size > 0
            with destination.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            report["downloads"].append({"file": filename, "bytes": destination.stat().st_size, "sha256": digest})
        item = json.loads((tmp_path / "item.json").read_text())
        assert item["collection"] == "sentinel-2-l2a"
        for band in ("B04", "B08", "B11", "B12", "SCL"):
            assert "?" not in item["assets"][band]["href"]
        page.evaluate("window.scrollTo(0,0)")
        page.screenshot(path=str(report_root / "download-complete.png"), full_page=True)
        for width, height in ((1280, 900), (390, 844)):
            page.set_viewport_size({"width": width, "height": height})
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            assert page.locator("#preview").evaluate("image => image.naturalWidth > 0")
            report["layouts"].append({"width": width, "height": height, "overflow": False, "preview": "PASS"})
            page.screenshot(path=str(report_root / f"download-{width}.png"), full_page=True)
        page.route("**/api/stac/v1/collections/sentinel-2-l2a/items/*", lambda route: route.abort())
        page.reload()
        page.get_by_role("button", name="Retry connection").wait_for(state="visible")
        page.unroute("**/api/stac/v1/collections/sentinel-2-l2a/items/*")
        page.get_by_role("button", name="Retry connection").click()
        page.get_by_role("status").filter(has_text="Ready:").wait_for(timeout=60000)
        assert page.get_by_role("button", name="Download", exact=False).count() == 6
        report["retry"] = "PASS"
        assert errors == []
        browser.close()
    (report_root / "browser-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
