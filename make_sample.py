"""Synthetic 2-band GeoTIFF with a KNOWN NDVI answer.

256x256, EPSG:32640 (UTM 40N), 10 m pixels, centred near Nizwa.
  vegetation 25%   red=800  nir=4000  -> NDVI 0.666667
  water      12.5% red=500  nir=300   -> NDVI -0.25
  soil       62.5% red=3000 nir=3600  -> NDVI 0.090909

Expected: mean 0.1922  min -0.25  max 0.6667  veg_pct 25.0  pixels 65536
"""
import numpy as np
import rasterio
from rasterio.transform import from_origin

SIZE, PIXEL_M, OUT = 256, 10, "sample_oman.tif"
CENTRE_E, CENTRE_N = 554_300, 2_535_000
half = (SIZE * PIXEL_M) / 2
transform = from_origin(CENTRE_E - half, CENTRE_N + half, PIXEL_M, PIXEL_M)

red = np.full((SIZE, SIZE), 3000, dtype=np.uint16)
nir = np.full((SIZE, SIZE), 3600, dtype=np.uint16)
red[:128, :128] = 800
nir[:128, :128] = 4000
red[128:, :64] = 500
nir[128:, :64] = 300

profile = {
    "driver": "GTiff", "height": SIZE, "width": SIZE, "count": 2,
    "dtype": "uint16", "crs": "EPSG:32640", "transform": transform,
    "compress": "deflate",
}
with rasterio.open(OUT, "w", **profile) as dst:
    dst.write(red, 1)
    dst.write(nir, 2)
    dst.set_band_description(1, "red")
    dst.set_band_description(2, "nir")
    dst.update_tags(ACQUISITION_DATE="2024-03-15")

print(f"wrote {OUT}")
print("expected: mean=0.1922 min=-0.25 max=0.6667 veg_pct=25.0 pixels=65536")
