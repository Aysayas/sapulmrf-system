"""Draws a Report as CSV or PDF. Both read the same structure the page shows."""

import csv
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reports.schemas import Report

ORG = "Barangay Sapul MRF"  # placeholder name


def to_csv(r: Report) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([ORG, r.title])
    w.writerow([r.subtitle])
    for label, value in r.summary:
        w.writerow([label, value])
    w.writerow([])
    w.writerow(r.columns)
    w.writerows(r.rows)
    return b"\xef\xbb\xbf" + out.getvalue().encode()  # BOM so Excel reads it as UTF-8


def to_pdf(r: Report, by: str, at: datetime) -> bytes:
    buf = io.BytesIO()
    wide = len(r.columns) > 5
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4) if wide else A4, title=f"{ORG} - {r.title}", author=by,
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm)
    st = getSampleStyleSheet()
    story = [
        Paragraph(f"{ORG}: {r.title}", st["Title"]),
        Paragraph(r.subtitle, st["Normal"]),
        Paragraph(f"Generated {at.strftime('%Y-%m-%d %H:%M')} by {by}", st["Normal"]),
        Spacer(1, 4 * mm),
        Paragraph("&nbsp;&nbsp;&nbsp;".join(f"<b>{k}:</b> {v}" for k, v in r.summary), st["Normal"]),
        Spacer(1, 5 * mm),
    ]
    money = [i for i, h in enumerate(r.columns) if "PHP" in h]  # pesos always show two decimals
    data = [r.columns] + [[f"{c:,.2f}" if i in money else str(c) for i, c in enumerate(row)] for row in r.rows] \
        if r.rows else [r.columns, ["No records in this range."]]
    table = Table(data, repeatRows=1)
    style = [("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
             ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black), ("GRID", (0, 1), (-1, -1), 0.25, colors.grey),
             ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i in range(len(r.columns)):  # numbers sit on the right
        if r.rows and isinstance(r.rows[0][i], (int, float)):
            style.append(("ALIGN", (i, 0), (i, -1), "RIGHT"))
    table.setStyle(TableStyle(style))
    story.append(table)

    def footer(canvas, d):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(d.pagesize[0] - 15 * mm, 10 * mm, f"Page {d.page}")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
