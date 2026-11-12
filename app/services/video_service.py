"""
Konversi video/audio dengan FFmpeg (system binary).

Mendukung:
  - MOV/MP4/AVI/MKV/WebM/3GP  ->  MP4   (H.264 + AAC, paling kompatibel)
  - MOV/MP4/...               ->  MOV   (H.264 + AAC)
  - MOV/MP4/...               ->  MP3   (ekstrak audio saja)

FFmpeg dipanggil via subprocess dengan -loglevel error agar output tidak membanjiri log.
"""
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SUPPORTED_INPUT = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm", ".3gp"}
VIDEO_OUTPUT_FORMATS = {"mp4", "mov"}
AUDIO_OUTPUT_FORMATS = {"mp3"}
ALL_OUTPUT_FORMATS = VIDEO_OUTPUT_FORMATS | AUDIO_OUTPUT_FORMATS

# Preset H.264 -> (label, argumen ffmpeg)
VIDEO_PRESETS = {
    "fast": ("Cepat (kualitas cukup)", ["-preset", "veryfast", "-crf", "24"]),
    "balanced": ("Seimbang (disarankan)", ["-preset", "medium", "-crf", "20"]),
    "best": ("Kualitas terbaik (lambat)", ["-preset", "slow", "-crf", "18"]),
}
DEFAULT_PRESET = "balanced"

AUDIO_BITRATES = {"128k", "192k", "256k", "320k"}
DEFAULT_BITRATE = "192k"

FFMPEG_SETUP_HINT = (
    "FFmpeg tidak ditemukan. Install FFmpeg (Windows: `winget install Gyan.FFmpeg -e`) "
    "atau atur FFMPEG_PATH di file .env."
)


# =========================================================
# Deteksi FFmpeg
# =========================================================

def find_ffmpeg(configured: str = "") -> "str | None":
    """Cari executable FFmpeg. Mengembalikan path lengkap atau None."""
    candidates = []
    if configured:
        candidates.append(configured)

    candidates += ["ffmpeg.exe", "ffmpeg"] if os.name == "nt" else ["ffmpeg"]

    for candidate in candidates:
        p = Path(candidate)
        if p.is_file():
            return str(p)
        found = shutil.which(candidate)
        if found:
            return found

    return None


def is_video_file(path) -> bool:
    """Cek signature file video via header magic bytes (cepat, tanpa ffprobe)."""
    try:
        with open(path, "rb") as fh:
            header = fh.read(12)
    except OSError:
        return False

    # MP4 / MOV / M4V: box ftyp pada offset 4
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return True
    # AVI: RIFF....AVI
    if header[:4] == b"RIFF" and header[8:12] == b"AVI ":
        return True
    # MKV / WebM: EBML header
    if header[:4] == b"\x1a\x45\xdf\xa3":
        return True
    # 3GP: ftyp3gp (sama seperti MP4, sudah tertangkap di atas)
    return False


# =========================================================
# Konversi satu file
# =========================================================

def convert_one(path, output_dir, original_name: str, ffmpeg: str,
                target_format: str, preset: str, bitrate: str,
                timeout: int = 600) -> dict:
    """Konversi satu file. Tidak melempar error, hasilnya berupa dict."""
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    if target_format not in ALL_OUTPUT_FORMATS:
        result["error"] = "Format tujuan tidak didukung."
        return result

    out_name = f"{path.stem}.{target_format}"
    out_path = output_dir / out_name

    cmd = [ffmpeg, "-y", "-i", str(path), "-hide_banner", "-loglevel", "error"]

    if target_format == "mp3":
        cmd += ["-vn", "-acodec", "libmp3lame", "-b:a", bitrate]
    elif target_format == "mp4":
        preset_args = VIDEO_PRESETS.get(preset, VIDEO_PRESETS[DEFAULT_PRESET])[1]
        cmd += [
            "-c:v", "libx264", *preset_args,
            "-pix_fmt", "yuv420p",        # wajib untuk player lama / Safari
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",    # streaming friendly
        ]
    elif target_format == "mov":
        preset_args = VIDEO_PRESETS.get(preset, VIDEO_PRESETS[DEFAULT_PRESET])[1]
        cmd += ["-c:v", "libx264", *preset_args, "-c:a", "aac", "-b:a", "128k"]

    cmd.append(str(out_path))

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        original_size = path.stat().st_size
        completed = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, **kwargs,
        )

        if completed.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            out_path.unlink(missing_ok=True)
            detail = (completed.stderr or completed.stdout or "").strip()
            detail = detail.splitlines()[-1][:200] if detail else ""
            result["error"] = f"FFmpeg gagal: {detail}" if detail else "Konversi gagal."
            return result

        result.update({
            "status": "success",
            "output": out_name,
            "original_size": original_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": target_format.upper(),
        })
    except subprocess.TimeoutExpired:
        out_path.unlink(missing_ok=True)
        result["error"] = (
            f"Proses melebihi batas waktu {timeout} detik. Video terlalu besar/panjang."
        )
    except Exception as exc:  # noqa: BLE001
        out_path.unlink(missing_ok=True)
        result["error"] = f"Gagal mengonversi: {exc}"

    return result


def convert_many(entries, output_dir, ffmpeg: str, target_format: str,
                 preset: str, bitrate: str, timeout: int = 600,
                 max_workers: int = 2) -> list:
    """Konversi banyak file secara paralel. Urutan hasil = urutan input."""
    results = [None] * len(entries)
    if not entries:
        return results

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(
                convert_one, e["path"], output_dir, e["original_name"],
                ffmpeg, target_format, preset, bitrate, timeout,
            ): i
            for i, e in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()

    return results