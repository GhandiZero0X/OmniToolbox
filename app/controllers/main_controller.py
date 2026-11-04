from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, send_from_directory

from ..utils.file_utils import is_valid_job_id

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/download/<job_id>/<filename>")
def download(job_id, filename):
    """Unduh file hasil proses. send_from_directory menolak path traversal."""
    if not is_valid_job_id(job_id):
        abort(404)
    directory = Path(current_app.config["OUTPUT_FOLDER"]) / job_id
    if not directory.is_dir():
        abort(404)
    return send_from_directory(directory, filename, as_attachment=True)
