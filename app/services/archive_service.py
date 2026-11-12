from asyncio import subprocess
import os
import re
import shutil
import zipfile
import py7zr
import rarfile
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

# =========================================================
# DETEKSI WINRAR (Untuk buat file RAR)
# =========================================================
def find_winrar() -> "str | None":
    """Cari file rar.exe dari WinRAR."""
    if os.name != "nt":
        return shutil.which("rar")
    
    candidates = [
        r"C:\Program Files\WinRAR\rar.exe",
        r"C:\Program Files (x86)\WinRAR\rar.exe",
    ]
    for c in candidates:
        if Path(c).is_file():
            return c
    return shutil.which("rar")

# =========================================================
# EKSTRAK ARSIP (Zip, RAR, 7z)
# =========================================================
def extract_archive(archive_path, extract_dir):
    """Ekstrak ZIP, RAR, atau 7z ke dalam folder tujuan."""
    archive_path = Path(archive_path)
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    ext = archive_path.suffix.lower()
    
    try:
        if ext == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(extract_dir)
        elif ext == ".7z":
            with py7zr.SevenZipFile(archive_path, mode="r") as zf:
                zf.extractall(extract_dir)
        elif ext == ".rar":
            with rarfile.RarFile(archive_path) as rf:
                rf.extractall(extract_dir)
        else:
            raise ValueError("Format arsip tidak didukung.")
    except Exception as exc:
        # Tangkap error jika password (misal encrypted file) atau file korup
        raise ValueError(f"Gagal mengekstrak: {exc}")

def extract_archives_to_zip(entries, output_dir, work_dir) -> dict:
    """
    Ekstrak arsip yang di-upload, lalu bungkus kembali isinya menjadi 1 file ZIP baru.
    """
    outcome = {"count": 0, "original_size": 0, "failed": [], "error": None}
    work_dir.mkdir(parents=True, exist_ok=True)
    
    for entry in entries:
        try:
            # Ekstrak ke folder sementara
            temp_extract = work_dir / f"ext_{entry['path'].stem}"
            extract_archive(entry["path"], temp_extract)
            
            # Bungkus kembali ke ZIP
            zip_name = f"{entry['path'].stem}_extracted.zip"
            output_zip = output_dir / zip_name
            
            with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(temp_extract):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(temp_extract)
                        zf.write(file_path, arcname=arcname)
                        
            outcome["count"] += 1
            outcome["original_size"] += entry["path"].stat().st_size
            
            # Bersihkan folder sementara setelah satu arsip selesai
            shutil.rmtree(temp_extract, ignore_errors=True)
        except Exception as exc:
            outcome["failed"].append({"name": entry["original_name"], "error": str(exc)})
            
    if outcome["count"] == 0:
        outcome["error"] = "Tidak ada arsip yang berhasil diekstrak."
    
    return outcome

# =========================================================
# KOMPRESI KE 7Z / RAR
# =========================================================
def compress_to_7z(files, output_path, work_dir) -> dict:
    """Bungkus kumpulan file menjadi .7z (mempertahankan struktur folder)."""
    output_path = Path(output_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Simpan semua file di folder sementara (mirip dengan zip_files)
    used_names = set()
    for index, storage in enumerate(files):
        original = storage.filename or f"file_{index}"
        arcname = _safe_arcname(original)
        if not arcname: continue
        
        # pastikan unik
        base_arc = arcname
        counter = 1
        while str(arcname).lower() in used_names:
            arcname = base_arc.with_name(f"{base_arc.stem}_{counter}{base_arc.suffix}")
            counter += 1
        used_names.add(str(arcname).lower())
        
        tmp = work_dir / str(arcname)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        storage.save(tmp)
        
    with py7zr.SevenZipFile(output_path, 'w') as archive:
        archive.writeall(work_dir, arcname='')
        
    shutil.rmtree(work_dir, ignore_errors=True)
    return {"status": "success", "output": output_path.name}

def compress_to_rar(files, output_path, work_dir, rar_exe) -> dict:
    """Bungkus file jadi .rar menggunakan WinRAR."""
    output_path = Path(output_path)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    
    used_names = set()
    for index, storage in enumerate(files):
        original = storage.filename or f"file_{index}"
        arcname = _safe_arcname(original)
        if not arcname: continue
        
        base_arc = arcname
        counter = 1
        while str(arcname).lower() in used_names:
            arcname = base_arc.with_name(f"{base_arc.stem}_{counter}{base_arc.suffix}")
            counter += 1
        used_names.add(str(arcname).lower())
        
        tmp = work_dir / str(arcname)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        storage.save(tmp)
        
    # Panggil rar.exe secara silent
    cmd = [rar_exe, "a", "-r", "-idq", str(output_path.resolve()), "."]
    subprocess.run(cmd, cwd=str(work_dir.resolve()), check=True, capture_output=True)
    
    shutil.rmtree(work_dir, ignore_errors=True)
    return {"status": "success", "output": output_path.name}