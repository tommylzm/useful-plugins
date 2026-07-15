# neuip-reimburse Skill — 設計規格

- 日期：2026-07-15
- 狀態：設計已確認，待實作
- 交付：一個可透過 `/neuip-reimburse` 執行的 Claude Code personal skill

## 1. 目標

把歸檔在資料夾裡的發票圖片，整合成單一 PDF（< 10 MB），依分類自動歸檔到年月資料夾，
並帶著結構化欄位（金額、分類、日期、事由）透過 neuip API 送出請款。

核心特性：

- 圖片來源為固定 inbox，依**分類子資料夾**存放；skill 依年月自動建立歸檔資料夾並搬入。
- 每個**分類**產生一份 PDF、一筆請款送出。
- 發票金額由 Claude 以 vision 逐張辨識並加總，**送出前一律由使用者確認**。
- 每個分類有月上限，`送出金額 = min(發票加總, 上限)`，超過上限明確警告。
- 認證採「第一次開瀏覽器手動登入 → 擷取 neuip 實際核發的認證物（token 或 cookie）→ 後續沿用」。

## 2. 非目標（YAGNI）

- 不做本地 OCR 函式庫（tesseract 等）——改用 Claude vision，較準且零額外相依。
- 不自動分類發票——由使用者以 inbox 子資料夾決定分類。
- 不做全自動盲送——金額與送出內容一律經使用者確認（除非明確加 `--yes`）。
- 不管理 neuip 帳密——只做一次性手動登入，之後用擷取到的認證物。

## 3. 目錄與檔案佈局

專案集中在 `neuip-flow/`（進 git／可分享，**不含任何秘密**）：

```
/Users/tommy/workspace/neuip-flow/
  docs/
    2026-07-15-neuip-reimburse-skill-design.md   # 本規格
    plans/                                        # 實作計畫
  skill/                     # skill 本體，symlink 到 ~/.claude/skills/neuip-reimburse
    SKILL.md                 # 給 Claude 的編排指示
    scripts/
      setup_capture.py       # phase: setup  — Playwright headed 登入 + 網路擷取
      build_pdf.py           # phase: build  — 歸檔圖片 + 合併成 PDF(<10MB)
      submit_claim.py        # phase: submit — 帶 stored auth 呼叫 neuip API
      neuip_client.py        # 共用：auth 載入、endpoint replay、過期判斷、設定與上限
    tests/                   # pytest 單元測試
    requirements.txt         # pillow, playwright, pytest
```

安裝：`ln -s /Users/tommy/workspace/neuip-flow/skill ~/.claude/skills/neuip-reimburse`，
reload plugins 後 `/neuip-reimburse` 即可用。

執行期狀態（**永不進 git、永不寫入 skill 目錄**）：

```
~/.config/neuip-reimburse/
  venv/                    # 私有 virtualenv，首次執行自動建立
  config.json              # base_url、擷取到的 endpoints、欄位對應、分類與上限
  auth.json                # token 或 cookies + 擷取到的過期資訊（chmod 600）
```

歸檔樹：

```
~/Documents/報帳/
  inbox/
    通勤補助/               # 你把通勤發票丟這
    停車補助/               # 你把停車發票丟這
  2026-07/                  # 自動建立
    通勤補助/claim.pdf
    停車補助/claim.pdf
```

## 4. 設定檔 config.json（範例）

```json
{
  "base_url": "https://<company>.neuip.com",
  "endpoints": {
    "login": { "method": "POST", "path": "/..." },
    "submit": { "method": "POST", "path": "/..." }
  },
  "field_mapping": {
    "amount": "<neuip 欄位名>",
    "date": "<neuip 欄位名>",
    "reason": "<neuip 欄位名>",
    "category_code": "<neuip 欄位名>",
    "attachment": "<neuip 檔案欄位名>"
  },
  "categories": [
    { "name": "通勤補助", "cap": 1000, "neuip_category_code": "<擷取後填入>" },
    { "name": "停車補助", "cap": 1500, "neuip_category_code": "<擷取後填入>" }
  ],
  "archive_root": "~/Documents/報帳",
  "max_pdf_bytes": 10485760
}
```

`endpoints`、`field_mapping`、`neuip_category_code` 在 `--setup` 擷取階段確定後填入。

## 5. 認證流程

1. 首次或 auth 過期時執行 `--setup`。
2. `setup_capture.py` 以 Playwright 開啟 headed 瀏覽器，導向 neuip 登入頁。
3. 使用者手動輸入帳密（必要時含 2FA）並手動送出一筆請款作為範本。
4. 腳本監聽網路流量，擷取：
   - 登入相關 request/response，判斷 neuip 核發的是 **bearer token** 還是 **session cookie**。
   - 請款送出的 endpoint、method、payload 結構與欄位名 → 寫入 `config.json`。
