import io
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

# Register modern image formats (HEIC / HEIF)
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

# Supported file extensions categorized
OFFICE_EXTENSIONS = {
    ".docx", ".doc", ".docm", ".dotx", ".dot",
    ".odt", ".rtf",
    ".xlsx", ".xls", ".xlsm", ".ods",
    ".pptx", ".ppt", ".potx", ".pot", ".odp",
    ".txt", ".csv", ".tsv", ".html", ".htm", ".md"
}

DOCUMENT_EXTENSIONS = {
    ".pdf", ".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif",
    ".heic", ".heif", ".avif", ".gif", ".ico", ".psd", ".tga"
}

ALL_SUPPORTED_EXTENSIONS = OFFICE_EXTENSIONS | DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex string (e.g. '#002060' or '002060') to (R, G, B) tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c * 2 for c in hex_color])
    if len(hex_color) != 6:
        return (0, 32, 96)  # Default navy
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def recolor_numpy_image(
    img_arr: np.ndarray,
    target_rgb: tuple[int, int, int],
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    color_threshold: int = 32
) -> np.ndarray:
    """
    Recolor an RGB uint8 numpy array.
    Replaces black/gray text and dark strokes with target_rgb.
    """
    if img_arr.ndim != 3 or img_arr.shape[2] < 3:
        raise ValueError("Image array must have at least 3 channels (RGB)")

    # Work with RGB channels
    arr = img_arr[:, :, :3].astype(np.float32)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]

    # Calculate luminance (ITU-R BT.601)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    lum_norm = lum / 255.0

    # Contrast boost (gamma curve to darken text and clean whites)
    if contrast_boost > 0.1:
        lum_norm = np.clip(np.power(lum_norm, contrast_boost), 0.0, 1.0)

    target_np = np.array(target_rgb, dtype=np.float32)

    # Base duotone recoloring: black (0) -> target_rgb, white (1) -> 255
    recolored = target_np + lum_norm[:, :, None] * (255.0 - target_np)

    # Background cleaning: remove faint scanner grays and off-white paper noise
    if clean_bg:
        is_bg = lum >= bg_threshold
        recolored[is_bg] = [255.0, 255.0, 255.0]

    if mode == "selective":
        # Check chromaticity: max(R,G,B) - min(R,G,B)
        max_ch = np.maximum(np.maximum(r, g), b)
        min_ch = np.minimum(np.minimum(r, g), b)
        color_diff = max_ch - min_ch

        # Near-grayscale or very dark (where printers would use black ink anyway)
        is_dark_or_gray = (color_diff < color_threshold) | (lum < 40)
        final_arr = np.where(is_dark_or_gray[:, :, None], recolored, arr)
    else:
        # Full monochrome duotone
        final_arr = recolored

    return np.clip(final_arr, 0, 255).astype(np.uint8)

