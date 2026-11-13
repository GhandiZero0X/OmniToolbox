import os
import subprocess
from pathlib import Path
import shutil

def download_instagram(url: str, output_dir: Path, mode: str = "all") -> list:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    cookie_path = Path("cookies.txt").resolve()
    if not cookie_path.exists():
        return [{"name": "Instagram", "status": "failed", "error": "File cookies.txt tidak ditemukan di folder utama project."}]

    gdl_path = shutil.which("gallery-dl")
    if not gdl_path:
        return [{"name": "Instagram", "status": "failed", "error": "Library gallery-dl tidak ditemukan."}]

    clean_url = url.split("?")[0]

    cmd = [
        gdl_path,
        "-d", str(output_dir),
        "--cookies", str(cookie_path),
        clean_url
    ]

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if process.returncode != 0:
            error_msg = process.stderr.strip() if process.stderr else "Gagal mengunduh."
            return [{"name": "Instagram", "status": "failed", "error": error_msg[:200]}]
    except subprocess.TimeoutExpired:
        return [{"name": "Instagram", "status": "failed", "error": "Proses timeout (lebih dari 3 menit)."}]
    except Exception as exc:
        return [{"name": "Instagram", "status": "failed", "error": f"Error: {str(exc)}"}]

    # --- Kumpulkan dan FILTER Hasil ---
    all_files = []
    for root, _, files in os.walk(output_dir):
        for file in files:
            file_path = Path(root) / file
            if file_path.is_file() and not file_path.name.endswith(".json"):
                # Pindahkan ke root output_dir
                new_path = output_dir / file_path.name
                shutil.move(str(file_path), str(new_path))
                all_files.append(new_path)

    # Bersihkan folder kosong sisa gallery-dl
    for item in output_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)

    all_files.sort(key=lambda x: x.name)

    # Lakukan Filter berdasarkan mode
    filtered_files = []
    for f in all_files:
        is_video = f.suffix.lower() in ('.mp4', '.webm', '.mkv')
        
        # Logika Filter
        if mode == "story_video" and not is_video:
            f.unlink() # Hapus jika bukan video
            continue
        if mode == "story_thumbnail" and is_video:
            f.unlink() # Hapus jika video (kita hanya mau gambar)
            continue
            
        filtered_files.append((f, is_video))

    # Susun output
    for f, is_video in filtered_files:
        results.append({
            "name": f.name,
            "status": "success",
            "output": f.name,
            "original_size": f.stat().st_size,
            "new_size": f.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "MP4" if is_video else "JPG",
        })

    if not results:
        return [{"name": "Instagram", "status": "failed", "error": "Tidak ada media yang ditemukan sesuai tipe unduhan yang dipilih."}]

    return results