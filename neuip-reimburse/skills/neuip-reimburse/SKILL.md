---
name: neuip-reimburse
description: Use when the user wants to file neuip 報帳/請款 from receipt images — archives images by year-month + category, merges each category into one sub-10MB PDF, recognizes and sums invoice amounts (user-confirmed, capped per category), and submits each claim to neuip via its API. Triggers like "/neuip-reimburse", "幫我報帳", "把這個月發票送 neuip".
---

# neuip-reimburse

把 `~/Documents/報帳/inbox/<分類>/` 的發票，依年月+分類歸檔、合併成 < 10MB PDF，
辨識並加總金額（套分類上限、你確認後）透過 neuip API 送出。

## 環境

- venv: `~/.config/neuip-reimburse/venv`（缺就先 `python3 -m venv ~/.config/neuip-reimburse/venv`
  並 `~/.config/neuip-reimburse/venv/bin/pip install -r <skill>/requirements.txt`，
  接著 `~/.config/neuip-reimburse/venv/bin/python -m playwright install chromium`）。
- `<skill>` = **此 skill 的 base directory（啟動時系統會告訴你絕對路徑，例如
  `~/.claude/skills/neuip-reimburse`）**。所有指令一律用這個實際 base dir，不要寫死他人路徑。
- 所有腳本從 skill 目錄以模組執行：
  `cd <skill> && ~/.config/neuip-reimburse/venv/bin/python -m scripts.<name> ...`
- 秘密只在 `~/.config/neuip-reimburse/`（config.json / auth.json），永不外流、不進 git。

## 指令解析

從使用者訊息解析參數：
- 年月：`-m 2026-06`；未給則用當月（以系統日期）。
- `--setup`：重新擷取登入。
- `--dry-run`：只辨識 + 產 PDF，不送出。
- `--yes`：跳過逐筆送出前確認（預設要確認）。

## 流程

### `--setup`：先判斷模式

先讀 `~/.config/neuip-reimburse/config.json`：
- **有 `endpoints.submit.path`（一般安裝者，config 由 `config.template.json` 產生）→ 走「輕量 setup」**。
- 沒有 config.json、或缺 `endpoints`（第一次逆向這個系統的開發者）→ 走「完整探索 setup」。

多數人是輕量 setup。**不需要重新逆向 API**——endpoint/欄位/csrf 已在 config 裡。

#### 輕量 setup（一般安裝者）
1. **登入取 cookie**：請使用者用 `!` 執行（此工具 bash 無互動 stdin，且會開瀏覽器）：
   `! cd <skill> && ~/.config/neuip-reimburse/venv/bin/python -m scripts.setup_capture --base-url https://portal.nueip.com/login`
   → 在瀏覽器登入自己的 nueip（登一次即可，不必送範本），然後**關閉瀏覽器視窗**結束。
2. **寫入 auth + 列出科目**：請使用者用 `!` 執行：
   `! cd <skill> && ~/.config/neuip-reimburse/venv/bin/python -m scripts.finalize_setup`
   → 這會把 cookie 寫進 `auth.json`（chmod 600），並印出該帳號可用的科目 `name → code`。
3. 依印出的清單，和使用者確認要報帳哪些科目，把 `name` / `neuip_category_code` / `cap`
   填進 `~/.config/neuip-reimburse/config.json` 的 `categories`（取代範本的佔位值）。
4. **授權 submit wrapper**（見下方步驟 4）。

#### 完整探索 setup（僅在缺 endpoints 時）
1. 問使用者 nueip base URL。
2. `! cd <skill> && ~/.config/neuip-reimburse/venv/bin/python -m scripts.setup_capture --base-url <url>`；
   使用者登入 + **手動送一筆範本**（才抓得到送出 endpoint），關閉視窗結束。
3. 讀 `capture_raw.json`，和使用者一起指認 login/submit endpoint、欄位對應、科目 code，
   寫入 `config.json`；cookies 以 `{"kind":"cookie","cookies":{…}}` 寫入 `auth.json`
   （用 `neuip_client.save_auth`，chmod 600）。可用 `finalize_setup` 完成 auth + 科目查詢。