5. 把認證物（token 或 cookies）與可得的過期資訊寫入 `auth.json`（chmod 600）。
6. 後續 `submit` 直接載入 `auth.json`，不再開瀏覽器。

**設計為 token / cookie 皆可**：`neuip_client.py` 依 `auth.json` 內容決定帶 `Authorization` header 或 cookie jar。

## 6. 指令介面

- `/neuip-reimburse` — 處理當月，所有有發票的分類。
- `/neuip-reimburse -m 2026-06` — 指定年月。
- `/neuip-reimburse --setup` — 重新跑瀏覽器登入擷取（token/cookie 過期時）。
- `/neuip-reimburse --dry-run` — 只辨識金額 + 產 PDF，不送出。
- `/neuip-reimburse --yes` — 跳過每筆送出前的逐筆確認（預設會確認）。

## 7. 完整資料流

```
inbox/<分類>/*.jpg|png       使用者丟發票到對應分類子夾
        │  執行 /neuip-reimburse （預設當月，可 -m 指定）
        ▼
[build] 對每個有圖的分類：
   1. Claude 用 vision 逐張辨識金額(+日期) → 顯示明細與加總
   2. 套上限：送出金額 = min(加總, cap)，超過則警告
   3. 使用者確認金額；輸入該分類「事由」（日期能辨識則帶入）
   4. 圖片搬到 <archive_root>/<年月>/<分類>/，合併成 claim.pdf
   5. Pillow 迴圈壓縮（降尺寸 / 調 JPEG 品質）直到 < max_pdf_bytes
        ▼
[submit] 對每筆確認後的請款：
   neuip_client 帶 stored auth 呼叫 submit endpoint，
   附上 PDF、金額、分類 code、日期、事由
   → 逐筆顯示送出結果（成功 / 失敗 + 原因）
```

## 8. 金額與上限邏輯

- 每張圖辨識金額 → 該分類加總 `sum`。
- 送出金額 `amount = min(round(sum), cap)`。
- `sum > cap` 時輸出警告行，例如：
  `通勤補助  發票加總 NT$1,540 → 超過上限，表單填 NT$1,000 ⚠️`
- `amount` 為純函式，易於單元測試。

## 9. 錯誤處理與安全

- **auth 過期**：submit 收到 401 或被重導登入頁 → 停止並提示執行 `--setup`，**不盲送**。
- **金額確認**：vision 辨識僅為輔助，送出前一律顯示最終數字由使用者確認。
- **秘密資料**：`auth.json` chmod 600，僅存於 `~/.config/neuip-reimburse/`，不進 git、不寫入 skill 目錄。
- **送出前預覽**：預設每筆 submit 前列出將送出內容供過目（`--yes` 可跳過）。
- **PDF 壓不到 10MB**：壓縮到下限仍超標則警告並停止該筆，不硬送。
- **無發票的分類**：inbox 子夾為空則略過，不建立空 PDF。

## 10. 相依與執行環境

- Python 3.14（已安裝於 `/opt/homebrew/bin/python3`）。
- 私有 venv 於 `~/.config/neuip-reimburse/venv`，首次執行自動建立並 `pip install -r requirements.txt`。
- 相依：`pillow`（圖轉 PDF + 壓縮）、`playwright`（首次擷取；需 `playwright install chromium`）。
- API 呼叫優先用 Python 標準庫（urllib）以降低相依；若 multipart 上傳需要再評估加入 `requests`。

## 11. 測試計畫

自動化：

- `build_pdf.py`：用假圖驗證產出 PDF `< max_pdf_bytes`、頁數 = 圖片數、分類夾正確建立、inbox 清空。
- 上限邏輯：`min(sum, cap)` 邊界測試（低於 / 等於 / 超過）。
- `neuip_client.py`：以 mock response 測 auth 載入、token vs cookie 分支、401 過期判斷。

手動（需真 neuip，列於實作後驗證清單）：

- `--setup` 擷取能正確寫出 `config.json` 與 `auth.json`。
- `--dry-run` 產出正確 PDF 且不送出。
- 真實送出一筆並在 neuip 後台確認出現。

## 12. 開放項目 / 待擷取後確認

- neuip 認證物實際型態（token 或 cookie）與過期長度 —— `--setup` 階段確定。
- 送出 endpoint 是否為 multipart（決定是否需 `requests`）。
- neuip 各分類的 `category_code` 對應值 —— `--setup` 階段擷取。
