# Discord Integration Usage Guide

Complete guide on how to use Discord integration across all your scripts.

## Prerequisites

1. ✅ Create `.env` file with your Discord webhook URL (see DISCORD_QUICKSTART.md)
2. ✅ Run `python test_discord.py` to verify setup
3. ✅ Ensure `.env` is in your `.gitignore` (it already is)

---

## 📋 Using Discord with Each Script

### 1. `run_match.py` - Single Match Predictions

**Basic (auto-push if confident):**
```bash
python run_match.py --sport soccer --home "Liverpool" --away "Arsenal"
```

**Force Discord push:**
```bash
python run_match.py --sport soccer --home "Liverpool" --away "Arsenal" --push-discord
```

**With market information:**
```bash
python run_match.py --sport mlb --home "NYY" --away "BOS" --market-line 0.0 --market-total 8.5 --push-discord
```

### 2. `run_slate.py` - Batch Processing

**Process multiple matches from CSV:**
```bash
python run_slate.py --input matches.csv --push-discord
```

**All results pushed to Discord automatically**

CSV format (`matches.csv`):
```
sport,home,away,league
soccer,Liverpool,Arsenal,Premier League
basketball,Real Madrid,FC Barcelona,EuroLeague
baseball,NYY,BOS,MLB
```

### 3. `predict_match.py` - Legacy CLI

**Basic prediction (original CLI):**
```bash
python predict_match.py soccer "Liverpool" "Arsenal"
```

Update your code to push to Discord:
```python
from discord_integration import push_to_discord

push_to_discord(
    sport="soccer",
    home="Liverpool",
    away="Arsenal",
    recommendation="BET",
    confidence=75.5,
    edge="+2.3%",
)
```

### 4. `app.py` - Streamlit Web Interface

```bash
streamlit run app.py
```

Features:
- ✅ "Push to Discord" checkbox on prediction form
- ✅ One-click Discord updates
- ✅ Automatic rich embed formatting

### 5. Python Scripts - Direct Integration

**In any of your analysis scripts:**

```python
from discord_integration import push_to_discord, push_batch_to_discord

# Single prediction
push_to_discord(
    sport="soccer",
    home="Liverpool",
    away="Arsenal",
    recommendation="BET",
    confidence=75.5,
    edge="+2.3%",
    market_total=2.5,
    use_embed=True,  # Pretty formatting
    additional_fields={
        "Injury Status": "Both teams at full strength",
        "Recent Form": "Liverpool 3W, Arsenal 2W"
    }
)

# Batch predictions
predictions = [
    {
        "sport": "soccer",
        "home": "Liverpool",
        "away": "Arsenal",
        "recommendation": "BET",
        "confidence": 75.5,
        "edge": "+2.3%",
    },
    {
        "sport": "basketball",
        "home": "Real Madrid",
        "away": "Barcelona",
        "recommendation": "LEAN",
        "confidence": 62.0,
        "edge": "+1.5%",
    }
]
push_batch_to_discord(predictions)
```

---

## 🎨 Message Formatting Options

### Rich Embeds (Recommended)
```python
push_to_discord(
    sport="soccer",
    home="Liverpool",
    away="Arsenal",
    recommendation="BET",
    confidence=75.5,
    edge="+2.3%",
    use_embed=True,  # ← Colored, formatted cards
)
```

**Result in Discord:**
```
⚽ LIVERPOOL vs ARSENAL
Soccer Prediction
📊 Recommendation: BET
📈 Confidence: 75.5%
💰 Edge: +2.3%
```

### Plain Text
```python
push_to_discord(
    sport="soccer",
    home="Liverpool",
    away="Arsenal",
    recommendation="BET",
    confidence=75.5,
    edge="+2.3%",
    use_embed=False,  # ← Plain text message
)
```

---

## 🔧 Advanced Customization

### Custom Colors

Edit `discord_integration.py`:
```python
COLORS = {
    "strong_bet": 3066993,    # Green
    "bet": 10181046,          # Light blue
    "lean": 16776960,         # Yellow
    "pass": 15158332,         # Red
    "neutral": 9807270,       # Gray
}
```

[Find color codes here](https://www.sitepoint.com/quick-tip-convert-hex-to-rgb-with-javascript/)

### Custom Emojis

Edit `discord_integration.py`:
```python
SPORT_EMOJIS = {
    "soccer": "⚽",
    "basketball": "🏀",
    "baseball": "⚾",
    # Add more...
}
```

### Additional Fields

```python
push_to_discord(
    sport="soccer",
    home="Liverpool",
    away="Arsenal",
    recommendation="BET",
    confidence=75.5,
    edge="+2.3%",
    additional_fields={
        "📍 Venue": "Emirates Stadium",
        "🌧️ Weather": "Light Rain, 12°C",
        "⚠️ Injuries": "Salah - Hamstring (Day-to-Day)",
        "📊 xG": "Liverpool 2.1 - Arsenal 1.3"
    }
)
```

---

## 🐛 Troubleshooting

### Test Your Setup
```bash
python test_discord.py
```

### Check Webhook
```python
from discord_integration import test_webhook

if test_webhook():
    print("✓ Webhook is working!")
else:
    print("✗ Webhook is invalid")
```

### Debug Logging
```python
import logging

logging.basicConfig(level=logging.DEBUG)

# Now run your code with verbose output
```

---

## 📊 Complete Example: Soccer Match with All Features

```python
from discord_integration import push_to_discord

# Get your prediction
home = "Liverpool"
away = "Arsenal"
confidence = 78.5
recommendation = "BET"
edge = "+2.8%"

# Push to Discord with all options
push_to_discord(
    sport="soccer",
    home=home,
    away=away,
    recommendation=recommendation,
    confidence=confidence,
    edge=edge,
    market_total=2.5,
    use_embed=True,
    additional_fields={
        "🏆 Form": "Liverpool 4W-1D, Arsenal 3W-2D",
        "🥅 xG (Last 5)": "Liverpool 11.2, Arsenal 9.8",
        "⚠️ Key Players": "Salah OUT, Martinelli IN",
        "📊 Win Probability": "65%",
        "💰 Implied Odds": "-180 (64.3%)"
    }
)
```

**Result in Discord:**

```
⚽ LIVERPOOL vs ARSENAL
Soccer Prediction
📊 Recommendation: BET
📈 Confidence: 78.5%
💰 Edge: +2.8%
📍 Market Total: 2.5
🏆 Form: Liverpool 4W-1D, Arsenal 3W-2D
🥅 xG (Last 5): Liverpool 11.2, Arsenal 9.8
⚠️ Key Players: Salah OUT, Martinelli IN
📊 Win Probability: 65%
💰 Implied Odds: -180 (64.3%)
```

---

## 🚀 Next Steps

1. ✅ Set up `.env` with your webhook URL
2. ✅ Run `python test_discord.py`
3. ✅ Use any of the methods above to start pushing predictions
4. ✅ Customize colors and emojis for your server
5. ✅ Integrate into your daily prediction workflow

**Questions?** Check the logs:
```bash
python test_discord.py  # Shows detailed setup info
```