#### 步驟 4（兩種模式都要，首次一次即可）
**授權 submit wrapper**：agent 無法自我擴權，所以**請使用者用 `!` 執行**：
`! python3 <skill>/scripts/grant_submit_permission.py`
這會 `chmod +x submit.sh` 並把 `Bash(<submit.sh 絕對路徑>:*)` 加進 `~/.claude/settings.json`
的 `permissions.allow`，之後 `submit.sh` 才能免逐筆核准直接送出。加完可能需 `/reload-plugins`
或重開 session 才生效。若 submit 仍被安全層擋下，代表這步沒做或尚未生效。

config.json 結構（已對 nueip 實測確定）：
- `base_url`: `https://cloud.nueip.com`
- `endpoints.submit`: `{method:"POST", path:"/payment_request"}`
- `submit_extra_fields`: `{"action":"add"}`（建立請款的固定欄位）
- `headers`: `{"X-Requested-With":"XMLHttpRequest"}`
- `csrf`: `{"cookie":"csrf_token","header":"X-Csrf-Token"}`（送出時把該 cookie 值放進此 header）
- `field_mapping`: `amount→pay`, `date→["start_date","end_date"]`, `reason→remark`,
  `category_code→p_sn`, `attachment→files[]`
- `categories`: `[{name,cap,neuip_category_code}]`
  （各科目 `neuip_category_code` 用下方 `get_payroll_options` 查詢取得；範本見 `config.template.json`）
- `archive_root`, `max_pdf_bytes`

認證：`auth.json = {"kind":"cookie","cookies":{…}}`。`neuip_client` 走 cookie 認證並自動
帶 `X-Csrf-Token`。SSL：`neuip_client` 已放寬 Python 3.14 的 `VERIFY_X509_STRICT`
（nueip 憑證缺 SKI 欄位），仍保有 CA/網域驗證。

科目代碼查詢（可用於未來動態比對或新增分類）：帶 cookie POST `payment_request`
`action=get_payroll_options&startDate=<YYYY-MM-DD>`，回傳陣列每筆的 `s_sn` 即 `p_sn`、
`name` 為科目名稱。

### 每次報帳
1. 決定年月與 `archive_root`（config 的 `archive_root`，預設 `~/Documents/報帳`）。
2. 列出 `<archive_root>/inbox/` 下有檔案的分類子資料夾。逐一處理每個分類：
   a. **辨識金額**：用 Read 工具讀該分類 inbox 內每張圖，辨識金額與日期。
   b. 顯示每張明細 + 加總；套上限（config 該分類 `cap`）：`送出金額 = min(加總, cap)`，
      超過上限用 ⚠️ 標示。
   c. **請使用者確認金額**，並輸入該分類「事由」；日期預設取辨識到的最新一張，可修改。
   d. 產 PDF：
      `python -m scripts.build_pdf --category <cat> --month <ym> --archive-root <root> --inbox <root>/inbox --max-bytes 10485760`
      （這步會把圖搬到 `<root>/<ym>/<cat>/` 並產 `claim.pdf`；回傳 JSON 含 pdf 路徑與 bytes。
      回傳 `skipped:true` 表示該分類沒圖，略過。）
3. **送出**（除非 `--dry-run`）：逐筆先列出將送出內容（分類/金額/日期/事由/PDF），
   除非 `--yes` 否則等使用者確認，再透過 allowlisted wrapper 執行（避免安全攔截）：
   `<skill>/submit.sh --pdf <pdf> --category <cat> --amount <amt> --date <date> --reason <reason> [--yes]`
   （用啟動時給你的實際 base dir 取代 `<skill>`；此路徑須與 `permissions.allow` 授權的路徑一致）。
   （此 wrapper 已在 `~/.claude/settings.json` 的 `permissions.allow` 授權，可直接送出、不需逐筆核准。
   `submit_claim` 內部會自動 `min(amount, cap)`，所以帶原始加總即可。）
   - **通勤補助 / 停車補助免事由** → `--reason ""`。
4. 若任何一筆回傳 `{"error":"auth_expired"}`：停止並提示使用者跑 `--setup` 重新登入，不要盲送其餘筆。
5. 彙總每筆結果（成功/失敗）回報使用者。

## 重要規則

- 金額一律經使用者確認才送；vision 辨識僅為輔助。
- 空的分類子夾略過，不產空 PDF。
- 不要把 auth.json / config.json 內容印到對話或寫進 git。
