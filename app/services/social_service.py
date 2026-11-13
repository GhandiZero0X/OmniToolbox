import os
import subprocess
from pathlib import Path
import shutil

import csv
import json
import zipfile

def get_cookie_file(platform: str) -> Path:
    """
    Mencari file cookies spesifik untuk platform tertentu.
    Jika tidak ada, fallback ke cookies.txt utama.
    """
    # Cari file misal: cookies_instagram.txt
    specific_path = Path(f"cookies_{platform}.txt").resolve()
    if specific_path.exists():
        return specific_path
    
    # Fallback ke cookies.txt lama
    default_path = Path("cookies.txt").resolve()
    if default_path.exists():
        return default_path
        
    return None

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

def download_youtube(url: str, output_dir: Path, mode: str = "mp4_720") -> list:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    ydl_path = shutil.which("yt-dlp")
    if not ydl_path:
        return [{"name": "YouTube", "status": "failed", "error": "yt-dlp tidak ditemukan. Jalankan 'pip install yt-dlp'."}]

    # Atur opsi format berdasarkan pilihan user
    if mode == "mp3":
        format_arg = "ba/b" # Best audio
        ext = "mp3"
        extra_args = ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]
    elif mode == "mp4_1080":
        format_arg = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        ext = "mp4"
        extra_args = ["--merge-output-format", "mp4"]
    elif mode == "mp4_480":
        format_arg = "bestvideo[height<=480]+bestaudio/best[height<=480]"
        ext = "mp4"
        extra_args = ["--merge-output-format", "mp4"]
    else: # Default mp4_720
        format_arg = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        ext = "mp4"
        extra_args = ["--merge-output-format", "mp4"]

    # Format nama file: ID_Title.ext
    outtmpl = str(output_dir / "%(id)s_%(title).50s.%(ext)s")

    cmd = [
        ydl_path,
        "-f", format_arg,
        "-o", outtmpl,
        "--no-playlist",   # Hanya unduh video tunggal
        "--no-warnings",   # <-- TAMBAHKAN INI UNTUK MENYEMBUNYIKAN PERINGATAN
        *extra_args,
        url
    ]

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if process.returncode != 0:
            error_msg = process.stderr.strip() if process.stderr else "Gagal mengunduh video."
            return [{"name": "YouTube", "status": "failed", "error": error_msg[:200]}]
    except subprocess.TimeoutExpired:
        return [{"name": "YouTube", "status": "failed", "error": "Proses timeout (lebih dari 5 menit)."}]
    except Exception as exc:
        return [{"name": "YouTube", "status": "failed", "error": f"Error: {str(exc)}"}]

    # Kumpulkan Hasil
    files = [f for f in output_dir.iterdir() if f.is_file() and not f.name.endswith((".json", ".part", ".ytdl"))]
    
    for f in files:
        is_video = f.suffix.lower() in ('.mp4', '.webm', '.mkv')
        results.append({
            "name": f.name,
            "status": "success",
            "output": f.name,
            "original_size": f.stat().st_size,
            "new_size": f.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "MP3" if ext == "mp3" else "MP4",
        })

    if not results:
        return [{"name": "YouTube", "status": "failed", "error": "Tidak ada media yang ditemukan."}]

    return results

def download_tiktok(url: str, output_dir: Path, mode: str = "all") -> list:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    gdl_path = shutil.which("gallery-dl")
    if not gdl_path:
        return [{"name": "TikTok", "status": "failed", "error": "Library gallery-dl tidak ditemukan."}]

    # Bersihkan URL dari parameter pelacak
    clean_url = url.split("?")[0]

    cmd = [
        gdl_path,
        "-d", str(output_dir),
        clean_url
    ]

    # Gunakan cookies jika ada (sering dibutuhkan TikTok untuk menghindari blokir)
    cookie_path = Path("cookies.txt").resolve()
    if cookie_path.exists():
        cmd.extend(["--cookies", str(cookie_path)])

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if process.returncode != 0 and not process.stderr.strip() == "":
            error_msg = process.stderr.strip() if process.stderr else "Gagal mengunduh TikTok."
            return [{"name": "TikTok", "status": "failed", "error": error_msg[:200]}]
    except subprocess.TimeoutExpired:
        return [{"name": "TikTok", "status": "failed", "error": "Proses timeout."}]
    except Exception as exc:
        return [{"name": "TikTok", "status": "failed", "error": f"Error: {str(exc)}"}]

    # --- Kumpulkan Hasil ---
    all_files = []
    for root, _, files in os.walk(output_dir):
        for file in files:
            file_path = Path(root) / file
            if file_path.is_file() and not file_path.name.endswith((".json", ".txt")):
                new_path = output_dir / file_path.name
                shutil.move(str(file_path), str(new_path))
                all_files.append(new_path)

    # Bersihkan folder kosong
    for item in output_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)

    all_files.sort(key=lambda x: x.name)

    # Filter berdasarkan mode
    filtered_files = []
    for f in all_files:
        is_video = f.suffix.lower() in ('.mp4', '.webm', '.mkv')
        
        if mode == "video" and not is_video:
            f.unlink()
            continue
        if mode == "photo" and is_video:
            f.unlink()
            continue
            
        filtered_files.append((f, is_video))

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
        return [{"name": "TikTok", "status": "failed", "error": "Tidak ada media yang ditemukan atau sesuai filter."}]

    return results

