import asyncio
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .calibration import CALIBRATION_SWATCHES, generate_calibration_pdf
from .processor import (
    ALL_SUPPORTED_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    OFFICE_EXTENSIONS,
    convert_to_printable_pdf,
    get_document_info,
    process_document,
    render_original_preview,
    render_preview_page,
)

logger = logging.getLogger("colorprint")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
FILE_TTL_SECONDS = int(os.environ.get("FILE_TTL_SECONDS", "1800"))  # 30 minutes

_VALID_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_VALID_OUTPUT_ID = re.compile(r"^[0-9a-f]{32}_out$")
_VALID_HEX_COLOR = re.compile(r"^#?[0-9a-fA-F]{6}$")

# Limit concurrent headless LibreOffice conversions to protect RAM/CPU
_LO_SEMAPHORE = asyncio.Semaphore(2)

app = FastAPI(title="ColorPrint - color.deft.work", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "HEAD"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static",
)


def validate_file_id(file_id: str) -> str:
    if not _VALID_FILE_ID.match(file_id):
        raise HTTPException(status_code=400, detail="Identificador de archivo no válido.")
    return file_id


def validate_output_id(output_id: str) -> str:
    if not _VALID_OUTPUT_ID.match(output_id):
        raise HTTPException(status_code=400, detail="Identificador de salida no válido.")
    return output_id


def cleanup_old_files() -> None:
    """Remove temporary files older than FILE_TTL_SECONDS (30 min by default)."""
    now = time.time()
    cutoff = now - FILE_TTL_SECONDS
    for folder in (UPLOAD_DIR, OUTPUT_DIR):
        for p in folder.iterdir():
            if p.is_file() and not p.name.startswith(".") and p.stat().st_mtime < cutoff:
                try:
                    p.unlink()
                except Exception:
                    pass


def find_upload_file(file_id: str) -> Optional[Path]:
    """
    Safely resolve a validated 32-char hex file_id against known extensions without globbing.
    """
    validate_file_id(file_id)
    pdf_converted = UPLOAD_DIR / f"{file_id}.pdf"
    if pdf_converted.is_file():
        return pdf_converted

    for ext in ALL_SUPPORTED_EXTENSIONS:
        candidate = UPLOAD_DIR / f"{file_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


class ProcessRequest(BaseModel):
    file_id: str
    color: str = Field(default="#0038A8")
    mode: str = Field(default="selective")
    clean_bg: bool = True
    bg_threshold: int = Field(default=242, ge=180, le=255)
    contrast: float = Field(default=1.15, ge=0.5, le=2.5)
    dpi: int = Field(default=300)
    engine: str = Field(default="vector")  # "vector" | "raster"
    scanner_mode: bool = False
    force_cmyk_no_k: bool = False
    page_range: Optional[str] = Field(default=None, max_length=120)


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def get_index():
    template_path = Path(__file__).resolve().parent / "templates" / "index.html"
    if not template_path.exists():
        return HTMLResponse("<h1>ColorPrint</h1>")
    return HTMLResponse(template_path.read_text(encoding="utf-8"))


@app.api_route("/manifest.json", methods=["GET", "HEAD"])
async def get_manifest():
    manifest_path = Path(__file__).resolve().parent / "static" / "manifest.json"
    return FileResponse(str(manifest_path), media_type="application/manifest+json")


@app.api_route("/sw.js", methods=["GET", "HEAD"])
async def get_service_worker():
    sw_path = Path(__file__).resolve().parent / "static" / "sw.js"
    return FileResponse(str(sw_path), media_type="application/javascript")


@app.api_route("/health", methods=["GET", "HEAD"])
@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "app": "color.deft.work", "version": "3.0.0"}


@app.get("/api/calibration-swatches")
async def get_calibration_swatches():
    return {"swatches": CALIBRATION_SWATCHES}


@app.get("/api/calibration-sheet")
async def get_calibration_sheet(download: bool = Query(False)):
    pdf_bytes = await asyncio.to_thread(generate_calibration_pdf)
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="hoja_calibracion_colorprint.pdf"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    if background_tasks:
        background_tasks.add_task(cleanup_old_files)

    orig_name = Path(file.filename or "documento.pdf").name
    ext = Path(orig_name).suffix.lower()

    if ext not in ALL_SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extensión '{ext}' no soportada. Sube un archivo PDF, Word, Excel, PowerPoint, LibreOffice, ePub, SVG o imagen.",
        )

    file_id = uuid.uuid4().hex
    saved_path = UPLOAD_DIR / f"{file_id}{ext}"

    # Stream in chunks with strict size limit enforcement
    total_written = 0
    try:
        with open(saved_path, "wb") as buffer:
            while True:
                chunk = await file.read(65536)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"El archivo supera el límite máximo permitido de {MAX_UPLOAD_MB} MB.",
                    )
                buffer.write(chunk)
    except HTTPException:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        logger.exception("Upload write error: %s", exc)
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Error al recibir el archivo subido.")

    if total_written == 0:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="El archivo subido está vacío.")

    actual_work_file = saved_path
    format_type = "pdf"

    try:
        if ext in OFFICE_EXTENSIONS or ext in (DOCUMENT_EXTENSIONS - {".pdf"}):
            converted_pdf_path = UPLOAD_DIR / f"{file_id}.pdf"
            async with _LO_SEMAPHORE:
                await asyncio.to_thread(
                    convert_to_printable_pdf, str(saved_path), str(converted_pdf_path)
                )
            # Remove the raw office file once converted to PDF
            if saved_path != converted_pdf_path and saved_path.exists():
                saved_path.unlink(missing_ok=True)
            actual_work_file = converted_pdf_path
            format_type = "office" if ext in OFFICE_EXTENSIONS else "document"
        elif ext in IMAGE_EXTENSIONS:
            format_type = "image"
        else:
            format_type = "pdf"

        info = await asyncio.to_thread(get_document_info, str(actual_work_file))
    except ValueError as ve:
        saved_path.unlink(missing_ok=True)
        (UPLOAD_DIR / f"{file_id}.pdf").unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception("Error processing uploaded file: %s", exc)
        saved_path.unlink(missing_ok=True)
        (UPLOAD_DIR / f"{file_id}.pdf").unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="No se pudo procesar el archivo. Verifica que no esté dañado ni protegido con contraseña.",
        )

    return {
        "file_id": file_id,
        "filename": orig_name,
        "format": format_type,
        "original_ext": ext,
        "page_count": info["page_count"],
        "has_vector_text": info.get("has_vector_text", False),
        "pages": info["pages"],
    }


