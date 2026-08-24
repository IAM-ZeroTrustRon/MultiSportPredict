#!/usr/bin/env python
"""
Soccer Prop Training Data Pipeline
===================================
Extracts features from existing match analysis JSONs to build training dataset.

Pipeline:
1. Scan output/soccer/*.json for completed analyses
2. Extract team stats, player data, and match results
3. Build feature vectors for ML training
4. Save to training_data/soccer_props_training.csv
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class SoccerPropTrainingPipeline:
    """
    Extracts and prepares training data from historical match analyses.
    """
    
    def __init__(self, output_dir: str = "output/soccer", training_dir: str = "training_data"):
        self.output_dir = Path(output_dir)
        self.training_dir = Path(training_dir)
        self.training_dir.mkdir(exist_ok=True)
        
    def extract_training_data(self) -> pd.DataFrame:
        """
        Extract training features from JSON analysis files.
        
        Returns:
            DataFrame with features and target for ML training
        """
        print("=" * 80)
        print("SOCCER PROP TRAINING DATA EXTRACTION")
        print("=" * 80)
        
        if not self.output_dir.exists():
            print(f"Warning: {self.output_dir} not found")
            return self._generate_synthetic_data()
        
        json_files = list(self.output_dir.glob("*.json"))
        if not json_files:
            print(f"No JSON files found in {self.output_dir}")
            return self._generate_synthetic_data()
        
        print(f"Found {len(json_files)} analysis files")
        
        training_records = []
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    match_data = json.load(f)
                
                records = self._extract_from_match(match_data)
                training_records.extend(records)
                
            except Exception as e:
                print(f"Warning: Could not process {json_file}: {e}")
                continue
        
        if not training_records:
            print("No valid records extracted, using synthetic data")
            return self._generate_synthetic_data()
        
        df = pd.DataFrame(training_records)
        print(f"\nExtracted {len(df)} training records from {len(json_files)} matches")
        
        # Save extracted data
        output_path = self.training_dir / "soccer_props_extracted.csv"
        df.to_csv(output_path, index=False)
        print(f"Saved to: {output_path}")
        
        return df
    
    def _extract_from_match(self, match_data: Dict) -> List[Dict]:
        """
        Extract player-level features from a single match analysis.
        """
        records = []
        
        try:
            # Extract match-level info
            home_team = match_data.get('game_info', {}).get('home_team', '')
            away_team = match_data.get('game_info', {}).get('away_team', '')
            
            # Extract team stats
            home_stats = match_data.get('team_stats', {}).get('home', {})
            away_stats = match_data.get('team_stats', {}).get('away', {})
            
            # Determine if away team uses low block
            away_tactics = match_data.get('tactical_analysis', {})
            is_low_block = 1 if 'low block' in str(away_tactics.get('away_style', '')).lower() else 0
            
            # Extract projections
            projections = match_data.get('projections', {})
            
            # Process player props if available
            player_props = match_data.get('player_props', [])
            
            for prop in player_props:
                if prop.get('prop_type') == 'Shots on Target':
                    record = self._build_player_record(
                        prop, home_team, away_team, home_stats, away_stats,
                        is_low_block, match_data
                    )
                    if record:
                        records.append(record)
            
        except Exception as e:
            print(f"Warning: Error extracting match data: {e}")
        
        return records
    
    def _build_player_record(self, prop: Dict, home_team: str, away_team: str,
                             home_stats: Dict, away_stats: Dict,
                             is_low_block: int, match_data: Dict) -> Optional[Dict]:
        """
        Build a single training record from player prop data.
        """
        try:
            player_name = prop.get('player_name', '')
            team = prop.get('team', '')
            is_home = 1 if team == home_team else 0
            
            # Get player stats (would come from roster in production)
            player_sot_per_90 = prop.get('proj_sot', 1.0)  # Use projection as proxy
            shot_accuracy = 0.35  # Default, would come from player stats
            
            # Opponent defensive stats
            if is_home:
                opp_sot_allowed = away_stats.get('sot_per_game', 4.5)
                opp_possession = away_stats.get('possession_pct', 0.50)
                defensive_width = away_stats.get('width_crossing', 0.50)
            else:
                opp_sot_allowed = home_stats.get('sot_per_game', 4.5)
                opp_possession = home_stats.get('possession_pct', 0.50)
                defensive_width = home_stats.get('width_crossing', 0.50)
            
            touches_in_box = prop.get('touches_in_box', 3.0)  # Would come from detailed stats
            
            # Determine if player hit the over (target)
            # In production, this would come from actual match results
            proj_sot = prop.get('proj_sot', 1.0)
            line = prop.get('prop_line', 1.5)
            target_hit_over = 1 if proj_sot > line else 0
            
            record = {
                'player_name': player_name,
                'team': team,
                'opponent': away_team if is_home else home_team,
                'is_home_game': is_home,
                'player_sot_per_90': player_sot_per_90,
                'shot_accuracy_pct': shot_accuracy,
                'opp_sot_allowed': opp_sot_allowed,
                'touches_in_box': touches_in_box,
                'is_low_block': is_low_block if is_home else 0,
                'possession_against': 1 - opp_possession,
                'defensive_width': defensive_width,
                'xg_for': home_stats.get('xg_for', 1.5) if is_home else away_stats.get('xg_for', 1.5),
                'recent_form': home_stats.get('recent_form', 0.50) if is_home else away_stats.get('recent_form', 0.50),
                'target_hit_over': target_hit_over,
                'match_date': match_data.get('game_info', {}).get('date', ''),
            }
            
            return record
            
        except Exception as e:
            print(f"Warning: Could not build player record: {e}")
            return None
    
    def _generate_synthetic_data(self, n_samples: int = 1000) -> pd.DataFrame:
        """
        Generate synthetic training data for demonstration.
        In production, replace with real historical data extraction.
        """
        print(f"Generating {n_samples} synthetic training samples...")
        
        np.random.seed(42)
        
        data = {
            'player_sot_per_90': np.random.uniform(0.5, 3.0, n_samples),
            'shot_accuracy_pct': np.random.uniform(0.20, 0.60, n_samples),
            'opp_sot_allowed': np.random.uniform(2.0, 7.0, n_samples),
            'touches_in_box': np.random.uniform(1.0, 8.0, n_samples),
            'is_low_block': np.random.randint(0, 2, n_samples),
            'is_home_game': np.random.randint(0, 2, n_samples),
            'possession_against': np.random.uniform(0.30, 0.70, n_samples),
            'defensive_width': np.random.uniform(0.25, 0.85, n_samples),
            'xg_for': np.random.uniform(0.8, 2.2, n_samples),
            'recent_form': np.random.uniform(0.30, 0.75, n_samples),
        }
        
        df = pd.DataFrame(data)
        
        # Simulate target
        base_prob = (
            df['player_sot_per_90'] * 0.3 +
            df['touches_in_box'] * 0.05 +
            df['shot_accuracy_pct'] * 0.2
        )
        base_prob = np.where(df['is_low_block'] == 1, base_prob * 0.8, base_prob)
        base_prob = np.where(df['is_home_game'] == 1, base_prob * 1.1, base_prob)
        
        df['target_hit_over'] = np.where(
            base_prob + np.random.normal(0, 0.2, n_samples) > 0.55,
            1, 0
        )
        
        # Save synthetic data
        output_path = self.training_dir / "soccer_props_training_synthetic.csv"
        df.to_csv(output_path, index=False)
        print(f"Saved synthetic data to: {output_path}")
        
        return df
    
    def prepare_for_training(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Prepare final training dataset with feature engineering.
        """
        if df is None:
            df = self.extract_training_data()
        
        print("\n--- Training Data Summary ---")
        print(f"Total samples: {len(df)}")
        print(f"Features: {list(df.columns)}")
        print(f"Target distribution:")
        print(df['target_hit_over'].value_counts())
        
        # Feature engineering
        if 'player_sot_per_90' in df.columns and 'opp_sot_allowed' in df.columns:
            df['sot_matchup_strength'] = df['player_sot_per_90'] / df['opp_sot_allowed']
        
        if 'shot_accuracy_pct' in df.columns and 'touches_in_box' in df.columns:
            df['volume_efficiency'] = df['shot_accuracy_pct'] * df['touches_in_box']
        
        return df


def main():
    """Run training data pipeline"""
    pipeline = SoccerPropTrainingPipeline()
    
    # Extract and prepare data
    df = pipeline.extract_training_data()
    df = pipeline.prepare_for_training(df)
    
    print("\n" + "=" * 80)
    print("TRAINING DATA READY")
    print("=" * 80)
    print(f"Use this DataFrame to train the model:")
    print(f"  model.train(df)")
    print()


if __name__ == "__main__":
    main()