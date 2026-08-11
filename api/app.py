"""Day 4 Task A: expose compute_stats() behind POST /analyze.

Run from ~/Day1-clean:
    pip3 install fastapi uvicorn
    SAMPLES_DIR=. uvicorn api.app:app --reload --port 8001
"""
from __future__ import annotations

import os
from pathlib import Path

import shutil
import tempfile
import uuid

import psycopg2
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from compute_stats import compute_stats, MissingBandError
from pipeline import run_pipeline, DB
SAMPLES_DIR = Path(os.getenv("SAMPLES_DIR", ".")).resolve()
ALLOWED = {".tif", ".tiff"}

app = FastAPI(title="Oman Lens AI Service", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to the actual frontend origin once known
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ServiceError(Exception):
    status_code, code = 500, "internal_error"

    def __init__(self, en, ar):
        self.message_en, self.message_ar = en, ar


class ImageNotFound(ServiceError):
    status_code, code = 404, "image_not_found"


class BadImageName(ServiceError):
    status_code, code = 400, "bad_image_name"


class UnreadableRaster(ServiceError):
    status_code, code = 422, "unreadable_raster"


class MissingBand(ServiceError):
    status_code, code = 422, "missing_band"


@app.exception_handler(ServiceError)
async def handle(_: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"error": {
        "code": exc.code, "message_en": exc.message_en, "message_ar": exc.message_ar}})


class AnalyzeRequest(BaseModel):
    image: str = Field(..., examples=["sample_oman.tif"])
    area_name: str | None = Field(None, description="Omit to auto-detect from the image coordinates")
    area_id: int = Field(1)
    acquired_date: str | None = Field(None)
    red_band: int = Field(1, ge=1)
    nir_band: int = Field(2, ge=1)


class NdviStats(BaseModel):
    mean: float
    min: float
    max: float


class AnalyzeResponse(BaseModel):
    """Shared shape. These field names are the contract with the Web team."""
    image_id: str
    area_name_ar: str
    date: str
    ndvi: NdviStats
    vegetation_percent: float
    pixel_count: int
    latitude: float | None
    longitude: float | None


def resolve_image(name: str) -> Path:
    if not name or "\x00" in name:
        raise BadImageName("Image name is empty.", "اسم الصورة فارغ.")
    p = (SAMPLES_DIR / name).resolve()
    if not p.is_relative_to(SAMPLES_DIR):
        raise BadImageName("No path segments allowed.", "لا يُسمح بمسارات فرعية.")
    if p.suffix.lower() not in ALLOWED:
        raise BadImageName(f"Bad extension '{p.suffix}'.", "امتداد غير مدعوم.")
    if not p.is_file():
        raise ImageNotFound(f"No image '{name}'.", f"لا توجد صورة باسم '{name}'.")
    return p


@app.get("/health")
def health():
    return {"status": "ok", "samples_dir": str(SAMPLES_DIR)}


@app.get("/images")
def images():
    if not SAMPLES_DIR.is_dir():
        return {"images": []}
    return {"images": sorted(p.name for p in SAMPLES_DIR.iterdir()
                             if p.suffix.lower() in ALLOWED)}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    path = resolve_image(req.image)
    try:
        raw = compute_stats(str(path), area_name=req.area_name, area_id=req.area_id,
                            acquired_date=req.acquired_date,
                            red_band=req.red_band, nir_band=req.nir_band)
    except FileNotFoundError as e:
        raise ImageNotFound(f"No image '{req.image}'.", "لا توجد صورة.") from e
    # MissingBandError before ValueError -- it is a subclass, so order matters.
    except MissingBandError as e:
        raise MissingBand(str(e), "الصورة تفتقد نطاقًا مطلوبًا.") from e
    except ValueError as e:
        raise UnreadableRaster(str(e), "تعذّرت قراءة الصورة.") from e

    return {
        "image_id": req.image,
        "area_name_ar": raw["areaName"],
        "date": raw["date"],
        "ndvi": raw["ndvi"],
        "vegetation_percent": raw["land_cover"]["vegetation_pct"],
        "pixel_count": raw["pixel_count"],
        "latitude": raw["latitude"],
        "longitude": raw["longitude"],
    }
class BadKMLFile(ServiceError):
    status_code, code = 400, "bad_kml_file"


class PipelineFailed(ServiceError):
    status_code, code = 500, "pipeline_failed"


class KMLAnalyzeResponse(BaseModel):
    """Same contract as AnalyzeResponse, extended with the Arabic explanation
    and the saved analysis row id."""
    analysis_id: int
    image_id: str
    area_name_ar: str
    date: str
    ndvi: NdviStats
    vegetation_percent: float
    pixel_count: int
    latitude: float | None
    longitude: float | None
    explanation_ar: str | None


UPLOAD_DIR = Path(tempfile.gettempdir()) / "omanlens_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _fetch_analysis_row(analysis_id: int) -> dict:
    conn = psycopg2.connect(DB)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM analyses WHERE id = %s", (analysis_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        raise PipelineFailed(
            f"Row {analysis_id} not found after pipeline run.",
            "تعذّر العثور على نتيجة التحليل بعد المعالجة.",
        )
    return row


@app.post("/analyze-kml", response_model=KMLAnalyzeResponse)
async def analyze_kml(file: UploadFile = File(...)):
    """Accepts a user-uploaded KML file, runs the full pipeline (fetch real
    imagery, compute NDVI, get Arabic explanation, save to Postgres), and
    returns the result in the same contract shape as /analyze."""

    if not file.filename or not file.filename.lower().endswith(".kml"):
        raise BadKMLFile(
            "Only .kml files are accepted.", "يُقبل ملف بصيغة .kml فقط.",
        )

    # Save the upload to a unique temp path -- never trust the client's filename
    saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.kml"
    try:
        with saved_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    finally:
        file.file.close()

    try:
        analysis_id = run_pipeline(str(saved_path))
    except Exception as e:
        # run_pipeline can fail for many real reasons: no cloud-free imagery
        # found, Sentinel Hub auth/network issues, an invalid/empty polygon,
        # a Postgres connection problem. Surface it, don't swallow it.
        raise PipelineFailed(
            f"Pipeline failed: {e}",
            "تعذّر إتمام التحليل. يُرجى التحقق من ملف المنطقة والمحاولة مجددًا.",
        ) from e
    finally:
        saved_path.unlink(missing_ok=True)

    row = _fetch_analysis_row(analysis_id)
    raw = row.get("raw") or {}

    return {
        "analysis_id": analysis_id,
        "image_id": row["image_id"],
        "area_name_ar": row["area_name_ar"],
        "date": str(row["acquired_date"]),
        "ndvi": {
            "mean": row["ndvi_mean"],
            "min": row["ndvi_min"],
            "max": row["ndvi_max"],
        },
        "vegetation_percent": row["vegetation_pct"],
        "pixel_count": row["pixel_count"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "explanation_ar": raw.get("explanation_ar"),
    }


