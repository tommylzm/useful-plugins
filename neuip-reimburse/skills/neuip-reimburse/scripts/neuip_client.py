import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/neuip-reimburse")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
AUTH_PATH = os.path.join(CONFIG_DIR, "auth.json")


def apply_cap(total: int, cap: int) -> int:
    """Return the amount to submit: the receipt total, capped at the category max."""
    return min(total, cap)


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def category_for(name: str):
    for c in load_config().get("categories", []):
        if c.get("name") == name:
            return c
    return None


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


import mimetypes
import ssl
import urllib.request


def _make_ssl_context():
    """CA + hostname verification, but relax Python 3.14's RFC5280 strict mode
    (VERIFY_X509_STRICT) — the nueip cert lacks the Subject Key Identifier
    extension that strict mode now demands, which would otherwise abort the TLS
    handshake. This keeps real certificate/hostname verification intact."""
    ctx = ssl.create_default_context()
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        ctx.verify_flags &= ~strict
    return ctx


_SSL_CONTEXT = _make_ssl_context()


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
    with urllib.request.urlopen(req, context=_SSL_CONTEXT) as resp:
        return resp.status, resp.read()


class NeuipClient:
    def __init__(self, config: dict, auth: dict, opener=_default_opener):
        self.config = config
        self.auth = auth
        self.opener = opener

    def submit(self, pdf_path, category_code, amount, date, reason) -> dict:
        fm = self.config["field_mapping"]
        fields = {}

        def put(logical, value):
            target = fm[logical]
            if isinstance(target, list):      # one logical value → several form fields
                for name in target:
                    fields[name] = value
            else:
                fields[target] = value

        put("amount", str(amount))
        put("date", date)
        put("reason", reason)
        put("category_code", str(category_code))
        # constant fields the form always sends (e.g. {"action": "add"})
        fields.update(self.config.get("submit_extra_fields", {}))

        body, content_type = _multipart(fields, fm["attachment"], pdf_path)
        url = self.config["base_url"] + self.config["endpoints"]["submit"]["path"]
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", content_type)
        for hk, hv in self.config.get("headers", {}).items():
            req.add_header(hk, hv)
        if self.auth.get("kind") == "token":
            req.add_header("Authorization", f"Bearer {self.auth['token']}")
        elif self.auth.get("kind") == "cookie":
            cookies = self.auth["cookies"]
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
            csrf = self.config.get("csrf")
            if csrf and csrf.get("cookie") in cookies:
                req.add_header(csrf["header"], cookies[csrf["cookie"]])
        status, raw = self.opener(req)
        if status == 401 or (300 <= status < 400):
            raise AuthExpired(f"neuip rejected stored auth (HTTP {status})")
        text = raw.decode("utf-8", "replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"status": status, "body": text}
