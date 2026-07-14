"""Arabic PDF report generator for an analysis.

Two layers, testable independently:
  render_report(data, out_path)  -- pure: dict in, PDF out, no database
  generate_report(analysis_id)   -- thin: reads the row, calls render_report

Arabic needs two transforms before it can be drawn in a PDF:
  arabic_reshaper : joins letters into their correct connected forms
  python-bidi     : reorders the text right-to-left
Without both, Arabic renders as disconnected, backwards glyphs.
"""
from __future__ import annotations

import psycopg2
from psycopg2.extras import RealDictCursor
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

DB = "dbname=omanlens"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

# Platform standard colours (RGB), from the standards doc.
FOREST = (44, 95, 45)     # #2C5F2D
INK = (29, 43, 32)        # #1D2B20


def ar(text: str) -> str:
    """Shape + reorder Arabic so it draws correctly in a PDF."""
    return get_display(arabic_reshaper.reshape(str(text)))


def cell_text(value) -> str:
    """ar() only if the value actually contains Arabic; numbers pass through."""
    s = str(value)
    if any("\u0600" <= ch <= "\u06FF" for ch in s):
        return ar(s)
    return s


def render_report(data: dict, out_path: str) -> str:
    """Pure renderer: analysis dict -> Arabic PDF at out_path. No database."""
    pdf = FPDF()
    pdf.add_page()
    # Register the Arabic-capable font once; reuse by name.
    pdf.add_font("arabic", "", FONT_PATH, uni=True)

    # --- title bar ---
    pdf.set_fill_color(*FOREST)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_font("arabic", size=20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(0, 8)
    pdf.cell(210, 12, ar("تقرير تحليل الغطاء النباتي"), align="C")

    pdf.ln(28)
    pdf.set_text_color(*INK)

    # --- body rows: (Arabic label, value) ---
    rows = [
        ("المنطقة", data["area_name_ar"]),
        ("تاريخ الصورة", str(data["acquired_date"])),
        ("متوسط المؤشر NDVI", f"{data['ndvi_mean']:.2f}"),
        ("أدنى قيمة", f"{data['ndvi_min']:.2f}"),
        ("أعلى قيمة", f"{data['ndvi_max']:.2f}"),
        ("نسبة الغطاء النباتي", f"{data['vegetation_pct']:.1f}%"),
        ("عدد البكسلات", str(data["pixel_count"])),
        ("خط العرض", f"{data['latitude']:.5f}"),
        ("خط الطول", f"{data['longitude']:.5f}"),
    ]

    pdf.set_font("arabic", size=13)
    for label, value in rows:
        # Label on the right (RTL), value on the left. Numbers stay 0-9.
        pdf.set_x(15)
        pdf.cell(90, 11, cell_text(value), border="B", align="L")
        pdf.cell(90, 11, ar(label), border="B", align="R")
        pdf.ln(11)

    pdf.output(out_path)
    return out_path


def generate_report(analysis_id: int, out_path: str | None = None) -> str:
    """Read one analyses row by id, render it to an Arabic PDF."""
    out_path = out_path or f"report_{analysis_id}.pdf"
    conn = psycopg2.connect(DB)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM analyses WHERE id = %s", (analysis_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise ValueError(f"No analysis with id {analysis_id}")

    return render_report(row, out_path)


if __name__ == "__main__":
    path = generate_report(4)   # row 4 from your table
    print(f"wrote {path}")
