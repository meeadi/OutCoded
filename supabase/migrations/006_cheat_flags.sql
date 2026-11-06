-- Browser-reported time the tab was out of focus during a question.
alter table public.attempts
    add column away_ms integer check (away_ms is null or away_ms >= 0);

-- One row per player per kind of suspicion, for a human to review.
create table public.cheat_flags (
    id         bigint generated always as identity primary key,
    user_id    uuid not null references public.profiles (id) on delete cascade,
    kind       text not null check (kind in
                   ('superhuman_speed', 'overperformance', 'robotic_timing', 'tab_switching')),
    severity   double precision not null,
    evidence   jsonb not null,
    status     text not null default 'open' check (status in ('open', 'dismissed', 'confirmed')),
    first_seen timestamptz not null default now(),
    last_seen  timestamptz not null default now(),
    unique (user_id, kind)
);

create index cheat_flags_open_idx on public.cheat_flags (severity desc) where status = 'open';

-- Only the backend (service connection) can read or write flags.
alter table public.cheat_flags enable row level security;
revoke all on public.cheat_flags from anon, authenticated;