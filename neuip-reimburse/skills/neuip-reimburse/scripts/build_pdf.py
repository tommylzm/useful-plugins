import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile

from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
PDF_EXTS = {".pdf"}
RECEIPT_EXTS = IMAGE_EXTS | PDF_EXTS

OUT_NAME = "claim.pdf"

# PDF receipts (e-invoice mailers send these) are rasterized first, so images and
# PDFs then travel the exact same compression path below.
PDF_RENDER_DPI = 150
_GS_FALLBACKS = ("/opt/homebrew/bin/gs", "/usr/local/bin/gs", "/usr/bin/gs")

# (scale factor, jpeg quality) tried in order — first result <= max_bytes wins
_COMPRESSION_LADDER = [
    (1.0, 85), (1.0, 70), (0.8, 70), (0.6, 60), (0.5, 50), (0.4, 40), (0.35, 30),
]


def archive_receipts(inbox_dir: str, archive_root: str, ym: str, category: str) -> list:
    src = os.path.join(inbox_dir, category)
    if not os.path.isdir(src):
        return []
    dest_dir = os.path.join(archive_root, ym, category)
    os.makedirs(dest_dir, exist_ok=True)
    dests = []
    for name in sorted(os.listdir(src)):
        if name == OUT_NAME:  # a previous run's output, not a receipt
            continue
        if os.path.splitext(name)[1].lower() not in RECEIPT_EXTS:
            continue
        dest = os.path.join(dest_dir, name)
        shutil.move(os.path.join(src, name), dest)
        dests.append(dest)
    return sorted(dests)


def _gs_binary() -> str:
    gs = shutil.which("gs") or next((p for p in _GS_FALLBACKS if os.path.exists(p)), None)
    if gs is None:
        raise RuntimeError(
            "ghostscript (gs) not found — it is needed to rasterize PDF receipts; "
            "install it with `brew install ghostscript`")
    return gs


def _rasterize_pdf(path: str, dpi: int = PDF_RENDER_DPI) -> list:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [_gs_binary(), "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
             "-sDEVICE=png16m", f"-r{dpi}",
             f"-sOutputFile={os.path.join(tmp, 'page-%04d.png')}", path],
            check=True, capture_output=True)
        rendered = sorted(glob.glob(os.path.join(tmp, "page-*.png")))
        if not rendered:
            raise RuntimeError(f"ghostscript rendered no pages from {path}")
        # convert() copies pixels into memory, so pages outlive the temp dir
        return [Image.open(p).convert("RGB") for p in rendered]


def _rgb_pages(path: str) -> list:
    """One receipt file → its page images. A PDF may contribute several."""
    if os.path.splitext(path)[1].lower() in PDF_EXTS:
        return _rasterize_pdf(path)
    return [Image.open(path).convert("RGB")]


def _load_rgb(paths) -> list:
    pages = []
    for p in paths:
        pages.extend(_rgb_pages(p))
    return pages


def build_pdf(receipt_paths: list, out_path: str, max_bytes: int) -> dict:
    """Merge receipts (images and/or PDFs) into one PDF under max_bytes.

    Returns {"bytes", "page_count"}.
    """
    if not receipt_paths:
        raise ValueError("no receipts to build a PDF from")
    base = _load_rgb(receipt_paths)
    size = None
    for scale, quality in _COMPRESSION_LADDER:
        pages = []
        for im in base:
            if scale != 1.0:
                w, h = im.size
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
            pages.append(im)
        pages[0].save(
            out_path, "PDF", save_all=True, append_images=pages[1:],
            quality=quality, optimize=True,
        )
        size = os.path.getsize(out_path)
        if size <= max_bytes:
            return {"bytes": size, "page_count": len(base)}
    raise RuntimeError(
        f"cannot compress PDF under {max_bytes} bytes (smallest was {size})")


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True)
    ap.add_argument("--month", required=True)
    ap.add_argument("--archive-root", required=True)
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--max-bytes", type=int, default=10 * 1024 * 1024)
    args = ap.parse_args(argv)
    args.archive_root = os.path.expanduser(args.archive_root)
    args.inbox = os.path.expanduser(args.inbox)

    dests = archive_receipts(args.inbox, args.archive_root, args.month, args.category)
    if not dests:
        result = {"category": args.category, "skipped": True}
        print(json.dumps(result, ensure_ascii=False))
        return result
    out_dir = os.path.join(args.archive_root, args.month, args.category)
    pdf_path = os.path.join(out_dir, OUT_NAME)
    built = build_pdf(dests, pdf_path, args.max_bytes)
    result = {"category": args.category, "pdf": pdf_path,
              "receipt_count": len(dests), "page_count": built["page_count"],
              "bytes": built["bytes"]}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
