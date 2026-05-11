from fastapi import APIRouter, HTTPException
from app.db import supabase

router = APIRouter()


@router.get("/teams")
def list_teams():
    res = supabase.table("teams").select("id, name").order("name").execute()
    return res.data or []


@router.get("/teams/{team_id}")
def get_team(team_id: int):
    team_res = supabase.table("teams").select("id, name").eq("id", team_id).limit(1).execute()
    if not team_res.data:
        raise HTTPException(status_code=404, detail="Team not found")
    team = team_res.data[0]

    all_matches = (
        supabase.table("matches")
        .select("id, season, winner_id, team1_id, team2_id")
        .or_(f"team1_id.eq.{team_id},team2_id.eq.{team_id}")
        .execute()
    )
    matches = all_matches.data or []

    wins = sum(1 for m in matches if m.get("winner_id") == team_id)
    losses = sum(
        1 for m in matches
        if m.get("winner_id") and m["winner_id"] != team_id
    )
    no_result = len(matches) - wins - losses

    by_season = {}
    for m in matches:
        s = m["season"]
        if s not in by_season:
            by_season[s] = {"played": 0, "won": 0, "lost": 0, "no_result": 0}
        by_season[s]["played"] += 1
        if m.get("winner_id") == team_id:
            by_season[s]["won"] += 1
        elif m.get("winner_id"):
            by_season[s]["lost"] += 1
        else:
            by_season[s]["no_result"] += 1

    return {
        "id": team["id"],
        "name": team["name"],
        "overall": {
            "played": len(matches),
            "won": wins,
            "lost": losses,
            "no_result": no_result,
        },
        "by_season": [
            {"season": s, **stats} for s, stats in sorted(by_season.items())
        ],
    }


@router.get("/teams/{team_id}/players")
def get_team_players(team_id: int):
    team_res = supabase.table("teams").select("id").eq("id", team_id).limit(1).execute()
    if not team_res.data:
        raise HTTPException(status_code=404, detail="Team not found")

    match_res = (
        supabase.table("matches")
        .select("id")
        .or_(f"team1_id.eq.{team_id},team2_id.eq.{team_id}")
        .execute()
    )
    match_ids = [m["id"] for m in (match_res.data or [])]
    if not match_ids:
        return []

    inn_res = (
        supabase.table("innings")
        .select("id")
        .eq("batting_team_id", team_id)
        .in_("match_id", match_ids)
        .execute()
    )
    inn_ids = [i["id"] for i in (inn_res.data or [])]
    if not inn_ids:
        return []

    del_res = (
        supabase.table("deliveries")
        .select("batter_id")
        .in_("innings_id", inn_ids)
        .execute()
    )
    player_ids = list({d["batter_id"] for d in (del_res.data or []) if d.get("batter_id")})
    if not player_ids:
        return []

    p_res = supabase.table("players").select("id, name").in_("id", player_ids).order("name").execute()
    return p_res.data or []
