with open("discord_integration.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''    embed = {
        "title": f" {home} vs {away}",
"description": f"Soccer Prediction | {prediction_data.get('league', 'Soccer')} |{datetime.utcnow().strftime('%B %d, %Y')}",
        "color": COLORS["neutral"],
       "fields": [
            {"name": " Competition & Live Market Lines", "value": "\\n".join(market_lines), "inline": False},
            {"name": " Goals & Team Totals", "value": "\\n".join(goals_lines), "inline": False},
            {"name": " Corner Forecasts", "value": "\\n".join(corner_lines), "inline": False},
            {"name": " BTTS & Halftime", "value": "\\n".join(btts_lines), "inline": False},
        ],
        "footer": {"text": "MultiSportPredict"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }'''

new = '''    side_rec = recommendation("side")
    total_rec = recommendation("total")
    btts_rec = btts.get("recommendation", "PASS")
    best_rec = "STRONG BET" if "STRONG BET" in [side_rec, total_rec, btts_rec] else "BET" if "BET" in [side_rec, total_rec, btts_rec] else "PASS"
    color_map = {"STRONG BET": 3066993, "BET": 10181046, "PASS": 9807270}
    embed_color = color_map.get(best_rec, 9807270)
    league_name = prediction_data.get("league", "Soccer")
    embed = {
        "title": f"{home} vs {away}",
        "description": f"**{league_name}** | {datetime.utcnow().strftime('%B %d, %Y')} | Best Signal: **{best_rec}**",
        "color": embed_color,
        "fields": [
            {"name": "MARKET LINES", "value": "\\n".join(market_lines), "inline": False},
            {"name": "GOALS & TOTALS", "value": "\\n".join(goals_lines), "inline": False},
            {"name": "CORNER FORECASTS", "value": "\\n".join(corner_lines), "inline": False},
            {"name": "BTTS & HALFTIME", "value": "\\n".join(btts_lines), "inline": False},
        ],
        "footer": {"text": "MultiSportPredict | Real data only"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }'''

if old in content:
    content = content.replace(old, new)
    with open("discord_integration.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS")
else:
    # Find exact text around the title
    idx = content.find('"title": f" {home} vs {away}"')
    print(repr(content[idx-20:idx+500]))
