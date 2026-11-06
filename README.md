# OutCoded

Chess.com for coding puzzles. You play quick, rated rounds of *predict the output*, *spot the bug* and quickfire questions, either solo or head-to-head against other players.

Built with React + TypeScript, FastAPI and Supabase (Postgres). The UI is minimal, keyboard-first and inspired by Monkeytype, with a few goofy effects thrown in.

## Features

- **Solo puzzle rush**: 10-question sessions with streaks, stamps and a results screen
- **Code-Off**: live 1v1 matches over WebSockets. Friend links play casual matches; the matchmaking queue plays ranked ones
- **Glicko-2 ratings**: implemented from Glickman's paper. Ratings show a `?` while they're still provisional
- **Leaderboard and player pages**: with rating history charts
- **Question calibration**: every answer counts as a mini rated game between the player and the question, so difficulty ratings come from real results
- **Cheat flags**: suspicious patterns get flagged for a human to review. Nobody is ever banned automatically
- **Themes**: midnight, paper and matcha. Answer with keys 1–4, and switch effects off if you want calm

## The one rule

**The server is the referee.** The browser never receives the correct answer before the reveal. The server times every answer with the database clock, and it decides what counts. Each player gets their own shuffle of the options, so "it's B" can't be passed around. The database enforces this too: signed-in users can't read the answer keys or other players' attempts, and can't change ratings.

## Project layout

```
OutCoded/
├── supabase/migrations/      run in order in the Supabase SQL Editor (never edit one that's been run)
│   ├── 001_init.sql              profiles, questions, attempts, events, security rules
│   ├── 002_usernames.sql
│   ├── 003_matches.sql
│   ├── 004_ratings.sql           rated matches, rating history
│   ├── 005_question_calibration.sql
│   └── 006_cheat_flags.sql
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI app
│   │   ├── auth.py               verifies Supabase sign-in tokens (JWKS)
│   │   ├── game.py               game rules: shuffling, timeouts, points
│   │   ├── scoring.py            scores an answer and calibrates the question
│   │   ├── glicko2.py            rating maths
│   │   ├── ratings.py            applies match results
│   │   ├── match_room.py         one live Code-Off match
│   │   ├── matchmaking.py        ranked queue pairing
│   │   ├── cheat_detection.py    suspicious-pattern detectors
│   │   └── routers/              solo, matches, profiles, leaderboard
│   ├── data/questions.csv        the question bank
│   ├── scripts/
│   │   ├── import_questions.py   load the CSV into the database
│   │   ├── question_report.py    calibration report: mislabelled questions
│   │   ├── detect_cheating.py    scan answers and record cheat flags
│   │   └── get_token.py          sign in as a test user from the terminal
│   └── tests/                    pytest
└── frontend/                     React 19 + TypeScript + Vite
    └── src/
        ├── components/           Home, PuzzleRush, CodeOff, Queue, Leaderboard, PlayerPage …
        ├── hooks/                useSession, useAwayTimer
        └── lib/                  api, supabase, effects, session, rating
```

## Setup

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com) and save the database password somewhere safe.
2. Go to **Project Settings → JWT Keys** and make sure the current key is asymmetric (ECC or RSA). The API refuses tokens signed with the legacy shared secret.
3. In **SQL Editor**, run each file in `supabase/migrations/`, in order.

### 2. Backend

You need Python 3.12 or newer.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Fill in `.env`. The comments in `.env.example` say where to find each value. Then:

```bash
python scripts/import_questions.py
uvicorn app.main:app --reload
```

http://localhost:8000/health should return `{"status":"ok"}`. The interactive API docs are at http://localhost:8000/docs.

