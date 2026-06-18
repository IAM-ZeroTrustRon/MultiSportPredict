"""
MLB Prop Features Pipeline
==========================
Automated pipeline for scraping live Statcast data and engineering
pitcher strikeout and batter walk features for prop betting.

Usage:
    python -m mlb.mlb_props_pipeline [days_back]

Dependencies:
    pip install pybaseball
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pybaseball as pyb

# Enable caching to prevent getting rate-limited by baseball savant during large scrapes
pyb.cache.enable()


def load_live_statcast_data(days_back=14):
    """
    Scrapes live, up-to-date pitch-level data using pybaseball's Statcast function.
    You will need to run `pip install pybaseball` in your VS Code terminal first.

    Args:
        days_back: Number of days to look back for Statcast data.

    Returns:
        Tuple of (pitch_df, matchup_df) or (None, None) on failure.
    """
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    print(f"Scraping live Statcast data from {start_date} to {end_date}...")
    try:
        # Pull real pitch-by-pitch data directly from Baseball Savant
        pitch_df = pyb.statcast(start_dt=start_date, end_dt=end_date)
        print(f"Successfully loaded {len(pitch_df)} pitches.")
    except Exception as e:
        print(f"Error scraping data: {e}")
        return None, None

    if pitch_df.empty:
        print("Warning: Statcast returned no data for this date range.")
        return None, None

    # Statcast uses 'pitcher' and 'batter' as ID columns, let's rename them to match our script
    pitch_df = pitch_df.rename(columns={'pitcher': 'pitcher_id', 'batter': 'batter_id'})
    
    # We still need a mockup for daily matchup context since pybaseball doesn't scrape umpire data or betting lines directly.
    # In a full production environment, you would scrape odds from an API like The-Odds-API and umpire data from SwishAnalytics.
    matchup_data = {
        'game_id': [1001, 1001],
        'pitcher_id': [pitch_df['pitcher_id'].iloc[0], pitch_df['pitcher_id'].iloc[100]], # Grab two real IDs from the scrape
        'pitcher_hand': ['R', 'L'],
        'batter_hand': ['L', 'R'],
        'start_time': ['16:00', '19:30'], 
        'park_factor_k': [0.95, 1.05], 
        'umpire_k_rate': [0.22, 0.28], 
    }
    
    return pitch_df, pd.DataFrame(matchup_data)


def load_sample_statcast_data():
    """
    Loads a small static sample of Statcast-style pitch data for offline testing.
    """
    df = pd.DataFrame({
        'pitcher_id': [101, 101, 102, 102, 101],
        'batter_id': [1001, 1002, 1001, 1002, 1001],
        'game_date': ['2024-06-17'] * 5,
        'inning': [1, 1, 2, 2, 3],
        'strike': [1, 0, 1, 1, 0],
        'swing': [1, 0, 1, 0, 1],
        'chase': [0, 0, 1, 1, 0],
        'zone': [1, 0, 1, 1, 0],
        'description': ['swinging_strike', 'ball', 'called_strike', 'swinging_strike', 'foul'],
        'pitch_type': ['FF', 'FF', 'SL', 'FF', 'FC'],
        'release_speed': [95.2, 96.1, 88.5, 95.0, 94.3],
        'stand': ['L', 'R', 'L', 'R', 'L'],
        'p_throws': ['R', 'R', 'L', 'L', 'R'],
    })
    return df


def engineer_pitcher_strikeout_metrics(pitches, matchups):
    """
    Compute pitcher-level strikeout rate features.

    Args:
        pitches: Pitch-level Statcast DataFrame.
        matchups: Game/matchup context DataFrame.

    Returns:
        DataFrame with pitcher strikeout features.
    """
    if pitches is None or pitches.empty:
        return pd.DataFrame()

    pitcher_hands = matchups.set_index('pitcher_id')['pitcher_hand'].to_dict()
    ump_k = matchups.set_index('game_id')['umpire_k_rate'].to_dict()
    park_k = matchups.set_index('game_id')['park_factor_k'].to_dict()

    features = []
    for pitcher_id, group in pitches.groupby('pitcher_id'):
        total = len(group)
        strikes = group['strike'].sum()
        swings = group['swing'].sum()
        chases = group['chase'].sum()
        zone = group['zone'].sum()

        csw = (total - strikes - swings) / total if total > 0 else 0.0
        swstr = (total - strikes) / total if total > 0 else 0.0
        zone_pct = zone / total if total > 0 else 0.0

        pitcher_hand = pitcher_hands.get(pitcher_id, 'R')
        matchup_row = matchups[matchups['pitcher_id'] == pitcher_id]
        game_id = matchup_row['game_id'].iloc[0] if not matchup_row.empty else None
        ump_rate = ump_k.get(game_id, 0.25)
        p_factor = park_k.get(game_id, 1.0)

        features.append({
            'pitcher_id': pitcher_id,
            'pitcher_hand': pitcher_hand,
            'csw_pct': csw,
            'swstr_pct': swstr,
            'sp_zone_pct': zone_pct,
            'sp_f_strike_pct': strikes / total if total > 0 else 0.0,
            'umpire_k_rate': ump_rate,
            'park_factor_k': p_factor,
            'proj_k_baseline': (0.20 + swstr * 0.15 + ump_rate * 0.10) * p_factor,
        })

    return pd.DataFrame(features)


def engineer_batter_walk_metrics(pitches, matchups, batter_stats):
    """
    Compute batter-level walk (BB) tendency features.

    Args:
        pitches: Pitch-level Statcast DataFrame.
        matchups: Game/matchup context DataFrame.
        batter_stats: DataFrame with batter season stats.

    Returns:
        DataFrame with batter walk features.
    """
    if pitches is None or pitches.empty:
        return pd.DataFrame()

    stat_map = batter_stats.set_index('batter_id').to_dict('index') if not batter_stats.empty else {}
    batter_hands = matchups.set_index('game_id')['batter_hand'].to_dict() if 'batter_hand' in matchups.columns else {}

    features = []
    for batter_id, group in pitches.groupby('batter_id'):
        total = len(group)
        zone = group['zone'].sum()
        swings = group['swing'].sum()
        chases = group['chase'].sum()

        zone_pct = zone / total if total > 0 else 0.0
        f_strike_pct = 1.0  # simplified; in production compute first-pitch strike %

        matchup_row = matchups[matchups['pitcher_id'].isin(pitches[pitches['batter_id'] == batter_id]['pitcher_id'].unique())]
        game_id = matchup_row['game_id'].iloc[0] if not matchup_row.empty else None
        batter_hand = batter_hands.get(game_id, 'R')
        pitcher_hand = 'R'

        platoon_adv = (batter_hand == 'L' and pitcher_hand == 'R') or (batter_hand == 'R' and pitcher_hand == 'L')

        stats = stat_map.get(batter_id, {})
        season_bb_pct = stats.get('season_bb_pct', 0.10)
        sp_chase = chases / total if total > 0 else 0.0

        features.append({
            'batter_id': batter_id,
            'batter_hand': batter_hand,
            'platoon_advantage': platoon_adv,
            'sp_zone_pct': zone_pct,
            'sp_f_strike_pct': f_strike_pct,
            'sp_chase_pct': sp_chase,
            'season_bb_pct': season_bb_pct,
            'walk_prob_multiplier': (1.25 if platoon_adv else 0.85),
        })

    return pd.DataFrame(features)


if __name__ == "__main__":
    print("Initializing MLB Prop Handicapping Pipeline...")

    # 1. Load Data (Swapped to Live Pybaseball Scrape instead of sample data)
    pitches, matchups = load_live_statcast_data(days_back=7)

    if pitches is not None:
        # Simulated Batter Season Stats (Would normally use pybaseball.batting_stats())
        # We assign these to real batter IDs pulled from the live statcast scrape
        real_batter_1 = pitches['batter_id'].dropna().unique()[0] if not pitches['batter_id'].dropna().empty else 10001
        real_batter_2 = pitches['batter_id'].dropna().unique()[1] if len(pitches['batter_id'].dropna().unique()) > 1 else 10002

        batter_stats = pd.DataFrame({
            'batter_id': [real_batter_1, real_batter_2],
            'season_bb_pct': [0.12, 0.06],
            'season_o_swing_pct': [0.25, 0.35],
            'on_deck_ops': [0.650, 0.890]
        })

        # 2. Engineer Features
        pitcher_k_features = engineer_pitcher_strikeout_metrics(pitches, matchups)
        batter_bb_features = engineer_batter_walk_metrics(pitches, matchups, batter_stats)

        print("\n--- Pitcher Strikeout Metrics ---")
        print(pitcher_k_features[['pitcher_id', 'csw_pct', 'swstr_pct', 'sp_zone_pct', 'proj_k_baseline']] if not pitcher_k_features.empty else pitcher_k_features)

        print("\n--- Batter Walk Metrics ---")
        print(batter_bb_features[['batter_id', 'platoon_advantage', 'sp_zone_pct', 'sp_f_strike_pct', 'walk_prob_multiplier']] if not batter_bb_features.empty else batter_bb_features)
    else:
        print("Unable to load live data. Exiting.")