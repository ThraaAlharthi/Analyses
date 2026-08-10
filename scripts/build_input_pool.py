#!/usr/bin/env python3
"""Builds data/input_pool.jsonl from REAL Sentinel-2 imagery + compute_stats.
No hand-typed numbers — every record here comes from an actual fetch + analysis.

Run this once per AOI now, and again on later days/weeks to accumulate
different dates for the same regions (needed for change-detection examples).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root

from compute_stats import compute_stats
from fetch_imagery import fetch_aoi_bands

AOIS_DIR = Path(__file__).resolve().parent.parent / "aois"
SCENES_DIR = Path(__file__).resolve().parent.parent / "scenes"
OUT = Path(__file__).resolve().parent.parent / "data" / "input_pool.jsonl"

def main():
    SCENES_DIR.mkdir(exist_ok=True)
    records = []

    for kml_path in sorted(AOIS_DIR.glob("*.kml")):
        print(f"--- {kml_path.name} ---")
        raster_path = SCENES_DIR / f"{kml_path.stem}.tif"
        try:
            scene = fetch_aoi_bands(str(kml_path), out_path=str(raster_path))
            stats = compute_stats(scene["path"])
        except Exception as e:
            print(f"  SKIPPED ({e})")
            continue

        record = dict(stats)
        record["scene_id"] = scene["scene_id"]
        record["cloud_cover_pct"] = scene["cloud"]
        record["source_kml"] = kml_path.name
        records.append(record)
        print(f"  OK: {stats.get('areaName')}  NDVI mean {stats.get('ndvi', {}).get('mean')}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # append, don't overwrite — running this again next week should ADD dates,
    # not erase the ones you already collected
    mode = "a" if OUT.exists() else "w"
    with OUT.open(mode, encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nwrote {len(records)} records -> {OUT}")

if __name__ == "__main__":
    main()