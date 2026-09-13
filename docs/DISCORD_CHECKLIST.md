# Discord Integration Checklist ✅

Complete this checklist to enable Discord predictions in your project.

## Step 1: Configuration (5 mins)

- [ ] Have Discord server access with webhook permissions
- [ ] Create Discord webhook in Server Settings → Integrations → Webhooks
- [ ] Copy the webhook URL
- [ ] Create `.env` file in project root with:
  ```
  DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_ID/YOUR_TOKEN
  ```
- [ ] Verify `.env` is in `.gitignore` (already done ✓)
- [ ] Run `python test_discord.py` and verify message appears in Discord

## Step 2: Basic Usage (Pick One)

### Option A: CLI with Auto-Push
- [ ] Use `python run_match.py --sport soccer --home Liverpool --away Arsenal`
- [ ] Predictions auto-push when confidence is high enough

### Option B: CLI with Force Push
- [ ] Use `python run_match.py --sport soccer --home Liverpool --away Arsenal --push-discord`
- [ ] Always pushes regardless of confidence

### Option C: Batch Processing
- [ ] Create `input/slate.csv` with your matches
- [ ] Run `python run_slate.py --push-discord`
- [ ] All results push to Discord

### Option D: Web App
- [ ] Run `streamlit run app.py`
- [ ] Check "Push to Discord" checkbox
- [ ] Click submit

## Step 3: Advanced Features (Optional)

- [ ] Customize Discord message colors in `discord_integration.py`
- [ ] Add custom emojis for your sports
- [ ] Add additional fields (injuries, weather, odds, etc.)
- [ ] Set up batch processing with multiple matches
- [ ] Create Python scripts that auto-push predictions

## Step 4: Automation (Optional)

### Windows Task Scheduler
- [ ] Create `.bat` file:
  ```batch
  cd C:\MultiSportPredict
  python run_slate.py --push-discord
  ```
- [ ] Create scheduled task in Task Scheduler
- [ ] Run daily at your preferred time

### Linux/Mac Cron
- [ ] Create cron job:
  ```bash
  0 8 * * * cd /path/to/MultiSportPredict && python run_slate.py --push-discord
  ```

## Troubleshooting Checklist

If Discord integration isn't working:

- [ ] `.env` file exists in project root (not in subdirectories)
- [ ] `DISCORD_WEBHOOK_URL` is correctly copied from Discord
- [ ] No extra spaces or quotes in `.env`
- [ ] Run `python test_discord.py` successfully
- [ ] Discord channel permissions allow bot messages
- [ ] `python-dotenv` and `requests` are installed
  ```bash
  pip install python-dotenv requests
  ```

## Files Created/Modified

✅ **New Files:**
- `discord_integration.py` - Enhanced Discord module
- `test_discord.py` - Quick test script
- `.env.example` - Template for your .env
- `DISCORD_SETUP.md` - Detailed setup guide
- `DISCORD_QUICKSTART.md` - 5-minute quick start
- `DISCORD_INTEGRATION_GUIDE.md` - Complete usage guide
- `DISCORD_CHECKLIST.md` - This file

⚠️ **Existing Files (Already Support Discord):**
- `run_match.py` - Already has `--push-discord` flag
- `app.py` - Already has "Push to Discord" checkbox
- `run_slate.py` - Already supports `--push-discord` flag
- `requirements.txt` - Already has requests & python-dotenv

## Quick Start Command

```bash
# 1. Create .env file
echo DISCORD_WEBHOOK_URL=YOUR_URL_HERE > .env

# 2. Test it
python test_discord.py

# 3. Make a prediction
python run_match.py --sport soccer --home Liverpool --away Arsenal --push-discord
```

## Support

- **Setup issues?** Check `DISCORD_SETUP.md`
- **Quick start?** See `DISCORD_QUICKSTART.md`
- **Advanced usage?** Read `DISCORD_INTEGRATION_GUIDE.md`
- **Test first?** Run `python test_discord.py`

---

**Status:** ⏳ Waiting for you to complete Step 1 Configuration

Once you've created the `.env` file, run `python test_discord.py` and you'll be ready to push predictions! 🚀
