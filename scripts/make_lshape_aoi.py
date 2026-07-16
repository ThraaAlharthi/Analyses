#!/usr/bin/env python3
"""Generate an L-shaped AOI to expose the bounding-box bug.

An L covers 3/4 of its bounding rectangle. So:
  - if the code honours the polygon -> pixel_count ~= 75% of the box
  - if the code silently uses the bbox -> pixel_count == 100% of the box

Square AOIs cannot detect this, because a square IS its own bounding box.
That is why the bug survived four test sites unnoticed.
"""
from pathlib import Path

# Centred on Al Awabi (the high-NDVI site) so the numbers stay interesting.
CENTRE_LAT, CENTRE_LON = 23.309571, 57.530744
SIZE = 0.010          # ~1.1 km
HALF = SIZE / 2

lat0, lat1 = CENTRE_LAT - HALF, CENTRE_LAT + HALF
lon0, lon1 = CENTRE_LON - HALF, CENTRE_LON + HALF
mid_lat, mid_lon = CENTRE_LAT, CENTRE_LON

# L-shape: full square minus the top-right quadrant.
#   lon0,lat0 -> lon1,lat0 -> lon1,mid  -> mid,mid -> mid,lat1 -> lon0,lat1 -> close
PTS = [
    (lon0, lat0),
    (lon1, lat0),
    (lon1, mid_lat),
    (mid_lon, mid_lat),
    (mid_lon, lat1),
    (lon0, lat1),
    (lon0, lat0),
]

coords = " ".join(f"{x:.6f},{y:.6f},0" for x, y in PTS)

KML = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>lshape_test</name>
    <description>L-shaped AOI: 75% of its bounding box. Test fixture.</description>
    <Placemark>
      <name>lshape_test</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              {coords}
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""

Path("aois").mkdir(exist_ok=True)
out = Path("aois") / "lshape_test.kml"
out.write_text(KML)
print(f"wrote {out}")
print("L covers 3/4 of its bbox -> expect pixel_count ~75% once the fix lands")
