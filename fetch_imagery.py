"""Fetch Sentinel-2 red + NIR bands clipped to an AOI.

Design: the cloud clips and returns ONLY the two bands we need, as a small
GeoTIFF. compute_stats then computes NDVI locally. This keeps the band math
in rasterio+numpy (the team standard) and keeps the grounding chain intact --
we produce the numbers, not a remote service.

Band order matches compute_stats defaults: band 1 = red (B04), band 2 = NIR (B08).
"""
import os
from datetime import date, timedelta

import rasterio
from rasterio.transform import from_bounds
from dotenv import load_dotenv
from shapely.geometry import Polygon
from sentinelhub import (
    SHConfig, SentinelHubCatalog, SentinelHubRequest, DataCollection,
    MimeType, BBox, CRS, Geometry, bbox_to_dimensions,
)

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

# Return B04 and B08 as raw surface reflectance, float32.
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "B03", "B02"],
    output: { bands: 4, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  // band order: red, NIR, green, blue
  // red+NIR stay first so compute_stats (band1=red, band2=NIR) is unaffected
  return [sample.B04, sample.B08, sample.B03, sample.B02];
}
"""


def aoi_geometry(kml_path: str) -> Geometry:
    """AOI polygon -> Sentinel Hub Geometry, preserving the actual shape.

    THE BUG THIS FIXES: aoi_bbox() below reduces the polygon to its bounding
    rectangle. An L-shaped AOI was analysed as a full square -- 2,830 pixels
    (25%) from ground the user had drawn around. Squares hid it, because a
    square IS its own bbox.

    Sentinel Hub returns 0 for pixels outside the geometry. NDVI then computes
    (0-0)/(0+0) = NaN, and compute_stats already excludes NaN from nanmean and
    from pixel_count -- so the mask composes with existing code untouched.
    """
    aoi = read_aoi.invoke({"kml_path": kml_path})
    # shapely wants (lon, lat); kml_reader gives (lat, lon).
    poly = Polygon([(lon, lat) for lat, lon in aoi["coordinates"]])
    return Geometry(poly, crs=CRS.WGS84)


def aoi_bbox(kml_path: str) -> BBox:
    """AOI polygon -> BBox. kml_reader gives (lat, lon); BBox wants lon first."""
    aoi = read_aoi.invoke({"kml_path": kml_path})
    lats = [p[0] for p in aoi["coordinates"]]
    lons = [p[1] for p in aoi["coordinates"]]
    return BBox(bbox=[min(lons), min(lats), max(lons), max(lats)], crs=CRS.WGS84)


def pick_clearest_scene(bbox: BBox, days_back: int = 365, max_cloud: float = 5.0):
    """Find the least-cloudy recent scene. Returns (scene_id, date_str, cloud_pct).

    The scene_id (e.g. S2B_MSIL2A_20260628T063619_N0512_R120_T40QEL) uniquely
    identifies one satellite pass. Storing it is what makes a result
    independently verifiable: anyone can load that exact scene in the
    Copernicus Browser, apply our stored polygon, and recompute NDVI.
    A date alone is ambiguous -- several satellites pass on the same day.

    Raises if nothing clear enough exists -- better an honest failure than
    silently analysing a cloudy scene.
    """
    end = date.today()
    start = end - timedelta(days=days_back)
    catalog = SentinelHubCatalog(config=config)
    scenes = list(catalog.search(
        DataCollection.SENTINEL2_L2A,
        bbox=bbox,
        time=(start.isoformat(), end.isoformat()),
        fields={"include": ["id", "properties.datetime",
                            "properties.eo:cloud_cover"], "exclude": []},
    ))
    usable = [s for s in scenes
              if s["properties"].get("eo:cloud_cover", 100) <= max_cloud]
    if not usable:
        raise ValueError(
            f"No scene under {max_cloud}% cloud in the last {days_back} days."
        )
    best = min(usable, key=lambda s: s["properties"]["eo:cloud_cover"])
    return (best["id"],
            best["properties"]["datetime"][:10],
            best["properties"]["eo:cloud_cover"])


def _write_pngs(red, nir, green, blue, tif_path):
    """Write two PNGs next to the data TIFF: true-colour and NDVI map.

    These are for humans / vision models. Analysis always uses the float TIFF;
    PNGs are lossy 8-bit and must never feed compute_stats.
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = str(tif_path).rsplit(".", 1)[0]

    # true colour: stack R,G,B, stretch to 0-1 for display
    rgb = np.dstack([red, green, blue])
    lo, hi = np.nanpercentile(rgb, 2), np.nanpercentile(rgb, 98)
    rgb = np.clip((rgb - lo) / (hi - lo + 1e-9), 0, 1)
    plt.imsave(f"{base}_truecolor.png", rgb)

    # NDVI map: brown (bare) -> green (vegetation)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
    plt.imsave(f"{base}_ndvi.png", ndvi, cmap="RdYlGn", vmin=-0.2, vmax=0.8)


def fetch_aoi_bands(kml_path: str, out_path: str = "aoi_scene.tif",
                    resolution: int = 10) -> dict:
    bbox = aoi_bbox(kml_path)
    geometry = aoi_geometry(kml_path)
    scene_id, scene_date, cloud = pick_clearest_scene(bbox)
    size = bbox_to_dimensions(bbox, resolution=resolution)

    print(f"AOI bbox   : {list(bbox)}")
    print(f"best scene : {scene_date}  ({cloud}% cloud)")
    print(f"scene id   : {scene_id}")
    print(f"raster size: {size[0]} x {size[1]} px at {resolution}m")

    request = SentinelHubRequest(
        evalscript=EVALSCRIPT,
        input_data=[SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A.define_from(
                "s2l2a", service_url=config.sh_base_url),
            time_interval=(scene_date, scene_date),
        )],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        geometry=geometry,   # <- masks to the polygon, not the rectangle
        size=size,
        config=config,
    )

    data = request.get_data()[0]          # (height, width, 4): red, nir, green, blue
    red, nir = data[:, :, 0], data[:, :, 1]
    green, blue = data[:, :, 2], data[:, :, 3]

    profile = {
        "driver": "GTiff", "height": size[1], "width": size[0],
        "count": 4, "dtype": "float32", "crs": "EPSG:4326",
        "transform": from_bounds(*list(bbox), width=size[0], height=size[1]),
        "compress": "deflate",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(red, 1)
        dst.write(nir, 2)
        dst.write(green, 3)
        dst.write(blue, 4)
        dst.set_band_description(1, "red")
        dst.set_band_description(2, "nir")
        dst.set_band_description(3, "green")
        dst.set_band_description(4, "blue")
        dst.update_tags(ACQUISITION_DATE=scene_date, CLOUD_COVER=str(cloud),
                        SCENE_ID=scene_id)

    # --- PNG previews (for display; NOT used for analysis) ---
    _write_pngs(red, nir, green, blue, out_path)

    print(f"wrote      : {out_path}")
    return {"path": out_path, "date": scene_date, "cloud": cloud,
            "scene_id": scene_id}


if __name__ == "__main__":
    fetch_aoi_bands("aoi.kml")
