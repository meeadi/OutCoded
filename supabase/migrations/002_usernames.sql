-- Usernames are unique regardless of capitalisation,
-- so "Aditya" and "aditya" can't both exist.
create unique index profiles_username_lower_idx
    on public.profiles (lower(username));