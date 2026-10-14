-- Runs once when the Postgres container starts with an empty volume.
-- To re-run after changes: docker compose down -v && docker compose up
-- Mirrors the `Inspection` schema in contracts/backend.openapi.yaml.

create table if not exists inspections (
  id            uuid primary key default gen_random_uuid(),
  status        text not null default 'inspected'
                check (status in ('inspected', 'explaining', 'explained', 'explain_failed', 'decided', 'failed')),
  line_id       text,
  part_type     text,
  source        text not null default 'upload' check (source in ('upload', 'simulator')),
  image_path    text not null,
  mask_path     text,
  heatmap_path  text,
  vision        jsonb,          -- VisionResult
  explanation   jsonb,          -- Explanation
  error         text,
  created_at    timestamptz not null default now()
);

create index if not exists inspections_created_at_idx on inspections (created_at desc);
create index if not exists inspections_line_idx on inspections (line_id);

create table if not exists decisions (
  inspection_id            uuid primary key references inspections (id) on delete cascade,
  decision                 text not null check (decision in ('accept', 'reject', 'rework')),
  followed_recommendation  boolean,
  note                     text,
  operator                 text,
  decided_at               timestamptz not null default now(),
  time_to_decision_ms      integer not null
);

create table if not exists chat_messages (
  id             bigserial primary key,
  inspection_id  uuid not null references inspections (id) on delete cascade,
  role           text not null check (role in ('operator', 'assistant')),
  content        text not null,
  sources        jsonb not null default '[]',
  created_at     timestamptz not null default now()
);

create index if not exists chat_messages_inspection_idx on chat_messages (inspection_id, created_at);
