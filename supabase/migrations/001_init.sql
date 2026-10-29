-- =====================================================================
-- OutCode: initial schema
-- Run this once in the Supabase dashboard: SQL Editor -> New query ->
-- paste this file -> Run.
--
-- Design rule: the server is the referee. Browsers (anon / authenticated
-- roles) can never read questions, answers, attempts or events. Only the
-- FastAPI backend, which connects as the table owner, can.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Profiles: one row per signed-up user, created automatically on signup.
-- Rating columns use Glicko-2 defaults (rating 1500, RD 350, vol 0.06).
-- ---------------------------------------------------------------------
create table public.profiles (
    id                uuid primary key references auth.users (id) on delete cascade,
    username          text unique
                      check (username ~ '^[A-Za-z0-9_]{3,20}$'),
    rating            double precision not null default 1500,
    rating_deviation  double precision not null default 350,
    volatility        double precision not null default 0.06,
    created_at        timestamptz not null default now()
);


-- ---------------------------------------------------------------------
-- Questions. Multiple choice for the MVP: 2-4 options, one correct.
-- Questions get their own Glicko-2 rating so difficulty can calibrate
-- itself from real answers later (step 5).
-- ---------------------------------------------------------------------
create table public.questions (
    id                uuid primary key default gen_random_uuid(),
    slug              text not null unique,          -- stable ID from the CSV
    format            text not null
                      check (format in ('predict_output', 'spot_bug', 'quickfire')),
    category          text not null,                 -- e.g. python, sql, security
    language          text,                          -- code language, null for none
    difficulty        text not null
                      check (difficulty in ('easy', 'medium', 'hard')),
    prompt            text not null,
    code              text,
    options           jsonb not null,                -- JSON array of strings
    correct_index     smallint not null,             -- 0-based index into options
    explanation       text not null,
    time_limit_s      smallint not null default 30
                      check (time_limit_s between 5 and 300),
    status            text not null default 'active'
                      check (status in ('draft', 'active', 'retired')),
    rating            double precision not null default 1500,
    rating_deviation  double precision not null default 350,
    volatility        double precision not null default 0.06,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now(),

    constraint options_is_array
        check (jsonb_typeof(options) = 'array'
               and jsonb_array_length(options) between 2 and 4),
    constraint correct_index_in_range
        check (correct_index >= 0 and correct_index < jsonb_array_length(options))
);

create index questions_active_idx on public.questions (status) where status = 'active';


-- ---------------------------------------------------------------------
-- Attempts: one row each time a question is served to a player.
-- All timing comes from the database clock, never from the browser.
-- option_order stores how options were shuffled for this attempt, so
-- "the answer is B" can't be shared between players.
-- ---------------------------------------------------------------------
create table public.attempts (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references public.profiles (id) on delete cascade,
    question_id    uuid not null references public.questions (id),
    mode           text not null default 'solo'
                   check (mode in ('solo', 'match')),
    option_order   smallint[] not null,              -- displayed position -> original index
    shown_at       timestamptz not null default now(),
    answered_at    timestamptz,
    chosen_index   smallint,                         -- original index the player picked
    is_correct     boolean,
    timed_out      boolean not null default false,
    response_ms    integer
);

create index attempts_user_shown_idx on public.attempts (user_id, shown_at desc);
create index attempts_question_idx   on public.attempts (question_id);


-- ---------------------------------------------------------------------
-- Events: append-only analytics log (question served, answer submitted,
-- later: match started, match finished, ...). This is the raw material
-- for retention dashboards, question calibration and cheat detection.
-- ---------------------------------------------------------------------
create table public.events (
    id           bigint generated always as identity primary key,
    event_type   text not null,
    user_id      uuid references public.profiles (id) on delete set null,
    attempt_id   uuid references public.attempts (id) on delete set null,
    question_id  uuid references public.questions (id) on delete set null,
    properties   jsonb not null default '{}'::jsonb,
    created_at   timestamptz not null default now()
);

create index events_type_time_idx on public.events (event_type, created_at);
create index events_user_time_idx on public.events (user_id, created_at);


-- ---------------------------------------------------------------------
-- Create a profile automatically whenever someone signs up.
-- ---------------------------------------------------------------------
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.profiles (id) values (new.id);
    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();


-- ---------------------------------------------------------------------
-- Row Level Security and grants.
-- Supabase exposes the public schema to browsers through its Data API,
-- so lock everything down and open only what the frontend may touch.
-- ---------------------------------------------------------------------
alter table public.profiles  enable row level security;
alter table public.questions enable row level security;
alter table public.attempts  enable row level security;
alter table public.events    enable row level security;

-- Browsers get nothing on these tables. No policies + no grants = no access.
revoke all on public.questions, public.attempts, public.events from anon, authenticated;

-- Profiles: everyone can read (leaderboards), users can change only
-- their own username. Ratings can only be changed by the backend.
revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to anon, authenticated;
grant update (username) on public.profiles to authenticated;

create policy "Profiles are readable by everyone"
    on public.profiles for select
    to anon, authenticated
    using (true);

create policy "Users can update their own username"
    on public.profiles for update
    to authenticated
    using ((select auth.uid()) = id)
    with check ((select auth.uid()) = id);
