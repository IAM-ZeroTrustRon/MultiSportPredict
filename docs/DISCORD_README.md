# 🚀 Discord Integration - What's New

Your MultiSportPredict project now has complete Discord integration! Here's everything that was added:

## 📦 What's Included

### Core Module
- **`discord_integration.py`** - Enhanced Discord webhook module with:
  - Rich embed formatting with colors
  - Support for multiple sports with emojis
  - Error handling and logging
  - Batch processing for multiple predictions
  - Webhook testing functionality

### Utilities
- **`test_discord.py`** - Quick test script to verify your setup works

### Documentation
- **`DISCORD_SETUP.md`** - Detailed setup guide with troubleshooting
- **`DISCORD_QUICKSTART.md`** - 5-minute quick start guide
- **`DISCORD_INTEGRATION_GUIDE.md`** - Complete usage guide with examples
- **`DISCORD_CHECKLIST.md`** - Step-by-step checklist for setup and troubleshooting
- **`.env.example`** - Template for your configuration file

## ⚡ Quick Start (3 Steps)

### 1. Create `.env` file
Create a file named `.env` in your project root with:
```
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

**Get your webhook URL:**
1. Go to Discord server → Server Settings (⚙️)
2. Integrations → Webhooks → New Webhook
3. Copy the URL

### 2. Test it
```bash
python test_discord.py
```

You'll see a test message in your Discord channel! ✅

### 3. Start pushing predictions
```bash
# Option 1: Force push single match
python run_match.py --sport soccer --home Liverpool --away Arsenal --push-discord

# Option 2: Process batch
python run_slate.py --push-discord

# Option 3: Web app
streamlit run app.py  # Check "Push to Discord" checkbox
```

## 🎯 Example Discord Messages

Your predictions will appear formatted like this:

```
⚽ LIVERPOOL vs ARSENAL
Soccer Prediction
├─ Recommendation: BET
├─ Confidence: 78.5%
├─ Edge: +2.3%
├─ Market Total: 2.5
└─ Additional Info (if provided)
```

## 📚 Documentation Guide

| Document | Purpose |
|----------|---------|
| `DISCORD_QUICKSTART.md` | **START HERE** - 5-minute setup |
| `DISCORD_CHECKLIST.md` | Step-by-step checklist & troubleshooting |
| `DISCORD_SETUP.md` | Detailed technical setup guide |
| `DISCORD_INTEGRATION_GUIDE.md` | Complete usage examples for all scripts |

## 🔧 Integration Points

Discord is already integrated into:

| Script | Feature |
|--------|---------|
| `run_match.py` | `--push-discord` flag for single predictions |
| `app.py` | "Push to Discord" checkbox in web UI |
| `run_slate.py` | `--push-discord` flag for batch processing |
| Any Python script | Import and use `discord_integration` module |

## 💡 Common Usage Patterns

### Pattern 1: Auto-Push (Smart)
```bash
python run_match.py --sport soccer --home Liverpool --away Arsenal
# Pushes if confidence > threshold
```

### Pattern 2: Always Push
```bash
python run_match.py --sport soccer --home Liverpool --away Arsenal --push-discord
# Always sends to Discord
```

### Pattern 3: Batch Processing
```bash
python run_slate.py --push-discord
# Processes all matches from CSV, pushes all results
```

### Pattern 4: Custom Script
```python
from discord_integration import push_to_discord

push_to_discord(
    sport="soccer",
    home="Liverpool",
    away="Arsenal",
    recommendation="BET",
    confidence=75.5,
    edge="+2.3%",
    use_embed=True,
)
```

## ✨ Features

✅ **Rich Formatting** - Colored embeds with emojis
✅ **Multiple Sports** - Soccer, Basketball, Baseball, Tennis, etc.
✅ **Error Handling** - Graceful failures with detailed logging
✅ **Batch Support** - Push multiple predictions at once
✅ **Testing** - Built-in webhook test function
✅ **Customization** - Colors, emojis, custom fields
✅ **Security** - .env file for API keys (already in .gitignore)
✅ **Logging** - Detailed logs for debugging

## 🐛 Troubleshooting

**Quick Test:**
```bash
python test_discord.py
```

This will:
1. ✓ Check if `.env` exists
2. ✓ Verify webhook URL is configured
3. ✓ Test webhook connectivity
4. ✓ Send a test prediction to Discord

## 📖 Next Steps

1. **Read** `DISCORD_QUICKSTART.md` (5 mins)
2. **Create** `.env` file with your webhook URL
3. **Run** `python test_discord.py`
4. **Use** any of the integration patterns above

## 🤔 Need Help?

1. Check `DISCORD_CHECKLIST.md` for troubleshooting
2. Review `DISCORD_INTEGRATION_GUIDE.md` for advanced usage
3. Read `DISCORD_SETUP.md` for detailed configuration
4. Run `python test_discord.py` for diagnostics

---

**You're all set!** Your Discord integration is ready to use. Start with `DISCORD_QUICKSTART.md` 🚀
