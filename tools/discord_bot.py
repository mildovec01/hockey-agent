import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import threading
from datetime import datetime, date, timezone
from hockey_config import (
    DISCORD_HOCKEY_BOT_TOKEN,
    DISCORD_GUILD_ID,
    DISCORD_CHANNEL_HOCKEY,
)
from tools.hockey_api import (
    get_standings, get_matches_by_date,
    get_leagues, get_teams
)
from hockey_agents.hockey import (
    format_standings_table,
    format_score_line,
    get_favorite_matches_today,
    generate_pregame_report,
    generate_tournament_prediction,
    WORLD_CHAMPIONSHIP_LEAGUE_ID as WC_ID,
    WORLD_CHAMPIONSHIP_SEASON as WC_SEASON,
    get_abbr,
)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
_ready = threading.Event()

# {match_id: {"message": discord.Message, "score": "0:0", "goals": [], "state": ""}}
_live_messages = {}


@bot.event
async def on_ready():
    print(f"[HockeyBot] Přihlášen jako {bot.user}")
    guild = discord.Object(id=DISCORD_GUILD_ID)
    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"[HockeyBot] Synchronizovány {len(synced)} příkazy")
    except Exception as e:
        print(f"[HockeyBot] Sync error: {e}")
    live_score_loop.start()
    pregame_check_loop.start()
    _ready.set()


def build_live_embed(match: dict, goals: list) -> discord.Embed:
    home = match["homeTeam"]["name"]
    away = match["awayTeam"]["name"]
    home_abbr = get_abbr(home)
    away_abbr = get_abbr(away)
    score = match["state"]["score"]["current"]
    state_desc = match["state"]["description"]
    clock = match["state"].get("clock") or ""

    home_score = score["home"] if score else 0
    away_score = score["away"] if score else 0

    finished = state_desc in ("Finished", "Finished after penalties", "Finished after over time")

    if finished:
        title = f"✅ KONEC: [{home_abbr}] {home_score} : {away_score} [{away_abbr}]"
        color = 0x5a5a6e
    elif score:
        title = f"🔴 LIVE: [{home_abbr}] {home_score} : {away_score} [{away_abbr}]"
        color = 0xff4757
    else:
        title = f"⏳ [{home_abbr}] - : - [{away_abbr}]"
        color = 0x7b5ea7

    period_map = {
        "1st period": "1. perioda",
        "2nd period": "2. perioda",
        "3rd period": "3. perioda",
        "Over time": "Prodloužení",
        "Break time": "Přestávka",
        "Penalties": "Nájezdy",
        "Finished": "Konec",
        "Finished after penalties": "Konec po nájezdech",
        "Finished after over time": "Konec po prodloužení",
        "Not started": "Nezačalo",
    }
    period_str = period_map.get(state_desc, state_desc)

    embed = discord.Embed(title=title, color=color)
    embed.add_field(
        name="🕐 Stav",
        value=f"{period_str} {clock}".strip(),
        inline=True,
    )

    s = match["state"]["score"]
    thirds = []
    if s.get("firstPeriod"):
        thirds.append(f"1. třetina: {s['firstPeriod']['home']}:{s['firstPeriod']['away']}")
    if s.get("secondPeriod"):
        thirds.append(f"2. třetina: {s['secondPeriod']['home']}:{s['secondPeriod']['away']}")
    if s.get("thirdPeriod"):
        thirds.append(f"3. třetina: {s['thirdPeriod']['home']}:{s['thirdPeriod']['away']}")
    if s.get("overTime"):
        thirds.append(f"Prodloužení: {s['overTime']['home']}:{s['overTime']['away']}")
    if s.get("penalties"):
        thirds.append(f"Nájezdy: {s['penalties']['home']}:{s['penalties']['away']}")

    if thirds:
        embed.add_field(
            name="📊 Po třetinách",
            value="\n".join(thirds),
            inline=True,
        )

    if goals:
        goal_lines = []
        for g in goals[-8:]:
            goal_lines.append(f"🏒 {g['team_abbr']} — {g['time']} ({g['score']})")
        embed.add_field(
            name="⚡ Góly",
            value="\n".join(goal_lines),
            inline=False,
        )
    else:
        embed.add_field(name="⚡ Góly", value="Zatím žádný gól", inline=False)

    embed.set_footer(text=f"Aktualizováno: {datetime.now().strftime('%H:%M:%S')}")
    return embed


