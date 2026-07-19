"""Render the training dataset as an Arabic PDF via HTML.

HTML handles variable-length text natively -- no manual card-height math,
which is what broke the fpdf2 version. wkhtmltopdf isn't installed, so we
render with the browser: write HTML, open it, print to PDF from there.
Simpler and it just works for RTL + wrapping.
"""
import json
import webbrowser
from pathlib import Path

examples = [json.loads(l) for l in open("data/to_write.jsonl", encoding="utf-8") if l.strip()]

cards = ""
for ex in examples:
    d = json.loads(ex["input"])

    if ex.get("category") == "comparison":
        obs = d["observations"]
        rows = " &nbsp;&rarr;&nbsp; ".join(
            f"{o['date']}: NDVI {o['ndvi_mean']}, veg {o['vegetation_percent']}%"
            for o in obs
        )
        nums = (f"{rows} &nbsp;|&nbsp; change: NDVI {d['delta_ndvi_mean']}, "
                f"veg {d['delta_vegetation_percent']} pts")
        head = f"{d['area_name_ar']} &nbsp;(مقارنة)"
        badge = "comparison"
    elif ex.get("category") == "refusal":
        bits = []
        if "cloud_cover_percent" in d:
            bits.append(f"cloud {d['cloud_cover_percent']}%")
        if "valid_pixel_ratio" in d:
            bits.append(f"valid pixels {d['valid_pixel_ratio']}")
        nums = " &nbsp;|&nbsp; ".join(bits) or "unanalysable input"
        head = f"{d.get('area_name_ar', '?')} &nbsp;({d.get('date', '')})"
        badge = "refusal"
    else:
        n = d["ndvi"]
        nums = (f"NDVI mean {n['mean']} &nbsp; min {n['min']} &nbsp; max {n['max']}"
                f" &nbsp;|&nbsp; veg {d['vegetation_percent']}% &nbsp; {d['pixel_count']:,} px")
        head = f"{d['area_name_ar']} &nbsp;({d['date']})"
        badge = "single date"

    cards += f"""
    <div class="card">
      <div class="head">{head} <span class="badge">{badge}</span></div>
      <div class="nums" dir="ltr">{nums}</div>
      <div class="out">{ex['output']}</div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<style>
  body {{ font-family: "Arial", sans-serif; margin: 40px; color: #1d2b20; }}
  .banner {{ background:#2c5f2d; color:#fff; padding:22px; border-radius:8px;
             text-align:center; margin-bottom:28px; }}
  .banner h1 {{ margin:0; font-size:24px; }}
  .banner p  {{ margin:6px 0 0; font-size:13px; opacity:.9; }}
  .card {{ background:#f0f4f0; border-right:5px solid #5e813e;
           border-radius:6px; padding:16px 20px; margin-bottom:16px; }}
  .head {{ color:#2c5f2d; font-size:16px; font-weight:bold; margin-bottom:8px; }}
  .nums {{ color:#333; font-size:12px; font-family:monospace;
           background:#fff; padding:6px 10px; border-radius:4px;
           margin-bottom:10px; display:inline-block; }}
  .out  {{ font-size:15px; line-height:1.9; }}
  .badge {{ font-size:10px; background:#5e813e; color:#fff; padding:2px 8px;
           border-radius:10px; font-family:sans-serif; margin-right:8px; }}
  .card:has(.badge:only-child) {{ }}
  @media print {{ .card {{ break-inside: avoid; }} }}
</style></head><body>
  <div class="banner"><h1>مجموعة بيانات التدريب</h1>
    <p>تحليلات حقيقية من القمر الصناعي — النصوص بخط اليد — {len(examples)} أمثلة</p></div>
  {cards}
</body></html>"""

out = Path("dataset_showcase.html").resolve()
out.write_text(html, encoding="utf-8")
print(f"wrote {out}")
print("opening in browser -> then File > Print > Save as PDF")
webbrowser.open(f"file://{out}")
