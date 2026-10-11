import sys
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from embed_builder import build_embed, normalise
from run_tennis import format_tennis_review, show_review


def sample_prediction():
    return {
        "sport": "tennis",
        "match": "Matteo Berrettini vs Brandon Nakashima",
        "tournament": "Shanghai",
        "round": "R1",
        "surface": "hard",
        "best_of_5": False,
        "moneyline": {
            "home": "Matteo Berrettini",
            "away": "Brandon Nakashima",
            "home_win_prob": 0.382,
            "away_win_prob": 0.618,
        },
        "market_prob": 0.411,
        "market_home_odds": "+132",
        "market_away_odds": "-162",
        "alternative_markets": [
            {
                "kind": "games_total",
                "line": 20.5,
                "price_a": -110,
                "price_b": -110,
                "prob_a": 0.684,
                "prob_b": 0.316,
                "push_prob": 0,
                "ev_a": 0.305,
                "ev_b": -0.397,
                "line_origin": "user_supplied",
            },
            {
                "kind": "games_spread",
                "line": 2.5,
                "price_a": -110,
                "price_b": -110,
                "prob_a": 0.541,
                "prob_b": 0.459,
                "push_prob": 0,
                "ev_a": 0.033,
                "ev_b": -0.124,
                "line_origin": "user_supplied",
            },
        ],
    }


