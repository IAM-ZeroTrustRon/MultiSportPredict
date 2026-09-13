# Discord Integration - Quick Start

## 5-Minute Setup

### 1️⃣ Create Discord Webhook

1. Go to your Discord server → **Server Settings** (⚙️)
2. **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Select a channel (e.g., #predictions)
5. Click **Copy Webhook URL**

Your URL looks like: `https://discordapp.com/api/webhooks/123456/abcdef...`

### 2️⃣ Create .env File

Create a file named `.env` in your project root (same folder as `app.py`):

```
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

**That's it!** (Replace `YOUR_ID/YOUR_TOKEN` with your actual webhook URL)

### 3️⃣ Test It

```bash
python test_discord.py
```

You should see a test message in your Discord channel! ✅

## Using Discord Integration

### Method 1: Automatic (Smart)
Automatically pushes to Discord if confidence is high enough:
```bash
python run_match.py --sport soccer --home Liverpool --away Arsenal
```

### Method 2: Force Push
Always sends to Discord:
```bash
python run_match.py --sport soccer --home Liverpool --away Arsenal --push-discord
```

### Method 3: Batch Processing
Process multiple matches:
```bash
python run_slate.py --push-discord
```

### Method 4: Web App
```bash
streamlit run app.py
```
Check the "Push to Discord" checkbox when you make a prediction.

## Example Discord Messages

When you push predictions, you'll see formatted messages like:

```
⚽ LIVERPOOL vs ARSENAL
Soccer Prediction
├─ Recommendation: BET
├─ Confidence: 75.5%
├─ Edge: +2.3%
└─ MultiSportPredict
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Webhook URL not set" | Check `.env` file exists in root directory with correct URL |
| "401/403 Unauthorized" | Webhook URL is invalid or expired, regenerate in Discord |
| "404 Not Found" | Webhook was deleted, create a new one |
| No message appears | Check Discord channel permissions allow bot messages |

## Advanced: Custom Messages

Edit `discord_integration.py` to customize:
- Colors (bright, dim, red, green, etc.)
- Message format (text vs embeds)
- Additional fields (odds, rankings, etc.)

## Python Script Example

```python
from discord_integration import push_to_discord

push_to_discord(
    sport="soccer",
    home="Liverpool",
    away="Arsenal",
    recommendation="BET",
    confidence=75.5,
    edge="+2.3%",
    market_total=2.5,
    use_embed=True,  # Pretty formatting
)
```

That's all you need! 🚀
