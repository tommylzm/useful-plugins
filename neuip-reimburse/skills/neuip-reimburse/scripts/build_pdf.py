import argparse
import json
import os
import shutil

from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# (scale factor, jpeg quality) tried in order — first result <= max_bytes wins
_COMPRESSION_LADDER = [
    (1.0, 85), (1.0, 70), (0.8, 70), (0.6, 60), (0.5, 50), (0.4, 40), (0.35, 30),
]


def archive_images(inbox_dir: str, archive_root: str, ym: str, category: str) -> list:
    src = os.path.join(inbox_dir, category)
    if not os.path.isdir(src):
        return []
    dest_dir = os.path.join(archive_root, ym, category)
    os.makedirs(dest_dir, exist_ok=True)
    dests = []
    for name in sorted(os.listdir(src)):
        if os.path.splitext(name)[1].lower() not in IMAGE_EXTS:
            continue
        dest = os.path.join(dest_dir, name)
        shutil.move(os.path.join(src, name), dest)
        dests.append(dest)
    return sorted(dests)


def _load_rgb(paths):
    imgs = []
    for p in paths:
        im = Image.open(p)
        imgs.append(im.convert("RGB"))
    return imgs


def build_pdf(image_paths: list, out_path: str, max_bytes: int) -> int:
    if not image_paths:
        raise ValueError("no images to build a PDF from")
    base = _load_rgb(image_paths)
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
            return size
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

    dests = archive_images(args.inbox, args.archive_root, args.month, args.category)
    if not dests:
        result = {"category": args.category, "skipped": True}
        print(json.dumps(result, ensure_ascii=False))
        return result
    out_dir = os.path.join(args.archive_root, args.month, args.category)
    pdf_path = os.path.join(out_dir, "claim.pdf")
    size = build_pdf(dests, pdf_path, args.max_bytes)
    result = {"category": args.category, "pdf": pdf_path,
              "image_count": len(dests), "bytes": size}
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
