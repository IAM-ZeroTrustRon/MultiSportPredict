with open("discord_integration.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''    embed = {
        "title": f" {home} vs {away}",
        "description": f"Soccer Prediction | {prediction_data.get('league', 'Soccer')} | {datetime.utcnow().strftime('%B %d, %Y')}",
        "color": COLORS.get(
            {"STRONG BET": "strong_bet", "BET": "bet", "PASS": "pass"}.get(
                recommendation("side").upper(), "neutral"
            ), COLORS["neutral"]
        ),
        "fields": [
            {"name": " Competition & Live Market Lines", "value": "\\n".join(market_lines), "inline": False},
            {"name": " Goals & Team Totals", "value": "\\n".join(goals_lines), "inline": False},
            {"name": " Corner Forecasts", "value": "\\n".join(corner_lines), "inline": False},
            {"name": " BTTS & Halftime", "value": "\\n".join(btts_lines), "inline": False},
        ],
        "footer": {"text": "MultiSportPredict"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }'''

new = '''    # Color based on best recommendation
    side_rec = recommendation("side")
    total_rec = recommendation("total")
    btts_rec = btts.get("recommendation", "PASS")
    best_rec = "STRONG BET" if "STRONG BET" in [side_rec, total_rec, btts_rec] else \
               "BET" if "BET" in [side_rec, total_rec, btts_rec] else "PASS"
    color_map = {"STRONG BET": 3066993, "BET": 10181046, "PASS": 9807270}
    embed_color = color_map.get(best_rec, 9807270)

    league_name = prediction_data.get("league", "Soccer")
    embed = {
        "title": f"{home} vs {away}",
        "description": f"**{league_name}** | {datetime.utcnow().strftime('%B %d, %Y')} | Best Signal: **{best_rec}**",
        "color": embed_color,
        "fields": [
            {"name": ":bar_chart: Market Lines", "value": "\\n".join(market_lines), "inline": False},
            {"name": ":soccer: Goals & Totals", "value": "\\n".join(goals_lines), "inline": False},
            {"name": ":triangular_flag_on_post: Corner Forecasts", "value": "\\n".join(corner_lines), "inline": False},
            {"name": ":handshake: BTTS & Halftime", "value": "\\n".join(btts_lines), "inline": False},
        ],
        "footer": {"text": "MultiSportPredict | Real data only"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }'''

if old in content:
    content = content.replace(old, new)
    with open("discord_integration.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: Soccer embed updated.")
else:
    # Try finding the embed block a different way
    idx = content.find('"title": f" {home} vs {away}"')
    if idx == -1:
        idx = content.find('"title": f"{home} vs {away}"')
    print(f"Pattern not found. Title found at index: {idx}")
    if idx > 0:
        print(repr(content[idx-200:idx+300]))
