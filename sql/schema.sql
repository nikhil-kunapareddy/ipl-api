-- Teams
CREATE TABLE IF NOT EXISTS teams (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

-- Players
CREATE TABLE IF NOT EXISTS players (
  id SERIAL PRIMARY KEY,
  cricsheet_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL
);

-- Matches
CREATE TABLE IF NOT EXISTS matches (
  id SERIAL PRIMARY KEY,
  cricsheet_file TEXT UNIQUE NOT NULL,
  season TEXT NOT NULL,
  date DATE NOT NULL,
  venue TEXT,
  city TEXT,
  match_number INTEGER,
  team1_id INTEGER REFERENCES teams(id),
  team2_id INTEGER REFERENCES teams(id),
  toss_winner_id INTEGER REFERENCES teams(id),
  toss_decision TEXT,
  winner_id INTEGER REFERENCES teams(id),
  win_by_runs INTEGER,
  win_by_wickets INTEGER,
  player_of_match_id INTEGER REFERENCES players(id),
  match_type TEXT,
  overs INTEGER
);

-- Innings
CREATE TABLE IF NOT EXISTS innings (
  id SERIAL PRIMARY KEY,
  match_id INTEGER REFERENCES matches(id),
  innings_number INTEGER NOT NULL,
  batting_team_id INTEGER REFERENCES teams(id),
  total_runs INTEGER,
  total_wickets INTEGER,
  total_overs NUMERIC(4,1)
);

-- Deliveries
CREATE TABLE IF NOT EXISTS deliveries (
  id SERIAL PRIMARY KEY,
  innings_id INTEGER REFERENCES innings(id),
  over_number INTEGER NOT NULL,
  ball_number INTEGER NOT NULL,
  batter_id INTEGER REFERENCES players(id),
  bowler_id INTEGER REFERENCES players(id),
  non_striker_id INTEGER REFERENCES players(id),
  runs_batter INTEGER DEFAULT 0,
  runs_extras INTEGER DEFAULT 0,
  runs_total INTEGER DEFAULT 0,
  extras_type TEXT,
  is_wicket BOOLEAN DEFAULT FALSE
);

-- Wickets
CREATE TABLE IF NOT EXISTS wickets (
  id SERIAL PRIMARY KEY,
  delivery_id INTEGER REFERENCES deliveries(id),
  player_out_id INTEGER REFERENCES players(id),
  kind TEXT,
  fielder_id INTEGER REFERENCES players(id)
);

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  key_hash TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE
);

-- Request Counts
CREATE TABLE IF NOT EXISTS request_counts (
  id SERIAL PRIMARY KEY,
  key_hash TEXT NOT NULL,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  count INTEGER DEFAULT 0,
  UNIQUE(key_hash, date)
);
