import re

# ── Step 1: Wire extra_markets into universal_runner.py ──────────────────────
with open("universal_runner.py", "r", encoding="utf-8") as f:
    ur = f.read()

old_soccer = '''    result = run_soccer_game(home, away, league=league or "Premier League",
                             market_line=market_line, market_total=market_total,
                             home_stats=hs, away_stats=aws)'''

new_soccer = '''    result = run_soccer_game(home, away, league=league or "Premier League",
                             market_line=market_line, market_total=market_total,
                             home_stats=hs, away_stats=aws)

    # Wire extra_markets — halftime, team corners, BTTS enrichment
    try:
        from extra_markets import enrich_result
        result = enrich_result(result, home_team=home, away_team=away)
        em = result.get("extra_markets", {})
        # Halftime
        fh = em.get("first_half_goals", {})
        result["halftime"] = {
            "recommendation_1h_total": f"Over 0.5: {fh.get('over_05', 0)*100:.1f}% | Over 1.5: {fh.get('over_15', 0)*100:.1f}%",
            "predicted_1h_result": f"Proj: {fh.get('projection', 'N/A')}",
        }
        # Team corners
        tc = em.get("team_corners", {})
        if tc and "_warning" not in tc:
            result["team_corners"] = {
                "home_proj": tc.get("home", {}).get("projection", "N/A"),
                "away_proj": tc.get("away", {}).get("projection", "N/A"),
            }
    except Exception as e:
        print(f"[WARNING] extra_markets enrichment failed: {e}")'''

if old_soccer in ur:
    ur = ur.replace(old_soccer, new_soccer)
    print("Step 1: extra_markets wired into universal_runner.py")
else:
    print("Step 1 ERROR: Pattern not found in universal_runner.py")

with open("universal_runner.py", "w", encoding="utf-8") as f:
    f.write(ur)

# ── Step 2: Fix discord_integration.py ──────────────────────────────────────
with open("discord_integration.py", "r", encoding="utf-8") as f:
    di = f.read()

# Fix 1: Team corners N/A -> real data
old_corners = '        f"Expected corners: {home} N/A | {away} N/A",'
new_corners = '''        f"Expected corners: {home} {prediction_data.get('team_corners', {}).get('home_proj', 'N/A')} | {away} {prediction_data.get('team_corners', {}).get('away_proj', 'N/A')}",'''

if old_corners in di:
    di = di.replace(old_corners, new_corners)
    print("Step 2a: Team corners wired")
else:
    print("Step 2a ERROR: corners pattern not found")

# Fix 2: Color coding based on recommendation
old_color = '    "color": COLORS["neutral"],'
new_color = '''    "color": COLORS.get(
        {"STRONG BET": "strong_bet", "BET": "bet", "PASS": "pass"}.get(
            recommendation("side").upper(), "neutral"
        ), COLORS["neutral"]
    ),'''

if old_color in di:
    di = di.replace(old_color, new_color, 1)
    print("Step 2b: Color coding fixed")
else:
    print("Step 2b ERROR: color pattern not found")

# Fix 3: Description shows league and competition
old_desc = '        "description": "Soccer match forecast",'
new_desc = '        "description": f"Soccer Prediction | {prediction_data.get(\'league\', \'Soccer\')} | {datetime.utcnow().strftime(\'%B %d, %Y\')}",'

if old_desc in di:
    di = di.replace(old_desc, new_desc)
    print("Step 2c: Description fixed")
else:
    print("Step 2c ERROR: description pattern not found")

# Fix 4: Add edge/confidence indicator to goals section
old_goals = '        f"Team totals: {home} {game.get(\'projected_home_goals\', \'N/A\')} | {away} {game.get(\'projected_away_goals\', \'N/A\')}",\n    ]'
new_goals = '''        f"Team totals: {home} {game.get('projected_home_goals', 'N/A')} | {away} {game.get('projected_away_goals', 'N/A')}",
        f"Edge: {preds.get('total', {}).get('edge', 'N/A')} | Confidence: {preds.get('total', {}).get('confidence', 'N/A')}",
    ]'''

if old_goals in di:
    di = di.replace(old_goals, new_goals)
    print("Step 2d: Edge/confidence indicator added")
else:
    print("Step 2d ERROR: goals pattern not found")

with open("discord_integration.py", "w", encoding="utf-8") as f:
    f.write(di)

print("\nAll steps complete. Run a test match to verify.")
