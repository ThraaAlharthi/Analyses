"""AOI analysis pipeline: KML boundary -> NDVI analysis -> saved DB row.

This wires together three pieces built separately:
  - kml_reader.read_aoi   : where the user wants analysed (the AOI)
  - compute_stats         : the NDVI numbers for a raster
  - Postgres analyses table : durable, per-user storage

NOTE: compute_stats needs a satellite raster with an NIR band. The KML gives
the *location*; it does not give *imagery*. Until real Sentinel-2 imagery for
the AOI is available, we analyse the synthetic sample_oman.tif. The wiring is
real; only the raster is a stand-in.
"""
from __future__ import annotations

import json

import psycopg2
from psycopg2.extras import Json

from compute_stats import compute_stats
from kml_reader import read_aoi

DB = "dbname=omanlens"   # local socket; same connection psql uses


def run_pipeline(kml_path: str, raster_path: str, user_id: int = 1) -> int:
    """Read an AOI, analyse a raster, store the result. Returns the new row id."""

    # 1. WHERE — read the area of interest from the KML
    aoi = read_aoi.invoke({"kml_path": kml_path})
    print(f"AOI centre: {aoi['center']}  ({aoi['point_count']} boundary points)")

    # 2. WHAT — run NDVI analysis on the raster
    #    (area_name left to auto-detect from the raster's own coordinates)
    stats = compute_stats(raster_path)
    print(f"analysis  : {stats['areaName']}  NDVI mean {stats['ndvi']['mean']}")

    # 3. STORE — one row in the analyses table, AOI attached inside raw JSON
    payload = dict(stats)
    payload["aoi"] = {
        "center": aoi["center"],
        "coordinates": aoi["coordinates"],
        "source_kml": kml_path,
    }

    conn = psycopg2.connect(DB)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analyses
                  (user_id, image_id, area_name_ar, acquired_date,
                   ndvi_mean, ndvi_min, ndvi_max,
                   vegetation_pct, pixel_count, latitude, longitude, raw)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    user_id,
                    raster_path,
                    stats["areaName"],
                    stats["date"],
                    stats["ndvi"]["mean"],
                    stats["ndvi"]["min"],
                    stats["ndvi"]["max"],
                    stats["land_cover"]["vegetation_pct"],
                    stats["pixel_count"],
                    stats["latitude"],
                    stats["longitude"],
                    Json(payload),
                ),
            )
            new_id = cur.fetchone()[0]
    finally:
        conn.close()

    print(f"saved     : analyses row id={new_id}")
    return new_id


if __name__ == "__main__":
    run_pipeline("aoi.kml", "sample_oman.tif")
