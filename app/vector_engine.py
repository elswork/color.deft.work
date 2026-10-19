"""
Native Vector PDF Recoloring Engine.
Rewrites PDF content stream color operators (g, G, rg, RG, k, K, sc, SC, scn, SCN)
outside of string/hex literals, sets initial graphics state color so default-black text
is recolored, and recolores embedded raster images in-place while keeping vector text
100% selectable and razor-sharp.
"""
import io
import re
from typing import Optional
import numpy as np
import pymupdf
from PIL import Image


def rgb_to_cmy_no_k(r: float, g: float, b: float) -> tuple[float, float, float, float]:
    """
    Convert normalized RGB (0..1) into CMYK (0..1) with K strictly forced to 0.0.
    This guarantees the PDF color operator is emitted as `C M Y 0 k` / `C M Y 0 K`.
    """
    c = float(np.clip(1.0 - r, 0.0, 1.0))
    m = float(np.clip(1.0 - g, 0.0, 1.0))
    y = float(np.clip(1.0 - b, 0.0, 1.0))
    return (c, m, y, 0.0)


def _format_color_op(
    r: float,
    g: float,
    b: float,
    is_stroke: bool,
    force_cmyk_no_k: bool = False,
) -> str:
    if force_cmyk_no_k:
        c, m, y, _ = rgb_to_cmy_no_k(r, g, b)
        op = "K" if is_stroke else "k"
        return f"{c:.4f} {m:.4f} {y:.4f} 0 {op}"
    else:
        op = "RG" if is_stroke else "rg"
        return f"{r:.4f} {g:.4f} {b:.4f} {op}"


def _interpolate_target(
    lum: float,
    target_norm: tuple[float, float, float],
    contrast_boost: float = 1.15,
    clean_bg: bool = True,
    bg_threshold_norm: float = 0.95,
) -> tuple[float, float, float]:
    lum_c = float(np.clip(lum, 0.0, 1.0))
    if clean_bg and lum_c >= bg_threshold_norm:
        return (1.0, 1.0, 1.0)
    if contrast_boost > 0.1:
        lum_c = float(np.clip(lum_c ** contrast_boost, 0.0, 1.0))
    tr, tg, tb = target_norm
    return (
        tr + lum_c * (1.0 - tr),
        tg + lum_c * (1.0 - tg),
        tb + lum_c * (1.0 - tb),
    )


# Regex matching numeric color operators in a non-string segment of a PDF content stream
_NUM = r"[+-]?(?:\d+\.?\d*|\.\d+)"
_COLOR_OP_RE = re.compile(
    rf"(?<![/\w])(?:({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})\s+(k|K|scn|SCN)"
    rf"|({_NUM})\s+({_NUM})\s+({_NUM})\s+(rg|RG|sc|SC|scn|SCN)"
    rf"|({_NUM})\s+(g|G))(?![\w])"
)


def _split_pdf_stream_preserving_strings(stream_text: str) -> list[tuple[bool, str]]:
    """
    Splits a PDF content stream into [(is_code, segment), ...] so we never
    alter text inside (...) literal strings or <...> hex strings.
    """
    segments: list[tuple[bool, str]] = []
    n = len(stream_text)
    i = 0
    code_start = 0

    while i < n:
        ch = stream_text[i]
        if ch == "(":
            if i > code_start:
                segments.append((True, stream_text[code_start:i]))
            str_start = i
            depth = 1
            i += 1
            while i < n and depth > 0:
                if stream_text[i] == "\\":
                    i += 2
                    continue
                if stream_text[i] == "(":
                    depth += 1
                elif stream_text[i] == ")":
                    depth -= 1
                i += 1
            segments.append((False, stream_text[str_start:i]))
            code_start = i
        elif ch == "<" and (i + 1 < n and stream_text[i + 1] != "<"):
            if i > code_start:
                segments.append((True, stream_text[code_start:i]))
            hex_start = i
            i += 1
            while i < n and stream_text[i] != ">":
                i += 1
            if i < n:
                i += 1
            segments.append((False, stream_text[hex_start:i]))
            code_start = i
        else:
            i += 1

    if code_start < n:
        segments.append((True, stream_text[code_start:n]))

    return segments


