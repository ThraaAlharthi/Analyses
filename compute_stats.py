"""NDVI + land-cover statistics from a GeoTIFF.

Place name is detected automatically by reverse-geocoding the raster's centre.
Pass area_name= only if you want to override the detected value.
"""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache

import numpy as np
import rasterio
from geopy.geocoders import Nominatim
from rasterio.crs import CRS
from rasterio.warp import transform


class MissingBandError(ValueError):
    """Raster lacks a band NDVI needs. Subclasses ValueError so old
    `except ValueError` still works, while the API can tell 'wrong bands'
    apart from 'corrupt file'."""


def get_center_latlon(src):
    """Centre of the raster in WGS84 degrees. (None, None) if no usable CRS."""
    if src.crs is None:
        return None, None
    try:
        b = src.bounds
        cx = (b.left + b.right) / 2
        cy = (b.top + b.bottom) / 2
        lon, lat = transform(src.crs, CRS.from_epsg(4326), [cx], [cy])
        return round(float(lat[0]), 6), round(float(lon[0]), 6)
    except Exception:
        return None, None


# Cached: Nominatim allows ~1 request/second. Re-analysing the same scene
# should not hit the network twice.
@lru_cache(maxsize=256)
def detect_area_name(lat: float, lon: float) -> str:
    """Reverse-geocode to an Arabic place name. Never raises.

    Returns the most SPECIFIC component available -- village before country.
    The old code took address.split(",")[-1], which is the country, so every
    title read 'تحليل عُمان'.
    """
    try:
        geo = Nominatim(user_agent="omanlens-satellite-analyzer")
        loc = geo.reverse(f"{lat}, {lon}", language="ar", timeout=10)
        if not loc:
            return f"{lat:.4f}N, {lon:.4f}E"
        addr = loc.raw.get("address", {})
        for key in ("village", "town", "city", "municipality", "suburb",
                    "county", "state_district", "state", "country"):
            if addr.get(key):
                return addr[key]
        return loc.address
    except Exception:
        # Offline, rate-limited, timed out. Coordinates still survive.
        return f"{lat:.4f}N, {lon:.4f}E"


def compute_stats(image_path, area_name=None, area_id=1,
                  acquired_date=None, red_band=1, nir_band=2, threshold=0.2):
    """area_name=None means: detect it from the image's own coordinates."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        with rasterio.open(image_path) as src:
            needed = max(red_band, nir_band)
            if src.count < needed:
                raise MissingBandError(
                    f"Image has {src.count} band(s); need at least {needed} "
                    f"(red={red_band}, nir={nir_band})."
                )
            red = src.read(red_band).astype(float)
            nir = src.read(nir_band).astype(float)
            lat, lon = get_center_latlon(src)
            tags = src.tags()
    except MissingBandError:
        raise
    except rasterio.errors.RasterioIOError as e:
        raise ValueError(f"Could not read image: {e}") from e

    # Detect the place unless the caller overrode it.
    if area_name is None:
        area_name = detect_area_name(lat, lon) if lat is not None else "Unknown"

    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)

    total_pixels = int(np.count_nonzero(~np.isnan(ndvi)))
    if total_pixels == 0:
        raise ValueError("Every NDVI pixel is NaN; red and NIR are identical or empty.")

    vegetation_pixels = int(np.count_nonzero(ndvi > threshold))

    if acquired_date is None:
        acquired_date = (tags.get("TIFFTAG_DATETIME")
                         or tags.get("ACQUISITION_DATE")
                         or str(date.today()))

    return {
        "id": area_id,
        "areaName": area_name,
        "date": acquired_date,
        "image": "",
        "ndvi": {
            "mean": round(float(np.nanmean(ndvi)), 4),
            "min": round(float(np.nanmin(ndvi)), 4),
            "max": round(float(np.nanmax(ndvi)), 4),
        },
        "land_cover": {
            "vegetation_pct": round((vegetation_pixels / total_pixels) * 100, 2),
            "non_vegetation_pct": round(((total_pixels - vegetation_pixels) / total_pixels) * 100, 2),
            "threshold_used": threshold,
        },
        "pixel_count": total_pixels,
        "latitude": lat,
        "longitude": lon,
    }


if __name__ == "__main__":
    print(json.dumps(compute_stats("sample_oman.tif"), indent=2, ensure_ascii=False))
