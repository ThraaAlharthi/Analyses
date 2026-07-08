import rasterio
import numpy as np
import json
import os
from datetime import date
from rasterio.crs import CRS
from rasterio.warp import transform
from geopy.geocoders import Nominatim

def get_area_name(src):
    try:
        bounds = src.bounds
        center_x = (bounds.left + bounds.right) / 2
        center_y = (bounds.top + bounds.bottom) / 2
        lon, lat = transform(src.crs, CRS.from_epsg(4326), [center_x], [center_y])
        geolocator = Nominatim(user_agent="satellite-analyzer")
        location = geolocator.reverse(f"{lat[0]}, {lon[0]}", language="ar")
        if location:
            return location.address
        return f"{lat[0]:.4f}N, {lon[0]:.4f}E"
    except:
        return "Unknown"

def compute_stats(image_path, area_id=1):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        with rasterio.open(image_path) as src:
            if src.count < 2:
                raise ValueError(f"Image needs at least 2 bands, found {src.count}")
            red = src.read(1).astype(float)
            nir = src.read(2).astype(float)
            area_name = get_area_name(src)
    except rasterio.errors.RasterioIOError as e:
        raise ValueError(f"Could not read image: {e}")

    np.seterr(divide='ignore', invalid='ignore')
    ndvi = (nir - red) / (nir + red)

    threshold = 0.2
    total_pixels = np.count_nonzero(~np.isnan(ndvi))
    vegetation_pixels = np.count_nonzero(ndvi > threshold)
    non_vegetation_pixels = total_pixels - vegetation_pixels
    vegetation_pct = round((vegetation_pixels / total_pixels) * 100, 2)
    non_vegetation_pct = round((non_vegetation_pixels / total_pixels) * 100, 2)

    result = {
        "id": area_id,
        "areaName": area_name,
        "date": str(date.today()),
        "image": "",
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

if __name__ == "__main__":
    result = compute_stats("sample.tif", area_id=1)
    print(json.dumps(result, indent=2, ensure_ascii=False))
