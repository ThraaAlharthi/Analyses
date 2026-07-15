"""Tests for compute_stats.

Rewritten as real pytest. The previous version used a check() helper that
PRINTED "FAIL" but never raised -- so pytest reported all 20 green no matter
what they found. A test suite that cannot fail is worse than none, because it
manufactures confidence. That is exactly how sample.tif spent three days in
the Bahamas.

Every assertion below can fail. The known-value tests compare against
arithmetic derived on paper before the code ran (see make_sample.py).
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

from compute_stats import compute_stats, MissingBandError, get_center_latlon

SAMPLE = "sample_oman.tif"


@pytest.fixture(scope="session", autouse=True)
def ensure_sample():
    """Generate the synthetic raster if absent.

    sample_oman.tif is gitignored (regenerable), so a teammate cloning the
    repo would otherwise have no fixture. Tests that only run on one laptop
    are not tests.
    """
    if not Path(SAMPLE).exists():
        subprocess.run([sys.executable, "make_sample.py"], check=True)
    return SAMPLE


# --- shape -------------------------------------------------------------

@pytest.mark.parametrize("key", [
    "id", "areaName", "date", "ndvi", "land_cover",
    "pixel_count", "latitude", "longitude",
])
def test_result_has_key(key):
    assert key in compute_stats(SAMPLE, area_name="test")


@pytest.mark.parametrize("key", ["mean", "min", "max"])
def test_ndvi_has_key(key):
    assert key in compute_stats(SAMPLE, area_name="test")["ndvi"]


# --- known values ------------------------------------------------------
# The whole point of a synthetic raster: the answer is known in advance.
# 25% vegetation (NDVI 0.666667), 12.5% water (-0.25), 62.5% soil (0.090909).

def test_ndvi_mean_matches_hand_calculation():
    assert compute_stats(SAMPLE)["ndvi"]["mean"] == 0.1922


def test_ndvi_min_matches_water_block():
    assert compute_stats(SAMPLE)["ndvi"]["min"] == -0.25


def test_ndvi_max_matches_vegetation_block():
    assert compute_stats(SAMPLE)["ndvi"]["max"] == 0.6667


def test_vegetation_pct_matches_block_size():
    assert compute_stats(SAMPLE)["land_cover"]["vegetation_pct"] == 25.0


def test_pixel_count_matches_raster_size():
    assert compute_stats(SAMPLE)["pixel_count"] == 65536


# --- internal consistency ---------------------------------------------

def test_percentages_sum_to_100():
    lc = compute_stats(SAMPLE)["land_cover"]
    total = lc["vegetation_pct"] + lc["non_vegetation_pct"]
    assert abs(total - 100.0) < 0.01, f"got {total}"


def test_mean_lies_between_min_and_max():
    n = compute_stats(SAMPLE)["ndvi"]
    assert n["min"] <= n["mean"] <= n["max"]


def test_matches_independent_recomputation():
    """Recompute NDVI here, separately. Catches a wrong band index."""
    r = compute_stats(SAMPLE)
    with rasterio.open(SAMPLE) as src:
        red = src.read(1).astype(float)
        nir = src.read(2).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
    assert abs(r["ndvi"]["mean"] - round(float(np.nanmean(ndvi)), 4)) < 1e-6
    assert r["pixel_count"] == int(np.count_nonzero(~np.isnan(ndvi)))


# --- the tripwire ------------------------------------------------------

def test_scene_centre_falls_inside_oman():
    """THE test that would have caught sample.tif on Day 1.

    The old suite had nothing like this. It asserted -1 <= NDVI <= 1, which
    is algebraically incapable of failing, while the pipeline computed
    green-minus-red over the Bahamas.
    """
    r = compute_stats(SAMPLE)
    lat, lon = r["latitude"], r["longitude"]
    assert lat is not None and lon is not None, "raster has no usable CRS"
    assert 16.0 <= lat <= 27.0, f"latitude {lat} is outside Oman"
    assert 51.0 <= lon <= 60.5, f"longitude {lon} is outside Oman"


# --- errors ------------------------------------------------------------

def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        compute_stats("does_not_exist.tif")


def test_out_of_range_band_raises():
    with rasterio.open(SAMPLE) as src:
        n = src.count
    with pytest.raises(MissingBandError):
        compute_stats(SAMPLE, nir_band=n + 1)


def test_missing_band_error_is_a_valueerror():
    """Subclassing matters: the API layer catches MissingBandError before
    ValueError, so ordering in app.py depends on this relationship."""
    assert issubclass(MissingBandError, ValueError)


# --- area name ---------------------------------------------------------

def test_explicit_area_name_overrides_geocoding():
    assert compute_stats(SAMPLE, area_name="TestName")["areaName"] == "TestName"


def test_no_crs_returns_none_coordinates(tmp_path):
    """A raster with no CRS must return None, not invent coordinates."""
    p = tmp_path / "nocrs.tif"
    with rasterio.open(p, "w", driver="GTiff", height=4, width=4,
                       count=2, dtype="uint16") as dst:
        dst.write(np.full((4, 4), 100, dtype=np.uint16), 1)
        dst.write(np.full((4, 4), 200, dtype=np.uint16), 2)
    with rasterio.open(p) as src:
        assert get_center_latlon(src) == (None, None)
