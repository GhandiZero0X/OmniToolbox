import shutil

from flask import Blueprint, current_app, jsonify, render_template, request

from ..extensions import limiter
from ..services import image_service, watermark_service
from ..utils.file_utils import merge_results, save_uploaded_files
from .helpers import build_job_response, get_upload_files, new_job_dirs

bp = Blueprint("image", __name__, url_prefix="/image")


def _page_context() -> dict:
    return {
        "max_files": current_app.config["MAX_FILES_PER_REQUEST"],
        "max_mb": current_app.config["MAX_UPLOAD_MB"],
        "accept": ",".join(sorted(image_service.SUPPORTED_INPUT)),
    }


# ---------------------------------------------------------
# Kompres gambar
# ---------------------------------------------------------

@bp.get("/compress")
def compress_page():
    return render_template("image/compress.html", **_page_context())


@bp.post("/compress/process")
@limiter.limit("20 per minute")
def compress_process():
    cfg = current_app.config

    files, error = get_upload_files()
    if error:
        return jsonify(error=error), 400

    quality = image_service.clamp_quality(request.form.get("quality"))
    output_choice = request.form.get("output_format", "original")
    if output_choice not in image_service.OUTPUT_FORMATS:
        output_choice = "original"

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(files, upload_dir, image_service.SUPPORTED_INPUT)
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = image_service.compress_images(
            valid_entries, output_dir, quality, output_choice, cfg["IMAGE_WORKERS"]
        )
    finally:
        # File asli langsung dihapus setelah diproses
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir)


# ---------------------------------------------------------
# Konversi format gambar (JPG / JPEG / PNG / WebP / HEIC)
# ---------------------------------------------------------

@bp.get("/convert")
def convert_page():
    return render_template("image/convert.html", **_page_context())


@bp.post("/convert/process")
@limiter.limit("20 per minute")
def convert_process():
    cfg = current_app.config

    files, error = get_upload_files()
    if error:
        return jsonify(error=error), 400

    target = request.form.get("target_format", "jpg")
    if target not in image_service.CONVERT_FORMATS:
        return jsonify(error="Format tujuan tidak valid."), 400

    quality = image_service.clamp_quality(request.form.get("quality"), default=95)

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(files, upload_dir, image_service.SUPPORTED_INPUT)
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = image_service.convert_images(
            valid_entries, output_dir, target, quality, cfg["IMAGE_WORKERS"]
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir, show_savings=False)


# ---------------------------------------------------------
# Hapus teks / watermark (inpainting)
# ---------------------------------------------------------

def _form_number(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(request.form.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


@bp.get("/watermark")
def watermark_page():
    context = _page_context()
    context["accept"] = ",".join(sorted(watermark_service.SUPPORTED_INPUT))
    return render_template("image/watermark.html", **context)


@bp.post("/watermark/process")
@limiter.limit("10 per minute")
def watermark_process():
    cfg = current_app.config

    files, error = get_upload_files()
    if error:
        return jsonify(error=error), 400

    # Area teks dalam persen (kiri, atas, kanan, bawah)
    left = _form_number("roi_left", 3, 0, 100) / 100
    top = _form_number("roi_top", 93, 0, 100) / 100
    right = _form_number("roi_right", 46, 0, 100) / 100
    bottom = _form_number("roi_bottom", 99, 0, 100) / 100
    if right <= left or bottom <= top:
        return jsonify(error="Area teks tidak valid. Pastikan kanan > kiri dan bawah > atas."), 400

    mode = request.form.get("mode", "white")
    output_choice = request.form.get("output_format", "original")
    options = watermark_service.WatermarkOptions(
        roi=(left, top, right, bottom),
        mode=mode if mode in watermark_service.MODES else "white",
        threshold=int(_form_number("threshold", 235, 150, 250)),
        dilate=int(_form_number("dilate", 3, 0, 8)),
        radius=int(_form_number("radius", 5, 1, 15)),
        output_choice=output_choice if output_choice in watermark_service.OUTPUT_CHOICES else "original",
        quality=int(_form_number("quality", 95, 50, 100)),
    )

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(files, upload_dir, watermark_service.SUPPORTED_INPUT)
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = watermark_service.remove_watermarks(
            valid_entries, output_dir, options, cfg["IMAGE_WORKERS"]
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir, show_savings=False, previews=True)
