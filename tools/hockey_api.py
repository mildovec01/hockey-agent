import requests
from hockey_config import HIGHLIGHTLY_API_KEY

BASE_URL = "https://hockey.highlightly.net"
HEADERS = {
    "x-rapidapi-key": HIGHLIGHTLY_API_KEY,
    "x-rapidapi-host": "hockey-highlights-api.p.rapidapi.com"
}

def get_matches_by_date(date: str, team_name: str = None, league_name: str = None):
    """Date format: YYYY-MM-DD"""
    params = {"date": date, "timezone": "Europe/Prague"}
    if team_name:
        params["homeTeamName"] = team_name
    if league_name:
        params["leagueName"] = league_name
    r = requests.get(f"{BASE_URL}/matches", headers=HEADERS, params=params)
    return r.json().get("data", [])

def get_match_detail(match_id: int):
    r = requests.get(f"{BASE_URL}/matches/{match_id}", headers=HEADERS)
    data = r.json()
    return data[0] if isinstance(data, list) else data

def get_standings(league_id: int, season: int):
    params = {"leagueId": league_id, "season": season}
    r = requests.get(f"{BASE_URL}/standings", headers=HEADERS, params=params)
    return r.json().get("data", [])

def get_leagues(league_name: str = None, country_name: str = None):
    params = {}
    if league_name:
        params["leagueName"] = league_name
    if country_name:
        params["countryName"] = country_name
    r = requests.get(f"{BASE_URL}/leagues", headers=HEADERS, params=params)
    return r.json().get("data", [])

def get_teams(name: str = None):
    params = {}
    if name:
        params["name"] = name
    r = requests.get(f"{BASE_URL}/teams", headers=HEADERS, params=params)
    return r.json().get("data", [])

def get_team_stats(team_id: int, from_date: str):
    """Format from-date: YYYY-MM-DD"""
    params = {"fromDate": from_date, "timezone": "Europe/Prague"}
    r = requests.get(f"{BASE_URL}/teams/statistics/{team_id}", headers=HEADERS, params=params)
    return r.json()

def get_last_five_games(team_id: int):
    r = requests.get(f"{BASE_URL}/last-five-games", headers=HEADERS, params={"teamId": team_id})
    return r.json()

def get_head_to_head(team_id_1: int, team_id_2: int):
    params = {"teamIdOne": team_id_1, "teamIdTwo": team_id_2}
    r = requests.get(f"{BASE_URL}/head-2-head", headers=HEADERS, params=params)
    return r.json()

            
