#!/usr/bin/env python3
"""Fetches a SECOND, earlier scene per AOI already in the pool, to unlock
change_detection examples. Appends to the same input_pool.jsonl."""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compute_stats import compute_stats
from fetch_imagery import fetch_aoi_bands

AOIS_DIR = Path(__file__).resolve().parent.parent / "aois"
SCENES_DIR = Path(__file__).resolve().parent.parent / "scenes"
POOL = Path(__file__).resolve().parent.parent / "data" / "input_pool.jsonl"

EXCLUDE_KML = {"lshape_test.kml"}
MONTHS_BACK = 3

def existing_dates_by_kml():
    seen = {}
    if POOL.exists():
        with POOL.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                seen.setdefault(row["source_kml"], []).append(row["date"])
    return seen

def main():
    existing = existing_dates_by_kml()
    records = []

    for kml_path in sorted(AOIS_DIR.glob("*.kml")):
        if kml_path.name in EXCLUDE_KML:
            continue
        prior_dates = existing.get(kml_path.name, [])
        if not prior_dates:
            print(f"--- {kml_path.name}: no existing date, skipping ---")
            continue
        latest = max(datetime.strptime(d, "%Y-%m-%d").date() for d in prior_dates)
        target_end = latest - timedelta(days=MONTHS_BACK * 30)

        print(f"--- {kml_path.name} (targeting before {target_end}) ---")
        raster_path = SCENES_DIR / f"{kml_path.stem}_prior.tif"
        try:
            scene = fetch_aoi_bands(str(kml_path), out_path=str(raster_path),
                                     end_date=target_end)
            if scene["date"] in prior_dates:
                print(f"  SKIPPED (same date {scene['date']} already in pool)")
                continue
            stats = compute_stats(scene["path"])
        except Exception as e:
            print(f"  SKIPPED ({e})")
            continue

        record = dict(stats)
        record["scene_id"] = scene["scene_id"]
        record["cloud_cover_pct"] = scene["cloud"]
        record["source_kml"] = kml_path.name
        records.append(record)
        print(f"  OK: {stats.get('areaName')}  {scene['date']}  NDVI mean {stats.get('ndvi', {}).get('mean')}")

    if records:
        with POOL.open("a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nadded {len(records)} second-date records -> {POOL}")

if __name__ == "__main__":
    main()
