-- Search, upload and moderation fixes. Safe to re-run.
-- Run once against the production database (Supabase SQL editor or psql).
-- Either order relative to the deploy works; until both are done, search is just slower.

-- Trigram support for autocomplete (ILIKE '%...%')
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Old indexes: a B-tree on the full text (no query can use it) and the 'english' FTS index,
-- which the app no longer queries
DROP INDEX IF EXISTS ix_subtitle_text;
DROP INDEX IF EXISTS idx_fts_subtitle;

-- Subtitle lines can be longer than 500 characters (no table rewrite: varchar -> text is free)
ALTER TABLE subtitle ALTER COLUMN text TYPE TEXT;

-- Full-text search with the 'simple' config (keeps words like "to", "be", "I").
-- Must match FTS_CONFIG in app.py.
CREATE INDEX IF NOT EXISTS ix_subtitle_text_fts ON subtitle USING GIN (to_tsvector('simple', text));

-- Autocomplete substring search
CREATE INDEX IF NOT EXISTS ix_subtitle_text_trgm ON subtitle USING GIN (text gin_trgm_ops);

-- Foreign key lookups (previous/next line on the quote page, admin line counts, deletes)
CREATE INDEX IF NOT EXISTS ix_subtitle_movie_id ON subtitle (movie_id);

-- alter_db.py added is_approved with DEFAULT TRUE; new rows should default to pending
ALTER TABLE movie ALTER COLUMN is_approved SET DEFAULT false;
