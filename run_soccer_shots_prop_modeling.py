#!/usr/bin/env python
"""
Soccer Shots Prop ML Model Runner
==================================
Trains and runs XGBoost model for soccer player Shots on Target predictions.

Usage:
    # Train the model
    python run_soccer_shots_prop_modeling.py --train
    
    # Predict for specific teams
    python run_soccer_shots_prop_modeling.py --predict --home "Shenzhen Peng City" --away "Shenzhen Juniors"
    
    # Predict for today's slate
    python run_soccer_shots_prop_modeling.py --predict --slate
    
    # Retrain with latest data
    python run_soccer_shots_prop_modeling.py --train --retrain
"""

import sys
import json
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime

# Import model and pipeline
from models.soccer_shots_prop_model import (
    SoccerShotsPropModel,
    load_historical_training_data,
    prepare_training_data_from_outputs,
)
from ingest.soccer_prop_training_data import SoccerPropTrainingPipeline


def train_model(retrain: bool = False):
    """Train the XGBoost model"""
    print("\n" + "=" * 80)
    print("TRAINING SOCCER SHOTS PROP ML MODEL")
    print("=" * 80)
    
    # Try to load from existing analysis files
    pipeline = SoccerPropTrainingPipeline()
    df = pipeline.extract_training_data()
    df = pipeline.prepare_for_training(df)
    
    # Train model
    model = SoccerShotsPropModel()
    
    # Force retrain if requested
    if retrain:
        model.model = None
    
    results = model.train(df)
    
    # Save training results
    output_dir = Path("output/soccer")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert numpy types to native Python for JSON serialization
    def convert_to_native(obj):
        if hasattr(obj, 'item'):  # numpy types
            return obj.item()
        elif isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(i) for i in obj]
        return obj
    
    results_path = output_dir / "soccer_shots_prop_model_results.json"
    with open(results_path, 'w') as f:
        json.dump({
            'training_results': convert_to_native(results),
            'metadata': convert_to_native(model.get_metadata()),
            'feature_importance': convert_to_native(model.get_feature_importance()),
            'timestamp': datetime.now().isoformat(),
        }, f, indent=2)
    
    print(f"\nResults saved to: {results_path}")
    
    return model


def predict_match(home_team: str, away_team: str, league: str = "Chinese Super League"):
    """Predict player props for a specific match"""
    print("\n" + "=" * 80)
    print(f"PREDICTING PROPS: {home_team} vs {away_team}")
    print("=" * 80)
    
    # Load model
    model = SoccerShotsPropModel()
    if model.model is None:
        print("Warning: No trained model found. Training new model...")
        model = train_model()
    
    # Try to get match data from existing analysis
    output_dir = Path("output/soccer")
    match_data = None
    
    if output_dir.exists():
        # Look for matching analysis file
        for json_file in output_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    home = data.get('game_info', {}).get('home_team', '')
                    away = data.get('game_info', {}).get('away_team', '')
                    if home_team.lower() in home.lower() and away_team.lower() in away.lower():
                        match_data = data
                        break
            except:
                continue
    
    # Use props engine to get roster data
    try:
        from models.props_engine import PropsEngine
        engine = PropsEngine()
        
        # Determine tactics
        home_tactics = {}
        away_tactics = {}
        is_low_block = 0
        
        if match_data:
            tactical = match_data.get('tactical_analysis', {})
            if 'low block' in str(tactical.get('away_style', '')).lower():
                is_low_block = 1
                away_tactics = {'is_low_block': 1}
        
        # Generate props with ML
        props = engine.generate_props(
            sport="soccer",
            home_team=home_team,
            away_team=away_team,
            league=league,
            use_ml_model=True,
            home_tactics=home_tactics,
            away_tactics=away_tactics,
        )
        
        # Display results
        print(f"\nMatch: {home_team} vs {away_team}")
        print(f"League: {league}")
        print(f"ML Model Used: {props.get('ml_model_used', False)}")
        print()
        
        print("=" * 80)
        print("PLAYER PROP RECOMMENDATIONS")
        print("=" * 80)
        
        # Group by team
        home_props = [p for p in props.get('player_props', []) if p.get('team') == home_team]
        away_props = [p for p in props.get('player_props', []) if p.get('team') == away_team]
        
        if home_props:
            print(f"\n{home_team}:")
            print("-" * 40)
            for prop in home_props[:5]:
                print(f"  {prop.get('player_name', 'Unknown'):<25} {prop.get('prop_type', 'Unknown'):<20}")
                print(f"    Line: {prop.get('line', 'N/A')} | Proj: {prop.get('projection', 'N/A')}")
                if 'edge_rating' in prop:
                    print(f"    Edge Rating: {prop['edge_rating']:.1f} ({prop.get('classification', 'N/A')})")
                if 'over_probability' in prop:
                    print(f"    Over Probability: {prop['over_probability']:.3f} | True Odds: {prop.get('true_odds', 'N/A')}")
                print(f"    Recommendation: {prop.get('recommendation', 'N/A')}")
                print()
        
        if away_props:
            print(f"\n{away_team}:")
            print("-" * 40)
            for prop in away_props[:5]:
                print(f"  {prop.get('player_name', 'Unknown'):<25} {prop.get('prop_type', 'Unknown'):<20}")
                print(f"    Line: {prop.get('line', 'N/A')} | Proj: {prop.get('projection', 'N/A')}")
                if 'edge_rating' in prop:
                    print(f"    Edge Rating: {prop['edge_rating']:.1f} ({prop.get('classification', 'N/A')})")
                if 'over_probability' in prop:
                    print(f"    Over Probability: {prop['over_probability']:.3f} | True Odds: {prop.get('true_odds', 'N/A')}")
                print(f"    Recommendation: {prop.get('recommendation', 'N/A')}")
                print()
        
        # Save predictions
        output_dir = Path("output/soccer")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{home_team.replace(' ', '_')}_vs_{away_team.replace(' ', '_')}_props.json"
        
        with open(output_path, 'w') as f:
            json.dump(props, f, indent=2)
        
        print(f"\nPredictions saved to: {output_path}")
        
        return props
        
    except Exception as e:
        print(f"Error predicting props: {e}")
        import traceback
        traceback.print_exc()
        return None


