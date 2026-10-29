-- OutCoded: ratings.
-- Only matches from the matchmaking queue are rated; friend links stay casual.

alter table public.matches
    add column rated boolean not null default false;

-- One row per player per rated match: the full rating history.
create table public.rating_history (
    id                 bigint generated always as identity primary key,
    user_id            uuid not null references public.profiles (id) on delete cascade,
    match_id           uuid not null references public.matches (id) on delete cascade,
    result             text not null check (result in ('win', 'loss', 'draw')),
    rating_before      double precision not null,
    rating_after       double precision not null,
    rd_before          double precision not null,
    rd_after           double precision not null,
    volatility_before  double precision not null,
    volatility_after   double precision not null,
    created_at         timestamptz not null default now(),

    unique (user_id, match_id)
);

create index rating_history_user_idx on public.rating_history (user_id, created_at);

alter table public.rating_history enable row level security;
revoke all on public.rating_history from anon, authenticated;