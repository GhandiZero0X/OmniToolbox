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
* **Format Converter:** Convert between **JPG, JPEG, PNG, WebP, and HEIC** in any direction.
* **Image Compression:** Reduce the file size of JPG, JPEG, PNG, WebP, and HEIC images with minimal visible quality loss.
* **Image Upscaler:** Enlarge images 2x / 3x / 4x with AI ([Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) ncnn Vulkan, runs on your GPU). Photo and anime/illustration models, progress shown live while it runs in the background.
* **Text / Watermark Remover:** Erase text in a chosen area (drag a box on the preview) across many images at once, using OpenCV inpainting.

### 🎬 Media Suite (Video & Audio)
* **Video Converter:** Convert **MOV to MP4** (H.264 + AAC) for wide compatibility.
* **Audio Extractor:** Extract **MP3** audio tracks directly from video files.

### 📄 Document Suite
* **Word to PDF:** Convert `.doc` / `.docx` files to PDF while keeping the layout intact.
* **PDF to Word:** Convert PDF files to editable `.docx`.
* **Image to PDF:** Combine many images into one PDF. Reorder pages with arrow buttons, choose page size (image size / A4 / Letter) and margin. JPEGs are embedded without re-compression.
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
| Remove text / watermark | `opencv-python-headless` + `numpy` (`cv2.inpaint`) |
| Image upscale | **Real-ESRGAN ncnn Vulkan** (external program installed by `setup_realesrgan.py`; needs a Vulkan-capable GPU, no PyTorch required) |
| Video & audio | **FFmpeg** (system binary, via `subprocess` or `ffmpeg-python`) |
| Word → PDF | **LibreOffice** (headless mode, system binary) |
| PDF → Word | `pdf2docx` |
| Image → PDF | `img2pdf` |
| PDF → Image | `PyMuPDF` (fitz) |
| Merge PDF | `pypdf` |
| Compress PDF | **Ghostscript** (system binary) |
| Zip | `zipfile` (Python standard library) |

> ⚠️ **Note:** FFmpeg and Ghostscript are **system programs**, not Python packages. They must be installed separately (see below).
>
> Install only **one** OpenCV package (`opencv-python-headless`). Having several (`opencv-python`, `opencv-contrib-python`) installed together can break `import cv2`.

---

## 📋 Prerequisites

* Python 3.10 or newer
* [FFmpeg](https://ffmpeg.org/download.html)
* [Ghostscript](https://ghostscript.com/releases/gsdnld.html)
* *(Only for Upscale)* A GPU with Vulkan support (NVIDIA / AMD / Intel Arc) and an up-to-date graphics driver

Install the system tools:

**Ubuntu / Debian**
```bash
sudo apt update
sudo apt install -y ffmpeg ghostscript
```

**macOS (Homebrew)**
```bash
brew install ffmpeg ghostscript
```

**Windows**

1. Install FFmpeg and Ghostscript from their official websites.
2. Add the `bin` folder of FFmpeg and Ghostscript to your system `PATH`.

Verify the installation:
```bash
ffmpeg -version
gs --version
```

---

### 🔍 Upscale setup (Real-ESRGAN)

The upscaler uses the standalone `realesrgan-ncnn-vulkan` program. Install it once (about 47 MB):

```bash
python setup_realesrgan.py
```

It downloads the build for your OS into `tools/realesrgan-ncnn-vulkan/` and the app finds it automatically.
If the download is blocked, download the ZIP manually from the
[Real-ESRGAN releases](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0) and run
`python setup_realesrgan.py --zip path/to/file.zip`. You can also point `REALESRGAN_PATH` in `.env` to the program.

> Upscaling is heavy. Keep `UPSCALE_WORKERS` at **2 or lower on a 4 GB GPU** (e.g. RTX 3050), otherwise it may run out of VRAM.

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

# Upscale (Real-ESRGAN)
REALESRGAN_PATH=              # empty = auto-detect in tools/realesrgan-ncnn-vulkan
UPSCALE_WORKERS=2             # images processed at the same time (GPU safety limit)
UPSCALE_TILE_SIZE=128         # smaller = less VRAM, slower
UPSCALE_MAX_FILES=10
UPSCALE_MAX_INPUT_MP=4        # max megapixels per input image
UPSCALE_MAX_OUTPUT_MP=64
UPSCALE_MAX_QUEUE=30
```

---

## 📁 Project Structure

```text
omni-toolbox/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── controllers/         # Routes / request handling (C)
│   ├── models/              # Data & job models (M)
│   ├── services/            # Processing logic (image, media, document, archive)
│   ├── templates/           # Jinja2 templates (V)
│   └── static/              # CSS, JS, images
├── uploads/                 # Temporary uploaded files
├── outputs/                 # Temporary processed files
├── requirements.txt
├── .env.example
├── run.py
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

Or with Docker (requires a `Dockerfile` that installs `ffmpeg` and `ghostscript`):

```bash
docker build -t omni-toolbox .
docker run -p 8000:8000 --env-file .env omni-toolbox
```

> Video conversion and Word → PDF are CPU-heavy: use a longer request timeout. Upscaling already runs in a background queue, but its job status is kept **in memory**, so run it with a **single worker process** (`gunicorn -w 1 --threads 4`). For multiple workers or servers, move the queue to Celery + Redis.

---

## 🗺️ Roadmap

- [x] Image converter & compressor
- [x] Image → PDF
- [x] Merge PDF, PDF → Image
- [x] Compress PDF
- [x] Text / watermark remover
- [x] Zip folder
- [x] MOV → MP4 & MP3 extractor
- [x] Word ↔ PDF, PDF ↔ Word
- [x] Image upscaler (Real-ESRGAN, background queue with live progress)
- [ ] Background job queue shared across workers (Celery + Redis)
- [x] Batch processing & drag-and-drop upload

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
