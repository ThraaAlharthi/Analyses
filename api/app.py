"""Day 4 Task A: expose compute_stats() behind POST /analyze.

Run from ~/Day1-clean:
    pip3 install fastapi uvicorn
    SAMPLES_DIR=. uvicorn api.app:app --reload --port 8001
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from compute_stats import compute_stats, MissingBandError

SAMPLES_DIR = Path(os.getenv("SAMPLES_DIR", ".")).resolve()
ALLOWED = {".tif", ".tiff"}

app = FastAPI(title="Oman Lens AI Service", version="0.4.0")


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
