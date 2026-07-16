#!/usr/bin/env python3
"""Export real analyses from Postgres as dataset inputs, ready for hand-writing.

Why this exists: the original 60 examples were generated from templates,
describing numbers that were never measured. A model fine-tuned on that
learns the template. These inputs come from real Sentinel-2 analyses, so
the Arabic written against them describes real ground.

Usage:
    python3 scripts/export_for_writing.py > data/to_write.jsonl

Then open data/to_write.jsonl and fill in each empty "output" field in your
own Arabic. Vary the phrasing deliberately -- if every example opens the same
way, the model learns the opening, not the reasoning.
"""
import json
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

DB = "dbname=omanlens"

# Vary the instruction too. A model that only ever sees one phrasing of the
# request will not generalise to how a real user asks.
INSTRUCTIONS = [
    "حلّل نتائج مؤشر NDVI التالية وقدّم ملخصًا موجزًا.",
    "اشرح للمزارع ما تعنيه هذه القراءات عن أرضه.",
    "هل تدل هذه القراءات على غطاء نباتي صحي؟ وضّح إجابتك.",
    "لخّص حالة الغطاء النباتي في هذه المنطقة.",
    "قدّم تقريرًا موجزًا عن نتائج التحليل الطيفي لهذه الصورة.",
]


def fetch_real_rows():
    conn = psycopg2.connect(DB)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT area_name_ar, acquired_date, ndvi_mean, ndvi_min,
                       ndvi_max, vegetation_pct, pixel_count,
                       latitude, longitude
                  FROM analyses
                 WHERE data_source = 'sentinel2_l2a'
                 ORDER BY id
            """)
            return cur.fetchall()
    finally:
        conn.close()


def main():
    rows = fetch_real_rows()

    seen, unique = set(), []
    for r in rows:
        key = (r["area_name_ar"], str(r["acquired_date"]),
               float(r["ndvi_mean"]), r["pixel_count"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    if len(unique) < len(rows):
        print(f"# deduped {len(rows) - len(unique)} identical analyses",
              file=sys.stderr)
    rows = unique

    if not rows:
        sys.exit("No sentinel2_l2a rows found. Run pipeline.py on a real AOI first.")

    for i, row in enumerate(rows):
        payload = {
            "area_name_ar": row["area_name_ar"],
            "date": str(row["acquired_date"]),
            "ndvi": {
                "mean": round(float(row["ndvi_mean"]), 4),
                "min": round(float(row["ndvi_min"]), 4),
                "max": round(float(row["ndvi_max"]), 4),
            },
            "vegetation_percent": round(float(row["vegetation_pct"]), 2),
            "pixel_count": row["pixel_count"],
            "latitude": round(float(row["latitude"]), 6),
            "longitude": round(float(row["longitude"]), 6),
        }
        record = {
            "instruction": INSTRUCTIONS[i % len(INSTRUCTIONS)],
            "input": json.dumps(payload, ensure_ascii=False),
            "output": "",                    # <- you write this
            "category": "single_date",       # standards doc 2.7
        }
        print(json.dumps(record, ensure_ascii=False))

    print(f"\n# {len(rows)} real analyses exported. Fill in each empty output.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
