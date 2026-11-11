"""
Upscale foto dengan Real-ESRGAN ncnn Vulkan (program eksternal, butuh GPU berdukungan Vulkan).

Alur per gambar:
  1. Baca dengan Pillow: putar sesuai EXIF, dukung HEIC/BMP, ratakan mode warna.
  2. Simpan sebagai PNG sementara (lossless) lalu jalankan realesrgan-ncnn-vulkan.
  3. Baca hasilnya, simpan ke format pilihan (JPG/PNG/WebP) dengan ICC profile asli.

Catatan penting: program ini SELALU keluar dengan kode 0 walaupun gagal
(model salah, gambar rusak, dll), jadi keberhasilan dicek dari file hasilnya.
"""
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from . import image_service

SUPPORTED_INPUT = image_service.SUPPORTED_INPUT | {".bmp"}
SCALES = (2, 3, 4)
OUTPUT_FORMATS = {"jpg", "png", "webp"}
DEFAULT_MODEL = "realesrgan-x4plus"

# nama model -> (label, daftar nama file model yang harus ada di folder models/)
KNOWN_MODELS = {
    "realesrgan-x4plus": (
        "Foto umum (x4plus)", ["realesrgan-x4plus"]),
    "realesrgan-x4plus-anime": (
        "Ilustrasi / anime / manga (x4plus-anime)", ["realesrgan-x4plus-anime"]),
    "realesr-animevideov3": (
        "Anime ringan & cepat (animevideov3)",
        ["realesr-animevideov3-x2", "realesr-animevideov3-x3", "realesr-animevideov3-x4"]),
}

_FORMAT_BY_CHOICE = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}
_EXT_BY_CHOICE = {"jpg": ".jpg", "png": ".png", "webp": ".webp"}
WEBP_MAX_SIDE = 16383  # batas format WebP


def _format_pixels(count: float) -> str:
    """Tampilkan jumlah piksel yang mudah dibaca: megapiksel bila besar, piksel bila kecil."""
    if count >= 100_000:
        return f"{count / 1e6:.1f} MP"
    return f"{int(count):,} px".replace(",", ".")


class UpscaleError(Exception):
    """Kesalahan yang pesannya aman ditampilkan ke pengguna."""


@dataclass(frozen=True)
class Runner:
    exe: Path
    tile: int = 128
    gpu_id: str = ""
    timeout: int = 900

    @property
    def models_dir(self) -> Path:
        return self.exe.parent / "models"


@dataclass(frozen=True)
class UpscaleOptions:
    model: str = DEFAULT_MODEL
    scale: int = 4
    output_format: str = "jpg"
    quality: int = 95


# =========================================================
# Mencari program & model
# =========================================================

def _exe_name() -> str:
    return "realesrgan-ncnn-vulkan.exe" if os.name == "nt" else "realesrgan-ncnn-vulkan"


def _search_dir(folder: Path):
    direct = folder / _exe_name()
    if direct.is_file():
        return direct
    for found in sorted(folder.rglob(_exe_name())):
        if found.is_file():
            return found
    return None


def find_executable(configured: str, base_dir) -> "Path | None":
    base_dir = Path(base_dir)
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = base_dir / path
        if path.is_file():
            return path
        if path.is_dir():
            found = _search_dir(path)
            if found:
                return found

    tools_dir = base_dir / "tools" / "realesrgan-ncnn-vulkan"
    if tools_dir.is_dir():
        found = _search_dir(tools_dir)
        if found:
            return found

    on_path = shutil.which("realesrgan-ncnn-vulkan")
    return Path(on_path) if on_path else None


def get_runner(config) -> "Runner | None":
    exe = find_executable(config.get("REALESRGAN_PATH", ""), config["BASE_DIR"])
    if exe is None:
        return None
    return Runner(
        exe=exe,
        tile=int(config.get("UPSCALE_TILE_SIZE", 128)),
        gpu_id=str(config.get("UPSCALE_GPU_ID", "") or ""),
        timeout=int(config.get("UPSCALE_TIMEOUT_SECONDS", 900)),
    )


def available_models(runner: "Runner | None") -> list:
    """Daftar (nama, label) model yang file-nya benar-benar ada di folder models/."""
    if runner is None:
        return []
    models = []
    for name, (label, files) in KNOWN_MODELS.items():
        if all((runner.models_dir / f"{f}.param").is_file()
               and (runner.models_dir / f"{f}.bin").is_file() for f in files):
            models.append((name, label))
    return models


SETUP_HINT = (
    "Real-ESRGAN belum terpasang. Jalankan `python setup_realesrgan.py` di folder project, "
    "atau atur REALESRGAN_PATH di file .env."
)


# =========================================================
# Menjalankan Real-ESRGAN
# =========================================================

