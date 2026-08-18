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




def _draw_right_fit(pdf, text, x, y, max_width, font_name="Helvetica-Bold", start_size=8.5, min_size=5.2):
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
    pdf.setStrokeColor(border_color)
    pdf.setLineWidth(1.5)
    pdf.roundRect(x - 3, y - 3, size + 6, size + 6, 5, stroke=1, fill=0)
    renderPDF.draw(drawing, pdf, x, y)


def generar_comprobante_devoto(stream, devoto, qr_url):
    """Genera un comprobante A4 inspirado en el ejemplo aportado por el usuario."""
    h = devoto.hermandad
    primary = _hex_color(h.color_primario, "#111111")
    accent = _hex_color(h.color_acento, "#d4af37")
    dark = colors.HexColor("#111111")
    dark_2 = colors.HexColor("#1a1a1a")
    text_gray = colors.HexColor("#4a4a4a")
    light_gray = colors.HexColor("#ededed")
    green_bg = colors.HexColor("#dff3e3")
    green = colors.HexColor("#18883b")

    pdf = canvas.Canvas(stream, pagesize=A4)
    page_w, page_h = A4
    left = 18 * mm
    right = page_w - 18 * mm
    content_w = right - left

    # Línea superior institucional.
    pdf.setFillColor(accent)
    pdf.rect(left, page_h - 14 * mm, content_w, 1.5 * mm, stroke=0, fill=1)

    # Logo y nombre.
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

    pdf.setFillColor(dark)
    org_x = logo_x + logo_size + 6 * mm
    org_lines = textwrap.wrap(h.nombre, width=43)[:2] or [h.nombre]
    org_font = 12 if len(org_lines) == 1 else 9.5
    pdf.setFont("Helvetica-Bold", org_font)
    org_y = page_h - 27 * mm
    for line in org_lines:
        pdf.drawString(org_x, org_y, line)
        org_y -= 4.8 * mm
    city_y = min(page_h - 36 * mm, org_y - 1 * mm)
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 7.2)
    pdf.drawString(org_x, city_y, (h.ciudad or "LA ANTIGUA GUATEMALA").upper())

    pdf.setFillColor(text_gray)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawRightString(right, page_h - 25 * mm, "COMPROBANTE DE")
    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(right, page_h - 32 * mm, "Registro de Devoto")

    # Franja principal de identificación.
    band_top = page_h - 50 * mm
    band_h = 32 * mm
    pdf.setFillColor(dark)
    pdf.rect(left, band_top - band_h, content_w, band_h, stroke=0, fill=1)
    pdf.setFillColor(accent)
    pdf.rect(left, band_top - band_h, 1.5 * mm, 10 * mm, stroke=0, fill=1)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(left + 10 * mm, band_top - 8 * mm, "I D E N T I F I C A C I O N")
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(left + 10 * mm, band_top - 14 * mm, "DEVOTO")
    pdf.setFillColor(colors.HexColor("#d6d6d6"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(left + 10 * mm, band_top - 20 * mm, "Registro completado")

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 23)
    pdf.drawRightString(right - 8 * mm, band_top - 14 * mm, devoto.dpi)
    pdf.setFillColor(colors.HexColor("#d6d6d6"))
    pdf.setFont("Helvetica", 6.5)
    pdf.drawRightString(right - 8 * mm, band_top - 20 * mm, "C U I / D P I")

    name_strip_y = band_top - band_h
    pdf.setFillColor(dark_2)
    pdf.rect(left, name_strip_y, content_w, 11 * mm, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(left + 11 * mm, name_strip_y + 3.8 * mm, devoto.nombre_completo.upper()[:58])

    # Mensaje de confirmación.
    y = name_strip_y - 8 * mm
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(1.1)
    pdf.line(left + 10 * mm, y + 4 * mm, left + 10 * mm, y - 7 * mm)
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
        "<b>Conserve este comprobante en formato digital o impreso</b> como respaldo de su registro."
    )
    used = _paragraph(pdf, msg, left + 14 * mm, y + 3 * mm, 112 * mm, body_style)
    y -= max(used, 10 * mm) + 6 * mm

    # Datos y QR.
    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 7.3)
    pdf.drawString(left + 10 * mm, y, "D A T O S  D E L  D E V O T O")
    pdf.setStrokeColor(accent)
    pdf.setLineWidth(.8)
    pdf.line(left + 10 * mm, y - 3 * mm, left + 116 * mm, y - 3 * mm)

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
        ("NOMBRES", " ".join(filter(None, [devoto.primer_nombre, devoto.otros_nombres]))),
        ("APELLIDOS", " ".join(filter(None, [devoto.primer_apellido, devoto.otros_apellidos]))),
        ("FECHA NAC.", devoto.fecha_nacimiento.strftime("%d/%m/%Y")),
        ("UBICACION", f"{devoto.municipio}, {devoto.departamento}"),
        ("MEDIDA HOMBRO", medida_text),
    ]
    for index, (label, value) in enumerate(rows):
        row_y = table_y - index * row_h
        pdf.setFillColor(light_gray)
        pdf.rect(table_x, row_y - row_h + 1, label_w, row_h - 1, stroke=0, fill=1)
        pdf.setFillColor(text_gray)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(table_x + 3 * mm, row_y - 4.9 * mm, label)
        pdf.setFillColor(dark)
        pdf.setFont("Helvetica-Bold", 7.3)
        safe_value = (value or "-")[:46]
        pdf.drawString(table_x + label_w + 3 * mm, row_y - 4.9 * mm, safe_value)
        pdf.setStrokeColor(colors.HexColor("#cccccc"))
        pdf.setLineWidth(.35)
        pdf.line(table_x, row_y - row_h + 1, table_x + label_w + value_w, row_y - row_h + 1)

    qr_size = 31 * mm
    qr_x = right - qr_size - 13 * mm
    qr_y = table_y - 42 * mm
    _draw_qr(pdf, qr_url, qr_x, qr_y, qr_size, accent)
    pdf.setFillColor(text_gray)
    pdf.setFont("Helvetica-Bold", 6)
    pdf.drawCentredString(qr_x + qr_size / 2, qr_y - 6 * mm, "CODIGO QR DEL COMPROBANTE")

    y = table_y - len(rows) * row_h - 8 * mm

    # Aviso importante.
    notice_h = 17 * mm
    pdf.setFillColor(green_bg)
    pdf.setStrokeColor(green)
    pdf.setLineWidth(.8)
    pdf.rect(left + 10 * mm, y - notice_h, content_w - 20 * mm, notice_h, stroke=1, fill=1)
    pdf.setFillColor(green)
    pdf.rect(left + 13 * mm, y - 8 * mm, 25 * mm, 6 * mm, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 6.8)
    pdf.drawCentredString(left + 25.5 * mm, y - 6 * mm, "IMPORTANTE")
    pdf.setFillColor(colors.HexColor("#1f6331"))
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(left + 13 * mm, y - 13 * mm, "Asegure que el codigo QR permanezca visible y conserve este documento como respaldo.")

    y -= notice_h + 7 * mm
    pdf.setFillColor(dark)
    pdf.setFont("Helvetica-Bold", 7.3)
    pdf.drawString(left + 10 * mm, y, "N O T A S  I M P O R T A N T E S")
    pdf.setStrokeColor(accent)
    pdf.line(left + 10 * mm, y - 2 * mm, right - 10 * mm, y - 2 * mm)

    note_style = ParagraphStyle(
        "receipt-note",
        fontName="Helvetica",
        fontSize=7.3,
        leading=10,
        textColor=text_gray,
        leftIndent=0,
    )
    notes = [
        "1. Este comprobante confirma el registro de datos del devoto en la organizacion indicada.",
        "2. El comprobante <b>no equivale a una reserva de turno</b> ni garantiza participacion en una actividad especifica.",
        "3. La hermandad o cofradia puede solicitar su documento de identificacion para validar los datos registrados.",
        "4. Puede volver a abrir este PDF utilizando el enlace contenido en el codigo QR mientras el comprobante siga vigente.",
    ]
    y -= 7 * mm
    for note in notes:
        height = _paragraph(pdf, note, left + 13 * mm, y, content_w - 26 * mm, note_style)
        y -= height + 3 * mm

    # Pie institucional.
    footer_y = 15 * mm
    pdf.setFillColor(dark)
    pdf.rect(left, footer_y, content_w, 17 * mm, stroke=0, fill=1)
    pdf.setFillColor(accent)
    pdf.rect(left, footer_y + 17 * mm, content_w, 1.2 * mm, stroke=0, fill=1)
    pdf.setFillColor(accent)
    _draw_right_fit(
        pdf,
        h.nombre,
        right - 3 * mm,
        footer_y + 10 * mm,
        content_w - 18 * mm,
        start_size=8.5,
        min_size=5.2,
    )
    pdf.setFillColor(colors.HexColor("#c7c7c7"))
    pdf.setFont("Helvetica", 5.5)
    pdf.drawRightString(right - 3 * mm, footer_y + 5 * mm, "TRADICION VIVA - SISTEMA DE GESTION PROCESIONAL")

    pdf.setTitle(f"Comprobante de registro - {devoto.nombre_completo}")
    pdf.setAuthor("TRADICION VIVA")
    pdf.showPage()
    pdf.save()
