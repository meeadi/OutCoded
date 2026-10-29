# OutCoded

**Chess.com for coding puzzles.** Quick, rated rounds of *predict the output*, *spot the bug* and quickfire questions, solo or head-to-head in live 1v1 **Code-Offs**.

As AI writes more of the code, the human job shifts to reading it, judging it and catching where it's wrong. OutCoded trains exactly that, and makes it competitive.

## Features

- **Solo rush:** sessions of 10 questions against a draining timer, keyboard-first (1–4 to answer, Enter for next). Ends with a rank (S to F), accuracy, average time, best streak and a per-question speed chart.
- **Code-Off:** challenge a friend with an invite link. Five rounds, same question at the same moment, points for being right plus a bonus for being fast. You see when your opponent locks in, but never what they picked.
- **Effects:** streak confetti, screen shake and red flash on wrong answers, "clutch!" and "too easy" stamps, a timer that panics in the last 5 seconds. One toggle turns them off, and the system's reduced-motion setting is respected automatically.
- **Themes:** midnight, paper and matcha, built on CSS variables.
- **Accounts:** email sign-in, usernames that are unique regardless of capitalisation, and goofy random name suggestions.

## How it works

**The server is the referee.** Everything that decides a score happens on the backend:

- The browser never receives the correct answer until the question is over.
- Response times are measured with the database clock, not the player's.
- Options are shuffled per attempt (and per player in a Code-Off), so "it's option 2" can't be shared.
- The database enforces this too: Row Level Security means signed-in users can't read questions, answers or match data, and can't change their own rating.

**Code-Offs run over WebSockets.** Each live match is a `MatchRoom` on the server. It picks the questions, starts every round for both players at once, scores answers, and declares the winner. Leaving mid-match counts as a forfeit. The full message protocol is documented at the top of `backend/app/match_room.py`.

**Every action is logged** to an `events` table (questions served, answers, matches started and finished). That log is the groundwork for question difficulty calibration, cheat detection and an analytics dashboard.

## Tech stack

| Part | Tech |
|---|---|
| Frontend | React 19, TypeScript, Vite, plain CSS with variables, canvas-confetti |
| Backend | Python 3.12, FastAPI, WebSockets, asyncpg |
| Database & auth | Supabase (PostgreSQL, Row Level Security, Supabase Auth with asymmetric JWT keys) |
| Testing | pytest, ruff |

## Project structure

```
OutCoded/
├── supabase/migrations/       database schema, run in order in the Supabase SQL Editor
│   ├── 001_init.sql           profiles, questions, attempts, events, security rules
│   ├── 002_usernames.sql      case-insensitive unique usernames
│   └── 003_matches.sql        Code-Off matches
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app
│   │   ├── auth.py            verifies Supabase sign-in tokens
│   │   ├── game.py            game rules: shuffling, timeouts, match points
│   │   ├── scoring.py         scores one answer (shared by solo and Code-Off)
│   │   ├── match_room.py      the live Code-Off referee
│   │   ├── question_bank.py   CSV validation
│   │   ├── events.py          analytics event log
│   │   └── routers/           /me, /solo, /matches, /ws/matches
│   ├── data/questions.csv     the question bank
│   ├── scripts/               import_questions.py, get_token.py
│   └── tests/
└── frontend/
    └── src/
        ├── App.tsx            themes, effects toggle, signed-in vs signed-out
        ├── components/        Home, Menu, PuzzleRush, CodeOff, QuestionCard, Results, ...
        └── lib/               api client, Supabase client, effects, session stats
```

## Running it locally

You need **Python 3.12+**, **Node.js 20+** and a free [Supabase](https://supabase.com) project.

### 1. Database

1. Create a Supabase project (region: Frankfurt).
2. In **Project Settings → JWT Keys**, make sure the current key is asymmetric (ECC or RSA), not the legacy shared secret.
3. In **SQL Editor**, run each file in `supabase/migrations/` **in order**: 001, then 002, then 003.
4. For development, turn off **Authentication → Sign In / Providers → Email → Confirm email**.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Fill in `backend/.env`:

| Variable | Where to find it |
|---|---|
| `DATABASE_URL` | Supabase → **Connect → Session pooler**. Replace `[YOUR-PASSWORD]` (brackets included). |
| `SUPABASE_URL` | **Project Settings → API**, Project URL |
| `SUPABASE_PUBLISHABLE_KEY` | **Project Settings → API Keys**, publishable key (`sb_publishable_...`) |
| `CORS_ORIGINS` | `http://localhost:5173` |

Then:

```bash
python scripts/import_questions.py
uvicorn app.main:app --reload
```

http://localhost:8000/health should show `{"status":"ok"}`. Interactive API docs are at http://localhost:8000/docs.

### 3. Frontend

In a second terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

Only public values go here, since anything prefixed `VITE_` ends up in the browser. The API address defaults to `http://localhost:8000`; set `VITE_API_URL` to change it.

```bash
npm run dev
```

Open http://localhost:5173, sign up, and pick a name.

### Playing a Code-Off against yourself

You need two accounts signed in at once. Use a normal window and a private/incognito window: press **2** in one, then open the invite link in the other.

## Tests

```bash
cd backend
pytest
```

```bash
cd frontend
npm run lint
npm run build      # also type-checks
```

## Writing questions

Questions live in `backend/data/questions.csv`.

| Column | Notes |
|---|---|
| `slug` | Unique ID like `py-late-binding`. Never change it after importing. |
| `format` | `predict_output`, `spot_bug` or `quickfire` |
| `category` | e.g. `python`, `sql`, `security`, `git` |
| `language` | Code language, or empty |
| `difficulty` | `easy`, `medium` or `hard` |
| `prompt`, `code` | The question and optional snippet. Indentation is kept exactly. |
| `option_a` … `option_d` | At least A and B, filled in order |
| `correct` | `A`, `B`, `C` or `D` |
| `explanation` | Shown after answering. Explain *why*. |
| `time_limit_s` | 5 to 300, default 30 |
| `status` | `active`, `draft` or `retired`. Retire instead of deleting. |

Check a file without touching the database, then import:

```bash
python scripts/import_questions.py --dry-run
python scripts/import_questions.py
```

The importer rejects the whole file if any row is broken, matches existing questions by slug, and never resets a question's difficulty rating. **Run every predict-the-output snippet before importing.** A wrong answer key in a ranked match costs more trust than ten good questions earn.

## Known limitations

- Live matches are kept in server memory: restarting the backend (including `--reload` after saving a Python file) ends matches in progress.
- Refreshing mid-match counts as leaving: there's no reconnecting yet.
- Invite links only work for people who can reach your server. They're `localhost` until it's deployed.

## Roadmap

- [x] Foundation: database, API, sign-in, question bank, event logging
- [x] Solo rush: themes, effects, sessions, results screen, usernames
- [x] Code-Off: live 1v1 matches with invite links
- [ ] Ranked: Glicko-2 ratings, matchmaking queue, leaderboard
- [ ] Data layer: self-calibrating question difficulty, cheat detection, analytics dashboard
- [ ] Original soundtrack and sound effects
- [ ] Reconnecting mid-match, deployment, and a pilot tournament at a university coding cell