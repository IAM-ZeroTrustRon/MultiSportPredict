r"""
European Basketball ML Model
============================
Machine Learning pipeline for European basketball predictions.

Features:
- Date-based train/validation/test splits
- Automatic feature engineering
- Random Forest models for regression and classification
- Model persistence with joblib
- Prediction scoring for new games

Usage:
    python EuroBallMLModel.py --train --data data/
    python EuroBallMLModel.py --predict --input input/new_games.csv --models models/
"""

import pandas as pd
import numpy as np
from pathlib import Path
from glob import glob
import json
import joblib
import argparse
from datetime import datetime

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score
from sklearn.exceptions import NotFittedError

# Configuration
DATA_DIR = Path("data")
OUT_DIR = Path("output")
MODEL_DIR = Path("models")

# Ensure directories exist
OUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# DATA LOADING
# ============================================================================

def load_file(path):
    """Load a single CSV or JSON file into a DataFrame"""
    ext = Path(path).suffix.lower()
    
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext == ".json":
        try:
            df = pd.read_json(path)
        except ValueError:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                df = pd.json_normalize(raw)
            elif isinstance(raw, dict):
                df = pd.json_normalize(raw)
            else:
                raise ValueError(f"Unsupported JSON format in {path}")
    else:
        raise ValueError(f"Unsupported file type: {path}")
    
    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["source_file"] = Path(path).name
    return df


def load_all_data(folder=DATA_DIR):
    """Load all CSV and JSON files from a directory"""
    files = []
    files.extend(glob(str(folder / "*.csv")))
    files.extend(glob(str(folder / "*.json")))
    files.extend(glob(str(folder / "**/*.csv"), recursive=True))
    files.extend(glob(str(folder / "**/*.json"), recursive=True))
    
    if not files:
        raise FileNotFoundError(f"No CSV or JSON files found in {folder}")
    
    frames = []
    for f in files:
        try:
            frames.append(load_file(f))
        except Exception as e:
            print(f"Skipping {Path(f).name}: {e}")
    
    if not frames:
        raise ValueError("No readable files found.")
    
    return pd.concat(frames, ignore_index=True)


# ============================================================================
# DATA PREPROCESSING
# ============================================================================

def prepare_date_column(df, date_col="game_date"):
    """Prepare and sort by date column"""
    if date_col not in df.columns:
        return df
    
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col])
    out = out.sort_values(date_col).reset_index(drop=True)
    return out


def date_based_split(df, date_col="game_date", val_size=0.2, test_size=0.1):
    """
    Split DataFrame into train/val/test based on date.
    
    Args:
        df: Input DataFrame with date column
        date_col: Name of the date column
        val_size: Fraction for validation set
        test_size: Fraction for test set
    
    Returns:
        train_df, val_df, test_df
    """
    if date_col not in df.columns:
        raise ValueError(f"Missing date column: {date_col}")
    
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)
    
    n = len(df)
    if n < 30:
        raise ValueError("Not enough rows for date-based split.")
    
    test_n = max(1, int(n * test_size))
    val_n = max(1, int(n * val_size))
    train_n = n - val_n - test_n
    
    if train_n <= 0:
        raise ValueError("Split sizes too large for dataset.")
    
    train_df = df.iloc[:train_n].copy()
    val_df = df.iloc[train_n:train_n + val_n].copy()
    test_df = df.iloc[train_n + val_n:].copy()
    
    print(f"Date-based split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")
    return train_df, val_df, test_df


