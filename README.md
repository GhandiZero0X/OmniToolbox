# 🧰 OmniToolbox

> An all-in-one web utility suite to convert, compress, merge, and upscale your images, videos, audio, and documents in one place.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-MVC-lightgrey?style=flat-square&logo=flask&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple?style=flat-square&logo=bootstrap&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-required-green?style=flat-square&logo=ffmpeg&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)

---

## ✨ Features

### 🖼️ Image Suite

- **Format Converter:** Convert between **JPG, JPEG, PNG, WebP, and HEIC** formats.
- **Image Compression:** Reduce the file size of JPG, JPEG, PNG, WebP, and HEIC images while maintaining visual quality.
- **Image Upscaler:** Enlarge images by **2x, 3x, or 4x** using [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) ncnn Vulkan. Supports photo and anime/illustration models, with background processing and live progress updates.
- **Text / Watermark Remover:** Remove text or watermarks from selected areas. Select an area on the image preview and process multiple images using OpenCV inpainting.

### 🎬 Media Suite (Video & Audio)

- **Video Converter:** Convert between **MOV and MP4** using H.264 video and AAC audio for broad compatibility.
- **Audio Extractor:** Extract **MP3** audio tracks directly from video files.

### 📄 Document Suite

- **Word to PDF:** Convert `.docx` files to PDF while preserving the document layout. Requires Microsoft Word to be installed.
- **PDF to Word:** Convert PDF files into editable `.docx` documents.
- **Image to PDF:** Combine multiple images into one PDF. Reorder pages, select page size (image size, A4, or Letter), and configure margins. JPEG images are embedded without re-compression.
- **PDF to Image:** Export PDF pages as **JPG** or **PNG**, with a configurable DPI.
- **Merge PDF:** Combine multiple PDF files into a single document.
- **Compress PDF:** Reduce PDF file sizes using Ghostscript.

### 📦 Archive Utility

- **Zip Folder / Files:** Package multiple files or an entire folder into one `.zip` archive while preserving the folder structure.

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
| Remove text / watermark | `opencv-python-headless`, `numpy` (`cv2.inpaint`) |
| Image upscale | **Real-ESRGAN ncnn Vulkan** (standalone external program; requires a Vulkan-capable GPU) |
| Video & audio | **FFmpeg** (system binary) |
| Word → PDF | `docx2pdf` (requires Microsoft Word) |
| PDF → Word | `pdf2docx` |
| Image → PDF | `img2pdf` |
| PDF → Image | `PyMuPDF` (`fitz`) |
| Merge PDF | `pypdf` |
| Compress PDF | **Ghostscript** (system binary) |
| Zip | `zipfile` (Python standard library) |

> ⚠️ **System dependencies:** FFmpeg and Ghostscript are external system programs, not Python packages. Install them separately before using the related features.
>
> **OpenCV:** Install only one OpenCV distribution. This project uses `opencv-python-headless`; installing multiple OpenCV packages together (such as `opencv-python` and `opencv-contrib-python`) may cause conflicts when importing `cv2`.

---

## 📋 Prerequisites

