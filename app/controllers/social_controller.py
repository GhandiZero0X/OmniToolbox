import shutil
from flask import Blueprint, current_app, jsonify, render_template, request
from ..extensions import limiter
from ..services import social_service
from .helpers import build_job_response, new_job_dirs

bp = Blueprint("social", __name__, url_prefix="/social")

@bp.get("/instagram")
def instagram_page():
    return render_template("social/instagram.html")

@bp.post("/instagram/process")
@limiter.limit("5 per minute")
def instagram_process():
    url = request.form.get("url", "").strip()
    mode = request.form.get("mode", "all").strip() # TAMBAHKAN INI

    if not url:
        return jsonify(error="URL tidak boleh kosong."), 400

    if "instagram.com" not in url:
        return jsonify(error="URL harus berupa link Instagram yang valid."), 400

    job_id, upload_dir, output_dir = new_job_dirs()
    
    try:
        # Kirim mode ke service
        results = social_service.download_instagram(url, output_dir, mode)
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    if isinstance(results, dict) and "error" in results:
        return jsonify(error=results["error"]), 500

    return build_job_response(job_id, results, output_dir, show_savings=False, previews=True)

@bp.get("/youtube")
def youtube_page():
    return render_template("social/youtube.html")

@bp.post("/youtube/process")
@limiter.limit("3 per minute") # Limit lebih ketat karena video YouTube biasanya besar
def youtube_process():
    url = request.form.get("url", "").strip()
    mode = request.form.get("mode", "mp4_720").strip()

    if not url:
        return jsonify(error="URL tidak boleh kosong."), 400

    if "youtube.com" not in url and "youtu.be" not in url:
        return jsonify(error="URL harus berupa link YouTube yang valid."), 400

    job_id, upload_dir, output_dir = new_job_dirs()
    
    try:
        results = social_service.download_youtube(url, output_dir, mode)
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    if isinstance(results, dict) and "error" in results:
        return jsonify(error=results["error"]), 500

    return build_job_response(job_id, results, output_dir, show_savings=False)