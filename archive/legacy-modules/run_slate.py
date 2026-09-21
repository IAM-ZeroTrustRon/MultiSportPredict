#!/usr/bin/env python
"""
Daily Slate Runner — Batch Processing
======================================
Reads a .csv of today's matchups, loops through sport runners,
and generates a master report sorted by Highest Confidence Score.

Usage:
    python run_slate.py                              # Uses input/slate.csv
    python run_slate.py --input my_matches.csv       # Custom CSV
    python run_slate.py --output my_report.md        # Custom output
    python run_slate.py --store-to-db                # Save all to SQLite

CSV Format (input/slate.csv):
    sport,home_team,away_team,league,market_line,market_total
    soccer,Liverpool,Aston Villa,EPL,0.25,2.5
    mlb,NYY,BOS,MLB,0.0,8.5
    tennis,Djokovic,Alcaraz,Grass,0.0,0.0
    basketball,Real Madrid,Barcelona,EuroLeague,0.0,0.0
"""

import argparse
import csv
import json
import sys
import math
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Import the predictors from run_match.py
from run_match import (
    SoccerPredictor,
    BasketballPredictor,
    BaseballPredictor,
    TennisPredictor,
    PredictionDatabase,
    confidence_score,
    bet_recommendation
)


# ============================================================================
# SLATE CONFIGURATION
# ============================================================================

DEFAULT_INPUT = Path("input/slate.csv")
DEFAULT_OUTPUT_MD = Path("output/slate_report.md")
DEFAULT_OUTPUT_JSON = Path("output/slate_report.json")


# ============================================================================
# SLATE RUNNER
# ============================================================================

