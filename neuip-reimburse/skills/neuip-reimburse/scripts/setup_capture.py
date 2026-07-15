"""One-time interactive capture of nueip auth + endpoints.

Opens a headed browser and lets the user log in and submit ONE claim manually.
It records network traffic and cookies incrementally to capture_raw.json, and
finishes when the user CLOSES the browser window (no stdin needed — the tool
that launches this has no interactive terminal). Claude then helps the user
turn the capture into config.json + auth.json.
"""
import argparse
import base64
import json
import os

from playwright.sync_api import sync_playwright

from scripts import neuip_client

RAW_PATH = os.path.join(neuip_client.CONFIG_DIR, "capture_raw.json")


def _persist(calls, cookies):
    os.makedirs(neuip_client.CONFIG_DIR, exist_ok=True)
    tmp = RAW_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"calls": calls, "cookies": cookies}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RAW_PATH)
    os.chmod(RAW_PATH, 0o600)


def capture(base_url: str) -> dict:
    calls = []
    cookies = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        def on_response(resp):
            req = resp.request
            if req.resource_type in ("xhr", "fetch") or req.method == "POST":
                entry = {"method": req.method, "url": req.url,
                         "status": resp.status, "resource_type": req.resource_type}
                # capture request headers so we can see auth/csrf mechanism
                try:
                    entry["headers"] = dict(req.headers)
                except Exception:
                    entry["headers"] = {}
                # capture request post data (text form) so field names are visible
                try:
                    entry["post_data"] = req.post_data
                except Exception:
                    entry["post_data"] = None
                # capture raw body buffer (base64) for multipart/file submits
                try:
                    buf = req.post_data_buffer
                    entry["post_data_b64"] = base64.b64encode(buf).decode() if buf else None
                except Exception:
                    entry["post_data_b64"] = None
                calls.append(entry)
                _persist(calls, cookies)

        page.on("response", on_response)
        page.goto(base_url)
        print("\n瀏覽器已開啟。請在視窗內：")
        print("  1) 手動登入 nueip（帳密/2FA 都在瀏覽器操作，本工具看不到）。")
        print("  2) 手動實際送出一筆請款作為範本（這樣才抓得到送出 endpoint 與欄位）。")
        print("  3) 完成後直接【關閉整個瀏覽器視窗】即可，無需回到終端機。\n")
        print("擷取進行中…（關閉視窗後自動結束）")

        # Finish when the user closes the browser window. Refresh cookies while alive.
        while browser.is_connected():
            try:
                cookies = {c["name"]: c["value"] for c in context.cookies()}
                _persist(calls, cookies)
                page.wait_for_timeout(1000)
            except Exception:
                break
    _persist(calls, cookies)
    return {"calls": calls, "cookies": cookies}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    args = ap.parse_args(argv)

    data = capture(args.base_url)
    print("\n擷取到的候選 API 呼叫：")
    for i, c in enumerate(data["calls"]):
        print(f"  [{i}] {c['method']} {c['status']} {c['url']}")
    print(f"\n共 {len(data['calls'])} 筆呼叫、{len(data['cookies'])} 個 cookie。")
    print(f"原始擷取已存到 {RAW_PATH}")
    print("接下來回到 Claude，由它依這份資料協助你確認 endpoints/欄位並寫入設定。")
    return data


if __name__ == "__main__":
    main()
