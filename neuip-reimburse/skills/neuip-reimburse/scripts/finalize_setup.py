"""Lightweight setup finalizer (for installs where config.json already has the
API structure, i.e. seeded from config.template.json).

After the user logs in via setup_capture (which writes capture_raw.json), this:
  1. writes auth.json from the captured cookies (kind=cookie, chmod 600), and
  2. queries nueip's payroll options and prints the available 科目 name → code
     so the user can fill `categories` in ~/.config/neuip-reimburse/config.json.

It does NOT re-discover endpoints/fields — those are already in config.json.
Run from the skill dir (hits nueip with your own cookies):
    cd <skill> && ~/.config/neuip-reimburse/venv/bin/python -m scripts.finalize_setup
"""
import datetime
import json
import os
import urllib.parse
import urllib.request

from scripts import neuip_client

RAW = os.path.join(neuip_client.CONFIG_DIR, "capture_raw.json")


def _list_categories(cfg, cookies):
    csrf = cfg.get("csrf", {})
    cookie_hdr = "; ".join(f"{k}={v}" for k, v in cookies.items())
    today = datetime.date.today().isoformat()
    body = urllib.parse.urlencode({"action": "get_payroll_options", "startDate": today}).encode()
    url = cfg["base_url"] + cfg["endpoints"]["submit"]["path"]
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    if csrf.get("cookie") in cookies:
        req.add_header(csrf.get("header", "X-Csrf-Token"), cookies[csrf["cookie"]])
    for hk, hv in cfg.get("headers", {}).items():
        req.add_header(hk, hv)
    req.add_header("Cookie", cookie_hdr)
    with urllib.request.urlopen(req, timeout=20, context=neuip_client._SSL_CONTEXT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    if not os.path.exists(RAW):
        raise SystemExit("找不到 capture_raw.json —— 請先跑 setup_capture 登入。")
    cookies = json.load(open(RAW, encoding="utf-8"))["cookies"]

    neuip_client.save_auth({"kind": "cookie", "cookies": cookies})
    print(f"auth.json 已寫入（{len(cookies)} cookies, chmod 600）")

    cfg = neuip_client.load_config()
    try:
        options = _list_categories(cfg, cookies)
    except Exception as e:
        print(f"（科目查詢失敗，可稍後手動填 categories）：{e}")
        return

    print("\n此帳號可用科目（name → code）：")
    for item in options:
        sn = item.get("s_sn") or ""
        name = item.get("name") or item.get("item_name") or ""
        if sn:
            print(f"  {name}: {sn}")
    print("\n請把要報帳的科目填進 ~/.config/neuip-reimburse/config.json 的 categories，")
    print("每筆設定 name / neuip_category_code / cap（月上限）。")


if __name__ == "__main__":
    main()