def download_twitter(url: str, output_dir: Path, mode: str = "all") -> list:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    gdl_path = shutil.which("gallery-dl")
    if not gdl_path:
        return [{"name": "Twitter", "status": "failed", "error": "Library gallery-dl tidak ditemukan."}]

    # Bersihkan URL dari parameter pelacak
    clean_url = url.split("?")[0]

    cmd = [
        gdl_path,
        "-d", str(output_dir),
        clean_url
    ]

    # Cookies sangat disarankan untuk Twitter agar tidak diblokir
    cookie_path = Path("cookies.txt").resolve()
    if cookie_path.exists():
        cmd.extend(["--cookies", str(cookie_path)])

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        # Twitter kadang mengembalikan exit code != 0 tapi tetap berhasil mendownload,
        # jadi kita cek apakah ada file yang masuk
        if process.returncode != 0 and not any(output_dir.iterdir()):
            error_msg = process.stderr.strip() if process.stderr else "Gagal mengunduh dari Twitter."
            return [{"name": "Twitter", "status": "failed", "error": error_msg[:200]}]
    except subprocess.TimeoutExpired:
        return [{"name": "Twitter", "status": "failed", "error": "Proses timeout."}]
    except Exception as exc:
        return [{"name": "Twitter", "status": "failed", "error": f"Error: {str(exc)}"}]

    # --- Kumpulkan Hasil ---
    all_files = []
    for root, _, files in os.walk(output_dir):
        for file in files:
            file_path = Path(root) / file
            if file_path.is_file() and not file_path.name.endswith((".json", ".txt")):
                new_path = output_dir / file_path.name
                shutil.move(str(file_path), str(new_path))
                all_files.append(new_path)

    # Bersihkan folder kosong
    for item in output_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)

    all_files.sort(key=lambda x: x.name)

    # Filter berdasarkan mode
    filtered_files = []
    for f in all_files:
        is_video = f.suffix.lower() in ('.mp4', '.webm', '.mkv')
        
        if mode == "video" and not is_video:
            f.unlink()
            continue
        if mode == "photo" and is_video:
            f.unlink()
            continue
            
        filtered_files.append((f, is_video))

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
        return [{"name": "Twitter", "status": "failed", "error": "Tidak ada media yang ditemukan atau sesuai filter."}]

    return results

def scrape_twitter(query: str, limit: int, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    gdl_path = shutil.which("gallery-dl")
    if not gdl_path:
        return {"error": "Library gallery-dl tidak ditemukan."}

    if query.startswith("@"):
        username = query.replace("@", "")
        target_url = f"https://twitter.com/{username}"
    else:
        encoded_query = query.replace("#", "%23").replace(" ", "%20")
        target_url = f"https://twitter.com/search?q={encoded_query}&f=live"

    cmd = [
        gdl_path,
        "-d", str(output_dir),
        "--range", f"1-{limit}",
        "--write-metadata",
        target_url
    ]

    cookie_path = Path("cookies.txt").resolve()
    if cookie_path.exists():
        cmd.extend(["--cookies", str(cookie_path)])

    try:
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        # Cek jika Twitter memblokir (AuthRequired)
        if "authrequired" in process.stderr.lower() or "cookies" in process.stderr.lower():
            return {"error": "Twitter memblokir akses. Pastikan cookies.txt di-export dari akun X/Twitter yang sudah login."}
            
        if process.returncode != 0 and not any(output_dir.iterdir()):
            return {"error": f"Gagal scraping: {process.stderr[:200]}"}
            
    except subprocess.TimeoutExpired:
        return {"error": "Proses timeout (lebih dari 3 menit)."}
    except Exception as exc:
        return {"error": f"Error sistem: {str(exc)}"}

    tweets_data = []
    files_to_zip = []

    # Kumpulkan file dan baca JSON
    for root, _, files in os.walk(output_dir):
        for file in files:
            file_path = Path(root) / file
            if file.endswith(".json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        
                        # --- PERBAIKAN PARSING JSON ---
                        # Pastikan tipe datanya aman sebelum memanggil .get()
                        author = data.get("author", {})
                        user_name = author.get("name", "Unknown") if isinstance(author, dict) else str(author)
                        
                        tweets_data.append({
                            "User": user_name,
                            "Date": data.get("date", ""),
                            "Tweet": str(data.get("content", "")).replace("\n", " "),
                            "URL": data.get("url", "")
                        })
                except Exception:
                    pass # Abaikan jika ada satu JSON yang rusak
                file_path.unlink() # Hapus file JSON asli
            elif file.endswith((".mp4", ".jpg", ".png", ".webp")):
                new_path = output_dir / file_path.name
                if not new_path.exists():
                    shutil.move(str(file_path), str(new_path))
                files_to_zip.append(new_path)

    # Bersihkan folder kosong sisa gallery-dl
    for item in output_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)

    # Buat CSV
    csv_path = output_dir / "hasil_scraping.csv"
    if tweets_data:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["User", "Date", "Tweet", "URL"])
            writer.writeheader()
            writer.writerows(tweets_data)
        files_to_zip.append(csv_path)

    if not files_to_zip:
        return {"error": "Tidak ada tweet atau media yang ditemukan."}

    # --- PERBAIKAN ZIP (Windows File Lock) ---
    zip_name = f"Twitter_Scrape_{query.replace('#', '').replace('@', '')}.zip"
    zip_path = output_dir / zip_name

    # 1. Masukkan ke ZIP
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files_to_zip:
            if f.exists():
                zf.write(f, arcname=f.name)

    # 2. Hapus file asli SETELAH ZIP selesai ditutup (keluar dari blok with)
    for f in files_to_zip:
        f.unlink(missing_ok=True)

    results = [{
        "name": zip_name,
        "status": "success",
        "output": zip_name,
        "original_size": zip_path.stat().st_size,
        "new_size": zip_path.stat().st_size,
        "saved_percent": 0,
        "kept_original": False,
        "badge": f"{len(tweets_data)} Tweet",
    }]

    return {"results": results}