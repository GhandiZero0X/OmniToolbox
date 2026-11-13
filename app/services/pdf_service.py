import sys
import uuid
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

# =========================================================
# MERGE PDF
# =========================================================

def merge_pdfs(entries, output_path) -> dict:
    """
    Gabungkan banyak PDF menjadi satu. Urutan = urutan entries.
    Mengembalikan:
      {"pages": jumlah halaman,
       "used": [entry yang berhasil],
       "failed": [{"name":..., "error":...}],
       "error": pesan fatal atau None}
    """
    from pypdf import PdfReader, PdfWriter

    output_path = Path(output_path)
    outcome = {"pages": 0, "used": [], "failed": [], "error": None}

    writer = PdfWriter()
    for entry in entries:
        try:
            reader = PdfReader(str(entry["path"]))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")  # coba password kosong
                except Exception:
                    raise ValueError("PDF terenkripsi, tidak bisa digabung.")
            for page in reader.pages:
                writer.add_page(page)
            outcome["used"].append(entry)
        except Exception as exc:  # noqa: BLE001
            outcome["failed"].append({
                "name": entry["original_name"],
                "error": f"Gagal membaca PDF: {exc}",
            })

    if not outcome["used"]:
        outcome["error"] = "Tidak ada PDF valid yang bisa digabung."
        return outcome

    try:
        with open(output_path, "wb") as fh:
            writer.write(fh)
        outcome["pages"] = len(writer.pages)
    except Exception as exc:  # noqa: BLE001
        output_path.unlink(missing_ok=True)
        outcome["error"] = f"Gagal menulis PDF: {exc}"
        outcome["used"] = []

    return outcome


# =========================================================
# PDF -> GAMBAR
# =========================================================

PDF_RENDER_DPI = {
    "72": 72,     # cepat, untuk pratinjau
    "100": 100,
    "150": 150,   # seimbang, disarankan
    "200": 200,
    "300": 300,   # cetak
}
DEFAULT_RENDER_DPI = "150"
RENDER_FORMATS = {"jpg", "png"}
DEFAULT_RENDER_FORMAT = "jpg"

_RENDER_FORMAT_BY_CHOICE = {"jpg": "JPEG", "png": "PNG"}
_RENDER_EXT_BY_CHOICE = {"jpg": ".jpg", "png": ".png"}


def render_pdf(path, output_dir, original_name: str, dpi: int, fmt: str,
               quality: int, max_pages: int) -> list:
    """
    Render setiap halaman PDF menjadi gambar.
    Mengembalikan list dict (satu per halaman), plus baris error jika ada.
    """
    import fitz  # PyMuPDF

    path, output_dir = Path(path), Path(output_dir)
    results = []

    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # noqa: BLE001
        return [{"name": original_name, "status": "failed",
                 "error": f"Gagal membuka PDF: {exc}"}]

    try:
        total_pages = len(doc)
        if total_pages == 0:
            return [{"name": original_name, "status": "failed",
                     "error": "PDF tidak memiliki halaman."}]
        if total_pages > max_pages:
            return [{"name": original_name, "status": "failed",
                     "error": f"PDF memiliki {total_pages} halaman, melebihi batas {max_pages}."}]

        target_format = _RENDER_FORMAT_BY_CHOICE[fmt]
        extension = _RENDER_EXT_BY_CHOICE[fmt]
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        original_size = path.stat().st_size
        # perkiraan porsi ukuran input per halaman (untuk laporan summary)
        per_page_input = original_size // max(total_pages, 1)
        stem = path.stem

        for i in range(total_pages):
            try:
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                del pix

                out_name = f"{stem}_p{i+1:03d}{extension}"
                out_path = output_dir / out_name

                # PNG selalu lossless; kualitas hanya berlaku untuk JPG
                effective_quality = 100 if target_format == "PNG" else quality
                image_service.save_image(img, out_path, target_format, effective_quality)

                thumb = image_service.save_thumbnail(
                    img, output_dir, f"{stem}_p{i+1:03d}"
                )
                del img

                results.append({
                    "name": f"{original_name} - hal. {i+1}",
                    "status": "success",
                    "output": out_name,
                    "original_size": per_page_input,
                    "new_size": out_path.stat().st_size,
                    "saved_percent": 0,
                    "kept_original": False,
                    "badge": extension.lstrip(".").upper(),
                    "thumb": thumb,
                })
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "name": f"{original_name} - hal. {i+1}",
                    "status": "failed",
                    "error": f"Gagal render halaman: {exc}",
                })
    finally:
        doc.close()

    return results


