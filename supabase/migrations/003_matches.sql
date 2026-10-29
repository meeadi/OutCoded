-- OutCoded: Code-Off matches.

create table public.matches (
    id            uuid primary key default gen_random_uuid(),
    code          text not null unique,                 -- short invite code in the link
    host_id       uuid not null references public.profiles (id) on delete cascade,
    guest_id      uuid references public.profiles (id) on delete set null,
    status        text not null default 'waiting'
                  check (status in ('waiting', 'playing', 'finished', 'abandoned')),
    rounds        smallint not null default 5,
    host_score    integer not null default 0,
    guest_score   integer not null default 0,
    winner_id     uuid references public.profiles (id) on delete set null,  -- null = draw
    forfeit       boolean not null default false,
    created_at    timestamptz not null default now(),
    started_at    timestamptz,
    finished_at   timestamptz,

    constraint host_is_not_guest check (guest_id is null or guest_id <> host_id)
);

create index matches_host_idx  on public.matches (host_id, created_at desc);
create index matches_guest_idx on public.matches (guest_id, created_at desc);

-- Each player's answer in a match is a normal attempt, linked to the match.
alter table public.attempts
    add column match_id uuid references public.matches (id) on delete cascade,
    add column points   integer;

create index attempts_match_idx on public.attempts (match_id) where match_id is not null;

-- Same rule as everything else: only the backend touches this.
alter table public.matches enable row level security;
revoke all on public.matches from anon, authenticated;