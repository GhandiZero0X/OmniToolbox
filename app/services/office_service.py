import os
import shutil
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import image_service

EXCEL_EXTENSIONS = {".xls", ".xlsx"}
PPT_EXTENSIONS = {".ppt", ".pptx"}

OFFICE_SETUP_HINT = (
    "Microsoft Office (Excel/PowerPoint) tidak terdeteksi. "
    "Fitur ini membutuhkan aplikasi Office yang terinstall di Windows."
)

def is_office_available() -> bool:
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False

def is_excel_file(path) -> bool:
    """Cek signature file Excel (OLE / ZIP)."""
    try:
        with open(path, "rb") as fh:
            header = fh.read(8)
        return header.startswith(b"PK\x03\x04") or header.startswith(b"\xd0\xcf\x11\xe0")
    except OSError:
        return False

def is_ppt_file(path) -> bool:
    """Cek signature file PowerPoint."""
    return is_excel_file(path) # Logika header sama (OLE / ZIP)

# =========================================================
# EXCEL -> PDF
# =========================================================
def excel_to_pdf(path, output_dir, original_name: str) -> dict:
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}
    
    import pythoncom
    import win32com.client
    
    pythoncom.CoInitialize()
    excel = None
    wb = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        wb = excel.Workbooks.Open(str(path.resolve()), ReadOnly=True)
        out_path = output_dir / f"{path.stem}.pdf"
        out_path.unlink(missing_ok=True)
        
        # 0 = xlTypePDF
        wb.ExportAsFixedFormat(0, str(out_path.resolve()))
        
        if not out_path.exists() or out_path.stat().st_size == 0:
            result["error"] = "Excel tidak menghasilkan file PDF."
            return result
            
        result.update({
            "status": "success",
            "output": out_path.name,
            "original_size": path.stat().st_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "PDF",
        })
    except Exception as exc:
        result["error"] = f"Gagal mengonversi Excel: {exc}"
    finally:
        if wb: wb.Close(False)
        if excel: excel.Quit()
        pythoncom.CoUninitialize()
    return result

# =========================================================
# POWERPOINT -> PDF
# =========================================================
def ppt_to_pdf(path, output_dir, original_name: str) -> dict:
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}
    
    import pythoncom
    import win32com.client
    
    pythoncom.CoInitialize()
    ppt = None
    presentation = None
    try:
        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        # PowerPoint COM tidak bisa Visible=False di beberapa versi Windows
        # tapi kita bisa menutup window presentasinya saat selesai.
        
        presentation = ppt.Presentations.Open(str(path.resolve()), WithWindow=False)
        out_path = output_dir / f"{path.stem}.pdf"
        out_path.unlink(missing_ok=True)
        
        # 32 = ppSaveAsPDF
        presentation.SaveAs(str(out_path.resolve()), 32)
        
        if not out_path.exists() or out_path.stat().st_size == 0:
            result["error"] = "PowerPoint tidak menghasilkan file PDF."
            return result
            
        result.update({
            "status": "success",
            "output": out_path.name,
            "original_size": path.stat().st_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "PDF",
        })
    except Exception as exc:
        result["error"] = f"Gagal mengonversi PowerPoint: {exc}"
    finally:
        if presentation: presentation.Close()
        if ppt: ppt.Quit()
        pythoncom.CoUninitialize()
    return result

# =========================================================
# PDF -> POWERPOINT
# =========================================================
def pdf_to_ppt(path, output_dir, original_name: str, max_pages: int = 50) -> dict:
    import fitz
    from pptx import Presentation
    from pptx.util import Inches
    
    path, output_dir = Path(path), Path(output_dir)
    result = {"name": original_name, "status": "failed", "error": None}
    out_path = output_dir / f"{path.stem}.pptx"
    
    try:
        doc = fitz.open(str(path))
        if len(doc) == 0:
            return {**result, "error": "PDF tidak memiliki halaman."}
        if len(doc) > max_pages:
            return {**result, "error": f"PDF memiliki {len(doc)} halaman, melebihi batas {max_pages}."}
            
        prs = Presentation()
        # Gunakan ukuran slide default 16:9
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_slide_layout = prs.slide_layouts[6]
        
        zoom = 150 / 72.0 # Render di 150 DPI
        mat = fitz.Matrix(zoom, zoom)
        
        import io
        for i in range(len(doc)):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert pixmap to BytesIO (PNG)
            img_data = pix.tobytes("png")
            img_stream = io.BytesIO(img_data)
            
            # Tambah slide
            slide = prs.slides.add_slide(blank_slide_layout)
            
            # Gambar akan mengisi seluruh area slide
            slide.shapes.add_picture(img_stream, 0, 0, width=prs.slide_width, height=prs.slide_height)
            
        prs.save(str(out_path))
        
        result.update({
            "status": "success",
            "output": out_path.name,
            "original_size": path.stat().st_size,
            "new_size": out_path.stat().st_size,
            "saved_percent": 0,
            "kept_original": False,
            "badge": "PPTX",
            "info": f"{len(doc)} slide (berupa gambar)"
        })
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        result["error"] = f"Gagal mengonversi PDF ke PPT: {exc}"
        
    return result

# =========================================================
# BATCH PROCESSING (SERIAL)
# =========================================================
# Office COM TIDAK thread-safe, jadi kita proses berurutan (max_workers=1)
def process_batch(func, entries, output_dir, *args, **kwargs):
    results = []
    for e in entries:
        results.append(func(e["path"], output_dir, e["original_name"], *args, **kwargs))
    return results