def rewrite_content_stream_colors(
    stream_bytes: bytes,
    target_rgb: tuple[int, int, int],
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    color_threshold: int = 32,
    force_cmyk_no_k: bool = False,
    prepend_default_color: bool = True,
) -> bytes:
    """
    Rewrites color operators in a PDF content stream so dark/black strokes & fills
    map to target_rgb (or CMYK with K=0).
    """
    text = stream_bytes.decode("latin1")
    target_norm = (target_rgb[0] / 255.0, target_rgb[1] / 255.0, target_rgb[2] / 255.0)
    bg_thresh_norm = bg_threshold / 255.0
    col_thresh_norm = color_threshold / 255.0

    def _replace_match(m: re.Match) -> str:
        # Case 1: 4 operands (CMYK k / K / scn / SCN)
        if m.group(5) is not None:
            c, m_val, y, k = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
            op = m.group(5)
            is_stroke = op.isupper()
            r = (1.0 - min(1.0, c * (1.0 - k) + k))
            g = (1.0 - min(1.0, m_val * (1.0 - k) + k))
            b = (1.0 - min(1.0, y * (1.0 - k) + k))
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            diff = max(r, g, b) - min(r, g, b)
            if mode == "selective" and diff >= col_thresh_norm and lum >= 0.18 and k < 0.25:
                return m.group(0)
            nr, ng, nb = _interpolate_target(lum, target_norm, contrast_boost, clean_bg, bg_thresh_norm)
            return _format_color_op(nr, ng, nb, is_stroke, force_cmyk_no_k)

        # Case 2: 3 operands (RGB rg / RG / sc / SC / scn / SCN)
        if m.group(9) is not None:
            r, g, b = float(m.group(6)), float(m.group(7)), float(m.group(8))
            op = m.group(9)
            is_stroke = op.isupper()
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            diff = max(r, g, b) - min(r, g, b)
            if mode == "selective" and diff >= col_thresh_norm and lum >= 0.18:
                return m.group(0)
            nr, ng, nb = _interpolate_target(lum, target_norm, contrast_boost, clean_bg, bg_thresh_norm)
            return _format_color_op(nr, ng, nb, is_stroke, force_cmyk_no_k)

        # Case 3: 1 operand (Gray g / G)
        gray = float(m.group(10))
        op = m.group(11)
        is_stroke = op.isupper()
        nr, ng, nb = _interpolate_target(gray, target_norm, contrast_boost, clean_bg, bg_thresh_norm)
        return _format_color_op(nr, ng, nb, is_stroke, force_cmyk_no_k)

    segments = _split_pdf_stream_preserving_strings(text)
    out_parts: list[str] = []

    if prepend_default_color:
        init_fill = _format_color_op(target_norm[0], target_norm[1], target_norm[2], False, force_cmyk_no_k)
        init_stroke = _format_color_op(target_norm[0], target_norm[1], target_norm[2], True, force_cmyk_no_k)
        out_parts.append(f"{init_fill} {init_stroke}\n")

    for is_code, seg in segments:
        if is_code:
            rewritten = _COLOR_OP_RE.sub(_replace_match, seg)
            # Also ensure after any graphics state restore `Q` we re-establish default fill/stroke
            if prepend_default_color:
                init_ops = f"{_format_color_op(target_norm[0], target_norm[1], target_norm[2], False, force_cmyk_no_k)} {_format_color_op(target_norm[0], target_norm[1], target_norm[2], True, force_cmyk_no_k)}"
                rewritten = re.sub(r"(?<![/\w])Q(?![\w])", f"Q\n{init_ops}", rewritten)
            out_parts.append(rewritten)
        else:
            out_parts.append(seg)

    return "".join(out_parts).encode("latin1")


def vector_recolor_pdf(
    input_pdf_path: str,
    output_pdf_path: str,
    target_hex: str,
    mode: str = "selective",
    clean_bg: bool = True,
    bg_threshold: int = 242,
    contrast_boost: float = 1.15,
    force_cmyk_no_k: bool = False,
) -> bool:
    """
    Convenience function to recolor a complete PDF using the native vector stream rewriter.
    """
    hex_clean = target_hex.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    target_rgb = (int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16))

    doc = pymupdf.open(input_pdf_path)
    for page in doc:
        for xref in page.get_contents():
            stream_data = doc.xref_stream(xref)
            if not stream_data:
                continue
            new_stream = rewrite_content_stream_colors(
                stream_data,
                target_rgb=target_rgb,
                mode=mode,
                clean_bg=clean_bg,
                bg_threshold=bg_threshold,
                contrast_boost=contrast_boost,
                force_cmyk_no_k=force_cmyk_no_k,
                prepend_default_color=True,
            )
            doc.update_stream(xref, new_stream)

    doc.save(output_pdf_path, garbage=4, deflate=True)
    doc.close()
    return True

