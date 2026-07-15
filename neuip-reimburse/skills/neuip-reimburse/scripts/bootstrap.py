"""One-command environment bootstrap for neuip-reimburse.

Creates the private venv, installs requirements, downloads the Playwright
browser, and seeds config.json from config.template.json if absent.
Does NOT touch auth.json — each user logs in via `--setup`.

Run with any system python3:
    python3 <skill>/scripts/bootstrap.py
"""
import json
import os
import shutil
import subprocess
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_DIR = os.path.expanduser("~/.config/neuip-reimburse")
VENV = os.path.join(CFG_DIR, "venv")
VENV_PY = os.path.join(VENV, "bin", "python")


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    os.makedirs(CFG_DIR, exist_ok=True)

    if not os.path.exists(VENV_PY):
        run([sys.executable, "-m", "venv", VENV])
    run([VENV_PY, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    run([VENV_PY, "-m", "pip", "install", "-q", "-r",
         os.path.join(SKILL_DIR, "requirements.txt")])
    run([VENV_PY, "-m", "playwright", "install", "chromium"])

    cfg_path = os.path.join(CFG_DIR, "config.json")
    tmpl = os.path.join(SKILL_DIR, "config.template.json")
    if not os.path.exists(cfg_path) and os.path.exists(tmpl):
        shutil.copy(tmpl, cfg_path)
        print(f"seeded {cfg_path} from template — edit categories/archive_root as needed")

    print("\nbootstrap 完成。")
    print("下一步：在 Claude Code 執行 /neuip-reimburse --setup 完成登入擷取與授權。")


if __name__ == "__main__":
    main()
