import rasterio
import numpy as np
import matplotlib.pyplot as plt
import json

# Open the satellite image
with rasterio.open("sample.tif") as src:
    red = src.read(1).astype(float)
    nir = src.read(2).astype(float)

# Calculate NDVI
np.seterr(divide='ignore', invalid='ignore')
ndvi = (nir - red) / (nir + red)

# Calculate land cover estimate
threshold = 0.2
total_pixels = np.count_nonzero(~np.isnan(ndvi))
vegetation_pixels = np.count_nonzero(ndvi > threshold)
non_vegetation_pixels = total_pixels - vegetation_pixels
vegetation_pct = (vegetation_pixels / total_pixels) * 100
non_vegetation_pct = (non_vegetation_pixels / total_pixels) * 100

# Package as clean JSON
result = {
    "region": "sample_image",
    "ndvi": {
        "mean": round(float(np.nanmean(ndvi)), 4),
        "min": round(float(np.nanmin(ndvi)), 4),
        "max": round(float(np.nanmax(ndvi)), 4)
    },
    "land_cover": {
        "vegetation_pct": round(vegetation_pct, 2),
        "non_vegetation_pct": round(non_vegetation_pct, 2),
        "threshold_used": threshold
    }
}

# Print the JSON
print(json.dumps(result, indent=2))

# Save JSON to file
with open("ndvi_result.json", "w") as f:
    json.dump(result, f, indent=2)

print("\nSaved to ndvi_result.json")

# Save visual map
plt.imshow(ndvi, cmap='RdYlGn')
plt.colorbar(label='NDVI')
plt.title('NDVI Map')
plt.savefig('ndvi_map.png')
print("Map saved as ndvi_map.png")
