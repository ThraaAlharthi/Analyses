# Oman Lens — AI / Analysis Pipeline

Backend for the satellite-analysis platform. Turns a user-drawn area of
interest into a verified NDVI (vegetation) analysis in Arabic, and provides
training data for a fine-tuned Arabic explanation model.

## Pipeline

    KML (area)  ->  read_aoi  ->  fetch imagery  ->  compute NDVI  ->  Postgres  ->  Arabic PDF

One command runs the whole chain:

    python3 -c "from pipeline import run_pipeline; run_pipeline('aois/birkat_site.kml')"

## Files

| file | what it does |
|---|---|
| `kml_reader.py` | reads the AOI polygon from a KML (LangGraph tool) |
| `fetch_imagery.py` | fetches Sentinel-2 red+NIR bands, clipped to the polygon |
| `fetch_at_date.py` | same, for a chosen date window (used for comparisons) |
| `compute_stats.py` | computes NDVI locally (rasterio + numpy) |
| `pipeline.py` | ties the above together, saves to the database |
| `report_generator.py` | renders one analysis as an Arabic PDF (LangGraph tool) |
| `schema.sql` | the `analyses` table definition |
| `data/to_write.jsonl` | training dataset (grounded Arabic examples) |
| `scripts/` | dataset build/validate/showcase tools |
| `test_*.py` | pytest suites |

## Key design decisions

- **NDVI is computed locally**, not by the imagery provider — keeps the band
  math on our side (team standard) and keeps every number ours to verify.
- **Only the AOI polygon is fetched**, not its bounding box — an earlier bug
  analysed the rectangle, including ground outside the user's boundary.
- **Provenance is stored with every analysis** — scene ID, exact polygon,
  cloud cover — so any result can be independently reproduced in the
  Copernicus Browser.
- **The AOI polygon, not a single coordinate, is analysed** — each result
  averages thousands of pixels, so no single noisy pixel skews it.

## Running the tests

    pip3 install pytest
    python3 -m pytest -q

46 tests. The critical ones (NDVI correctness, polygon masking) have been
verified to fail when the code is deliberately broken — a green suite here
means the checks actually bite, not just that they exist.

## Status

**Done:** imagery pipeline, database, both tools, Arabic reports, test suite.
**In progress:** training dataset (7 grounded examples across 3 categories;
target is larger). Fine-tuning pending GPU, base-model choice, and dataset size.

## Not in the repo (by design)

- `.env` — API credentials (secrets never committed)
- `scenes/*.tif` — fetched imagery (regenerable from stored provenance)
- generated PDFs / HTML (regenerable)
