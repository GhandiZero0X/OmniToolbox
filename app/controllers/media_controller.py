import shutil

from flask import Blueprint, current_app, jsonify, render_template, request

from ..extensions import limiter
from ..services import video_service
from ..utils.file_utils import merge_results, save_uploaded_files
from .helpers import build_job_response, get_upload_files, new_job_dirs

bp = Blueprint("media", __name__, url_prefix="/media")

MEDIA_MAX_FILES = 5


@bp.get("/convert")
def convert_page():
    cfg = current_app.config
    ffmpeg = video_service.find_ffmpeg(cfg["FFMPEG_PATH"])
    return render_template(
        "media/convertmedia.html",
        max_files=MEDIA_MAX_FILES,
        max_mb=cfg["MAX_UPLOAD_MB"],
        accept=",".join(sorted(video_service.SUPPORTED_INPUT)),
        ffmpeg_ready=ffmpeg is not None,
        setup_hint=video_service.FFMPEG_SETUP_HINT,
        video_presets=video_service.VIDEO_PRESETS,
        default_preset=video_service.DEFAULT_PRESET,
        audio_bitrates=sorted(video_service.AUDIO_BITRATES,
                              key=lambda x: int(x[:-1])),
        default_bitrate=video_service.DEFAULT_BITRATE,
        video_workers=cfg["VIDEO_WORKERS"],   # ← TAMBAH baris ini
    )


@bp.post("/convert/process")
@limiter.limit("5 per minute")
def convert_process():
    cfg = current_app.config

    ffmpeg = video_service.find_ffmpeg(cfg["FFMPEG_PATH"])
    if not ffmpeg:
        return jsonify(error=video_service.FFMPEG_SETUP_HINT), 503

    files, error = get_upload_files(MEDIA_MAX_FILES)
    if error:
        return jsonify(error=error), 400

    target = request.form.get("target", "mp4")
    if target not in video_service.ALL_OUTPUT_FORMATS:
        return jsonify(error="Format tujuan tidak valid."), 400

    preset = request.form.get("preset", video_service.DEFAULT_PRESET)
    if preset not in video_service.VIDEO_PRESETS:
        preset = video_service.DEFAULT_PRESET

    bitrate = request.form.get("bitrate", video_service.DEFAULT_BITRATE)
    if bitrate not in video_service.AUDIO_BITRATES:
        bitrate = video_service.DEFAULT_BITRATE

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(
            files, upload_dir, video_service.SUPPORTED_INPUT,
            validator=video_service.is_video_file,
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = video_service.convert_many(
            valid_entries, output_dir, ffmpeg, target, preset, bitrate,
            cfg["VIDEO_TIMEOUT_SECONDS"], cfg["VIDEO_WORKERS"],
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir, show_savings=False)

# =========================================================
# KOMPRES VIDEO
# =========================================================

@bp.get("/compress")
def compress_page():
    cfg = current_app.config
    ffmpeg = video_service.find_ffmpeg(cfg["FFMPEG_PATH"])
    return render_template(
        "media/compressmedia.html",
        max_files=MEDIA_MAX_FILES,
        max_mb=cfg["MAX_UPLOAD_MB"],
        accept=",".join(sorted(video_service.SUPPORTED_INPUT)),
        ffmpeg_ready=ffmpeg is not None,
        setup_hint=video_service.FFMPEG_SETUP_HINT,
        presets=video_service.COMPRESS_PRESETS,
        default_preset=video_service.DEFAULT_COMPRESS_PRESET,
    )

@bp.post("/compress/process")
@limiter.limit("3 per minute") # Limit ketat karena kompresi video sangat berat
def compress_process():
    cfg = current_app.config

    ffmpeg = video_service.find_ffmpeg(cfg["FFMPEG_PATH"])
    if not ffmpeg:
        return jsonify(error=video_service.FFMPEG_SETUP_HINT), 503

    files, error = get_upload_files(MEDIA_MAX_FILES)
    if error:
        return jsonify(error=error), 400

    preset = request.form.get("preset", video_service.DEFAULT_COMPRESS_PRESET)
    if preset not in video_service.COMPRESS_PRESETS:
        preset = video_service.DEFAULT_COMPRESS_PRESET

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(
            files, upload_dir, video_service.SUPPORTED_INPUT,
            validator=video_service.is_video_file,
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        
        processed = video_service.compress_videos(
            valid_entries, output_dir, ffmpeg, preset,
            cfg["VIDEO_TIMEOUT_SECONDS"], cfg["VIDEO_WORKERS"],
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir, show_savings=True) 
    # show_savings=True agar menampilkan persentase hemat ukuran