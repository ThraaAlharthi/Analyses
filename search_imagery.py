"""Search Sentinel-2 for scenes covering our AOI.

Read-only: lists what exists and how cloudy it is. Downloads nothing.

Level-2A is the atmospherically corrected surface-reflectance product --
the atmosphere has already been accounted for, so NDVI reflects the ground
rather than the air in between.
"""
import os
from datetime import date, timedelta

from dotenv import load_dotenv
from sentinelhub import SHConfig, SentinelHubCatalog, BBox, CRS, DataCollection

from kml_reader import read_aoi

load_dotenv()

config = SHConfig()
config.sh_client_id = os.getenv("SH_CLIENT_ID")
config.sh_client_secret = os.getenv("SH_CLIENT_SECRET")
config.sh_base_url = "https://sh.dataspace.copernicus.eu"
config.sh_token_url = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
    "/protocol/openid-connect/token"
)


def aoi_bbox(kml_path: str) -> BBox:
    """AOI polygon -> Sentinel Hub bounding box.

    COORDINATE ORDER WARNING: kml_reader returns (lat, lon) pairs, but
    Sentinel Hub's BBox wants (min_lon, min_lat, max_lon, max_lat).
    Getting this backwards would silently search the wrong place -- the
    same class of bug that put sample.tif in the Bahamas.
    """
    aoi = read_aoi.invoke({"kml_path": kml_path})
    lats = [p[0] for p in aoi["coordinates"]]
    lons = [p[1] for p in aoi["coordinates"]]
    return BBox(bbox=[min(lons), min(lats), max(lons), max(lats)], crs=CRS.WGS84)


if __name__ == "__main__":
    bbox = aoi_bbox("aoi.kml")
    print(f"searching bbox : {list(bbox)}  (lon, lat order)")

    # Last 12 months.
    end = date.today()
    start = end - timedelta(days=365)
    print(f"date range     : {start} to {end}\n")

    catalog = SentinelHubCatalog(config=config)
    results = list(catalog.search(
        DataCollection.SENTINEL2_L2A,
        bbox=bbox,
        time=(start.isoformat(), end.isoformat()),
        fields={
            "include": ["id", "properties.datetime", "properties.eo:cloud_cover"],
            "exclude": [],
        },
    ))

    print(f"found {len(results)} scene(s)\n")
    for r in results[:15]:
        when = r["properties"]["datetime"][:10]
        cloud = r["properties"].get("eo:cloud_cover", "?")
        print(f"  {when}   cloud {cloud:>5}%   {r['id'][:44]}")
    if len(results) > 15:
        print(f"  ... and {len(results) - 15} more")
