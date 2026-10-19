"""
Printer Calibration Sheet Generator & Anti-GCR Color Profiles.
Helps users empirically find which CMY color combination bypasses their printer's
GCR/UCR (Gray Component Replacement) threshold without triggering the broken Black (K) head.
"""
import pymupdf

CALIBRATION_SWATCHES = [
    # Row 1: Blues & Cyans (Cyan + Magenta)
    {"id": 1,  "name": "Cobalto Real",       "hex": "#0038A8", "cmyk": (100, 67, 0, 0),  "group": "Azules (C+M)"},
    {"id": 2,  "name": "Azul Marino Vivo",   "hex": "#002B7F", "cmyk": (100, 75, 0, 0),  "group": "Azules (C+M)"},
    {"id": 3,  "name": "Cian Profundo",      "hex": "#00558F", "cmyk": (100, 40, 0, 0),  "group": "Azules (C+M)"},
    {"id": 4,  "name": "Azul Zafiro",        "hex": "#0F4C81", "cmyk": (88, 41, 0, 0),   "group": "Azules (C+M)"},
    # Row 2: Cyans & Teals
    {"id": 5,  "name": "Azul Eléctrico",     "hex": "#0047AB", "cmyk": (100, 58, 0, 0),  "group": "Azules (C+M)"},
    {"id": 6,  "name": "Azul Petróleo",      "hex": "#005F73", "cmyk": (100, 18, 15, 0), "group": "Azules (C+M)"},
    {"id": 7,  "name": "Turquesa Oscuro",    "hex": "#007791", "cmyk": (100, 18, 0, 0),  "group": "Azules (C+M)"},
    {"id": 8,  "name": "Cian Puro (100% C)", "hex": "#0088CC", "cmyk": (100, 0, 0, 0),   "group": "Azules (C+M)"},
    # Row 3: Violets & Purples
    {"id": 9,  "name": "Violeta Imperial",   "hex": "#3B0086", "cmyk": (56, 100, 0, 0),  "group": "Violetas y Magentas"},
    {"id": 10, "name": "Púrpura Real",       "hex": "#4B0082", "cmyk": (42, 100, 0, 0),  "group": "Violetas y Magentas"},
    {"id": 11, "name": "Amatista Intenso",   "hex": "#5A189A", "cmyk": (41, 84, 0, 0),   "group": "Violetas y Magentas"},
    {"id": 12, "name": "Ciruela CMY",        "hex": "#6A0572", "cmyk": (7, 95, 0, 0),    "group": "Violetas y Magentas"},
    # Row 4: Magentas, Crimsons & Burgundies
    {"id": 13, "name": "Borgoña Vivo",       "hex": "#7A003C", "cmyk": (0, 100, 51, 0),  "group": "Rojos y Magentas"},
    {"id": 14, "name": "Carmesí Profundo",   "hex": "#8B0032", "cmyk": (0, 100, 64, 0),  "group": "Rojos y Magentas"},
    {"id": 15, "name": "Rubí Intenso",       "hex": "#9B111E", "cmyk": (0, 89, 80, 0),   "group": "Rojos y Magentas"},
    {"id": 16, "name": "Magenta Puro (100%M)", "hex": "#B80078", "cmyk": (0, 100, 15, 0), "group": "Rojos y Magentas"},
    # Row 5: Greens (Cyan + Yellow)
    {"id": 17, "name": "Verde Esmeralda",    "hex": "#005C29", "cmyk": (100, 0, 55, 0),  "group": "Verdes (C+Y)"},
    {"id": 18, "name": "Verde Bosque",       "hex": "#084D22", "cmyk": (90, 0, 56, 0),   "group": "Verdes (C+Y)"},
    {"id": 19, "name": "Verde Pino",         "hex": "#006B3C", "cmyk": (100, 0, 44, 0),  "group": "Verdes (C+Y)"},
    {"id": 20, "name": "Jade Oscuro",        "hex": "#007A5E", "cmyk": (100, 0, 23, 0),  "group": "Verdes (C+Y)"},
    # Row 6: Sepias, Browns & Safe CMY Dark
    {"id": 21, "name": "Sepia Cálido",       "hex": "#5C2C06", "cmyk": (0, 52, 90, 0),   "group": "Sepias y CMY"},
    {"id": 22, "name": "Terracota Oscuro",   "hex": "#7C2D12", "cmyk": (0, 64, 85, 0),   "group": "Sepias y CMY"},
    {"id": 23, "name": "Índigo Anti-GCR",    "hex": "#1B2A6B", "cmyk": (75, 60, 0, 0),   "group": "Sepias y CMY"},
    {"id": 24, "name": "Azul Noche Seguro",  "hex": "#002060", "cmyk": (100, 67, 0, 0),  "group": "Sepias y CMY"},
]


