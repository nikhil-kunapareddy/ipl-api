from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.db import supabase

router = APIRouter()


@router.get("/players")
def list_players(name: Optional[str] = Query(None)):
    query = supabase.table("players").select("id, name, cricsheet_id")
    if name:
        query = query.ilike("name", f"%{name}%")
    res = query.order("name").execute()
    return res.data or []


@router.get("/players/{player_id}")
def get_player(player_id: int):
    res = supabase.table("players").select("*").eq("id", player_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Player not found")
    return res.data[0]


@router.get("/players/{player_id}/batting")
def get_batting_stats(player_id: int):
    p_res = supabase.table("players").select("id, name").eq("id", player_id).limit(1).execute()
    if not p_res.data:
        raise HTTPException(status_code=404, detail="Player not found")
    player = p_res.data[0]

    del_res = (
        supabase.table("deliveries")
        .select("id, innings_id, runs_batter, is_wicket")
        .eq("batter_id", player_id)
        .execute()
    )
    deliveries = del_res.data or []

    if not deliveries:
        return {
            "player": player["name"],
            "matches": 0,
            "innings": 0,
            "runs": 0,
            "balls": 0,
            "average": None,
            "strike_rate": None,
            "fifties": 0,
            "hundreds": 0,
            "highest_score": 0,
        }

    del_ids = [d["id"] for d in deliveries if d["is_wicket"]]
    dismissed_deliveries = set()
    if del_ids:
        w_res = (
            supabase.table("wickets")
            .select("delivery_id")
            .in_("delivery_id", del_ids)
            .eq("player_out_id", player_id)
            .execute()
        )
        dismissed_deliveries = {w["delivery_id"] for w in (w_res.data or [])}

    inn_res = (
        supabase.table("innings")
        .select("id, match_id")
        .in_("id", list({d["innings_id"] for d in deliveries}))
        .execute()
    )
    inn_to_match = {i["id"]: i["match_id"] for i in (inn_res.data or [])}

    innings_stats = {}
    for d in deliveries:
        iid = d["innings_id"]
        if iid not in innings_stats:
            innings_stats[iid] = {"runs": 0, "balls": 0, "dismissed": False}
        innings_stats[iid]["runs"] += d["runs_batter"]
        innings_stats[iid]["balls"] += 1
        if d["id"] in dismissed_deliveries:
            innings_stats[iid]["dismissed"] = True

    total_runs = sum(s["runs"] for s in innings_stats.values())
    total_balls = sum(s["balls"] for s in innings_stats.values())
    dismissals = sum(1 for s in innings_stats.values() if s["dismissed"])
    innings_count = len(innings_stats)
    matches = len({inn_to_match.get(iid) for iid in innings_stats})

    scores = [s["runs"] for s in innings_stats.values()]
    fifties = sum(1 for s in scores if 50 <= s < 100)
    hundreds = sum(1 for s in scores if s >= 100)
    highest = max(scores) if scores else 0

    average = round(total_runs / dismissals, 2) if dismissals else None
    strike_rate = round(total_runs / total_balls * 100, 2) if total_balls else None

    return {
        "player": player["name"],
        "matches": matches,
        "innings": innings_count,
        "runs": total_runs,
        "balls": total_balls,
        "average": average,
        "strike_rate": strike_rate,
        "fifties": fifties,
        "hundreds": hundreds,
        "highest_score": highest,
    }


@router.get("/players/{player_id}/bowling")
def get_bowling_stats(player_id: int):
    p_res = supabase.table("players").select("id, name").eq("id", player_id).limit(1).execute()
    if not p_res.data:
        raise HTTPException(status_code=404, detail="Player not found")
    player = p_res.data[0]

    del_res = (
        supabase.table("deliveries")
        .select("id, innings_id, runs_total, runs_extras, extras_type, is_wicket")
        .eq("bowler_id", player_id)
        .execute()
    )
    deliveries = del_res.data or []

    if not deliveries:
        return {
            "player": player["name"],
            "matches": 0,
            "wickets": 0,
            "balls": 0,
            "runs_conceded": 0,
            "economy": None,
            "average": None,
            "best_figures": None,
        }

    del_ids = [d["id"] for d in deliveries if d["is_wicket"]]
    wickets_map = {}
    if del_ids:
        w_res = (
            supabase.table("wickets")
            .select("delivery_id, kind")
            .in_("delivery_id", del_ids)
            .execute()
        )
        wickets_map = {w["delivery_id"]: w["kind"] for w in (w_res.data or [])}

    non_credit_kinds = {"run out", "retired hurt", "obstructing the field"}
    wide_noball = {"wides", "noballs"}

    inn_res = (
        supabase.table("innings")
        .select("id, match_id")
        .in_("id", list({d["innings_id"] for d in deliveries}))
        .execute()
    )
    inn_to_match = {i["id"]: i["match_id"] for i in (inn_res.data or [])}

    innings_stats = {}
    for d in deliveries:
        iid = d["innings_id"]
        if iid not in innings_stats:
            innings_stats[iid] = {"balls": 0, "runs": 0, "wickets": 0}
        # wides and no-balls don't count as legal deliveries
        if d["extras_type"] not in wide_noball:
            innings_stats[iid]["balls"] += 1
        # runs conceded: exclude byes and leg-byes
        if d["extras_type"] not in ("byes", "legbyes"):
            innings_stats[iid]["runs"] += d["runs_total"]
        if d["is_wicket"] and d["id"] in wickets_map:
            if wickets_map[d["id"]] not in non_credit_kinds:
                innings_stats[iid]["wickets"] += 1

    total_balls = sum(s["balls"] for s in innings_stats.values())
    total_runs = sum(s["runs"] for s in innings_stats.values())
    total_wickets = sum(s["wickets"] for s in innings_stats.values())
    matches = len({inn_to_match.get(iid) for iid in innings_stats})

    economy = round(total_runs / (total_balls / 6), 2) if total_balls >= 6 else None
    average = round(total_runs / total_wickets, 2) if total_wickets else None

    best = None
    if innings_stats:
        best_inn = max(innings_stats.values(), key=lambda s: (s["wickets"], -s["runs"]))
        best = f"{best_inn['wickets']}/{best_inn['runs']}"

    return {
        "player": player["name"],
        "matches": matches,
        "wickets": total_wickets,
        "balls": total_balls,
        "runs_conceded": total_runs,
        "economy": economy,
        "average": average,
        "best_figures": best,
    }
