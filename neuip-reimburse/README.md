# neuip-flow — nueip 報帳自動化 skill

Claude Code personal skill：把發票圖片依年月+分類歸檔、合併成 < 10MB PDF、辨識並加總金額
（套分類上限、使用者確認後）透過 nueip API 送出請款。

- 設計規格：`docs/2026-07-15-neuip-reimburse-skill-design.md`
- 實作計畫：`docs/plans/2026-07-15-neuip-reimburse-implementation.md`
- skill 本體：`skills/neuip-reimburse/`

nueip 是台灣的 HR/請款 SaaS（`cloud.nueip.com`），本工具適用任何使用 nueip 的公司；
各公司只需把自己的科目代碼與上限填進設定即可。

## 可以分享什麼 / 不能分享什麼

| 內容 | 位置 | 可分享？ |
|---|---|---|
| skill 程式（scripts、SKILL.md、submit.sh、requirements、config 範本） | `skills/neuip-reimburse/`（本 repo） | ✅ 可 |
| 設定「範本」（endpoint、欄位對應等通用結構，科目代碼為佔位） | `skills/neuip-reimburse/config.template.json` | ✅ 可 |
| **個人實際設定**（含貴公司科目代碼/上限） | `~/.config/neuip-reimburse/config.json` | ⚠️ 內部，各自由範本填 |
| **登入憑證** | `~/.config/neuip-reimburse/auth.json` | ❌ **絕對不可**，含個人 cookie |

秘密只存在 `~/.config/neuip-reimburse/`，永遠不在本 repo 內。**分享時只給 `skill/`（或整個 repo），不要附上任何人的 `~/.config/neuip-reimburse/`。**

## 這是一個 Claude Code plugin

本 repo 本身就是一個獨立 plugin（獨立個人 marketplace，**不屬於任何公司 marketplace**）：

```
neuip-flow/
  .claude-plugin/
    plugin.json          # plugin 定義
    marketplace.json     # 個人 marketplace（名稱：tommy-neuip）
  skills/neuip-reimburse/ # skill 本體（SKILL.md / scripts / submit.sh / config 範本）
  docs/                   # 設計規格與實作計畫
```

### 給同事安裝（每人各做一次）

1. **加入這個個人 marketplace**（擇一）：
   - 從 git：`/plugin marketplace add <本 repo 的 git URL>`
   - 從本機資料夾：`/plugin marketplace add /path/to/neuip-flow`
2. **安裝 plugin**：`/plugin install neuip-reimburse@tommy-neuip`
3. **建環境**（venv + 相依 + 瀏覽器 + 由範本產 config）：
   `python3 ~/.claude/skills/neuip-reimburse/scripts/bootstrap.py`
   （plugin 安裝後，skill 會出現在 plugin 快取路徑；bootstrap 用相對自身路徑，直接跑 plugin 內的即可，
   或用上面的 symlink 路徑。找不到路徑時，`find ~/.claude -name bootstrap.py -path '*neuip*'`。）
4. **重載**：`/reload-plugins`（或重開），確認 `/neuip-reimburse` 出現。
5. **首次設定登入**：`/neuip-reimburse --setup`
   - 依指示用 `!` 開瀏覽器登入自己的 nueip，送一筆範本 → 產生自己的 `auth.json`。
   - 過程會請你用 `!` 跑 `grant_submit_permission.py` 授權 `submit.sh`（agent 無法自我擴權）。
6. 之後：把發票丟到 `~/Documents/報帳/inbox/<分類>/`，執行 `/neuip-reimburse`。

> 不想用 plugin 機制的話，也可直接把 `skills/neuip-reimburse/` 複製或 symlink 到
> `~/.claude/skills/neuip-reimburse`，效果相同。

> 設定範本的科目代碼是佔位值（`REPLACE_WITH_YOUR_CODE`）。請依貴公司實際科目，用 SKILL.md
> 說明的 `get_payroll_options` 查詢取得 `code`，填進 `~/.config/neuip-reimburse/config.json` 的 `categories`。

## 環境需求

- macOS / Python 3.11+（實測 3.14）
- 首次 `bootstrap.py` 會裝 pillow、playwright、pytest 到私有 venv，並下載 chromium
