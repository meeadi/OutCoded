-- =====================================================================
-- OutCoded: practice. Topics, question pools, and practice modes.
-- Run once in the SQL Editor: dev first, then production.
-- =====================================================================

-- The fixed list of topics practice is organised by. Every question must use
-- one, so a typo in a CSV ("Sql", "postgres") can't create a phantom topic.
create table public.topics (
    id         text primary key check (id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    name       text not null,
    sort_order smallint not null default 0
);

insert into public.topics (id, name, sort_order) values
    ('python',     'python',             1),
    ('javascript', 'javascript',         2),
    ('sql',        'sql',                3),
    ('dsa',        'dsa & complexity',   4),
    ('java',       'java',               5),
    ('c-cpp',      'c / c++',            6),
    ('git-linux',  'git & linux',        7),
    ('web',        'web & apis',         8),
    ('security',   'security',           9),
    ('databases',  'databases & design', 10);

-- Served through the API like everything else.
alter table public.topics enable row level security;
revoke all on public.topics from anon, authenticated;

-- Move the old categories onto the new topics.
update public.questions set category = case category
    when 'complexity' then 'dsa'
    when 'git'        then 'git-linux'
    when 'regex'      then 'git-linux'
    else category
end;

-- Stop with a clear message if any question still has a category that isn't a topic.
do $$
declare unknown text;
begin
    select string_agg(distinct category, ', ') into unknown
    from public.questions where category not in (select id from public.topics);
    if unknown is not null then
        raise exception 'These question categories are not topics yet: %. Map them in this file, then run it again.', unknown;
    end if;
end $$;

alter table public.questions
    add constraint questions_category_is_a_topic
    foreign key (category) references public.topics (id) on update cascade;

-- Which modes a question appears in: practice teaches, ranked tests.
alter table public.questions
    add column pool text not null default 'both'
    check (pool in ('practice', 'ranked', 'both'));

create index questions_practice_idx on public.questions (category, rating)
    where status = 'active';

-- Which practice mode an answer came from (null for Code-Off matches).
alter table public.attempts
    add column variant text
    check (variant in ('rush', 'blitz', 'survival', 'zen', 'review'));