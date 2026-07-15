#!/bin/bash
# Wrapper so the nueip submit is a single, narrowly-allowlistable command.
# Self-locating: works wherever the skill is installed (real dir or symlink).
# The skill's scripts import as a package, so we run from the skill dir.
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SKILL_DIR" || exit 1
exec ~/.config/neuip-reimburse/venv/bin/python -m scripts.submit_claim "$@"
