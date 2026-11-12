import shutil
from pathlib import Path
from flask import Blueprint, current_app, jsonify, render_template, request

from ..extensions import limiter
from ..services import archive_service
from .helpers import build_job_response, get_upload_files, new_job_dirs
from ..utils.file_utils import save_uploaded_files

bp = Blueprint("zip", __name__, url_prefix="/zip")

# 1. KOMPRES FOLDER/FILE KE ARSIP (ZIP, 7Z, RAR)
@bp.get("/folder")
def folder_page():
    cfg = current_app.config
    rar_exe = archive_service.find_winrar()
    return render_template(
        "zip/folder.html",
        max_files=cfg["MAX_FILES_MERGE"],
        max_mb=cfg["MAX_UPLOAD_MB"],
        compression_levels=archive_service.COMPRESSION_LEVELS,
        default_compression=archive_service.DEFAULT_COMPRESSION,
        winrar_ready=rar_exe is not None,
    )

@bp.post("/folder/process")
@limiter.limit("10 per minute")
def folder_process():
    cfg = current_app.config
    files, error = get_upload_files(cfg["MAX_FILES_MERGE"])
    if error: return jsonify(error=error), 400

    fmt = request.form.get("format", "zip")
    zip_name = archive_service.clean_zip_name(request.form.get("zip_name"))
    job_id, upload_dir, output_dir = new_job_dirs()
    work_dir = upload_dir / "_work"

    try:
        if fmt == "7z":
            out_name = f"{zip_name}.7z"
            archive_service.compress_to_7z(files, output_dir / out_name, work_dir)
            badge = "7Z"
        elif fmt == "rar":
            rar_exe = archive_service.find_winrar()
            if not rar_exe: return jsonify(error="WinRAR (rar.exe) tidak ditemukan. Tidak bisa membuat file RAR."), 503
            out_name = f"{zip_name}.rar"
            archive_service.compress_to_rar(files, output_dir / out_name, work_dir, rar_exe)
            badge = "RAR"
        else:
            out_name = f"{zip_name}.zip"
            # gunakan fungsi zip_files yang sudah ada
            outcome = archive_service.zip_files(files, output_dir / out_name, work_dir, request.form.get("compression", "deflate"))
            if outcome["error"]: return jsonify(error=outcome["error"]), 500
            badge = "ZIP"

        results = [{
            "name": out_name, "status": "success", "output": out_name,
            "original_size": sum(f.stream.seek(0, 2) or f.stream.tell() for f in files),
            "new_size": (output_dir / out_name).stat().st_size,
            "saved_percent": 0, "kept_original": False, "badge": badge
        }]
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return build_job_response(job_id, results, output_dir, show_savings=False)


# 2. EKSTRAK ARSIP (ZIP, RAR, 7Z) KE FOLDER/ZIP BARU
@bp.get("/extract")
def extract_page():
    return render_template("zip/extract.html", max_files=20, max_mb=current_app.config["MAX_UPLOAD_MB"])

@bp.post("/extract/process")
@limiter.limit("10 per minute")
def extract_process():
    files, error = get_upload_files(20)
    if error: return jsonify(error=error), 400

    job_id, upload_dir, output_dir = new_job_dirs()
    work_dir = upload_dir / "_work"

    try:
        # Terima ZIP, RAR, 7Z
        entries = save_uploaded_files(files, upload_dir, {".zip", ".rar", ".7z"})
        valid = [e for e in entries if e["path"] is not None]
        
        outcome = archive_service.extract_archives_to_zip(valid, output_dir, work_dir)
        
        # Kumpulkan hasil
        results = []
        for e in valid:
            # Cari apakah ekstraksi untuk file ini sukses
            success = next((True for _ in range(outcome["count"])), False)
            # (Penyederhanaan: kita anggap sukses jika tidak masuk failed)
            if not any(f["name"] == e["original_name"] for f in outcome["failed"]):
                out_file = f"{e['path'].stem}_extracted.zip"
                results.append({
                    "name": f"{e['original_name']} (diextract)",
                    "status": "success", "output": out_file,
                    "original_size": e["path"].stat().st_size,
                    "new_size": (output_dir / out_file).stat().st_size,
                    "saved_percent": 0, "kept_original": False, "badge": "ZIP",
                })
        
        # Tambahkan yang gagal
        for f in outcome["failed"]:
            results.append({"name": f["name"], "status": "failed", "error": f["error"]})
            
        # Format salah
        for e in entries:
            if e["path"] is None:
                results.append({"name": e["original_name"], "status": "failed", "error": e["error"]})

    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return build_job_response(job_id, results, output_dir, show_savings=False)