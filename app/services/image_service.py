import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

# Aktifkan dukungan baca/tulis HEIC
pillow_heif.register_heif_opener()

SUPPORTED_INPUT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
OUTPUT_FORMATS = {"original", "jpg", "webp", "png", "heic"}

# Nama format Pillow
_FORMAT_BY_CHOICE = {"jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP", "png": "PNG", "heic": "HEIF"}
_EXT_BY_FORMAT = {"JPEG": ".jpg", "WEBP": ".webp", "PNG": ".png", "HEIF": ".heic"}

# Fitur konversi: pilihan format -> ekstensi file hasil
_EXT_BY_CONVERT_CHOICE = {
    "png": ".png",
    "jpg": ".jpg",
    "jpeg": ".jpeg",
    "webp": ".webp",
    "heic": ".heic",
}
CONVERT_FORMATS = set(_EXT_BY_CONVERT_CHOICE)

MIN_QUALITY, MAX_QUALITY = 10, 100


def clamp_quality(value, default: int = 75) -> int:
    try:
        quality = int(value)
    except (TypeError, ValueError):
        quality = default
    return max(MIN_QUALITY, min(MAX_QUALITY, quality))


def _resolve_target_format(source_format, output_choice: str) -> str:
    if output_choice in _FORMAT_BY_CHOICE:
        return _FORMAT_BY_CHOICE[output_choice]
    # "original": pertahankan format sumber
    if source_format in _EXT_BY_FORMAT:
        return source_format
    return "JPEG"


def _has_alpha(img: Image.Image) -> bool:
    return (
        img.mode in ("RGBA", "LA", "PA")
        or (img.mode == "P" and "transparency" in img.info)
    )


def _prepare_image(img: Image.Image, target_format: str) -> Image.Image:
    """Samakan mode warna dengan format tujuan."""
    has_alpha = _has_alpha(img)

    if target_format == "JPEG":
        if has_alpha:
            # JPG tidak punya transparansi: tempel di atas latar putih
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return img if img.mode in ("RGB", "L") else img.convert("RGB")

    if has_alpha:
        return img.convert("RGBA")

    if target_format == "PNG":
        return img if img.mode in ("RGB", "L") else img.convert("RGB")

    # WEBP dan HEIF: RGB / RGBA
    return img if img.mode == "RGB" else img.convert("RGB")


def _save_image(img: Image.Image, out_path: Path, target_format: str, quality: int,
                icc_profile=None) -> None:
    # ICC profile menjaga warna tetap akurat (foto iPhone memakai Display P3)
    icc = {"icc_profile": icc_profile} if icc_profile else {}

    if target_format == "JPEG":
        img.save(out_path, "JPEG", quality=quality, optimize=True, progressive=True, **icc)
    elif target_format == "WEBP":
        img.save(out_path, "WEBP", quality=quality, method=6, **icc)
    elif target_format == "HEIF":
        img.save(out_path, "HEIF", quality=quality)
    elif target_format == "PNG":
        # PNG bersifat lossless. Kualitas < 90 memakai pengurangan warna (256 warna)
        # agar ukuran file benar-benar turun, mirip layanan kompres PNG populer.
        if quality < 90 and img.mode in ("RGB", "RGBA"):
            method = Image.Quantize.FASTOCTREE if img.mode == "RGBA" else Image.Quantize.MEDIANCUT
            img = img.quantize(colors=256, method=method)
        img.save(out_path, "PNG", optimize=True, compress_level=9, **icc)


