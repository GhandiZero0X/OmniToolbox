from pathlib import Path

from flask import current_app, jsonify, request, url_for

from ..services.archive_service import make_zip
from ..utils.file_utils import human_size, new_job_id

ZIP_NAME = "OmniToolbox_hasil.zip"
PREVIEW_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def new_job_dirs():
    """Buat job baru: (job_id, folder upload sementara, folder output)."""
    cfg = current_app.config
    job_id = new_job_id()
    upload_dir = Path(cfg["UPLOAD_FOLDER"]) / job_id
    output_dir = Path(cfg["OUTPUT_FOLDER"]) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return job_id, upload_dir, output_dir


def get_upload_files(max_files=None):
    """Ambil file dari request. Mengembalikan (files, pesan_error)."""
    limit = max_files or current_app.config["MAX_FILES_PER_REQUEST"]
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return None, "Belum ada file yang dipilih."
    if len(files) > limit:
        return None, f"Maksimal {limit} file sekali proses."
    return files, None


def build_job_response(job_id: str, results: list, output_dir, show_savings: bool = True,
                       previews: bool = False):
    """
    Ubah hasil proses menjadi JSON untuk frontend (lengkap dengan link unduhan).

    show_savings=True  -> fitur kompres (menampilkan persen hemat)
    show_savings=False -> fitur konversi/edit (ukuran bisa naik atau turun)
    previews=True      -> sertakan link pratinjau untuk hasil berupa gambar
    """
    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]

    for item in success:
        item["url"] = url_for("main.download", job_id=job_id, filename=item["output"])
        item["original_size_h"] = human_size(item["original_size"])
        item["new_size_h"] = human_size(item["new_size"])
        if previews and Path(item["output"]).suffix.lower() in PREVIEW_EXTENSIONS:
            item["preview_url"] = url_for("main.preview", job_id=job_id, filename=item["output"])

    # Lebih dari satu file berhasil: sediakan ZIP
    zip_url = None
    if len(success) >= 2:
        make_zip(output_dir / ZIP_NAME, [output_dir / item["output"] for item in success])
        zip_url = url_for("main.download", job_id=job_id, filename=ZIP_NAME)

    total_original = sum(item["original_size"] for item in success)
    total_new = sum(item["new_size"] for item in success)
    saved_percent = (1 - total_new / total_original) * 100 if total_original else 0

    return jsonify(
        job_id=job_id,
        results=results,
        zip_url=zip_url,
        summary={
            "success": len(success),
            "failed": len(failed),
            "original_size_h": human_size(total_original),
            "new_size_h": human_size(total_new),
            "saved_percent": round(max(saved_percent, 0.0), 1),
            "show_savings": show_savings,
        },
    )
