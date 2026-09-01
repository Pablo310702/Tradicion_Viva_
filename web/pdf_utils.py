from pathlib import Path
import textwrap

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


def _hex_color(value, fallback):
    try:
        return colors.HexColor(value or fallback)
    except (TypeError, ValueError):
        return colors.HexColor(fallback)


def _paragraph(pdf, text, x, y_top, width, style):
    paragraph = Paragraph(text, style)
    _, height = paragraph.wrap(width, 100 * mm)
    paragraph.drawOn(pdf, x, y_top - height)
    return height


def _draw_right_fit(
    pdf,
    text,
    x,
    y,
    max_width,
    font_name="Helvetica-Bold",
    start_size=8.5,
    min_size=5.2,
):
    size = start_size
    while size > min_size and pdf.stringWidth(text, font_name, size) > max_width:
        size -= 0.4

    if pdf.stringWidth(text, font_name, size) > max_width:
        while text and pdf.stringWidth(text + "...", font_name, size) > max_width:
            text = text[:-1]
        text = text.rstrip() + "..."

    pdf.setFont(font_name, size)
    pdf.drawRightString(x, y, text)


def _draw_qr(pdf, data, x, y, size, border_color):
    qr = QrCodeWidget(data)
    x1, y1, x2, y2 = qr.getBounds()
    width = x2 - x1
    height = y2 - y1

    drawing = Drawing(
        size,
        size,
        transform=[size / width, 0, 0, size / height, 0, 0],
    )
    drawing.add(qr)

    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(border_color)
    pdf.setLineWidth(1.25)
    pdf.roundRect(
        x - 3,
        y - 3,
        size + 6,
        size + 6,
        5,
        stroke=1,
        fill=1,
    )
    renderPDF.draw(drawing, pdf, x, y)


