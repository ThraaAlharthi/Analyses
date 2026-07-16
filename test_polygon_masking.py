"""Regression test for the bounding-box bug.

Found by our engineer: fetch_imagery reduced the AOI polygon to its bounding
rectangle, so an L-shaped AOI was analysed as a full square -- 2,830 pixels
(25%) from ground the user had excluded, shifting NDVI by 9%.

Square AOIs cannot catch this: a square IS its own bbox. This test uses an
L-shape, where bbox and polygon genuinely differ.
"""
import pytest
from shapely.geometry import Polygon

from fetch_imagery import aoi_geometry, aoi_bbox

LSHAPE = "aois/lshape_test.kml"


def test_geometry_is_not_the_bounding_box():
    """The whole point: an L must not become its rectangle."""
    geom = aoi_geometry(LSHAPE)
    bbox = aoi_bbox(LSHAPE)
    bbox_area = (bbox.max_x - bbox.min_x) * (bbox.max_y - bbox.min_y)
    assert geom.geometry.area < bbox_area * 0.9, (
        "polygon area should be well under its bbox for an L-shape; "
        "if these are equal the mask is not being applied"
    )


def test_lshape_covers_three_quarters_of_its_bbox():
    geom = aoi_geometry(LSHAPE)
    bbox = aoi_bbox(LSHAPE)
    bbox_area = (bbox.max_x - bbox.min_x) * (bbox.max_y - bbox.min_y)
    ratio = geom.geometry.area / bbox_area
    assert 0.7 < ratio < 0.8, f"L should cover ~75% of its bbox, got {ratio:.1%}"


def test_geometry_preserves_all_vertices():
    """A rectangle has 5 points (closed). An L has 7. If we get 5 back,
    the shape was silently squared off."""
    geom = aoi_geometry(LSHAPE)
    assert len(geom.geometry.exterior.coords) == 7


def test_geometry_uses_lon_lat_order():
    """shapely wants (lon, lat); kml_reader emits (lat, lon). Getting this
    backwards puts the AOI in the wrong hemisphere without erroring."""
    geom = aoi_geometry(LSHAPE)
    lon, lat = list(geom.geometry.exterior.coords)[0]
    assert 51.0 <= lon <= 60.5, f"longitude {lon} outside Oman"
    assert 16.0 <= lat <= 27.0, f"latitude {lat} outside Oman"


def test_geometry_is_actually_passed_to_the_request(monkeypatch):
    """The tests above prove aoi_geometry() builds a correct polygon.

    They do NOT prove fetch_aoi_bands passes it to Sentinel Hub. Remove
    `geometry=geometry` from the request and every test above still passes
    while the bug returns. This one catches that.
    """
    import fetch_imagery

    captured = {}

    class FakeRequest:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def get_data(self):
            import numpy as np
            return [np.zeros((10, 10, 2), dtype="float32")]

        @staticmethod
        def input_data(**kwargs):
            return kwargs

        @staticmethod
        def output_response(*args, **kwargs):
            return {}

    monkeypatch.setattr(fetch_imagery, "SentinelHubRequest", FakeRequest)
    monkeypatch.setattr(fetch_imagery, "pick_clearest_scene",
                        lambda *a, **k: ("2026-06-28", 0.0))

    fetch_imagery.fetch_aoi_bands(LSHAPE, out_path="/tmp/_test_mask.tif")

    assert "geometry" in captured, (
        "fetch_aoi_bands did not pass geometry= to SentinelHubRequest -- "
        "the AOI is being reduced to its bounding box again"
    )
    assert len(captured["geometry"].geometry.exterior.coords) == 7
