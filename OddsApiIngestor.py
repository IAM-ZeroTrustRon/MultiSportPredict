"""
Odds API Ingestor Module
========================
Integration with The-Odds-API.com for fetching live betting odds.
Provides structured data for the MultiSportModel's soccer analysis.

Supported Soccer Leagues:
- soccer_epl (English Premier League)
- soccer_uefa_champs_league (UEFA Champions League)
- soccer_spain_la_liga (La Liga)
- soccer_italy_serie_a (Serie A)
- soccer_germany_bundesliga (Bundesliga)
- soccer_france_ligue_one (Ligue 1)
- soccer_brazil_campeonato (Brazilian Serie A)
- soccer_fifa_world_cup (FIFA World Cup)
- soccer_uefa_euro_championship (UEFA Euro)

Author: MultiSportPredict Team
Date: June 2026
"""

import os
import json
import requests
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime

# NOTE: config.ODDS_API_DEFAULT_BASE_URL points at api.opticodds.com, which is
# what ingest/odds_client.py's OddsClient talks to -- a different API with a
# different schema. This class's request params (apiKey/regions/markets/
# oddsFormat) and response parsing (bookmakers/markets/outcomes,
# commence_time, sport_title) are The Odds API's v4 shape, so it needs its
# own default host, not the shared OptiOdds one.
THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com"


