#!/usr/bin/env python
"""
XGBoost ML Model for Soccer Shots on Target Props
==================================================
Predicts whether a player will hit OVER 1.5 Shots on Target.

Features:
- Historical training with backtesting
- Feature importance analysis
- Model persistence (save/load)
- Integration with MultiSportPredict pipeline
"""

import pandas as pd
import numpy as np
import warnings
import pickle
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# ML imports
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, classification_report
from xgboost import XGBClassifier

# Import project modules
from core.confidence_engine import confidence_score

warnings.filterwarnings('ignore')


class SoccerShotsPropModel:
    """
    XGBoost-based model for predicting soccer player Shots on Target props.
    
    Usage:
        model = SoccerShotsPropModel()
        model.train(historical_df)
        predictions = model.predict(todays_df)
    """
    
    def __init__(self, model_path: str = "models/artifacts/soccer_shots_prop_model.pkl"):
        self.model_path = Path(model_path)
        self.model: Optional[XGBClassifier] = None
        self.features = [
            'player_sot_per_90',
            'shot_accuracy_pct', 
            'opp_sot_allowed',
            'touches_in_box',
            'is_low_block',
            'is_home_game',
            'possession_against',
            'defensive_width',
            'xg_for',
            'recent_form',
        ]
        self.feature_importance: Dict[str, float] = {}
        self.metadata: Dict[str, Any] = {}
        
        # Try to load existing model
        self._load_model()
    
    def train(self, df: pd.DataFrame, retrain: bool = False) -> Dict[str, Any]:
        """
        Train the XGBoost model on historical data.
        
        Args:
            df: DataFrame with features and target column 'target_hit_over'
            retrain: Force retrain even if model exists
            
        Returns:
            Dictionary with training metrics and feature importance
        """
        print("\n--- Training XGBoost Soccer Shots Prop Model ---")
        
        # Validate features exist
        missing_features = [f for f in self.features if f not in df.columns]
        if missing_features:
            raise ValueError(f"Missing required features: {missing_features}")
        
        if 'target_hit_over' not in df.columns:
            raise ValueError("DataFrame must contain 'target_hit_over' column")
        
        # Prepare data
        X = df[self.features]
        y = df['target_hit_over']
        
        # Split: 80% train, 20% test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Initialize model
        self.model = XGBClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=4,
            objective='binary:logistic',
            eval_metric='logloss',
            use_label_encoder=False,
            random_state=42,
        )
        
        # Train
        self.model.fit(X_train, y_train)
        
        # Backtesting
        predictions = self.model.predict(X_test)
        probabilities = self.model.predict_proba(X_test)[:, 1]
        
        acc = accuracy_score(y_test, predictions)
        prec = precision_score(y_test, predictions)
        
        # Feature importance
        self.feature_importance = dict(zip(self.features, self.model.feature_importances_))
        
        # Save metadata
        self.metadata = {
            'trained_at': datetime.now().isoformat(),
            'n_samples': len(df),
            'accuracy': round(acc, 4),
            'precision': round(prec, 4),
            'features': self.features,
            'feature_importance': self.feature_importance,
        }
        
        # Save model
        self._save_model()
        
        print(f"Model Accuracy: {acc * 100:.2f}%")
        print(f"Model Precision: {prec * 100:.2f}%")
        print("\n--- Feature Importance ---")
        for feat, imp in sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True):
            print(f"  {feat:<25} {imp:.4f}")
        
        return {
            'accuracy': acc,
            'precision': prec,
            'feature_importance': self.feature_importance,
            'classification_report': classification_report(y_test, predictions, output_dict=True),
        }
    
    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict Over probability for player props.
        
        Args:
            df: DataFrame with feature columns
            
        Returns:
            DataFrame with added columns: over_probability, true_odds, edge_rating, recommendation
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first or load a saved model.")
        
        # Validate features
        missing = [f for f in self.features if f not in df.columns]
        if missing:
            raise ValueError(f"Missing features for prediction: {missing}")
        
        X = df[self.features]
        
        # Get probabilities
        probs = self.model.predict_proba(X)[:, 1]
        
        # Create results DataFrame
        results = df.copy()
        results['over_probability'] = probs
        
        # Calculate true odds (American format)
        results['true_odds'] = np.where(
            probs > 0.5,
            ((probs / (1 - probs)) * -100).round(0),
            ((100 / probs) - 100).round(0)
        )
        
        # Calculate edge rating (0-10 scale)
        # Combines probability confidence and feature strength
        results['edge_rating'] = self._calculate_edge_rating(results)
        
        # Classification
        results['classification'] = results['edge_rating'].apply(self._classify_edge)
        
        # Recommendation
        results['recommendation'] = results.apply(self._generate_recommendation, axis=1)
        
        return results
    
    def _calculate_edge_rating(self, df: pd.DataFrame) -> pd.Series:
        """Calculate edge rating (0-10) based on probability and feature strength"""
        # Base from over probability (0-5 points)
        prob_score = df['over_probability'] * 5
        
        # Bonus for strong features (top 3 important)
        feature_strength = (
            df['player_sot_per_90'] * self.feature_importance.get('player_sot_per_90', 0) * 10 +
            df['touches_in_box'] * self.feature_importance.get('touches_in_box', 0) * 5 +
            df['opp_sot_allowed'] * self.feature_importance.get('opp_sot_allowed', 0) * 3
        )
        
        edge = (prob_score + feature_strength).clip(0, 10)
        return edge.round(1)
    
    def _classify_edge(self, edge: float) -> str:
        """Classify edge rating"""
        if edge >= 7.0:
            return "Elite"
        elif edge >= 5.0:
            return "Strong"
        elif edge >= 3.0:
            return "Moderate"
        else:
            return "Avoid"
    
    def _generate_recommendation(self, row: pd.Series) -> str:
        """Generate betting recommendation"""
        if row['classification'] == 'Elite':
            return f"OVER 1.5 SoT - {row.get('player_name', 'Player')}"
        elif row['classification'] == 'Strong':
            return f"Consider OVER 1.5 SoT - {row.get('player_name', 'Player')}"
        elif row['classification'] == 'Moderate':
            return f"Fade - insufficient edge"
        else:
            return f"Avoid - {row.get('player_name', 'Player')}"
    
    def _save_model(self):
        """Save model to disk"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'features': self.features,
                'feature_importance': self.feature_importance,
                'metadata': self.metadata,
            }, f)
        print(f"\nModel saved to: {self.model_path}")
    
    def _load_model(self) -> bool:
        """Load model from disk if exists"""
        if self.model_path.exists():
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                self.model = data['model']
                self.features = data['features']
                self.feature_importance = data['feature_importance']
                self.metadata = data.get('metadata', {})
                print(f"Loaded existing model from: {self.model_path}")
                return True
            except Exception as e:
                print(f"Warning: Could not load model: {e}")
        return False
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Return feature importance dict"""
        return self.feature_importance
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return model metadata"""
        return self.metadata


def load_historical_training_data() -> pd.DataFrame:
    """
    Load historical training data from project outputs.
    
    In production, this would:
    1. Query historical database of match results
    2. Extract player performance data
    3. Merge with opponent defensive stats
    4. Calculate features and targets
    
    Currently generates synthetic data for demonstration.
    """
    print("Loading historical data for model training...")
    
    # Try to load from existing analysis files first
    output_dir = Path("output/soccer")
    if output_dir.exists():
        json_files = list(output_dir.glob("*.json"))
        if json_files:
            print(f"Found {len(json_files)} existing analysis files")
            # TODO: Parse real data from JSON files
    
    # Generate synthetic training data (1000 samples)
    np.random.seed(42)
    n_samples = 1000
    
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
    
    # Simulate target (1 = Hit Over 1.5 SoT, 0 = Missed)
    base_prob = (
        df['player_sot_per_90'] * 0.3 +
        df['touches_in_box'] * 0.05 +
        df['shot_accuracy_pct'] * 0.2
    )
    # Low block penalty
    base_prob = np.where(df['is_low_block'] == 1, base_prob * 0.8, base_prob)
    # Home game boost
    base_prob = np.where(df['is_home_game'] == 1, base_prob * 1.1, base_prob)
    
    df['target_hit_over'] = np.where(
        base_prob + np.random.normal(0, 0.2, n_samples) > 0.55,
        1, 0
    )
    
    print(f"Generated {len(df)} training samples")
    print(f"Positive class (Hit Over): {df['target_hit_over'].sum()} ({df['target_hit_over'].mean():.1%})")
    
    return df


def prepare_training_data_from_outputs(output_dir: str = "output/soccer") -> pd.DataFrame:
    """
    Extract training features from existing match analysis JSON files.
    
    Args:
        output_dir: Directory containing soccer analysis JSONs
        
    Returns:
        DataFrame with features for training
    """
    output_path = Path(output_dir)
    if not output_path.exists():
        print(f"Warning: {output_dir} not found, using synthetic data")
        return load_historical_training_data()
    
    json_files = list(output_path.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {output_dir}, using synthetic data")
        return load_historical_training_data()
    
    print(f"Extracting features from {len(json_files)} analysis files...")
    
    # TODO: Parse actual JSON structure and extract features
    # For now, fall back to synthetic data
    return load_historical_training_data()


if __name__ == "__main__":
    # Standalone training script
    print("=" * 80)
    print("SOCCER SHOTS PROP MODEL - TRAINING SCRIPT")
    print("=" * 80)
    
    # Load data
    df = load_historical_training_data()
    
    # Train model
    model = SoccerShotsPropModel()
    results = model.train(df)
    
    # Show summary
    print("\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print(f"Accuracy: {results['accuracy'] * 100:.2f}%")
    print(f"Precision: {results['precision'] * 100:.2f}%")
    print("\nModel saved to: models/artifacts/soccer_shots_prop_model.pkl")