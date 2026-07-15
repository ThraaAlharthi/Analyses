"""Tests for the KML area-of-interest reader.

Design note: these tests build their own KML fixture rather than relying on
aoi.kml. That file is gitignored (it is someone's specific area), so a
teammate cloning the repo could not run tests that depend on it. A test that
only passes on one laptop is not much of a test.
"""
import pytest

from kml_reader import read_aoi

# A minimal, valid KML. Square in Oman, corners chosen so every expected
# value can be worked out by hand -- the same principle as sample_oman.tif.
#   lon 57.0-57.1, lat 22.0-22.1, closed (last point == first)
#   expected centre: lat (22.0+22.0+22.1+22.1+22.0)/5 = 22.04
#                    lon (57.0+57.1+57.1+57.0+57.0)/5 = 57.04
FIXTURE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              57.0,22.0,0 57.1,22.0,0 57.1,22.1,0 57.0,22.1,0 57.0,22.0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""

NO_POLYGON_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark><Point><coordinates>57.0,22.0,0</coordinates></Point></Placemark>
  </Document>
</kml>
"""


@pytest.fixture
def kml_file(tmp_path):
    p = tmp_path / "test.kml"
    p.write_text(FIXTURE_KML)
    return str(p)


def test_reads_all_points(kml_file):
    result = read_aoi.invoke({"kml_path": kml_file})
    assert result["point_count"] == 5


def test_coordinate_order_is_lat_lon(kml_file):
    """THE critical test.

    KML stores lon,lat. We must emit (lat, lon). If this ever flips, an AOI
    in Oman silently relocates -- latitude 57 does not exist, but the code
    would not complain. This is the Bahamas failure in miniature.
    """
    result = read_aoi.invoke({"kml_path": kml_file})
    first_lat, first_lon = result["coordinates"][0]
    assert first_lat == 22.0, f"latitude should be 22.0, got {first_lat}"
    assert first_lon == 57.0, f"longitude should be 57.0, got {first_lon}"


def test_center_is_the_mean_of_the_points(kml_file):
    result = read_aoi.invoke({"kml_path": kml_file})
    assert result["center"] == (22.04, 57.04)


def test_polygon_is_closed(kml_file):
    result = read_aoi.invoke({"kml_path": kml_file})
    assert result["coordinates"][0] == result["coordinates"][-1]


def test_latitudes_are_physically_possible(kml_file):
    result = read_aoi.invoke({"kml_path": kml_file})
    for lat, lon in result["coordinates"]:
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180


def test_raises_when_no_polygon(tmp_path):
    p = tmp_path / "point_only.kml"
    p.write_text(NO_POLYGON_KML)
    with pytest.raises(ValueError, match="No polygon"):
        read_aoi.invoke({"kml_path": str(p)})


def test_raises_on_missing_file():
    with pytest.raises(Exception):
        read_aoi.invoke({"kml_path": "does_not_exist.kml"})


def test_is_a_langgraph_tool():
    """The @tool wrapper must expose what an agent needs."""
    assert read_aoi.name == "read_aoi"
    assert "kml_path" in read_aoi.args
    assert read_aoi.description
