#!/usr/bin/env python3
"""Make a KML AOI box from a centre coordinate.

Usage:
    python3 scripts/make_aoi.py <name> <lat> <lon> [size_km]

Example:
    python3 scripts/make_aoi.py nizwa_site 23.242748 57.411120 1.0

Deliberately does NOT label the terrain. We do not guess what is on the
ground -- we measure it. The NDVI that comes back is the answer.
"""
import sys
from pathlib import Path

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <description>centre {lat}, {lon} -- {size} km box</description>
    <Placemark>
      <name>{name}</name>
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


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)

    name = sys.argv[1]
    lat, lon = float(sys.argv[2]), float(sys.argv[3])
    size_km = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    # ~111 km per degree of latitude; longitude shrinks toward the poles,
    # but at 23 N the cosine factor is ~0.92 -- close enough for a box.
    half = (size_km / 111.0) / 2

    pts = [
        (lon - half, lat - half),
        (lon + half, lat - half),
        (lon + half, lat + half),
        (lon - half, lat + half),
        (lon - half, lat - half),   # close the ring
    ]
    coords = " ".join(f"{x:.6f},{y:.6f},0" for x, y in pts)

    Path("aois").mkdir(exist_ok=True)
    out = Path("aois") / f"{name}.kml"
    out.write_text(KML.format(name=name, lat=lat, lon=lon,
                              size=size_km, coords=coords))
    print(f"wrote {out}  ({size_km} km box centred {lat}, {lon})")


if __name__ == "__main__":
    main()
