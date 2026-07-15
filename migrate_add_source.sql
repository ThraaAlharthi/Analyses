-- Distinguish real imagery from the synthetic stand-in used before
-- Sentinel-2 fetching existed. Rows are kept as history, but labelled --
-- unlabelled history is indistinguishable from a mistake.

ALTER TABLE analyses ADD COLUMN IF NOT EXISTS data_source TEXT;

UPDATE analyses
   SET data_source = 'synthetic_sample'
 WHERE image_id = 'sample_oman.tif';

UPDATE analyses
   SET data_source = 'sentinel2_l2a'
 WHERE image_id LIKE 'S2_%';
