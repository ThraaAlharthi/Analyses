"""Tests for compute_stats. Run: python3 test_compute_stats.py

The old test_ndvi_range() asserted -1 <= NDVI <= 1, which cannot fail --
(nir-red)/(nir+red) is algebraically confined to that interval. A test that
cannot fail is why sample.tif spent three days in the Bahamas unnoticed.
"""
import os
import numpy as np
import rasterio
from compute_stats import compute_stats, MissingBandError

SAMPLE = "sample_oman.tif"
passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f" -- {detail}" if detail else ""))


def test_output_shape():
    r = compute_stats(SAMPLE, area_name="test")
    for k in ("id", "areaName", "date", "ndvi", "land_cover",
              "pixel_count", "latitude", "longitude"):
        check(f"result has '{k}'", k in r)
    for k in ("mean", "min", "max"):
        check(f"ndvi has '{k}'", k in r.get("ndvi", {}))


def test_missing_file():
    try:
        compute_stats("nonexistent.tif")
        check("missing file raises", False, "no exception")
    except FileNotFoundError:
        check("missing file raises FileNotFoundError", True)


def test_missing_band():
    with rasterio.open(SAMPLE) as src:
        n = src.count
    try:
        compute_stats(SAMPLE, nir_band=n + 1)
        check("out-of-range band raises", False, "no exception")
    except MissingBandError:
        check("out-of-range band raises MissingBandError", True)


def test_known_values():
    """The whole point of a synthetic raster: the answer is known in advance."""
    r = compute_stats(SAMPLE)
    check("mean == 0.1922", r["ndvi"]["mean"] == 0.1922, f"got {r['ndvi']['mean']}")
    check("min == -0.25", r["ndvi"]["min"] == -0.25, f"got {r['ndvi']['min']}")
    check("max == 0.6667", r["ndvi"]["max"] == 0.6667, f"got {r['ndvi']['max']}")
    check("vegetation_pct == 25.0",
          r["land_cover"]["vegetation_pct"] == 25.0,
          f"got {r['land_cover']['vegetation_pct']}")
    check("pixel_count == 65536", r["pixel_count"] == 65536, f"got {r['pixel_count']}")


def test_percentages_sum():
    lc = compute_stats(SAMPLE)["land_cover"]
    total = lc["vegetation_pct"] + lc["non_vegetation_pct"]
    check("veg% + non-veg% == 100", abs(total - 100.0) < 0.01, f"got {total}")


def test_coordinates_in_oman():
    """Tripwire. This is the test that should have existed on Day 3."""
    r = compute_stats(SAMPLE)
    lat, lon = r["latitude"], r["longitude"]
    if lat is None or lon is None:
        check("coordinates present", False, "no usable CRS")
        return
    check("centre falls inside Oman",
          16.0 <= lat <= 27.0 and 51.0 <= lon <= 60.5,
          f"({lat}, {lon}) is outside Oman")


if __name__ == "__main__":
    if not os.path.exists(SAMPLE):
        raise SystemExit(f"{SAMPLE} not found -- run python3 make_sample.py first.")
    for fn in (test_output_shape, test_missing_file, test_missing_band,
               test_known_values, test_percentages_sum, test_coordinates_in_oman):
        print(f"\n{fn.__name__}")
        fn()
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