- Python 3.10 or newer
- [FFmpeg](https://ffmpeg.org/download.html) (for video conversion and audio extraction)
- [Ghostscript](https://ghostscript.com/releases/gsdnld.html) (for PDF compression)
- Microsoft Word installed (for Word → PDF conversion with `docx2pdf`)
- A Vulkan-compatible GPU and up-to-date graphics driver (only for image upscaling)

### Install System Tools

#### Windows

Install FFmpeg and Ghostscript using Windows Package Manager (`winget`):

```powershell
winget install Gyan.FFmpeg -e
winget install ArtifexSoftware.GhostScript -e
```

If the commands are not recognized after installation, check that their installation directories are available in your system `PATH`.

#### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y ffmpeg ghostscript
```

#### macOS (Homebrew)

```bash
brew install ffmpeg ghostscript
```

> **Word → PDF compatibility:** `docx2pdf` requires Microsoft Word to be installed. It is supported on Windows and macOS; this conversion workflow is not available on Linux through `docx2pdf`.

Verify the FFmpeg and Ghostscript installations:

```bash
ffmpeg -version
```

On Windows, the Ghostscript command-line executable is commonly:

```powershell
gswin64c --version
```

On Linux/macOS, use:

```bash
gs --version
```

---

## 🔍 Upscale Setup (Real-ESRGAN)

The upscaler uses the standalone `realesrgan-ncnn-vulkan` program. Install it once:

```bash
python setup_realesrgan.py
```

The setup script downloads the build for your operating system into:

```text
tools/
└── realesrgan-ncnn-vulkan/
    ├── realesrgan-ncnn-vulkan.exe
    └── models/
```

The executable name may differ by operating system.

If automatic downloading is blocked by SSL or antivirus software, download the ZIP manually from the [Real-ESRGAN v0.2.5.0 releases](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0), then either pass the ZIP to the setup script:

```bash
python setup_realesrgan.py --zip path/to/file.zip
```

Or configure `REALESRGAN_PATH` in `.env` to point to the executable.

> ⚠️ Upscaling is resource-intensive. Keep `UPSCALE_WORKERS` at **2 or lower on a GPU with 4 GB VRAM** (for example, an RTX 3050) to reduce the risk of running out of video memory.

---

## 🚀 Getting Started (Local Installation)

### 1. Clone the repository

```bash
git clone https://github.com/username/omni-toolbox.git
cd omni-toolbox
```

Replace the repository URL with the actual URL of your GitHub repository.

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

**Windows (PowerShell):**

```powershell
venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
source venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example environment file:

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**

```bash
cp .env.example .env
```

Edit `.env` as needed. See the [Configuration](#️-configuration) section.

### 5. Run the application

```bash
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## ⚙️ Configuration

Example `.env` configuration:

```env
# Flask
FLASK_ENV=development
SECRET_KEY=change-this-to-a-random-string
PORT=5000

# Upload limits
MAX_CONTENT_LENGTH_MB=200
MAX_FILES_PER_REQUEST=20
MAX_FILES_MERGE=100

# Temporary files are deleted after this many minutes
FILE_RETENTION_MINUTES=60

# Parallel processing
IMAGE_WORKERS=4
PDF_WORKERS=2

# System binaries (empty = auto-detect in PATH)
GHOSTSCRIPT_PATH=gswin64c
FFMPEG_PATH=

# Upscale (Real-ESRGAN)
REALESRGAN_PATH=
UPSCALE_WORKERS=2
UPSCALE_TILE_SIZE=128
UPSCALE_MAX_FILES=10
UPSCALE_MAX_INPUT_MP=30
UPSCALE_MAX_OUTPUT_MP=200
UPSCALE_MAX_QUEUE=30
UPSCALE_TIMEOUT_SECONDS=900

# PDF & Word limits
PDF_RENDER_MAX_PAGES=100
PDF_TO_WORD_MAX_PAGES=50
WORD_TIMEOUT_SECONDS=120

# Video & Audio
VIDEO_TIMEOUT_SECONDS=600
VIDEO_WORKERS=2
```

Adjust binary paths according to your operating system. For example, `GHOSTSCRIPT_PATH` may be `gs` on Linux/macOS and `gswin64c` on Windows.

---

## 📁 Project Structure

```text
omni-toolbox/
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── config.py            # Configuration and environment variables
│   ├── controllers/         # Routes and request handling (Controller)
│   ├── services/            # Processing logic (image, media, PDF, archive)
│   ├── templates/           # Jinja2 templates (View)
│   ├── utils/               # Helper functions (file utilities, etc.)
│   └── static/               # CSS, JavaScript, and images
├── uploads/                  # Temporary uploaded files
├── outputs/                  # Temporary processed files
├── tools/                    # External binaries (Real-ESRGAN)
├── requirements.txt
├── .env.example
├── run.py
└── README.md
```

> Adjust this structure if your actual project folders differ.

---

## 🔒 Privacy & Safety Notes

- Uploaded and processed files are temporary and are automatically deleted after the configured retention period (`FILE_RETENTION_MINUTES`).
- Filenames are sanitized using `werkzeug.utils.secure_filename`.
- Uploaded files are validated by file signatures (magic bytes) before processing.
- Upload size is limited through `MAX_CONTENT_LENGTH_MB`.
- Rate limiting is applied through `Flask-Limiter` to help prevent abuse of resource-intensive features.

---

## 🐳 Deployment (Optional)

Run the application with Gunicorn:

```bash
gunicorn -w 2 -b 0.0.0.0:8000 "app:create_app()" --timeout 300
```

For Docker deployment, use a `Dockerfile` that installs the required system dependencies, including FFmpeg and Ghostscript:

```bash
docker build -t omni-toolbox .
docker run -p 8000:8000 --env-file .env omni-toolbox
```

> **Background job note:** If the upscaling job queue and job status are stored in memory, run a single Gunicorn worker process (for example, `gunicorn -w 1 --threads 4 ...`). Multiple worker processes do not share in-memory job state. For a multi-worker or multi-server deployment, consider moving background jobs to Celery with Redis.

---

## 🗺️ Roadmap

- [x] Image converter and compressor
- [x] Image → PDF
- [x] Merge PDF and PDF → Image
- [x] Compress PDF
- [x] Text / watermark remover
- [x] Zip folder and files
- [x] MOV ↔ MP4 converter and MP3 extractor
- [x] Word → PDF and PDF → Word
- [x] Image upscaler (Real-ESRGAN with background processing and live progress)
- [x] Batch processing and drag-and-drop upload
- [ ] Shared background job queue across workers (Celery + Redis)

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
