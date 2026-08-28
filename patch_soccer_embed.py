#!/usr/bin/env python3
"""Replace push_soccer_prediction_to_discord with a grid-style embed."""
import datetime, re
from pathlib import Path

ROOT = Path.home() / "mnt" / "MultiSportPredict"
TARGET = ROOT / "discord_integration.py"
STAMP = datetime.date.today().strftime("%Y%m%d")

raw = TARGET.read_text(encoding="utf-8-sig")
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")

START = "def push_soccer_prediction_to_discord("
END = "# ---------------------------------------------------------------------------\n# TENNIS PREDICTION PUSH"
i, j = text.index(START), text.index(END)

NEW = '''def push_soccer_prediction_to_discord(
    match_name: str,
    prediction_data: dict,
    *,
    dry_run: bool = False,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Push a soccer match prediction to Discord.

    Formatting note: the earlier version put every section in a full-width
    field, so four dense `Label: value | Label: value` paragraphs stacked into
    a wall of text. Discord lays `inline` fields out as a grid three across,
    which is the whole reason the baseball embed reads better -- it was never a
    data problem. Soccer actually carries MORE markets than baseball; they just
    needed to be broken into short, bold, scannable cards.

    Empty sections are omitted rather than rendered as "N/A | N/A | N/A".
    A field that says nothing is worse than no field.
    """
    game = prediction_data.get("game", {}) or {}
    preds = prediction_data.get("predictions", {}) or {}
    goals = prediction_data.get("goals_analysis", {}) or {}
    corners = prediction_data.get("corners_analysis", {}) or {}
    btts = preds.get("btts", {}) or {}
    halftime = prediction_data.get("halftime", {}) or {}
    team_corners = prediction_data.get("team_corners", {}) or {}
    live_market = (prediction_data.get("live_market", {}) or {}).get("market", {}) or {}
    home = prediction_data.get("home_team", "Home")
    away = prediction_data.get("away_team", "Away")
    league_name = prediction_data.get("league", "Soccer")

    def num(value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def pct(value):
        parsed = num(value)
        return None if parsed is None else f"{parsed * 100:.1f}%"

    def badge(recommendation, confidence=None):
        text = str(recommendation or "PASS").strip().upper()
        icon = {"STRONG BET": "\\U0001F7E2", "BET": "\\U0001F7E2",
                "PASS": "\\u26AA", "NO BET": "\\u26AA"}.get(text, "\\U0001F7E1")
        score = num(confidence)
        suffix = f" *(conf {score:.0f})*" if score is not None else ""
        return f"{icon} **{text}**{suffix}"

    def field(name, lines, inline=True):
        kept = [line for line in lines if line]
        return {"name": name, "value": "\\n".join(kept), "inline": inline} if kept else None

    fields = []

    # --- moneyline -------------------------------------------------------
    home_prob, draw_prob, away_prob = (pct(game.get("home_win_prob")),
                                       pct(game.get("draw_prob")),
                                       pct(game.get("away_win_prob")))
    if home_prob or away_prob:
        side = preds.get("side", {}) or {}
        fields.append(field("\\U0001F4B0 MONEYLINE", [
            f"**{home}** {home_prob}" if home_prob else None,
            f"**Draw** {draw_prob}" if draw_prob else None,
            f"**{away}** {away_prob}" if away_prob else None,
            badge(side.get("recommendation"), side.get("confidence")),
        ]))

    # --- projected scoreline ---------------------------------------------
    ph, pa = num(game.get("projected_home_goals")), num(game.get("projected_away_goals"))
    if ph is not None and pa is not None:
        total = num(game.get("projected_total_goals"), ph + pa)
        fields.append(field("\\U0001F4CA PROJECTED", [
            f"**{ph:.2f} - {pa:.2f}**",
            f"Total **{total:.2f}**",
        ]))

    # --- match total ------------------------------------------------------
    total_block = preds.get("total", {}) or {}
    line = total_block.get("market_total")
    if line is not None or total_block.get("recommendation"):
        edge = total_block.get("edge")
        fields.append(field("\\U0001F3AF MATCH TOTAL", [
            f"Line **{line}**" if line is not None else None,
            badge(total_block.get("recommendation"), total_block.get("confidence")),
            f"Edge **{edge}**" if edge not in (None, "N/A") else None,
        ]))

    # --- goal lines -------------------------------------------------------
    over15, over25, over35 = (pct(goals.get("over_15_prob")),
                              pct(goals.get("over_25_prob")),
                              pct(goals.get("over_35_prob")))
    if any((over15, over25, over35)):
        fields.append(field("\\U0001F945 GOAL LINES", [
            f"O1.5 **{over15}**" if over15 else None,
            f"O2.5 **{over25}**" if over25 else None,
            f"O3.5 **{over35}**" if over35 else None,
        ]))

    # --- BTTS -------------------------------------------------------------
    btts_prob = pct(btts.get("probability", prediction_data.get("btts_probability")))
    if btts_prob or btts.get("recommendation"):
        fields.append(field("\\U0001F91D BTTS", [
            f"Yes **{btts_prob}**" if btts_prob else None,
            badge(btts.get("recommendation"), btts.get("confidence")),
        ]))

    # --- first half -------------------------------------------------------
    ht_total = halftime.get("recommendation_1h_total")
    ht_result = halftime.get("predicted_1h_result")
    if ht_total or ht_result:
        fields.append(field("\\u23F1\\uFE0F FIRST HALF", [
            f"Total {badge(ht_total)}" if ht_total else None,
            f"Result **{ht_result}**" if ht_result else None,
        ]))

    # --- corners ----------------------------------------------------------
    corner_total = corners.get("projection", prediction_data.get("corner_projection"))
    o85, o95, o105 = (pct(corners.get("over_85_prob")), pct(corners.get("over_95_prob")),
                      pct(corners.get("over_105_prob")))
    corner_bits = []
    if corner_total not in (None, "N/A"):
        corner_bits.append(f"Projected **{corner_total}**")
    spread = " | ".join(x for x in (f"O8.5 **{o85}**" if o85 else "",
                                    f"O9.5 **{o95}**" if o95 else "",
                                    f"O10.5 **{o105}**" if o105 else "") if x)
    if spread:
        corner_bits.append(spread)
    hp, ap = team_corners.get("home_proj"), team_corners.get("away_proj")
    if hp not in (None, "N/A") and ap not in (None, "N/A"):
        corner_bits.append(f"{home} **{hp}** | {away} **{ap}**")
    if corner_bits:
        fields.append(field("\\U0001F6A9 CORNERS", corner_bits, inline=False))

    # --- book prices, only when they actually arrived ---------------------
    ml_home = live_market.get("moneyline_home")
    ml_away = live_market.get("moneyline_away")
    if ml_home not in (None, "N/A") or ml_away not in (None, "N/A"):
        fields.append(field("\\U0001F4C9 BOOK PRICES", [
            f"{home} **{ml_home}** | Draw **{live_market.get('moneyline_draw', 'N/A')}** "
            f"| {away} **{ml_away}**",
        ], inline=False))

    fields = [f for f in fields if f]

    side_rec = str((preds.get("side", {}) or {}).get("recommendation", "PASS")).upper()
    total_rec = str((preds.get("total", {}) or {}).get("recommendation", "PASS")).upper()
    btts_rec = str(btts.get("recommendation", "PASS")).upper()
    all_recs = [side_rec, total_rec, btts_rec]
    best_rec = ("STRONG BET" if "STRONG BET" in all_recs
                else "BET" if "BET" in all_recs else "PASS")
    color_map = {"STRONG BET": 3066993, "BET": 10181046, "PASS": 9807270}

    tier = prediction_data.get("data_tier")
    footer = "MultiSportPredict | Soccer"
    if tier and int(num(tier, 0) or 0) >= 2:
        footer += "  \\u2022  Tier 2 data: xG estimated from goals"

    embed = {
        "title": f"{home} vs {away}",
        "description": (f"**{league_name}**  \\u2022  "
                        f"{datetime.utcnow().strftime('%B %d, %Y')}  \\u2022  "
                        f"Best signal: {badge(best_rec)}"),
        "color": color_map.get(best_rec, 9807270),
        "fields": fields,
        "footer": {"text": footer},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if dry_run:
        payload = {"embeds": [embed]}
        print(f"[DRY RUN] Soccer Prediction Payload for {match_name}:")
        print(json.dumps(payload, indent=2, default=str))
        return True

    target_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not target_url or target_url == "None" or requests is None:
        logger.error("Soccer Discord push aborted: webhook or requests unavailable.")
        return False
    payload = {"embeds": [embed]}
    if _is_duplicate(_content_hash(payload)):
        return True
    try:
        response = requests.post(target_url, json=payload,
                                 headers={"Content-Type": "application/json"}, timeout=15)
        return response.status_code in (200, 204)
    except requests.exceptions.RequestException as exc:
        logger.error("Soccer Discord webhook request failed: %s", exc)
        return False


'''

out = text[:i] + NEW + text[j:]
backup = TARGET.with_suffix(f".py.bak-{STAMP}")
if not backup.exists():
    backup.write_text(raw, encoding="utf-8")
TARGET.write_text(out.replace("\n", "\r\n") if crlf else out, encoding="utf-8", newline="")
print(f"patched {TARGET.name}  (backup: {backup.name})")
