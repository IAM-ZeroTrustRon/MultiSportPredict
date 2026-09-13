# Wales vs Ghana Match Analysis Summary

## Match Details
- **Teams:** Wales vs Ghana
- **Competition:** International Friendly
- **Date:** June 3, 2026
- **Venue:** Cardiff City Stadium
- **Analysis Type:** Comprehensive soccer handicapping

## Key Projections

### Score Prediction
- **Wales:** 1.90 expected goals
- **Ghana:** 1.51 expected goals
- **Total Goals:** 3.42
- **Most Likely Score:** 2-1 to Wales

### Probabilities
- **Over 1.5 Goals:** 85.5%
- **Over 2.5 Goals:** 66.3%
- **Over 3.5 Goals:** 44.5%
- **BTTS (Both Teams to Score):** 57.6%
- **Over 8.5 Corners:** 72.3%
- **Over 9.5 Corners:** 60.6%
- **Over 10.5 Corners:** 48.3%

## Betting Recommendations

### Primary Recommendations (HIGH Confidence)
1. **Goals Total: Over 2.5** (Probability: 66.3%)
2. **BTTS: Yes** (Probability: 65.1%)
3. **Corners Total: Over 9.5** (Probability: 60.6%)

### Model Scores
- **Goals Model Score:** 0.915
- **BTTS Model Score:** 0.151
- **Corners Model Score:** 8.027

## Team Analysis

### Wales (Home)
**Strengths:**
- Home advantage
- Better xG for (1.35 vs 1.25)
- More shots per game (11.5 vs 10.8)
- Better defensive record (1.1 GA vs 1.2 GA)
- More clean sheets (4 vs 3 in last 10)

**Weaknesses:**
- Missing a creative midfielder

**Metrics:**
- Goal Strength: 0.13
- BTTS Strength: 0.28
- Corner Strength: 1.19

### Ghana (Away)
**Strengths:**
- Faster tempo could create chances
- Wales missing a creative midfielder

**Weaknesses:**
- Missing a key attacker
- Missing a center back
- Lower xG for (1.25 vs 1.35)
- Worse defensive record

**Metrics:**
- Goal Strength: -0.24
- BTTS Strength: 0.14
- Corner Strength: 0.58

## Key Factors

### Factors Favoring Over 2.5 Goals
- Both teams have attacking intent
- Friendly match typically more open
- Total xG suggests 3.42 goals
- Both teams missing key defenders

### Factors Favoring BTTS
- Both teams missing key defenders
- Friendly nature = more attacking substitutions
- Wales strong at home (1.90 xG)
- Ghana capable of scoring away (1.51 xG)

### Factors Favoring Over Corners
- Wales high corner strength (1.19)
- Both teams generate decent shot volume
- Projected total: 10.5 corners

## Files Generated

1. **Analysis Script:** `run_wales_ghana_analysis.py`
   - Comprehensive Python script following the same structure as Murcia vs Barcelona analysis
   - Uses MultiSportModel functions for soccer analysis
   - Generates detailed console output and JSON results

2. **Odds API Ingestor:** `OddsApiIngestor.py`
   - Integrated module for fetching live betting odds from The-Odds-API.com
   - Provides structured data for model input
   - Supports multiple soccer leagues and markets

3. **Input Data:** `input/wales_ghana_analysis.csv`
   - CSV format compatible with MultiSportModel
   - Contains all team metrics for goals, BTTS, and corners analysis

4. **Output Results:** `output/wales_vs_ghana_analysis.json`
   - Complete analysis results in JSON format
   - Includes projections, probabilities, recommendations, and model details

## Model Methodology

The analysis uses a Poisson-based soccer handicapping model that considers:

1. **Team Goal Strength:** Based on xG for/against, shots, shots on target, goals scored/conceded
2. **BTTS Strength:** Considers both teams' attacking and defensive capabilities
3. **Corner Strength:** Based on shots, shots on target, final third pressure, width/crossing
4. **Contextual Factors:** Home advantage, missing players, tempo, clean sheets
5. **Market Validation:** Compares model projections with current market lines

## Confidence Assessment

**Overall Confidence: HIGH**

- Multiple markets showing strong probabilities (>60%)
- Consistent signals across goals, BTTS, and corners
- Model scores indicate positive expected value
- Factors align well with projections

## Recommendations for Use

1. **Primary Bet:** Over 2.5 goals (66.3% probability)
2. **Secondary Bet:** BTTS Yes (65.1% probability)
3. **Tertiary Bet:** Over 9.5 corners (60.6% probability)

**Bankroll Management:** Consider standard unit sizing given HIGH confidence level.

---

*Analysis generated on June 3, 2026 at 10:25 AM*
*Model: MultiSportModel v2.0 - Soccer Module*
*Confidence: HIGH*