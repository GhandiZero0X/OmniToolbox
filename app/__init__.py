import time
from pathlib import Path

from flask import Flask, jsonify

from .config import Config
from .extensions import limiter
from .services.job_service import JobManager
from .utils.file_utils import cleanup_old_jobs

_last_cleanup = 0.0


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    for folder in (app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]):
        Path(folder).mkdir(parents=True, exist_ok=True)

    limiter.init_app(app)

    # Antrean tugas berat (upscale). Jumlah worker = batas proses GPU bersamaan.
    app.extensions["job_manager"] = JobManager(
        max_workers=app.config["UPSCALE_WORKERS"],
        max_queue=app.config["UPSCALE_MAX_QUEUE"],
    )

    # Daftarkan controller (routes)
    from .controllers.image_controller import bp as image_bp
    from .controllers.main_controller import bp as main_bp
    from .controllers.media_controller import bp as media_bp
    from .controllers.pdf_controller import bp as pdf_bp
    from .controllers.zip_controller import bp as zip_bp
    from .controllers.office_controller import bp as office_bp
    from .controllers.social_controller import bp as social_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(zip_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(office_bp)
    app.register_blueprint(social_bp)

    # Bersihkan file lama (maksimal sekali per menit)
    @app.before_request
    def periodic_cleanup():
        global _last_cleanup
        now = time.time()
        if now - _last_cleanup < 60:
            return
        _last_cleanup = now
        cleanup_old_jobs(
            [app.config["UPLOAD_FOLDER"], app.config["OUTPUT_FOLDER"]],
            app.config["FILE_RETENTION_MINUTES"],
        )
        app.extensions["job_manager"].purge(app.config["FILE_RETENTION_MINUTES"])

    @app.errorhandler(413)
    def too_large(_error):
        mb = app.config["MAX_UPLOAD_MB"]
        return jsonify(error=f"Total ukuran upload melebihi batas {mb} MB."), 413

    @app.errorhandler(429)
    def too_many_requests(_error):
        return jsonify(error="Terlalu banyak permintaan. Coba lagi sebentar lagi."), 429

    return app
