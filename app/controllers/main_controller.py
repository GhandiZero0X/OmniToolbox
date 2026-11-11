from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, send_from_directory

from ..extensions import limiter
from ..utils.file_utils import is_valid_job_id
from .helpers import PREVIEW_EXTENSIONS

bp = Blueprint("main", __name__)


def _job_directory(job_id: str) -> Path:
    if not is_valid_job_id(job_id):
        abort(404)
    directory = Path(current_app.config["OUTPUT_FOLDER"]) / job_id
    if not directory.is_dir():
        abort(404)
    return directory


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/download/<job_id>/<filename>")
@limiter.exempt
def download(job_id, filename):
    """Unduh file hasil proses. send_from_directory menolak path traversal."""
    return send_from_directory(_job_directory(job_id), filename, as_attachment=True)


@bp.get("/preview/<job_id>/<filename>")
@limiter.exempt
def preview(job_id, filename):
    """Tampilkan hasil berupa gambar langsung di browser (hanya JPG/PNG/WebP)."""
    if Path(filename).suffix.lower() not in PREVIEW_EXTENSIONS:
        abort(404)
    return send_from_directory(_job_directory(job_id), filename, as_attachment=False)
