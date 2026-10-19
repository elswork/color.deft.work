import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pymupdf
from PIL import Image, ImageFilter, ImageOps

from .vector_engine import rewrite_content_stream_colors

# Prevent decompression bomb attacks (max 100 MP)
Image.MAX_IMAGE_PIXELS = 100_000_000
MAX_PAGES = 200

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
    """Convert hex string (e.g. '#0038A8' or '0038A8') to (R, G, B) tuple."""
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])
    if len(hex_color) != 6:
        return (0, 56, 168)  # Default Cobalt Blue (Anti-GCR safe)
    try:
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
    except ValueError:
        return (0, 56, 168)


def parse_page_range(page_range: Optional[str], total_pages: int) -> list[int]:
    """
    Parse a human-friendly page range string like '1-3, 5, 8-10' into sorted 0-based page indices.
    If empty or None, returns all pages up to total_pages.
    """
    if not page_range or not page_range.strip():
        return list(range(total_pages))

    selected: set[int] = set()
    parts = page_range.replace(";", ",").split(",")
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            bounds = token.split("-", 1)
            try:
                start = max(1, int(bounds[0].strip()))
                end = min(total_pages, int(bounds[1].strip()))
                if start <= end:
                    for p in range(start, end + 1):
                        selected.add(p - 1)
            except ValueError:
                continue
        else:
            try:
                p = int(token)
                if 1 <= p <= total_pages:
                    selected.add(p - 1)
            except ValueError:
                continue

    if not selected:
        return list(range(total_pages))
    return sorted(selected)


