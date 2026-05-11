# IPL API

A production-ready REST API for IPL cricket data, built with **FastAPI**, **Supabase (PostgreSQL)**, and deployable on **Railway**.

Data is sourced from [Cricsheet](https://cricsheet.org/matches/) JSON match files covering all IPL seasons.

---

## Overview

| Layer | Technology |
|---|---|
| Framework | FastAPI (Python) |
| Database | Supabase (PostgreSQL via `supabase-py`) |
| Auth | API key (SHA-256 HMAC, stored as hashes) |
| Rate limiting | 100 requests / day per key, tracked in DB |
| Deployment | Railway (`railway.toml`) |

---

## Getting Started (Local)

### 1. Clone and install

```bash
git clone <your-repo-url>
cd ipl-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, API_KEY_SECRET
```

### 3. Set up the database

In your Supabase project's SQL editor, run both SQL files in order:

```sql
-- 1. Create tables
\i sql/schema.sql

-- 2. Create indexes
\i sql/indexes.sql
```

Or paste their contents directly into the Supabase dashboard SQL editor.

### 4. Seed data

See [Seeding Data](#seeding-data) below.

### 5. Run the API

```bash
uvicorn app.main:app --reload
```

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API explorer.

---

## Seeding Data

### Download IPL JSONs from Cricsheet

1. Go to [https://cricsheet.org/matches/](https://cricsheet.org/matches/)
2. Download the **IPL JSON** zip file
3. Extract it to a local folder, e.g. `./data/ipl_json/`

### Run the seed script

```bash
python scripts/seed.py ./data/ipl_json
```

The script is fully **idempotent** — it safely skips matches already in the database. You can re-run it whenever new match files are added.

Sample output:

```
Found 1247 JSON files in ./data/ipl_json

[1/1247] Loaded: 335982.json
[2/1247] Loaded: 335983.json
[3/1247] Skipped: 335984.json   ← already in DB
...

--- Summary ---
Loaded:  1244
Skipped: 3
Errors:  0
Total:   1247
```

---

## Authentication

### Register for an API key

```bash
curl -X POST https://your-api.railway.app/v1/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'
```

Response:

```json
{
  "api_key": "your_key_here",
  "message": "Store this key safely. It will not be shown again.",
  "rate_limit": "100 requests/day"
}
```

The plaintext key is shown **once** and never stored. Copy it immediately.

### Pass the key in requests

Include the key in the `x-api-key` header:

```bash
curl https://your-api.railway.app/v1/matches \
  -H "x-api-key: your_key_here"
```

---

## Rate Limits

- **100 requests per day** per API key
- Limit resets at midnight UTC
- Exceeding the limit returns `429 Too Many Requests`

---

## Endpoints

All endpoints are prefixed with `/v1`.

### Registration

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/register` | Register email and receive an API key |

### Matches

| Method | Path | Query Params | Description |
|---|---|---|---|
| `GET` | `/v1/matches` | `season`, `team`, `venue` | List all matches |
| `GET` | `/v1/matches/{id}` | — | Match detail with innings summaries |
| `GET` | `/v1/matches/{id}/scorecard` | — | Full batting & bowling scorecard |
| `GET` | `/v1/matches/{id}/deliveries` | — | Ball-by-ball delivery log |

**Example — list matches for IPL 2023:**

```bash
curl "/v1/matches?season=2023" -H "x-api-key: ..."
```

```json
[
  {
    "id": 1,
    "date": "2023-03-31",
    "season": "2023",
    "venue": "Narendra Modi Stadium",
    "team1": "Gujarat Titans",
    "team2": "Chennai Super Kings",
    "winner": "Gujarat Titans",
    "player_of_match": "Shubman Gill"
  }
]
```

### Teams

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/teams` | List all teams |
| `GET` | `/v1/teams/{id}` | Team detail with win/loss record by season |
| `GET` | `/v1/teams/{id}/players` | All players who have batted for this team |

### Players

| Method | Path | Query Params | Description |
|---|---|---|---|
| `GET` | `/v1/players` | `name` | List/search players |
| `GET` | `/v1/players/{id}` | — | Player detail |
| `GET` | `/v1/players/{id}/batting` | — | Career batting stats |
| `GET` | `/v1/players/{id}/bowling` | — | Career bowling stats |

**Example — batting stats:**

```json
{
  "player": "Virat Kohli",
  "matches": 237,
  "innings": 232,
  "runs": 7263,
  "balls": 5194,
  "average": 37.03,
  "strike_rate": 129.82,
  "fifties": 50,
  "hundreds": 8,
  "highest_score": 113
}
```

---

## Deploying to Railway

1. Push this repo to GitHub.
2. In [Railway](https://railway.app), create a **New Project → Deploy from GitHub repo**.
3. Add the following environment variables in the Railway dashboard:

   | Variable | Value |
   |---|---|
   | `SUPABASE_URL` | Your Supabase project URL |
   | `SUPABASE_SERVICE_ROLE_KEY` | Your service role key |
   | `API_KEY_SECRET` | A long random secret string |

4. Railway auto-detects `railway.toml` and deploys with:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Visit your Railway-assigned domain to confirm the API is live.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes — keep new routes RESTful and add them to the appropriate router file.
3. Test locally with `uvicorn app.main:app --reload`.
4. Open a pull request with a clear description of your change.

Please do not commit `.env` files or credentials.