class TennisOutputTests(unittest.TestCase):
    def test_terminal_review_names_sides_and_explains_actions(self):
        row = {
            "p1": "Matteo Berrettini",
            "p2": "Brandon Nakashima",
            "tournament": "Shanghai",
            "surface": "hard",
            "best_of_5": False,
            "model_prob": 0.382,
            "market_prob": 0.411,
            "p1_ml": 132,
            "p2_ml": -162,
            "market_source": "live",
            "custom_markets": [],
            "alternative_markets": sample_prediction()["alternative_markets"],
        }
        report = "\n".join(format_tennis_review(row))
        self.assertIn("Matteo Berrettini +132 (41.1%)", report)
        self.assertIn("Brandon Nakashima -162 (58.9%)", report)
        self.assertIn("LEAN Brandon Nakashima ML (-162) (Edge: +2.9%)", report)
        self.assertIn("BET OVER 20.5 Games (-110) (EV: +30.5%)", report)
        self.assertIn("Matteo Berrettini +2.5 (-110) vs Brandon Nakashima -2.5 (-110)", report)
        self.assertIn("BET Matteo Berrettini +2.5 Games (-110) (EV: +3.3%)", report)
        self.assertIn("⚠️ Note: Simulation uses baseline 75% serve-hold rate (uncalibrated)", report)
        self.assertNotIn("First/Second", report)

    def test_discord_embed_has_full_names_lines_prices_ev_and_verdicts(self):
        embed = build_embed("tennis", sample_prediction())
        self.assertIn("Matteo Berrettini vs Brandon Nakashima", embed["title"])
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        moneyline = next(value for name, value in fields.items() if "Moneyline" in name)
        total = next(value for name, value in fields.items() if "Total Games" in name)
        spread = next(value for name, value in fields.items() if "Games Spread" in name)
        self.assertIn("Market Odds (User-Supplied)", moneyline)
        self.assertIn("LEAN Brandon Nakashima ML (-162)", moneyline)
        self.assertIn("User-Supplied / Manual Line", total)
        self.assertIn("BET OVER 20.5 Games (-110) (EV: +30.5%)", total)
        self.assertIn("Matteo Berrettini (+2.5) 54.1%", spread)
        self.assertIn("BET Matteo Berrettini +2.5 Games (-110) (EV: +3.3%)", spread)
        self.assertTrue(all(not field["inline"] for field in embed["fields"]
                            if field["name"].strip()))
        self.assertNotIn("First/Second", str(embed))

    def test_rich_terminal_renderer_uses_clear_market_review(self):
        from universal_runner import _display_full_result

        output = StringIO()
        with redirect_stdout(output):
            _display_full_result(sample_prediction())
        rendered = output.getvalue()
        self.assertIn("🏆 MONEYLINE (MATCH WINNER)", rendered)
        self.assertIn("📊 TOTAL GAMES (OVER / UNDER 20.5)", rendered)
        self.assertIn("⚖️ GAMES SPREAD (HANDICAP +/- 2.5)", rendered)
        self.assertIn("👉 ACTION: LEAN Brandon Nakashima ML (-162)", rendered)
        self.assertNotIn("Recommendations", rendered)

    def test_review_index_keeps_full_names_and_verdict_without_ambiguous_columns(self):
        row = {
            "p1": "Matteo Berrettini",
            "p2": "Brandon Nakashima",
            "tournament": "Shanghai",
            "surface": "hard",
            "model_prob": 0.382,
            "market_prob": None,
            "p1_ml": None,
            "p2_ml": None,
        }
        output = StringIO()
        with redirect_stdout(output):
            show_review([row])
        rendered = output.getvalue()
        self.assertIn("1. Matteo Berrettini vs Brandon Nakashima", rendered)
        self.assertIn("👉 ACTION: PASS — No priced moneyline market supplied", rendered)
        self.assertNotIn("unavailableunavailable", rendered)

    def test_missing_alternative_price_has_no_ev_and_passes(self):
        prediction = sample_prediction()
        prediction["alternative_markets"] = [{
            "kind": "games_total",
            "line": 20.5,
            "price_a": None,
            "price_b": None,
            "prob_a": 0.684,
            "prob_b": 0.316,
            "push_prob": 0,
            "ev_a": None,
            "ev_b": None,
            "line_origin": "user_supplied",
        }]
        row = normalise("tennis", prediction)["markets"][-1]
        self.assertIn("Over Price: None — No EV calculated (PASS)", row["model"])
        self.assertIn("Under Price: None — No EV calculated (PASS)", row["model"])
        self.assertIn("👉 ACTION: PASS", row["verdict"])
        terminal_row = {
            "p1": "Matteo Berrettini",
            "p2": "Brandon Nakashima",
            "tournament": "Shanghai",
            "surface": "hard",
            "model_prob": 0.382,
            "market_prob": None,
            "p1_ml": None,
            "p2_ml": None,
            "custom_markets": [],
            "alternative_markets": prediction["alternative_markets"],
        }
        terminal = "\n".join(format_tennis_review(terminal_row))
        self.assertIn("Over Price: None — No EV calculated (PASS)", terminal)
        self.assertIn("Under Price: None — No EV calculated (PASS)", terminal)
        self.assertIn("👉 ACTION: PASS", terminal)

    def test_live_alternative_line_is_labeled_live(self):
        prediction = sample_prediction()
        prediction["alternative_markets"] = [dict(
            prediction["alternative_markets"][0], line_origin="live_market")]
        rendered = normalise("tennis", prediction)["markets"][-1]["model"]
        self.assertIn("(Live Market Line)", rendered)

    def test_moneyline_action_thresholds_and_missing_prices(self):
        row = {
            "p1": "Player One",
            "p2": "Player Two",
            "tournament": "Test",
            "surface": "hard",
            "best_of_5": False,
            "market_prob": 0.40,
            "p1_ml": 150,
            "p2_ml": -150,
            "market_source": "user",
            "custom_markets": [],
            "alternative_markets": [],
        }
        row["model_prob"] = 0.42
        self.assertIn("LEAN Player One ML", "\n".join(format_tennis_review(row)))
        row["model_prob"] = 0.45
        self.assertIn("BET Player One ML", "\n".join(format_tennis_review(row)))
        row["model_prob"] = 0.41
        self.assertIn("PASS — Market is efficient", "\n".join(format_tennis_review(row)))
        row["p1_ml"] = None
        self.assertIn("PASS — No priced moneyline market supplied",
                      "\n".join(format_tennis_review(row)))


if __name__ == "__main__":
    unittest.main()