def render_pdfs(entries, output_dir, dpi: int, fmt: str, quality: int,
                max_pages: int, max_workers: int = 2) -> list:
    """
    Render banyak PDF secara paralel. Urutan hasil = urutan input (flat list).
    """
    if not entries:
        return []

    batches = [None] * len(entries)
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(
                render_pdf, e["path"], output_dir, e["original_name"],
                dpi, fmt, quality, max_pages,
            ): i
            for i, e in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            batches[future_to_index[future]] = future.result()

    flat = []
    for batch in batches:
        flat.extend(batch)
    return flat

# =========================================================
# WORD -> PDF via Microsoft Word (docx2pdf)
# =========================================================

WORD_INPUT_EXTENSIONS = {".docx"}   # .doc lama tidak didukung docx2pdf

WORD_SETUP_HINT = (
    "Microsoft Word tidak terdeteksi. Fitur ini membutuhkan Microsoft Word terinstall & teraktivasi. "
    "Jika Word sudah ada, pastikan `pip install docx2pdf` sudah berhasil."
)


def is_word_via_com_available() -> bool:
    """Cek apakah Microsoft Word bisa dipakai via COM (Windows + docx2pdf)."""
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa: F401
        from docx2pdf import convert  # noqa: F401
        return True
    except ImportError:
        return False


def is_word_file(path) -> bool:
    """Cek signature .docx (ZIP archive dengan header PK)."""
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"PK\x03\x04"
    except OSError:
        return False


def word_to_pdf(path, output_dir, original_name: str, timeout: int = 120) -> dict:
    """Konversi satu .docx ke PDF via Microsoft Word. Tidak melempar error."""
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    if path.suffix.lower() != ".docx":
        result["error"] = "Hanya file .docx yang didukung. Simpan .doc lama sebagai .docx dulu."
        return result

    # COM harus diinisialisasi di thread yang sama dengan Word
    com_initialized = False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception:  # noqa: BLE001 - beberapa versi docx2pdf init sendiri
        pass

    try:
        from docx2pdf import convert

        original_size = path.stat().st_size
        expected_out = output_dir / f"{path.stem}.pdf"
        expected_out.unlink(missing_ok=True)  # hindari konflik dengan hasil lama

        convert(str(path.resolve()), str(expected_out.resolve()))

        if not expected_out.exists() or expected_out.stat().st_size == 0:
            expected_out.unlink(missing_ok=True)
            result["error"] = "Word tidak menghasilkan file PDF."
            return result

        result.update({
            "status": "success",
            "output": expected_out.name,
            "original_size": original_size,
            "new_size": expected_out.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "PDF",
        })
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Gagal mengonversi Word: {exc}"
    finally:
        if com_initialized:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass

    return result


def word_to_pdfs(entries, output_dir, timeout: int = 120, max_workers: int = 1) -> list:
    """
    Konversi banyak Word. SELALU serial (bukan paralel) — Word COM tidak
    thread-safe, dua instance Word di thread berbeda bisa crash.
    Parameter max_workers dipertahankan hanya untuk signature compatibility.
    """
    return [
        word_to_pdf(e["path"], output_dir, e["original_name"], timeout)
        for e in entries
    ]


# =========================================================
# PDF -> WORD (pdf2docx)
# =========================================================

def pdf_to_word(path, output_dir, original_name: str, max_pages: int = 50) -> dict:
    """Konversi satu PDF ke DOCX via pdf2docx. Tidak melempar error."""
    from pdf2docx import Converter
    import fitz

    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}
    out_name = f"{path.stem}.docx"
    out_path = output_dir / out_name

    try:
        original_size = path.stat().st_size

        # Cek jumlah halaman dulu (proteksi batas waktu proses)
        with fitz.open(str(path)) as doc:
            page_count = len(doc)
        if page_count == 0:
            return {**result, "error": "PDF tidak memiliki halaman."}
        if page_count > max_pages:
            return {**result, "error":
                    f"PDF memiliki {page_count} halaman, melebihi batas {max_pages}."}

        cv = Converter(str(path))
        try:
            cv.convert(str(out_path), start=0, end=page_count)
        finally:
            cv.close()

        if not out_path.exists() or out_path.stat().st_size == 0:
            out_path.unlink(missing_ok=True)
            return {**result, "error":
                    "pdf2docx tidak menghasilkan file. PDF mungkin hasil scan "
                    "(butuh OCR) atau strukturnya terlalu kompleks."}

        result.update({
            "status": "success",
            "output": out_name,
            "original_size": original_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "DOCX",
            "info": f"{page_count} halaman",
        })
    except Exception as exc:  # noqa: BLE001
        out_path.unlink(missing_ok=True)
        result["error"] = f"Gagal mengonversi PDF ke Word: {exc}"

    return result


