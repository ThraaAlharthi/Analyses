"""AOI analysis pipeline: KML -> fetch real imagery -> NDVI -> Arabic explanation -> saved DB row."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import psycopg2
import requests
from psycopg2.extras import Json

from compute_stats import compute_stats, describe_place
from fetch_imagery import fetch_aoi_bands
from kml_reader import read_aoi

DB = "dbname=omanlens"
AI_SERVICE_URL = "http://localhost:8000"  # serve_api.py, once running


def get_arabic_explanation(stats: dict) -> str | None:
    """Calls the fine-tuned model's serving API for the Arabic explanation.
    Returns None (not a fake string) if the service is unreachable, so a
    down AI service never silently produces fabricated Arabic text."""
    payload = {
        "area_name_ar": stats["areaName"],
        "date": stats["date"],
        "ndvi": stats["ndvi"],
        "vegetation_percent": stats["land_cover"]["vegetation_pct"],
    }
    try:
        resp = requests.post(
            f"{AI_SERVICE_URL}/analyze/vegetation", json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()["explanation_ar"]
    except requests.RequestException as e:
        print(f"WARNING: AI service unavailable ({e}); explanation not generated")
        return None


def run_pipeline(kml_path: str, user_id: int = 1, max_cloud: float = 5.0) -> int:
    """Read an AOI, fetch imagery for it, analyse, explain, store. Returns the row id."""

    # 1. WHERE -- the area of interest
    aoi = read_aoi.invoke({"kml_path": kml_path})
    print(f"AOI centre : {aoi['center']}  ({aoi['point_count']} boundary points)")

    # 2. IMAGERY
    Path("scenes").mkdir(exist_ok=True)
    stem = Path(kml_path).stem
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    raster_path = f"scenes/{stem}_{ts}.tif"
    scene = fetch_aoi_bands(kml_path, out_path=raster_path)

    # 3. ANALYSE
    stats = compute_stats(scene["path"])
    print(f"analysis   : {stats['areaName']}  NDVI mean {stats['ndvi']['mean']}")

    # 3b. EXPLAIN -- Arabic explanation from the fine-tuned model, via serve_api.py
    explanation_ar = get_arabic_explanation(stats)
    if explanation_ar:
        print(f"explanation: {explanation_ar[:60]}...")

    # 4. STORE
    location = describe_place(stats["latitude"], stats["longitude"])

    payload = dict(stats)
    payload["location"] = location
    payload["explanation_ar"] = explanation_ar
    payload["aoi"] = {
        "center": aoi["center"],
        "coordinates": aoi["coordinates"],
        "source_kml": kml_path,
    }
    payload["source"] = {
        "mission": "Sentinel-2 L2A",
        "scene_id": scene["scene_id"],
        "scene_date": scene["date"],
        "raster_path": scene["path"],
        "cloud_cover_pct": scene["cloud"],
        "max_cloud_allowed": max_cloud,
    }

    image_id = f"S2_{scene['date']}_{kml_path.rsplit('/', 1)[-1].replace('.kml', '')}"

    conn = psycopg2.connect(DB)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analyses
                  (user_id, image_id, area_name_ar, acquired_date,
                   ndvi_mean, ndvi_min, ndvi_max,
                   vegetation_pct, pixel_count, latitude, longitude, raw,
                   data_source)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    user_id, image_id, stats["areaName"], stats["date"],
                    stats["ndvi"]["mean"], stats["ndvi"]["min"], stats["ndvi"]["max"],
                    stats["land_cover"]["vegetation_pct"], stats["pixel_count"],
                    stats["latitude"], stats["longitude"], Json(payload),
                    "sentinel2_l2a",
                ),
            )
            new_id = cur.fetchone()[0]
    finally:
        conn.close()

    print(f"saved      : analyses row id={new_id}")
    return new_id


if __name__ == "__main__":
    row_id = run_pipeline("aoi.kml")
    print(f"\nreport: python3 -c \"from report_generator import generate_report; "
          f"print(generate_report({row_id}))\"")
