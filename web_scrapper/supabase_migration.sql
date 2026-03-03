-- Add category column to events table if it doesn't exist
-- Run this in Supabase SQL Editor: Dashboard -> SQL Editor -> New query
ALTER TABLE events
ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'campus_event';

-- Optional: Create index for faster filtering by category
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

-- Add updated_at for "last updated" display (optional)
ALTER TABLE events
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- =============================================================
-- SECURITY: Enable Row Level Security (RLS)
-- Run this in Supabase SQL Editor to lock down the events table
-- =============================================================

-- 1. Enable RLS on the events table
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- 2. Public (anon) users can only SELECT (read)
CREATE POLICY "anon_read_only" ON events
  FOR SELECT
  TO anon
  USING (true);

-- 3. Only the service_role (your backend scraper via .env secret key) can insert
CREATE POLICY "service_role_insert" ON events
  FOR INSERT
  TO service_role
  WITH CHECK (true);

-- 4. Only the service_role can update
CREATE POLICY "service_role_update" ON events
  FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

-- 5. Only the service_role can delete
CREATE POLICY "service_role_delete" ON events
  FOR DELETE
  TO service_role
  USING (true);
