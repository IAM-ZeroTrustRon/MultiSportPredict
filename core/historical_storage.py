"""
Historical Storage Module for MultiSportPredict
================================================
Provides SQLite-based storage for predictions across all sports.
Enables tracking of prediction performance over time.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


# Database path
DB_PATH = Path("multisport_history.db")


def init_db(db_path: Optional[Path] = None) -> None:
    """
    Initialize the SQLite database with required tables.
    
    Args:
        db_path: Optional custom database path
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    # Main predictions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            market_type TEXT NOT NULL,
            model_value REAL,
            market_value REAL,
            edge REAL,
            confidence REAL,
            recommendation TEXT,
            timestamp TEXT NOT NULL,
            raw_json TEXT,
            result_outcome TEXT,
            profit_loss REAL DEFAULT 0.0
        )
    """)

    # league wasn't part of the original table; add it if this db predates it.
    existing_columns = {row[1] for row in cur.execute("PRAGMA table_info(predictions)")}
    if "league" not in existing_columns:
        cur.execute("ALTER TABLE predictions ADD COLUMN league TEXT")

    # Index for faster queries
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_sport 
        ON predictions(sport, timestamp)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_teams 
        ON predictions(home_team, away_team)
    """)
    
    conn.commit()
    conn.close()


def store_prediction(
    sport: str,
    home_team: str,
    away_team: str,
    market_type: str,
    model_value: float,
    market_value: float,
    edge: float,
    confidence: float,
    recommendation: str,
    raw_json: Dict[str, Any],
    db_path: Optional[Path] = None,
    league: Optional[str] = None,
) -> int:
    """
    Store a prediction in the database.

    If an identical (sport, home_team, away_team, market_type) prediction was
    already logged today and hasn't been graded yet, this overwrites that row
    instead of inserting a new one -- re-running the same matchup (a common
    thing to do while testing, or to refresh with a new line) used to log a
    duplicate every time, which inflates the game count and skews the win rate
    once grading runs.

    Args:
        sport: Sport type (basketball, soccer, mlb)
        home_team: Home team name
        away_team: Away team name
        market_type: Type of market (spread, total, moneyline, props)
        model_value: Model's projected value
        market_value: Market line/value
        edge: Difference between model and market
        confidence: Confidence score (0-100)
        recommendation: Bet recommendation (STRONG BET, BET, PASS)
        raw_json: Full prediction result dictionary
        db_path: Optional custom database path
        league: Optional league/competition (e.g. "MLB", "KBO", "EPL")

    Returns:
        ID of the inserted (or overwritten) row
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    today = datetime.now().date().isoformat()
    existing = cur.execute("""
        SELECT id FROM predictions
        WHERE sport = ? AND home_team = ? AND away_team = ? AND market_type = ?
          AND date(timestamp) = ? AND result_outcome IS NULL
        ORDER BY id DESC LIMIT 1
    """, (sport, home_team, away_team, market_type, today)).fetchone()

    if existing:
        row_id = existing[0]
        cur.execute("""
            UPDATE predictions
            SET model_value = ?, market_value = ?, edge = ?, confidence = ?,
                recommendation = ?, timestamp = ?, raw_json = ?, league = ?
            WHERE id = ?
        """, (
            model_value, market_value, edge, confidence, recommendation,
            datetime.now().isoformat(), json.dumps(raw_json), league, row_id
        ))
    else:
        cur.execute("""
            INSERT INTO predictions (
                sport, home_team, away_team, market_type,
                model_value, market_value, edge,
                confidence, recommendation, timestamp, raw_json, league
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sport, home_team, away_team, market_type,
            model_value, market_value, edge,
            confidence, recommendation,
            datetime.now().isoformat(),
            json.dumps(raw_json), league
        ))
        row_id = cur.lastrowid

    conn.commit()
    conn.close()

    return row_id


def update_prediction_outcome(
    prediction_id: int,
    outcome: str,
    profit_loss: float = 0.0,
    db_path: Optional[Path] = None
) -> None:
    """
    Update a prediction with its actual outcome.
    
    Args:
        prediction_id: ID of the prediction to update
        outcome: Result outcome (win, loss, push)
        profit_loss: Profit/loss amount
        db_path: Optional custom database path
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE predictions 
        SET result_outcome = ?, profit_loss = ?
        WHERE id = ?
    """, (outcome, profit_loss, prediction_id))
    
    conn.commit()
    conn.close()