@app.get("/api/preview/{file_id}")
async def get_preview(
    file_id: str,
    page: int = Query(1, ge=1, le=200),
    type: str = Query("recolored"),
    color: str = Query("#0038A8"),
    mode: str = Query("selective"),
    clean_bg: bool = Query(True),
    bg_threshold: int = Query(242, ge=180, le=255),
    contrast: float = Query(1.15, ge=0.5, le=2.5),
    scanner_mode: bool = Query(False),
):
    src_file = find_upload_file(file_id)
    if not src_file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado.")

    if not _VALID_HEX_COLOR.match(color):
        color = "#0038A8"
    if mode not in ("selective", "monochrome"):
        mode = "selective"

    try:
        if type == "original":
            img_bytes = await asyncio.to_thread(render_original_preview, str(src_file), page)
        else:
            img_bytes = await asyncio.to_thread(
                render_preview_page,
                str(src_file),
                page,
                color,
                mode,
                clean_bg,
                bg_threshold,
                contrast,
                scanner_mode,
            )
        return Response(
            content=img_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=60"},
        )
    except Exception as exc:
        logger.exception("Preview generation error: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo generar la vista previa del documento.")


@app.post("/api/process")
async def process_file(
    req: ProcessRequest,
    background_tasks: BackgroundTasks,
):
    src_file = find_upload_file(req.file_id)
    if not src_file:
        raise HTTPException(status_code=404, detail="Archivo no encontrado o expirado.")

    color = req.color if _VALID_HEX_COLOR.match(req.color) else "#0038A8"
    mode = req.mode if req.mode in ("selective", "monochrome") else "selective"
    engine = req.engine if req.engine in ("vector", "raster") else "vector"
    dpi = req.dpi if req.dpi in (150, 300) else 300

    output_id = f"{req.file_id}_out"
    output_pdf_path = OUTPUT_DIR / f"{output_id}.pdf"

    is_image = src_file.suffix.lower() in IMAGE_EXTENSIONS
    output_img_path = str(OUTPUT_DIR / f"{output_id}.png") if is_image else None

    try:
        await asyncio.to_thread(
            process_document,
            str(src_file),
            str(output_pdf_path),
            color,
            mode,
            req.clean_bg,
            req.bg_threshold,
            req.contrast,
            dpi,
            engine,
            req.scanner_mode,
            req.force_cmyk_no_k,
            req.page_range,
            output_img_path,
        )

        background_tasks.add_task(cleanup_old_files)

        res = {
            "output_id": output_id,
            "download_url": f"/api/download/{output_id}",
            "view_url": f"/api/view/{output_id}",
            "has_image": is_image,
            "engine_used": "raster" if (is_image or req.scanner_mode) else engine,
        }
        if is_image:
            res["download_image_url"] = f"/api/download-image/{output_id}"
        return res
    except Exception as exc:
        logger.exception("Process document error: %s", exc)
        raise HTTPException(status_code=500, detail="Error al procesar el documento.")


@app.delete("/api/file/{file_id}")
async def delete_user_file(file_id: str):
    """Allows the user to immediately wipe their uploaded and processed files from the server."""
    validate_file_id(file_id)
    removed = 0
    for ext in list(ALL_SUPPORTED_EXTENSIONS) + [".pdf"]:
        p = UPLOAD_DIR / f"{file_id}{ext}"
        if p.is_file():
            p.unlink(missing_ok=True)
            removed += 1
    for out_ext in (".pdf", ".png"):
        out_p = OUTPUT_DIR / f"{file_id}_out{out_ext}"
        if out_p.is_file():
            out_p.unlink(missing_ok=True)
            removed += 1
    return {"status": "deleted", "files_removed": removed}


@app.get("/api/download/{output_id}")
async def download_file(output_id: str):
    validate_output_id(output_id)
    file_path = OUTPUT_DIR / f"{output_id}.pdf"
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Documento procesado no encontrado o expirado.")

    return FileResponse(
        path=str(file_path),
        filename="documento_colorprint.pdf",
        media_type="application/pdf",
    )


@app.get("/api/download-image/{output_id}")
async def download_image_file(output_id: str):
    validate_output_id(output_id)
    file_path = OUTPUT_DIR / f"{output_id}.png"
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Imagen procesada no encontrada o expirada.")

    return FileResponse(
        path=str(file_path),
        filename="imagen_colorprint.png",
        media_type="image/png",
    )


@app.get("/api/view/{output_id}")
async def view_file(output_id: str):
    validate_output_id(output_id)
    file_path = OUTPUT_DIR / f"{output_id}.pdf"
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Documento procesado no encontrado o expirado.")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        content_disposition_type="inline",
    )
