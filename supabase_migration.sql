-- Add category column to events table if it doesn't exist
-- Run this in Supabase SQL Editor: Dashboard -> SQL Editor -> New query
ALTER TABLE events
ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'campus_event';

-- Optional: Create index for faster filtering by category
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

-- Add updated_at for "last updated" display (optional)
ALTER TABLE events
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
