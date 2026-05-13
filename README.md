# IPL API

A free REST API for IPL cricket data — every match, every ball, every player, going back to the first season. Data comes from [Cricsheet](https://cricsheet.org/matches/).

Use it to build dashboards, fantasy tools, stats explorers, or anything else you want to do with ball-by-ball IPL data.

---

## Quick start

You need three things to make a request: a base URL, an API key, and an endpoint.

```bash
# 1. Register your email to get a key (one-time)
curl -X POST https://your-api.railway.app/v1/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'

# 2. Use the key in every other request
curl https://your-api.railway.app/v1/matches?season=2023 \
  -H "x-api-key: your_key_here"
```

That's it. The rest of this guide is reference.

---

## Getting an API key

`POST /v1/register` with your email returns a key:

```json
{
  "api_key": "abc123...",
  "message": "Store this key safely. It will not be shown again.",
  "rate_limit": "100 requests/day"
}
```

Important things to know:

- **The key is shown once.** Copy it into a password manager or `.env` file immediately — there is no "recover key" endpoint.
- **One key per email.** Registering the same email twice returns `409 Conflict`.
- **Pass the key as `x-api-key`** in every request to `/v1/...`. Missing or invalid keys return `401`.

---

## Rate limits

- **100 requests per day** per key
- Counter resets at midnight UTC
- Over the limit → `429 Too Many Requests`

If 100/day isn't enough for what you're building, reach out.

---

## Browse interactively

The fastest way to explore is the live Swagger UI at:

```
https://your-api.railway.app/docs
```

You can paste your API key in the "Authorize" button and call any endpoint from the browser.

---

## Endpoints

All endpoints are `GET` (except `/register`) and live under `/v1`.

### Matches

| Path | What you get |
|---|---|
| `/v1/matches` | List of matches. Filter with `?season=2023`, `?team=Mumbai`, `?venue=Wankhede` |
| `/v1/matches/{id}` | One match — teams, toss, result, innings totals |
| `/v1/matches/{id}/scorecard` | Full batting & bowling card for both innings |
| `/v1/matches/{id}/deliveries` | Ball-by-ball: every delivery with batter, bowler, runs, wickets |

Example — list IPL 2023 matches:

```bash
curl "https://your-api.railway.app/v1/matches?season=2023" \
  -H "x-api-key: $KEY"
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

### Players

| Path | What you get |
|---|---|
| `/v1/players` | List players. Search with `?name=kohli` |
| `/v1/players/{id}` | Player profile |
| `/v1/players/{id}/batting` | Career batting: runs, average, strike rate, 50s/100s, HS |
| `/v1/players/{id}/bowling` | Career bowling: wickets, economy, average, best figures |

Example — Kohli's batting stats:

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

### Teams

| Path | What you get |
|---|---|
| `/v1/teams` | List of all teams |
| `/v1/teams/{id}` | Overall W/L record + season-by-season breakdown |
| `/v1/teams/{id}/players` | Every player who has batted for the team |

---

## Common recipes

**"What's the score of match 42?"**
```bash
curl https://your-api.railway.app/v1/matches/42/scorecard -H "x-api-key: $KEY"
```

**"Find a player by name, then get their stats."**
```bash
curl "https://your-api.railway.app/v1/players?name=bumrah" -H "x-api-key: $KEY"
# → use the id from the response
curl https://your-api.railway.app/v1/players/57/bowling -H "x-api-key: $KEY"
```

**"All Mumbai Indians matches in 2024."**
```bash
curl "https://your-api.railway.app/v1/matches?season=2024&team=Mumbai" -H "x-api-key: $KEY"
```

**"Every ball of an IPL final."**
```bash
curl https://your-api.railway.app/v1/matches/1234/deliveries -H "x-api-key: $KEY"
```

---

## Errors

| Status | Meaning |
|---|---|
| `401 Unauthorized` | Missing or invalid `x-api-key` header |
| `404 Not Found` | The match / player / team ID doesn't exist |
| `409 Conflict` | Email already registered |
| `422 Unprocessable Entity` | Bad input (e.g. invalid email format) |
| `429 Too Many Requests` | You've hit the 100/day limit |

---
