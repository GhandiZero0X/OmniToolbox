import shutil
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from ..extensions import limiter
from ..services import image_service
from ..utils.file_utils import merge_results, new_job_id, save_uploaded_files
from .helpers import build_job_response

bp = Blueprint("image", __name__, url_prefix="/image")


def _page_context() -> dict:
    return {
        "max_files": current_app.config["MAX_FILES_PER_REQUEST"],
        "max_mb": current_app.config["MAX_UPLOAD_MB"],
        "accept": ",".join(sorted(image_service.SUPPORTED_INPUT)),
    }


def _new_job_dirs():
    """Buat job baru: (job_id, folder upload sementara, folder output)."""
    cfg = current_app.config
    job_id = new_job_id()
    upload_dir = Path(cfg["UPLOAD_FOLDER"]) / job_id
    output_dir = Path(cfg["OUTPUT_FOLDER"]) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return job_id, upload_dir, output_dir


def _get_upload_files():
    """Ambil file dari request. Mengembalikan (files, pesan_error)."""
    cfg = current_app.config
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return None, "Belum ada file yang dipilih."
    if len(files) > cfg["MAX_FILES_PER_REQUEST"]:
        return None, f"Maksimal {cfg['MAX_FILES_PER_REQUEST']} file sekali proses."
    return files, None


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

    files, error = _get_upload_files()
    if error:
        return jsonify(error=error), 400

    quality = image_service.clamp_quality(request.form.get("quality"))
    output_choice = request.form.get("output_format", "original")
    if output_choice not in image_service.OUTPUT_FORMATS:
        output_choice = "original"

    job_id, upload_dir, output_dir = _new_job_dirs()

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

    files, error = _get_upload_files()
    if error:
        return jsonify(error=error), 400

    target = request.form.get("target_format", "jpg")
    if target not in image_service.CONVERT_FORMATS:
        return jsonify(error="Format tujuan tidak valid."), 400

    quality = image_service.clamp_quality(request.form.get("quality"), default=95)

    job_id, upload_dir, output_dir = _new_job_dirs()

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
