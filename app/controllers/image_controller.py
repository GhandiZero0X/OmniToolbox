import shutil
from functools import partial

from flask import Blueprint, current_app, jsonify, render_template, request, url_for

from ..extensions import limiter
from ..services import image_service, upscale_service, watermark_service
from ..services.job_service import Job
from ..utils.file_utils import merge_results, save_uploaded_files
from .helpers import build_job_payload, build_job_response, get_upload_files, new_job_dirs

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


# ---------------------------------------------------------
# Upscale foto (Real-ESRGAN) - berjalan di latar belakang
# ---------------------------------------------------------

@bp.get("/upscale")
def upscale_page():
    cfg = current_app.config
    runner = upscale_service.get_runner(cfg)
    context = _page_context()
    context.update(
        accept=",".join(sorted(upscale_service.SUPPORTED_INPUT)),
        max_files=cfg["UPSCALE_MAX_FILES"],
        max_input_mp=cfg["UPSCALE_MAX_INPUT_MP"],
        models=upscale_service.available_models(runner),
        runner_ready=runner is not None,
        setup_hint=upscale_service.SETUP_HINT,
        scales=upscale_service.SCALES,
    )
    return render_template("image/upscale.html", **context)


@bp.post("/upscale/process")
@limiter.limit("5 per minute")
def upscale_process():
    cfg = current_app.config

    runner = upscale_service.get_runner(cfg)
    models = [name for name, _label in upscale_service.available_models(runner)]
    if runner is None or not models:
        return jsonify(error=upscale_service.SETUP_HINT), 503

    files, error = get_upload_files(cfg["UPSCALE_MAX_FILES"])
    if error:
        return jsonify(error=error), 400

    manager = current_app.extensions["job_manager"]
    if not manager.has_room(len(files)):
        return jsonify(error="Antrean upscale sedang penuh. Coba lagi beberapa menit lagi."), 503

    model = request.form.get("model", upscale_service.DEFAULT_MODEL)
    if model not in models:
        model = models[0]
    try:
        scale = int(request.form.get("scale", 4))
    except (TypeError, ValueError):
        scale = 4
    if scale not in upscale_service.SCALES:
        scale = 4
    output_format = request.form.get("output_format", "jpg")
    if output_format not in upscale_service.OUTPUT_FORMATS:
        output_format = "jpg"

    options = upscale_service.UpscaleOptions(
        model=model, scale=scale, output_format=output_format,
        quality=int(_form_number("quality", 95, 50, 100)),
    )

    job_id, upload_dir, output_dir = new_job_dirs()
    try:
        entries = save_uploaded_files(files, upload_dir, upscale_service.SUPPORTED_INPUT)
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise

    max_input_px = int(cfg["UPSCALE_MAX_INPUT_MP"] * 1_000_000)
    max_output_px = int(cfg["UPSCALE_MAX_OUTPUT_MP"] * 1_000_000)
    work_dir = upload_dir / "_work"

    tasks = [
        (
            entry["original_name"],
            partial(
                upscale_service.upscale_image, entry["path"], output_dir, entry["original_name"],
                options, runner, work_dir, max_input_px, max_output_px,
            ),
        )
        for entry in entries if entry["path"] is not None
    ]

    job = Job(job_id, entries, output_dir, total=len(tasks))
    manager.submit(job, tasks, on_finish=lambda: shutil.rmtree(upload_dir, ignore_errors=True))

    return jsonify(
        job_id=job_id,
        total=len(tasks),
        status_url=url_for("image.upscale_status", job_id=job_id),
    ), 202


@bp.get("/upscale/status/<job_id>")
@limiter.exempt   # dipanggil berulang oleh browser untuk memantau progres
def upscale_status(job_id):
    from ..utils.file_utils import is_valid_job_id

    job = current_app.extensions["job_manager"].get(job_id) if is_valid_job_id(job_id) else None
    if job is None:
        return jsonify(error="Proses tidak ditemukan atau sudah kedaluwarsa."), 404

    if job.state != "done":
        return jsonify(state="running", done=job.done, total=job.total)

    payload = build_job_payload(
        job_id, job.final_results(), job.output_dir, show_savings=False, previews=True
    )
    return jsonify(state="done", **payload)
