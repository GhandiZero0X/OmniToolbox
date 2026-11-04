import zipfile
from pathlib import Path


def make_zip(zip_path, files) -> Path:
    """Bungkus beberapa file menjadi satu ZIP (nama di dalam ZIP = nama file)."""
    zip_path = Path(zip_path)
    # Gambar/PDF hasil kompres sudah padat, jadi tidak perlu dikompres lagi.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        for file in files:
            zf.write(file, arcname=Path(file).name)
    return zip_path