def safe_numeric(df):
    """Convert columns to numeric where possible"""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = pd.to_numeric(out[col], errors="ignore")
    return out


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def add_features(df):
    """Add derived features for basketball analysis"""
    df = df.copy()
    
    # Convert basketball-related columns to numeric
    basketball_keywords = [
        "ortg", "drtg", "pace", "rest", "travel", "line", "rating",
        "usage", "minutes", "reb", "ast", "tov", "ft", "fg", "3p",
        "injury", "split", "form", "margin", "total", "quarter",
        "points", "score", "win", "loss"
    ]
    
    for col in df.columns:
        if any(k in col for k in basketball_keywords):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Net rating features
    if {"offensive_rating", "defensive_rating"}.issubset(df.columns):
        df["net_rating"] = df["offensive_rating"] - df["defensive_rating"]
    
    if {"home_offensive_rating", "away_defensive_rating"}.issubset(df.columns):
        df["matchup_offense_edge"] = df["home_offensive_rating"] - df["away_defensive_rating"]
    
    if {"home_defensive_rating", "away_offensive_rating"}.issubset(df.columns):
        df["matchup_defense_edge"] = df["away_offensive_rating"] - df["home_defensive_rating"]
    
    # Rest and travel features
    if {"home_rest_days", "away_rest_days"}.issubset(df.columns):
        df["rest_edge"] = df["home_rest_days"] - df["away_rest_days"]
    
    if {"home_travel_km", "away_travel_km"}.issubset(df.columns):
        df["travel_edge"] = df["away_travel_km"] - df["home_travel_km"]
    
    # Home/away split features
    if {"home_split_edge", "away_split_edge"}.issubset(df.columns):
        df["home_away_split_edge"] = df["home_split_edge"] - df["away_split_edge"]
    
    # Line movement features
    if {"opening_line", "current_line"}.issubset(df.columns):
        df["line_move"] = df["current_line"] - df["opening_line"]
    
    # Injury features
    if {"injury_penalty_home", "injury_penalty_away"}.issubset(df.columns):
        df["injury_edge"] = df["injury_penalty_away"] - df["injury_penalty_home"]
    
    # Interaction features
    if {"pace", "rest_edge"}.issubset(df.columns):
        df["pace_rest_interaction"] = df["pace"] * df["rest_edge"]
    
    # First quarter features
    if {"first_quarter_points_for", "first_quarter_points_against"}.issubset(df.columns):
        df["first_q_net"] = df["first_quarter_points_for"] - df["first_quarter_points_against"]
    
    # Player features
    if {"player_minutes", "player_usage"}.issubset(df.columns):
        df["minutes_usage"] = df["player_minutes"] * df["player_usage"]
    
    return df


# ============================================================================
# MODEL TRAINING
# ============================================================================

def choose_task(y):
    """Determine if problem is classification or regression"""
    if y.dropna().nunique() <= 2:
        return "classification"
    if pd.api.types.is_integer_dtype(y) and y.dropna().nunique() <= 10:
        return "classification"
    return "regression"


def detect_target(df, candidates):
    """Find the first matching target column"""
    return next((c for c in candidates if c in df.columns), None)


