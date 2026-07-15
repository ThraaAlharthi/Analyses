"""Tests for the Arabic PDF report generator.

Split along the same seam as the code: cell_text and render_report are pure
and tested directly; generate_report needs Postgres and is marked so it can
be skipped where no database exists.
"""
import pytest

from report_generator import cell_text, render_report, generate_report

SAMPLE = {
    "area_name_ar": "ولاية بهلاء",
    "acquired_date": "2026-06-28",
    "ndvi_mean": 0.0652,
    "ndvi_min": 0.0021,
    "ndvi_max": 0.5907,
    "vegetation_pct": 0.3,
    "pixel_count": 5795,
    "latitude": 22.76759,
    "longitude": 57.21223,
}


def test_cell_text_leaves_numbers_alone():
    """Standards doc: Western Arabic numerals (0-9) everywhere.

    Numbers must not go through the bidi reshaper -- that is what reversed
    '0.25-' into nonsense before.
    """
    assert cell_text("25.0") == "25.0"
    assert cell_text(0.1922) == "0.1922"
    assert cell_text("2026-06-28") == "2026-06-28"
    assert cell_text(65536) == "65536"


def test_cell_text_reshapes_arabic():
    """Arabic must be transformed; if it comes back identical, the reshaper
    is not running and the PDF will show disconnected backwards letters."""
    arabic = "ولاية بهلاء"
    assert cell_text(arabic) != arabic


def test_cell_text_handles_mixed_content():
    mixed = cell_text("ولاية 25")
    assert "25" in mixed


def test_render_report_writes_a_file(tmp_path):
    out = tmp_path / "r.pdf"
    render_report(SAMPLE, str(out))
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_report_produces_a_real_pdf(tmp_path):
    """Every PDF starts with the magic bytes %PDF. A file that exists but
    is not a PDF would otherwise pass the test above."""
    out = tmp_path / "r.pdf"
    render_report(SAMPLE, str(out))
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_report_returns_its_path(tmp_path):
    out = tmp_path / "r.pdf"
    assert render_report(SAMPLE, str(out)) == str(out)


def test_is_a_langgraph_tool():
    assert generate_report.name == "generate_report"
    assert "analysis_id" in generate_report.args


@pytest.mark.db
def test_generate_report_raises_on_unknown_id():
    """Needs Postgres. Run with: pytest -m db"""
    with pytest.raises(ValueError, match="No analysis"):
        generate_report.invoke({"analysis_id": 999999})
