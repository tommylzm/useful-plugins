"""Interactive re-login when the stored nueip cookie has expired.

Opens a headed browser on the nueip login page, waits until the user has
logged in (verified by an authenticated API call, not just a URL change),
then closes the browser on its own and hands back fresh cookies.

Used automatically by submit_claim on a 401; can also be run directly:
    cd <skill> && ~/.config/neuip-reimburse/venv/bin/python -m scripts.login
"""
import argparse
import datetime
import json
import sys
import time
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from scripts import neuip_client

DEFAULT_LOGIN_URL = "https://portal.nueip.com/login"
DEFAULT_TIMEOUT_S = 300


def _should_probe(url: str) -> bool:
    """Only hit the API once the page is on nueip and past the login screen,
    so we never poke the server mid-login (SSO hops, /login itself)."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if not (host == "nueip.com" or host.endswith(".nueip.com")):
        return False
    return not parts.path.startswith("/login")


def probe(context, cfg) -> bool:
    """True if the browser's cookies are accepted by the same endpoint submit uses."""
    url = cfg["base_url"] + cfg["endpoints"]["submit"]["path"]
    cookies = {c["name"]: c["value"] for c in context.cookies(cfg["base_url"])}
    headers = dict(cfg.get("headers", {}))
    csrf = cfg.get("csrf")
    if csrf and csrf.get("cookie") in cookies:
        headers[csrf["header"]] = cookies[csrf["cookie"]]
    form = {"action": "get_payroll_options", "startDate": datetime.date.today().isoformat()}
    resp = context.request.post(url, form=form, headers=headers)
    if resp.status != 200:
        return False
    try:
        return isinstance(resp.json(), list)
    except ValueError:      # redirected to an HTML login page
        return False


def _wait_for_login(context, cfg, timeout_s, alive, poll_ms=1500, clock=time.monotonic) -> bool:
    """Poll until logged in (True), or the window is closed / time runs out (False)."""
    deadline = clock() + timeout_s
    while clock() < deadline:
        pages = context.pages
        if not alive() or not pages:
            return False
        try:
            if any(_should_probe(p.url) for p in pages) and probe(context, cfg):
                return True
            pages[0].wait_for_timeout(poll_ms)
        except PlaywrightError:
            # a page closed mid-poll; the next iteration re-checks what is left
            continue
    return False


def interactive_login(cfg, timeout_s=DEFAULT_TIMEOUT_S):
    """Return a fresh {"kind":"cookie",...} auth, or None if the user gave up."""
    login_url = cfg.get("login_url", DEFAULT_LOGIN_URL)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(login_url)
            print(f"已開啟 nueip 登入視窗，請在 {timeout_s // 60} 分鐘內登入；"
                  "登入完成後視窗會自動關閉。", file=sys.stderr, flush=True)
            if not _wait_for_login(context, cfg, timeout_s, alive=browser.is_connected):
                return None
            cookies = {c["name"]: c["value"] for c in context.cookies()}
            return {"kind": "cookie", "cookies": cookies}
        finally:
            browser.close()


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    args = ap.parse_args(argv)

    auth = interactive_login(neuip_client.load_config(), timeout_s=args.timeout)
    if auth is None:
        result = {"error": "login_abandoned"}
    else:
        neuip_client.save_auth(auth)
        result = {"ok": True, "cookies": len(auth["cookies"])}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    sys.exit(0 if main().get("ok") else 1)
