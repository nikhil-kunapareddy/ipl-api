"""
Bulk-load Cricsheet IPL JSON files into Supabase.

Usage:
    python scripts/seed.py ./data/ipl_json
"""

import sys
import os
import json
import glob
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def upsert_team(name: str, cache: dict) -> int:
    if name in cache:
        return cache[name]
    res = supabase.table("teams").upsert({"name": name}, on_conflict="name").execute()
    row = res.data[0]
    cache[name] = row["id"]
    return row["id"]


def upsert_player(cricsheet_id: str, player_name: str, cache: dict) -> int:
    if cricsheet_id in cache:
        return cache[cricsheet_id]
    res = supabase.table("players").upsert(
        {"cricsheet_id": cricsheet_id, "name": player_name},
        on_conflict="cricsheet_id",
    ).execute()
    row = res.data[0]
    cache[cricsheet_id] = row["id"]
    return row["id"]


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_file(path: Path, teams_cache: dict, players_cache: dict) -> str:
    """Return 'loaded', 'skipped', or raise on error."""
    filename = path.name

    # idempotency check
    existing = (
        supabase.table("matches")
        .select("id")
        .eq("cricsheet_file", filename)
        .limit(1)
        .execute()
    )
    if existing.data:
        return "skipped"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = data.get("info", {})
    registry = info.get("registry", {}).get("people", {})

    # teams
    team_names = info.get("teams", [])
    if len(team_names) < 2:
        raise ValueError("Less than 2 teams in match info")

    team1_id = upsert_team(team_names[0], teams_cache)
    team2_id = upsert_team(team_names[1], teams_cache)

    # players: upsert all players listed in the registry
    # Cricsheet registry format: {player_name: cricsheet_id}
    for player_name, cricsheet_id in registry.items():
        upsert_player(cricsheet_id, player_name, players_cache)

    # toss
    toss = info.get("toss", {})
    toss_winner_name = toss.get("winner")
    toss_winner_id = teams_cache.get(toss_winner_name) if toss_winner_name else None

    # outcome / winner
    outcome = info.get("outcome", {})
    winner_name = outcome.get("winner")
    winner_id = teams_cache.get(winner_name) if winner_name else None
    win_by = outcome.get("by", {})
    win_by_runs = win_by.get("runs")
    win_by_wickets = win_by.get("wickets")

    # player of match (Cricsheet stores names here, not IDs)
    pom_names = info.get("player_of_match", [])
    player_of_match_id = None
    if pom_names:
        pom_name = pom_names[0]
        pom_cid = _resolve_cricsheet_id(registry, pom_name)
        if pom_cid:
            player_of_match_id = upsert_player(pom_cid, pom_name, players_cache)

    # dates
    dates = info.get("dates", [])
    match_date = dates[0] if dates else None

    season = str(info.get("season", ""))

    match_row = {
        "cricsheet_file": filename,
        "season": season,
        "date": match_date,
        "venue": info.get("venue"),
        "city": info.get("city"),
        "match_number": info.get("event", {}).get("match_number"),
        "team1_id": team1_id,
        "team2_id": team2_id,
        "toss_winner_id": toss_winner_id,
        "toss_decision": toss.get("decision"),
        "winner_id": winner_id,
        "win_by_runs": win_by_runs,
        "win_by_wickets": win_by_wickets,
        "player_of_match_id": player_of_match_id,
        "match_type": info.get("match_type"),
        "overs": info.get("overs"),
    }

    match_res = supabase.table("matches").insert(match_row).execute()
    match_id = match_res.data[0]["id"]

    # innings
    raw_innings = data.get("innings", [])
    for inn_num, inn_data in enumerate(raw_innings, start=1):
        batting_team_name = inn_data.get("team")
        batting_team_id = teams_cache.get(batting_team_name) if batting_team_name else None

        total_runs = 0
        total_wickets = 0
        ball_count = 0  # legal deliveries for overs calculation

        # insert innings placeholder, update totals after processing deliveries
        inn_res = supabase.table("innings").insert({
            "match_id": match_id,
            "innings_number": inn_num,
            "batting_team_id": batting_team_id,
            "total_runs": 0,
            "total_wickets": 0,
            "total_overs": 0,
        }).execute()
        innings_id = inn_res.data[0]["id"]

        deliveries_batch = []
        wickets_batch = []

        for over_data in inn_data.get("overs", []):
            over_number = over_data.get("over", 0)
            for ball_idx, delivery in enumerate(over_data.get("deliveries", []), start=1):
                runs = delivery.get("runs", {})
                runs_batter = runs.get("batter", 0)
                runs_extras = runs.get("extras", 0)
                runs_total = runs.get("total", 0)

                extras = delivery.get("extras", {})
                extras_type = next(iter(extras.keys()), None) if extras else None

                is_wide = "wides" in extras
                is_noball = "noballs" in extras
                if not is_wide and not is_noball:
                    ball_count += 1

                total_runs += runs_total

                is_wicket = bool(delivery.get("wickets"))

                batter_name = delivery.get("batter", "")
                bowler_name = delivery.get("bowler", "")
                non_striker_name = delivery.get("non_striker", "")

                batter_cid = _resolve_cricsheet_id(registry, batter_name)
                bowler_cid = _resolve_cricsheet_id(registry, bowler_name)
                non_striker_cid = _resolve_cricsheet_id(registry, non_striker_name)

                batter_db_id = upsert_player(batter_cid, batter_name, players_cache) if batter_cid else None
                bowler_db_id = upsert_player(bowler_cid, bowler_name, players_cache) if bowler_cid else None
                non_striker_db_id = upsert_player(non_striker_cid, non_striker_name, players_cache) if non_striker_cid else None

                deliveries_batch.append({
                    "innings_id": innings_id,
                    "over_number": over_number,
                    "ball_number": ball_idx,
                    "batter_id": batter_db_id,
                    "bowler_id": bowler_db_id,
                    "non_striker_id": non_striker_db_id,
                    "runs_batter": runs_batter,
                    "runs_extras": runs_extras,
                    "runs_total": runs_total,
                    "extras_type": extras_type,
                    "is_wicket": is_wicket,
                })

                if is_wicket:
                    for w in delivery.get("wickets", []):
                        player_out_name = w.get("player_out", "")
                        player_out_cid = _resolve_cricsheet_id(registry, player_out_name)
                        player_out_id = upsert_player(player_out_cid, player_out_name, players_cache) if player_out_cid else None

                        fielders = w.get("fielders", [])
                        fielder_name = fielders[0].get("name") if fielders else None
                        fielder_id = None
                        if fielder_name:
                            f_cid = _resolve_cricsheet_id(registry, fielder_name)
                            fielder_id = upsert_player(f_cid, fielder_name, players_cache) if f_cid else None

                        total_wickets += 1
                        wickets_batch.append({
                            "_delivery_idx": len(deliveries_batch) - 1,
                            "player_out_id": player_out_id,
                            "kind": w.get("kind"),
                            "fielder_id": fielder_id,
                        })

        # insert deliveries in batches of 500
        delivery_ids = []
        for i in range(0, len(deliveries_batch), 500):
            chunk = deliveries_batch[i:i + 500]
            res = supabase.table("deliveries").insert(chunk).execute()
            delivery_ids.extend([r["id"] for r in res.data])

        # insert wickets
        if wickets_batch:
            wickets_to_insert = []
            for w in wickets_batch:
                del_id = delivery_ids[w["_delivery_idx"]]
                wickets_to_insert.append({
                    "delivery_id": del_id,
                    "player_out_id": w["player_out_id"],
                    "kind": w["kind"],
                    "fielder_id": w["fielder_id"],
                })
            supabase.table("wickets").insert(wickets_to_insert).execute()

        total_overs = ball_count // 6 + (ball_count % 6) / 10
        supabase.table("innings").update({
            "total_runs": total_runs,
            "total_wickets": total_wickets,
            "total_overs": round(total_overs, 1),
        }).eq("id", innings_id).execute()

    return "loaded"


