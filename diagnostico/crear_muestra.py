"""Crea un PDF de muestra simulando una cotización del ERP para pruebas."""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("samples/cotizacion_ejemplo.pdf", pagesize=A4)
styles = getSampleStyleSheet()
elements = []

elements.append(Paragraph("COTIZACION #001-2026", styles["Title"]))
elements.append(Spacer(1, 12))
elements.append(Paragraph("Cliente: Empresa Ejemplo SAS", styles["Normal"]))
elements.append(Paragraph("Fecha: 24/06/2026", styles["Normal"]))
elements.append(Spacer(1, 24))

data = [
    ["Cant.", "Descripcion", "V. Unitario", "Total"],
    ["2", "Laptop Gamer Pro X", "$2.500.000,00", "$5.000.000,00"],
    ["5", "Monitor 27 4K", "$850.000,00", "$4.250.000,00"],
    ["10", "Teclado Mecanico RGB", "$180.000,00", "$1.800.000,00"],
    ["3", "Mouse Inalambrico", "$120.000,00", "$360.000,00"],
    ["", "", "SUBTOTAL:", "$11.410.000,00"],
    ["", "", "DESCUENTO 5%:", "-$570.500,00"],
    ["", "", "TOTAL:", "$10.839.500,00"],
]

t = Table(data, colWidths=[50, 200, 100, 100])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, 0), 10),
    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 1), (-1, -1), 9),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f5e9")),
    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
]))
elements.append(t)
elements.append(Spacer(1, 24))
elements.append(Paragraph(
    "Observaciones: Entrega a 15 dias habiles. Forma de pago: 50% anticipo, 50% contra entrega.",
    styles["Normal"],
))
elements.append(Spacer(1, 12))
elements.append(Paragraph(
    "*Precios no incluyen IVA. IVA 19% sera liquidado en facturacion.",
    styles["Italic"],
))

doc.build(elements)
print("PDF de muestra creado en samples/cotizacion_ejemplo.pdf")
