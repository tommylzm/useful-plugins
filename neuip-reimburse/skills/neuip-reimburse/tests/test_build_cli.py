from PIL import Image

from scripts.build_pdf import main


def _img(p):
    Image.new("RGB", (800, 1000), (10, 20, 30)).save(p)


def _pdf(p, pages=2):
    ims = [Image.new("RGB", (800, 1000), (40, 50 * (i + 1), 60)) for i in range(pages)]
    ims[0].save(p, "PDF", save_all=True, append_images=ims[1:])


def test_cli_builds_and_reports(tmp_path):
    inbox = tmp_path / "inbox" / "通勤補助"
    inbox.mkdir(parents=True)
    _img(str(inbox / "a.jpg"))
    _img(str(inbox / "b.jpg"))
    res = main([
        "--category", "通勤補助", "--month", "2026-07",
        "--archive-root", str(tmp_path / "arc"), "--inbox", str(tmp_path / "inbox"),
        "--max-bytes", str(10 * 1024 * 1024),
    ])
    assert res["receipt_count"] == 2
    assert res["page_count"] == 2
    assert res["pdf"].endswith("2026-07/通勤補助/claim.pdf")
    assert res["bytes"] <= 10 * 1024 * 1024


def test_cli_counts_pdf_pages(tmp_path):
    inbox = tmp_path / "inbox" / "停車補助"
    inbox.mkdir(parents=True)
    _img(str(inbox / "a.jpg"))
    _pdf(str(inbox / "b.pdf"), pages=2)
    res = main([
        "--category", "停車補助", "--month", "2026-07",
        "--archive-root", str(tmp_path / "arc"), "--inbox", str(tmp_path / "inbox"),
        "--max-bytes", str(10 * 1024 * 1024),
    ])
    assert res["receipt_count"] == 2
    assert res["page_count"] == 3


def test_cli_skips_empty(tmp_path):
    res = main([
        "--category", "停車補助", "--month", "2026-07",
        "--archive-root", str(tmp_path / "arc"), "--inbox", str(tmp_path / "inbox"),
        "--max-bytes", str(10 * 1024 * 1024),
    ])
    assert res["skipped"] is True
