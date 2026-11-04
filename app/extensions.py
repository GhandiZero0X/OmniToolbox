from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Pembatas request per IP. Untuk deploy dengan banyak worker,
# ganti storage_uri ke Redis, contoh: "redis://localhost:6379".
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)
