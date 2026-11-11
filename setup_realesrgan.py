#!/usr/bin/env python3
"""
Pasang Real-ESRGAN ncnn Vulkan untuk fitur Upscale Foto.

Cara pakai (jalankan dari folder project):
    python setup_realesrgan.py                 # unduh otomatis sesuai sistem operasi
    python setup_realesrgan.py --zip file.zip  # pakai ZIP yang sudah kamu unduh manual
    python setup_realesrgan.py --force         # pasang ulang

Hasil: tools/realesrgan-ncnn-vulkan/ (berisi program + folder models).
Butuh GPU dan driver yang mendukung Vulkan (NVIDIA / AMD / Intel Arc).
"""
import argparse
import os
import platform
import stat
import sys
import urllib.request
import zipfile
from pathlib import Path

RELEASE_BASE = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
ASSETS = {
    "Windows": "realesrgan-ncnn-vulkan-20220424-windows.zip",
    "Linux": "realesrgan-ncnn-vulkan-20220424-ubuntu.zip",
    "Darwin": "realesrgan-ncnn-vulkan-20220424-macos.zip",
}
DEFAULT_DEST = Path(__file__).resolve().parent / "tools" / "realesrgan-ncnn-vulkan"
EXE_NAME = "realesrgan-ncnn-vulkan.exe" if os.name == "nt" else "realesrgan-ncnn-vulkan"
REQUIRED_MODEL = "realesrgan-x4plus"


def download(url: str, target: Path) -> None:
    def progress(block_num, block_size, total_size):
        if total_size > 0:
            percent = min(block_num * block_size * 100 / total_size, 100)
            print(f"\r[UNDUH] {percent:5.1f}%", end="", flush=True)

    print(f"[INFO] Mengunduh {url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, target, reporthook=progress)
    print()


def safe_extract(zip_path: Path, dest: Path) -> None:
    """Ekstrak ZIP, menolak entri yang mencoba keluar dari folder tujuan (zip-slip)."""
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (dest / member.filename).resolve()
            if target != dest and dest not in target.parents:
                raise ValueError(f"Entri ZIP tidak aman, dibatalkan: {member.filename}")
        archive.extractall(dest)


def find_exe(folder: Path):
    for found in sorted(folder.rglob(EXE_NAME)):
        if found.is_file():
            return found
    return None


def install(zip_path: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    print("[INFO] Mengekstrak...")
    safe_extract(zip_path, dest)

    exe = find_exe(dest)
    if exe is None:
        raise FileNotFoundError(f"{EXE_NAME} tidak ditemukan di dalam ZIP.")
    if os.name != "nt":
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return exe


def main() -> int:
    parser = argparse.ArgumentParser(description="Pasang Real-ESRGAN ncnn Vulkan")
    parser.add_argument("--zip", type=Path, help="pakai file ZIP lokal (tanpa mengunduh)")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="folder tujuan")
    parser.add_argument("--force", action="store_true", help="pasang ulang walau sudah ada")
    args = parser.parse_args()

    existing = find_exe(args.dest) if args.dest.exists() else None
    if existing and not args.force:
        print(f"[OK] Sudah terpasang: {existing}\n     (gunakan --force untuk memasang ulang)")
        return 0

    system = platform.system()
    if args.zip is None and system not in ASSETS:
        print(f"[ERROR] Sistem operasi '{system}' tidak dikenali. Unduh manual lalu pakai --zip.")
        return 1

    try:
        zip_path = args.zip
        if zip_path is None:
            zip_path = args.dest.parent / ASSETS[system]
            download(RELEASE_BASE + ASSETS[system], zip_path)
        elif not zip_path.is_file():
            print(f"[ERROR] File tidak ditemukan: {zip_path}")
            return 1

        exe = install(zip_path, args.dest)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Gagal memasang: {exc}")
        return 1

    models_dir = exe.parent / "models"
    models = sorted({p.stem for p in models_dir.glob("*.param")}) if models_dir.is_dir() else []
    print(f"[OK] Terpasang: {exe}")
    print(f"[OK] Model tersedia ({len(models)}): {', '.join(models) or '-'}")
    if REQUIRED_MODEL not in models:
        print(f"[PERINGATAN] Model '{REQUIRED_MODEL}' tidak ditemukan.")
        return 1
    print("\nSelesai. Jalankan aplikasi dengan `python run.py`, lalu buka halaman Upscale Foto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
