"""
Hapus teks / watermark dengan OpenCV inpainting.

Cara kerja (sama seperti script terminal):
  1. Tentukan area (ROI) tempat teks berada, dalam persen ukuran gambar.
  2. Di dalam area itu, piksel terang (atau gelap) dianggap teks -> dibuat mask.
  3. Mask diperlebar sedikit (dilate) agar tepi teks ikut terhapus.
  4. cv2.inpaint mengisi area mask dari piksel di sekitarnya.

Optimasi: inpainting hanya dijalankan pada potongan gambar di sekitar area teks
(bukan seluruh gambar), sehingga jauh lebih cepat untuk foto beresolusi besar.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from . import image_service

SUPPORTED_INPUT = image_service.SUPPORTED_INPUT | {".bmp"}
MODES = {"white", "dark", "box"}
OUTPUT_CHOICES = {"original", "png", "jpg"}

_EXT_BY_FORMAT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


@dataclass(frozen=True)
class WatermarkOptions:
    roi: tuple              # (kiri, atas, kanan, bawah) dalam pecahan 0..1
    mode: str = "white"     # white = teks terang | dark = teks gelap | box = seluruh kotak
    threshold: int = 235    # ambang kecerahan (150-250)
    dilate: int = 3         # pelebaran mask (piksel)
    radius: int = 5         # radius inpainting
    output_choice: str = "original"
    quality: int = 95


def build_mask(gray: np.ndarray, options: WatermarkOptions):
    """Buat mask teks. Mengembalikan (mask, (x1, y1, x2, y2))."""
    height, width = gray.shape
    left, top, right, bottom = options.roi
    x1, y1 = int(left * width), int(top * height)
    x2, y2 = int(right * width), int(bottom * height)
    x2, y2 = max(x2, x1 + 1), max(y2, y1 + 1)
    x2, y2 = min(x2, width), min(y2, height)

    mask = np.zeros((height, width), dtype=np.uint8)

    if options.mode == "box":
        mask[y1:y2, x1:x2] = 255
        return mask, (x1, y1, x2, y2)

    region = gray[y1:y2, x1:x2]
    if options.mode == "dark":
        _, text = cv2.threshold(region, 255 - options.threshold, 255, cv2.THRESH_BINARY_INV)
    else:
        _, text = cv2.threshold(region, options.threshold, 255, cv2.THRESH_BINARY)
    mask[y1:y2, x1:x2] = text

    if options.dilate > 0:
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=options.dilate)
    return mask, (x1, y1, x2, y2)


def inpaint_rgb(rgb: np.ndarray, options: WatermarkOptions):
    """Hapus teks pada array RGB. Mengembalikan (rgb_hasil, ada_teks_terdeteksi)."""
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask, (x1, y1, x2, y2) = build_mask(gray, options)

    if not mask.any():
        return rgb, False

    # Potong area di sekitar teks (dengan margin) supaya inpainting cepat
    height, width = gray.shape
    pad = max(2 * options.radius, 32) + options.dilate + 2
    cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
    cx2, cy2 = min(width, x2 + pad), min(height, y2 + pad)

    patch = cv2.inpaint(
        bgr[cy1:cy2, cx1:cx2], mask[cy1:cy2, cx1:cx2], options.radius, cv2.INPAINT_TELEA
    )
    result = bgr.copy()
    result[cy1:cy2, cx1:cx2] = patch
    return cv2.cvtColor(result, cv2.COLOR_BGR2RGB), True


def _resolve_target_format(source_format, output_choice: str) -> str:
    if output_choice == "png":
        return "PNG"
    if output_choice == "jpg":
        return "JPEG"
    # "original": pertahankan format; HEIC dan lainnya diubah ke format yang umum
    if source_format in _EXT_BY_FORMAT:
        return source_format
    return "JPEG" if source_format == "HEIF" else "PNG"


def remove_watermark(path, output_dir, original_name: str, options: WatermarkOptions) -> dict:
    """Proses satu gambar. Tidak melempar error, hasilnya berupa dict."""
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    try:
        original_size = path.stat().st_size

        with Image.open(path) as source:
            source_format = source.format
            icc_profile = source.info.get("icc_profile")
            img = ImageOps.exif_transpose(source)
            img.load()

        alpha = None
        if image_service.has_alpha(img):
            rgba = img.convert("RGBA")
            alpha = rgba.getchannel("A")
            img = rgba.convert("RGB")
        else:
            img = img.convert("RGB")

        cleaned, found_text = inpaint_rgb(np.asarray(img), options)
        final = Image.fromarray(cleaned)
        if alpha is not None:
            final.putalpha(alpha)

        target_format = _resolve_target_format(source_format, options.output_choice)
        extension = _EXT_BY_FORMAT[target_format]
        out_name = f"{path.stem}_clean{extension}"
        out_path = output_dir / out_name

        prepared = image_service.prepare_image(final, target_format)
        quality = 100 if target_format == "PNG" else options.quality
        image_service.save_image(prepared, out_path, target_format, quality, icc_profile)

        result.update({
            "status": "success",
            "output": out_name,
            "original_size": original_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": extension.lstrip(".").upper(),
        })
        if not found_text:
            result["note"] = "Tidak ada teks terdeteksi di area itu, gambar tidak berubah."
    except Exception as exc:  # noqa: BLE001 - satu file gagal tidak boleh menghentikan yang lain
        result["error"] = image_service._friendly_error(exc)

    return result


def remove_watermarks(entries, output_dir, options: WatermarkOptions, max_workers: int = 4) -> list:
    """Proses banyak gambar secara paralel. Urutan hasil sama dengan urutan input."""
    results = [None] * len(entries)
    if not entries:
        return results

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(remove_watermark, e["path"], output_dir, e["original_name"], options): i
            for i, e in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()

    return results
