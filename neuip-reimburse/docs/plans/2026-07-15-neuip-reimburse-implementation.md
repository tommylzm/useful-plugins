# neuip-reimburse Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code personal skill `/neuip-reimburse` that archives receipt images by year-month + category, merges each category into one sub-10 MB PDF, has Claude recognize + sum invoice amounts (user-confirmed, capped per category), and submits each claim to neuip via its API using a once-captured auth artifact (token or cookie).

**Architecture:** A `neuip-flow/skill/` directory (symlinked into `~/.claude/skills/neuip-reimburse`) holds `SKILL.md` orchestration plus three phase scripts (`setup_capture.py`, `build_pdf.py`, `submit_claim.py`) and a shared `neuip_client.py`. Claude does vision-based amount recognition and confirmation in the orchestration layer; Python does deterministic archiving, PDF building/compression, and API calls. Secrets live only in `~/.config/neuip-reimburse/` and never enter git.

**Tech Stack:** Python 3.14, Pillow (image→PDF + compression), Playwright (one-time login capture), stdlib `urllib` for API calls, pytest for tests.

---

## File Structure

- `neuip-flow/skill/SKILL.md` — orchestration instructions for Claude (commands, vision flow, confirmation gates).
- `neuip-flow/skill/scripts/neuip_client.py` — shared: config paths/load, `apply_cap`, auth load/save, `NeuipClient.submit`, `AuthExpired`.
- `neuip-flow/skill/scripts/build_pdf.py` — CLI: archive one category's inbox images into year-month folder, merge to `claim.pdf`, compress under limit.
- `neuip-flow/skill/scripts/submit_claim.py` — CLI: submit one confirmed claim via `NeuipClient`.
- `neuip-flow/skill/scripts/setup_capture.py` — Playwright headed login + network capture, writes `config.json` + `auth.json`.
- `neuip-flow/skill/tests/` — pytest unit tests for the deterministic pieces.
- `neuip-flow/skill/requirements.txt` — pillow, playwright, pytest.

Runtime state (NOT in git): `~/.config/neuip-reimburse/{venv,config.json,auth.json}`.

---

### Task 0: Scaffold project + venv

**Files:**
- Create: `neuip-flow/skill/requirements.txt`
- Create: `neuip-flow/skill/scripts/__init__.py` (empty)
- Create: `neuip-flow/skill/tests/__init__.py` (empty)

- [ ] **Step 1: Write requirements.txt**

```
pillow>=11
playwright>=1.48
pytest>=8
```

- [ ] **Step 2: Create the runtime venv and install deps**

Run:
```bash
mkdir -p ~/.config/neuip-reimburse
python3 -m venv ~/.config/neuip-reimburse/venv
~/.config/neuip-reimburse/venv/bin/pip install -q -r /Users/tommy/workspace/neuip-flow/skill/requirements.txt
~/.config/neuip-reimburse/venv/bin/python -c "import PIL, playwright; print('deps ok')"
```
Expected: `deps ok`

- [ ] **Step 3: Create empty package markers**

Create `neuip-flow/skill/scripts/__init__.py` and `neuip-flow/skill/tests/__init__.py` as empty files.

- [ ] **Step 4: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/requirements.txt skill/scripts/__init__.py skill/tests/__init__.py .gitignore
git commit -m "chore: scaffold neuip-reimburse skill + venv deps"
```

---

### Task 1: `apply_cap` pure function

**Files:**
- Create: `neuip-flow/skill/scripts/neuip_client.py`
- Test: `neuip-flow/skill/tests/test_cap.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cap.py
from scripts.neuip_client import apply_cap

def test_below_cap_returns_total():
    assert apply_cap(980, 1500) == 980

def test_equal_cap_returns_total():
    assert apply_cap(1000, 1000) == 1000

def test_over_cap_returns_cap():
    assert apply_cap(1540, 1000) == 1000

def test_zero_total():
    assert apply_cap(0, 1000) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_cap.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError: cannot import name 'apply_cap'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/neuip_client.py
def apply_cap(total: int, cap: int) -> int:
    """Return the amount to submit: the receipt total, capped at the category max."""
    return min(total, cap)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_cap.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/neuip_client.py skill/tests/test_cap.py
git commit -m "feat: apply_cap pure function for per-category limits"
```

---

### Task 2: Config paths + load/save

**Files:**
- Modify: `neuip-flow/skill/scripts/neuip_client.py`
- Test: `neuip-flow/skill/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import json, os
from scripts import neuip_client

