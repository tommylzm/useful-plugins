import json
import os
import stat

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
