# 🧰 OmniToolbox

> An all-in-one web utility suite to convert, compress, merge, organize, upscale, download, and scrape media (images, videos, audio, documents, and social media) in one place.

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
- **Image Upscaler:** Enlarge images by **2x, 3x, or 4x** using [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) ncnn Vulkan. Supports photo and anime models, with background processing and live progress updates.
- **Text / Watermark Remover:** Remove text or watermarks from selected areas using OpenCV inpainting.
- **AI Background Remover:** Automatically remove image backgrounds using AI (`rembg`). Replace the background with a solid color or keep it transparent (PNG).

### 🎬 Media Suite (Video & Audio)
- **Video Converter:** Convert between **MOV and MP4** using H.264 video and AAC audio for broad compatibility.
- **Audio Extractor:** Extract **MP3** audio tracks directly from video files.

### 📄 Document & PDF Suite
- **Image to PDF:** Combine multiple images into one PDF. Reorder pages, select page size (image size, A4, or Letter), and configure margins.
- **PDF to Image:** Export PDF pages as **JPG** or **PNG** with configurable DPI.
- **Merge PDF:** Combine multiple PDF files into a single document.
- **Split PDF:** Split a PDF into individual pages, or extract specific page ranges into a new document.
- **Organize PDF:** Interactively arrange PDF pages. Drag & drop to reorder, rotate pages, delete pages, and merge multiple PDFs into one (with color-coded borders and zoom preview).
- **Compress PDF:** Reduce PDF file sizes using Ghostscript.
- **Word to PDF:** Convert `.docx` files to PDF. Requires Microsoft Word.
- **PDF to Word:** Convert PDF files into editable `.docx` documents.
- **Excel to PDF & PowerPoint to PDF:** Convert Office files to PDF via COM Automation.
- **PDF to PowerPoint:** Convert PDF pages into an image-based `.pptx` presentation.

### 📦 Archive Utility
- **Create Archive:** Package files or entire folders into `.zip`, `.7z`, or `.rar` while preserving the folder structure.
- **Extract Archive:** Extract contents from `.zip`, `.7z`, and `.rar` files safely.

### 🌐 Social Media Downloader & Scraper
- **Instagram Downloader:** Download Reels, Videos, Photos (Carousels), and Stories. Includes options to extract video-only or thumbnail-only from Stories.
- **YouTube Downloader:** Download YouTube videos up to 1080p (MP4) or extract audio to MP3.
- **TikTok Downloader:** Download TikTok videos (no watermark), photo slideshows, and stories.
- **Twitter / X Downloader:** Download Photos and Videos from a specific Tweet/Thread.
- **Twitter / X Scraper:** Scrape tweets based on Keywords, Hashtags, or Usernames. Exports media and a `.csv` file containing tweet text, dates, and URLs.

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3.10+, Flask (MVC architecture) |
| **Frontend** | HTML5, Jinja2 templates, Bootstrap 5, Vanilla JavaScript |
| **Production server** | Gunicorn (behind Nginx, optional) |

### Processing Tools

| Feature | Library / Tool |
| :--- | :--- |
| **Image convert & compress** | `Pillow`, `pillow-heif` |
| **Remove text / watermark** | `opencv-python-headless`, `numpy` (`cv2.inpaint`) |
| **AI Background Remover** | `rembg`, `onnxruntime` |
| **Image upscale** | **Real-ESRGAN ncnn Vulkan** (requires Vulkan-capable GPU) |
| **Video & audio conversion** | **FFmpeg** (system binary) |
| **PDF manipulation** | `pypdf`, `PyMuPDF` (`fitz`), `img2pdf` |
| **Office ↔ PDF** | `docx2pdf`, `pdf2docx`, `python-pptx`, `win32com.client` |
| **Compress PDF** | **Ghostscript** (system binary) |
| **Archive handling** | `zipfile`, `py7zr`, `rarfile`, **WinRAR** |
| **YouTube & Media Downloads** | `yt-dlp` |
| **Social Media Scraping** | `gallery-dl` |

> ⚠️ **System dependencies:** FFmpeg, Ghostscript, Microsoft Office, and WinRAR are external system programs. Install them separately before using the related features.
>
> **OpenCV:** Install only one OpenCV distribution (`opencv-python-headless`).

