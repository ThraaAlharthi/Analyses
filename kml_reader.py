"""Read an area-of-interest polygon from a KML file.

KML stores coordinates as "lon,lat,altitude" triples separated by spaces.
Note the order: LONGITUDE first, then latitude -- the reverse of how they're
usually spoken, and the reverse of what Leaflet's [lat, lng] expects. We swap
to (lat, lon) on the way out so downstream code isn't tempted to guess.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from langchain_core.tools import tool


# KML lives in this XML namespace; every tag must be looked up with it.
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


@tool
def read_aoi(kml_path: str) -> dict:
    """Extract the first polygon boundary from a KML file.

    Returns a dict with:
      - coordinates: list of (latitude, longitude) pairs, in that order
      - point_count: how many points the boundary has
      - center: (lat, lon) centroid, handy as a marker / for geocoding
    Raises ValueError if the file has no polygon.
    """
    tree = ET.parse(kml_path)
    root = tree.getroot()

    # Find the first <coordinates> block anywhere in the document.
    coords_el = root.find(".//kml:Polygon//kml:coordinates", KML_NS)
    if coords_el is None or not (coords_el.text or "").strip():
        raise ValueError(f"No polygon coordinates found in {kml_path}")

    latlon = []
    for triple in coords_el.text.split():
        parts = triple.split(",")
        if len(parts) < 2:
            continue
        lon, lat = float(parts[0]), float(parts[1])   # KML order: lon first
        latlon.append((lat, lon))                       # emit lat first

    if not latlon:
        raise ValueError(f"Polygon in {kml_path} had no usable points")

    lats = [p[0] for p in latlon]
    lons = [p[1] for p in latlon]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))

    return {
        "coordinates": latlon,
        "point_count": len(latlon),
        "center": (round(center[0], 6), round(center[1], 6)),
    }


if __name__ == "__main__":
    import json
    result = read_aoi("aoi.kml")
    print(f"points : {result['point_count']}")
    print(f"center : {result['center']}  (lat, lon)")
    print("boundary:")
    for lat, lon in result["coordinates"]:
        print(f"  lat={lat:.6f}  lon={lon:.6f}")
