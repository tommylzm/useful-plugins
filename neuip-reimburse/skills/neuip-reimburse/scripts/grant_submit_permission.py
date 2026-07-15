"""First-run authorization for the nueip submit wrapper.

The agent cannot widen its own permissions (Claude Code blocks self-modification),
so this MUST be run by the user (via `!` in Claude Code, or a normal shell).

It does two things, idempotently:
  1. chmod +x <skill>/submit.sh  (a fresh git checkout can lose the exec bit)
  2. add  Bash(<abs path to submit.sh>:*)  to ~/.claude/settings.json
     permissions.allow  so the agent may run the wrapper without per-call prompts.

Safe to run repeatedly. Only permissions.allow is touched — all other settings
are preserved.
"""
import json
import os
import stat

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMIT = os.path.join(SKILL_DIR, "submit.sh")
RULE = f"Bash({SUBMIT}:*)"
SETTINGS = os.path.expanduser("~/.claude/settings.json")


def ensure_executable():
    st = os.stat(SUBMIT).st_mode
    os.chmod(SUBMIT, st | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"chmod +x  {SUBMIT}")


def ensure_permission():
    if os.path.exists(SETTINGS):
        with open(SETTINGS, encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        cfg = {}
    allow = cfg.setdefault("permissions", {}).setdefault("allow", [])
    if RULE in allow:
        print("允許規則已存在:", RULE)
        return
    allow.append(RULE)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS)
    print("已加入允許規則:", RULE)


if __name__ == "__main__":
    ensure_executable()
    ensure_permission()
    print("完成。若規則未立即生效，請 /reload-plugins 或重開 session。")
