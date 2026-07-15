"""AOI analysis pipeline: KML -> fetch real imagery -> NDVI -> saved DB row.

Wires together four pieces, each built and verified separately:
  kml_reader.read_aoi   : where the user wants analysed
  fetch_imagery         : real Sentinel-2 B04+B08 clipped to that AOI
  compute_stats         : NDVI, computed locally in rasterio+numpy
  Postgres analyses      : durable storage

No stand-in raster. The imagery is fetched for the AOI itself, so the
area name and the boundary finally describe the same ground.
"""
from __future__ import annotations

import psycopg2
from psycopg2.extras import Json

from compute_stats import compute_stats
from fetch_imagery import fetch_aoi_bands
from kml_reader import read_aoi

DB = "dbname=omanlens"


def run_pipeline(kml_path: str, user_id: int = 1, max_cloud: float = 5.0) -> int:
    """Read an AOI, fetch imagery for it, analyse, store. Returns the row id."""

    # 1. WHERE -- the area of interest
    aoi = read_aoi.invoke({"kml_path": kml_path})
    print(f"AOI centre : {aoi['center']}  ({aoi['point_count']} boundary points)")

    # 2. IMAGERY -- fetch the clearest recent scene covering that AOI
    scene = fetch_aoi_bands(kml_path)

    # 3. ANALYSE -- our own band math. compute_stats reads the acquisition
    #    date from the GeoTIFF tag fetch_imagery wrote, so `date` is the real
    #    capture date, not date.today(). That closes a long-standing bug.
    stats = compute_stats(scene["path"])
    print(f"analysis   : {stats['areaName']}  NDVI mean {stats['ndvi']['mean']}")

    # 4. STORE -- AOI + provenance travel with the numbers
    payload = dict(stats)
    payload["aoi"] = {
        "center": aoi["center"],
        "coordinates": aoi["coordinates"],
        "source_kml": kml_path,
    }
    payload["source"] = {
        "mission": "Sentinel-2 L2A",
        "scene_date": scene["date"],
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
