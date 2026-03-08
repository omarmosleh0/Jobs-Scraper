-- Jordan Jobs Scraper - Supabase Schema
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/_/sql

-- Jobs table (embedding stored as jsonb for compatibility; pgvector optional for similarity search)
create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  company text not null,
  location text,
  url text not null,
  description text,
  posted_date timestamptz,
  scraped_at timestamptz default now(),
  source text not null,
  category text,
  category_confidence float,
  relevance_score float,
  content_hash text not null,
  embedding jsonb,
  notified boolean default false,
  raw_data jsonb,
  unique(content_hash)
);

-- Scrape runs for monitoring
create table if not exists scrape_runs (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz default now(),
  finished_at timestamptz,
  status text,
  jobs_found integer default 0,
  new_jobs integer default 0,
  errors jsonb
);

-- Indexes
create index if not exists idx_jobs_content_hash on jobs(content_hash);
create index if not exists idx_jobs_notified on jobs(notified) where notified = false;
create index if not exists idx_jobs_scraped_at on jobs(scraped_at);
create index if not exists idx_jobs_category on jobs(category);

-- RLS: service_role key bypasses RLS. If using anon key, add policies:
-- create policy "Allow all for jobs" on jobs for all using (true) with check (true);
-- create policy "Allow all for scrape_runs" on scrape_runs for all using (true) with check (true);
