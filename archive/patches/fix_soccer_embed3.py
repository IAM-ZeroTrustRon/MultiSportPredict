with open("discord_integration.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the embed block start
start = None
end = None
for i, line in enumerate(lines):
    if '"title": f" {home} vs {away}"' in line:
        # Go back to find "embed = {"
        for j in range(i, max(i-5, 0), -1):
            if "embed = {" in lines[j]:
                start = j
                break
        # Go forward to find closing "}"
        brace = 0
        for j in range(start, min(start+30, len(lines))):
            brace += lines[j].count("{") - lines[j].count("}")
            if brace == 0:
                end = j + 1
                break
        break

if start is None:
    print("ERROR: Could not find embed block")
else:
    print(f"Found embed block: lines {start+1} to {end}")
    replacement = '''    side_rec = recommendation("side")
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
    }
'''
    new_lines = lines[:start] + [replacement] + lines[end:]
    with open("discord_integration.py", "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("SUCCESS: Soccer embed replaced.")
