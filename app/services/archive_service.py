import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath


def make_zip(zip_path, files) -> Path:
    """Bungkus beberapa file menjadi satu ZIP (nama di dalam ZIP = nama file)."""
    zip_path = Path(zip_path)
    # Gambar/PDF hasil kompres sudah padat, jadi tidak perlu dikompres lagi.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for file in files:
            zf.write(file, arcname=Path(file).name)
    return zip_path


# =========================================================
# ZIP FOLDER (dari upload web, struktur folder dipertahankan)
# =========================================================

COMPRESSION_LEVELS = {
    "deflate": ("Kompres (lebih kecil, agak lambat)", zipfile.ZIP_DEFLATED),
    "store": ("Cepat (tanpa kompresi, cocok foto/video)", zipfile.ZIP_STORED),
}
DEFAULT_COMPRESSION = "deflate"


def clean_zip_name(raw: str) -> str:
    """Sanitasi nama file ZIP dari input user."""
    name = (raw or "").strip()
    if name.lower().endswith(".zip"):
        name = name[:-4]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    return name[:80] or "arsip"


def _safe_arcname(filename: str):
    """
    Bersihkan path relatif di dalam ZIP.
    - normalisasi separator ke '/'
    - buang komponen kosong / '.' / '..' (anti path traversal)
    - buang karakter berbahaya Windows
    Return PurePosixPath atau None jika tidak valid.
    """
    name = (filename or "").replace("\\", "/").lstrip("/")
    parts = []
    for part in PurePosixPath(name).parts:
        if part in ("", ".", ".."):
            continue
        cleaned = re.sub(r'[<>:"|?*\x00-\x1f]', "_", part).strip()
        if cleaned:
            parts.append(cleaned)
    return PurePosixPath(*parts) if parts else None


def zip_files(files, output_path, work_dir, compression: str = DEFAULT_COMPRESSION) -> dict:
    """
    ZIP kumpulan FileStorage. Jika filename berisi path relatif (mis. dari
    input folder <webkitdirectory>), struktur folder dipertahankan.

    Mengembalikan:
      {"count": jumlah file masuk ZIP,
       "original_size": total byte input,
       "failed": [{"name":..., "error":...}],
       "error": pesan fatal atau None}
    """
    output_path = Path(output_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    outcome = {"count": 0, "original_size": 0, "failed": [], "error": None}
    mode = COMPRESSION_LEVELS.get(compression, COMPRESSION_LEVELS[DEFAULT_COMPRESSION])[1]
    used_names: set[str] = set()

    try:
        with zipfile.ZipFile(output_path, "w", compression=mode, allowZip64=True) as zf:
            for index, storage in enumerate(files):
                original = storage.filename or f"file_{index}"
                arcname = _safe_arcname(original)

                if arcname is None:
                    outcome["failed"].append(
                        {"name": original, "error": "Nama file tidak valid."}
                    )
                    continue

                # Pastikan nama unik (jika ada duplikat dari folder berbeda)
                base_arc = arcname
                counter = 1
                while str(arcname).lower() in used_names:
                    arcname = base_arc.with_name(
                        f"{base_arc.stem}_{counter}{base_arc.suffix}"
                    )
                    counter += 1
                used_names.add(str(arcname).lower())

                # Simpan ke file sementara dulu (agar tidak load seluruh file ke RAM)
                tmp = work_dir / f"part_{index:05d}"
                try:
                    storage.save(tmp)
                    size = tmp.stat().st_size
                    zf.write(tmp, arcname=str(arcname))
                    outcome["count"] += 1
                    outcome["original_size"] += size
                except Exception as exc:  # noqa: BLE001
                    outcome["failed"].append(
                        {"name": original, "error": f"Gagal menambahkan: {exc}"}
                    )
                finally:
                    tmp.unlink(missing_ok=True)

        if outcome["count"] == 0:
            output_path.unlink(missing_ok=True)
            outcome["error"] = "Tidak ada file yang bisa diarsipkan."
    except Exception as exc:  # noqa: BLE001
        outcome["error"] = f"Gagal membuat ZIP: {exc}"
        output_path.unlink(missing_ok=True)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return outcome