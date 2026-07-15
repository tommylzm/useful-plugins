# neuip-reimburse

A Claude Code plugin that automates filing reimbursement claims on **nueip**
(`cloud.nueip.com`, a Taiwanese HR/expense SaaS): it archives receipt images by
year-month and category, merges each category into a single sub-10MB PDF,
recognizes and sums the invoice amounts (capped per category, confirmed by you),
and submits each claim through the nueip API.

Works for any company that uses nueip — each user just fills in their own
category codes and limits.

- Design spec: `docs/2026-07-15-neuip-reimburse-skill-design.md`
- Implementation plan: `docs/plans/2026-07-15-neuip-reimburse-implementation.md`
- Skill itself: `skills/neuip-reimburse/`

## What is / isn't shareable

| Item | Location | Shareable? |
|---|---|---|
| Skill code (scripts, SKILL.md, submit.sh, requirements, config template) | `skills/neuip-reimburse/` (this repo) | ✅ Yes |
| Config **template** (generic structure; category codes are placeholders) | `skills/neuip-reimburse/config.template.json` | ✅ Yes |
| **Your real config** (your company's category codes / limits) | `~/.config/neuip-reimburse/config.json` | ⚠️ Internal — each user fills from the template |
| **Login credentials** | `~/.config/neuip-reimburse/auth.json` | ❌ **Never** — contains your personal session cookies |

Secrets live only under `~/.config/neuip-reimburse/`, never in this repo. When
sharing, hand over the repo only — never anyone's `~/.config/neuip-reimburse/`.

## Install (each user does this once)

1. **Add the marketplace**:
   `/plugin marketplace add https://github.com/tommylzm/useful-plugins.git`
2. **Install the plugin**: `/plugin install neuip-reimburse@useful-plugins`
3. **Bootstrap the environment** (venv + deps + browser + config from template):
   `python3 ~/.claude/skills/neuip-reimburse/scripts/bootstrap.py`
   (If the path differs after a plugin install: `find ~/.claude -name bootstrap.py -path '*neuip*'`.)
4. **Reload**: `/reload-plugins` (or restart) and confirm `/neuip-reimburse` appears.
5. **First-time login setup**: `/neuip-reimburse --setup`
   - Follow the prompt to open a browser with `!`, log into your own nueip, and
     submit one sample claim → this produces your own `auth.json`.
   - You'll also be asked to run `grant_submit_permission.py` via `!` to authorize
     `submit.sh` (the agent cannot widen its own permissions).
6. From then on: drop receipts into `~/Documents/報帳/inbox/<category>/` and run
   `/neuip-reimburse`.

> Prefer not to use the plugin mechanism? Just copy or symlink
> `skills/neuip-reimburse/` to `~/.claude/skills/neuip-reimburse` — same result.

> The template's category codes are placeholders (`REPLACE_WITH_YOUR_CODE`). Find
> your company's real codes with the `get_payroll_options` query described in
> `SKILL.md`, then fill them into `categories` in
> `~/.config/neuip-reimburse/config.json`.

## Requirements

- macOS / Python 3.11+ (tested on 3.14)
- The first `bootstrap.py` run installs pillow, playwright, and pytest into a
  private venv and downloads Chromium.
