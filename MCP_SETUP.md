# MCP SERVER SETUP GUIDE
# ======================
# 
# Run the Paderborn vs Freiburg match via Cowork/Cline
# 
# OPTION 1: Via Claude Code Settings (claude_desktop_config.json)
# ---------------------------------------------------------------
# 1. Open your Claude Desktop config:
#    Windows: %APPDATA%\Claude\claude_desktop_config.json
#    Mac: ~/Library/Application\ Support/Claude/claude_desktop_config.json
#
# 2. Add this to the 'mcpServers' section:
#    {
#      "mcpServers": {
#        "multisport": {
#          "command": "python",
#          "args": ["C:\\MultiSportPredict\\mcp_server.py"]
#        }
#      }
#    }
#
# 3. Restart Claude (or the extension in your IDE)
# 4. In Cowork/Cline, use the tool selector to find 'multisport' tools
#
# AVAILABLE TOOLS
# ===============
# 1. predict_match
#    - home_team: "SC Paderborn 07"
#    - away_team: "SC Freiburg"
#    - league: "Bundesliga"
#    - market_total: 2.5
#    - push_to_discord: true/false
#
# 2. run_slate (run multiple matches at once)
#    - slate_name: "bundesliga_day1"
#    - push_all: true/false
#
# 3. list_slates
#    - No parameters needed
#
# EXAMPLE COWORK PROMPT
# =====================
# "Run the Paderborn vs Freiburg match and push to both Discord webhooks"
#
# Step 1: Call list_slates to confirm slate is available
# Step 2: Call run_slate with slate_name='bundesliga_day1' and push_all=true
# Step 3: Parse the prediction result
#
# TROUBLESHOOTING
# ===============
# - If tools don't appear: Check that the path in claude_desktop_config.json is correct
# - If connection fails: Verify Python is in PATH (python --version)
# - If predictions error: Check that universal_runner and models/* are importable
