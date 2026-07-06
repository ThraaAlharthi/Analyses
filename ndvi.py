import rasterio
import numpy as np
import matplotlib.pyplot as plt

# Open the image
with rasterio.open("sample.tif") as src:
    red = src.read(1).astype(float)   # Band 1 = Red
    nir = src.read(2).astype(float)   # Band 2 = NIR

# Avoid division by zero
np.seterr(divide='ignore', invalid='ignore')

# Calculate NDVI
ndvi = (nir - red) / (nir + red)

# Print results
print(f"Average NDVI: {np.nanmean(ndvi):.4f}")
print(f"Min NDVI:     {np.nanmin(ndvi):.4f}")
print(f"Max NDVI:     {np.nanmax(ndvi):.4f}")

# Save a visual map
plt.imshow(ndvi, cmap='RdYlGn')
plt.colorbar(label='NDVI')
plt.title('NDVI Map')
plt.savefig('ndvi_map.png')
print("Map saved as ndvi_map.png")
