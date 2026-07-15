import pytest
from PIL import Image

from scripts.build_pdf import build_pdf


def _img(path, size=(1200, 1600), color=(200, 100, 50)):
    Image.new("RGB", size, color).save(path)


def test_builds_pdf_under_limit(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"r{i}.jpg"
        _img(str(p))
        imgs.append(str(p))
    out = tmp_path / "claim.pdf"
    size = build_pdf(imgs, str(out), max_bytes=10 * 1024 * 1024)
    assert out.exists()
    assert 0 < size <= 10 * 1024 * 1024
    assert out.read_bytes()[:4] == b"%PDF"


def test_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        build_pdf([], str(tmp_path / "x.pdf"), max_bytes=10 * 1024 * 1024)


def test_tiny_limit_raises(tmp_path):
    p = tmp_path / "r.jpg"
    _img(str(p))
    with pytest.raises(RuntimeError):
        build_pdf([str(p)], str(tmp_path / "x.pdf"), max_bytes=10)
