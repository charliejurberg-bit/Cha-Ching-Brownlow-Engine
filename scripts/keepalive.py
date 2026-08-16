#!/usr/bin/env python3
"""Keep-alive wake for the deployed Streamlit Cloud app.

A curl ping proves the edge answers, not that the app is up: Streamlit Cloud
serves the host page with a 200 while the app behind it is asleep, and the
"get this app back up" screen is itself a 200. This drives a real browser so a
sleeping app is actually woken, and so success means the Python script ran.

Structure of the deployed page, verified against the live DOM on 16 August 2026:
the bare app URL is NOT the app. That document has an empty <title>, no
stAppViewContainer and no app markup; it is Streamlit Cloud's host shell wrapping
the real app in an <iframe src=".../~/+/">. Everything asserted below is
therefore looked up inside that frame.

Readiness selector is `.st-key-ccnav_page`, the page-strip container stamped by
st.container(key="ccnav_page") in _render_page_nav(). It is chosen because it
cannot exist until the Python script has run and its output has come back over
the websocket, and because the page strip renders unconditionally, including for
an anonymous visitor. Deliberately NOT stAppViewContainer / stMain / #root: those
are the frontend's own chrome and mount as soon as the JS bundle boots, so they
would go green against a woken-but-broken app. The button count inside the strip
is asserted too, so an empty container cannot pass either.

Exits 0 on success, non-zero on any failure, printing the page title and URL.
"""

import re
import sys

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

APP_URL = "https://chachingbrownlow.streamlit.app/"

# Do not point this at /~/+/ directly. See the note in keepalive.yml: that suffix
# answers 400 from GitHub Actions runners while the app is healthy.
APP_FRAME = 'iframe[src*="/~/+/"]'
READY_SELECTOR = ".st-key-ccnav_page"
READY_CHILDREN = f'{READY_SELECTOR} [data-testid="stButton"]'

# Matches Streamlit's sleep screen: "Yes, get this app back up!". Kept loose
# (substring, case-insensitive) so a wording tweak upstream does not silently
# turn a wake into a timeout.
WAKE_TEXT = re.compile(r"get this app back up", re.I)

NAV_TIMEOUT_MS = 90_000      # host page; generous, the handshake is several hops
WAKE_TIMEOUT_MS = 10_000     # only long enough to decide the button is absent
READY_TIMEOUT_MS = 240_000   # a cold wake rebuilds the container, this is slow


def _fail(page, why):
    """Print what a maintainer needs to tell a sleeping app from a broken one."""
    print(f"FAIL: {why}", file=sys.stderr)
    try:
        print(f"  page title: {page.title()!r}", file=sys.stderr)
        print(f"  page url:   {page.url}", file=sys.stderr)
    except PWError as exc:
        print(f"  page unreadable: {exc}", file=sys.stderr)
    # The outer title is empty by design, so the frame's title is the useful one.
    try:
        frame = next((f for f in page.frames if "/~/+/" in (f.url or "")), None)
        if frame is None:
            print("  app iframe: NOT PRESENT (host shell only)", file=sys.stderr)
        else:
            print(f"  app iframe: {frame.url}", file=sys.stderr)
            print(f"  frame title: {frame.title()!r}", file=sys.stderr)
    except PWError as exc:
        print(f"  frame unreadable: {exc}", file=sys.stderr)
    return 1


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            # Both required on GitHub's runners: no sandbox without root-ish
            # privileges, and /dev/shm is too small for Chromium's default use.
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        try:
            page.goto(APP_URL, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)

            # Wake the app if Streamlit is showing the sleep screen. Absence of
            # the button is the normal case, not an error, so the short timeout
            # here is a probe rather than a wait.
            woke = False
            wake = page.locator("button, [role='button'], a").filter(
                has_text=WAKE_TEXT).first
            try:
                wake.wait_for(state="visible", timeout=WAKE_TIMEOUT_MS)
                wake.click()
                woke = True
                print("app was asleep, clicked the wake button")
            except PWTimeout:
                pass

            frame = page.frame_locator(APP_FRAME)
            frame.locator(READY_SELECTOR).first.wait_for(
                state="visible", timeout=READY_TIMEOUT_MS)
            pages = frame.locator(READY_CHILDREN).count()
            if pages < 1:
                return _fail(page, f"{READY_SELECTOR} rendered but is empty; "
                                   "the script ran without producing a page strip")

            print(f"OK: app rendered, {pages} page buttons in {READY_SELECTOR}"
                  f"{' (after wake)' if woke else ''}")
            return 0
        except PWTimeout as exc:
            return _fail(page, f"timed out waiting for the app: "
                               f"{str(exc).splitlines()[0]}")
        except PWError as exc:
            return _fail(page, f"playwright error: {str(exc).splitlines()[0]}")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
