# Automated Prediction System

## Quick Start

**No more manual CSV files or placeholder data!** Just run predictions.

### Single Match Prediction

```bash
# Soccer (default)
python predict.py mexico "south africa"

# Basketball
python predict.py --sport basketball lakers heat

# KBO (Korean baseball)
python predict.py --sport kbo "kia tigers" "hanwha eagles"
```

### Predict Upcoming Matches in a League

```bash
# Fetch upcoming EPL matches and predict all
python predict.py --upcoming --league epl

# Champions League
python predict.py --upcoming --league champions_league

# Supported leagues: epl, champions_league, la_liga, serie_a, bundesliga, ligue1, world_cup, euro
```

### Batch Processing

```bash
# Predict all upcoming matches across all sports
python predict.py --batch
```

---

## How It Works

### Before (Manual Process)
1. ❌ Manually edit CSV files
2. ❌ Add placeholder/guessed values
3. ❌ Run with fixed parameters
4. ❌ Prone to errors

### After (Automated)
1. ✅ Call `python predict.py home away`
2. ✅ Auto-fetches live odds data (if API key available)
3. ✅ Generates features on-demand
4. ✅ Caches results for fast re-runs
5. ✅ Runs model and saves output

---

## API Configuration (Optional but Recommended)

The system works even without an API key, using sensible defaults. But to get live odds data:

### Set up The-Odds-API

1. **Get API Key**: Sign up at https://the-odds-api.com/
2. **Set Environment Variable**:
   
   **Windows (PowerShell)**:
   ```powershell
   $env:ODDS_API_KEY = "your_api_key_here"
   ```
   
   **Windows (Command Prompt)**:
   ```cmd
   set ODDS_API_KEY=your_api_key_here
   ```
   
   **Linux/Mac**:
   ```bash
   export ODDS_API_KEY="your_api_key_here"
   ```

3. **Or pass it directly**:
   ```bash
   python predict.py --api-key "your_api_key" mexico "south africa"
   ```

---

## Output

Predictions are saved to:
- **Soccer**: `output/soccer/{home}_vs_{away}.json`
- **Basketball**: `output/basketball/{home}_vs_{away}.json`
- **KBO**: `output/kbo/{home}_vs_{away}.json`

Example output:
```json
{
  "sport": "soccer",
  "home_team": "Mexico",
  "away_team": "South Africa",
  "model": {
    "prediction": 2.4,
    "confidence": 0.73,
    "recommendation": "Under 2.5"
  }
}
```

---

## Under the Hood

### Auto-Dispatcher Features

**Automatic Feature Generation**
- If `data/processed/{sport}_features.csv` is missing, creates it with defaults
- Fetches live odds if API key is available
- Caches results for fast subsequent runs

**Smart Error Handling**
- Missing CSV? Auto-creates with defaults
- Missing team? Falls back to statistical averages
- API down? Uses cached/default data

**Batch Prediction**
- Process multiple matches in one run
- Parallel feature generation (scalable)
- Detailed logging for each step

---

## Troubleshooting

### "Missing feature file" error

**Before**: You'd manually edit CSV
**Now**: Auto-dispatcher handles it automatically

The system will:
1. Detect missing CSV
2. Create template with defaults
3. Retry prediction

### "No API key" warning

**Not a problem!** The system uses statistical defaults. To get live odds:
```bash
export ODDS_API_KEY="your_key"
python predict.py mexico "south africa"
```

### "No match found for X vs Y"

Check spelling (case-insensitive):
```bash
# These all work:
python predict.py mexico "south africa"
python predict.py MEXICO "SOUTH AFRICA"
python predict.py Mexico "South Africa"
```

---

## Development / Advanced Use

### Use in Code

```python
from models.auto_dispatcher import AutoDispatcher

dispatcher = AutoDispatcher(api_key="your_key")

# Single prediction
dispatcher.predict_match("soccer", "Mexico", "South Africa")

# Batch
results = dispatcher.predict_batch("soccer", [
    ("Mexico", "South Africa"),
    ("Brazil", "Argentina"),
])

# Upcoming league
dispatcher.predict_upcoming_league("soccer_epl")
```

### Access Features Directly

```python
from models.auto_dispatcher import AutoFeatureGenerator

gen = AutoFeatureGenerator(api_key="your_key")
features = gen.get_or_generate_features("soccer", "Mexico", "South Africa")
print(features)
```

---

## Feature Columns by Sport

### Soccer
- **Possession**: xG, xGA, shots, corners, form
- **Market Signals**: sharp_score, reverse_line_movement, money_ticket_gap, public_tickets_pct

### Basketball
- **Efficiency**: ORTG, DRTG, pace
- **Context**: rest difference
- **Market Signals**: (same as soccer)

### KBO
- **Hitting**: wOBA, wRC+
- **Pitching**: FIP, WHIP, bullpen FIP
- **Market Signals**: (same as soccer)

---

## Roadmap

- [ ] Multi-league batch processing
- [ ] Real-time updates every 30 minutes
- [ ] Database persistence (SQLite, PostgreSQL)
- [ ] Webhook for external triggers
- [ ] Discord/Slack notifications
- [ ] Web dashboard

---

**Questions?** Check `models/auto_dispatcher.py` for full implementation details.
