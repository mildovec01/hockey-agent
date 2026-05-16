import anthropic
import json
from datetime import datetime, date, timedelta
from json_repair import repair_json
from hockey_config import ANTHROPIC_API_KEY, FAVORITE_TEAMS, TEAM_ABBR
from tools.hockey_api import (
    get_matches_by_date, get_match_detail,
    get_standings, get_last_five_games,
    get_head_to_head, get_teams
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

WORLD_CHAMPIONSHIP_LEAGUE_ID = 95245
WORLD_CHAMPIONSHIP_SEASON = 2026

def get_abbr(team_name: str) -> str:
    return TEAM_ABBR.get(team_name, team_name[:3].upper())

def format_score_line(match: dict) -> str:
    home = match["homeTeam"]["name"]
    away = match["awayTeam"]["name"]
    score = match["state"]["score"]["current"]
    home_abbr = get_abbr(home)
    away_abbr = get_abbr(away)
    if score:
        return f"[{home_abbr}] {score['home'] : {score['away']} [{away_abbr}]}"
    return f"[{home_abbr}] - : - [{away_abbr}]"

def get_todays_matches(league_id: int = None) -> list:
    today = str(date.today())
    params = {"date": today}
    if league_id:
        params["leagueId"] = league_id
    from tools.hockey_api import get_matches_by_date
    return get_matches_by_date(today)

def get_favorite_matches_today() -> list:
    today = str(date.today())
    matches = []
    for team in FAVORITE_TEAMS:
        team_matches = get_matches_by_date(today, team_name=team)
        matches.extend(team_matches)
    seen = set()
    unique = []
    for m in matches:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    return unique

def get_upcoming_favorite_matches(days_ahead: int = 3) -> list:
    upcoming = []
    for i in range(1, days_ahead + 1):
        day = str(date.today() + timedelta(days=i))
        for team in FAVORITE_TEAMS:
            matches = get_matches_by_date(day, team_name=team)
            upcoming.extend(matches)
    seen = set()
    unique = []
    for m in upcoming:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    return unique

def format_standings_table(standings_data: dict) -> str:
    lines = []
    groups = standings_data.get("groups", [standings_data]) if "groups" in standings_data else [standings_data]
    for group in groups:
        name = group.get("name", "Tabulka")
        lines.append(f"**{name}**")
        lines.append("'Tým        Z     V     P     VPP     PPP     GF     GA     B")
        for t in group.get("standings", []):
            team = t.get("team", {})
            pos = t.get("position", "-")
            gp = t.get("gamesPlayed", 0)
            w = t.get("wins", 0)
            l = t.get("loses", 0)
            wot = t.get("winsOvertime", 0)
            lot = t.get("losesOvertime", 0)
            gf = t.get("scoredGoals", 0)
            ga = t.get("receivedGoals", 0)
            pts = w * 3 + wot * 2 + lot * 1
            name_short = team.get("name", "?")[:16].ljust(16)
            lines.append(f"`{pos}. {name_short} {gp:2} {w:2} {l:2} {wot:2}  {lot:2}  {gf:3} {ga:3} {pts:3}`")
        lines.append("")
    return "\n".join(lines)

def generate_pregame_report(match: dict) -> dict:
    home = match["homeTeam"]["name"]
    away = match["awayTeam"]["name"]
    home_id = match["homeTeam"]["id"]
    away_id = match["awayTeam"]["id"]
    match_time = match["date"]

    home_last5 = get_last_five_games(home_id)
    away_last5 = get_last_five_games(away_id)
    h2h = get_head_to_head(home_id, away_id)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system="""Jsi hokejový analytik. Dostaneš data o zápase a vrátíš JSON analýzu.
Vždy odpovídej POUZE validním JSON bez markdown bloků.""",
        messages=[{
            "role": "user",
            "content": f"""Analyzuj nadcházející hokejový zápas a vrať JSON:
{{
  "home_team": "{home}",
  "away_team": "{away}",
  "match_time": "{match_time}",
  "home_strengths": ["silná stránka 1", "silná stránka 2"],
  "home_weaknesses": ["slabá stránka 1"],
  "away_strengths": ["silná stránka 1", "silná stránka 2"],
  "away_weaknesses": ["slabá stránka 1"],
  "predicted_score": "3:2",
  "predicted_winner": "{home} nebo {away}",
  "win_probability": {{"home": 55, "away": 45}},
  "analysis": "Krátká analýza 2-3 věty",
  "key_factors": ["faktor 1", "faktor 2"]
}}

Poslední 5 zápasů {home}: {json.dumps(home_last5, ensure_ascii=False)}
Poslední 5 zápasů {away}: {json.dumps(away_last5, ensure_ascii=False)}
H2H: {json.dumps(h2h, ensure_ascii=False)}"""
        }]
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(repair_json(raw))


def generate_tournament_prediction(standings_data: dict) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system="""Jsi hokejový expert. Analyzuješ průběh turnaje a předpovídáš výsledky.
Vždy odpovídej POUZE validním JSON bez markdown bloků.""",
        messages=[{
            "role": "user",
            "content": f"""Na základě aktuálních tabulek MS předpověz výsledky turnaje. Vrať JSON:
{{
  "gold_medal_prediction": "Tým",
  "silver_medal_prediction": "Tým",
  "bronze_medal_prediction": "Tým",
  "dark_horse": "Tým",
  "favorites": ["Tým1", "Tým2", "Tým3"],
  "group_winners": {{"Group A": "Tým", "Group B": "Tým"}},
  "analysis": "Analýza 3-4 věty",
  "team_predictions": [
    {{"team": "Tým", "predicted_finish": "Zlatá medaile", "reasoning": "Proč"}}
  ]
}}

Aktuální tabulky: {json.dumps(standings_data, ensure_ascii=False)}"""
        }]
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(repair_json(raw))                                  