class SlateRunner:
    """
    Reads a CSV of matchups and runs all predictions,
    returning a consolidated, sorted report.
    """

    # Map CSV sport values to predictor classes
    SPORT_PREDICTORS = {
        "soccer": SoccerPredictor,
        "football": SoccerPredictor,
        "basketball": BasketballPredictor,
        "euroleague": lambda: BasketballPredictor(league="EuroLeague"),
        "baseball": BaseballPredictor,
        "mlb": BaseballPredictor,
        "kbo": BaseballPredictor,
        "tennis": TennisPredictor,
    }

    def __init__(self, input_path: Path = DEFAULT_INPUT,
                 store_to_db: bool = False):
        self.input_path = Path(input_path)
        self.store_to_db = store_to_db
        self.results: List[Dict[str, Any]] = []
        self.db = PredictionDatabase() if store_to_db else None

    def load_matchups(self) -> List[Dict[str, Any]]:
        """Read the CSV file and return a list of matchup dicts."""
        if not self.input_path.exists():
            print(f"[ERROR] Input file not found: {self.input_path}")
            print(f"  Create a CSV with columns: "
                  f"sport,home_team,away_team,league,market_line,market_total")
            sys.exit(1)

        matchups = []
        with open(self.input_path, 'r') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                # Strip whitespace from keys and values
                clean_row = {}
                for k, v in row.items():
                    key = k.strip().lower() if k else k
                    clean_row[key] = v.strip() if v else ""

                sport = clean_row.get("sport", "").lower().strip()
                home = clean_row.get("home_team", "") or clean_row.get("home", "")
                away = clean_row.get("away_team", "") or clean_row.get("away", "")
                league = clean_row.get("league", "")

                # Parse numeric fields
                try:
                    market_line = float(clean_row.get("market_line", 0) or 0)
                except (ValueError, TypeError):
                    market_line = 0.0
                try:
                    market_total = float(clean_row.get("market_total", 0) or 0)
                except (ValueError, TypeError):
                    market_total = 0.0

                if not sport or not home or not away:
                    print(f"  [WARNING] Row {row_num}: Missing required fields. Skipping.")
                    continue

                matchups.append({
                    "sport": sport,
                    "home": home,
                    "away": away,
                    "league": league,
                    "market_line": market_line,
                    "market_total": market_total,
                })

        print(f"Loaded {len(matchups)} matchups from {self.input_path}")
        return matchups

    def _get_predictor(self, sport: str, league: str = "") -> Any:
        """Get the appropriate predictor for a sport."""
        sport_lower = sport.lower().strip()

        # Direct match
        if sport_lower in self.SPORT_PREDICTORS:
            predictor_factory = self.SPORT_PREDICTORS[sport_lower]
            if callable(predictor_factory) and not isinstance(predictor_factory, type):
                return predictor_factory()
            # Handle league-specific constructors
            if predictor_factory == BasketballPredictor:
                return BasketballPredictor(league=league or "EuroLeague")
            return predictor_factory()

        # Fuzzy match
        for key, predictor_factory in self.SPORT_PREDICTORS.items():
            if key in sport_lower or sport_lower in key:
                if callable(predictor_factory) and not isinstance(predictor_factory, type):
                    return predictor_factory()
                if predictor_factory == BasketballPredictor:
                    return BasketballPredictor(league=league or "EuroLeague")
                return predictor_factory()

        return None

    def run_matchup(self, matchup: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run a single matchup and return the result with metadata."""
        sport = matchup["sport"]
        home = matchup["home"]
        away = matchup["away"]
        league = matchup["league"]
        market_line = matchup["market_line"]
        market_total = matchup["market_total"]

        print(f"\n{'='*60}")
        print(f"MATCHUP: {sport.upper()} | {home} vs {away}")
        print(f"{'='*60}")

        # Get predictor
        predictor = self._get_predictor(sport, league=league)

        if predictor is None:
            print(f"  [ERROR] No predictor found for sport: {sport}")
            return None

        # Map sport-specific constructor args
        if isinstance(predictor, TennisPredictor):
            # Tennis expects surface/altitude from kwargs
            pred_kwargs = {"surface": league or "Hard_Outdoor", "altitude": 0}
            predictor = TennisPredictor(**pred_kwargs)

        # Run prediction
        try:
            result = predictor.run_pipeline(
                home_team=home,
                away_team=away,
                player_a=home,
                player_b=away,
                market_line=market_line,
                market_total=market_total,
                league=league or "Premier League",
            )
        except Exception as e:
            print(f"  [ERROR] Prediction failed: {e}")
            return None

        # Extract confidence score from result
        conf, rec, edge = self._extract_confidence(result, sport)

        # Store to DB if requested
        if self.store_to_db and self.db:
            self.db.save_prediction(
                sport=sport,
                home=home,
                away=away,
                m_line=market_line,
                m_total=market_total,
                result=result,
                league=league
            )

        # Return standardized record
        record = {
            "sport": sport,
            "home_team": home,
            "away_team": away,
            "league": league or "N/A",
            "confidence": conf,
            "recommendation": rec,
            "edge": edge,
            "market_line": market_line,
            "market_total": market_total,
            "result": result,
            "data_source": result.get("data_source", "baseline"),
        }

        self.results.append(record)
        print(f"  Confidence: {conf:.1f}% | Recommendation: {rec}")
        return record

    def _extract_confidence(self, result: Dict, sport: str) -> Tuple[float, str, float]:
        """Extract confidence score, recommendation, and edge from result."""
        conf = 0.0
        rec = "PASS"
        edge = 0.0

        if sport in ("baseball", "mlb"):
            game = result.get("game", {})
            side_conf = game.get("confidence", {}).get("side", {})
            conf = side_conf.get("score", 0.0)
            rec = side_conf.get("recommendation", "PASS")
            edge = game.get("projected_run_differential", 0.0)
        elif sport in ("soccer", "football"):
            preds = result.get("predictions", {})
            side = preds.get("side", {})
            conf = side.get("confidence", 0.0)
            rec = side.get("recommendation", "PASS")
            edge = side.get("edge", 0.0)
            # Fall back to total if side confidence is low
            if conf < 30:
                total = preds.get("total", {})
                conf = total.get("confidence", conf)
                rec = total.get("recommendation", rec)
                edge = total.get("edge", edge)
        elif sport in ("basketball", "euroleague"):
            full_game = result.get("full_game", {})
            prob = full_game.get("probability", 0.0)
            conf = prob * 100
            rec = full_game.get("lean", "PASS")
            if conf >= 63:
                rec = "STRONG BET" if conf >= 75 else "BET"
            edge = full_game.get("model_edge", 0.0)
        elif sport == "tennis":
            dr_a = result.get("pA_dr", 1.0)
            dr_b = result.get("pB_dr", 1.0)
            conf = min(100, abs(dr_a - dr_b) * 100)
            edge = dr_a - dr_b
            verdict = result.get("pre_match_edge", "Neutral")
            rec = "STRONG BET" if "Strong" in verdict else "LEAN" if "DANGER" in verdict else "PASS"

        return conf, rec, edge

    def generate_report(self) -> List[Dict]:
        """
        Sort results by confidence descending and return sorted list.
        """
        # Sort by confidence descending
        self.results.sort(key=lambda r: r["confidence"], reverse=True)
        return self.results

    def write_markdown_report(self, output_path: Path = DEFAULT_OUTPUT_MD):
        """Write a Markdown report sorted by confidence."""
        self.generate_report()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = []
        lines.append(f"# Daily Slate Report — {today}")
        lines.append("")
        lines.append(
            f"**Total Matchups:** {len(self.results)} | "
            f"**Sorted by:** Highest Confidence Score\n"
        )
        lines.append("---")
        lines.append("")

        for i, rec in enumerate(self.results, start=1):
            sport_emoji = {
                "soccer": "⚽", "football": "⚽",
                "basketball": "🏀", "euroleague": "🏀",
                "baseball": "⚾", "mlb": "⚾", "kbo": "⚾",
                "tennis": "🎾",
            }.get(rec["sport"], "📊")

            lines.append(f"### {i}. {sport_emoji} **{rec['sport'].upper()}**: {rec['home_team']} vs {rec['away_team']}")
            lines.append("")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| **League** | {rec['league']} |")
            lines.append(f"| **Confidence** | {rec['confidence']:.1f}% |")
            lines.append(f"| **Recommendation** | **{rec['recommendation']}** |")
            lines.append(f"| **Edge** | {rec['edge']:.3f} |")
            lines.append(f"| **Data Source** | {rec['data_source']} |")

            # Sport-specific details
            result = rec["result"]
            if rec["sport"] in ("baseball", "mlb"):
                game = result.get("game", {})
                lines.append(f"| **Projected Runs** | {game.get('projected_home_runs', 'N/A')} - {game.get('projected_away_runs', 'N/A')} |")
                lines.append(f"| **Total** | {game.get('projected_total_runs', 'N/A')} |")
                lines.append(f"| **Win Prob** | {game.get('home_win_probability', 0)*100:.1f}% (Home) |")
            elif rec["sport"] in ("soccer", "football"):
                game = result.get("game", {})
                lines.append(f"| **Projected Goals** | {game.get('projected_home_goals', 'N/A')} - {game.get('projected_away_goals', 'N/A')} |")
                lines.append(f"| **Total xG** | {game.get('projected_total_goals', 'N/A')} |")
                lines.append(f"| **BTTS Prob** | {result.get('predictions', {}).get('btts', {}).get('probability', 0)*100:.1f}% |")
            elif rec["sport"] in ("basketball", "euroleague"):
                fg = result.get("full_game", {})
                lines.append(f"| **Projected Score** | {fg.get('projected_home_score', 'N/A')} - {fg.get('projected_away_score', 'N/A')} |")
                lines.append(f"| **Total** | {fg.get('projected_total', 'N/A')} |")
                lines.append(f"| **Model Edge** | {fg.get('model_edge', 'N/A')} |")
            elif rec["sport"] == "tennis":
                lines.append(f"| **Verdict** | {result.get('pre_match_edge', 'N/A')} |")
                lines.append(f"| **DR Diff** | {result.get('pA_dr', 0) - result.get('pB_dr', 0):.3f} |")

            lines.append("")
            lines.append("---")
            lines.append("")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"\nMarkdown report written to: {output_path}")
        return output_path

    def write_json_report(self, output_path: Path = DEFAULT_OUTPUT_JSON):
        """Write a JSON report."""
        self.generate_report()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to serializable format
        serializable = []
        for rec in self.results:
            serializable.append({
                "sport": rec["sport"],
                "home_team": rec["home_team"],
                "away_team": rec["away_team"],
                "league": rec["league"],
                "confidence": rec["confidence"],
                "recommendation": rec["recommendation"],
                "edge": rec["edge"],
                "data_source": rec["data_source"],
                "market_line": rec["market_line"],
                "market_total": rec["market_total"],
                "full_result": rec["result"],
            })

        with open(output_path, 'w') as f:
            json.dump(serializable, f, indent=2, default=str)

        print(f"JSON report written to: {output_path}")
        return output_path


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Daily Slate Runner — Batch process multiple matchups"
    )
    parser.add_argument("--input", "-i", default=str(DEFAULT_INPUT),
                        help=f"Input CSV path (default: {DEFAULT_INPUT})")
    parser.add_argument("--output-md", "-o", default=str(DEFAULT_OUTPUT_MD),
                        help=f"Output Markdown path (default: {DEFAULT_OUTPUT_MD})")
    parser.add_argument("--output-json", "-j", default=str(DEFAULT_OUTPUT_JSON),
                        help=f"Output JSON path (default: {DEFAULT_OUTPUT_JSON})")
    parser.add_argument("--store-to-db", "-db", action="store_true",
                        help="Store all predictions to SQLite database")

    args = parser.parse_args()

    print("=" * 60)
    print("DAILY SLATE RUNNER")
    print("=" * 60)

    # Initialize runner
    runner = SlateRunner(
        input_path=Path(args.input),
        store_to_db=args.store_to_db
    )

    # Load matchups
    matchups = runner.load_matchups()
    if not matchups:
        print("[ERROR] No valid matchups found.")
        sys.exit(1)

    # Run all matchups
    successful = 0
    failed = 0
    for matchup in matchups:
        result = runner.run_matchup(matchup)
        if result is not None:
            successful += 1
        else:
            failed += 1

    # Generate reports
    print(f"\n{'='*60}")
    print(f"RESULTS: {successful} successful, {failed} failed")
    print(f"{'='*60}")

    if successful > 0:
        runner.write_markdown_report()
        runner.write_json_report()
        print(f"\nDone! Open {DEFAULT_OUTPUT_MD} for the sorted slate.")
    else:
        print("[ERROR] No successful predictions to report.")
        sys.exit(1)


if __name__ == "__main__":
    main()