def test_load_config_reads_json(tmp_path, monkeypatch):
    cfg = {"base_url": "https://x.neuip.com", "categories": []}
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    monkeypatch.setattr(neuip_client, "CONFIG_PATH", str(p))
    assert neuip_client.load_config()["base_url"] == "https://x.neuip.com"

def test_load_config_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(neuip_client, "CONFIG_PATH", str(tmp_path / "nope.json"))
    try:
        neuip_client.load_config()
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass

def test_categories_for_returns_match(tmp_path, monkeypatch):
    cfg = {"categories": [{"name": "通勤補助", "cap": 1000}]}
    p = tmp_path / "config.json"; p.write_text(json.dumps(cfg))
    monkeypatch.setattr(neuip_client, "CONFIG_PATH", str(p))
    assert neuip_client.category_for("通勤補助")["cap"] == 1000
    assert neuip_client.category_for("不存在") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError`/`ImportError` for `CONFIG_PATH`/`load_config`

- [ ] **Step 3: Write minimal implementation (prepend to neuip_client.py)**

```python
import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/neuip-reimburse")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
AUTH_PATH = os.path.join(CONFIG_DIR, "auth.json")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def category_for(name: str):
    for c in load_config().get("categories", []):
        if c.get("name") == name:
            return c
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/neuip_client.py skill/tests/test_config.py
git commit -m "feat: config load + category lookup"
```

---

### Task 3: Auth load/save + expiry error

**Files:**
- Modify: `neuip-flow/skill/scripts/neuip_client.py`
- Test: `neuip-flow/skill/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth.py
import json, os, stat
from scripts import neuip_client

def test_save_auth_chmod_600(tmp_path, monkeypatch):
    p = tmp_path / "auth.json"
    monkeypatch.setattr(neuip_client, "AUTH_PATH", str(p))
    neuip_client.save_auth({"kind": "token", "token": "abc"})
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600
    assert json.loads(p.read_text())["token"] == "abc"

def test_load_auth_roundtrip(tmp_path, monkeypatch):
    p = tmp_path / "auth.json"
    monkeypatch.setattr(neuip_client, "AUTH_PATH", str(p))
    neuip_client.save_auth({"kind": "cookie", "cookies": {"SESS": "1"}})
    got = neuip_client.load_auth()
    assert got["kind"] == "cookie" and got["cookies"]["SESS"] == "1"

