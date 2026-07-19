"""Fetch a scene for an AOI within a chosen date window.

fetch_imagery always picks the clearest RECENT scene. For comparisons we need
a specific PAST window instead, so the same place can be analysed at two times.
Reuses everything from fetch_imagery -- only the date range differs.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sentinelhub import (
    SentinelHubCatalog, SentinelHubRequest, DataCollection, MimeType,
    bbox_to_dimensions,
)
import rasterio
from rasterio.transform import from_bounds

from fetch_imagery import config, EVALSCRIPT, aoi_bbox, aoi_geometry


def fetch_in_window(kml_path: str, start: str, end: str,
                    out_path: str, resolution: int = 10,
                    max_cloud: float = 10.0) -> dict:
    """Clearest scene between start and end (YYYY-MM-DD)."""
    bbox = aoi_bbox(kml_path)
    geometry = aoi_geometry(kml_path)

    catalog = SentinelHubCatalog(config=config)
    scenes = list(catalog.search(
        DataCollection.SENTINEL2_L2A, bbox=bbox, time=(start, end),
        fields={"include": ["id", "properties.datetime",
                            "properties.eo:cloud_cover"], "exclude": []},
    ))
    usable = [s for s in scenes
              if s["properties"].get("eo:cloud_cover", 100) <= max_cloud]
    if not usable:
        raise ValueError(f"No scene under {max_cloud}% cloud between {start} and {end}")
    best = min(usable, key=lambda s: s["properties"]["eo:cloud_cover"])
    scene_id = best["id"]
    scene_date = best["properties"]["datetime"][:10]
    cloud = best["properties"]["eo:cloud_cover"]

    print(f"window {start}..{end}: chose {scene_date} ({cloud}% cloud)")

    size = bbox_to_dimensions(bbox, resolution=resolution)
    request = SentinelHubRequest(
        evalscript=EVALSCRIPT,
        input_data=[SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A.define_from(
                "s2l2a", service_url=config.sh_base_url),
            time_interval=(scene_date, scene_date),
        )],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox, geometry=geometry, size=size, config=config,
    )
    data = request.get_data()[0]

    Path(out_path).parent.mkdir(exist_ok=True)
    profile = {
        "driver": "GTiff", "height": size[1], "width": size[0], "count": 2,
        "dtype": "float32", "crs": "EPSG:4326",
        "transform": from_bounds(*list(bbox), width=size[0], height=size[1]),
        "compress": "deflate",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data[:, :, 0], 1)
        dst.write(data[:, :, 1], 2)
        dst.set_band_description(1, "red")
        dst.set_band_description(2, "nir")
        dst.update_tags(ACQUISITION_DATE=scene_date, CLOUD_COVER=str(cloud),
                        SCENE_ID=scene_id)
    return {"path": out_path, "date": scene_date, "cloud": cloud,
            "scene_id": scene_id}


if __name__ == "__main__":
    import sys
    from compute_stats import compute_stats
    kml, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out = f"scenes/{Path(kml).stem}_{start}_{ts}.tif"
    scene = fetch_in_window(kml, start, end, out)
    stats = compute_stats(out)
    print(f"\n{stats['areaName']}  {scene['date']}")
    print(f"  NDVI mean {stats['ndvi']['mean']}  veg {stats['land_cover']['vegetation_pct']}%")
