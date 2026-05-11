from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.db import supabase

router = APIRouter()


def _team_name(team_id, teams_map):
    return teams_map.get(team_id)


def _player_name(player_id, players_map):
    return players_map.get(player_id)


@router.get("/matches")
def list_matches(
    season: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    venue: Optional[str] = Query(None),
):
    query = supabase.table("matches").select(
        "id, date, season, venue, city, match_number, match_type, "
        "team1_id, team2_id, winner_id, player_of_match_id, "
        "win_by_runs, win_by_wickets"
    )
    if season:
        query = query.eq("season", season)
    if venue:
        query = query.ilike("venue", f"%{venue}%")

    result = query.order("date").execute()
    matches = result.data or []

    if not matches:
        return []

    team_ids = set()
    player_ids = set()
    for m in matches:
        for k in ("team1_id", "team2_id", "winner_id"):
            if m.get(k):
                team_ids.add(m[k])
        if m.get("player_of_match_id"):
            player_ids.add(m["player_of_match_id"])

    teams_map = {}
    if team_ids:
        t_res = supabase.table("teams").select("id, name").in_("id", list(team_ids)).execute()
        teams_map = {r["id"]: r["name"] for r in (t_res.data or [])}

    players_map = {}
    if player_ids:
        p_res = supabase.table("players").select("id, name").in_("id", list(player_ids)).execute()
        players_map = {r["id"]: r["name"] for r in (p_res.data or [])}

    output = []
    for m in matches:
        t1 = teams_map.get(m["team1_id"], "")
        t2 = teams_map.get(m["team2_id"], "")
        # team filter applied post-fetch (team name contains)
        if team and team.lower() not in t1.lower() and team.lower() not in t2.lower():
            continue
        output.append({
            "id": m["id"],
            "date": m["date"],
            "season": m["season"],
            "venue": m["venue"],
            "city": m["city"],
            "match_number": m["match_number"],
            "match_type": m["match_type"],
            "team1": t1,
            "team2": t2,
            "winner": teams_map.get(m["winner_id"]),
            "win_by_runs": m["win_by_runs"],
            "win_by_wickets": m["win_by_wickets"],
            "player_of_match": players_map.get(m["player_of_match_id"]),
        })
    return output


@router.get("/matches/{match_id}")
def get_match(match_id: int):
    m_res = supabase.table("matches").select("*").eq("id", match_id).limit(1).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Match not found")
    m = m_res.data[0]

    team_ids = [v for k, v in m.items() if k.endswith("_id") and "team" in k and v]
    player_ids = [m["player_of_match_id"]] if m.get("player_of_match_id") else []

    teams_map = {}
    if team_ids:
        t_res = supabase.table("teams").select("id, name").in_("id", team_ids).execute()
        teams_map = {r["id"]: r["name"] for r in (t_res.data or [])}

    players_map = {}
    if player_ids:
        p_res = supabase.table("players").select("id, name").in_("id", player_ids).execute()
        players_map = {r["id"]: r["name"] for r in (p_res.data or [])}

    inn_res = supabase.table("innings").select(
        "id, innings_number, batting_team_id, total_runs, total_wickets, total_overs"
    ).eq("match_id", match_id).order("innings_number").execute()

    innings = []
    for i in inn_res.data or []:
        innings.append({
            "innings_number": i["innings_number"],
            "batting_team": teams_map.get(i["batting_team_id"]),
            "total_runs": i["total_runs"],
            "total_wickets": i["total_wickets"],
            "total_overs": i["total_overs"],
        })

    return {
        "id": m["id"],
        "cricsheet_file": m["cricsheet_file"],
        "season": m["season"],
        "date": m["date"],
        "venue": m["venue"],
        "city": m["city"],
        "match_number": m["match_number"],
        "match_type": m["match_type"],
        "overs": m["overs"],
        "team1": teams_map.get(m["team1_id"]),
        "team2": teams_map.get(m["team2_id"]),
        "toss_winner": teams_map.get(m["toss_winner_id"]),
        "toss_decision": m["toss_decision"],
        "winner": teams_map.get(m["winner_id"]),
        "win_by_runs": m["win_by_runs"],
        "win_by_wickets": m["win_by_wickets"],
        "player_of_match": players_map.get(m["player_of_match_id"]),
        "innings": innings,
    }


