import shutil
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from ..extensions import limiter
from ..services import pdf_service
from ..utils.file_utils import merge_results, new_job_id, save_uploaded_files
from .helpers import build_job_response

bp = Blueprint("pdf", __name__, url_prefix="/pdf")


@bp.get("/compress")
def compress_page():
    return render_template(
        "pdf/compress.html",
        max_files=current_app.config["MAX_FILES_PER_REQUEST"],
        max_mb=current_app.config["MAX_UPLOAD_MB"],
        presets=pdf_service.PRESETS,
        default_preset=pdf_service.DEFAULT_PRESET,
    )


@bp.post("/compress/process")
@limiter.limit("10 per minute")
def compress_process():
    cfg = current_app.config

    gs_path = pdf_service.find_ghostscript(cfg["GHOSTSCRIPT_PATH"])
    if not gs_path:
        return jsonify(
            error="Ghostscript tidak ditemukan di server. Install Ghostscript, "
                  "lalu atur GHOSTSCRIPT_PATH di file .env."
        ), 500

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify(error="Belum ada file yang dipilih."), 400
    if len(files) > cfg["MAX_FILES_PER_REQUEST"]:
        return jsonify(error=f"Maksimal {cfg['MAX_FILES_PER_REQUEST']} file sekali proses."), 400

    preset = request.form.get("preset", pdf_service.DEFAULT_PRESET)
    if preset not in pdf_service.PRESETS:
        preset = pdf_service.DEFAULT_PRESET

    job_id = new_job_id()
    upload_dir = Path(cfg["UPLOAD_FOLDER"]) / job_id
    output_dir = Path(cfg["OUTPUT_FOLDER"]) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        entries = save_uploaded_files(
            files, upload_dir, {".pdf"}, validator=pdf_service.is_pdf_file
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = pdf_service.compress_pdfs(
            valid_entries, output_dir, preset, gs_path,
            cfg["PDF_TIMEOUT_SECONDS"], cfg["PDF_WORKERS"],
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir)
