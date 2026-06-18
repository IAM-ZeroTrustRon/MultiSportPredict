"""
FBRef Squad Shooting Scraper
=============================
Scrapes live player shooting statistics from FBRef squad pages and applies
tactical multipliers to project Shots on Target (SoT) for prop betting.

Usage:
    from soccer.fbref_shooting_scraper import scrape_fbref_squad_shooting
    df = scrape_fbref_squad_shooting("https://fbref.com/en/squads/b8fd03ef/2023-2024/Manchester-City-Stats")
"""

import io
import warnings
from typing import Optional

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings('ignore')


def get_fallback_data() -> pd.DataFrame:
    """Provides a fallback dataset if the live web scrape fails."""
    data = {
        'Player': [
            'Erling Haaland', 'Phil Foden', 'Kevin De Bruyne', 'Rodri', 'Bernardo Silva'
        ],
        'Pos': ['FW', 'AM,FW', 'MF', 'MF', 'MF,FW'],
        '90s': [28.5, 30.2, 18.4, 32.1, 29.8],
        'Sh': [115, 88, 54, 45, 38],
        'SoT': [58, 42, 20, 12, 14],
        'SoT%': [50.4, 47.7, 37.0, 26.7, 36.8],
        'Sh/90': [4.04, 2.91, 2.93, 1.40, 1.28],
        'SoT/90': [2.04, 1.39, 1.09, 0.37, 0.47],
        'Dist': [12.4, 18.2, 22.5, 24.1, 16.5],
    }
    return pd.DataFrame(data)


def scrape_fbref_squad_shooting(
    squad_url: str,
    fallback_on_error: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Scrapes live player shooting statistics from an FBRef squad page.

    Parameters
    ----------
    squad_url : str
        FBRef squad page URL, e.g.
        "https://fbref.com/en/squads/b8fd03ef/2023-2024/Manchester-City-Stats"
    fallback_on_error : bool
        If True, returns get_fallback_data() when scraping fails.

    Returns
    -------
    pd.DataFrame or None
        Cleaned squad shooting dataframe, or fallback if enabled.
    """
    print(f"Scraping live shooting data from FBRef: {squad_url}")

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/91.0.4472.124 Safari/537.36'
        )
    }

    try:
        response = requests.get(squad_url, headers=headers, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(
            io.StringIO(response.text),
            match="Shooting",
        )

        if not tables:
            raise ValueError("Could not find the 'Shooting' table on this page.")

        df = tables[0]

        # FBRef uses a MultiIndex header (two rows); drop the top level.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel()

        # Keep only real player rows
        required_player_col = 'Player'
        if required_player_col not in df.columns:
            raise ValueError(f"Expected '{required_player_col}' column not found in table.")

        df = df[df['Player'].notna()]
        df = df[df['Player'] != 'Squad Total']
        df = df[df['Player'] != 'Opponent Total']

        cols_to_numeric = [
            '90s', 'Sh', 'SoT', 'SoT%', 'Sh/90', 'SoT/90', 'G/Sh', 'G/SoT', 'Dist'
        ]
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Remove noise from players with very little playing time
        df = df[df['90s'] >= 3.0].copy()

        df.reset_index(drop=True, inplace=True)
        return df

    except Exception as exc:
        print(f"Scraping failed: {exc}. FBRef might be rate-limiting your IP.")
        if fallback_on_error:
            print("Loading fallback historical dataset...")
            return get_fallback_data()
        return None


def engineer_shot_prop_features(
    df: pd.DataFrame,
    opponent_style: str,
    opponent_sot_allowed_90: float,
) -> pd.DataFrame:
    """
    Applies tactical multipliers to raw FBRef shooting data to project
    Shots on Target (SoT) and calculate an Edge Rating for prop markets.

    Parameters
    ----------
    df : pd.DataFrame
        Raw FBRef squad shooting data.
    opponent_style : str
        Tactical style of the opponent: 'Low Block' or 'High Line'.
    opponent_sot_allowed_90 : float
        Opponent's average SoT allowed per 90 minutes.

    Returns
    -------
    pd.DataFrame
        Enriched dataframe with projected stats and edge_rating, sorted descending.
    """
    print(f"Applying tactical multipliers. Opponent Style: {opponent_style}")

    if 'SoT/90' not in df.columns or 'Sh/90' not in df.columns:
        raise ValueError("Input dataframe is missing required 'Sh/90' or 'SoT/90' columns.")

    df = df.copy()

    # 1. Base Projections
    df['proj_total_shots'] = df['Sh/90']
    df['proj_sot'] = df['SoT/90']

    # 2. Opponent Quality Adjustment
    league_avg_sot_allowed = 4.0
    opponent_quality_modifier = opponent_sot_allowed_90 / league_avg_sot_allowed
    df['proj_sot'] = df['proj_sot'] * opponent_quality_modifier

    # 3. Tactical Environment
    if opponent_style == 'Low Block':
        df['proj_total_shots'] = df['proj_total_shots'] * 1.20
        df['proj_sot'] = df['proj_sot'] * 0.80
        # Long-range shooters get heavily blocked in low blocks
        if 'Dist' in df.columns:
            df['proj_sot'] = np.where(
                df['Dist'] > 18.0,
                df['proj_sot'] * 0.70,
                df['proj_sot'],
            )

    elif opponent_style == 'High Line':
        df['proj_total_shots'] = df['proj_total_shots'] * 0.85
        df['proj_sot'] = df['proj_sot'] * 1.15
        # Forwards in behind the defensive line benefit most
        if 'Pos' in df.columns and 'Dist' in df.columns:
            df['proj_sot'] = np.where(
                (df['Dist'] < 15.0) & (df['Pos'].astype(str).str.contains('FW')),
                df['proj_sot'] * 1.25,
                df['proj_sot'],
            )

    # 4. Final Edge Calculation
    # Higher projected SoT combined with high baseline accuracy creates the best edge
    df['edge_rating'] = (df['proj_sot'] * (df['SoT%'] / 100.0)) * 10.0

    output_cols = [
        'Player', 'Pos', '90s', 'Sh/90', 'SoT/90', 'Dist',
        'proj_total_shots', 'proj_sot', 'edge_rating',
    ]
    available_cols = [c for c in output_cols if c in df.columns]
    df = df[available_cols].sort_values(by='edge_rating', ascending=False).round(2)
    return df


__all__ = [
    'scrape_fbref_squad_shooting',
    'engineer_shot_prop_features',
    'get_fallback_data',
]