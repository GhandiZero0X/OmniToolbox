import shutil

from flask import Blueprint, current_app, jsonify, render_template, request

from ..extensions import limiter
from ..services import archive_service
from .helpers import build_job_response, get_upload_files, new_job_dirs

bp = Blueprint("zip", __name__, url_prefix="/zip")


@bp.get("/folder")
def folder_page():
    cfg = current_app.config
    return render_template(
        "zip/folder.html",
        max_files=cfg["MAX_FILES_MERGE"],
        max_mb=cfg["MAX_UPLOAD_MB"],
        compression_levels=archive_service.COMPRESSION_LEVELS,
        default_compression=archive_service.DEFAULT_COMPRESSION,
    )


@bp.post("/folder/process")
@limiter.limit("10 per minute")
def folder_process():
    cfg = current_app.config

    files, error = get_upload_files(cfg["MAX_FILES_MERGE"])
    if error:
        return jsonify(error=error), 400

    compression = request.form.get("compression", archive_service.DEFAULT_COMPRESSION)
    if compression not in archive_service.COMPRESSION_LEVELS:
        compression = archive_service.DEFAULT_COMPRESSION

    zip_name = archive_service.clean_zip_name(request.form.get("zip_name"))

    job_id, upload_dir, output_dir = new_job_dirs()
    output_path = output_dir / f"{zip_name}.zip"

    try:
        outcome = archive_service.zip_files(
            files, output_path, upload_dir / "_work", compression
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    if outcome["error"]:
        return jsonify(error=outcome["error"]), 500

    results = []
    if outcome["count"]:
        results.append({
            "name": output_path.name,
            "status": "success",
            "output": output_path.name,
            "original_size": outcome["original_size"],
            "new_size": output_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": f"{outcome['count']} file",
        })
    for failure in outcome["failed"]:
        results.append({
            "name": failure["name"],
            "status": "failed",
            "error": failure["error"],
        })

    return build_job_response(job_id, results, output_dir, show_savings=False)