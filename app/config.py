import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Folder kerja (dibuat otomatis saat app start)
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    OUTPUT_FOLDER = BASE_DIR / "outputs"

    # Batas upload
    MAX_UPLOAD_MB = _env_int("MAX_CONTENT_LENGTH_MB", 200)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    MAX_FILES_PER_REQUEST = _env_int("MAX_FILES_PER_REQUEST", 20)
    # Gambar ke PDF biasanya berisi banyak halaman scan, jadi batasnya lebih longgar
    MAX_FILES_MERGE = _env_int("MAX_FILES_MERGE", 100)

    # File hasil dihapus otomatis setelah sekian menit
    FILE_RETENTION_MINUTES = _env_int("FILE_RETENTION_MINUTES", 60)

    # Jumlah proses paralel
    IMAGE_WORKERS = _env_int("IMAGE_WORKERS", 4)
    PDF_WORKERS = _env_int("PDF_WORKERS", 2)

    # Ghostscript: kosongkan agar dicari otomatis
    GHOSTSCRIPT_PATH = os.getenv("GHOSTSCRIPT_PATH", "")
    PDF_TIMEOUT_SECONDS = _env_int("PDF_TIMEOUT_SECONDS", 300)