def _hex_to_norm_rgb(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def generate_calibration_pdf() -> bytes:
    """
    Generates an A4 vector calibration sheet PDF containing all 24 swatches,
    text legibility tests at multiple sizes, line thickness tests, and barcode bars.
    Even the header and instructions are rendered in Cobalt Blue (#0038A8) so ZERO
    black ink is requested when printing the calibration sheet itself.
    """
    doc = pymupdf.open()
    # A4 dimensions in points: 595.28 x 841.89
    page = doc.new_page(width=595.28, height=841.89)

    header_rgb = _hex_to_norm_rgb("#0038A8")
    accent_rgb = _hex_to_norm_rgb("#00558F")
    border_rgb = _hex_to_norm_rgb("#94A3B8")

    # Top Header Box
    header_rect = pymupdf.Rect(28, 24, 567.28, 92)
    page.draw_rect(header_rect, color=header_rgb, fill=header_rgb, width=1)

    page.insert_text(
        (40, 46),
        "HOJA DE CALIBRACION DE IMPRESORA SIN TINTA NEGRA (K=0)",
        fontsize=13,
        fontname="hebo",
        color=(1, 1, 1),
    )
    page.insert_text(
        (40, 63),
        "1. Imprime esta pagina en tu impresora.   2. Revisa que numero (#1 a #24) se ve mas nitido, oscuro y sin rayas.",
        fontsize=8.5,
        fontname="helv",
        color=(0.9, 0.96, 1.0),
    )
    page.insert_text(
        (40, 77),
        "3. Elige ese numero en https://color.deft.work. Consejo: activa 'Papel Fotografico' en tu impresora para forzar tintas CMY.",
        fontsize=8.2,
        fontname="helv",
        color=(0.85, 0.93, 1.0),
    )

    # Grid layout: 4 columns x 6 rows
    cols = 4
    rows = 6
    margin_x = 28.0
    start_y = 104.0
    gap_x = 8.0
    gap_y = 8.0
    usable_w = 595.28 - (2 * margin_x) - ((cols - 1) * gap_x)
    usable_h = 685.0 - ((rows - 1) * gap_y)
    cell_w = usable_w / cols
    cell_h = usable_h / rows

    for idx, swatch in enumerate(CALIBRATION_SWATCHES):
        r_idx = idx // cols
        c_idx = idx % cols

        x0 = margin_x + c_idx * (cell_w + gap_x)
        y0 = start_y + r_idx * (cell_h + gap_y)
        x1 = x0 + cell_w
        y1 = y0 + cell_h

        s_rgb = _hex_to_norm_rgb(swatch["hex"])
        cell_rect = pymupdf.Rect(x0, y0, x1, y1)
        band_rect = pymupdf.Rect(x0, y0, x1, y0 + 22)

        # Card outline & top color band
        page.draw_rect(cell_rect, color=s_rgb, width=1.0)
        page.draw_rect(band_rect, color=s_rgb, fill=s_rgb, width=0.5)

        # Swatch number and name in white on top band
        page.insert_text(
            (x0 + 6, y0 + 15),
            f"#{swatch['id']}  {swatch['name']}",
            fontsize=8.5,
            fontname="hebo",
            color=(1, 1, 1),
        )

        # Sample texts in the swatch color
        page.insert_text(
            (x0 + 6, y0 + 37),
            "Texto Normal AaBbCc 123",
            fontsize=9.2,
            fontname="hebo",
            color=s_rgb,
        )
        page.insert_text(
            (x0 + 6, y0 + 50),
            "Letra pequena factura 0123456789",
            fontsize=7.2,
            fontname="helv",
            color=s_rgb,
        )
        page.insert_text(
            (x0 + 6, y0 + 61),
            "Detalle fino: contrato / etiqueta / ticket",
            fontsize=6.2,
            fontname="helv",
            color=s_rgb,
        )

        # Line weight test (0.5pt, 1.2pt, 2.2pt)
        line_y = y0 + 70
        page.draw_line((x0 + 6, line_y), (x0 + 68, line_y), color=s_rgb, width=0.5)
        page.draw_line((x0 + 6, line_y + 4), (x0 + 68, line_y + 4), color=s_rgb, width=1.2)
        page.draw_line((x0 + 6, line_y + 9), (x0 + 68, line_y + 9), color=s_rgb, width=2.2)

        # Mini barcode test on the right side of the card
        bar_x = x0 + 78
        bar_weights = [1.2, 0.6, 1.8, 0.6, 0.6, 1.5, 0.8, 1.2, 0.6, 1.8, 0.6, 1.0]
        cur_bx = bar_x
        for bw in bar_weights:
            if cur_bx + bw < x1 - 5:
                page.draw_line((cur_bx, y0 + 66), (cur_bx, y0 + 82), color=s_rgb, width=bw)
            cur_bx += bw + 1.6

        # Footer metadata inside card: HEX + CMYK
        c, m, y_val, k = swatch["cmyk"]
        page.insert_text(
            (x0 + 6, y1 - 6),
            f"{swatch['hex']}  |  C:{c} M:{m} Y:{y_val} K:{k}",
            fontsize=6.0,
            fontname="cour",
            color=s_rgb,
        )

    # Bottom explanation footer (also in Cobalt Blue so 0% black ink is used)
    footer_y = 808
    page.draw_line((28, footer_y - 10), (567.28, footer_y - 10), color=border_rgb, width=0.6)
    page.insert_text(
        (28, footer_y + 2),
        "Por que ocurre esto: Los drivers de impresora usan GCR (Gray Component Replacement) y envian al cabezal negro (K) los colores muy oscuros.",
        fontsize=7.3,
        fontname="helv",
        color=accent_rgb,
    )
    page.insert_text(
        (28, footer_y + 13),
        "Las muestras superiores tienen saturacion alta y K=0 para obligar a la impresora a inyectar solo Cian, Magenta y Amarillo.",
        fontsize=7.3,
        fontname="helv",
        color=accent_rgb,
    )

    pdf_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return pdf_bytes