### 3. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
# VITE_API_URL=http://localhost:8000   (this is the default)
```

Only put public values in `VITE_` variables, because they end up in the browser. The secret key and the database password never belong here.

```bash
npm run dev
```

Open http://localhost:5173.

### 4. Checks

```bash
cd backend && pytest && ruff check .
cd frontend && npm run lint && npx tsc -b
```

## API

| Endpoint | What it does |
|---|---|
| `GET /health` | Checks the database connection |
| `GET /me` | The signed-in player's profile |
| `PUT /me/username` | Claims a username |
| `POST /solo/next` | Serves a question with shuffled options and no answer |
| `POST /solo/answer` | Scores the answer with server time, then reveals the solution |
| `POST /matches` | Creates a friend match and returns its code |
| `GET /matches/{code}` | Match info |
| `WS /ws/matches/{code}` | Plays a Code-Off match |
| `WS /ws/queue` | Ranked matchmaking queue |
| `GET /leaderboard` | Top players (shown after 5 ranked matches) |
| `GET /players/{username}` | A public profile and its rating history |

Every serve and answer also writes a row to the `events` table, which is the raw material for analytics.

## Ratings

- **Players** start at 1500 with a rating deviation (RD) of 350. Only queue matches are rated; friend links stay casual. A rating shows `?` while its RD is above 110.
- **Questions** start at 1300, 1500 or 1700 depending on their easy/medium/hard label, with an RD of 200. Each answer nudges the rating. Run `python scripts/question_report.py` to list questions whose label doesn't match how players actually do on them.

## Cheat flags

`python scripts/detect_cheating.py` scans recent answers (`--days 30` by default) and records flags in the `cheat_flags` table:

| Flag | What it looks for |
|---|---|
| `superhuman_speed` | Right answers faster than the question could be read, counting first attempts only |
| `overperformance` | Playing far above your rating, by more than luck and rating uncertainty can explain |
| `robotic_timing` | Answer times too steady to be human |
| `tab_switching` | Repeatedly leaving the tab, then coming back with the right answer |

The thresholds were tuned on simulated players so that honest players are rarely flagged (around 1 in 1,000 or fewer). Flags are for a human to review, never automatic bans. Set a flag's `status` to `dismissed` or `confirmed`; re-running the script updates the evidence but keeps your decision.

## Analytics dashboard

A Streamlit dashboard covering activity, retention cohorts, question health and cheat-flag review.

```bash
cd backend
pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

It connects with `DATABASE_URL`, which can read everything, so it only listens on localhost. Run it on your own machine; never deploy it publicly.

- **Overview**: active players, answers by mode, and when people play (Indian time)
- **Retention**: next-day and within-a-week return rates, plus weekly cohorts
- **Questions**: real difficulty vs label, time-limit advice (1.5× the time 90% of right answers took), the favourite wrong answer, and a warning when a wrong option beats the right one
- **Cheat flags**: evidence, the player's recent answers, and confirm/dismiss/reopen

## Writing questions

Questions live in `backend/data/questions.csv`. In Google Sheets, Alt+Enter adds a line break inside a cell, which you need for code.

| Column | Notes |
|---|---|
| `slug` | Unique ID like `py-late-binding`. Never change it after importing; it's how updates are matched. |
| `format` | `predict_output`, `spot_bug` or `quickfire` |
| `category` | e.g. `python`, `sql`, `security`, `git` |
| `language` | Language for syntax highlighting, or empty |
| `difficulty` | `easy`, `medium` or `hard` |
| `prompt`, `code` | The question and an optional snippet. Indentation is kept exactly. |
| `option_a` … `option_d` | At least A and B, filled in order |
| `correct` | `A`, `B`, `C` or `D` |
| `explanation` | Shown after answering. Explain *why*. |
| `time_limit_s` | 5 to 300, default 30 |
| `status` | `active`, `draft` or `retired`. Retire questions instead of deleting them. |

Check the file first with `python scripts/import_questions.py --dry-run`. A broken row rejects the whole import, and re-importing never resets a calibrated rating.

**Always run predict-the-output snippets before importing.** One wrong answer key in a ranked match costs more trust than ten good questions earn.

## Roadmap

1. ✅ Database, API, sign-in, seed questions, event logging
2. ✅ Frontend with solo puzzle rush
3. ✅ Code-Off: 1v1 matches via friend link
4. ✅ Matchmaking, Glicko-2 ratings, leaderboard, player pages
5. ✅ Data layer: Question calibration, Cheat flags, Analytics dashboard
6. Polish and pilot: soundtrack, reconnecting, deployment, a uni coding cell tournament