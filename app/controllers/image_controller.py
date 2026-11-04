import shutil
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from ..extensions import limiter
from ..services import image_service
from ..utils.file_utils import merge_results, new_job_id, save_uploaded_files
from .helpers import build_job_response

bp = Blueprint("image", __name__, url_prefix="/image")


@bp.get("/compress")
def compress_page():
    return render_template(
        "image/compress.html",
        max_files=current_app.config["MAX_FILES_PER_REQUEST"],
        max_mb=current_app.config["MAX_UPLOAD_MB"],
        accept=",".join(sorted(image_service.SUPPORTED_INPUT)),
    )


@bp.post("/compress/process")
@limiter.limit("20 per minute")
def compress_process():
    cfg = current_app.config

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify(error="Belum ada file yang dipilih."), 400
    if len(files) > cfg["MAX_FILES_PER_REQUEST"]:
        return jsonify(error=f"Maksimal {cfg['MAX_FILES_PER_REQUEST']} file sekali proses."), 400

    quality = image_service.clamp_quality(request.form.get("quality"))
    output_choice = request.form.get("output_format", "original")
    if output_choice not in image_service.OUTPUT_FORMATS:
        output_choice = "original"

    job_id = new_job_id()
    upload_dir = Path(cfg["UPLOAD_FOLDER"]) / job_id
    output_dir = Path(cfg["OUTPUT_FOLDER"]) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

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
