import os
import time
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .processor import (
    ALL_SUPPORTED_EXTENSIONS,
    OFFICE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    convert_to_printable_pdf,
    get_document_info,
    render_preview_page,
    render_original_preview,
    process_document
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ColorPrint - color.deft.work", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static")

def cleanup_old_files():
    """Remove files older than 2 hours to avoid filling up disk."""
    now = time.time()
    cutoff = now - (2 * 3600)
    for folder in [UPLOAD_DIR, OUTPUT_DIR]:
        for p in folder.glob("*"):
            if p.is_file() and p.stat().st_mtime < cutoff and not p.name.startswith("."):
                try:
                    p.unlink()
                except Exception:
                    pass

class ProcessRequest(BaseModel):
    file_id: str
    color: str = "#002060"
    mode: str = "selective"
    clean_bg: bool = True
    bg_threshold: int = 242
    contrast: float = 1.15
    dpi: int = 300

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def get_index():
    template_path = Path(__file__).resolve().parent / "templates" / "index.html"
    if not template_path.exists():
        return HTMLResponse("<h1>ColorPrint</h1><p>Template loading...</p>")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.api_route("/health", methods=["GET", "HEAD"])
@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "app": "color.deft.work"}

@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    if background_tasks:
        background_tasks.add_task(cleanup_old_files)

    orig_name = file.filename or "documento.pdf"
    ext = Path(orig_name).suffix.lower()

    if ext not in ALL_SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión '{ext}' no soportada. Formatos aceptados: PDF, Word (docx, doc), Excel (xlsx, xls), PowerPoint (pptx, ppt), OpenDocument (odt, ods, odp), RTF, TXT, CSV, HTML, imágenes (PNG, JPG, HEIC, WEBP, TIFF, BMP, SVG, etc.)."
        )

    file_id = uuid.uuid4().hex
    saved_filename = f"{file_id}{ext}"
    saved_path = UPLOAD_DIR / saved_filename

    # Save uploaded file
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    actual_work_file = saved_path
    format_type = "pdf"

    try:
        # If it's an office file or non-PDF document (xps, epub, etc.), convert to PDF first
        if ext in OFFICE_EXTENSIONS or ext in (DOCUMENT_EXTENSIONS - {".pdf"}):
            converted_pdf_path = UPLOAD_DIR / f"{file_id}.pdf"
            convert_to_printable_pdf(str(saved_path), str(converted_pdf_path))
            actual_work_file = converted_pdf_path
            format_type = "office" if ext in OFFICE_EXTENSIONS else "document"

        elif ext in IMAGE_EXTENSIONS:
            format_type = "image"
        else:
            format_type = "pdf"

        info = get_document_info(str(actual_work_file))
    except Exception as e:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=400, detail=f"No se pudo procesar el archivo: {str(e)}")

    return {
        "file_id": file_id,
        "filename": orig_name,
        "format": format_type,
        "original_ext": ext,
        "page_count": info["page_count"],
        "pages": info["pages"]
    }

def find_upload_file(file_id: str) -> Optional[Path]:
    # Check if converted PDF exists first
    pdf_converted = UPLOAD_DIR / f"{file_id}.pdf"
    if pdf_converted.exists():
        return pdf_converted

    # Check for direct file
    matches = list(UPLOAD_DIR.glob(f"{file_id}.*"))
    if matches:
        return matches[0]
    return None

@app.get("/api/preview/{file_id}")
async def get_preview(
    file_id: str,
    page: int = Query(1, ge=1),
    type: str = Query("recolored"),
    color: str = Query("#002060"),
    mode: str = Query("selective"),
    clean_bg: bool = Query(True),
    bg_threshold: int = Query(242, ge=180, le=255),
    contrast: float = Query(1.15, ge=0.5, le=2.5)
):
    src_file = find_upload_file(file_id)
    if not src_file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado.")

    try:
        if type == "original":
            img_bytes = render_original_preview(str(src_file), page_num=page)
        else:
            img_bytes = render_preview_page(
                file_path=str(src_file),
                page_num=page,
                target_color=color,
                mode=mode,
                clean_bg=clean_bg,
                bg_threshold=bg_threshold,
                contrast_boost=contrast
            )
        return Response(content=img_bytes, media_type="image/jpeg", headers={
            "Cache-Control": "public, max-age=120"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar vista previa: {str(e)}")

@app.post("/api/process")
async def process_file(
    req: ProcessRequest,
    background_tasks: BackgroundTasks
):
    src_file = find_upload_file(req.file_id)
    if not src_file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado.")

    output_id = f"{req.file_id}_out"
    output_pdf_filename = f"{output_id}.pdf"
    output_pdf_path = OUTPUT_DIR / output_pdf_filename

    is_image = Path(src_file).suffix.lower() in IMAGE_EXTENSIONS
    output_img_path = str(OUTPUT_DIR / f"{output_id}.png") if is_image else None

    try:
        dpi = req.dpi if req.dpi in [150, 300] else 300

        process_document(
            input_path=str(src_file),
            output_pdf_path=str(output_pdf_path),
            target_color=req.color,
            mode=req.mode,
            clean_bg=req.clean_bg,
            bg_threshold=req.bg_threshold,
            contrast_boost=req.contrast,
            dpi=dpi,
            output_img_path=output_img_path
        )

        background_tasks.add_task(cleanup_old_files)

        res = {
            "output_id": output_id,
            "download_url": f"/api/download/{output_id}",
            "view_url": f"/api/view/{output_id}",
            "has_image": is_image
        }
        if is_image:
            res["download_image_url"] = f"/api/download-image/{output_id}"

        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(e)}")

@app.get("/api/download/{output_id}")
async def download_file(output_id: str):
    file_path = OUTPUT_DIR / f"{output_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Documento procesado no encontrado o expirado.")

    return FileResponse(
        path=str(file_path),
        filename="documento_para_imprimir.pdf",
        media_type="application/pdf"
    )

@app.get("/api/download-image/{output_id}")
async def download_image_file(output_id: str):
    file_path = OUTPUT_DIR / f"{output_id}.png"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imagen procesada no encontrada o expirada.")

    return FileResponse(
        path=str(file_path),
        filename="imagen_transformada.png",
        media_type="image/png"
    )

@app.get("/api/view/{output_id}")
async def view_file(output_id: str):
    file_path = OUTPUT_DIR / f"{output_id}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Documento procesado no encontrado o expirado.")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        content_disposition_type="inline"
    )
