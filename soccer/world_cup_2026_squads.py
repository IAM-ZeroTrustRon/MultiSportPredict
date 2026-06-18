"""
2026 World Cup Squad Metrics
=============================
Contains squad-season data and defensive profiles for 
Canada, Qatar, Mexico, and South Korea to feed into the prediction model.
"""

import pandas as pd


def load_world_cup_squad_metrics():
    """
    Returns player attacking metrics and team defensive profiles.
    """
    player_data = {
        'player_name': [
            # Canada (Group B)
            'Jonathan David', 'Cyle Larin', 'Alphonso Davies', 'Stephen Eustaquio',
            # Qatar (Group B)
            'Akram Afif', 'Almoez Ali', 'Yusuf Abdurisag', 'Abdulaziz Hatem',
            # Mexico (Co-Hosts)
            'Santiago Gimenez', 'Hirving Lozano', 'Julian Quinones', 'Edson Alvarez',
            # South Korea
            'Son Heung-min', 'Lee Kang-in', 'Hwang Hee-chan', 'Cho Gue-sung'
        ],
        'team': [
            'Canada', 'Canada', 'Canada', 'Canada',
            'Qatar', 'Qatar', 'Qatar', 'Qatar',
            'Mexico', 'Mexico', 'Mexico', 'Mexico',
            'South Korea', 'South Korea', 'South Korea', 'South Korea'
        ],
        'position': [
            'FW', 'FW', 'LW/LWB', 'CM',
            'FW/LW', 'FW', 'RW', 'CM',
            'FW', 'LW', 'RW/FW', 'DM',
            'LW/FW', 'RW/AM', 'LW', 'FW'
        ],
        '90s_played': [8.5, 7.2, 8.0, 8.0, 6.0, 5.5, 4.2, 5.0, 9.0, 7.5, 6.8, 8.5, 8.0, 7.5, 6.0, 4.5],
        'shots_per_90': [2.85, 2.10, 1.45, 0.85, 2.20, 1.85, 1.10, 0.60, 3.15, 2.70, 2.45, 0.95, 2.95, 2.10, 2.25, 2.80],
        'sot_per_90': [1.35, 0.95, 0.55, 0.20, 0.90, 0.80, 0.35, 0.15, 1.45, 1.10, 0.95, 0.25, 1.50, 0.95, 1.05, 1.15],
        'shot_accuracy_pct': [47.3, 45.2, 37.9, 23.5, 40.9, 43.2, 31.8, 25.0, 46.0, 40.7, 38.7, 26.3, 50.8, 45.2, 46.6, 41.0],
        'touches_in_box_per_90': [5.8, 4.2, 3.5, 0.9, 4.1, 3.8, 2.5, 0.5, 6.2, 5.1, 4.8, 0.8, 5.5, 4.0, 4.9, 5.2],
        'takes_free_kicks': [1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0]
    }

    team_defensive_data = {
        'team_name': ['Canada', 'Qatar', 'Mexico', 'South Korea'],
        'opp_defensive_style': ['Mid Block', 'Low Block', 'High Press', 'Mid Block / Transition'],
        'opp_shots_allowed_per_90': [11.5, 14.8, 9.2, 10.5],
        'opp_sot_allowed_per_90': [3.8, 5.2, 2.9, 3.4],
        'avg_possession_pct': [48.5, 38.0, 56.5, 52.0]
    }

    df_players = pd.DataFrame(player_data)
    df_teams = pd.DataFrame(team_defensive_data)

    return df_players, df_teams


def get_team_attack_profile(team_name):
    """
    Get aggregated attacking profile for a team from player data.
    """
    players, defenses = load_world_cup_squad_metrics()
    
    team_players = players[players['team'] == team_name]
    
    if team_players.empty:
        return None
    
    profile = {
        'team': team_name,
        'avg_shots_per_90': team_players['shots_per_90'].mean(),
        'avg_sot_per_90': team_players['sot_per_90'].mean(),
        'avg_shot_accuracy': team_players['shot_accuracy_pct'].mean(),
        'avg_box_touches': team_players['touches_in_box_per_90'].mean(),
        'total_90s': team_players['90s_played'].sum(),
        'player_count': len(team_players)
    }
    
    # Merge defensive context
    defense_row = defenses[defenses['team_name'] == team_name]
    if not defense_row.empty:
        profile['defensive_style'] = defense_row.iloc[0]['opp_defensive_style']
        profile['shots_allowed_per_90'] = defense_row.iloc[0]['opp_shots_allowed_per_90']
        profile['sot_allowed_per_90'] = defense_row.iloc[0]['opp_sot_allowed_per_90']
        profile['avg_possession_pct'] = defense_row.iloc[0]['avg_possession_pct']
    
    return profile


def get_matchup_context(home_team, away_team):
    """
    Get full matchup context for two teams.
    """
    home_profile = get_team_attack_profile(home_team)
    away_profile = get_team_attack_profile(away_team)
    
    return {
        'home': home_profile,
        'away': away_profile
    }


if __name__ == "__main__":
    print("Loading 2026 World Cup Squad Metrics for CAN, QAT, MEX, KOR...")
    players, defenses = load_world_cup_squad_metrics()

    print("\n--- Player Attacking Baselines ---")
    print(players[['player_name', 'team', 'shots_per_90', 'sot_per_90', 'shot_accuracy_pct']].head(10).to_string(index=False))

    print("\n--- Team Defensive Profiles ---")
    print(defenses.to_string(index=False))

    print("\n--- Matchup Context: Canada vs Qatar ---")
    context = get_matchup_context('Canada', 'Qatar')
    print(context)