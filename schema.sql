-- analyses table: one row per /analyze result, scoped to a user.
-- Column names follow the CURRENT working contract (image_id, area_name_ar,
-- latitude/longitude). The kickoff deck uses different names (analysis_id,
-- region, coordinates.lat) — reconcile in the meeting, then migrate with Alembic.

CREATE TABLE IF NOT EXISTS analyses (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL DEFAULT 1,
    image_id        TEXT    NOT NULL,
    area_name_ar    TEXT    NOT NULL,
    acquired_date   DATE,
    ndvi_mean       REAL,
    ndvi_min        REAL,
    ndvi_max        REAL,
    vegetation_pct  REAL,
    pixel_count     INTEGER,
    latitude        DOUBLE PRECISION,   -- nullable: some rasters have no CRS
    longitude       DOUBLE PRECISION,
    raw             JSONB,              -- full /analyze response, verbatim
    data_source     TEXT,               -- 'sentinel2_l2a' | 'synthetic_sample'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analyses_user    ON analyses (user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses (created_at DESC);
