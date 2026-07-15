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


def test_submit_auth_expired(tmp_path, monkeypatch):
    monkeypatch.setattr(neuip_client, "load_config", lambda: CFG)
    monkeypatch.setattr(neuip_client, "load_auth", lambda: {"kind": "token", "token": "T"})

    class Expiring:
        def __init__(self, *a, **k):
            pass

        def submit(self, *a, **k):
            raise neuip_client.AuthExpired("401")

    pdf = tmp_path / "c.pdf"
    pdf.write_bytes(b"%PDF")
    res = submit_claim.main(
        ["--pdf", str(pdf), "--category", "通勤補助", "--amount", "500",
         "--date", "2026-07-15", "--reason", "x", "--yes"],
        client_factory=lambda cfg, auth: Expiring(),
    )
    assert res["error"] == "auth_expired"
