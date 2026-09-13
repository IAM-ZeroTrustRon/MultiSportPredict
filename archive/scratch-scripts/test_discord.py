#!/usr/bin/env python
"""
Quick Discord Webhook Test
===========================

Run this script to test your Discord webhook configuration.

Usage:
    python test_discord.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from discord_integration import test_webhook, push_to_discord, SPORT_EMOJIS


def main():
    print("\n" + "=" * 60)
    print("🧪 Discord Webhook Configuration Test")
    print("=" * 60 + "\n")
    
    # Check if .env exists
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ ERROR: .env file not found!")
        print("\n   Create a .env file with the following content:")
        print("   DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_ID/YOUR_TOKEN")
        print("\n   See DISCORD_SETUP.md for complete instructions.")
        return 1
    
    print("✓ .env file found")
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "None":
        print("❌ ERROR: DISCORD_WEBHOOK_URL is not set in .env")
        return 1
    
    print(f"✓ Webhook URL configured: {webhook_url[:50]}...")
    print("\n" + "-" * 60)
    print("Testing webhook connection...")
    print("-" * 60 + "\n")
    
    # Test webhook
    if not test_webhook():
        print("❌ Webhook test failed!")
        print("\n   Possible issues:")
        print("   • Webhook URL is invalid or expired")
        print("   • Network connection issue")
        print("   • Discord API is temporarily unavailable")
        return 1
    
    print("\n" + "-" * 60)
    print("Sending test prediction...")
    print("-" * 60 + "\n")
    
    # Send test prediction
    success = push_to_discord(
        sport="soccer",
        home="Test Team A",
        away="Test Team B",
        recommendation="BET",
        confidence=75.5,
        edge="+2.3%",
        market_total=2.5,
        use_embed=True,
    )
    
    if success:
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Discord integration is working!")
        print("=" * 60)
        print("\nYou can now use Discord predictions with:")
        print("\n  1. CLI (force push):")
        print("     python run_match.py --sport soccer --home Liverpool --away Arsenal --push-discord")
        print("\n  2. Batch processing:")
        print("     python run_slate.py --push-discord")
        print("\n  3. Web app:")
        print("     streamlit run app.py  # Check 'Push to Discord' checkbox")
        print("\n" + "=" * 60 + "\n")
        return 0
    else:
        print("\n❌ Failed to send test prediction")
        return 1


if __name__ == "__main__":
    exit(main())
