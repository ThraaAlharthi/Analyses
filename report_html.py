"""HTML report generator — modern, self-contained, real buttons.

Why HTML instead of PDF: PDF can't do working buttons or reliable gradients,
and PDF-to-PDF links break. HTML does all three natively. Images are embedded
as base64 so the report is ONE self-contained file — nothing to lose or link.

Two layers, same as the PDF version:
  render_html(data, out_path)  -- pure: dict in, HTML out
  generate_html_report(id)     -- reads the row, calls render_html
"""
from __future__ import annotations

import base64
import os

import psycopg2
from psycopg2.extras import RealDictCursor

DB = "dbname=omanlens"


def _png_data_uri(path):
    """Read a PNG and return a base64 data URI, or None if missing."""
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _png_paths(data):
    raw = data.get("raw") or {}
    src = raw.get("source") or {}
    raster = src.get("raster_path")
    if not raster:
        return None, None
    base = raster.rsplit(".", 1)[0]
    return f"{base}_truecolor.png", f"{base}_ndvi.png"


def render_html(data: dict, out_path: str) -> str:
    tc_path, nd_path = _png_paths(data)
    tc = _png_data_uri(tc_path)
    nd = _png_data_uri(nd_path)

    rows = [
        ("متوسط المؤشر NDVI", f"{data['ndvi_mean']:.2f}"),
        ("أدنى قيمة", f"{data['ndvi_min']:.2f}"),
        ("أعلى قيمة", f"{data['ndvi_max']:.2f}"),
        ("نسبة الغطاء النباتي", f"{data['vegetation_pct']:.1f}%"),
        ("عدد البكسلات", str(data["pixel_count"])),
    ]
    table = "".join(
        f'<tr><td class="label">{lbl}</td><td class="val">{val}</td></tr>'
        for lbl, val in rows
    )

    coords = f"{data['latitude']:.5f}, {data['longitude']:.5f}"
    region = data["area_name_ar"]
    date = str(data["acquired_date"])

    # structured location from stored geocoding (place, governorate, country)
    loc = (data.get("raw") or {}).get("location") or {}
    loc_parts = [loc.get("place"), loc.get("governorate"), loc.get("country")]
    location_str = "، ".join(x for x in loc_parts if x)   # skip empties

    # image section: only if we have them
    img_block = ""
    if tc or nd:
        imgs = ""
        if tc:
            imgs += f'<figure><figcaption>صورة حقيقية</figcaption><img src="{tc}"></figure>'
        if nd:
            imgs += f'<figure><figcaption>خريطة مؤشر NDVI — أخضر: نبات، أحمر: جرداء</figcaption><img src="{nd}"></figure>'
        img_block = f'''
        <div id="images" class="images hidden">{imgs}</div>
        <div class="btnrow">
          <button onclick="document.getElementById('images').classList.toggle('hidden')">
            عرض / إخفاء الصور
          </button>
          <button onclick="window.print()">تحميل التقرير PDF</button>
        </div>'''
    else:
        img_block = '''
        <div class="btnrow">
          <button onclick="window.print()">تحميل التقرير PDF</button>
        </div>'''

    location_line = (
        f'<div class="meta"><span class="k">الموقع</span>'
        f'<span>{location_str}</span></div>'
    ) if location_str else ""

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>تقرير تحليل الغطاء النباتي</title>
<style>
  body {{
    margin: 0; padding: 40px;
    font-family: -apple-system, "SF Arabic", "Segoe UI", sans-serif;
    background: linear-gradient(160deg, #12203A 0%, #28143 7 100%);
    background: linear-gradient(160deg, #12203A 0%, #281437 100%);
    color: #fff; min-height: 100vh;
  }}
  .card {{
    max-width: 640px; margin: 0 auto;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px; padding: 32px 36px;
    backdrop-filter: blur(6px);
  }}
  h1 {{ text-align: center; font-weight: 600; font-size: 26px; margin: 0 0 6px; }}
  .sub {{ text-align: center; color: #9fb3d0; font-size: 13px;
          margin-bottom: 24px; border-bottom: 1px solid rgba(255,255,255,0.12);
          padding-bottom: 20px; }}
  .meta {{ display: flex; justify-content: space-between;
           font-size: 15px; margin: 10px 0; }}
  .meta .k {{ color: #9fb3d0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
  td {{ padding: 14px 4px; border-bottom: 1px solid rgba(255,255,255,0.10);
        font-size: 16px; }}
  td.val {{ text-align: left; direction: ltr; font-variant-numeric: tabular-nums; }}
  td.label {{ color: #cdd9ea; }}
  .btnrow {{ display: flex; gap: 12px; justify-content: center; margin-top: 28px; }}
  button {{
    background: #ffffff; color: #12203A; border: none;
    padding: 12px 22px; border-radius: 10px; font-size: 15px;
    font-family: inherit; cursor: pointer; font-weight: 600;
  }}
  button:hover {{ background: #dbe7f7; }}
  .images {{ display: flex; flex-wrap: wrap; gap: 16px;
             justify-content: center; margin-top: 24px; }}
  .images.hidden {{ display: none; }}
  figure {{ margin: 0; text-align: center; }}
  figure img {{ width: 260px; border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.2); }}
  figcaption {{ font-size: 13px; color: #9fb3d0; margin-bottom: 8px; }}
  @media print {{
    body {{ background: #12203A !important;
            -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .btnrow {{ display: none; }}
    .images.hidden {{ display: flex !important; }}
  }}
</style></head>
<body>
  <div class="card">
    <h1>تقرير تحليل الغطاء النباتي</h1>
    <div class="sub">{region} · {date}</div>
    <div class="meta"><span class="k">الإحداثيات</span><span dir="ltr">{coords}</span></div>
    {location_line}
    <table>{table}</table>
    {img_block}
  </div>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def generate_html_report(analysis_id: int, out_path: str | None = None) -> str:
    out_path = out_path or f"report_{analysis_id}.html"
    conn = psycopg2.connect(DB)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM analyses WHERE id = %s", (analysis_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"No analysis with id {analysis_id}")
    return render_html(row, out_path)


if __name__ == "__main__":
    import sys
    aid = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    path = generate_html_report(aid)
    print(f"wrote {path}")