def train_one_model(df, target_col, model_name, task=None):
    """
    Train a single model for a specific target.
    
    Args:
        df: Feature DataFrame
        target_col: Column name to predict
        model_name: Name for saving the model
        task: 'classification' or 'regression' (auto-detected if None)
    
    Returns:
        Dictionary with training results
    """
    if target_col not in df.columns:
        print(f"Skipping {model_name}: missing target '{target_col}'")
        return None
    
    # Remove rows with missing target
    data = df.dropna(subset=[target_col]).copy()
    if data.empty:
        print(f"Skipping {model_name}: no usable target values")
        return None
    
    # Get numeric feature columns
    feature_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    if target_col in feature_cols:
        feature_cols.remove(target_col)
    
    if not feature_cols:
        print(f"Skipping {model_name}: no numeric features")
        return None
    
    # Handle date-based split if date column exists
    date_col = "game_date"
    if date_col in data.columns:
        data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
        data = data.dropna(subset=[date_col]).sort_values(date_col).reset_index(drop=True)
        
        try:
            train_df, val_df, test_df = date_based_split(data, date_col=date_col, val_size=0.2, test_size=0.1)
        except ValueError as e:
            print(f"Date-based split failed for {model_name}: {e}")
            # Fall back to random split
            train_df, test_df = train_test_split(data, test_size=0.3, random_state=42)
            val_df, test_df = train_test_split(test_df, test_size=0.5, random_state=42)
    else:
        # Random split if no date column
        train_df, test_df = train_test_split(data, test_size=0.3, random_state=42)
        val_df, test_df = train_test_split(test_df, test_size=0.5, random_state=42)
    
    # Prepare features and targets
    X_train = train_df[feature_cols].replace([np.inf, -np.inf], np.nan)
    X_train = X_train.fillna(X_train.median(numeric_only=True))
    y_train = train_df[target_col]
    
    X_val = val_df[feature_cols].replace([np.inf, -np.inf], np.nan)
    X_val = X_val.fillna(X_train.median(numeric_only=True))
    y_val = val_df[target_col]
    
    X_test = test_df[feature_cols].replace([np.inf, -np.inf], np.nan)
    X_test = X_test.fillna(X_train.median(numeric_only=True))
    y_test = test_df[target_col]
    
    if len(X_train) < 20:
        print(f"Skipping {model_name}: not enough training rows ({len(X_train)})")
        return None
    
    # Auto-detect task if not specified
    if task is None:
        task = choose_task(y_train)
    
    if task == "classification" and y_train.dropna().nunique() < 2:
        print(f"Skipping {model_name}: target has only one class")
        return None
    
    try:
        # Create model
        if task == "classification":
            model = RandomForestClassifier(
                n_estimators=500,
                random_state=42,
                max_depth=10,
                min_samples_leaf=5
            )
        else:
            model = RandomForestRegressor(
                n_estimators=500,
                random_state=42,
                max_depth=10,
                min_samples_leaf=5
            )
        
        # Train
        model.fit(X_train, y_train)
        
        # Predict on validation and test sets
        val_preds = model.predict(X_val)
        test_preds = model.predict(X_test)
        
        # Calculate metrics
        if task == "classification":
            val_metrics = {"val_accuracy": accuracy_score(y_val, val_preds)}
            test_metrics = {"test_accuracy": accuracy_score(y_test, test_preds)}
        else:
            val_metrics = {
                "val_mae": mean_absolute_error(y_val, val_preds),
                "val_r2": r2_score(y_val, val_preds)
            }
            test_metrics = {
                "test_mae": mean_absolute_error(y_test, test_preds),
                "test_r2": r2_score(y_test, test_preds)
            }
        
        # Save model
        model_data = {
            "model": model,
            "columns": feature_cols,
            "task": task,
            "target": target_col,
            "feature_medians": X_train.median(numeric_only=True).to_dict()
        }
        joblib.dump(model_data, MODEL_DIR / f"{model_name}.joblib")
        
        # Save predictions
        pd.DataFrame({
            "actual": y_test.values,
            "predicted": test_preds
        }).to_csv(OUT_DIR / f"predictions_{model_name}.csv", index=False)
        
        # Save feature importance
        importance = pd.DataFrame({
            "feature": feature_cols,
            "importance": model.feature_importances_
        }).sort_values("importance", ascending=False)
        importance.to_csv(OUT_DIR / f"feature_importance_{model_name}.csv", index=False)
        
        result = {
            "model": model_name,
            "target": target_col,
            "task": task,
            "train_rows": len(X_train),
            "val_rows": len(X_val),
            "test_rows": len(X_test),
            "features": len(feature_cols),
            **val_metrics,
            **test_metrics
        }
        
        return result
    
    except NotFittedError:
        print(f"Skipping {model_name}: model not fitted")
        return None
    except Exception as e:
        print(f"Skipping {model_name}: training failed - {e}")
        return None


# ============================================================================
# PREDICTION
# ============================================================================

