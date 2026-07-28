import io
import urllib.error
import urllib.request

from scripts import neuip_client
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

    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = _client({"kind": "token", "token": "T0K"}, opener).submit(
        str(pdf), "C1", 1000, "2026-07-15", "通勤")
    assert seen["auth"] == "Bearer T0K"
    assert out["ok"] is True


def test_cookie_auth_sets_cookie_header(tmp_path):
    seen = {}

    def opener(req):
        seen["cookie"] = req.headers.get("Cookie")
        return 200, b'{"ok":true}'

    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(b"%PDF fake")
    _client({"kind": "cookie", "cookies": {"SESS": "1", "CSRF": "2"}}, opener).submit(
        str(pdf), "C1", 500, "2026-07-15", "停車")
    assert "SESS=1" in seen["cookie"] and "CSRF=2" in seen["cookie"]


def test_401_raises_auth_expired(tmp_path):
    def opener(req):
        return 401, b"unauthorized"

    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(b"%PDF fake")
    try:
        _client({"kind": "token", "token": "x"}, opener).submit(
            str(pdf), "C1", 100, "2026-07-15", "x")
        assert False, "expected AuthExpired"
    except AuthExpired:
        pass


def test_default_opener_reports_error_status(monkeypatch):
    """urlopen raises HTTPError on 4xx — the opener must hand the status back,
    otherwise submit() never reaches its 401 → AuthExpired branch."""
    def boom(req, context=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b"unauthorized"))

    monkeypatch.setattr(neuip_client.urllib.request, "urlopen", boom)
    req = urllib.request.Request("https://x.neuip.com/api/claim", data=b"", method="POST")
    assert neuip_client._default_opener(req) == (401, b"unauthorized")


# ---- nueip-shaped config: multi-field date, constant action, csrf header ----
NUEIP_CFG = {
    "base_url": "https://cloud.nueip.com",
    "endpoints": {"submit": {"method": "POST", "path": "/payment_request"}},
    "field_mapping": {"amount": "pay", "date": ["start_date", "end_date"],
                      "reason": "remark", "category_code": "p_sn", "attachment": "files[]"},
    "submit_extra_fields": {"action": "add"},
    "headers": {"X-Requested-With": "XMLHttpRequest"},
    "csrf": {"cookie": "csrf_token", "header": "X-Csrf-Token"},
}


def test_nueip_multipart_fields_and_csrf(tmp_path):
    seen = {}

    def opener(req):
        seen["body"] = req.data.decode("utf-8", "replace")
        seen["csrf"] = req.headers.get("X-csrf-token")
        seen["xrw"] = req.headers.get("X-requested-with")
        seen["cookie"] = req.headers.get("Cookie")
        return 200, b'{"status":"success"}'

    pdf = tmp_path / "claim.pdf"
    pdf.write_bytes(b"%PDF-1.4 data")
    auth = {"kind": "cookie", "cookies": {"PHPSESSID": "abc", "csrf_token": "TOK123"}}
    out = NeuipClient(NUEIP_CFG, auth, opener=opener).submit(
        str(pdf), "EXAMPLECODE", 1500, "2026-07-15", "停車費")

    b = seen["body"]
    assert 'name="pay"' in b and "1500" in b
    assert 'name="start_date"' in b and 'name="end_date"' in b  # date fanned out
    assert 'name="remark"' in b and "停車費" in b
    assert 'name="p_sn"' in b and "EXAMPLECODE" in b
    assert 'name="action"' in b and "add" in b
    assert 'name="files[]"; filename="claim.pdf"' in b
    assert seen["csrf"] == "TOK123"                 # csrf header from cookie
    assert seen["xrw"] == "XMLHttpRequest"          # config header
    assert "PHPSESSID=abc" in seen["cookie"]
    assert out["status"] == "success"
