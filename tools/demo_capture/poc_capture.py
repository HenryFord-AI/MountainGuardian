from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://mountainguardian.cn"
OUT = Path("artifacts/demo_capture")
OUT.mkdir(parents=True, exist_ok=True)

NAV_TARGETS = {
    "overview": [r"Overview", r"总览"],
    "historical": [r"Historical Replay", r"历史验证", r"历史回放"],
    "risk_watch": [r"Risk Watch", r"风险监测"],
    "intelligence": [r"Intelligence Center", r"智能中心", r"情报中心"],
}


def wait_for_app(page, seconds: float = 8.0) -> None:
    try:
        page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=20000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(int(seconds * 1000))


def clean_ui(page) -> None:
    page.add_style_tag(
        content="""
        [data-testid="stToolbar"], [data-testid="stDecoration"],
        header[data-testid="stHeader"], footer { display:none !important; }
        body { cursor: default !important; }
        """
    )


def screenshot(page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def click_by_text(page, patterns: list[str]) -> bool:
    for pattern in patterns:
        regex = re.compile(pattern, re.I)
        # Prefer sidebar to avoid clicking content cards with the same wording.
        for scope in [page.locator('[data-testid="stSidebar"]'), page.locator("body")]:
            for role in ["button", "link"]:
                try:
                    locator = scope.get_by_role(role, name=regex)
                    if locator.count() > 0:
                        locator.first.click(timeout=5000)
                        page.wait_for_timeout(3500)
                        return True
                except Exception:
                    pass
            try:
                locator = scope.get_by_text(regex, exact=False)
                if locator.count() > 0:
                    locator.first.click(timeout=5000)
                    page.wait_for_timeout(3500)
                    return True
            except Exception:
                pass
    return False


def main() -> None:
    report: dict[str, object] = {
        "url": BASE_URL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "steps": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            record_video_dir=str(OUT / "video_raw"),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.set_default_timeout(10000)

        try:
            resp = page.goto(BASE_URL, wait_until="domcontentloaded", timeout=45000)
            report["http_status"] = resp.status if resp else None
            wait_for_app(page)
            clean_ui(page)
            screenshot(page, "01_overview")
            report["steps"].append({"name": "overview", "ok": True})

            # Let the overview breathe on video.
            page.wait_for_timeout(4500)

            # Historical Replay
            ok = click_by_text(page, NAV_TARGETS["historical"])
            wait_for_app(page, 2.0)
            screenshot(page, "02_historical_replay")
            report["steps"].append({"name": "historical_replay", "ok": ok})
            page.wait_for_timeout(5000)

            # Risk Watch and a real scan attempt.
            ok = click_by_text(page, NAV_TARGETS["risk_watch"])
            wait_for_app(page, 2.0)
            screenshot(page, "03_risk_watch_before")
            report["steps"].append({"name": "risk_watch", "ok": ok})

            scan_clicked = False
            for label in [r"Run Risk Scan", r"立即执行风险扫描", r"执行风险扫描", r"立即扫描"]:
                try:
                    btn = page.get_by_role("button", name=re.compile(label, re.I))
                    if btn.count() > 0 and btn.first.is_enabled():
                        btn.first.click(timeout=5000)
                        scan_clicked = True
                        break
                except Exception:
                    pass
            report["scan_clicked"] = scan_clicked

            if scan_clicked:
                # Capture progression without assuming exact runtime text.
                page.wait_for_timeout(3500)
                screenshot(page, "04_risk_watch_running")
                page.wait_for_timeout(12000)
                screenshot(page, "05_risk_watch_mid")
                page.wait_for_timeout(18000)
                screenshot(page, "06_risk_watch_after")
            else:
                page.wait_for_timeout(5000)

            # Intelligence Center
            ok = click_by_text(page, NAV_TARGETS["intelligence"])
            wait_for_app(page, 2.0)
            screenshot(page, "07_intelligence_center")
            report["steps"].append({"name": "intelligence_center", "ok": ok})
            page.wait_for_timeout(4500)

            # Try to capture Evidence / Audit tabs if present.
            for name, patterns in [
                ("08_evidence_center", [r"Evidence Center", r"证据中心"]),
                ("09_audit_safety", [r"Audit\s*&\s*Safety", r"Audit and Safety", r"审计", r"安全"]),
            ]:
                clicked = click_by_text(page, patterns)
                page.wait_for_timeout(2000)
                screenshot(page, name)
                report["steps"].append({"name": name, "ok": clicked})

            # Final hero frame back on Overview if possible.
            click_by_text(page, NAV_TARGETS["overview"])
            wait_for_app(page, 2.0)
            screenshot(page, "10_overview_end")
            page.wait_for_timeout(3500)

            report["title"] = page.title()
            report["final_url"] = page.url
            report["body_excerpt"] = page.locator("body").inner_text()[:5000]
        except Exception as exc:
            report["fatal_error"] = repr(exc)
            try:
                screenshot(page, "99_failure")
                report["body_excerpt"] = page.locator("body").inner_text()[:5000]
            except Exception:
                pass
        finally:
            video = page.video
            context.close()
            try:
                raw_path = Path(video.path())
                target = OUT / "poc_full_session.webm"
                if raw_path.exists() and raw_path != target:
                    raw_path.replace(target)
                report["video"] = str(target)
            except Exception as exc:
                report["video_error"] = repr(exc)
            browser.close()

    (OUT / "capture_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
