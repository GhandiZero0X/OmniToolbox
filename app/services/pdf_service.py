import glob
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

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
