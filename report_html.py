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

    loc = (data.get("raw") or {}).get("location") or {}
    loc_parts = [loc.get("place"), loc.get("governorate"), loc.get("country")]
    location_str = "، ".join(x for x in loc_parts if x)

    # NEW: the AI-generated Arabic explanation, if available
    explanation_ar = (data.get("raw") or {}).get("explanation_ar")
    explanation_block = (
        f'<div class="explanation"><p>{explanation_ar}</p></div>'
        if explanation_ar else ""
    )

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
  .explanation {{ margin-top: 22px; padding: 16px 18px;
                  background: rgba(255,255,255,0.03);
                  border-radius: 10px; font-size: 15px; line-height: 1.8; }}
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
    * {{ -webkit-print-color-adjust: exact !important;
         print-color-adjust: exact !important; }}
    body {{ background: #12203A !important; padding: 20px !important; }}
    .card {{ background: rgba(255,255,255,0.04) !important;
             border: 1px solid rgba(255,255,255,0.2) !important;
             max-width: 100% !important; padding: 20px !important; }}
    h1, td, .meta span, figcaption {{ color: #fff !important; }}
    td.label, .meta .k {{ color: #cdd9ea !important; }}
    .btnrow {{ display: none !important; }}
    .images {{ display: flex !important; }}
    .images.hidden {{ display: flex !important; }}
    figure img {{ width: 200px !important; }}
    table {{ page-break-inside: avoid; }}
  }}
</style></head>
<body>
  <div class="card">
    <h1>تقرير تحليل الغطاء النباتي</h1>
    <div class="sub">{region} · {date}</div>
    <div class="meta"><span class="k">الإحداثيات</span><span dir="ltr">{coords}</span></div>
    {location_line}
    <table>{table}</table>
    {explanation_block}
    {img_block}
  </div>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
