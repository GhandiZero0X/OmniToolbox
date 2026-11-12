import shutil

from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from ..extensions import limiter
from ..services import image_service, pdf_service
from ..utils.file_utils import merge_results, save_uploaded_files
from .helpers import build_job_response, get_upload_files, new_job_dirs

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

    files, error = get_upload_files()
    if error:
        return jsonify(error=error), 400

    preset = request.form.get("preset", pdf_service.DEFAULT_PRESET)
    if preset not in pdf_service.PRESETS:
        preset = pdf_service.DEFAULT_PRESET

    job_id, upload_dir, output_dir = new_job_dirs()

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


# ---------------------------------------------------------
# Gambar -> PDF
# ---------------------------------------------------------

def _clean_pdf_name(raw: str) -> str:
    name = (raw or "").strip()
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return secure_filename(name)[:80] or "dokumen"


@bp.get("/images-to-pdf")
def images_to_pdf_page():
    return render_template(
        "pdf/images_to_pdf.html",
        max_files=current_app.config["MAX_FILES_MERGE"],
        max_mb=current_app.config["MAX_UPLOAD_MB"],
        accept=",".join(sorted(image_service.SUPPORTED_INPUT)),
        page_sizes=pdf_service.PAGE_SIZES,
    )


@bp.post("/images-to-pdf/process")
@limiter.limit("10 per minute")
def images_to_pdf_process():
    cfg = current_app.config

    files, error = get_upload_files(cfg["MAX_FILES_MERGE"])
    if error:
        return jsonify(error=error), 400

    page_size = request.form.get("page_size", "image")
    if page_size not in pdf_service.PAGE_SIZES:
        page_size = "image"

    try:
        margin_mm = float(request.form.get("margin", 0))
    except (TypeError, ValueError):
        margin_mm = 0
    margin_mm = max(0, min(pdf_service.MAX_MARGIN_MM, margin_mm))

    pdf_name = _clean_pdf_name(request.form.get("pdf_name"))
    job_id, upload_dir, output_dir = new_job_dirs()
    output_path = output_dir / f"{pdf_name}.pdf"

    try:
        entries = save_uploaded_files(files, upload_dir, image_service.SUPPORTED_INPUT)
        valid_entries = [e for e in entries if e["path"] is not None]
        outcome = pdf_service.images_to_pdf(
            valid_entries, output_path, upload_dir / "_work",
            page_size, margin_mm, cfg["IMAGE_WORKERS"],
        )
        used_size = sum(e["path"].stat().st_size for e in outcome["used"])
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    if outcome["error"]:
        return jsonify(error=outcome["error"]), 500

    results = []
    if outcome["pages"]:
        results.append({
            "name": f"{pdf_name}.pdf",
            "status": "success",
            "output": output_path.name,
            "original_size": used_size,
            "new_size": output_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": f"{outcome['pages']} hal.",
        })

    # File yang ditolak saat upload + gambar yang gagal dibaca
    for entry in entries:
        if entry["path"] is None:
            results.append({"name": entry["original_name"], "status": "failed", "error": entry["error"]})
    for failure in outcome["failed"]:
        results.append({"name": failure["name"], "status": "failed", "error": failure["error"]})

    return build_job_response(job_id, results, output_dir, show_savings=False)

# =========================================================
# MERGE PDF
# =========================================================

@bp.get("/merge")
def merge_page():
    return render_template(
        "pdf/merge.html",
        max_files=current_app.config["MAX_FILES_MERGE"],
        max_mb=current_app.config["MAX_UPLOAD_MB"],
    )


