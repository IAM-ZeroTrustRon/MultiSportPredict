#!/usr/bin/env python
"""
MCP Server: MultiSportPredict Slate Runner
============================================
Exposes soccer match prediction as MCP tools for Cowork/Cline integration.
"""

import json
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

class MCPServer:
    def __init__(self):
        self.tools = self._register_tools()

    def _register_tools(self) -> dict:
        return {
            name[5:]: getattr(self, name)
            for name, method in vars(self.__class__).items()
            if callable(method) and name.startswith("tool_")
        }

    def tool_predict_match(self, **kwargs) -> dict:
        """Predict a soccer match and optionally push to Discord."""
        from universal_runner import push_to_discord
        from team_stats_provider import get_soccer_team_stats

        home = kwargs.get("home_team", "").strip()
        away = kwargs.get("away_team", "").strip()
        league = kwargs.get("league", "").strip()
        market_total = float(kwargs.get("market_total", 2.5))
        market_line = kwargs.get("market_line")
        if market_line is not None:
            market_line = float(market_line)
        push = kwargs.get("push_to_discord", False)

        if not home or not away:
            return {"error": "home_team and away_team are required"}

        try:
            from models.soccer_predictor import SoccerPredictor
            predictor = SoccerPredictor(league=league or "default")
            home_stats = get_soccer_team_stats(home, league)
            away_stats = get_soccer_team_stats(away, league)

            # Build kwargs for predict (matching batch_run_soccer.py pattern)
            predict_kwargs = {"league": league}
            if home_stats:
                predict_kwargs.update({
                    "home_xg_for": home_stats.get("xg_for", 1.5),
                    "home_xg_against": home_stats.get("xg_against", 1.5),
                    "home_shots": home_stats.get("shots", 12),
                })
            if away_stats:
                predict_kwargs.update({
                    "away_xg_for": away_stats.get("xg_for", 1.5),
                    "away_xg_against": away_stats.get("xg_against", 1.5),
                    "away_shots": away_stats.get("shots", 12),
                })

            # Call predict with correct signature (features=None, model=None)
            result = predictor.predict(
                features=None,
                model=None,
                home_team=home,
                away_team=away,
                market_line=market_line or 0.0,
                market_total=market_total,
                **predict_kwargs
            )

            if push:
                preds = result.get("predictions", {})
                total_rec = preds.get("total", {}).get("recommendation", "PASS")
                total_edge = preds.get("total", {}).get("edge", 0)
                total_conf = preds.get("total", {}).get("confidence", 0)
                push_to_discord(
                    sport="soccer",
                    home=home,
                    away=away,
                    market_total=market_total,
                    market_line=market_line,
                    recommendation=total_rec,
                    edge=f"{total_edge:+.3f}",
                    confidence=total_conf,
                )
                result["discord_pushed"] = True

            return result
        except Exception as e:
            return {"error": f"Prediction failed: {str(e)}"}

    def tool_run_slate(self, **kwargs) -> dict:
        """Run a predefined match slate."""
        slate = kwargs.get("slate_name", "").strip().lower()
        push_all = kwargs.get("push_all", False)

        slates = {
            "bundesliga_day1": [
                {
                    "home_team": "SC Paderborn 07",
                    "away_team": "SC Freiburg",
                    "league": "Bundesliga",
                    "market_total": 2.5,
                    "market_line": 0.0,
                },
            ],
            "bundesliga_matchday": [
                {
                    "home_team": "Bayern Munich",
                    "away_team": "Bayer Leverkusen",
                    "league": "Bundesliga",
                    "market_total": 2.75,
                    "market_line": -1.5,
                },
                {
                    "home_team": "Borussia Dortmund",
                    "away_team": "Schalke 04",
                    "league": "Bundesliga",
                    "market_total": 2.5,
                    "market_line": 0.0,
                },
            ],
        }

        if slate not in slates:
            return {
                "error": f"Unknown slate: {slate}",
                "available_slates": list(slates.keys()),
            }

        matches = slates[slate]
        results = []
        for match in matches:
            match["push_to_discord"] = push_all
            result = self.tool_predict_match(**match)
            results.append({
                "match": f"{match['home_team']} vs {match['away_team']}",
                "prediction": result,
            })

        return {"slate": slate, "matches": len(matches), "predictions": results}

    def tool_list_slates(self, **kwargs) -> dict:
        return {
            "slates": {
                "bundesliga_day1": "Paderborn vs Freiburg",
                "bundesliga_matchday": "Bayern vs Leverkusen, BVB vs Schalke",
            }
        }

    def handle_request(self, request: dict) -> dict:
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "predict_match",
                        "description": "Predict a soccer match outcome",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "home_team": {"type": "string"},
                                "away_team": {"type": "string"},
                                "league": {"type": "string"},
                                "market_total": {"type": "number"},
                                "market_line": {"type": "number"},
                                "push_to_discord": {"type": "boolean"},
                            },
                            "required": ["home_team", "away_team", "league"],
                        },
                    },
                    {
                        "name": "run_slate",
                        "description": "Run a predefined slate of matches",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "slate_name": {"type": "string"},
                                "push_all": {"type": "boolean"},
                            },
                            "required": ["slate_name"],
                        },
                    },
                    {
                        "name": "list_slates",
                        "description": "List available match slates",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})

            if tool_name not in self.tools:
                return {"error": f"Unknown tool: {tool_name}"}

            try:
                result = self.tools[tool_name](**tool_args)
                return {"result": result}
            except Exception as e:
                return {"error": f"Tool execution failed: {str(e)}"}

        return {"error": "Unknown method"}


def main():
    server = MCPServer()
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            request = json.loads(line)
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON"}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)


if __name__ == "__main__":
    main()
