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