@router.get("/matches/{match_id}/scorecard")
def get_scorecard(match_id: int):
    m_res = supabase.table("matches").select("id").eq("id", match_id).limit(1).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Match not found")

    inn_res = supabase.table("innings").select(
        "id, innings_number, batting_team_id, total_runs, total_wickets, total_overs"
    ).eq("match_id", match_id).order("innings_number").execute()

    if not inn_res.data:
        return {"innings": []}

    team_ids = list({i["batting_team_id"] for i in inn_res.data if i.get("batting_team_id")})
    teams_map = {}
    if team_ids:
        t_res = supabase.table("teams").select("id, name").in_("id", team_ids).execute()
        teams_map = {r["id"]: r["name"] for r in (t_res.data or [])}

    scorecard = []
    for inn in inn_res.data:
        inn_id = inn["id"]

        del_res = supabase.table("deliveries").select(
            "id, over_number, ball_number, batter_id, bowler_id, "
            "runs_batter, runs_extras, runs_total, extras_type, is_wicket"
        ).eq("innings_id", inn_id).execute()
        deliveries = del_res.data or []

        del_ids = [d["id"] for d in deliveries if d["is_wicket"]]
        wickets_map = {}
        if del_ids:
            w_res = supabase.table("wickets").select(
                "delivery_id, player_out_id, kind"
            ).in_("delivery_id", del_ids).execute()
            for w in w_res.data or []:
                wickets_map[w["delivery_id"]] = w

        player_ids = set()
        for d in deliveries:
            player_ids.update([d["batter_id"], d["bowler_id"]])
        players_map = {}
        if player_ids:
            p_res = supabase.table("players").select("id, name").in_("id", list(player_ids)).execute()
            players_map = {r["id"]: r["name"] for r in (p_res.data or [])}

        # batting stats
        batting = {}
        for d in deliveries:
            bid = d["batter_id"]
            if bid not in batting:
                batting[bid] = {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissed": False}
            batting[bid]["balls"] += 1
            batting[bid]["runs"] += d["runs_batter"]
            if d["runs_batter"] == 4:
                batting[bid]["fours"] += 1
            if d["runs_batter"] == 6:
                batting[bid]["sixes"] += 1
            if d["is_wicket"] and d["id"] in wickets_map:
                w = wickets_map[d["id"]]
                if w["player_out_id"] == bid:
                    batting[bid]["dismissed"] = True

        batting_list = []
        for pid, stats in batting.items():
            sr = round(stats["runs"] / stats["balls"] * 100, 2) if stats["balls"] else 0
            batting_list.append({
                "player": players_map.get(pid),
                "runs": stats["runs"],
                "balls": stats["balls"],
                "fours": stats["fours"],
                "sixes": stats["sixes"],
                "strike_rate": sr,
                "dismissed": stats["dismissed"],
            })

        # bowling stats
        bowling = {}
        for d in deliveries:
            bwid = d["bowler_id"]
            if bwid not in bowling:
                bowling[bwid] = {"balls": 0, "runs": 0, "wickets": 0}
            bowling[bwid]["balls"] += 1
            bowling[bwid]["runs"] += d["runs_total"] - d["runs_extras"] if d["extras_type"] in ("wides", "noballs") else d["runs_total"]
            if d["is_wicket"] and d["id"] in wickets_map:
                w = wickets_map[d["id"]]
                if w["kind"] not in ("run out", "retired hurt", "obstructing the field"):
                    bowling[bwid]["wickets"] += 1

        bowling_list = []
        for pid, stats in bowling.items():
            overs_bowled = stats["balls"] // 6 + (stats["balls"] % 6) / 10
            economy = round(stats["runs"] / (stats["balls"] / 6), 2) if stats["balls"] >= 6 else None
            bowling_list.append({
                "player": players_map.get(pid),
                "overs": round(overs_bowled, 1),
                "runs": stats["runs"],
                "wickets": stats["wickets"],
                "economy": economy,
            })

        scorecard.append({
            "innings_number": inn["innings_number"],
            "batting_team": teams_map.get(inn["batting_team_id"]),
            "total_runs": inn["total_runs"],
            "total_wickets": inn["total_wickets"],
            "total_overs": inn["total_overs"],
            "batting": batting_list,
            "bowling": bowling_list,
        })

    return {"innings": scorecard}


@router.get("/matches/{match_id}/deliveries")
def get_deliveries(match_id: int):
    m_res = supabase.table("matches").select("id").eq("id", match_id).limit(1).execute()
    if not m_res.data:
        raise HTTPException(status_code=404, detail="Match not found")

    inn_res = supabase.table("innings").select(
        "id, innings_number, batting_team_id"
    ).eq("match_id", match_id).order("innings_number").execute()

    if not inn_res.data:
        return {"innings": []}

    team_ids = list({i["batting_team_id"] for i in inn_res.data if i.get("batting_team_id")})
    teams_map = {}
    if team_ids:
        t_res = supabase.table("teams").select("id, name").in_("id", team_ids).execute()
        teams_map = {r["id"]: r["name"] for r in (t_res.data or [])}

    result = []
    for inn in inn_res.data:
        del_res = supabase.table("deliveries").select(
            "id, over_number, ball_number, batter_id, bowler_id, non_striker_id, "
            "runs_batter, runs_extras, runs_total, extras_type, is_wicket"
        ).eq("innings_id", inn["id"]).order("over_number").order("ball_number").execute()
        deliveries = del_res.data or []

        player_ids = set()
        for d in deliveries:
            player_ids.update(filter(None, [d["batter_id"], d["bowler_id"], d["non_striker_id"]]))
        players_map = {}
        if player_ids:
            p_res = supabase.table("players").select("id, name").in_("id", list(player_ids)).execute()
            players_map = {r["id"]: r["name"] for r in (p_res.data or [])}

        del_ids = [d["id"] for d in deliveries if d["is_wicket"]]
        wickets_map = {}
        if del_ids:
            w_res = supabase.table("wickets").select(
                "delivery_id, player_out_id, kind, fielder_id"
            ).in_("delivery_id", del_ids).execute()
            for w in w_res.data or []:
                wickets_map[w["delivery_id"]] = w

        balls = []
        for d in deliveries:
            wicket = None
            if d["is_wicket"] and d["id"] in wickets_map:
                w = wickets_map[d["id"]]
                wicket = {
                    "player_out": players_map.get(w["player_out_id"]),
                    "kind": w["kind"],
                    "fielder": players_map.get(w["fielder_id"]) if w.get("fielder_id") else None,
                }
            balls.append({
                "over": d["over_number"],
                "ball": d["ball_number"],
                "batter": players_map.get(d["batter_id"]),
                "bowler": players_map.get(d["bowler_id"]),
                "non_striker": players_map.get(d["non_striker_id"]),
                "runs_batter": d["runs_batter"],
                "runs_extras": d["runs_extras"],
                "runs_total": d["runs_total"],
                "extras_type": d["extras_type"],
                "wicket": wicket,
            })

        result.append({
            "innings_number": inn["innings_number"],
            "batting_team": teams_map.get(inn["batting_team_id"]),
            "deliveries": balls,
        })

    return {"innings": result}
