"""Simple NDVI-threshold land-cover classifier.

HONEST SCOPE: this splits pixels into 3 classes using NDVI thresholds only:
  water        NDVI < 0        (water absorbs NIR -> negative)
  vegetation   NDVI > 0.3      (healthy plant cover)
  bare_or_built  in between    (bare soil, rock, AND urban -- red+NIR
                                cannot separate these; the name admits it)

This is NOT the 4-class cropland/urban/water/bare_soil the dataset spec
wants. Distinguishing urban from bare soil needs shortwave-infrared bands
we don't fetch. Every percentage here is derived from real pixels -- nothing
invented -- but the classes are coarse. Flagged for the team.
"""
from __future__ import annotations

import numpy as np
import rasterio


def classify_land_cover(tif_path: str, red_band: int = 1, nir_band: int = 2) -> dict:
    """Return land-cover percentages from NDVI thresholds. 3 honest classes."""
    with rasterio.open(tif_path) as src:
        red = src.read(red_band).astype("float32")
        nir = src.read(nir_band).astype("float32")

    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)

    valid = ~np.isnan(ndvi)
    total = int(np.count_nonzero(valid))
    if total == 0:
        raise ValueError(f"No valid pixels in {tif_path}")

    water = int(np.count_nonzero(valid & (ndvi < 0.0)))
    veg = int(np.count_nonzero(valid & (ndvi > 0.3)))
    bare_built = total - water - veg

    pct = lambda n: round(100.0 * n / total, 2)
    return {
        "land_cover_pct": {
            "water": pct(water),
            "vegetation": pct(veg),
            "bare_or_built": pct(bare_built),
        },
        "pixel_count": total,
        "method": "ndvi_threshold_3class",
        "note": "coarse; does not separate urban from bare soil",
    }


if __name__ == "__main__":
    import sys, json
    path = sys.argv[1] if len(sys.argv) > 1 else "sample_oman.tif"
    print(json.dumps(classify_land_cover(path), indent=2, ensure_ascii=False))