class OddsApiIngestor:
    """
    Fetches and parses betting odds from The-Odds-API.com
    Provides model-ready data for soccer match analysis.
    """
    
    def __init__(self, api_key: str = None, region: str = "us", markets: str = "h2h,spreads,totals"):
        """
        Initializes the ingestor for The Odds API.
        
        :param api_key: Your API token from the-odds-api.com (can also use env var ODDS_API_KEY)
        :param region: 'us', 'uk', 'eu', or 'au' (bookmaker region)
        :param markets: Comma-separated list of markets to pull (h2h, spreads, totals)
        """
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        if not self.api_key:
            raise ValueError("API key required. Set ODDS_API_KEY env var or pass api_key parameter.")
        
        self.base_url = os.environ.get("THE_ODDS_API_BASE_URL", THE_ODDS_API_BASE_URL)
        self.region = region
        self.markets = markets
        self.last_fetch = None
        self.cache = {}

    def fetch_live_odds(self, sport_key: str = "soccer_epl", days: int = 3) -> Optional[List[Dict]]:
        """
        Fetches raw JSON odds data for a specific league.
        
        :param sport_key: League identifier (e.g., 'soccer_epl', 'soccer_fifa_world_cup')
        :param days: Number of days of upcoming matches to fetch (max 3 for free tier)
        :return: List of match dictionaries or None on error
        """
        url = f"{self.base_url}/v4/sports/{sport_key}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": self.region,
            "markets": self.markets,
            "oddsFormat": "decimal",
            "dateFormat": "iso"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors in response
            if "errors" in data:
                print(f"[ERROR] API returned errors: {data['errors']}")
                return None
                
            self.last_fetch = datetime.now()
            
            # Cache the raw data
            self.cache[sport_key] = {
                'data': data,
                'fetched_at': self.last_fetch.isoformat()
            }
            
            return data.get('events', []) if isinstance(data, dict) else data
        except requests.exceptions.Timeout:
            print(f"[ERROR] Request timeout fetching {sport_key}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to communicate with Odds API: {e}")
            return None
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[ERROR] Invalid JSON response: {e}")
            return None

    def fetch_specific_match(self, sport_key: str, home_team: str, away_team: str) -> Optional[Dict]:
        """
        Fetch odds for a specific match by team names.
        
        :param sport_key: League identifier
        :param home_team: Home team name
        :param away_team: Away team name
        :return: Match dictionary or None
        """
        all_matches = self.fetch_live_odds(sport_key)
        if not all_matches:
            return None
        
        for match in all_matches:
            if (match.get("home_team") == home_team and 
                match.get("away_team") == away_team):
                return match
        
        # Try case-insensitive match
        for match in all_matches:
            home = match.get("home_team", "").lower().strip()
            away = match.get("away_team", "").lower().strip()
            if (home == home_team.lower().strip() and 
                away == away_team.lower().strip()):
                return match
        
        return None

    def parse_odds_to_dataframe(self, raw_json: List[Dict]) -> pd.DataFrame:
        """
        Parses complex nested JSON structure into a flattened, model-ready Pandas DataFrame.
        
        :param raw_json: List of match dictionaries from API
        :return: Flattened DataFrame with one row per bookmaker/market/selection combination
        """
        if not raw_json:
            return pd.DataFrame()

        parsed_records = []

        for match in raw_json:
            match_id = match.get("id", "unknown")
            sport = match.get("sport_title", "unknown")
            commence_time = match.get("commence_time", "")
            home_team = match.get("home_team", "")
            away_team = match.get("away_team", "")

            # Iterate through available bookmakers
            for bookmaker in match.get("bookmakers", []):
                bk_name = bookmaker.get("key", "unknown")

                for market in bookmaker.get("markets", []):
                    market_key = market.get("key", "unknown")

                    for outcome in market.get("outcomes", []):
                        name = outcome.get("name", "")
                        price = outcome.get("price")
                        point = outcome.get("point")

                        record = {
                            "match_id": match_id,
                            "sport": sport,
                            "commence_time": commence_time,
                            "home_team": home_team,
                            "away_team": away_team,
                            "bookmaker": bk_name,
                            "market_type": market_key,
                            "selection": name,
                            "odds": price if price else 0.0,
                            "line_value": float(point) if point is not None else 0.0
                        }
                        parsed_records.append(record)

        return pd.DataFrame(parsed_records)

    def extract_market_lines(self, match_data: Dict) -> Dict:
        """
        Extract key market lines from a single match for model input.
        
        :param match_data: Single match dictionary from API
        :return: Dictionary with aggregated market lines
        """
        result = {
            'match_id': match_data.get('id'),
            'home_team': match_data.get('home_team'),
            'away_team': match_data.get('away_team'),
            'commence_time': match_data.get('commence_time'),
            'moneyline_home': None,
            'moneyline_away': None,
            'moneyline_draw': None,
            'spread_home': None,
            'spread_home_line': None,
            'spread_away': None,
            'spread_away_line': None,
            'total_over': None,
            'total_under': None,
            'total_line': None,
            'bookmaker_count': 0
        }
        
        bookmakers = match_data.get('bookmakers', [])
        result['bookmaker_count'] = len(bookmakers)
        
        if not bookmakers:
            return result
        
        # Aggregate odds across bookmakers (use median for robustness)
        home_ml_odds = []
        away_ml_odds = []
        draw_ml_odds = []
        spread_home_odds = []
        spread_away_odds = []
        spread_lines = []
        over_odds = []
        under_odds = []
        total_lines = []
        
        for bookmaker in bookmakers:
            for market in bookmaker.get('markets', []):
                market_key = market.get('key')
                
                if market_key == 'h2h':
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '').strip()
                        price = outcome.get('price')
                        if price is None:
                            continue
                        
                        home_name = match_data.get('home_team', '').strip()
                        away_name = match_data.get('away_team', '').strip()
                        
                        if name == home_name:
                            home_ml_odds.append(price)
                        elif name == away_name:
                            away_ml_odds.append(price)
                        elif name.lower() == 'draw':
                            draw_ml_odds.append(price)
                
                elif market_key == 'spreads':
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '').strip()
                        price = outcome.get('price')
                        point = outcome.get('point')
                        
                        if price is None:
                            continue
                        
                        home_name = match_data.get('home_team', '').strip()
                        away_name = match_data.get('away_team', '').strip()
                        
                        if name == home_name:
                            spread_home_odds.append(price)
                            if point is not None:
                                spread_lines.append(point)
                        elif name == away_name:
                            spread_away_odds.append(price)
                            if point is not None:
                                spread_lines.append(point)
                
                elif market_key == 'totals':
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '').lower().strip()
                        price = outcome.get('price')
                        point = outcome.get('point')
                        
                        if price is None:
                            continue
                        
                        if 'over' in name:
                            over_odds.append(price)
                            if point is not None:
                                total_lines.append(point)
                        elif 'under' in name:
                            under_odds.append(price)
                            if point is not None:
                                total_lines.append(point)
        
        # Calculate medians safely
        if home_ml_odds:
            result['moneyline_home'] = sorted(home_ml_odds)[len(home_ml_odds)//2]
        if away_ml_odds:
            result['moneyline_away'] = sorted(away_ml_odds)[len(away_ml_odds)//2]
        if draw_ml_odds:
            result['moneyline_draw'] = sorted(draw_ml_odds)[len(draw_ml_odds)//2]
        if spread_home_odds:
            result['spread_home'] = sorted(spread_home_odds)[len(spread_home_odds)//2]
        if spread_away_odds:
            result['spread_away'] = sorted(spread_away_odds)[len(spread_away_odds)//2]
        if spread_lines:
            result['spread_home_line'] = sorted(spread_lines)[len(spread_lines)//2]
        if over_odds:
            result['total_over'] = sorted(over_odds)[len(over_odds)//2]
        if under_odds:
            result['total_under'] = sorted(under_odds)[len(under_odds)//2]
        if total_lines:
            result['total_line'] = sorted(total_lines)[len(total_lines)//2]
        
        return result

    def convert_decimal_to_implied_prob(self, decimal_odds: float) -> float:
        """Convert decimal odds to implied probability"""
        if decimal_odds and decimal_odds > 1:
            try:
                return 1.0 / float(decimal_odds)
            except (ValueError, ZeroDivisionError):
                return 0.0
        return 0.0

    def extract_model_ready_features(self, match_data: Dict) -> Dict:
        """
        Extract features specifically formatted for MultiSportModel soccer analysis.
        
        :param match_data: Single match dictionary from API
        :return: Dictionary with model-ready features
        """
        market_lines = self.extract_market_lines(match_data)
        
        # Convert moneyline to win probabilities
        home_prob = self.convert_decimal_to_implied_prob(market_lines['moneyline_home'])
        away_prob = self.convert_decimal_to_implied_prob(market_lines['moneyline_away'])
        draw_prob = self.convert_decimal_to_implied_prob(market_lines['moneyline_draw'])
        
        # Normalize probabilities (account for vig)
        total_prob = home_prob + away_prob + draw_prob
        if total_prob > 0:
            home_prob /= total_prob
            away_prob /= total_prob
            draw_prob /= total_prob
        
        return {
            'market_line': market_lines['total_line'] if market_lines['total_line'] else 2.5,
            'current_line': market_lines['total_line'] if market_lines['total_line'] else 2.5,
            'open_line': market_lines['total_line'] if market_lines['total_line'] else 2.5,
            'home_win_prob': round(home_prob, 4),
            'away_win_prob': round(away_prob, 4),
            'draw_prob': round(draw_prob, 4),
            'total_line': market_lines['total_line'],
            'spread_line': market_lines['spread_home_line'],
            'bookmaker_count': market_lines['bookmaker_count'],
        }


def fetch_and_save_odds(sport_key: str, output_file: str = "data/current_market_lines.csv", 
                        api_key: str = None) -> pd.DataFrame:
    """
    Convenience function to fetch odds and save to CSV.
    
    :param sport_key: League identifier
    :param output_file: Path to save CSV
    :param api_key: API key (optional if env var set)
    :return: DataFrame with parsed odds
    """
    if not api_key:
        api_key = os.environ.get("ODDS_API_KEY")
    
    if not api_key:
        print("[ERROR] No API key provided. Set ODDS_API_KEY env var or pass api_key parameter.")
        return pd.DataFrame()
    
    try:
        ingestor = OddsApiIngestor(api_key=api_key)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return pd.DataFrame()
    
    print(f"[INFO] Fetching odds for {sport_key}...")
    raw_data = ingestor.fetch_live_odds(sport_key)
    
    if not raw_data:
        print("[ERROR] No data retrieved.")
        return pd.DataFrame()
    
    df = ingestor.parse_odds_to_dataframe(raw_data)
    
    if df.empty:
        print("[WARNING] No records parsed from API response.")
        return pd.DataFrame()
    
    # Save to CSV
    try:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        df.to_csv(output_file, index=False)
        print(f"[SUCCESS] Saved {len(df)} records to {output_file}")
    except IOError as e:
        print(f"[ERROR] Failed to save CSV: {e}")
        return pd.DataFrame()
    
    return df


# Example usage and testing
if __name__ == "__main__":
    # Test with environment variable or placeholder
    API_KEY = os.environ.get("ODDS_API_KEY", "YOUR_API_KEY_HERE")
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("[INFO] No API key set. To use this module:")
        print("1. Get API key from https://the-odds-api.com")
        print("2. Set environment variable: export ODDS_API_KEY='your_key_here'")
        print("3. Or pass api_key parameter when initializing OddsApiIngestor")
        
        # Demo with sample data structure
        print("\n--- MODULE STRUCTURE DEMO ---")
        sample_match = {
            "id": "demo_match_001",
            "sport_title": "Soccer",
            "commence_time": "2026-06-03T15:00:00Z",
            "home_team": "Wales",
            "away_team": "Ghana",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Wales", "price": 2.50},
                                {"name": "Ghana", "price": 3.20},
                                {"name": "Draw", "price": 3.10}
                            ]
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "price": 1.91, "point": 2.5},
                                {"name": "Under", "price": 1.91, "point": 2.5}
                            ]
                        }
                    ]
                }
            ]
        }
        
        try:
            ingestor = OddsApiIngestor(api_key="demo")
            features = ingestor.extract_model_ready_features(sample_match)
            print("\nSample extracted features:")
            for key, value in features.items():
                print(f"  {key}: {value}")
        except ValueError:
            print("[INFO] Demo mode - API not initialized (as expected with demo key)")
    else:
        # Real API usage
        print("[INFO] Using API key from environment.")
        
        # Example: Fetch EPL odds
        df = fetch_and_save_odds("soccer_epl")
        if not df.empty:
            print("\n--- SAMPLE DATA ---")
            print(df.head(10))
