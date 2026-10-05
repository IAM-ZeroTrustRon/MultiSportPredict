"""NFL embeds must identify teams and preserve home-signed market lines."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from embed_builder import build_embed, UnrenderablePrediction


def prediction():
    return {
        "home": "Carolina Panthers", "away": "Detroit Lions",
        "spread": {"model_spread": -3.7, "market_spread": 3.5, "pick": "HOME", "edge_points": 7.2},
        "moneyline": {"home_win_probability": .607, "away_win_probability": .393,
                      "market_home_prob": .363, "recommendation": "BET HOME", "edge_pct": 24.4},
        "total": {"home_team_total": 35.6, "away_team_total": 31.9},
        "halftime": {"home_1h_points": 16.9, "away_1h_points": 15.2,
                     "home_1h_win_probability": .573},
    }


def field(data, name):
    return next(f["value"] for f in build_embed("nfl", data)["fields"] if name in f["name"])


@pytest.mark.parametrize("pick,line,expected", [
    ("HOME", 3.5, "BET Carolina Panthers +3.5"),
    ("AWAY", 3.5, "BET Detroit Lions -3.5"),
    ("HOME", -3.5, "BET Carolina Panthers -3.5"),
    ("AWAY", -3.5, "BET Detroit Lions +3.5"),
    ("HOME", 0, "BET Carolina Panthers +0.0"),
    ("PASS", 3.5, "PASS — Spread"),
])
def test_spread_side_and_sign(pick, line, expected):
    data = prediction()
    data["spread"].update(pick=pick, market_spread=line)
    before = copy.deepcopy(data)
    value = field(data, "Spread")
    assert expected in value
    assert f"mkt Carolina Panthers {line:+.1f}" in value
    assert "Model: Carolina Panthers -3.7" in value
    assert data == before


def test_missing_lines_do_not_claim_a_bet():
    data = prediction()
    data["spread"]["market_spread"] = None
    data["moneyline"]["market_home_prob"] = None
    assert "no market line supplied" in field(data, "Spread")
    assert "no market odds supplied" in field(data, "Moneyline")
    assert "BET" not in field(data, "Spread")
    assert "BET" not in field(data, "Moneyline")


def test_team_labels_and_probabilities():
    data = prediction()
    assert "BET Carolina Panthers ML" in field(data, "Moneyline")
    for text in ("**Detroit Lions** 39.3%", "**Panthers** 60.7%", "**Detroit Lions** 63.7%", "**Panthers** 36.3%"):
        assert text in field(data, "Moneyline")
    assert "**Detroit Lions** 31.9" in field(data, "Team totals")
    assert "**Panthers** 35.6" in field(data, "Team totals")
    assert "**Detroit Lions** 15.2" in field(data, "First half")
    assert "Panthers ML 57.3%" in field(data, "First half")
    data["moneyline"]["recommendation"] = "BET AWAY"
    assert "BET Detroit Lions ML" in field(data, "Moneyline")


def test_missing_values_are_omitted_and_missing_names_refused():
    data = prediction()
    data["halftime"].pop("home_1h_win_probability")
    data["total"].pop("away_team_total")
    assert "None" not in json.dumps(build_embed("nfl", data))
    assert "Lions" not in field(data, "Team totals")
    data.pop("home")
    with pytest.raises(UnrenderablePrediction):
        build_embed("nfl", data)


def test_saved_review_renders_without_writes():
    path = Path(__file__).resolve().parents[1] / "data/nfl_review.json"
    if not path.exists():
        pytest.skip("No saved review")
    rows = json.loads(path.read_text(encoding="utf-8-sig"))["rows"]
    for row in rows:
        embed = build_embed("nfl", row)
        assert row["home"] in embed["title"]
        assert row["away"] in embed["title"]
        assert "None" not in json.dumps(embed)