def pdf_to_words(entries, output_dir, max_pages: int = 50,
                 max_workers: int = 2) -> list:
    """Konversi banyak PDF ke DOCX secara paralel."""
    results = [None] * len(entries)
    if not entries:
        return results

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(
                pdf_to_word, e["path"], output_dir, e["original_name"], max_pages,
            ): i
            for i, e in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()

    return results

# =========================================================
# SPLIT PDF
# =========================================================

def parse_page_range(range_str: str, total_pages: int) -> list[int]:
    """
    Ubah string seperti '1-3, 5, 8-10' menjadi list index 0-based: [0,1,2,4,7,8,9].
    Angka 1 di UI = index 0 di list.
    """
    pages = set()
    if not range_str or not range_str.strip():
        return []

    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                # Pastikan urutan benar (misal user ketik 5-2, jadikan 2-5)
                start, end = min(start, end), max(start, end)
                for p in range(start, end + 1):
                    if 1 <= p <= total_pages:
                        pages.add(p - 1)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p - 1)
            except ValueError:
                continue

    return sorted(list(pages))


def split_pdf(path, output_dir, original_name: str, mode: str, page_range_str: str) -> list:
    """
    Pisahkan PDF. Tidak melempar error, mengembalikan list of dict (karena 1 file bisa jadi banyak output).
    mode: "every_page" atau "range"
    """
    from pypdf import PdfReader, PdfWriter
    
    path, output_dir = Path(path), Path(output_dir)
    results = []

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return [{"name": original_name, "status": "failed", "error": "PDF terenkripsi."}]
                
        total_pages = len(reader.pages)
        if total_pages == 0:
            return [{"name": original_name, "status": "failed", "error": "PDF kosong."}]

        # Kalkulasi porsi ukuran file asli per halaman untuk laporan
        original_size = path.stat().st_size
        per_page_size = original_size // total_pages

        if mode == "every_page":
            for i in range(total_pages):
                writer = PdfWriter()
                writer.add_page(reader.pages[i])
                
                out_name = f"{path.stem}_hal_{i+1}.pdf"
                out_path = output_dir / out_name
                
                with open(out_path, "wb") as fh:
                    writer.write(fh)
                    
                results.append({
                    "name": f"{original_name} (hal. {i+1})",
                    "status": "success",
                    "output": out_name,
                    "original_size": per_page_size,
                    "new_size": out_path.stat().st_size,
                    "saved_percent": 0,
                    "kept_original": False,
                    "badge": f"Hal {i+1}",
                })
                
        elif mode == "range":
            pages_to_extract = parse_page_range(page_range_str, total_pages)
            if not pages_to_extract:
                return [{"name": original_name, "status": "failed", "error": "Rentang halaman tidak valid atau kosong."}]
                
            writer = PdfWriter()
            for p_idx in pages_to_extract:
                writer.add_page(reader.pages[p_idx])
                
            out_name = f"{path.stem}_terpilih.pdf"
            out_path = output_dir / out_name
            
            with open(out_path, "wb") as fh:
                writer.write(fh)
                
            results.append({
                "name": f"{original_name} (ekstrak)",
                "status": "success",
                "output": out_name,
                "original_size": per_page_size * len(pages_to_extract),
                "new_size": out_path.stat().st_size,
                "saved_percent": 0,
                "kept_original": False,
                "badge": f"{len(pages_to_extract)} hal.",
            })
            
    except Exception as exc:  # noqa: BLE001
        return [{"name": original_name, "status": "failed", "error": f"Gagal memisahkan PDF: {exc}"}]

    return results


def split_pdfs(entries, output_dir, mode: str, page_range_str: str) -> list:
    """Proses banyak PDF secara berurutan. Mengembalikan flat list hasil."""
    all_results = []
    for e in entries:
        batch = split_pdf(e["path"], output_dir, e["original_name"], mode, page_range_str)
        all_results.extend(batch)
    return all_results

# =========================================================
# ORGANIZE PDF (RENDER THUMBNAILS & SIMPAN PERUBAHAN)
# =========================================================

def extract_pdf_thumbnails(pdf_paths: list, output_dir) -> list:
    """
    Render halaman dari BEBERAPA PDF menjadi gambar PNG.
    Mengembalikan list of dict: [{"file_id": 0, "filename": "pdf0_0.png"}, ...]
    """
    import fitz
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    thumbnails = []
    for file_id, pdf_path in enumerate(pdf_paths):
        try:
            doc = fitz.open(str(pdf_path))
            for page_idx in range(len(doc)):
                page = doc.load_page(page_idx)
                # Render resolusi lebih tinggi (400px) agar bagus saat di-zoom
                zoom = 400 / page.rect.width if page.rect.width > 0 else 1
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                filename = f"pdf{file_id}_p{page_idx}.png"
                img_path = output_dir / filename
                pix.save(str(img_path))
                
                thumbnails.append({
                    "file_id": file_id,
                    "page_index": page_idx,
                    "filename": filename
                })
            doc.close()
        except Exception as exc:
            raise ValueError(f"Gagal membaca PDF {file_id + 1}: {exc}")
            
    return thumbnails