def generar_comprobante_devoto(stream, devoto, qr_url):
    """Genera el comprobante A4 de registro de devoto para TRADICIÓN VIVA."""

    h = devoto.hermandad
    accent = _hex_color(h.color_acento, "#d4af37")

    dark = colors.HexColor("#171717")
    text_gray = colors.HexColor("#4a4a4a")
    soft_gray = colors.HexColor("#f3f3f3")
    line_gray = colors.HexColor("#d7d7d7")
    pale_accent = colors.Color(
        min(1, accent.red + (1 - accent.red) * 0.88),
        min(1, accent.green + (1 - accent.green) * 0.88),
        min(1, accent.blue + (1 - accent.blue) * 0.88),
    )

    pdf = canvas.Canvas(stream, pagesize=A4)
    page_w, page_h = A4

    left = 18 * mm
    right = page_w - 18 * mm
    content_w = right - left

    # =========================================================
    # ENCABEZADO
    # =========================================================

    pdf.setFillColor(accent)
    pdf.rect(left, page_h - 14 * mm, content_w, 1.5 * mm, stroke=0, fill=1)

    logo_x = left + 2 * mm
    logo_y = page_h - 42 * mm
    logo_size = 18 * mm

    if h.logo:
        try:
            logo_path = Path(h.logo.path)
            if logo_path.exists():
                pdf.drawImage(
                    str(logo_path),
                    logo_x,
                    logo_y,
                    width=logo_size,
                    height=logo_size,
                    preserveAspectRatio=True,
                    anchor="c",
                    mask="auto",
                )
        except Exception:
            pass

    org_x = logo_x + logo_size + 6 * mm
    org_lines = textwrap.wrap(h.nombre, width=43)[:2] or [h.nombre]
    org_font = 12 if len(org_lines) == 1 else 9.5

    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", org_font)

    org_y = page_h - 27 * mm
    for line in org_lines:
        pdf.drawString(org_x, org_y, line)
        org_y -= 4.8 * mm

    city_y = min(page_h - 36 * mm, org_y - 1 * mm)
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 7.2)
    pdf.drawString(
        org_x,
        city_y,
        (h.ciudad or "LA ANTIGUA GUATEMALA").upper(),
    )

    pdf.setFillColor(text_gray)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawRightString(
        right,
        page_h - 25 * mm,
        "COMPROBANTE DE",
    )

    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(
        right,
        page_h - 32 * mm,
        "Registro de Devoto",
    )

    # =========================================================
    # IDENTIFICACIÓN - SIN FRANJAS NEGRAS
    # =========================================================

    card_top = page_h - 49 * mm
    card_h = 31 * mm
    card_bottom = card_top - card_h

    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(line_gray)
    pdf.setLineWidth(0.8)
    pdf.roundRect(
        left,
        card_bottom,
        content_w,
        card_h,
        6,
        stroke=1,
        fill=1,
    )

    pdf.setFillColor(accent)
    pdf.rect(
        left,
        card_bottom,
        1.5 * mm,
        card_h,
        stroke=0,
        fill=1,
    )

    pdf.setFillColor(text_gray)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(
        left + 10 * mm,
        card_top - 8 * mm,
        "IDENTIFICACIÓN DEL DEVOTO",
    )

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(
        left + 10 * mm,
        card_top - 14 * mm,
        "REGISTRO CONFIRMADO",
    )

    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 21)
    pdf.drawRightString(
        right - 8 * mm,
        card_top - 14 * mm,
        devoto.dpi,
    )

    pdf.setFillColor(text_gray)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawRightString(
        right - 8 * mm,
        card_top - 20 * mm,
        "CUI / DPI",
    )

    pdf.setStrokeColor(line_gray)
    pdf.setLineWidth(0.5)
    pdf.line(
        left + 10 * mm,
        card_bottom + 10 * mm,
        right - 10 * mm,
        card_bottom + 10 * mm,
    )

    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 12.5)
    pdf.drawString(
        left + 10 * mm,
        card_bottom + 4.2 * mm,
        devoto.nombre_completo.upper()[:58],
    )

    # =========================================================
    # MENSAJE
    # =========================================================

    y = card_bottom - 8 * mm

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1.1)
    pdf.line(
        left + 10 * mm,
        y + 4 * mm,
        left + 10 * mm,
        y - 7 * mm,
    )

    body_style = ParagraphStyle(
        "receipt-body",
        fontName="Helvetica",
        fontSize=8.2,
        leading=11,
        textColor=text_gray,
        alignment=TA_LEFT,
    )

    msg = (
        "El registro de datos ha sido completado correctamente. "
        "<b>Conserve este comprobante en formato digital o impreso</b> "
        "como respaldo de su registro."
    )

    used = _paragraph(
        pdf,
        msg,
        left + 14 * mm,
        y + 3 * mm,
        112 * mm,
        body_style,
    )
    y -= max(used, 10 * mm) + 6 * mm

    # =========================================================
    # DATOS DEL DEVOTO + QR
    # =========================================================

    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 7.3)
    pdf.drawString(
        left + 10 * mm,
        y,
        "DATOS DEL DEVOTO",
    )

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(0.8)
    pdf.line(
        left + 10 * mm,
        y - 3 * mm,
        left + 116 * mm,
        y - 3 * mm,
    )

    table_x = left + 10 * mm
    table_y = y - 10 * mm
    label_w = 37 * mm
    value_w = 70 * mm
    row_h = 7.5 * mm

    medida_text = "No registrada"
    if devoto.medida_hombro_cm is not None:
        cm_value = float(devoto.medida_hombro_cm)
        medida_text = f"{cm_value / 100:.2f} m ({cm_value:.1f} cm)"

    rows = [
        ("CUI", devoto.dpi),
        (
            "NOMBRES",
            " ".join(
                filter(
                    None,
                    [
                        devoto.primer_nombre,
                        devoto.otros_nombres,
                    ],
                )
            ),
        ),
        (
            "APELLIDOS",
            " ".join(
                filter(
                    None,
                    [
                        devoto.primer_apellido,
                        devoto.otros_apellidos,
                    ],
                )
            ),
        ),
        (
            "FECHA NAC.",
            devoto.fecha_nacimiento.strftime("%d/%m/%Y"),
        ),
        (
            "UBICACIÓN",
            f"{devoto.municipio}, {devoto.departamento}",
        ),
    ]

    if devoto.hermandad.es_hermandad:
        rows.append(("MEDIDA HOMBRO", medida_text))

    for index, (label, value) in enumerate(rows):
        row_y = table_y - index * row_h

        pdf.setFillColor(soft_gray)
        pdf.rect(
            table_x,
            row_y - row_h + 1,
            label_w,
            row_h - 1,
            stroke=0,
            fill=1,
        )

        pdf.setFillColor(text_gray)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(
            table_x + 3 * mm,
            row_y - 4.9 * mm,
            label,
        )

        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 7.3)

        safe_value = (value or "-")[:46]
        pdf.drawString(
            table_x + label_w + 3 * mm,
            row_y - 4.9 * mm,
            safe_value,
        )

        pdf.setStrokeColor(line_gray)
        pdf.setLineWidth(0.35)
        pdf.line(
            table_x,
            row_y - row_h + 1,
            table_x + label_w + value_w,
            row_y - row_h + 1,
        )

    qr_size = 31 * mm
    qr_x = right - qr_size - 13 * mm
    qr_y = table_y - 42 * mm

    _draw_qr(
        pdf,
        qr_url,
        qr_x,
        qr_y,
        qr_size,
        accent,
    )

    pdf.setFillColor(text_gray)
    pdf.setFont("Helvetica-Bold", 6)
    pdf.drawCentredString(
        qr_x + qr_size / 2,
        qr_y - 6 * mm,
        "ACCESO A LA ORGANIZACIÓN",
    )

    y = table_y - len(rows) * row_h - 8 * mm

    # =========================================================
    # INFORMACIÓN DEL QR
    # =========================================================

    notice_h = 18 * mm

    pdf.setFillColor(pale_accent)
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(0.8)

    pdf.roundRect(
        left + 10 * mm,
        y - notice_h,
        content_w - 20 * mm,
        notice_h,
        4,
        stroke=1,
        fill=1,
    )

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 7.2)
    pdf.drawString(
        left + 14 * mm,
        y - 6 * mm,
        "CÓDIGO QR",
    )

    qr_notice_style = ParagraphStyle(
        "qr-notice",
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.5,
        textColor=text_gray,
        alignment=TA_LEFT,
    )

    _paragraph(
        pdf,
        (
            "El código QR está asociado de forma única a este registro. "
            "Al escanearlo desde un dispositivo público, abrirá la página "
            "de la hermandad o cofradía correspondiente."
        ),
        left + 14 * mm,
        y - 9 * mm,
        content_w - 28 * mm,
        qr_notice_style,
    )

    # =========================================================
    # INDICACIONES PARA EL DEVOTO
    # =========================================================

    y -= notice_h + 8 * mm

    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(
        left + 10 * mm,
        y,
        "INDICACIONES PARA EL DEVOTO",
    )

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(0.8)
    pdf.line(
        left + 10 * mm,
        y - 2 * mm,
        right - 10 * mm,
        y - 2 * mm,
    )

    note_style = ParagraphStyle(
        "receipt-note",
        fontName="Helvetica",
        fontSize=7.3,
        leading=10,
        textColor=text_gray,
        leftIndent=0,
    )

    notes = [
        (
            "1. Este comprobante confirma el registro de datos del devoto "
            "en la organización indicada."
        ),
        (
            "2. Conserve el comprobante y presente el código QR cuando "
            "la hermandad o cofradía lo solicite."
        ),
        (
            "3. La organización puede solicitar un documento de identificación "
            "para verificar los datos registrados."
        ),
        (
            "4. El código QR identifica este registro mediante un código seguro; "
            "el DPI no se utiliza como identificador público dentro de la URL."
        ),
    ]

    y -= 7 * mm

    for note in notes:
        height = _paragraph(
            pdf,
            note,
            left + 13 * mm,
            y,
            content_w - 26 * mm,
            note_style,
        )
        y -= height + 3 * mm

    # =========================================================
    # PIE LIMPIO - SIN FRANJA NEGRA
    # =========================================================

    footer_y = 16 * mm

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1.2)
    pdf.line(
        left,
        footer_y + 10 * mm,
        right,
        footer_y + 10 * mm,
    )

    pdf.setFillColor(accent)
    _draw_right_fit(
        pdf,
        h.nombre,
        right,
        footer_y + 5.5 * mm,
        content_w - 25 * mm,
        start_size=8.2,
        min_size=5.2,
    )

    pdf.setFillColor(text_gray)
    pdf.setFont("Helvetica", 5.7)
    pdf.drawString(
        left,
        footer_y + 5.5 * mm,
        "TRADICIÓN VIVA · SISTEMA DE GESTIÓN PROCESIONAL",
    )

    pdf.setTitle(
        f"Comprobante de registro - {devoto.nombre_completo}"
    )
    pdf.setAuthor("TRADICIÓN VIVA")
    pdf.showPage()
    pdf.save()
