# OutCode

Chess.com for coding puzzles: quick, rated rounds of *predict the output*, *spot the bug* and quickfire questions.

This is **step 1** of the MVP: the database, the API, sign-in, and a solo question loop you can play through the API docs page. The frontend comes in step 2.

## The one rule

**The server is the referee.** The browser never receives the correct answer, the server times every answer with its own clock, and the server decides what counts. Options are shuffled per attempt, so "it's B" can't be passed around. The database enforces this too: signed-in users can't read questions, attempts or events, and can't change ratings.

## What's in here

```
outcode/
├── supabase/migrations/001_init.sql   database tables, security rules, signup trigger
└── backend/
    ├── app/
    │   ├── main.py            FastAPI app
    │   ├── auth.py            checks Supabase sign-in tokens
    │   ├── game.py            game rules (shuffling, timeouts), no I/O
    │   ├── question_bank.py   CSV validation
    │   ├── events.py          analytics event log
    │   └── routers/           /me, /solo/next, /solo/answer
    ├── data/questions.csv     24 seed questions, answers verified by running the code
    ├── scripts/
    │   ├── import_questions.py  load the CSV into the database
    │   └── get_token.py         sign in as a test user (until the frontend exists)
    ├── tests/                 pytest unit tests
    └── Dockerfile
```

## Setup (about 20 minutes)

### 1. Create the Supabase project

1. Sign up at [supabase.com](https://supabase.com) and create a new project. Pick the **Frankfurt (eu-central-1)** region and save the database password somewhere safe.
2. Go to **Project Settings → JWT Keys**. The current key should be an asymmetric one (ECC or RSA). If it's still the legacy shared secret, follow the prompt there to switch. The API refuses legacy-signed tokens on purpose.
3. Open **SQL Editor → New query**, paste the whole of `supabase/migrations/001_init.sql`, and click **Run**.

### 2. Run the API locally

You need Python 3.12 or newer.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Fill in `.env`:

- `DATABASE_URL`: in Supabase click **Connect → Session pooler** and copy the string. Put your database password in place of `[YOUR-PASSWORD]`. (The "direct connection" string only works on IPv6 networks, the session pooler works everywhere.)
- `SUPABASE_URL`: **Project Settings → API**, the Project URL.
- `SUPABASE_PUBLISHABLE_KEY`: **Project Settings → API Keys**, the publishable key (`sb_publishable_...`).

Then:

```bash
python scripts/import_questions.py       # loads data/questions.csv
uvicorn app.main:app --reload
```

Open http://localhost:8000/health and you should see `{"status":"ok"}`.

### 3. Play a question through the API docs

1. In Supabase go to **Authentication → Users → Add user → Create new user**, tick **Auto Confirm User**.
2. Get a token: `python scripts/get_token.py you@example.com`
3. Open http://localhost:8000/docs, click **Authorize**, paste the token.
4. Try `POST /solo/next`. Copy the `attempt_id`, then call `POST /solo/answer` with it and a `choice` (0 to 3, the position of the option you picked).

Tokens expire after an hour by default; just run step 2 again.

### 4. Run the tests

```bash
pytest
```

## API

| Endpoint | What it does |
|---|---|
| `GET /health` | Checks the database connection |
| `GET /me` | The signed-in player's profile and rating |
| `POST /solo/next` | Serves a question the player hasn't seen recently, with shuffled options and no answer |
| `POST /solo/answer` | Scores `{attempt_id, choice}` using server time, then reveals the solution |

Every serve and answer also writes a row to the `events` table. That log is the raw material for the analytics dashboard, question calibration and cheat detection later, so it's there from day one.

## Writing questions

Questions live in `backend/data/questions.csv`. Edit it in any spreadsheet app (in Google Sheets, Alt+Enter adds a line break inside a cell, which you need for code).

| Column | Notes |
|---|---|
| `slug` | Unique ID like `py-late-binding`. Never change it once imported, it's how updates are matched. |
| `format` | `predict_output`, `spot_bug` or `quickfire` |
| `category` | e.g. `python`, `sql`, `security`, `git` |
| `language` | Code language for syntax highlighting, or empty |
| `difficulty` | `easy`, `medium` or `hard` (sets the starting difficulty rating) |
| `prompt`, `code` | The question and optional code snippet. Indentation is kept exactly. |
| `option_a` … `option_d` | At least A and B. Fill in order, no gaps. |
| `correct` | `A`, `B`, `C` or `D` |
| `explanation` | Shown after answering. Explain *why*, it's where people learn. |
| `time_limit_s` | 5 to 300, default 30 |
| `status` | `active`, `draft` or `retired`. Retire questions instead of deleting them. |

Before importing, check the file without touching the database:

```bash
python scripts/import_questions.py --dry-run
```

The importer rejects the whole file if any row is broken, and re-importing never resets a question's difficulty rating.

**Always run predict-the-output snippets before importing.** One wrong answer key in a ranked match costs more trust than ten good questions earn.

## Deploying

The `backend/Dockerfile` runs on Render, Railway, Fly.io or similar; they set `$PORT` and you add the same variables as in `.env`. Not needed until the frontend exists.

## Roadmap

1. ✅ Database, API, sign-in, seed questions, event logging
2. React + TypeScript frontend with solo puzzle rush
3. 1v1 matches via friend link (WebSockets)
4. Matchmaking queue, Glicko-2 ratings, leaderboard
5. Data layer: question difficulty calibration, cheat flags, analytics dashboard
6. Polish and pilot at the uni coding cell
