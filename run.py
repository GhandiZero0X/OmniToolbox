import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_ENV", "production") == "development"
    port = int(os.getenv("PORT", "5000"))
    
    # use_reloader=False mencegah server restart otomatis saat file baru dibuat di outputs/uploads
    app.run(
        host="127.0.0.1", 
        port=port, 
        debug=debug,
        use_reloader=False 
    )