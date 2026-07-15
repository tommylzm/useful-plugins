import json

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
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    monkeypatch.setattr(neuip_client, "CONFIG_PATH", str(p))
    assert neuip_client.category_for("通勤補助")["cap"] == 1000
    assert neuip_client.category_for("不存在") is None