def save_organized_pdf(pdf_paths: list, output_path, operations: list):
    """
    Simpan PDF gabungan berdasarkan urutan, rotasi, dan asal file.
    operations = [{"file_id": 0, "page_index": 2, "rotation": 90}, ...]
    """
    from pypdf import PdfReader, PdfWriter
    
    output_path = Path(output_path)
    readers = [PdfReader(str(p)) for p in pdf_paths]
    writer = PdfWriter()
    
    try:
        for op in operations:
            file_id = op["file_id"]
            page_idx = op["page_index"]
            rot = op.get("rotation", 0)
            
            if 0 <= file_id < len(readers):
                reader = readers[file_id]
                if 0 <= page_idx < len(reader.pages):
                    page = reader.pages[page_idx]
                    if rot > 0:
                        page.rotate(rot)
                    writer.add_page(page)
                
        if len(writer.pages) == 0:
            raise ValueError("PDF tidak boleh kosong. Sisakan minimal 1 halaman.")
            
        with open(output_path, "wb") as fh:
            writer.write(fh)
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise ValueError(f"Gagal menyimpan PDF: {exc}")

# =========================================================
# KUNCI & BUKA KUNCI PDF
# =========================================================

def lock_pdf(path, output_dir, original_name: str, password: str) -> dict:
    from pypdf import PdfReader, PdfWriter
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}
    out_path = output_dir / f"{path.stem}_locked.pdf"

    try:
        reader = PdfReader(str(path))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
            
        writer.encrypt(user_password=password)
        
        with open(out_path, "wb") as f:
            writer.write(f)
            
        result.update({
            "status": "success", "output": out_path.name,
            "original_size": path.stat().st_size, "new_size": out_path.stat().st_size,
            "saved_percent": 0, "kept_original": False, "badge": "Terkunci",
        })
    except Exception as exc:
        result["error"] = f"Gagal mengunci PDF: {exc}"
    return result

def unlock_pdf(path, output_dir, original_name: str, password: str) -> dict:
    from pypdf import PdfReader, PdfWriter
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}
    out_path = output_dir / f"{path.stem}_unlocked.pdf"

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            if not reader.decrypt(password):
                return {**result, "error": "Password salah atau PDF tidak bisa dibuka."}
                
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
            
        with open(out_path, "wb") as f:
            writer.write(f)
            
        result.update({
            "status": "success", "output": out_path.name,
            "original_size": path.stat().st_size, "new_size": out_path.stat().st_size,
            "saved_percent": 0, "kept_original": False, "badge": "Terbuka",
        })
    except Exception as exc:
        result["error"] = f"Gagal membuka PDF: {exc}"
    return result

# =========================================================
# WATERMARK PDF
# =========================================================

def watermark_pdf(path, output_dir, original_name: str, text: str) -> dict:
    import pymupdf  # Menggunakan pymupdf (bukan fitz) untuk menghilangkan FutureWarning
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}
    out_path = output_dir / f"{path.stem}_watermark.pdf"

    try:
        doc = pymupdf.open(str(path))
        
        # Hitung lebar teks agar bisa diletakkan tepat di tengah
        font = pymupdf.Font("helv")
        text_width = font.text_length(text, fontsize=60)

        for page in doc:
            rect = page.rect
            pivot = pymupdf.Point(rect.width / 2, rect.height / 2)
            
            # Gunakan morph (pivot, matrix) untuk rotasi 45 derajat
            page.insert_text(
                (pivot.x - text_width / 2, pivot.y + 20), # 20 adalah offset vertikal agar center
                text,
                fontsize=60,
                color=(0.8, 0.2, 0.2), 
                fill_opacity=0.3,
                morph=(pivot, pymupdf.Matrix(1, 1).prerotate(45)) # <-- ROTASI 45 DERAJAT
            )
            
        doc.save(str(out_path))
        doc.close()

        result.update({
            "status": "success", "output": out_path.name,
            "original_size": path.stat().st_size, "new_size": out_path.stat().st_size,
            "saved_percent": 0, "kept_original": False, "badge": "Watermark",
        })
    except Exception as exc:
        result["error"] = f"Gagal memberi watermark: {exc}"
    return result