def run_realesrgan(runner: Runner, input_path: Path, output_path: Path, model: str, scale: int) -> None:
    """Jalankan program untuk satu gambar. Melempar UpscaleError bila gagal."""
    output_path.unlink(missing_ok=True)  # buang sisa hasil lama

    cmd = [
        str(runner.exe),
        "-i", str(input_path),
        "-o", str(output_path),
        "-n", model,
        "-s", str(scale),
        "-t", str(runner.tile),
        "-m", str(runner.models_dir),   # absolut, jadi tidak tergantung folder kerja
        "-f", "png",
    ]
    if runner.gpu_id:
        cmd += ["-g", runner.gpu_id]

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, timeout=runner.timeout,
            cwd=str(runner.exe.parent), **kwargs,
        )
    except subprocess.TimeoutExpired:
        output_path.unlink(missing_ok=True)
        raise UpscaleError(f"Proses melebihi batas waktu {runner.timeout} detik.")
    except OSError as exc:
        raise UpscaleError(f"Real-ESRGAN tidak bisa dijalankan: {exc}")

    # Kode exit tidak bisa dipercaya: periksa file hasilnya
    if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        output_path.unlink(missing_ok=True)
        raise UpscaleError(_explain_failure(completed))


def _explain_failure(completed) -> str:
    text = f"{completed.stderr or ''}\n{completed.stdout or ''}".replace("\r", "\n")
    detail = ""
    for line in reversed([ln.strip() for ln in text.split("\n") if ln.strip()]):
        low = line.lower()
        if any(word in low for word in ("fail", "error", "invalid", "cannot", "not found")):
            detail = line[:160]
            break
    message = "Real-ESRGAN gagal memproses gambar. Pastikan driver GPU (Vulkan) terpasang dan VRAM cukup."
    return f"{message} ({detail})" if detail else message


# =========================================================
# Proses satu gambar
# =========================================================

def upscale_image(path, output_dir, original_name: str, options: UpscaleOptions,
                  runner: Runner, work_dir, max_input_px: int, max_output_px: int) -> dict:
    """Upscale satu gambar. Tidak melempar error, hasilnya berupa dict."""
    path, output_dir, work_dir = Path(path), Path(output_dir), Path(work_dir)
    result = {"name": original_name, "status": "failed", "error": None}

    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        original_size = path.stat().st_size

        with Image.open(path) as source:
            width, height = source.size
            if width * height > max_input_px:
                raise UpscaleError(
                    f"Gambar terlalu besar ({_format_pixels(width * height)}). "
                    f"Maksimal {_format_pixels(max_input_px)} untuk upscale; perkecil dulu gambarnya."
                )
            icc_profile = source.info.get("icc_profile")
            img = ImageOps.exif_transpose(source)
            img.load()

        width, height = img.size
        scale = options.scale
        target = (width * scale, height * scale)
        if target[0] * target[1] > max_output_px:
            raise UpscaleError(
                f"Hasil akan terlalu besar ({_format_pixels(target[0] * target[1])}, "
                f"maksimal {_format_pixels(max_output_px)}). Pilih skala lebih kecil."
            )
        if options.output_format == "webp" and max(target) > WEBP_MAX_SIDE:
            raise UpscaleError(
                f"WebP maksimal {WEBP_MAX_SIDE}px per sisi (hasil {target[0]}x{target[1]}). "
                "Pilih JPG atau PNG."
            )

        # Normalisasi: RGB(A) tanpa mode aneh. Alpha dipisah karena Real-ESRGAN hanya memproses RGB.
        alpha = None
        if image_service.has_alpha(img):
            rgba = img.convert("RGBA")
            alpha = rgba.getchannel("A")
            rgb = rgba.convert("RGB")
        else:
            rgb = img.convert("RGB")

        input_png = work_dir / f"{path.stem}_in.png"
        raw_out = work_dir / f"{path.stem}_out.png"
        rgb.save(input_png, "PNG")
        del img, rgb

        run_realesrgan(runner, input_png, raw_out, options.model, scale)
        input_png.unlink(missing_ok=True)

        with Image.open(raw_out) as upscaled_file:
            upscaled_file.load()
            upscaled = upscaled_file.convert("RGB")
        raw_out.unlink(missing_ok=True)

        if upscaled.size != target:   # pengaman bila program mengeluarkan ukuran lain
            upscaled = upscaled.resize(target, Image.LANCZOS)
        if alpha is not None:
            upscaled.putalpha(alpha.resize(target, Image.LANCZOS))

        target_format = _FORMAT_BY_CHOICE[options.output_format]
        out_name = f"{path.stem}_x{scale}{_EXT_BY_CHOICE[options.output_format]}"
        out_path = output_dir / out_name
        prepared = image_service.prepare_image(upscaled, target_format)
        quality = 100 if target_format == "PNG" else options.quality
        image_service.save_image(prepared, out_path, target_format, quality, icc_profile)
        del prepared
        thumb = image_service.save_thumbnail(upscaled, output_dir, path.stem)

        result.update({
            "status": "success",
            "output": out_name,
            "original_size": original_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": _EXT_BY_CHOICE[options.output_format].lstrip(".").upper(),
            "info": f"{width}\u00d7{height} \u2192 {target[0]}\u00d7{target[1]} px ({scale}x)",
            "thumb": thumb,
        })
    except UpscaleError as exc:
        result["error"] = str(exc)
    except MemoryError:
        result["error"] = "Memori tidak cukup untuk memproses gambar ini."
    except Exception as exc:  # noqa: BLE001 - satu file gagal tidak boleh menghentikan yang lain
        result["error"] = image_service._friendly_error(exc)

    return result
