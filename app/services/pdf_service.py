import glob
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import img2pdf
from PIL import Image, ImageOps

from . import image_service  # juga mengaktifkan dukungan HEIC

# preset Ghostscript -> kualitas
PRESETS = {
    "screen": "Ukuran terkecil (72 dpi)",
    "ebook": "Seimbang (150 dpi) - disarankan",
    "printer": "Kualitas cetak (300 dpi)",
    "prepress": "Kualitas tertinggi (300 dpi, warna dipertahankan)",
}
DEFAULT_PRESET = "ebook"


def find_ghostscript(configured: str = ""):
    """Cari executable Ghostscript. Mengembalikan path lengkap atau None."""
    candidates = []
    if configured:
        candidates.append(configured)
    candidates += ["gswin64c", "gswin32c", "gs"] if os.name == "nt" else ["gs"]

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found

    # Windows: instalasi default sering tidak masuk PATH
    if os.name == "nt":
        patterns = [
            r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
            r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe",
        ]
        for pattern in patterns:
            matches = sorted(glob.glob(pattern), reverse=True)  # versi terbaru dulu
            if matches:
                return matches[0]

    return None


def is_pdf_file(path) -> bool:
    """Cek signature '%PDF-' di awal file."""
    try:
        with open(path, "rb") as fh:
            return b"%PDF-" in fh.read(1024)
    except OSError:
        return False


def compress_pdf(path, output_dir, original_name: str, preset: str, gs_path: str, timeout: int = 300) -> dict:
    """Kompres satu PDF dengan Ghostscript. Tidak melempar error, hasilnya berupa dict."""
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    out_name = f"{path.stem}_compressed.pdf"
    out_path = output_dir / out_name

    cmd = [
        gs_path,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{preset}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dSAFER",
        f"-sOutputFile={out_path}",
        str(path),
    ]

    try:
        original_size = path.stat().st_size
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if completed.returncode != 0 or not out_path.exists():
            out_path.unlink(missing_ok=True)
            result["error"] = "PDF gagal diproses (mungkin terenkripsi atau rusak)."
            return result

        new_size = out_path.stat().st_size
        kept_original = False

        # Kalau hasil tidak lebih kecil, pertahankan file asli
        if new_size >= original_size:
            shutil.copyfile(path, out_path)
            new_size = original_size
            kept_original = True

        saved_percent = (1 - new_size / original_size) * 100 if original_size else 0
        result.update({
            "status": "success",
            "output": out_name,
            "original_size": original_size,
            "new_size": new_size,
            "saved_percent": round(max(saved_percent, 0.0), 1),
            "kept_original": kept_original,
        })
    except subprocess.TimeoutExpired:
        out_path.unlink(missing_ok=True)
        result["error"] = "Proses terlalu lama (timeout). Coba file yang lebih kecil."
    except Exception as exc:  # noqa: BLE001
        out_path.unlink(missing_ok=True)
        result["error"] = f"Gagal memproses PDF: {exc}"

    return result


def compress_pdfs(entries, output_dir, preset: str, gs_path: str, timeout: int = 300, max_workers: int = 2) -> list:
    """Kompres banyak PDF secara paralel. Urutan hasil sama dengan urutan input."""
    results = [None] * len(entries)
    if not entries:
        return results

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(
                compress_pdf,
                entry["path"], output_dir, entry["original_name"], preset, gs_path, timeout,
            ): index
            for index, entry in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()

    return results


# =========================================================
# GAMBAR -> PDF
# =========================================================

PAGE_SIZES = {
    "image": "Sesuai ukuran gambar",
    "a4": "A4 (otomatis portrait/landscape)",
    "letter": "Letter (otomatis portrait/landscape)",
}
_PAGE_DIMENSIONS_MM = {"a4": (210, 297), "letter": (215.9, 279.4)}
RENDER_DPI = 150  # dipakai saat halaman mengikuti ukuran gambar
MAX_MARGIN_MM = 30


def _prepare_page(entry: dict, work_dir: Path, index: int):
    """
    Siapkan satu gambar untuk dimasukkan ke PDF.
    Mengembalikan (path_file, error). JPEG biasa dipakai apa adanya (tanpa kompres ulang);
    format lain, gambar transparan, atau foto yang perlu diputar dikonversi ke JPEG kualitas 95.
    """
    path = entry["path"]
    try:
        with Image.open(path) as source:
            orientation = source.getexif().get(274, 1)
            if source.format == "JPEG" and source.mode in ("RGB", "L") and orientation in (0, 1):
                return path, None
            img = ImageOps.exif_transpose(source)
            img.load()

        prepared = image_service.prepare_image(img, "JPEG")  # alpha -> latar putih, CMYK -> RGB
        out_path = work_dir / f"page_{index:04d}.jpg"
        prepared.save(out_path, "JPEG", quality=95)
        return out_path, None
    except Exception as exc:  # noqa: BLE001
        return None, image_service._friendly_error(exc)


def _layout_function(page_size: str, margin_mm: float):
    if page_size in _PAGE_DIMENSIONS_MM:
        width_mm, height_mm = _PAGE_DIMENSIONS_MM[page_size]
        margin = img2pdf.mm_to_pt(margin_mm)
        return img2pdf.get_layout_fun(
            pagesize=(img2pdf.mm_to_pt(width_mm), img2pdf.mm_to_pt(height_mm)),
            border=(margin, margin),
            fit=img2pdf.FitMode.into,   # gambar diperkecil agar muat, rasio tetap
            auto_orient=True,           # halaman mengikuti orientasi gambar
        )
    return img2pdf.get_fixed_dpi_layout_fun((RENDER_DPI, RENDER_DPI))


def images_to_pdf(entries, output_path, work_dir, page_size: str = "image",
                  margin_mm: float = 0, max_workers: int = 4) -> dict:
    """
    Gabungkan gambar menjadi satu PDF, urutan halaman = urutan entries.

    Mengembalikan:
      {"pages": jumlah halaman, "used": [entry yang masuk PDF],
       "failed": [{"name":..., "error":...}], "error": pesan atau None}
    """
    output_path, work_dir = Path(output_path), Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    outcome = {"pages": 0, "used": [], "failed": [], "error": None}

    if page_size not in PAGE_SIZES:
        page_size = "image"

    # Siapkan semua halaman secara paralel; executor.map menjaga urutan
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        prepared = list(executor.map(
            lambda pair: _prepare_page(pair[1], work_dir, pair[0]), enumerate(entries)
        ))

    page_paths = []
    for entry, (page_path, error) in zip(entries, prepared):
        if error:
            outcome["failed"].append({"name": entry["original_name"], "error": error})
        else:
            page_paths.append(str(page_path))
            outcome["used"].append(entry)

    if not page_paths:
        return outcome

    try:
        pdf_bytes = img2pdf.convert(page_paths, layout_fun=_layout_function(page_size, margin_mm))
        output_path.write_bytes(pdf_bytes)
        outcome["pages"] = len(page_paths)
    except Exception as exc:  # noqa: BLE001
        outcome["error"] = f"Gagal membuat PDF: {exc}"
        outcome["used"] = []

    return outcome
