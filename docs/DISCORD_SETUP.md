# Discord Integration Setup

This guide walks you through setting up Discord webhook integration to receive your sports predictions directly in Discord.

## Prerequisites

- A Discord server where you have permissions to manage webhooks
- The ability to access server settings

## Step 1: Create a Discord Webhook

1. **Open your Discord server** and go to **Server Settings** (gear icon)
2. Navigate to **Integrations** → **Webhooks**
3. Click **"New Webhook"**
4. Configure the webhook:
   - **Name**: Something descriptive like "Sports Predictions"
   - **Channel**: Select the channel where predictions will be posted
   - Optionally upload an avatar
5. Click **Copy Webhook URL**

The URL will look like:
```
https://discordapp.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

## Step 2: Create .env File

1. In the root of your MultiSportPredict folder, create a file named `.env`
2. Add your webhook URL:
   ```
   DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
   ODDS_API_KEY=your_odds_api_key_here
   ```
3. **Save the file** (make sure it's in the root directory alongside `app.py`, `run_match.py`, etc.)

> **Security Note**: Never commit `.env` to version control. The file should be in `.gitignore`.

## Step 3: Verify .gitignore

Make sure your `.gitignore` includes:
```
.env
.env.local
*.env
```

## Step 4: Use Discord Integration

### Option A: Automatic Push (based on confidence)
```bash
python run_match.py --sport soccer --home "Liverpool" --away "Aston Villa"
```
Automatically pushes to Discord if confidence is high enough.

### Option B: Force Push to Discord
```bash
python run_match.py --sport soccer --home "Liverpool" --away "Aston Villa" --push-discord
```
Always pushes the result to Discord regardless of confidence.

### Option C: Using the Streamlit App
The Streamlit app has a **"Push to Discord"** checkbox when you run:
```bash
streamlit run app.py
```

### Option D: Batch Processing
```bash
python run_slate.py --push-discord
```
Processes multiple matches and pushes all results to Discord.

## Message Format

Discord predictions are formatted as:

```
SOCCER Prediction: Liverpool vs Aston Villa | Rec: BET | Conf: 72.5% | Edge: +2.3%
```

For match-specific markets:
```
BASEBALL Prediction: NYY vs BOS | Rec: STRONG BET | Conf: 85.1% | Edge: +5.2% | Market Line: 0.0 | Market Total: 8.5
```

## Troubleshooting

### "Discord push aborted: Webhook URL is invalid or None"
- Check that `.env` file exists in the root directory
- Verify the `DISCORD_WEBHOOK_URL` is correctly copied
- Ensure no extra spaces or quotes are in the URL
- Restart the Python process after creating/modifying `.env`

### Webhook returns 401/403 error
- Your webhook URL is invalid or expired
- Regenerate the webhook in Discord server settings

### Webhook returns 404 error
- The webhook has been deleted
- Create a new webhook and update `.env`

### No message appears in Discord
- Verify the bot has permission to send messages in the target channel
- Check Discord channel permissions: Message permissions should be enabled
- Look at the application logs for more details

## Advanced: Embed Messages (Rich Formatting)

For prettier Discord messages with embeds, you can modify the `push_to_discord()` function in `run_match.py` to send embed objects instead of plain text. Example:

```python
embed = {
    "title": f"{home} vs {away}",
    "description": f"Recommendation: {primary_recommendation}",
    "fields": [
        {"name": "Confidence", "value": f"{confidence:.1f}%", "inline": True},
        {"name": "Edge", "value": edge, "inline": True},
        {"name": "Sport", "value": sport, "inline": True}
    ],
    "color": 3066993  # Green
}
payload = {"embeds": [embed]}
```

This would create a nicely formatted card in Discord instead of plain text.

## Next Steps

Once set up:
1. Run a test prediction: `python run_match.py --sport soccer --home "Liverpool" --away "Aston Villa" --push-discord`
2. Check your Discord channel for the message
3. Integrate Discord pushes into your regular prediction workflow
4. (Optional) Set up automated daily runs using cron (Linux/Mac) or Task Scheduler (Windows)
