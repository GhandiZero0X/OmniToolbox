import shutil
from flask import Blueprint, current_app, jsonify, render_template, request
from ..extensions import limiter
from ..services import office_service, pdf_service
from ..utils.file_utils import merge_results, save_uploaded_files
from .helpers import build_job_response, get_upload_files, new_job_dirs

bp = Blueprint("office", __name__, url_prefix="/office")
MAX_FILES = 10

# --- EXCEL TO PDF ---
@bp.get("/excel-to-pdf")
def excel_page():
    ready = office_service.is_office_available()
    return render_template("office/excel_to_pdf.html", max_files=MAX_FILES, 
                           max_mb=current_app.config["MAX_UPLOAD_MB"], 
                           ready=ready, setup_hint=office_service.OFFICE_SETUP_HINT)

@bp.post("/excel-to-pdf/process")
@limiter.limit("5 per minute")
def excel_process():
    if not office_service.is_office_available():
        return jsonify(error=office_service.OFFICE_SETUP_HINT), 503
    files, error = get_upload_files(MAX_FILES)
    if error: return jsonify(error=error), 400
    
    job_id, upload_dir, output_dir = new_job_dirs()
    try:
        entries = save_uploaded_files(files, upload_dir, office_service.EXCEL_EXTENSIONS, validator=office_service.is_excel_file)
        valid = [e for e in entries if e["path"] is not None]
        processed = office_service.process_batch(office_service.excel_to_pdf, valid, output_dir)
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)
    return build_job_response(job_id, merge_results(entries, processed), output_dir, show_savings=False)

# --- PPT TO PDF ---
@bp.get("/ppt-to-pdf")
def ppt_page():
    ready = office_service.is_office_available()
    return render_template("office/ppt_to_pdf.html", max_files=MAX_FILES, 
                           max_mb=current_app.config["MAX_UPLOAD_MB"], 
                           ready=ready, setup_hint=office_service.OFFICE_SETUP_HINT)

@bp.post("/ppt-to-pdf/process")
@limiter.limit("5 per minute")
def ppt_process():
    if not office_service.is_office_available():
        return jsonify(error=office_service.OFFICE_SETUP_HINT), 503
    files, error = get_upload_files(MAX_FILES)
    if error: return jsonify(error=error), 400
    
    job_id, upload_dir, output_dir = new_job_dirs()
    try:
        entries = save_uploaded_files(files, upload_dir, office_service.PPT_EXTENSIONS, validator=office_service.is_ppt_file)
        valid = [e for e in entries if e["path"] is not None]
        processed = office_service.process_batch(office_service.ppt_to_pdf, valid, output_dir)
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)
    return build_job_response(job_id, merge_results(entries, processed), output_dir, show_savings=False)

# --- PDF TO PPT ---
@bp.get("/pdf-to-ppt")
def pdf_to_ppt_page():
    cfg = current_app.config
    return render_template("office/pdf_to_ppt.html", max_files=MAX_FILES, 
                           max_mb=cfg["MAX_UPLOAD_MB"], max_pages=cfg["PDF_TO_PPT_MAX_PAGES"])

@bp.post("/pdf-to-ppt/process")
@limiter.limit("3 per minute")
def pdf_to_ppt_process():
    cfg = current_app.config
    files, error = get_upload_files(MAX_FILES)
    if error: return jsonify(error=error), 400
    
    job_id, upload_dir, output_dir = new_job_dirs()
    try:
        entries = save_uploaded_files(files, upload_dir, {".pdf"}, validator=pdf_service.is_pdf_file)
        valid = [e for e in entries if e["path"] is not None]
        processed = office_service.process_batch(office_service.pdf_to_ppt, valid, output_dir, cfg["PDF_TO_PPT_MAX_PAGES"])
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)
    return build_job_response(job_id, merge_results(entries, processed), output_dir, show_savings=False)