def get_predictions(
    sport: Optional[str] = None,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    market_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    recommendation_filter: Optional[str] = None,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Query predictions with optional filters.
    
    Args:
        sport: Filter by sport type
        home_team: Filter by home team
        away_team: Filter by away team
        market_type: Filter by market type
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        recommendation_filter: Filter by recommendation type
        db_path: Optional custom database path
        
    Returns:
        DataFrame with matching predictions
    """
    path = db_path or DB_PATH
    
    query = "SELECT * FROM predictions WHERE 1=1"
    params = []
    
    if sport:
        query += " AND sport = ?"
        params.append(sport)
    if home_team:
        query += " AND home_team = ?"
        params.append(home_team)
    if away_team:
        query += " AND away_team = ?"
        params.append(away_team)
    if market_type:
        query += " AND market_type = ?"
        params.append(market_type)
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)
    if recommendation_filter:
        query += " AND recommendation = ?"
        params.append(recommendation_filter)
    
    query += " ORDER BY timestamp DESC"
    
    conn = sqlite3.connect(path)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Parse raw_json column
    if not df.empty and 'raw_json' in df.columns:
        df['raw_json_parsed'] = df['raw_json'].apply(
            lambda x: json.loads(x) if x else None
        )
    
    return df


def get_prediction_summary(
    sport: Optional[str] = None,
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Get summary statistics for predictions.
    
    Args:
        sport: Optional sport filter
        db_path: Optional custom database path
        
    Returns:
        Dictionary with summary statistics
    """
    df = get_predictions(sport=sport, db_path=db_path)
    
    if df.empty:
        return {
            "total_predictions": 0,
            "sports": {},
        }
    
    # Overall summary
    total = len(df)
    strong_bets = len(df[df["recommendation"] == "STRONG BET"])
    bets = len(df[df["recommendation"] == "BET"])
    passes = len(df[df["recommendation"] == "PASS"])
    
    avg_confidence = df["confidence"].mean()
    avg_edge = df["edge"].mean()
    
    # By sport summary
    sport_summary = {}
    for sport_name in df["sport"].unique():
        sport_df = df[df["sport"] == sport_name]
        sport_summary[sport_name] = {
            "count": len(sport_df),
            "avg_confidence": round(sport_df["confidence"].mean(), 1),
            "avg_edge": round(sport_df["edge"].mean(), 2),
            "strong_bets": len(sport_df[sport_df["recommendation"] == "STRONG BET"]),
            "bets": len(sport_df[sport_df["recommendation"] == "BET"]),
        }
    
    # By market type summary
    market_summary = {}
    for market in df["market_type"].unique():
        market_df = df[df["market_type"] == market]
        market_summary[market] = {
            "count": len(market_df),
            "avg_confidence": round(market_df["confidence"].mean(), 1),
            "avg_edge": round(market_df["edge"].mean(), 2),
        }
    
    return {
        "total_predictions": total,
        "strong_bets": strong_bets,
        "bets": bets,
        "passes": passes,
        "avg_confidence": round(avg_confidence, 1),
        "avg_edge": round(avg_edge, 2),
        "by_sport": sport_summary,
        "by_market": market_summary,
        "date_range": {
            "earliest": df["timestamp"].min(),
            "latest": df["timestamp"].max()
        }
    }


def export_predictions_to_json(
    output_path: Path,
    sport: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    Export predictions to a JSON file.
    
    Args:
        output_path: Path to output JSON file
        sport: Optional sport filter
        db_path: Optional custom database path
    """
    df = get_predictions(sport=sport, db_path=db_path)
    
    # Convert to list of dicts, excluding raw_json (use parsed version)
    records = df.to_dict('records')
    for record in records:
        if 'raw_json_parsed' in record:
            record['raw_json'] = record.pop('raw_json_parsed')
        elif 'raw_json' in record:
            try:
                record['raw_json'] = json.loads(record['raw_json'])
            except:
                record['raw_json'] = None
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(records, f, indent=2, default=str)


def get_recent_predictions(
    limit: int = 10,
    sport: Optional[str] = None,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Get most recent predictions.
    
    Args:
        limit: Number of predictions to return
        sport: Optional sport filter
        db_path: Optional custom database path
        
    Returns:
        DataFrame with most recent predictions
    """
    df = get_predictions(sport=sport, db_path=db_path)
    return df.head(limit)


def delete_old_predictions(
    days_old: int = 365,
    db_path: Optional[Path] = None
) -> int:
    """
    Delete predictions older than specified days.
    
    Args:
        days_old: Delete predictions older than this many days
        db_path: Optional custom database path
        
    Returns:
        Number of deleted records
    """
    from datetime import timedelta
    
    path = db_path or DB_PATH
    cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
    
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    cur.execute("""
        DELETE FROM predictions 
        WHERE timestamp < ?
    """, (cutoff_date,))
    
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    
    return deleted