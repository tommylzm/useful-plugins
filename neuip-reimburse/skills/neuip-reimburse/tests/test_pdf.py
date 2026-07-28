import pytest
from PIL import Image

from scripts import build_pdf as bp
from scripts.build_pdf import build_pdf


def _img(path, size=(1200, 1600), color=(200, 100, 50)):
    Image.new("RGB", size, color).save(path)


def _pdf(path, pages=2, size=(1200, 1600)):
    """A real multi-page PDF, the way an e-invoice mailer would send one."""
    ims = [Image.new("RGB", size, (30 * (i + 1), 60, 90)) for i in range(pages)]
    ims[0].save(path, "PDF", save_all=True, append_images=ims[1:])


def test_builds_pdf_under_limit(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"r{i}.jpg"
        _img(str(p))
        imgs.append(str(p))
    out = tmp_path / "claim.pdf"
    res = build_pdf(imgs, str(out), max_bytes=10 * 1024 * 1024)
    assert out.exists()
    assert 0 < res["bytes"] <= 10 * 1024 * 1024
    assert res["page_count"] == 3
    assert out.read_bytes()[:4] == b"%PDF"


def test_pdf_receipt_expands_to_one_page_each(tmp_path):
    src = tmp_path / "invoice.pdf"
    _pdf(str(src), pages=3)
    pages = bp._rgb_pages(str(src))
    assert len(pages) == 3
    assert all(im.mode == "RGB" for im in pages)


def test_builds_from_mixed_images_and_pdfs(tmp_path):
    jpg = tmp_path / "r.jpg"
    _img(str(jpg))
    src = tmp_path / "invoice.pdf"
    _pdf(str(src), pages=2)
    out = tmp_path / "claim.pdf"
    res = build_pdf([str(jpg), str(src)], str(out), max_bytes=10 * 1024 * 1024)
    assert out.read_bytes()[:4] == b"%PDF"
    assert 0 < res["bytes"] <= 10 * 1024 * 1024
    assert res["page_count"] == 3   # 1 image + 2 PDF pages


def test_pdf_receipt_obeys_size_limit(tmp_path):
    """PDF sources go through the same compression ladder as images."""
    src = tmp_path / "invoice.pdf"
    _pdf(str(src), pages=2)
    with pytest.raises(RuntimeError):
        build_pdf([str(src)], str(tmp_path / "x.pdf"), max_bytes=10)


def test_missing_ghostscript_is_explained(tmp_path, monkeypatch):
    src = tmp_path / "invoice.pdf"
    _pdf(str(src), pages=1)
    monkeypatch.setattr(bp.shutil, "which", lambda _: None)
    monkeypatch.setattr(bp, "_GS_FALLBACKS", ())
    with pytest.raises(RuntimeError, match="ghostscript"):
        bp._rgb_pages(str(src))


def test_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        build_pdf([], str(tmp_path / "x.pdf"), max_bytes=10 * 1024 * 1024)


def test_tiny_limit_raises(tmp_path):
    p = tmp_path / "r.jpg"
    _img(str(p))
    with pytest.raises(RuntimeError):
        build_pdf([str(p)], str(tmp_path / "x.pdf"), max_bytes=10)