def apply_scanner_normalization(img_arr: np.ndarray) -> np.ndarray:
    """
    Mobile Document Scanner enhancement:
    Divides each channel by a heavily blurred local background estimate to remove
    uneven lighting, phone camera shadows, and paper yellowing before recoloring.
    """
    pil_rgb = Image.fromarray(img_arr[:, :, :3])
    # Downscale for fast large-kernel blur, then upscale back
    w, h = pil_rgb.size
    small_w = max(32, w // 8)
    small_h = max(32, h // 8)
    small_bg = pil_rgb.resize((small_w, small_h), Image.Resampling.BILINEAR)
    blurred_bg = small_bg.filter(ImageFilter.GaussianBlur(radius=9)).resize(
        (w, h), Image.Resampling.BILINEAR
    )

    fg = np.asarray(pil_rgb, dtype=np.float32)
    bg = np.maximum(np.asarray(blurred_bg, dtype=np.float32), 15.0)

    # Normalize illumination and stretch contrast slightly
    norm = np.clip((fg / bg) * 255.0, 0.0, 255.0)
    # Suppress light paper grain above 225
    norm = np.where(norm > 225.0, 255.0, norm * 0.92)
    return np.clip(norm, 0, 255).astype(np.uint8)


def recolor_numpy_image(
    img_arr: np.ndarray,
    target_rgb: tuple[int, int, int],
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    color_threshold: int = 32,
    scanner_mode: bool = False,
) -> np.ndarray:
    """
    Recolor an RGB uint8 numpy array.
    Replaces black/gray text and dark strokes with target_rgb.
    """
    if img_arr.ndim != 3 or img_arr.shape[2] < 3:
        raise ValueError("Image array must have at least 3 channels (RGB)")

    work_arr = img_arr[:, :, :3]
    if scanner_mode:
        work_arr = apply_scanner_normalization(work_arr)

    arr = work_arr.astype(np.float32)
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
        max_ch = np.maximum(np.maximum(r, g), b)
        min_ch = np.minimum(np.minimum(r, g), b)
        color_diff = max_ch - min_ch

        # Near-grayscale or dark pixels where printer GCR would trigger black ink
        is_dark_or_gray = (color_diff < color_threshold) | (lum < 55)
        final_arr = np.where(is_dark_or_gray[:, :, None], recolored, arr)
    else:
        final_arr = recolored

    return np.clip(final_arr, 0, 255).astype(np.uint8)


def rgb_array_to_cmyk_no_k_jpeg(rgb_arr: np.ndarray, quality: int = 92) -> bytes:
    """
    Converts an RGB uint8 numpy array to a 4-channel CMYK JPEG where the K (Black)
    channel is strictly zeroed out (K=0 for every pixel).
    Note: Pillow/libjpeg writes CMYK JPEGs with inverted Adobe convention by default;
    standard CMYK in PIL has C=255-R, M=255-G, Y=255-B, K=0.
    """
    h, w, _ = rgb_arr.shape
    c = 255 - rgb_arr[:, :, 0]
    m = 255 - rgb_arr[:, :, 1]
    y = 255 - rgb_arr[:, :, 2]
    k = np.zeros((h, w), dtype=np.uint8)
    cmyk_arr = np.stack([c, m, y, k], axis=2)
    cmyk_img = Image.fromarray(cmyk_arr, mode="CMYK")
    buf = io.BytesIO()
    cmyk_img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def convert_to_printable_pdf(input_path: str, output_pdf_path: str) -> str:
    """
    Converts any supported office or document format (docx, xlsx, pptx, epub, xps, svg, etc.)
    into a standard printable PDF file using an isolated temporary LibreOffice profile.
    """
    ext = Path(input_path).suffix.lower()

    if ext == ".pdf":
        if input_path != output_pdf_path:
            shutil.copyfile(input_path, output_pdf_path)
        return output_pdf_path

    if ext in OFFICE_EXTENSIONS:
        out_dir = Path(output_pdf_path).parent
        with tempfile.TemporaryDirectory(prefix="lo_profile_") as lo_profile_dir:
            cmd = [
                "soffice",
                "--headless",
                "--nolockcheck",
                "--nodefault",
                "--norestore",
                f"-env:UserInstallation=file://{lo_profile_dir}",
                "--convert-to",
                "pdf",
                input_path,
                "--outdir",
                str(out_dir),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode != 0:
                raise RuntimeError("No se pudo convertir el documento ofimático a PDF.")

        expected_name = Path(input_path).stem + ".pdf"
        lo_output = out_dir / expected_name
        if lo_output.exists():
            if str(lo_output) != output_pdf_path:
                shutil.move(str(lo_output), output_pdf_path)
            return output_pdf_path
        raise FileNotFoundError("El conversor ofimático no generó el PDF esperado.")

    if ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = pymupdf.open(input_path)
        pdf_bytes = doc.convert_to_pdf()
        doc.close()
        with open(output_pdf_path, "wb") as f:
            f.write(pdf_bytes)
        return output_pdf_path

    raise ValueError(f"Formato no convertible directamente a PDF: {ext}")


def get_document_info(file_path: str) -> dict:
    """Get metadata: page count, format, dimensions, and whether it contains vector text."""
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf" or ext in OFFICE_EXTENSIONS or ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = pymupdf.open(file_path)
        page_count = len(doc)
        if page_count > MAX_PAGES:
            doc.close()
            raise ValueError(f"El documento supera el límite máximo de {MAX_PAGES} páginas ({page_count}).")

        pages_info = []
        has_vector_text = False
        for i in range(min(page_count, 50)):
            p = doc[i]
            if not has_vector_text and len(p.get_text("text").strip()) > 3:
                has_vector_text = True
            pages_info.append({
                "page": i + 1,
                "width": round(p.rect.width, 1),
                "height": round(p.rect.height, 1),
            })
        doc.close()
        return {
            "format": "pdf",
            "page_count": page_count,
            "has_vector_text": has_vector_text,
            "pages": pages_info,
        }
    else:
        with Image.open(file_path) as im:
            # Only treat multi-page TIFFs as multi-page; animated GIF/WEBP use frame 1
            raw_frames = getattr(im, "n_frames", 1)
            n_frames = min(raw_frames, MAX_PAGES) if ext in {".tiff", ".tif"} else 1
            return {
                "format": "image",
                "page_count": n_frames,
                "has_vector_text": False,
                "pages": [{"page": 1, "width": im.width, "height": im.height}],
            }


def render_preview_page(
    file_path: str,
    page_num: int,
    target_color: str,
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    scanner_mode: bool = False,
    max_dim: int = 1200,
) -> bytes:
    """Renders a recolored preview of a single page as JPEG bytes."""
    target_rgb = hex_to_rgb(target_color)
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf" or ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = pymupdf.open(file_path)
        if page_num < 1 or page_num > len(doc):
            page_num = 1
        page = doc[page_num - 1]

        rect = page.rect
        scale = min(max_dim / max(rect.width, 1), max_dim / max(rect.height, 1), 2.5)
        scale = max(scale, 0.5)

        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        doc.close()
    else:
        with Image.open(file_path) as pil_img:
            pil_img = ImageOps.exif_transpose(pil_img)
            if ext in {".tiff", ".tif"} and getattr(pil_img, "n_frames", 1) > 1 and page_num > 1:
                try:
                    pil_img.seek(page_num - 1)
                except EOFError:
                    pass
            # Handle transparency over white background
            if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                rgba = pil_img.convert("RGBA")
                white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                pil_img = Image.alpha_composite(white_bg, rgba).convert("RGB")
            else:
                pil_img = pil_img.convert("RGB")

            w, h = pil_img.size
            if max(w, h) > max_dim:
                ratio = max_dim / max(w, h)
                pil_img = pil_img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
            img_np = np.array(pil_img, dtype=np.uint8)

    recolored_np = recolor_numpy_image(
        img_arr=img_np,
        target_rgb=target_rgb,
        mode=mode,
        clean_bg=clean_bg,
        bg_threshold=bg_threshold,
        contrast_boost=contrast_boost,
        scanner_mode=scanner_mode,
    )

    out_img = Image.fromarray(recolored_np)
    buf = io.BytesIO()
    out_img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


def render_original_preview(
    file_path: str,
    page_num: int,
    max_dim: int = 1200,
) -> bytes:
    """Renders the original page preview as JPEG bytes."""
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf" or ext in {".xps", ".oxps", ".epub", ".cbz", ".fb2", ".svg"}:
        doc = pymupdf.open(file_path)
        if page_num < 1 or page_num > len(doc):
            page_num = 1
        page = doc[page_num - 1]

        rect = page.rect
        scale = min(max_dim / max(rect.width, 1), max_dim / max(rect.height, 1), 2.5)
        scale = max(scale, 0.5)

        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        doc.close()
        out_img = Image.fromarray(img_np)
    else:
        with Image.open(file_path) as pil_img:
            pil_img = ImageOps.exif_transpose(pil_img)
            if ext in {".tiff", ".tif"} and getattr(pil_img, "n_frames", 1) > 1 and page_num > 1:
                try:
                    pil_img.seek(page_num - 1)
                except EOFError:
                    pass
            if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                rgba = pil_img.convert("RGBA")
                white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                out_img = Image.alpha_composite(white_bg, rgba).convert("RGB")
            else:
                out_img = pil_img.convert("RGB")
            w, h = out_img.size
            if max(w, h) > max_dim:
                ratio = max_dim / max(w, h)
                out_img = out_img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    out_img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _recolor_pdf_vector_native(
    src_doc: pymupdf.Document,
    selected_indices: list[int],
    output_pdf_path: str,
    target_rgb: tuple[int, int, int],
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    scanner_mode: bool = False,
    force_cmyk_no_k: bool = False,
) -> None:
    """
    Recolors a PDF preserving 100% of vector text, fonts, and paths, while also
    recoloring any embedded bitmap images in-place.
    """
    out_doc = pymupdf.open()
    for page_idx in selected_indices:
        out_doc.insert_pdf(src_doc, from_page=page_idx, to_page=page_idx)

    processed_image_xrefs: set[int] = set()
    processed_form_xrefs: set[int] = set()

    for page in out_doc:
        page.clean_contents()
        for c_xref in page.get_contents():
            raw_stream = out_doc.xref_stream(c_xref)
            if raw_stream:
                new_stream = rewrite_content_stream_colors(
                    stream_bytes=raw_stream,
                    target_rgb=target_rgb,
                    mode=mode,
                    clean_bg=clean_bg,
                    bg_threshold=bg_threshold,
                    contrast_boost=contrast_boost,
                    force_cmyk_no_k=force_cmyk_no_k,
                    prepend_default_color=True,
                )
                out_doc.update_stream(c_xref, new_stream)

        # Also rewrite any Form XObjects referenced by the page
        for xobj in page.get_xobjects():
            x_xref = xobj[0]
            if x_xref not in processed_form_xrefs:
                processed_form_xrefs.add(x_xref)
                try:
                    raw_xstream = out_doc.xref_stream(x_xref)
                    if raw_xstream:
                        new_xstream = rewrite_content_stream_colors(
                            stream_bytes=raw_xstream,
                            target_rgb=target_rgb,
                            mode=mode,
                            clean_bg=clean_bg,
                            bg_threshold=bg_threshold,
                            contrast_boost=contrast_boost,
                            force_cmyk_no_k=force_cmyk_no_k,
                            prepend_default_color=True,
                        )
                        out_doc.update_stream(x_xref, new_xstream)
                except Exception:
                    pass

        # Recolor embedded raster images on the page
        for img_info in page.get_images(full=True):
            img_xref = img_info[0]
            if img_xref in processed_image_xrefs:
                continue
            processed_image_xrefs.add(img_xref)
            try:
                pix = pymupdf.Pixmap(out_doc, img_xref)
                if pix.Colorspace is None or pix.n > 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                elif pix.alpha:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                elif pix.n != 3:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)

                img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
                recolored_np = recolor_numpy_image(
                    img_arr=img_np,
                    target_rgb=target_rgb,
                    mode=mode,
                    clean_bg=clean_bg,
                    bg_threshold=bg_threshold,
                    contrast_boost=contrast_boost,
                    scanner_mode=scanner_mode,
                )
                buf = io.BytesIO()
                Image.fromarray(recolored_np).save(buf, format="PNG", optimize=True)
                page.replace_image(img_xref, stream=buf.getvalue())
            except Exception:
                continue

    out_doc.save(output_pdf_path, garbage=4, deflate=True)
    out_doc.close()


def process_document(
    input_path: str,
    output_pdf_path: str,
    target_color: str,
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    dpi: int = 300,
    engine: str = "vector",
    scanner_mode: bool = False,
    force_cmyk_no_k: bool = False,
    page_range: Optional[str] = None,
    output_img_path: Optional[str] = None,
    progress_callback=None,
) -> Tuple[str, Optional[str]]:
    """
    Transforms the complete document (PDF, Office or Image) and writes the recolored PDF.
    Supports:
    - engine='vector': Preserves vector text, fonts, and paths while recoloring in-place.
    - engine='raster': High-DPI rasterization (300/150 DPI), ideal for scanned documents.
    - scanner_mode=True: Removes mobile photo shadows & uneven lighting.
    - force_cmyk_no_k=True: Emits explicit DeviceCMYK with K=0.
    - page_range: Optional subset of pages (e.g. '1-3, 5').
    """
    target_rgb = hex_to_rgb(target_color)
    ext = Path(input_path).suffix.lower()

    if ext == ".pdf":
        src_doc = pymupdf.open(input_path)
        total_pages = min(len(src_doc), MAX_PAGES)
        selected_indices = parse_page_range(page_range, total_pages)

        # Use native vector engine if requested and scanner_mode is not forced
        if engine == "vector" and not scanner_mode:
            try:
                _recolor_pdf_vector_native(
                    src_doc=src_doc,
                    selected_indices=selected_indices,
                    output_pdf_path=output_pdf_path,
                    target_rgb=target_rgb,
                    mode=mode,
                    clean_bg=clean_bg,
                    bg_threshold=bg_threshold,
                    contrast_boost=contrast_boost,
                    scanner_mode=scanner_mode,
                    force_cmyk_no_k=force_cmyk_no_k,
                )
                src_doc.close()
                return output_pdf_path, None
            except Exception:
                # Fallback to high-DPI raster engine if a malformed PDF stream fails
                pass

        out_doc = pymupdf.open()
        zoom = dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)

        for idx_pos, page_idx in enumerate(selected_indices):
            page = src_doc[page_idx]
            rect = page.rect

            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))

            recolored_np = recolor_numpy_image(
                img_arr=img_np,
                target_rgb=target_rgb,
                mode=mode,
                clean_bg=clean_bg,
                bg_threshold=bg_threshold,
                contrast_boost=contrast_boost,
                scanner_mode=scanner_mode,
            )

            if force_cmyk_no_k:
                img_bytes = rgb_array_to_cmyk_no_k_jpeg(recolored_np, quality=92)
            else:
                buf = io.BytesIO()
                Image.fromarray(recolored_np).save(buf, format="JPEG", quality=92, optimize=True)
                img_bytes = buf.getvalue()

            new_page = out_doc.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=img_bytes)

            if progress_callback:
                progress_callback(idx_pos + 1, len(selected_indices))

        src_doc.close()
        out_doc.save(output_pdf_path, garbage=4, deflate=True)
        out_doc.close()
        return output_pdf_path, None

    else:
        # Singleimage or multi-page TIFF -> A4-fitted printable PDF + optional PNG
        with Image.open(input_path) as pil_img:
            pil_img = ImageOps.exif_transpose(pil_img)
            raw_frames = getattr(pil_img, "n_frames", 1)
            n_frames = min(raw_frames, MAX_PAGES) if ext in {".tiff", ".tif"} else 1
            selected_indices = parse_page_range(page_range, n_frames)

            out_doc = pymupdf.open()
            recolored_first_img = None

            for frame_idx in selected_indices:
                if n_frames > 1:
                    try:
                        pil_img.seek(frame_idx)
                    except EOFError:
                        break

                if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                    rgba = pil_img.convert("RGBA")
                    white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                    rgb_img = Image.alpha_composite(white_bg, rgba).convert("RGB")
                else:
                    rgb_img = pil_img.convert("RGB")

                w, h = rgb_img.size
                img_np = np.array(rgb_img, dtype=np.uint8)

                recolored_np = recolor_numpy_image(
                    img_arr=img_np,
                    target_rgb=target_rgb,
                    mode=mode,
                    clean_bg=clean_bg,
                    bg_threshold=bg_threshold,
                    contrast_boost=contrast_boost,
                    scanner_mode=scanner_mode,
                )

                out_img = Image.fromarray(recolored_np)
                if recolored_first_img is None:
                    recolored_first_img = out_img

                # Fit cleanly onto a standard A4 page (portrait or landscape) with 18pt margins
                is_landscape = w > h
                a4_w, a4_h = (841.89, 595.28) if is_landscape else (595.28, 841.89)
                margin = 18.0
                avail_w = a4_w - 2 * margin
                avail_h = a4_h - 2 * margin
                scale = min(avail_w / max(w, 1), avail_h / max(h, 1))
                draw_w = w * scale
                draw_h = h * scale
                x0 = (a4_w - draw_w) / 2.0
                y0 = (a4_h - draw_h) / 2.0
                target_rect = pymupdf.Rect(x0, y0, x0 + draw_w, y0 + draw_h)

                if force_cmyk_no_k:
                    img_bytes = rgb_array_to_cmyk_no_k_jpeg(recolored_np, quality=92)
                else:
                    buf = io.BytesIO()
                    out_img.save(buf, format="JPEG", quality=92, optimize=True)
                    img_bytes = buf.getvalue()

                new_page = out_doc.new_page(width=a4_w, height=a4_h)
                new_page.insert_image(target_rect, stream=img_bytes)

            out_doc.save(output_pdf_path, garbage=4, deflate=True)
            out_doc.close()

            img_result_path = None
            if output_img_path and recolored_first_img:
                recolored_first_img.save(output_img_path, format="PNG", optimize=True)
                img_result_path = output_img_path

            if progress_callback:
                progress_callback(1, 1)

            return output_pdf_path, img_result_path
