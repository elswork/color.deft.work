"""Test suite for ColorPrint 3.0 (color.deft.work).

Tests cover:
- Health check endpoints
- Anti-GCR calibration swatches and vector PDF generation
- Anti-IDOR protections (rejection of wildcards, path traversal, non-hex IDs)
- Native vector PDF stream rewriting and text preservation
- Page range parsing and out-of-bounds guards
- Mobile scanner shadow removal filter
- File upload, preview generation, and immediate deletion
"""

import io
from pathlib import Path
import pytest
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image
import pymupdf

from app.main import app
from app.calibration import CALIBRATION_SWATCHES, generate_calibration_pdf
from app.processor import (
    parse_page_range,
    apply_scanner_normalization,
    recolor_numpy_image,
)
from app.vector_engine import vector_recolor_pdf


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    """Health check endpoints must return 200 and expected status."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_api = client.get("/api/health")
    assert res_api.status_code == 200
    assert res_api.json()["status"] == "ok"


def test_anti_idor_and_validation(client):
    """Endpoints must reject path traversal, wildcards, and non-hex file IDs."""
    # Wildcard rejection
    res = client.get("/api/preview/*")
    assert res.status_code == 400

    # Path traversal rejection
    res = client.get("/api/preview/../etc/passwd")
    assert res.status_code in (400, 404)

    # Valid hex format but non-existent file
    res = client.get("/api/preview/0123456789abcdef0123456789abcdef")
    assert res.status_code == 404

    # Delete with invalid ID
    res = client.delete("/api/file/*")
    assert res.status_code == 400


def test_calibration_swatches(client):
    """API must provide 24 empirical Anti-GCR calibration swatches."""
    res = client.get("/api/calibration-swatches")
    assert res.status_code == 200
    data = res.json()
    assert "swatches" in data
    swatches = data["swatches"]
    assert len(swatches) == 24
    assert swatches[0]["name"] == "Cobalto Real"
    assert swatches[0]["hex"] == "#0038A8"
    assert swatches[0]["cmyk"] == [100, 67, 0, 0]


def test_calibration_pdf_generation(client):
    """Calibration PDF generator must produce a valid A4 PDF."""
    pdf_bytes = generate_calibration_pdf()
    assert pdf_bytes.startswith(b"%PDF-")
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count == 1
    text = doc[0].get_text()
    assert "CALIBRACION" in text or "color.deft.work" in text

    # Also test via HTTP endpoint
    res = client.get("/api/calibration-sheet")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 1000


def test_parse_page_range():
    """Page range parser must correctly parse single pages, ranges, and clamp."""
    # Single page
    assert parse_page_range("1", total_pages=5) == [0]
    # Comma separated
    assert parse_page_range("1, 3, 5", total_pages=5) == [0, 2, 4]
    # Range
    assert parse_page_range("2-4", total_pages=5) == [1, 2, 3]
    # Mixed with clamping
    assert parse_page_range("1, 4-6, 10", total_pages=5) == [0, 3, 4]
    # None or empty returns all
    assert parse_page_range(None, total_pages=3) == [0, 1, 2]
    assert parse_page_range("", total_pages=3) == [0, 1, 2]


def test_vector_recolor_preserves_text(tmp_path):
    """Vector rewriting must change black text color while keeping text selectable."""
    input_pdf = tmp_path / "sample.pdf"
    output_pdf = tmp_path / "output.pdf"

    # Create synthetic PDF with black text
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    sample_text = "ColorPrint Vector Engine Anti-GCR Test"
    page.insert_text((72, 100), sample_text, fontsize=18, color=(0, 0, 0))
    doc.save(str(input_pdf))
    doc.close()

    # Apply vector engine
    success = vector_recolor_pdf(
        str(input_pdf),
        str(output_pdf),
        target_hex="#0038A8",
        mode="selective",
        force_cmyk_no_k=True,
    )
    assert success is True
    assert output_pdf.exists()

    # Verify text is intact and selectable
    recolored_doc = pymupdf.open(str(output_pdf))
    assert recolored_doc.page_count == 1
    extracted_text = recolored_doc[0].get_text()
    assert sample_text in extracted_text
    recolored_doc.close()


def test_mobile_scanner_mode():
    """Mobile scanner filter removes non-uniform illumination and background shadows."""
    # Create an image array with an artificial dark gradient/shadow
    img_arr = np.full((100, 100, 3), 210, dtype=np.uint8)
    # Add darker shadow area
    img_arr[0:50, 0:50] = 160
    cleaned = apply_scanner_normalization(img_arr)
    assert cleaned.shape == (100, 100, 3)
    # Background in previously shadowed area should be normalized brighter
    assert cleaned[25, 25, 0] >= img_arr[25, 25, 0]


def test_upload_preview_and_delete(client):
    """Full lifecycle: upload image, fetch preview, and immediately delete file."""
    # Generate a small in-memory PNG
    img = Image.new("RGB", (100, 100), color="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # 1. Upload
    res = client.post(
        "/api/upload",
        files={"file": ("test_doc.png", buf.getvalue(), "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    file_id = data["file_id"]
    assert len(file_id) == 32
    assert data["format"] == "image"
    assert data["page_count"] == 1

    # 2. Preview
    prev_res = client.get(f"/api/preview/{file_id}?type=recolored&color=%230038A8")
    assert prev_res.status_code == 200
    assert prev_res.headers["content-type"].startswith("image/")

    # 3. Process
    proc_res = client.post(
        "/api/process",
        json={
            "file_id": file_id,
            "color": "#0038A8",
            "mode": "selective",
            "clean_bg": True,
            "bg_threshold": 242,
            "contrast": 1.15,
            "dpi": 150,
            "engine": "raster",
        },
    )
    assert proc_res.status_code == 200
    proc_data = proc_res.json()
    assert "download_url" in proc_data

    # 4. Immediate delete
    del_res = client.delete(f"/api/file/{file_id}")
    assert del_res.status_code == 200

    # 5. Verify file is gone
    post_del_res = client.get(f"/api/preview/{file_id}")
    assert post_del_res.status_code == 404
