from pathlib import Path

from scripts.build_pdf import archive_receipts


def test_moves_only_receipts_sorted(tmp_path):
    inbox = tmp_path / "inbox" / "通勤補助"
    inbox.mkdir(parents=True)
    (inbox / "b.jpg").write_bytes(b"x")
    (inbox / "a.PNG").write_bytes(b"x")
    (inbox / "c.PDF").write_bytes(b"x")
    (inbox / "note.txt").write_bytes(b"x")
    dests = archive_receipts(str(tmp_path / "inbox"), str(tmp_path / "arc"), "2026-07", "通勤補助")
    names = [Path(d).name for d in dests]
    assert names == ["a.PNG", "b.jpg", "c.PDF"]
    assert (tmp_path / "arc" / "2026-07" / "通勤補助" / "a.PNG").exists()
    assert (tmp_path / "arc" / "2026-07" / "通勤補助" / "c.PDF").exists()
    assert not (inbox / "a.PNG").exists()  # moved, not copied
    assert (inbox / "note.txt").exists()   # non-receipt left behind


def test_leaves_previous_output_behind(tmp_path):
    """A stray claim.pdf must never be folded back into the next claim."""
    inbox = tmp_path / "inbox" / "停車補助"
    inbox.mkdir(parents=True)
    (inbox / "claim.pdf").write_bytes(b"x")
    (inbox / "r.pdf").write_bytes(b"x")
    dests = archive_receipts(str(tmp_path / "inbox"), str(tmp_path / "arc"), "2026-07", "停車補助")
    assert [Path(d).name for d in dests] == ["r.pdf"]
    assert (inbox / "claim.pdf").exists()


def test_absent_category_returns_empty(tmp_path):
    assert archive_receipts(str(tmp_path / "inbox"), str(tmp_path / "arc"), "2026-07", "停車補助") == []
