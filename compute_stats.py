import rasterio
import numpy as np
import json
import os

def compute_stats(image_path, region="unknown"):
    """
    Computes NDVI and land cover stats from a satellite image.
    Returns a clean JSON-compatible dictionary.
    """

    # Error case 1 — file doesn't exist
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        with rasterio.open(image_path) as src:

            # Error case 2 — image doesn't have enough bands
            if src.count < 2:
                raise ValueError(f"Image needs at least 2 bands, found {src.count}")

            red = src.read(1).astype(float)
            nir = src.read(2).astype(float)

    except rasterio.errors.RasterioIOError as e:
        raise ValueError(f"Could not read image: {e}")

    # Calculate NDVI
    np.seterr(divide='ignore', invalid='ignore')
    ndvi = (nir - red) / (nir + red)

    # Land cover estimate
    threshold = 0.2
    total_pixels = np.count_nonzero(~np.isnan(ndvi))
    vegetation_pixels = np.count_nonzero(ndvi > threshold)
    non_vegetation_pixels = total_pixels - vegetation_pixels
    vegetation_pct = round((vegetation_pixels / total_pixels) * 100, 2)
    non_vegetation_pct = round((non_vegetation_pixels / total_pixels) * 100, 2)

    # Return clean shared JSON shape
    result = {
        "region": region,
        "ndvi": {
            "mean": round(float(np.nanmean(ndvi)), 4),
            "min": round(float(np.nanmin(ndvi)), 4),
            "max": round(float(np.nanmax(ndvi)), 4)
        },
        "land_cover": {
            "vegetation_pct": vegetation_pct,
            "non_vegetation_pct": non_vegetation_pct,
            "threshold_used": threshold
        }
    }

    return result


# Run directly to test
if __name__ == "__main__":
    result = compute_stats("sample.tif", region="sample_image")
    print(json.dumps(result, indent=2))