def _resolve_cricsheet_id(registry: dict, player_name: str) -> str:
    """Look up cricsheet ID for a player name. Registry is {name: cricsheet_id}."""
    if not player_name:
        return None
    cid = registry.get(player_name)
    if cid:
        return cid
    # fall back: synthetic ID so the player still gets a row
    return f"name:{player_name}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed.py <path_to_ipl_json_folder>")
        sys.exit(1)

    folder = Path(sys.argv[1])
    if not folder.is_dir():
        print(f"Error: {folder} is not a directory")
        sys.exit(1)

    files = sorted(folder.glob("*.json"))
    total = len(files)
    if total == 0:
        print("No JSON files found.")
        sys.exit(0)

    print(f"Found {total} JSON files in {folder}\n")

    teams_cache: dict = {}
    players_cache: dict = {}

    # pre-warm caches from existing DB rows
    existing_teams = supabase.table("teams").select("id, name").execute()
    for t in existing_teams.data or []:
        teams_cache[t["name"]] = t["id"]

    existing_players = supabase.table("players").select("id, cricsheet_id").execute()
    for p in existing_players.data or []:
        players_cache[p["cricsheet_id"]] = p["id"]

    loaded = skipped = errors = 0
    for idx, path in enumerate(files, start=1):
        try:
            result = load_file(path, teams_cache, players_cache)
            if result == "loaded":
                loaded += 1
                print(f"[{idx}/{total}] Loaded: {path.name}")
            else:
                skipped += 1
                print(f"[{idx}/{total}] Skipped: {path.name}")
        except Exception as e:
            errors += 1
            print(f"[{idx}/{total}] ERROR {path.name}: {e}")

    print(f"\n--- Summary ---")
    print(f"Loaded:  {loaded}")
    print(f"Skipped: {skipped}")
    print(f"Errors:  {errors}")
    print(f"Total:   {total}")


if __name__ == "__main__":
    main()
