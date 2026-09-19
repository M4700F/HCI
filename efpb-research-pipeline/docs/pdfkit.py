"""Small shared helpers for the PDF generators in docs/ (styles, tables, csv/markdown readers). Needs reportlab."""
from __future__ import annotations

import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
W = A4[0] - 40 * mm
NAVY, GREY, GREEN, AMBER = colors.HexColor("#1f3a5f"), colors.HexColor("#f0f0f0"), colors.HexColor("#e6f2e6"), colors.HexColor("#fdf1d8")
ss = getSampleStyleSheet()
body = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica", fontSize=10, leading=14, spaceAfter=6)
small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#444444"))
title = ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=NAVY, alignment=0, spaceAfter=4)
sub = ParagraphStyle("sub", parent=body, fontSize=11, textColor=colors.HexColor("#555555"), spaceAfter=12)
h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=NAVY, spaceBefore=12, spaceAfter=5, keepWithNext=1)
h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.black, spaceBefore=8, spaceAfter=3, keepWithNext=1)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=14, bulletIndent=2, spaceAfter=3)
cell = ParagraphStyle("cell", parent=body, fontSize=8, leading=10, spaceAfter=0)
cellw = ParagraphStyle("cellw", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)


def load(path):
    with open(ROOT / path, newline="") as handle:
        return list(csv.DictReader(handle))


def fnum(value, digits=2):
    return ("%." + str(digits) + "f") % float(value)


def is_true(value):
    return value in (True, "True", "true")


def md_table(path, heading):
    """Rows (cell strings, header first) of the markdown table that follows `heading` in a text file."""
    lines = (ROOT / path).read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):
                rows.append(cells)
        elif rows:
            break
    return rows


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def C(text):
    return "<font name='Courier'>%s</font>" % esc(text)


def P(text, style=body):
    return Paragraph(text, style)


def B(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def table(rows, widths, highlight=None, markup=False):
    data = [[Paragraph(str(c) if markup else esc(c), cellw if i == 0 else cell) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    for i in range(1, len(rows)):
        if highlight and i in highlight:
            style.append(("BACKGROUND", (0, i), (-1, i), highlight[i]))
        elif i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), GREY))
    t.setStyle(TableStyle(style))
    return t


def picture(path, width=W):
    w, h = ImageReader(str(path)).getSize()
    return Image(str(path), width=width, height=width * h / float(w))


def build(story, out, name, footer_text):
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(20 * mm, 12 * mm, footer_text)
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, "Page %d" % doc.page)
        canvas.restoreState()
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm, title=name, author="Claude Code").build(story, onFirstPage=footer, onLaterPages=footer)
    print("wrote", out)
