import re
import shutil
import time
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def new_job_id() -> str:
    return uuid.uuid4().hex


def is_valid_job_id(value: str) -> bool:
    return bool(JOB_ID_PATTERN.match(value or ""))


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def safe_filename(filename: str, fallback: str = "file") -> str:
    """Nama file aman untuk disimpan di disk (tanpa spasi/karakter aneh)."""
    path = Path(filename)
    stem = secure_filename(path.stem) or fallback
    return stem + path.suffix.lower()


def unique_filename(name: str, used_stems: set) -> str:
    """Pastikan nama (tanpa ekstensi) unik di dalam satu job."""
    path = Path(name)
    stem, ext = path.stem, path.suffix
    candidate, counter = stem, 1
    while candidate.lower() in used_stems:
        candidate = f"{stem}_{counter}"
        counter += 1
    used_stems.add(candidate.lower())
    return candidate + ext


def human_size(size_bytes: float) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"


def save_uploaded_files(files, dest_dir, allowed_extensions, validator=None) -> list:
    """
    Simpan file upload ke dest_dir dengan nama aman dan unik.

    Mengembalikan list sesuai urutan upload. Tiap item:
      {"original_name": str, "path": Path | None, "error": str | None}
    path = None berarti file ditolak (lihat 'error').
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    allowed_text = ", ".join(sorted(allowed_extensions))

    used_stems = set()
    entries = []

    for storage in files:
        original_name = storage.filename or "file"

        if get_extension(original_name) not in allowed_extensions:
            entries.append({
                "original_name": original_name,
                "path": None,
                "error": f"Format tidak didukung. Gunakan: {allowed_text}",
            })
            continue

        disk_name = unique_filename(safe_filename(original_name), used_stems)
        path = dest_dir / disk_name
        storage.save(path)

        if validator and not validator(path):
            path.unlink(missing_ok=True)
            entries.append({
                "original_name": original_name,
                "path": None,
                "error": "File tidak valid atau rusak.",
            })
            continue

        entries.append({"original_name": original_name, "path": path, "error": None})

    return entries


def merge_results(entries: list, processed: list) -> list:
    """Gabungkan file yang ditolak saat upload dengan hasil proses, urutan tetap."""
    processed_iter = iter(processed)
    results = []
    for entry in entries:
        if entry["path"] is None:
            results.append({
                "name": entry["original_name"],
                "status": "failed",
                "error": entry["error"],
            })
        else:
            results.append(next(processed_iter))
    return results


def cleanup_old_jobs(folders, max_age_minutes: int) -> None:
    """Hapus sub-folder job yang lebih lama dari batas retensi."""
    cutoff = time.time() - max_age_minutes * 60
    for folder in folders:
        folder = Path(folder)
        if not folder.exists():
            continue
        for job_dir in folder.iterdir():
            if not job_dir.is_dir():
                continue
            try:
                if job_dir.stat().st_mtime < cutoff:
                    shutil.rmtree(job_dir, ignore_errors=True)
            except OSError:
                pass