@bp.post("/merge/process")
@limiter.limit("10 per minute")
def merge_process():
    cfg = current_app.config

    files, error = get_upload_files(cfg["MAX_FILES_MERGE"])
    if error:
        return jsonify(error=error), 400
    if len(files) < 2:
        return jsonify(error="Butuh minimal 2 file PDF untuk digabung."), 400

    pdf_name = _clean_pdf_name(request.form.get("pdf_name"))
    job_id, upload_dir, output_dir = new_job_dirs()
    output_path = output_dir / f"{pdf_name}.pdf"

    total_in = 0
    try:
        entries = save_uploaded_files(
            files, upload_dir, {".pdf"}, validator=pdf_service.is_pdf_file
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        outcome = pdf_service.merge_pdfs(valid_entries, output_path)
        total_in = sum(e["path"].stat().st_size for e in outcome["used"])
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    if outcome["error"]:
        return jsonify(error=outcome["error"]), 500

    results = []
    if outcome["used"]:
        results.append({
            "name": output_path.name,
            "status": "success",
            "output": output_path.name,
            "original_size": total_in,
            "new_size": output_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": f"{outcome['pages']} hal.",
        })
    for entry in entries:
        if entry["path"] is None:
            results.append({"name": entry["original_name"], "status": "failed",
                            "error": entry["error"]})
    for failure in outcome["failed"]:
        results.append({"name": failure["name"], "status": "failed",
                        "error": failure["error"]})

    return build_job_response(job_id, results, output_dir, show_savings=False)


# =========================================================
# PDF -> GAMBAR
# =========================================================

@bp.get("/pdf-to-image")
def pdf_to_image_page():
    cfg = current_app.config
    return render_template(
        "pdf/pdf_to_image.html",
        max_files=cfg["MAX_FILES_PER_REQUEST"],
        max_mb=cfg["MAX_UPLOAD_MB"],
        max_pages=cfg["PDF_RENDER_MAX_PAGES"],
        dpi_choices=pdf_service.PDF_RENDER_DPI,
        default_dpi=pdf_service.DEFAULT_RENDER_DPI,
    )


@bp.post("/pdf-to-image/process")
@limiter.limit("10 per minute")
def pdf_to_image_process():
    cfg = current_app.config

    files, error = get_upload_files()
    if error:
        return jsonify(error=error), 400

    dpi_choice = request.form.get("dpi", pdf_service.DEFAULT_RENDER_DPI)
    if dpi_choice not in pdf_service.PDF_RENDER_DPI:
        dpi_choice = pdf_service.DEFAULT_RENDER_DPI
    dpi = pdf_service.PDF_RENDER_DPI[dpi_choice]

    fmt = request.form.get("format", pdf_service.DEFAULT_RENDER_FORMAT)
    if fmt not in pdf_service.RENDER_FORMATS:
        fmt = pdf_service.DEFAULT_RENDER_FORMAT

    quality = image_service.clamp_quality(request.form.get("quality"), default=90)

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(
            files, upload_dir, {".pdf"}, validator=pdf_service.is_pdf_file
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = pdf_service.render_pdfs(
            valid_entries, output_dir, dpi, fmt, quality,
            cfg["PDF_RENDER_MAX_PAGES"], cfg["PDF_WORKERS"],
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    rejected = [
        {"name": e["original_name"], "status": "failed", "error": e["error"]}
        for e in entries if e["path"] is None
    ]
    results = processed + rejected

    return build_job_response(job_id, results, output_dir,
                              show_savings=False, previews=True)

# =========================================================
# WORD -> PDF (via Microsoft Word / docx2pdf)
# =========================================================

WORD_MAX_FILES = 10


@bp.get("/word-to-pdf")
def word_to_pdf_page():
    cfg = current_app.config
    ready = pdf_service.is_word_via_com_available()
    return render_template(
        "pdf/word_to_pdf.html",
        max_files=WORD_MAX_FILES,
        max_mb=cfg["MAX_UPLOAD_MB"],
        soffice_ready=ready,             # nama template lama, isinya sekarang "word_ready"
        setup_hint=pdf_service.WORD_SETUP_HINT,
    )


@bp.post("/word-to-pdf/process")
@limiter.limit("5 per minute")
def word_to_pdf_process():
    cfg = current_app.config

    if not pdf_service.is_word_via_com_available():
        return jsonify(error=pdf_service.WORD_SETUP_HINT), 503

    files, error = get_upload_files(WORD_MAX_FILES)
    if error:
        return jsonify(error=error), 400

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(
            files, upload_dir, pdf_service.WORD_INPUT_EXTENSIONS,
            validator=pdf_service.is_word_file,
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = pdf_service.word_to_pdfs(
            valid_entries, output_dir, cfg["WORD_TIMEOUT_SECONDS"],
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir, show_savings=False)


# =========================================================
# PDF -> WORD
# =========================================================

PDF_TO_WORD_MAX_FILES = 5


@bp.get("/pdf-to-word")
def pdf_to_word_page():
    cfg = current_app.config
    return render_template(
        "pdf/pdf_to_word.html",
        max_files=PDF_TO_WORD_MAX_FILES,
        max_mb=cfg["MAX_UPLOAD_MB"],
        max_pages=cfg["PDF_TO_WORD_MAX_PAGES"],
    )


@bp.post("/pdf-to-word/process")
@limiter.limit("3 per minute")
def pdf_to_word_process():
    cfg = current_app.config

    files, error = get_upload_files(PDF_TO_WORD_MAX_FILES)
    if error:
        return jsonify(error=error), 400

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(
            files, upload_dir, {".pdf"}, validator=pdf_service.is_pdf_file
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        processed = pdf_service.pdf_to_words(
            valid_entries, output_dir,
            cfg["PDF_TO_WORD_MAX_PAGES"], cfg["PDF_WORKERS"],
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    results = merge_results(entries, processed)
    return build_job_response(job_id, results, output_dir, show_savings=False)

# =========================================================
# SPLIT PDF
# =========================================================

SPLIT_MAX_FILES = 10


@bp.get("/split")
def split_page():
    cfg = current_app.config
    return render_template(
        "pdf/split.html",
        max_files=SPLIT_MAX_FILES,
        max_mb=cfg["MAX_UPLOAD_MB"],
    )


@bp.post("/split/process")
@limiter.limit("10 per minute")
def split_process():
    files, error = get_upload_files(SPLIT_MAX_FILES)
    if error:
        return jsonify(error=error), 400

    mode = request.form.get("mode", "every_page")
    if mode not in ("every_page", "range"):
        mode = "every_page"

    page_range = request.form.get("page_range", "")

    job_id, upload_dir, output_dir = new_job_dirs()

    try:
        entries = save_uploaded_files(
            files, upload_dir, {".pdf"}, validator=pdf_service.is_pdf_file
        )
        valid_entries = [e for e in entries if e["path"] is not None]
        
        processed = pdf_service.split_pdfs(
            valid_entries, output_dir, mode, page_range
        )
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    # Gabungkan hasil file yang ditolak (jika format salah) dengan hasil proses
    rejected = [
        {"name": e["original_name"], "status": "failed", "error": e["error"]}
        for e in entries if e["path"] is None
    ]
    results = processed + rejected

    return build_job_response(job_id, results, output_dir, show_savings=False)
