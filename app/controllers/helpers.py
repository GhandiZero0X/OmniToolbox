from flask import jsonify, url_for

from ..services.archive_service import make_zip
from ..utils.file_utils import human_size

ZIP_NAME = "OmniToolbox_hasil.zip"


def build_job_response(job_id: str, results: list, output_dir, show_savings: bool = True):
    """
    Ubah hasil proses menjadi JSON untuk frontend (lengkap dengan link unduhan).

    show_savings=True  -> untuk fitur kompres (menampilkan persen hemat)
    show_savings=False -> untuk fitur konversi (ukuran bisa naik atau turun)
    """
    success = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]

    for item in success:
        item["url"] = url_for("main.download", job_id=job_id, filename=item["output"])
        item["original_size_h"] = human_size(item["original_size"])
        item["new_size_h"] = human_size(item["new_size"])

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
