# 🧰 OmniToolbox

> An all-in-one web utility suite to convert, compress, merge, and upscale your images, videos, audio, and documents in one place.

<!-- ![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-MVC-lightgrey?style=flat-square&logo=flask&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple?style=flat-square&logo=bootstrap&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-required-green?style=flat-square&logo=ffmpeg&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square) -->

---

## ✨ Features

### 🖼️ Image Suite
* **Format Converter:** Convert between **JPG, JPEG, PNG, WebP, and HEIC** in any direction.
* **Image Compression:** Reduce the file size of JPG, JPEG, PNG, WebP, and HEIC images with minimal visible quality loss.
* **Image Upscaler:** Increase image resolution (2x / 4x) using super-resolution models.

### 🎬 Media Suite (Video & Audio)
* **Video Converter:** Convert **MOV to MP4** (H.264 + AAC) for wide compatibility.
* **Audio Extractor:** Extract **MP3** audio tracks directly from video files.

### 📄 Document Suite
* **Word to PDF:** Convert `.doc` / `.docx` files to PDF while keeping the layout intact.
* **PDF to Word:** Convert PDF files to editable `.docx`.
* **Image to PDF:** Combine one or more images into a single PDF.
* **PDF to Image:** Export each PDF page as **JPG** or **PNG**.
* **Merge PDF:** Combine multiple PDF files into one document.
* **Compress PDF:** Shrink large PDF files for easier sharing.

### 📦 Archive Utility
* **Zip Folder / Files:** Package multiple files or a whole folder into a single `.zip` archive.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask (MVC architecture) |
| Frontend | HTML5, Jinja2 templates, Bootstrap 5, Vanilla JavaScript |
| Production server | Gunicorn (behind Nginx, optional) |

### Processing Tools

| Feature | Library / Tool |
|---|---|
| Image convert & compress | `Pillow`, `pillow-heif` |
| Image upscale | `opencv-contrib-python` (`dnn_superres`); Real-ESRGAN optional for higher quality (GPU recommended) |
| Video & audio | **FFmpeg** (system binary, via `subprocess` or `ffmpeg-python`) |
| Word → PDF | **LibreOffice** (headless mode, system binary) |
| PDF → Word | `pdf2docx` |
| Image → PDF | `img2pdf` |
| PDF → Image | `PyMuPDF` (fitz) |
| Merge PDF | `pypdf` |
| Compress PDF | **Ghostscript** (system binary) |
| Zip | `zipfile` (Python standard library) |

> ⚠️ **Note:** FFmpeg, LibreOffice, and Ghostscript are **system programs**, not Python packages. They must be installed separately (see below).

---

## 📋 Prerequisites

* Python 3.10 or newer
* [FFmpeg](https://ffmpeg.org/download.html)
* [LibreOffice](https://www.libreoffice.org/download/download/)
* [Ghostscript](https://ghostscript.com/releases/gsdnld.html)

Install the system tools:

**Ubuntu / Debian**
```bash
sudo apt update
sudo apt install -y ffmpeg libreoffice ghostscript
```

**macOS (Homebrew)**
```bash
brew install ffmpeg ghostscript
brew install --cask libreoffice
```

**Windows**

1. Install FFmpeg, LibreOffice, and Ghostscript from their official websites.
2. Add the `bin` folder of FFmpeg and Ghostscript to your system `PATH`.
3. Make sure `soffice` (LibreOffice) is reachable, or set its path in your `.env` file.

Verify the installation:
```bash
ffmpeg -version
soffice --version
gs --version
```

---

## 🚀 Getting Started (Local Installation)

1. **Clone the repository**
   ```bash
   git clone https://github.com/username/omni-toolbox.git
   cd omni-toolbox
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv

   # Linux / macOS
   source venv/bin/activate

   # Windows (PowerShell)
   venv\Scripts\Activate.ps1
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` as needed (see [Configuration](#️-configuration)).

5. **Run the development server**
   ```bash
   flask run
   ```
   Open **http://127.0.0.1:5000** in your browser.

---

## ⚙️ Configuration

Example `.env`:

```env
FLASK_ENV=development
SECRET_KEY=change-this-to-a-random-string

# Upload limits
MAX_CONTENT_LENGTH_MB=200

# Temporary files are deleted after this many minutes
FILE_RETENTION_MINUTES=60

# Optional: custom paths to system binaries
FFMPEG_PATH=ffmpeg
LIBREOFFICE_PATH=soffice
GHOSTSCRIPT_PATH=gs
```

---

## 📁 Project Structure

```text
omni-toolbox/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Pengaturan (limit upload, path binary, dll)
│   │
│   ├── controllers/             # BACKEND: routes / penerima request
│   │   ├── __init__.py
│   │   ├── main_controller.py   # Halaman utama
│   │   ├── image_controller.py
│   │   ├── pdf_controller.py
│   │   ├── media_controller.py
│   │   └── archive_controller.py
│   │
│   ├── services/                # BACKEND: logika pemrosesan file
│   │   ├── __init__.py
│   │   ├── image_service.py     # <- dari main.py kamu
│   │   ├── pdf_service.py       # <- dari compresPdf.py kamu
│   │   ├── media_service.py
│   │   └── archive_service.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── file_utils.py        # Validasi ekstensi, nama file aman, hapus file lama
│   │
│   ├── templates/               # FRONTEND: halaman HTML (Jinja2)
│   │   ├── base.html            # Layout utama (navbar, footer)
│   │   ├── index.html           # Dashboard semua tool
│   │   ├── image/
│   │   │   └── compress.html
│   │   └── pdf/
│   │       └── compress.html
│   │
│   └── static/                  # FRONTEND: aset statis
│       ├── css/style.css
│       ├── js/main.js
│       └── img/
│
├── uploads/                     # File upload sementara (jangan di-commit)
├── outputs/                     # Hasil proses sementara (jangan di-commit)
├── legacy/                      # Simpan script terminal lamamu di sini
│   ├── main.py
│   └── compresPdf.py
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py                       # Titik masuk untuk menjalankan app
└── README.md
```

> Adjust this structure to match your actual folders.

---

## 🔒 Privacy & Safety Notes

* Uploaded and processed files are **temporary** and should be deleted automatically after the retention period.
* Filenames are sanitized (`werkzeug.utils.secure_filename`) and files are validated by type before processing.
* Upload size is limited through `MAX_CONTENT_LENGTH_MB`.
* For public deployment, add rate limiting (e.g. `Flask-Limiter`) to prevent abuse of heavy features such as video conversion and upscaling.

---

## 🐳 Deployment (Optional)

Run with Gunicorn:

```bash
gunicorn -w 2 -b 0.0.0.0:8000 "app:create_app()" --timeout 300
```

Or with Docker (requires a `Dockerfile` that installs `ffmpeg`, `libreoffice`, and `ghostscript`):

```bash
docker build -t omni-toolbox .
docker run -p 8000:8000 --env-file .env omni-toolbox
```

> Video conversion, Word → PDF, and upscaling are CPU-heavy. Use a longer request timeout and consider a background job queue (Celery + Redis) for large files.

---

## 🗺️ Roadmap

- [ ] Image converter & compressor
- [ ] Merge PDF, Image → PDF, PDF → Image
- [ ] Compress PDF
- [ ] Zip folder
- [ ] MOV → MP4 & MP3 extractor
- [ ] Word ↔ PDF
- [ ] Image upscaler
- [ ] Background job queue for large files
- [ ] Batch processing & drag-and-drop upload

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m "Add your feature"`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).