def test_auth_expired_is_exception():
    assert issubclass(neuip_client.AuthExpired, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_auth.py -v`
Expected: FAIL — `save_auth`/`load_auth`/`AuthExpired` not defined

- [ ] **Step 3: Write minimal implementation (append to neuip_client.py)**

```python
class AuthExpired(Exception):
    """Raised when stored auth is rejected (401 or redirect to login)."""


def save_auth(auth: dict) -> None:
    os.makedirs(os.path.dirname(AUTH_PATH), exist_ok=True)
    with open(AUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(auth, f)
    os.chmod(AUTH_PATH, 0o600)


def load_auth() -> dict:
    with open(AUTH_PATH, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_auth.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/neuip_client.py skill/tests/test_auth.py
git commit -m "feat: auth load/save (chmod 600) + AuthExpired"
```

---

### Task 4: `NeuipClient.submit` request building + expiry handling

**Files:**
- Modify: `neuip-flow/skill/scripts/neuip_client.py`
- Test: `neuip-flow/skill/tests/test_client.py`

**Interface:** `NeuipClient(config: dict, auth: dict)` with
`submit(pdf_path, category_code, amount, date, reason) -> dict`. It builds a multipart POST
to `config["base_url"] + config["endpoints"]["submit"]["path"]`, attaches auth as a bearer
header (`auth["kind"] == "token"`) or a Cookie header (`auth["kind"] == "cookie"`), and posts
via an injectable `opener(request) -> (status, body)` seam so tests need no network. On status
401 or 3xx-to-login it raises `AuthExpired`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client.py
from scripts.neuip_client import NeuipClient, AuthExpired

CFG = {
    "base_url": "https://x.neuip.com",
    "endpoints": {"submit": {"method": "POST", "path": "/api/claim"}},
    "field_mapping": {"amount": "amt", "date": "dt", "reason": "rsn",
                      "category_code": "cat", "attachment": "file"},
}

def _client(auth, opener):
    return NeuipClient(CFG, auth, opener=opener)

def test_token_auth_sets_bearer(tmp_path):
    seen = {}
    def opener(req):
        seen["auth"] = req.headers.get("Authorization")
        return 200, b'{"ok":true}'
    pdf = tmp_path / "c.pdf"; pdf.write_bytes(b"%PDF-1.4 fake")
    out = _client({"kind": "token", "token": "T0K"}, opener).submit(
        str(pdf), "C1", 1000, "2026-07-15", "通勤")
    assert seen["auth"] == "Bearer T0K"
    assert out["ok"] is True

def test_cookie_auth_sets_cookie_header(tmp_path):
    seen = {}
    def opener(req):
        seen["cookie"] = req.headers.get("Cookie")
        return 200, b'{"ok":true}'
    pdf = tmp_path / "c.pdf"; pdf.write_bytes(b"%PDF fake")
    _client({"kind": "cookie", "cookies": {"SESS": "1", "CSRF": "2"}}, opener).submit(
        str(pdf), "C1", 500, "2026-07-15", "停車")
    assert "SESS=1" in seen["cookie"] and "CSRF=2" in seen["cookie"]

def test_401_raises_auth_expired(tmp_path):
    def opener(req):
        return 401, b"unauthorized"
    pdf = tmp_path / "c.pdf"; pdf.write_bytes(b"%PDF fake")
    try:
        _client({"kind": "token", "token": "x"}, opener).submit(
            str(pdf), "C1", 100, "2026-07-15", "x")
        assert False, "expected AuthExpired"
    except AuthExpired:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_client.py -v`
Expected: FAIL — `NeuipClient` not defined

- [ ] **Step 3: Write minimal implementation (append to neuip_client.py)**

```python
import mimetypes
import urllib.request


def _multipart(fields: dict, file_field: str, file_path: str):
    boundary = "----neuipreimburse7f3a2b"
    crlf = "\r\n"
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}{crlf}"
                     f'Content-Disposition: form-data; name="{k}"{crlf}{crlf}{v}{crlf}')
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    filename = os.path.basename(file_path)
    ctype = mimetypes.guess_type(filename)[0] or "application/pdf"
    head = (f"--{boundary}{crlf}"
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"{crlf}'
            f"Content-Type: {ctype}{crlf}{crlf}")
    body = b"".join(p.encode("utf-8") for p in parts)
    body += head.encode("utf-8") + file_bytes + crlf.encode("utf-8")
    body += f"--{boundary}--{crlf}".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


def _default_opener(req):
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read()


class NeuipClient:
    def __init__(self, config: dict, auth: dict, opener=_default_opener):
        self.config = config
        self.auth = auth
        self.opener = opener

    def submit(self, pdf_path, category_code, amount, date, reason) -> dict:
        fm = self.config["field_mapping"]
        fields = {
            fm["amount"]: str(amount),
            fm["date"]: date,
            fm["reason"]: reason,
            fm["category_code"]: category_code,
        }
        body, content_type = _multipart(fields, fm["attachment"], pdf_path)
        url = self.config["base_url"] + self.config["endpoints"]["submit"]["path"]
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", content_type)
        if self.auth.get("kind") == "token":
            req.add_header("Authorization", f"Bearer {self.auth['token']}")
        elif self.auth.get("kind") == "cookie":
            cookie = "; ".join(f"{k}={v}" for k, v in self.auth["cookies"].items())
            req.add_header("Cookie", cookie)
        status, raw = self.opener(req)
        if status == 401 or (300 <= status < 400):
            raise AuthExpired(f"neuip rejected stored auth (HTTP {status})")
        text = raw.decode("utf-8", "replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"status": status, "body": text}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/neuip_client.py skill/tests/test_client.py
git commit -m "feat: NeuipClient.submit with token/cookie auth + expiry detection"
```

---

### Task 5: Archive images into year-month/category

**Files:**
- Create: `neuip-flow/skill/scripts/build_pdf.py`
- Test: `neuip-flow/skill/tests/test_archive.py`

**Interface:** `archive_images(inbox_dir, archive_root, ym, category) -> list[str]` moves every
image file (`.jpg .jpeg .png` case-insensitive, sorted by name) from
`inbox_dir/category/` to `archive_root/ym/category/`, creating dirs as needed, and returns the
sorted destination paths. Non-image files are ignored. Empty/absent source returns `[]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_archive.py
from pathlib import Path
from scripts.build_pdf import archive_images

def test_moves_only_images_sorted(tmp_path):
    inbox = tmp_path / "inbox" / "通勤補助"
    inbox.mkdir(parents=True)
    (inbox / "b.jpg").write_bytes(b"x")
    (inbox / "a.PNG").write_bytes(b"x")
    (inbox / "note.txt").write_bytes(b"x")
    dests = archive_images(str(tmp_path / "inbox"), str(tmp_path / "arc"), "2026-07", "通勤補助")
    names = [Path(d).name for d in dests]
    assert names == ["a.PNG", "b.jpg"]
    assert (tmp_path / "arc" / "2026-07" / "通勤補助" / "a.PNG").exists()
    assert not (inbox / "a.PNG").exists()  # moved, not copied
    assert (inbox / "note.txt").exists()   # non-image left behind

def test_absent_category_returns_empty(tmp_path):
    assert archive_images(str(tmp_path / "inbox"), str(tmp_path / "arc"), "2026-07", "停車補助") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_archive.py -v`
Expected: FAIL — `build_pdf` / `archive_images` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/build_pdf.py
import os
import shutil

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def archive_images(inbox_dir: str, archive_root: str, ym: str, category: str) -> list:
    src = os.path.join(inbox_dir, category)
    if not os.path.isdir(src):
        return []
    dest_dir = os.path.join(archive_root, ym, category)
    os.makedirs(dest_dir, exist_ok=True)
    dests = []
    for name in sorted(os.listdir(src)):
        if os.path.splitext(name)[1].lower() not in IMAGE_EXTS:
            continue
        dest = os.path.join(dest_dir, name)
        shutil.move(os.path.join(src, name), dest)
        dests.append(dest)
    return sorted(dests)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_archive.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/build_pdf.py skill/tests/test_archive.py
git commit -m "feat: archive_images moves category inbox into year-month tree"
```

---

### Task 6: Merge images to PDF under size limit

**Files:**
- Modify: `neuip-flow/skill/scripts/build_pdf.py`
- Test: `neuip-flow/skill/tests/test_pdf.py`

**Interface:** `build_pdf(image_paths, out_path, max_bytes) -> int`. Opens each image with
Pillow (converting to RGB), and writes a single multi-page PDF. It tries progressively smaller
output: a sequence of (scale, jpeg_quality) settings, stopping at the first that yields a file
`<= max_bytes`. Returns the final byte size. Raises `ValueError` if `image_paths` is empty.
Raises `RuntimeError` if even the smallest setting exceeds `max_bytes`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf.py
from PIL import Image
from scripts.build_pdf import build_pdf
import os, pytest

def _img(path, size=(1200, 1600), color=(200, 100, 50)):
    Image.new("RGB", size, color).save(path)

def test_builds_pdf_under_limit(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"r{i}.jpg"; _img(str(p)); imgs.append(str(p))
    out = tmp_path / "claim.pdf"
    size = build_pdf(imgs, str(out), max_bytes=10 * 1024 * 1024)
    assert out.exists()
    assert 0 < size <= 10 * 1024 * 1024
    assert out.read_bytes()[:4] == b"%PDF"

def test_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        build_pdf([], str(tmp_path / "x.pdf"), max_bytes=10 * 1024 * 1024)

def test_tiny_limit_raises(tmp_path):
    p = tmp_path / "r.jpg"; _img(str(p))
    with pytest.raises(RuntimeError):
        build_pdf([str(p)], str(tmp_path / "x.pdf"), max_bytes=10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_pdf.py -v`
Expected: FAIL — `build_pdf` not defined

- [ ] **Step 3: Write minimal implementation (append to build_pdf.py)**

```python
from PIL import Image

# (scale factor, jpeg quality) tried in order — first result <= max_bytes wins
_COMPRESSION_LADDER = [
    (1.0, 85), (1.0, 70), (0.8, 70), (0.6, 60), (0.5, 50), (0.4, 40), (0.35, 30),
]


def _load_rgb(paths):
    imgs = []
    for p in paths:
        im = Image.open(p)
        imgs.append(im.convert("RGB"))
    return imgs


def build_pdf(image_paths: list, out_path: str, max_bytes: int) -> int:
    if not image_paths:
        raise ValueError("no images to build a PDF from")
    base = _load_rgb(image_paths)
    for scale, quality in _COMPRESSION_LADDER:
        pages = []
        for im in base:
            if scale != 1.0:
                w, h = im.size
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
            pages.append(im)
        pages[0].save(
            out_path, "PDF", save_all=True, append_images=pages[1:],
            quality=quality, optimize=True,
        )
        size = os.path.getsize(out_path)
        if size <= max_bytes:
            return size
    raise RuntimeError(
        f"cannot compress PDF under {max_bytes} bytes (smallest was {size})")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_pdf.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/build_pdf.py skill/tests/test_pdf.py
git commit -m "feat: build_pdf merges images and compresses under size limit"
```

---

### Task 7: `build_pdf.py` CLI

**Files:**
- Modify: `neuip-flow/skill/scripts/build_pdf.py`
- Test: `neuip-flow/skill/tests/test_build_cli.py`

**Interface:** `python -m scripts.build_pdf --category 通勤補助 --month 2026-07 --archive-root <dir> --inbox <dir> --max-bytes 10485760`.
Archives the category's images, builds `<archive-root>/<month>/<category>/claim.pdf`, and
prints a single JSON line: `{"category","pdf","image_count","bytes"}`. If no images, prints
`{"category","skipped":true}` and exits 0. `main(argv)` returns the dict for testing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_cli.py
from PIL import Image
from scripts.build_pdf import main

def _img(p): Image.new("RGB", (800, 1000), (10, 20, 30)).save(p)

def test_cli_builds_and_reports(tmp_path):
    inbox = tmp_path / "inbox" / "通勤補助"; inbox.mkdir(parents=True)
    _img(str(inbox / "a.jpg")); _img(str(inbox / "b.jpg"))
    res = main([
        "--category", "通勤補助", "--month", "2026-07",
        "--archive-root", str(tmp_path / "arc"), "--inbox", str(tmp_path / "inbox"),
        "--max-bytes", str(10 * 1024 * 1024),
    ])
    assert res["image_count"] == 2
    assert res["pdf"].endswith("2026-07/通勤補助/claim.pdf")
    assert res["bytes"] <= 10 * 1024 * 1024

def test_cli_skips_empty(tmp_path):
    res = main([
        "--category", "停車補助", "--month", "2026-07",
        "--archive-root", str(tmp_path / "arc"), "--inbox", str(tmp_path / "inbox"),
        "--max-bytes", str(10 * 1024 * 1024),
    ])
    assert res["skipped"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_build_cli.py -v`
Expected: FAIL — `main` not defined

- [ ] **Step 3: Write minimal implementation (append to build_pdf.py)**

```python
import argparse
import json


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True)
    ap.add_argument("--month", required=True)
    ap.add_argument("--archive-root", required=True)
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    args = ap.parse_args(argv)

    dests = archive_images(args.inbox, args.archive_root, args.month, args.category)
    if not dests:
        result = {"category": args.category, "skipped": True}
        print(json.dumps(result, ensure_ascii=False))
        return result
    out_dir = os.path.join(args.archive_root, args.month, args.category)
    pdf_path = os.path.join(out_dir, "claim.pdf")
    size = build_pdf(dests, pdf_path, args.max_bytes)
    result = {"category": args.category, "pdf": pdf_path,
              "image_count": len(dests), "bytes": size}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_build_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/build_pdf.py skill/tests/test_build_cli.py
git commit -m "feat: build_pdf CLI with JSON report + empty-skip"
```

---

### Task 8: `submit_claim.py` CLI

**Files:**
- Create: `neuip-flow/skill/scripts/submit_claim.py`
- Test: `neuip-flow/skill/tests/test_submit_cli.py`

**Interface:** `python -m scripts.submit_claim --pdf <path> --category 通勤補助 --amount 1000 --date 2026-07-15 --reason 通勤`.
Loads config + auth, resolves the category's `neuip_category_code` and `cap`, re-applies
`apply_cap(amount, cap)` as a safety net, submits via `NeuipClient`, prints a JSON result
`{"category","submitted_amount","ok"|"error"}`. On `AuthExpired` prints
`{"error":"auth_expired","hint":"run --setup"}` and exits non-zero. `main(argv, client_factory=...)`
takes an injectable factory so tests avoid the network.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_submit_cli.py
import json
from scripts import submit_claim, neuip_client

CFG = {
    "base_url": "https://x.neuip.com",
    "endpoints": {"submit": {"method": "POST", "path": "/api/claim"}},
    "field_mapping": {"amount": "amt", "date": "dt", "reason": "rsn",
                      "category_code": "cat", "attachment": "file"},
    "categories": [{"name": "通勤補助", "cap": 1000, "neuip_category_code": "CMT"}],
}

def test_submit_applies_cap_and_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(neuip_client, "load_config", lambda: CFG)
    monkeypatch.setattr(neuip_client, "load_auth", lambda: {"kind": "token", "token": "T"})
    captured = {}
    class FakeClient:
        def __init__(self, *a, **k): pass
        def submit(self, pdf, code, amount, date, reason):
            captured.update(code=code, amount=amount)
            return {"ok": True}
    pdf = tmp_path / "c.pdf"; pdf.write_bytes(b"%PDF")
    res = submit_claim.main(
        ["--pdf", str(pdf), "--category", "通勤補助", "--amount", "1540",
         "--date", "2026-07-15", "--reason", "通勤", "--yes"],
        client_factory=lambda cfg, auth: FakeClient(),
    )
    assert captured["code"] == "CMT"
    assert captured["amount"] == 1000          # capped from 1540
    assert res["submitted_amount"] == 1000 and res["ok"] is True

def test_submit_auth_expired(tmp_path, monkeypatch):
    monkeypatch.setattr(neuip_client, "load_config", lambda: CFG)
    monkeypatch.setattr(neuip_client, "load_auth", lambda: {"kind": "token", "token": "T"})
    class Expiring:
        def __init__(self, *a, **k): pass
        def submit(self, *a, **k): raise neuip_client.AuthExpired("401")
    pdf = tmp_path / "c.pdf"; pdf.write_bytes(b"%PDF")
    res = submit_claim.main(
        ["--pdf", str(pdf), "--category", "通勤補助", "--amount", "500",
         "--date", "2026-07-15", "--reason", "x", "--yes"],
        client_factory=lambda cfg, auth: Expiring(),
    )
    assert res["error"] == "auth_expired"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_submit_cli.py -v`
Expected: FAIL — `submit_claim` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/submit_claim.py
import argparse
import json

from scripts import neuip_client
from scripts.neuip_client import NeuipClient, AuthExpired, apply_cap


def main(argv=None, client_factory=lambda cfg, auth: NeuipClient(cfg, auth)) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--amount", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    cfg = neuip_client.load_config()
    auth = neuip_client.load_auth()
    cat = next((c for c in cfg.get("categories", []) if c["name"] == args.category), None)
    if cat is None:
        result = {"error": "unknown_category", "category": args.category}
        print(json.dumps(result, ensure_ascii=False))
        return result

    amount = apply_cap(args.amount, cat["cap"])
    client = client_factory(cfg, auth)
    try:
        resp = client.submit(args.pdf, cat["neuip_category_code"], amount, args.date, args.reason)
    except AuthExpired:
        result = {"error": "auth_expired", "hint": "run /neuip-reimburse --setup"}
        print(json.dumps(result, ensure_ascii=False))
        return result
    result = {"category": args.category, "submitted_amount": amount,
              "ok": True, "response": resp}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    import sys
    r = main()
    sys.exit(0 if r.get("ok") else 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest tests/test_submit_cli.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full suite + commit**

```bash
cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest -v
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/submit_claim.py skill/tests/test_submit_cli.py
git commit -m "feat: submit_claim CLI with cap safety net + auth-expired handling"
```

---

### Task 9: `setup_capture.py` (Playwright login + network capture)

**Files:**
- Create: `neuip-flow/skill/scripts/setup_capture.py`

No unit test — this is inherently interactive (real login). It is verified manually in Task 11.
Keep it small and readable.

- [ ] **Step 1: Write the capture script**

```python
# scripts/setup_capture.py
"""One-time interactive capture of neuip auth + endpoints.

Opens a headed browser, lets the user log in and submit ONE claim manually,
records network traffic, and writes config.json + auth.json. The user confirms
the detected login/submit endpoints in the terminal before saving.
"""
import argparse
import json
import os

from playwright.sync_api import sync_playwright

from scripts import neuip_client


def capture(base_url: str) -> dict:
    calls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        def on_response(resp):
            req = resp.request
            if req.resource_type in ("xhr", "fetch") or req.method == "POST":
                calls.append({
                    "method": req.method, "url": req.url,
                    "status": resp.status, "resource_type": req.resource_type,
                })

        page.on("response", on_response)
        page.goto(base_url)
        print("\n請在瀏覽器手動登入，並手動送出一筆請款作為範本。")
        input("完成後回到這裡按 Enter 繼續擷取…")

        cookies = {c["name"]: c["value"] for c in context.cookies()}
        browser.close()
    return {"calls": calls, "cookies": cookies}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    args = ap.parse_args(argv)

    data = capture(args.base_url)
    # Show POST/xhr calls so the human can identify login + submit endpoints.
    print("\n擷取到的候選 API 呼叫：")
    for i, c in enumerate(data["calls"]):
        print(f"  [{i}] {c['method']} {c['status']} {c['url']}")

    os.makedirs(neuip_client.CONFIG_DIR, exist_ok=True)
    raw_path = os.path.join(neuip_client.CONFIG_DIR, "capture_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n原始擷取已存到 {raw_path}")
    print("接下來由 Claude 依這份資料協助你確認 endpoints/欄位，寫入 config.json，"
          "並把 cookies 或 token 寫入 auth.json。")
    return data


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Syntax check (no interactive run here)**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -c "import ast; ast.parse(open('scripts/setup_capture.py').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Install the Playwright browser**

Run: `~/.config/neuip-reimburse/venv/bin/python -m playwright install chromium`
Expected: chromium downloaded

- [ ] **Step 4: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/scripts/setup_capture.py
git commit -m "feat: setup_capture opens headed browser and records API calls"
```

---

### Task 10: SKILL.md orchestration + install symlink

**Files:**
- Create: `neuip-flow/skill/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

````markdown
---
name: neuip-reimburse
description: Use when the user wants to file neuip 報帳/請款 from receipt images — archives images by year-month + category, merges each category into one sub-10MB PDF, recognizes and sums invoice amounts (user-confirmed, capped per category), and submits each claim to neuip via its API. Triggers like "/neuip-reimburse", "幫我報帳", "把這個月發票送 neuip".
---

# neuip-reimburse

把 `~/Documents/報帳/inbox/<分類>/` 的發票，依年月+分類歸檔、合併成 < 10MB PDF，
辨識並加總金額（套分類上限、你確認後）透過 neuip API 送出。

## 環境

- venv: `~/.config/neuip-reimburse/venv`（缺就先 `python3 -m venv` 並 `pip install -r <skill>/requirements.txt`）。
- 所有腳本從 skill 目錄以模組執行：`cd <skill> && ~/.config/neuip-reimburse/venv/bin/python -m scripts.<name> ...`
- 秘密只在 `~/.config/neuip-reimburse/`（config.json / auth.json），永不外流、不進 git。

## 指令解析

參數（從使用者訊息解析）：
- 年月：`-m 2026-06`；未給則用當月（以系統日期）。
- `--setup`：重新擷取登入。
- `--dry-run`：只辨識 + 產 PDF，不送出。
- `--yes`：跳過逐筆送出前確認（預設要確認）。

## 流程

### 若尚未設定或 `--setup`
1. 問使用者 neuip base URL（若 config.json 沒有）。
2. 執行 `python -m scripts.setup_capture --base-url <url>`（開瀏覽器，使用者手動登入 + 送一筆範本）。
3. 讀 `~/.config/neuip-reimburse/capture_raw.json`，和使用者一起指認 login/submit endpoint、
   欄位對應、各分類 code，寫入 `config.json`；把 cookies（或找到的 token）以
   `{"kind":"cookie"|"token", ...}` 寫入 `auth.json`（用 `neuip_client.save_auth`）。

### 每次報帳
1. 決定年月與 `archive_root`（config 的 `archive_root`，預設 `~/Documents/報帳`）。
2. 列出 `inbox/` 下有檔案的分類子資料夾。逐一處理每個分類：
   a. **辨識金額**：用 Read 工具讀該分類 inbox 內每張圖，辨識金額與日期。
   b. 顯示每張明細 + 加總；套上限（config 該分類 `cap`）：`送出金額 = min(加總, cap)`，
      超過上限用 ⚠️ 標示。
   c. **請使用者確認金額**，並輸入該分類「事由」；日期預設取辨識到的最新一張，可修改。
   d. 產 PDF：`python -m scripts.build_pdf --category <cat> --month <ym> --archive-root <root> --inbox <root>/inbox --max-bytes 10485760`
      （這步會把圖搬到 `<root>/<ym>/<cat>/` 並產 `claim.pdf`）。
3. **送出**（除非 `--dry-run`）：逐筆先列出將送出內容（分類/金額/日期/事由/PDF），
   除非 `--yes` 否則等使用者確認，再執行
   `python -m scripts.submit_claim --pdf <pdf> --category <cat> --amount <amt> --date <date> --reason <reason> [--yes]`。
4. 若任何一筆回傳 `{"error":"auth_expired"}`：停止並提示使用者跑 `--setup` 重新登入，不要盲送其餘筆。
5. 彙總每筆結果（成功/失敗）回報使用者。

## 重要規則

- 金額一律經使用者確認才送；vision 辨識僅為輔助。
- 空的分類子夾略過，不產空 PDF。
- 不要把 auth.json / config.json 內容印到對話或寫進 git。
````

- [ ] **Step 2: Install symlink so `/neuip-reimburse` resolves**

Run:
```bash
ln -sfn /Users/tommy/workspace/neuip-flow/skill ~/.claude/skills/neuip-reimburse
ls -l ~/.claude/skills/neuip-reimburse
```
Expected: symlink pointing at `neuip-flow/skill`

- [ ] **Step 3: Commit**

```bash
cd /Users/tommy/workspace/neuip-flow
git add skill/SKILL.md
git commit -m "feat: SKILL.md orchestration for neuip-reimburse"
```

---

### Task 11: Manual end-to-end verification

**No code.** Confirm the whole flow against real neuip. Record results in the PR/notes.

- [ ] **Step 1: Full unit suite green**

Run: `cd /Users/tommy/workspace/neuip-flow/skill && ~/.config/neuip-reimburse/venv/bin/python -m pytest -v`
Expected: all pass.

- [ ] **Step 2: Reload plugins, confirm command appears**

In Claude Code run `/reload-plugins` (or restart). Confirm `/neuip-reimburse` shows in the `/` menu.

- [ ] **Step 3: `--setup` capture**

Run the skill with `--setup`, log in, submit one claim manually. Confirm `config.json` +
`auth.json` written and `auth.json` is `-rw-------` (chmod 600).

- [ ] **Step 4: `--dry-run`**

Put a couple of test images in `inbox/通勤補助/` and `inbox/停車補助/`. Run
`/neuip-reimburse --dry-run`. Confirm: amounts recognized + summed, cap applied with warning
when over, images moved to `2026-07/<category>/`, `claim.pdf` exists and is < 10 MB, nothing submitted.

- [ ] **Step 5: Real submit (one category)**

Run `/neuip-reimburse` for one category, confirm the pre-submit preview, submit, then verify in
neuip's web UI that the claim appears with the right amount, date, category, and attached PDF.

- [ ] **Step 6: Expiry path**

Corrupt `auth.json` (e.g. edit the token) and run a submit. Confirm it reports `auth_expired`
and prompts for `--setup` rather than silently failing.

---

## Self-Review Notes

- **Spec coverage:** inbox→year-month/category archiving (T5,T7); one PDF+one submit per category (T7,T8); <10MB compression (T6); vision amount recognition + confirm (SKILL.md T10); per-category cap `min(sum,cap)` (T1, re-applied T8); token-or-cookie auth (T3,T4); one-time browser capture (T9); expiry→`--setup` (T4,T8,T10); secrets in `~/.config` chmod 600 (T3); commands `-m/--setup/--dry-run/--yes` (T10). All covered.
- **Type consistency:** `apply_cap`, `load_config`, `category_for`, `load_auth`, `save_auth`, `AuthExpired`, `NeuipClient(config, auth, opener=)`/`.submit(pdf_path, category_code, amount, date, reason)`, `archive_images(inbox_dir, archive_root, ym, category)`, `build_pdf(image_paths, out_path, max_bytes)`, `build_pdf.main(argv)`, `submit_claim.main(argv, client_factory=)` — names consistent across tasks.
- **Open items (need real neuip during T11):** actual auth kind (token vs cookie) and lifetime; whether submit is multipart (assumed multipart in T4); real `neuip_category_code` values. These are captured in `--setup` and filled into `config.json`.