def predict_slate():
    """Predict for all available match data"""
    print("\n" + "=" * 80)
    print("PREDICTING TODAY'S SLATE")
    print("=" * 80)
    
    # Load model
    model = SoccerShotsPropModel()
    if model.model is None:
        print("Warning: No trained model found. Training new model...")
        model = train_model()
    
    # Find all soccer analysis files
    output_dir = Path("output/soccer")
    if not output_dir.exists():
        print(f"Error: {output_dir} not found")
        return
    
    json_files = list(output_dir.glob("*.json"))
    print(f"Found {len(json_files)} match analyses")
    
    predictions = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                match_data = json.load(f)
            
            home_team = match_data.get('game_info', {}).get('home_team', '')
            away_team = match_data.get('game_info', {}).get('away_team', '')
            
            if home_team and away_team:
                print(f"\nProcessing: {home_team} vs {away_team}")
                result = predict_match(home_team, away_team)
                if result:
                    predictions.append(result)
        
        except Exception as e:
            print(f"Warning: Could not process {json_file}: {e}")
            continue
    
    # Save all predictions
    if predictions:
        output_path = Path("output/soccer") / "slate_predictions.json"
        with open(output_path, 'w') as f:
            json.dump(predictions, f, indent=2)
        print(f"\nAll predictions saved to: {output_path}")
    
    return predictions


def main():
    parser = argparse.ArgumentParser(description="Soccer Shots Prop ML Model")
    parser.add_argument('--train', action='store_true', help='Train the model')
    parser.add_argument('--retrain', action='store_true', help='Force retrain even if model exists')
    parser.add_argument('--predict', action='store_true', help='Run predictions')
    parser.add_argument('--home', type=str, help='Home team name')
    parser.add_argument('--away', type=str, help='Away team name')
    parser.add_argument('--league', type=str, default='Chinese Super League', help='League name')
    parser.add_argument('--slate', action='store_true', help='Predict for all matches in slate')
    
    args = parser.parse_args()
    
    if args.train:
        train_model(retrain=args.retrain)
    
    if args.predict:
        if args.slate:
            predict_slate()
        elif args.home and args.away:
            predict_match(args.home, args.away, args.league)
        else:
            print("Error: --predict requires either --slate or both --home and --away")
            parser.print_help()
    
    if not args.train and not args.predict:
        parser.print_help()
        print("\nExample usage:")
        print("  python run_soccer_shots_prop_modeling.py --train")
        print("  python run_soccer_shots_prop_modeling.py --predict --home 'Shenzhen Peng City' --away 'Shenzhen Juniors'")


if __name__ == "__main__":
    main()