def convert_to_printable_pdf(input_path: str, output_pdf_path: str) -> str:
    """
    Converts any supported office or document format (docx, xlsx, pptx, epub, xps, svg, etc.)
    into a standard printable PDF file.
    """
    ext = Path(input_path).suffix.lower()

    if ext == ".pdf":
        if input_path != output_pdf_path:
            shutil.copyfile(input_path, output_pdf_path)
        return output_pdf_path

    # Office documents -> LibreOffice conversion
    if ext in OFFICE_EXTENSIONS:
        out_dir = Path(output_pdf_path).parent
        cmd = [
            "soffice", "--headless",
            "-env:UserInstallation=file:///tmp/libreoffice_profile",
            "--convert-to", "pdf",
            input_path,
            "--outdir", str(out_dir)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if res.returncode != 0:
            raise RuntimeError(f"Error al convertir documento ofimático: {res.stderr or res.stdout}")

        # LibreOffice names the output {stem}.pdf
        expected_name = Path(input_path).stem + ".pdf"
        lo_output = out_dir / expected_name
        if lo_output.exists():
            if str(lo_output) != output_pdf_path:
                shutil.move(str(lo_output), output_pdf_path)
            return output_pdf_path
        else:
            raise FileNotFoundError(f"LibreOffice no generó el archivo esperado: {lo_output}")

    # Documents supported directly by PyMuPDF (xps, oxps, epub, cbz, fb2, svg)
    if ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = fitz.open(input_path)
        pdf_bytes = doc.convert_to_pdf()
        doc.close()
        with open(output_pdf_path, "wb") as f:
            f.write(pdf_bytes)
        return output_pdf_path

    raise ValueError(f"Formato no convertible directamente a PDF: {ext}")

def get_document_info(file_path: str) -> dict:
    """Get metadata: page count, format, dimensions."""
    ext = Path(file_path).suffix.lower()

    if ext == '.pdf' or ext in OFFICE_EXTENSIONS or ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = fitz.open(file_path)
        page_count = len(doc)
        pages_info = []
        for i in range(min(page_count, 50)):
            p = doc[i]
            pages_info.append({
                "page": i + 1,
                "width": round(p.rect.width, 1),
                "height": round(p.rect.height, 1)
            })
        doc.close()
        return {
            "format": "pdf",
            "page_count": page_count,
            "pages": pages_info
        }
    else:
        with Image.open(file_path) as im:
            # Check if multi-frame / multi-page TIFF or GIF
            n_frames = getattr(im, "n_frames", 1)
            return {
                "format": "image",
                "page_count": n_frames,
                "pages": [{"page": 1, "width": im.width, "height": im.height}]
            }

def render_preview_page(
    file_path: str,
    page_num: int,
    target_color: str,
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    max_dim: int = 1200
) -> bytes:
    """
    Renders an original and/or recolored preview of a single page as JPEG bytes.
    """
    target_rgb = hex_to_rgb(target_color)
    ext = Path(file_path).suffix.lower()

    if ext == '.pdf' or ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = fitz.open(file_path)
        if page_num < 1 or page_num > len(doc):
            page_num = 1
        page = doc[page_num - 1]

        rect = page.rect
        scale = min(max_dim / max(rect.width, 1), max_dim / max(rect.height, 1), 2.5)
        scale = max(scale, 0.5)

        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        doc.close()
    else:
        with Image.open(file_path) as pil_img:
            if getattr(pil_img, "n_frames", 1) > 1 and page_num > 1:
                try:
                    pil_img.seek(page_num - 1)
                except EOFError:
                    pass
            pil_img = pil_img.convert("RGB")
            w, h = pil_img.size
            if max(w, h) > max_dim:
                ratio = max_dim / max(w, h)
                pil_img = pil_img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
            img_np = np.array(pil_img, dtype=np.uint8)

    # Apply recoloring
    recolored_np = recolor_numpy_image(
        img_arr=img_np,
        target_rgb=target_rgb,
        mode=mode,
        clean_bg=clean_bg,
        bg_threshold=bg_threshold,
        contrast_boost=contrast_boost
    )

    out_img = Image.fromarray(recolored_np)
    buf = io.BytesIO()
    out_img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()

def render_original_preview(
    file_path: str,
    page_num: int,
    max_dim: int = 1200
) -> bytes:
    """Renders the original page preview as JPEG bytes."""
    ext = Path(file_path).suffix.lower()

    if ext == '.pdf' or ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = fitz.open(file_path)
        if page_num < 1 or page_num > len(doc):
            page_num = 1
        page = doc[page_num - 1]

        rect = page.rect
        scale = min(max_dim / max(rect.width, 1), max_dim / max(rect.height, 1), 2.5)
        scale = max(scale, 0.5)

        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        doc.close()
        out_img = Image.fromarray(img_np)
    else:
        with Image.open(file_path) as pil_img:
            if getattr(pil_img, "n_frames", 1) > 1 and page_num > 1:
                try:
                    pil_img.seek(page_num - 1)
                except EOFError:
                    pass
            out_img = pil_img.convert("RGB")
            w, h = out_img.size
            if max(w, h) > max_dim:
                ratio = max_dim / max(w, h)
                out_img = out_img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    out_img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()

def process_document(
    input_path: str,
    output_pdf_path: str,
    target_color: str,
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    dpi: int = 300,
    output_img_path: Optional[str] = None,
    progress_callback = None
) -> Tuple[str, Optional[str]]:
    """
    Transforms the complete document (PDF, Office or Image) and writes the recolored PDF.
    Preserves original page dimensions and aspect ratio at high print resolution (DPI).
    If an image was uploaded and output_img_path is provided, also saves the recolored PNG image.
    """
    target_rgb = hex_to_rgb(target_color)
    ext = Path(input_path).suffix.lower()

    if ext == '.pdf':
        src_doc = fitz.open(input_path)
        total_pages = len(src_doc)
        out_doc = fitz.open()

        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for i in range(total_pages):
            page = src_doc[i]
            rect = page.rect

            # Render at target DPI
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))

            # Recolor
            recolored_np = recolor_numpy_image(
                img_arr=img_np,
                target_rgb=target_rgb,
                mode=mode,
                clean_bg=clean_bg,
                bg_threshold=bg_threshold,
                contrast_boost=contrast_boost
            )

            # Compress to JPEG stream for embedding in PDF
            buf = io.BytesIO()
            Image.fromarray(recolored_np).save(buf, format="JPEG", quality=92, optimize=True)
            img_bytes = buf.getvalue()

            # Create new page matching original physical size
            new_page = out_doc.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=img_bytes)

            if progress_callback:
                progress_callback(i + 1, total_pages)

        src_doc.close()
        out_doc.save(output_pdf_path, garbage=4, deflate=True)
        out_doc.close()
        return output_pdf_path, None

    else:
        # Single or multi-frame image
        with Image.open(input_path) as pil_img:
            n_frames = getattr(pil_img, "n_frames", 1)
            out_doc = fitz.open()
            recolored_first_img = None

            for frame_idx in range(n_frames):
                if n_frames > 1:
                    pil_img.seek(frame_idx)

                rgb_img = pil_img.convert("RGB")
                w, h = rgb_img.size
                img_np = np.array(rgb_img, dtype=np.uint8)

                recolored_np = recolor_numpy_image(
                    img_arr=img_np,
                    target_rgb=target_rgb,
                    mode=mode,
                    clean_bg=clean_bg,
                    bg_threshold=bg_threshold,
                    contrast_boost=contrast_boost
                )

                out_img = Image.fromarray(recolored_np)
                if frame_idx == 0:
                    recolored_first_img = out_img

                # Standard pt dimensions based on pixel dimensions
                pt_w = (w / dpi) * 72.0
                pt_h = (h / dpi) * 72.0
                if pt_w < 50 or pt_h < 50:
                    pt_w = 595.0
                    pt_h = 595.0 * (h / w)

                rect = fitz.Rect(0, 0, pt_w, pt_h)
                buf = io.BytesIO()
                out_img.save(buf, format="JPEG", quality=92, optimize=True)

                new_page = out_doc.new_page(width=pt_w, height=pt_h)
                new_page.insert_image(rect, stream=buf.getvalue())

            out_doc.save(output_pdf_path, garbage=4, deflate=True)
            out_doc.close()

            # If image output requested, save PNG
            img_result_path = None
            if output_img_path and recolored_first_img:
                recolored_first_img.save(output_img_path, format="PNG", optimize=True)
                img_result_path = output_img_path

            if progress_callback:
                progress_callback(1, 1)

            return output_pdf_path, img_result_path