def predict_with_model(input_path, model_name):
    """
    Make predictions using a trained model.
    
    Args:
        input_path: Path to input CSV with game data
        model_name: Name of the model to use
    
    Returns:
        DataFrame with predictions
    """
    model_path = MODEL_DIR / f"{model_name}.joblib"
    if not model_path.exists():
        print(f"Model '{model_name}' not found. Train first with --train")
        return None
    
    # Load model
    model_data = joblib.load(model_path)
    model = model_data["model"]
    feature_cols = model_data["columns"]
    task = model_data["task"]
    feature_medians = model_data["feature_medians"]
    
    # Load input data
    df = pd.read_csv(input_path)
    df = add_features(safe_numeric(df))
    
    # Prepare features
    X = df[feature_cols].replace([np.inf, -np.inf], np.nan)
    X = X.fillna(feature_medians)
    
    # Make predictions
    predictions = model.predict(X)
    probabilities = None
    
    if task == "classification":
        probabilities = model.predict_proba(X)
        classes = model.classes_
    
    # Create results DataFrame
    results = df.copy()
    results[f"{model_name}_prediction"] = predictions
    
    if probabilities is not None:
        for i, cls in enumerate(classes):
            results[f"{model_name}_prob_{cls}"] = probabilities[:, i]
    
    return results


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def train_models(data_dir=DATA_DIR):
    """Train all models on historical data"""
    print("=" * 80)
    print("EUROPEAN BASKETBALL ML MODEL - TRAINING")
    print("=" * 80)
    print(f"Data directory: {data_dir}")
    
    # Load data
    try:
        df = load_all_data(data_dir)
        print(f"Loaded {len(df)} records from {data_dir}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading data: {e}")
        return
    
    # Preprocess
    df = add_features(safe_numeric(df))
    
    # Define model specifications
    model_specs = [
        {
            "model_name": "game_model",
            "targets": ["margin", "total_points", "home_win", "away_win", "target", "point_spread"],
            "task": None
        },
        {
            "model_name": "first_quarter_model",
            "targets": ["first_quarter_total", "first_q_total", "q1_total", "first_quarter_points", "q1_margin"],
            "task": None
        },
        {
            "model_name": "player_prop_model",
            "targets": ["player_points", "player_rebounds", "player_assists", "player_stats"],
            "task": None
        }
    ]
    
    # Train each model
    summaries = []
    for spec in model_specs:
        target_col = detect_target(df, spec["targets"])
        if target_col is None:
            print(f"Skipping {spec['model_name']}: no target found among {spec['targets']}")
            continue
        
        print(f"\nTraining {spec['model_name']} for target: {target_col}")
        result = train_one_model(
            df=df,
            target_col=target_col,
            model_name=spec["model_name"],
            task=spec["task"]
        )
        
        if result is not None:
            summaries.append(result)
            print(f"  ✓ Trained: {result}")
    
    # Save summary
    if summaries:
        summary_df = pd.DataFrame(summaries)
        summary_df.to_csv(OUT_DIR / "model_summary.csv", index=False)
        print("\n" + "=" * 80)
        print("TRAINING SUMMARY")
        print("=" * 80)
        print(summary_df.to_string(index=False))
        print(f"\nModels saved to: {MODEL_DIR}")
        print(f"Predictions saved to: {OUT_DIR}")
    else:
        print("\nNo models were trained. Check your data has the required target columns.")


def predict_games(input_path, model_name="game_model"):
    """Make predictions for new games"""
    print("=" * 80)
    print("EUROPEAN BASKETBALL ML MODEL - PREDICTION")
    print("=" * 80)
    print(f"Input: {input_path}")
    print(f"Model: {model_name}")
    
    results = predict_with_model(input_path, model_name)
    
    if results is not None:
        output_path = OUT_DIR / f"ml_predictions_{Path(input_path).stem}.csv"
        results.to_csv(output_path, index=False)
        print(f"\nPredictions saved to: {output_path}")
        print(f"\nColumns added: {[c for c in results.columns if 'prediction' in c or 'prob_' in c]}")


def main():
    parser = argparse.ArgumentParser(description="European Basketball ML Model")
    parser.add_argument("--train", action="store_true", help="Train models on historical data")
    parser.add_argument("--predict", action="store_true", help="Make predictions for new games")
    parser.add_argument("--data", type=str, default=str(DATA_DIR), help="Data directory for training")
    parser.add_argument("--input", type=str, help="Input CSV file for predictions")
    parser.add_argument("--model", type=str, default="game_model", help="Model name to use")
    
    args = parser.parse_args()
    
    if args.train:
        train_models(args.data)
    elif args.predict:
        if not args.input:
            print("Error: --input required for prediction mode")
            return
        predict_games(args.input, args.model)
    else:
        print("Usage:")
        print("  python EuroBallMLModel.py --train --data data/")
        print("  python EuroBallMLModel.py --predict --input input/new_games.csv --model game_model")


if __name__ == "__main__":
    main()