def compress_image(path, output_dir, original_name: str, quality: int, output_choice: str) -> dict:
    """Kompres satu gambar. Fungsi ini tidak melempar error, hasilnya berupa dict."""
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    try:
        original_size = path.stat().st_size

        with Image.open(path) as source:
            source_format = source.format
            # Perbaiki orientasi dari EXIF (foto HP sering miring)
            img = ImageOps.exif_transpose(source)
            img.load()

        target_format = _resolve_target_format(source_format, output_choice)
        out_name = f"{path.stem}_min{_EXT_BY_FORMAT[target_format]}"
        out_path = output_dir / out_name

        prepared = _prepare_image(img, target_format)
        _save_image(prepared, out_path, target_format, quality)

        new_size = out_path.stat().st_size
        kept_original = False

        # Mode "format asli": kalau hasil malah lebih besar, pakai file asli saja
        if output_choice == "original" and new_size >= original_size:
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
    except Exception as exc:  # noqa: BLE001 - satu file gagal tidak boleh menghentikan yang lain
        result["error"] = _friendly_error(exc)

    return result


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, Image.DecompressionBombError):
        return "Resolusi gambar terlalu besar untuk diproses."
    if isinstance(exc, (Image.UnidentifiedImageError, OSError)):
        return "File gambar rusak atau tidak bisa dibaca."
    return f"Gagal memproses gambar: {exc}"


def compress_images(entries, output_dir, quality: int, output_choice: str, max_workers: int = 4) -> list:
    """Kompres banyak gambar secara paralel. Urutan hasil sama dengan urutan input."""
    results = [None] * len(entries)
    if not entries:
        return results

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(
                compress_image,
                entry["path"], output_dir, entry["original_name"], quality, output_choice,
            ): index
            for index, entry in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()

    return results


# =========================================================
# KONVERSI FORMAT
# =========================================================

def convert_image(path, output_dir, original_name: str, target_choice: str, quality: int) -> dict:
    """Konversi satu gambar ke format lain. Tidak melempar error, hasilnya berupa dict."""
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    try:
        original_size = path.stat().st_size

        with Image.open(path) as source:
            icc_profile = source.info.get("icc_profile")
            # Perbaiki orientasi dari EXIF (foto HP sering miring)
            img = ImageOps.exif_transpose(source)
            img.load()

        target_format = _FORMAT_BY_CHOICE[target_choice]
        extension = _EXT_BY_CONVERT_CHOICE[target_choice]
        out_name = f"{path.stem}{extension}"
        out_path = output_dir / out_name

        prepared = _prepare_image(img, target_format)
        # PNG selalu lossless (kualitas dipaksa 100 supaya tidak ada pengurangan warna)
        effective_quality = 100 if target_format == "PNG" else quality
        _save_image(prepared, out_path, target_format, effective_quality, icc_profile)

        result.update({
            "status": "success",
            "output": out_name,
            "original_size": original_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": extension.lstrip(".").upper(),
        })
    except Exception as exc:  # noqa: BLE001 - satu file gagal tidak boleh menghentikan yang lain
        result["error"] = _friendly_error(exc)

    return result


def convert_images(entries, output_dir, target_choice: str, quality: int, max_workers: int = 4) -> list:
    """Konversi banyak gambar secara paralel. Urutan hasil sama dengan urutan input."""
    results = [None] * len(entries)
    if not entries:
        return results

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(
                convert_image,
                entry["path"], output_dir, entry["original_name"], target_choice, quality,
            ): index
            for index, entry in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()

    return results


# Alias publik agar service lain (PDF, watermark) bisa memakai ulang logika ini
prepare_image = _prepare_image
save_image = _save_image
has_alpha = _has_alpha


THUMB_SIZE = 160


def save_thumbnail(img: Image.Image, output_dir, stem: str):
    """
    Simpan gambar mini (JPG) untuk tabel hasil dan kembalikan nama file-nya.
    PERHATIAN: img diperkecil di tempat (in-place), jadi panggil setelah file utama disimpan.
    """
    try:
        img.thumbnail((THUMB_SIZE, THUMB_SIZE))
        small = _prepare_image(img, "JPEG")
        name = f"thumb_{stem}.jpg"
        small.save(Path(output_dir) / name, "JPEG", quality=80)
        return name
    except Exception:  # noqa: BLE001 - thumbnail hanya pelengkap
        return None
