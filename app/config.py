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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    BASE_DIR = BASE_DIR

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

    # ----- Upscale (Real-ESRGAN ncnn Vulkan) -----
    # Kosongkan agar dicari otomatis di tools/realesrgan-ncnn-vulkan atau PATH
    REALESRGAN_PATH = os.getenv("REALESRGAN_PATH", "")
    # RTX 3050 4GB: maksimal 2 proses bersamaan agar tidak kehabisan VRAM
    UPSCALE_WORKERS = _env_int("UPSCALE_WORKERS", 2)
    # Ukuran tile: kecil = hemat VRAM tapi lebih lambat. 0 = otomatis
    UPSCALE_TILE_SIZE = _env_int("UPSCALE_TILE_SIZE", 128)
    UPSCALE_GPU_ID = os.getenv("UPSCALE_GPU_ID", "")
    UPSCALE_MAX_FILES = _env_int("UPSCALE_MAX_FILES", 10)
    # Batas ukuran gambar (megapiksel) agar proses tidak berjam-jam / kehabisan memori
    UPSCALE_MAX_INPUT_MP = _env_float("UPSCALE_MAX_INPUT_MP", 4.0)
    UPSCALE_MAX_OUTPUT_MP = _env_float("UPSCALE_MAX_OUTPUT_MP", 64.0)
    # Jumlah gambar maksimal yang boleh menunggu di antrean (semua pengguna)
    UPSCALE_MAX_QUEUE = _env_int("UPSCALE_MAX_QUEUE", 30)
    UPSCALE_TIMEOUT_SECONDS = _env_int("UPSCALE_TIMEOUT_SECONDS", 900)

    # PDF -> Gambar: batas jumlah halaman per PDF (mencegah abuse & memory blow-up)
    PDF_RENDER_MAX_PAGES = _env_int("PDF_RENDER_MAX_PAGES", 100)
