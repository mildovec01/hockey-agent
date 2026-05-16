import os
from dotenv import load_dotenv

load_dotenv()

HIGHLIGHTLY_API_KEY = os.getenv("HIGHLIGHTLY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

DISCORD_HOCKEY_BOT_TOKEN = os.getenv("DISCORD_HOCKEY_BOT_TOKEN")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
DISCORD_CHANNEL_HOCKEY = os.getenv("DISCORD_CHANNEL_HOCKEY", "0")

WORLD_CHAMPIONSHIP_LEAGUE_ID = 95245
WORLD_CHAMPIONSHIP_SEASON = 2026

FAVORITE_TEAMS = ["Czech republic", "Czech republic U20", "HC Energie Karlovy Vary"]

TEAM_ABBR = {
    "Czech Republic": "CZE",
    "Slovakia": "SVK",
    "Canada": "CAN",
    "USA": "USA",
    "Finland": "FIN",
    "Sweden": "SWE",
    "Germany": "GER",
    "Switzerland": "SUI",
    "Russia": "RUS",
    "Latvia": "LAT",
    "Czech Republic U20": "CZE U20",
    "HC Energie Karlovy Vary": "KVA",
}