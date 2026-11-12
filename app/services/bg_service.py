import io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageOps
from rembg import remove, new_session

from . import image_service

# Buat session sekali agar model tidak di-load berulang kali di setiap request
_session = None

def get_session():
    global _session
    if _session is None:
        _session = new_session("u2net")
    return _session

def remove_background(path, output_dir, original_name: str, bg_choice: str, bg_color: str, quality: int) -> dict:
    """
    Hapus background. bg_choice: "transparent" atau "color".
    bg_color: hex code (misal "#ffffff") jika bg_choice="color".
    """
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    try:
        original_size = path.stat().st_size

        with Image.open(path) as source:
            icc_profile = source.info.get("icc_profile")
            img = ImageOps.exif_transpose(source)
            img.load()

        # 1. Proses AI Remove Background
        session = get_session()
        # Konversi PIL Image ke bytes agar rembg bisa memprosesnya
        input_bytes = io.BytesIO()
        img.save(input_bytes, format="PNG")
        
        output_bytes = remove(
            input_bytes.getvalue(),
            session=session,
            alpha_matting=True, # Fitur untuk tepi yang lebih halus (rambut/bulu)
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10,
        )
        
        # Buka hasil dari rembg (mode RGBA)
        result_img = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

        # 2. Terapkan background (Transparan atau Warna)
        if bg_choice == "color":
            # Buat kanvas warna solid
            bg = Image.new("RGBA", result_img.size, bg_color)
            # Tempel gambar hasil hapus bg ke atas kanvas
            bg.paste(result_img, (0, 0), result_img)
            final_img = bg.convert("RGB")
            out_ext = ".jpg"
            target_format = "JPEG"
        else:
            # Transparan (PNG atau WebP)
            final_img = result_img
            out_ext = ".png"
            target_format = "PNG"

        out_name = f"{path.stem}_nobg{out_ext}"
        out_path = output_dir / out_name

        prepared = image_service.prepare_image(final_img, target_format)
        # PNG selalu lossless, JPG pakai quality user
        eff_quality = 100 if target_format == "PNG" else quality
        image_service.save_image(prepared, out_path, target_format, eff_quality, icc_profile)

        # Buat thumbnail untuk pratinjau
        thumb = image_service.save_thumbnail(final_img, output_dir, path.stem)

        result.update({
            "status": "success",
            "output": out_name,
            "original_size": original_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "PNG" if bg_choice == "transparent" else "JPG",
            "thumb": thumb,
        })
    except Exception as exc:
        result["error"] = f"Gagal menghapus background: {exc}"

    return result

def remove_backgrounds(entries, output_dir, bg_choice, bg_color, quality, max_workers=2):
    results = [None] * len(entries)
    if not entries:
        return results

    # Gunakan worker terbatas (1 atau 2) karena rembg sangat memakan RAM/CPU
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        future_to_index = {
            executor.submit(
                remove_background,
                e["path"], output_dir, e["original_name"], bg_choice, bg_color, quality
            ): i
            for i, e in enumerate(entries)
        }
        for future in as_completed(future_to_index):
            results[future_to_index[future]] = future.result()

    return results