---

## 📋 Prerequisites

- Python 3.10 or newer
- [FFmpeg](https://ffmpeg.org/download.html) (video/audio conversion)
- [Ghostscript](https://ghostscript.com/releases/gsdnld.html) (PDF compression)
- Microsoft Office (Word, Excel, PowerPoint) for Office conversions.
- WinRAR (optional, required only for creating `.rar` files).
- A Vulkan-compatible GPU (only for image upscaling).

### Install System Tools (Windows)

```powershell
# Install FFmpeg via Winget
winget install Gyan.FFmpeg -e

# Install Ghostscript via Winget
winget install ArtifexSoftware.GhostScript -e
```

*(For Linux/macOS, install via `apt` or `brew`).*

---

## 🔑 Social Media Authentication (`cookies.txt`)

To download from Instagram, TikTok, or Twitter/X, you must provide authentication cookies. Platforms block anonymous requests.

1. Install the browser extension **"Get cookies.txt LOCALLY"** (Chrome/Edge).
2. Login to the target platform (Instagram, X, etc.) in your browser.
3. Click the extension icon and **Export**.
4. Save the file as `cookies.txt` in the root directory of this project (next to `run.py`).
5. *(Optional)* If you want separate cookies per platform, you can save them as `cookies_instagram.txt`, `cookies_twitter.txt`, etc. The app will automatically prioritize these specific files.
6. **Important:** Add `cookies*.txt` to your `.gitignore` to prevent leaking your session.

---

## 🚀 Getting Started (Local Installation)

### 1. Clone the repository
```bash
git clone https://github.com/username/omni-toolbox.git
cd omni-toolbox
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate    # Linux/macOS
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
```

### 5. Run the application
```bash
python run.py
```

> ⚠️ **Note for Windows Users:** If you are running the app locally in development mode, the `run.py` file is configured with `use_reloader=False`. This prevents Flask from restarting itself unexpectedly while the app is downloading large files into the `outputs/` folder.

Open `http://127.0.0.1:5000` in your browser.

---

## ⚙️ Configuration (`.env`)

```env
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

# PDF & Office limits
PDF_RENDER_MAX_PAGES=100
PDF_TO_WORD_MAX_PAGES=50
PDF_TO_PPT_MAX_PAGES=50
WORD_TIMEOUT_SECONDS=120

# Video & Audio
VIDEO_TIMEOUT_SECONDS=600
VIDEO_WORKERS=2
```

---

## 📁 Project Structure

```text
omni-toolbox/
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── config.py            # Configuration & env variables
│   ├── controllers/         # Routes (image, pdf, office, media, social, zip)
│   ├── services/            # Processing logic (bg, image, pdf, office, social)
│   ├── templates/           # Jinja2 templates
│   ├── utils/               # Helper functions
│   └── static/              # CSS, JS, images
├── uploads/                 # Temporary uploaded files
├── outputs/                 # Temporary processed files
├── tools/                   # External binaries (Real-ESRGAN)
├── cookies.txt              # (You create this) Social media auth
├── requirements.txt
├── .env.example
├── run.py
└── README.md
```

---

## 🔒 Privacy & Safety Notes

- Uploaded and processed files are temporary and are automatically deleted after the retention period.
- Filenames are sanitized using `werkzeug.utils.secure_filename`.
- Uploaded files are validated by magic bytes before processing.
- Rate limiting is applied via `Flask-Limiter` to prevent abuse.
- Cookies are not uploaded to any server; they are only used locally by your machine to authenticate with the respective social media platforms.

---

## 🗺️ Roadmap

- [x] Image converter, compressor, & watermark remover
- [x] AI Background Remover
- [x] Image ↔ PDF, Merge, Split, & Organize PDF
- [x] Compress PDF
- [x] Zip / 7z / RAR Archive Utility
- [x] MOV ↔ MP4 & MP3 extractor
- [x] Word / Excel / PowerPoint ↔ PDF
- [x] Image upscaler (Real-ESRGAN background queue)
- [x] Instagram, YouTube, TikTok, & Twitter Downloaders
- [x] Twitter Scraper (Keyword & Profile)
- [ ] Shared background job queue across workers (Celery + Redis)

---

## 📜 License

This project is licensed under the MIT License.