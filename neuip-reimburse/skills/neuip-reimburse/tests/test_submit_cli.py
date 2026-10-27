from scripts import submit_claim, neuip_client

CFG = {
    "base_url": "https://x.neuip.com",
    "endpoints": {"submit": {"method": "POST", "path": "/api/claim"}},
    "field_mapping": {"amount": "amt", "date": "dt", "reason": "rsn",
                      "category_code": "cat", "attachment": "file"},
    "categories": [{"name": "通勤補助", "cap": 1000, "neuip_category_code": "CMT"}],
}


def test_submit_applies_cap_and_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(neuip_client, "load_config", lambda: CFG)
    monkeypatch.setattr(neuip_client, "load_auth", lambda: {"kind": "token", "token": "T"})
    captured = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def submit(self, pdf, code, amount, date, reason):
            captured.update(code=code, amount=amount)
            return {"ok": True}

    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(b"%PDF")
    res = submit_claim.main(
        ["--pdf", str(pdf), "--category", "通勤補助", "--amount", "1540",
         "--date", "2026-07-15", "--reason", "通勤", "--yes"],
        client_factory=lambda cfg, auth: FakeClient(),
    )
    assert captured["code"] == "CMT"
    assert captured["amount"] == 1000          # capped from 1540
    assert res["submitted_amount"] == 1000 and res["ok"] is True


class Expiring:
    def submit(self, *a, **k):
        raise neuip_client.AuthExpired("401")


class Accepting:
    def submit(self, *a, **k):
        return {"status": "success"}


def _run(tmp_path, client_factory, relogin):
    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(b"%PDF")
    return submit_claim.main(
        ["--pdf", str(pdf), "--category", "通勤補助", "--amount", "500",
         "--date", "2026-07-15", "--reason", "x", "--yes"],
        client_factory=client_factory, relogin=relogin,
    )


def test_submit_auth_expired_relogs_in_and_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(neuip_client, "load_config", lambda: CFG)
    monkeypatch.setattr(neuip_client, "load_auth", lambda: {"kind": "cookie", "cookies": {"S": "old"}})
    saved = []
    monkeypatch.setattr(neuip_client, "save_auth", saved.append)
    fresh = {"kind": "cookie", "cookies": {"S": "new"}}

    res = _run(tmp_path,
               client_factory=lambda cfg, auth: Accepting() if auth == fresh else Expiring(),
               relogin=lambda cfg: fresh)

    assert res["ok"] is True and res["submitted_amount"] == 500
    assert saved == [fresh]                    # new login persisted for later claims


def test_submit_auth_expired_when_login_abandoned(tmp_path, monkeypatch):
    monkeypatch.setattr(neuip_client, "load_config", lambda: CFG)
    monkeypatch.setattr(neuip_client, "load_auth", lambda: {"kind": "token", "token": "T"})
    saved = []
    monkeypatch.setattr(neuip_client, "save_auth", saved.append)

    res = _run(tmp_path, client_factory=lambda cfg, auth: Expiring(),
               relogin=lambda cfg: None)      # window closed / timed out

    assert res["error"] == "auth_expired"
    assert saved == []


def test_submit_relogs_in_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(neuip_client, "load_config", lambda: CFG)
    monkeypatch.setattr(neuip_client, "load_auth", lambda: {"kind": "token", "token": "T"})
    monkeypatch.setattr(neuip_client, "save_auth", lambda auth: None)
    logins = []

    def relogin(cfg):
        logins.append(cfg)
        return {"kind": "cookie", "cookies": {"S": "new"}}

    res = _run(tmp_path, client_factory=lambda cfg, auth: Expiring(), relogin=relogin)

    assert res["error"] == "auth_expired"
    assert len(logins) == 1
