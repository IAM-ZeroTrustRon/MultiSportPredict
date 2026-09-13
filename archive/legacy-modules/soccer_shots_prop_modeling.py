import pandas as pd
import numpy as np
import warnings
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, classification_report
import xgboost as xgb

warnings.filterwarnings('ignore')

def load_historical_training_data():
    """
    Simulates loading thousands of past matches/props to train the ML model.
    In production, this would be your cached database of historical scrapes.
    """
    print("Loading historical data for model training...")
    
    # We create a fake dataset of 1000 past player props
    np.random.seed(42)
    n_samples = 1000
    
    data = {
        'player_sot_per_90': np.random.uniform(0.5, 3.0, n_samples),
        'shot_accuracy_pct': np.random.uniform(0.20, 0.60, n_samples),
        'opp_sot_allowed': np.random.uniform(2.0, 7.0, n_samples),
        'touches_in_box': np.random.uniform(1.0, 8.0, n_samples),
        'is_low_block': np.random.randint(0, 2, n_samples), # 1 for Yes, 0 for No
        'is_home_game': np.random.randint(0, 2, n_samples),
    }
    
    df = pd.DataFrame(data)
    
    # Simulate the actual outcome (Did they get 1+ Shots on Target?)
    # We artificially make the outcome correlate with our features so the ML can learn it
    base_prob = (df['player_sot_per_90'] * 0.3) + (df['touches_in_box'] * 0.05)
    base_prob = np.where(df['is_low_block'] == 1, base_prob * 0.8, base_prob) # Low block hurts SoT
    
    # 1 = Hit the Over, 0 = Missed the Over
    df['target_hit_over'] = np.where(base_prob + np.random.normal(0, 0.2, n_samples) > 0.6, 1, 0)
    
    return df

def train_prop_model(df):
    """
    Trains an XGBoost model to predict if a player will hit their prop over.
    """
    print("\n--- Training XGBoost Model ---")
    
    # Define our features (X) and what we are trying to predict (y)
    features = ['player_sot_per_90', 'shot_accuracy_pct', 'opp_sot_allowed', 
                'touches_in_box', 'is_low_block', 'is_home_game']
    
    X = df[features]
    y = df['target_hit_over']
    
    # Split data: 80% to train the model, 20% to blind-test it (Backtesting)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Initialize the XGBoost Classifier
    model = xgb.XGBClassifier(
        n_estimators=100, 
        learning_rate=0.1, 
        max_depth=4,
        objective='binary:logistic',
        eval_metric='logloss'
    )
    
    # Train the model
    model.fit(X_train, y_train)
    
    # --- AUTOMATED BACKTESTING ---
    print("\n--- Backtesting Results (Holdout Set) ---")
    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)[:, 1] # Probability of hitting the Over
    
    acc = accuracy_score(y_test, predictions)
    prec = precision_score(y_test, predictions)
    
    print(f"Model Accuracy (Overall Win Rate): {acc * 100:.2f}%")
    print(f"Model Precision (Win Rate when predicting 'OVER'): {prec * 100:.2f}%")
    
    # --- FEATURE IMPORTANCE ---
    # This tells us exactly what data points the model thinks are the most valuable
    print("\n--- Feature Importance (What drives the edge?) ---")
    importance = model.feature_importances_
    for i, v in enumerate(importance):
        print(f"Feature: {features[i]:<20} Score: {v:.4f}")
        
    return model, features

def predict_todays_slate(model, features):
    """
    Feeds today's matchups into the trained ML model.
    """
    print("\n--- Running Today's Slate ---")
    
    # Simulate today's raw scraped data
    todays_players = pd.DataFrame({
        'player': ['Lionel Messi', 'Mo Salah', 'Scott McTominay'],
        'player_sot_per_90': [2.8, 2.1, 0.6],
        'shot_accuracy_pct': [0.55, 0.48, 0.25],
        'opp_sot_allowed': [5.5, 4.0, 3.1],
        'touches_in_box': [7.2, 5.1, 1.2],
        'is_low_block': [1, 0, 1], # Messi faces a low block
        'is_home_game': [1, 0, 0]
    })
    
    # Ask the model for the probability of each player hitting the over
    X_today = todays_players[features]
    todays_players['Over_Probability'] = model.predict_proba(X_today)[:, 1]
    
    # Calculate American Odds equivalent for comparison against sportsbooks
    todays_players['True_Odds'] = np.where(
        todays_players['Over_Probability'] > 0.5,
        (todays_players['Over_Probability'] / (1 - todays_players['Over_Probability'])) * -100,
        (100 / todays_players['Over_Probability']) - 100
    )
    
    # Format and display
    todays_players = todays_players.sort_values(by='Over_Probability', ascending=False)
    print(todays_players[['player', 'Over_Probability', 'True_Odds']].round(2).to_string(index=False))

if __name__ == "__main__":
    # Note: Run `pip install xgboost scikit-learn pandas numpy` in your terminal first!
    historical_df = load_historical_training_data()
    trained_model, model_features = train_prop_model(historical_df)
    predict_todays_slate(trained_model, model_features)