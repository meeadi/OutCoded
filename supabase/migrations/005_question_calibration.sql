-- OutCoded: question difficulty calibration.
-- Questions start less uncertain than players (RD 200 instead of 350),
-- because the easy/medium/hard label is already a decent first guess.

alter table public.questions
    alter column rating_deviation set default 200;

-- Existing questions that haven't been calibrated yet start from the same place.
update public.questions
set rating_deviation = 200
where rating_deviation = 350;