def format_group_embed(group: dict, league_name: str, season: int) -> discord.Embed:
    group_name = group.get("name", "Tabulka")
    lines = ["`Tým              Z  V  P  VPP PPP  GF  GA  B`"]
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

    embed = discord.Embed(
        title=f"🏒 {league_name} {season} — {group_name}",
        description="\n".join(lines),
        color=0x1D9E75,
    )
    embed.set_footer(text=f"Aktualizováno: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    return embed


@bot.tree.command(
    name="htable",
    description="Zobrazí tabulku zadané ligy/turnaje",
    guild=discord.Object(id=DISCORD_GUILD_ID),
)
@app_commands.describe(liga="Název ligy (např. World Championship, NHL, Tipsport Extraliga)")
async def htable(interaction: discord.Interaction, liga: str):
    await interaction.response.defer(thinking=True)
    loop = asyncio.get_event_loop()

    leagues = await loop.run_in_executor(None, lambda: get_leagues(liga))
    if not leagues:
        await interaction.followup.send(f"❌ Liga **{liga}** nenalezena.")
        return

    league = leagues[0]
    league_id = league["id"]
    seasons = league.get("seasons", [])
    season = max(s["season"] for s in seasons) if seasons else 2026

    standings_data = await loop.run_in_executor(
        None, lambda: get_standings(league_id, season)
    )
    if not standings_data:
        await interaction.followup.send(f"❌ Tabulka pro **{liga}** není dostupná.")
        return

    groups = standings_data.get("groups", [])
    if not groups:
        await interaction.followup.send(f"❌ Tabulka pro **{liga}** nemá skupiny.")
        return

    embeds = [format_group_embed(g, league["name"], season) for g in groups]
    for i in range(0, len(embeds), 10):
        await interaction.followup.send(embeds=embeds[i:i+10])


@bot.tree.command(
    name="hteams",
    description="Zobrazí oblíbené týmy",
    guild=discord.Object(id=DISCORD_GUILD_ID),
)
async def hteams(interaction: discord.Interaction):
    from hockey_config import FAVORITE_TEAMS
    teams_list = "\n".join(f"• {t}" for t in FAVORITE_TEAMS)
    embed = discord.Embed(
        title="⭐ Oblíbené týmy",
        description=teams_list or "Žádné oblíbené týmy.",
        color=0x7b5ea7,
    )
    embed.set_footer(text="Pro změnu uprav FAVORITE_TEAMS v hockey_config.py")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="hlive",
    description="Zobrazí aktuální live skóre oblíbených týmů",
    guild=discord.Object(id=DISCORD_GUILD_ID),
)
async def hlive(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    loop = asyncio.get_event_loop()
    matches = await loop.run_in_executor(None, get_favorite_matches_today)

    if not matches:
        await interaction.followup.send("📭 Dnes žádné zápasy oblíbených týmů.")
        return

    embeds = []
    for m in matches:
        match_id = m["id"]
        goals = _live_messages.get(match_id, {}).get("goals", [])
        embeds.append(build_live_embed(m, goals))

    await interaction.followup.send(embeds=embeds[:4])


@bot.tree.command(
    name="hpredict",
    description="Predikce výsledků MS 2026",
    guild=discord.Object(id=DISCORD_GUILD_ID),
)
async def hpredict(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    loop = asyncio.get_event_loop()

    standings_data = await loop.run_in_executor(
        None, lambda: get_standings(WC_ID, WC_SEASON)
    )
    prediction = await loop.run_in_executor(
        None, lambda: generate_tournament_prediction(standings_data)
    )

    embed = discord.Embed(
        title="🔮 Predikce MS 2026",
        description=prediction.get("analysis", ""),
        color=0xffd93d,
    )
    embed.add_field(name="🥇 Zlato", value=prediction.get("gold_medal_prediction", "?"), inline=True)
    embed.add_field(name="🥈 Stříbro", value=prediction.get("silver_medal_prediction", "?"), inline=True)
    embed.add_field(name="🥉 Bronz", value=prediction.get("bronze_medal_prediction", "?"), inline=True)
    embed.add_field(name="🃏 Dark horse", value=prediction.get("dark_horse", "?"), inline=True)
    favorites = prediction.get("favorites", [])
    if favorites:
        embed.add_field(name="⭐ Favorité", value=", ".join(favorites), inline=False)
    await interaction.followup.send(embed=embed)


@bot.tree.command(
    name="hpregame",
    description="Analýza a predikce před zápasem",
    guild=discord.Object(id=DISCORD_GUILD_ID),
)
@app_commands.describe(
    home="Domácí tým (např. Czech Republic)",
    away="Hostující tým (např. Canada)"
)
async def hpregame(interaction: discord.Interaction, home: str, away: str):
    await interaction.response.defer(thinking=True)
    loop = asyncio.get_event_loop()

    today = str(date.today())
    matches = await loop.run_in_executor(
        None, lambda: get_matches_by_date(today, team_name=home)
    )
    match = next(
        (m for m in matches if
         away.lower() in m["awayTeam"]["name"].lower() or
         away.lower() in m["homeTeam"]["name"].lower()),
        None
    )
    if not match:
        match = {
            "homeTeam": {"name": home, "id": 0},
            "awayTeam": {"name": away, "id": 0},
            "date": today,
        }

    report = await loop.run_in_executor(None, lambda: generate_pregame_report(match))
    home_name = report.get("home_team", home)
    away_name = report.get("away_team", away)
    prob = report.get("win_probability", {})

    embed = discord.Embed(
        title=f"📋 {home_name} vs {away_name}",
        description=report.get("analysis", ""),
        color=0x38bdf8,
    )
    embed.add_field(
        name=f"✅ {home_name} — silné stránky",
        value="\n".join(f"• {s}" for s in report.get("home_strengths", [])) or "—",
        inline=True,
    )
    embed.add_field(
        name=f"✅ {away_name} — silné stránky",
        value="\n".join(f"• {s}" for s in report.get("away_strengths", [])) or "—",
        inline=True,
    )
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(
        name=f"⚠️ {home_name} — slabé stránky",
        value="\n".join(f"• {s}" for s in report.get("home_weaknesses", [])) or "—",
        inline=True,
    )
    embed.add_field(
        name=f"⚠️ {away_name} — slabé stránky",
        value="\n".join(f"• {s}" for s in report.get("away_weaknesses", [])) or "—",
        inline=True,
    )
    embed.add_field(
        name="🎯 Predikce skóre",
        value=f"**{report.get('predicted_score', '?')}** — vítěz: **{report.get('predicted_winner', '?')}**",
        inline=False,
    )
    embed.add_field(
        name="📊 Pravděpodobnost",
        value=f"{home_name}: **{prob.get('home', '?')}%** | {away_name}: **{prob.get('away', '?')}%**",
        inline=False,
    )
    await interaction.followup.send(embed=embed)


@tasks.loop(minutes=1)
async def live_score_loop():
    channel = bot.get_channel(DISCORD_CHANNEL_HOCKEY)
    if not channel:
        return

    today = str(date.today())
    from hockey_config import FAVORITE_TEAMS

    for team in FAVORITE_TEAMS:
        matches = get_matches_by_date(today, team_name=team)
        for match in matches:
            state_desc = match["state"]["description"]
            match_id = match["id"]
            score = match["state"]["score"]["current"]

            if state_desc == "Not started":
                continue

            finished = state_desc in ("Finished", "Finished after penalties", "Finished after over time")

            if match_id not in _live_messages:
                goals = []
                embed = build_live_embed(match, goals)
                msg = await channel.send(embed=embed)
                _live_messages[match_id] = {
                    "message": msg,
                    "score": f"{score['home']}:{score['away']}" if score else "0:0",
                    "goals": goals,
                    "state": state_desc,
                }
                continue

            tracked = _live_messages[match_id]
            prev_score = tracked["score"]
            goals = tracked["goals"]

            if score:
                current_score = f"{score['home']}:{score['away']}"
                if current_score != prev_score:
                    prev_home, prev_away = map(int, prev_score.split(":"))
                    new_home = score["home"]
                    new_away = score["away"]
                    clock = match["state"].get("clock") or "?"

                    if new_home > prev_home:
                        scorer_abbr = get_abbr(match["homeTeam"]["name"])
                    else:
                        scorer_abbr = get_abbr(match["awayTeam"]["name"])

                    goals.append({
                        "team_abbr": scorer_abbr,
                        "time": clock,
                        "score": current_score,
                    })
                    tracked["score"] = current_score

            tracked["state"] = state_desc

            try:
                embed = build_live_embed(match, goals)
                await tracked["message"].edit(embed=embed)
            except Exception as e:
                print(f"[HockeyBot] Edit error: {e}")

            if finished:
                del _live_messages[match_id]


@tasks.loop(minutes=5)
async def pregame_check_loop():
    channel = bot.get_channel(DISCORD_CHANNEL_HOCKEY)
    if not channel:
        return

    now = datetime.now(timezone.utc)
    today = str(date.today())
    from hockey_config import FAVORITE_TEAMS

    for team in FAVORITE_TEAMS:
        matches = get_matches_by_date(today, team_name=team)
        for match in matches:
            if match["state"]["description"] != "Not started":
                continue
            try:
                match_time = datetime.fromisoformat(match["date"].replace("Z", "+00:00"))
                diff = (match_time - now).total_seconds() / 60
                if 28 <= diff <= 32:
                    loop = asyncio.get_event_loop()
                    report = await loop.run_in_executor(
                        None, lambda m=match: generate_pregame_report(m)
                    )
                    await send_pregame_embed(channel, report, match)
            except Exception as e:
                print(f"[HockeyBot] Pregame check error: {e}")


async def send_pregame_embed(channel, report: dict, match: dict):
    home = report.get("home_team", match["homeTeam"]["name"])
    away = report.get("away_team", match["awayTeam"]["name"])
    match_time_str = match.get("date", "")
    try:
        mt = datetime.fromisoformat(match_time_str.replace("Z", "+00:00"))
        time_str = mt.strftime("%H:%M")
    except Exception:
        time_str = "?"

    prob = report.get("win_probability", {})
    embed = discord.Embed(
        title=f"🏒 Za 30 minut: {home} vs {away} ({time_str})",
        description=report.get("analysis", ""),
        color=0xf97316,
    )
    embed.add_field(
        name=f"✅ {home}",
        value="\n".join(f"• {s}" for s in report.get("home_strengths", [])) or "—",
        inline=True,
    )
    embed.add_field(
        name=f"✅ {away}",
        value="\n".join(f"• {s}" for s in report.get("away_strengths", [])) or "—",
        inline=True,
    )
    embed.add_field(
        name="🎯 Predikce",
        value=f"**{report.get('predicted_score', '?')}** — {report.get('predicted_winner', '?')}\n"
              f"{home}: {prob.get('home', '?')}% | {away}: {prob.get('away', '?')}%",
        inline=False,
    )
    key_factors = report.get("key_factors", [])
    if key_factors:
        embed.add_field(
            name="🔑 Klíčové faktory",
            value="\n".join(f"• {f}" for f in key_factors),
            inline=False,
        )
    await channel.send(embed=embed)


def run_bot():
    bot.run(DISCORD_HOCKEY_BOT_TOKEN)


def start_bot_thread():
    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
    print("[HockeyBot] Thread spuštěn")
    return thread