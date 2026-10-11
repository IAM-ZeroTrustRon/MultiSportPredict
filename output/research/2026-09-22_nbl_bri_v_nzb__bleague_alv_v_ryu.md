# Brisbane Bullets vs NZ Breakers · Alvark Tokyo vs Ryukyu Golden Kings
Research plus a forced run (`force_run.py`, guards off). **Not stored in the database, not graded.**

---

## 1. Brisbane Bullets vs New Zealand Breakers
**Australian NBL (NBL27) Round 1, not the NZ NBL · Tue 22 Sep · 7:30pm AEST = 5:30 AM ET · Pat Rafter Arena (open-air, first basketball game ever played there)**

### Bottom line
| Bet | Price | Model | Break-even | Call |
|---|---|---|---|---|
| **NZ +2.5** | -105 (BetMGM) | 60–69% | 51.2% | **Lean** (Low) |
| **Under 187.5** | -105 (DraftKings) | 62.5% | 51.2% | **Lean** (Low) |
| NZ ML | +115 (BetMGM) | 48–61% | 46.5% | Smaller alternative to the +2.5. Pick one |
| NZ half-time ML | +115 (Stake) | 57.6% | 46.5% | Small, and correlated with the above |
| PJC 10+ assists | +140 | about 28% (see props) | 41.7% | Pass |
| Vasiljevic 3+ threes | -143 | no data | 58.8% | Pass |

**Read this before trusting the edges.** The model's printed edges (+11 to +17) come from 2025-26 numbers. Brisbane went 6-27 last season and has **rebuilt almost the whole roster** (imports Velička, Hinton and J. Williams, coach Weaver). The model regresses last season 50% toward average; the NZ side still covers at every setting tried:

| Regress | Projected margin | NZ +2.5 cover |
|---|---|---|
| 30% | NZ by 6.0 | about 77% |
| 50% (used) | NZ by 3.3 | 68.6% |
| 70% | NZ by 0.6 | about 60% |

The printed size of the edge is not real, but the direction is consistent.

### Market (oddspedia, Before You Bet)
- **Spread:** BRI -2.5 at -109 (FanDuel), NZ +2.5 at -105 (BetMGM). Before You Bet quotes BRI -3.5.
- **Total:** 187.5, -105 / -105.
- **Moneyline:** BRI -143 / NZ +115 (BetMGM). In Australian odds: BRI $1.65 / NZ $2.25.
- **Not found:** 1Q lines, full 1H spread/total, team totals, points/rebounds/PRA props.

### Fair segment lines (model, not market)
| Segment | Fair spread | Fair total |
|---|---|---|
| 1st half | NZ by about 1.6 | about 89.2 |
| 1st quarter | NZ by about 0.8 | about 45.5 |

### Form
- **NZ, R1 (Sun 20 Sep):** beat Illawarra 95–81 at Spark Arena. Running score by quarter 28–24, 54–47, 76–61, 95–81.
  - Mennenga 27 pts, 8 reb; Vasiljevic 24 pts (6/10 from three); PJC 23 pts, 13 ast.
  - Only 5 turnovers.
- **Brisbane:** no regular-season games yet. Preseason:
  - Beat Tasmania 112–91
  - Lost to SE Melbourne 105–113
  - Lost to Cairns 98–129
  - Preseason totals were 203, 218 and 227. Weaver's teams play fast, which is the main risk to the under.

### Head to head, 2025-26 (Brisbane 3–1)
| Date | Venue | Result | Total |
|---|---|---|---|
| 19 Sep 2025 | Auckland | BRI 104–95 | 199 |
| 23 Oct 2025 | Auckland | BRI 84–83 | 167 |
| 12 Nov 2025 | Gold Coast | NZ 113–84 | 197 |
| 22 Dec 2025 | Brisbane | BRI 99–85 | 184 |

The four totals average 186.75.

### Travel and rest
- **NZ:** played Sunday in Auckland, then flew to Brisbane. About 2 days of rest. The model cuts NZ by 1.5 points for this, and that figure is an ESTIMATE.
- **Brisbane:** last played 12 Sep, about 10 days ago.

### Injuries and availability
- **Brisbane:** Taine Murray (lower leg, 4–6 weeks) and Sam McDaniel (hand, about a month). Both are likely out.
- **NZ:** Josiah-Jordan James (hamstring) is out. **Kouat Noi (ankle) left R1 early. Check his status before betting.**

### Props
- **PJC 10+ assists (+140):** 13 in R1. Last season he averaged 11.7 per 48 minutes. At about 33 minutes that is about 8.0 per game, which puts 10+ at about 28%. Pass.
- **Vasiljevic 3+ threes (-143):** 6 in R1, and no earlier per-game data found. Can't price it. Pass.

### Sharp money
**None exists for this league.** The NZ picks from Before You Bet, Dailysports and Freetips are tipster picks.

### Case against
- The model is working from last season's data.
- Brisbane beat NZ 3–1 last season despite going 6-27.
- Weaver's pace plus the preseason totals could blow up the under.
- An open-air venue is untested.

---

## 2. Alvark Tokyo vs Ryukyu Golden Kings
**B.LEAGUE B.PREMIER opener, Game 1 of 2 · Tue 22 Sep · 14:00 JST = 1:00 AM ET · TOYOTA ARENA TOKYO**

### Bottom line
| Bet | Price | Model | Break-even | Call |
|---|---|---|---|---|
| Alvark ML | -135 (book not named) | 51.7% | 57.4% | **Pass** (lean Ryukyu, but no price found) |
| Alvark 1Q ML | -116 | 50.8% | 53.7% | Pass |
| Total 158.5 | no price found | 53.7% over | about 52.4% | Pass |

**Recommendation: no bet on Game 1.** Both rosters changed a lot. Watch Game 1 and use it for **Game 2 (Wed 23 Sep, 1:05 AM ET)**.

### What changed since last season
- **Alvark:**
  - New coach Ryan Richman.
  - Their three top scorers are gone (Saiz 17.0, Foster 15.6, Davis 13.4).
  - New imports: D.J. Hogg (16.5 ppg at Chiba), Keyontae Johnson, and Lachlan Olbrich (ex-Bulls).
  - Rossiter (10.6 reb, 5.4 ast) and Toews (4.8 ast) stay.
- **Ryukyu:**
  - Head coach Hosaka.
  - Lost Vic Law, Kirk and Dotson.
  - Added David Nwaba (20.7 ppg at Niigata) and Kiefer Ravena.
  - **Grant Jerrett is out** (blood clot in his leg). Replacement Kevin Jones is 37 years old.
- **New rule:** up to 4 foreign players can be on court at once.

### Inputs (derived, labelled in the input file)
- **Points per game (2025-26, including playoffs):** Alvark 81.0, Ryukyu 81.5 (bleague-db).
- **Points allowed per game:** derived from defensive rating × estimated possessions. Alvark about 78.1, Ryukyu about 74.6. No source publishes these directly.
- **Regress:** 50%, because both rosters turned over.
- **Model:** Alvark 80.3 – Ryukyu 79.8. Total 160.1. Home win 51.7%.

### Fair lines (model, not market)
| | Spread | Total |
|---|---|---|
| Full game | Alvark about -0.5 | about 160 |
| 1st half | pick'em | about 78.5 |
| 1st quarter | pick'em | about 40 |

### Head to head, 2025-26: Ryukyu 3–0
- 83–68 (total 151)
- 82–76 (total 158)
- 77–76 in the EASL third-place game (total 153)

### Preseason
- **Alvark:**
  - Lost 80–100 to Yokohama Excellence (a second-division team)
  - Won 88–82 at Yokohama BC
  - Won 87–61 against Koshigaya
- **Ryukyu:**
  - Won 71–52 against Shibuya
  - Won 110–86 against Chiba
  - Lost 82–110 to Perth
  - Tied 60–60 with Ibaraki

### Rest
- **Ryukyu:** last played 15 Sep, then flew Okinawa to Tokyo.
- **Alvark:** last played 13 Sep.
- **Both** play again the next day (Game 2).

### Props
None found. No props are posted for this game on any page that could be read.

### Sharp money
**None exists.** The scores24 "Over 158.5" is a tipster pick.

---

## Sources
- [Wikipedia: 2026–27 NBL season](https://en.wikipedia.org/wiki/2026%E2%80%9327_NBL_season)
- [Wikipedia: 2025–26 NBL season](https://en.wikipedia.org/wiki/2025%E2%80%9326_NBL_season)
- [Bullets schedule](https://www.brisbanebullets.com.au/schedule/brisbane-bullets-v-new-zealand-breakers-men-22-09-2026)
- [NBL: Pat Rafter Arena opener](https://www.nbl.com.au/news/brisbane-bullets-to-open-season-in-historic-fashion)
- [NBL: Bullets injuries](https://www.nbl.com.au/news/injuries-sideline-bullets-duo-taine-murray-sam-mcdaniel)
- [NBL: Breakers beat Illawarra](https://www.nbl.com.au/news/new-breakers-era-begins-with-big-win)
- [Before You Bet: Bullets v Breakers](https://www.beforeyoubet.com.au/bullets-vs-breakers-prediction-tips-nbl27-round-1)
- [Oddspedia: Bullets v Breakers](https://oddspedia.com/us/basketball/nz-breakers-brisbane-bullets-278846)
- [Dailysports: Bullets v Breakers](https://dailysports.net/predictions/can-new-zealand-continue-their-strong-start-brisbane-bullets-vs-new-zealand-breakers-preview-september-22-2026/)
- [Freetips: Bullets v Breakers](https://www.freetips.com/basketball/brisbane-bullets-vs-new-zealand-breakers-tips-20260921-0027/)
- [basketball.com.au: preseason results](https://www.basketball.com.au/news/nbl27-pre-season-results-supercoach-scores-every-game)
- [RealGM: Bullets schedule](https://basketball.realgm.com/international/league/5/Australian-NBL/team/159/Brisbane-Bullets/schedule)
- [RealGM: Breakers per-48 stats](https://basketball.realgm.com/international/league/5/Australian-NBL/team/407/New-Zealand/stats/2026/Per_48/All/All/points/All/desc/1/Regular_Season)
- [The Underdog: NBL27 preview](https://theunderdog.news/nbl-27-preview-and-predictions/)
- [Wikipedia: 2025–26 Bullets season](https://en.wikipedia.org/wiki/2025%E2%80%9326_Brisbane_Bullets_season)
- [Wikipedia: 2025–26 Breakers season](https://en.wikipedia.org/wiki/2025%E2%80%9326_New_Zealand_Breakers_season)
- [Alvark: opener](https://www.alvark-tokyo.jp/news/detail/game/id=21217)
- [Golden Kings: opener](https://goldenkings.jp/news/detail/id=22744)
- [Goal JP: tip times and broadcast](https://www.goal.com/jp/%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9/alvark-tokyo-ryukyu-golden-kings-tv-broadcast-live-stream-b-league-2026-27/blt28fa942b2b0256f5)
- [Basket Count: 4-foreigner rule](https://basket-count.com/article/detail/274529)
- [scores24: Alvark v Ryukyu](https://scores24.live/en/basketball/m-22-09-2026-alvark-tokyo-ryukyu-golden-kings-okinawa-prediction)
- [bleague-db: Alvark](https://www.bleague-db.com/teams/706)
- [bleague-db: Ryukyu](https://www.bleague-db.com/teams/701)
- [bleague.jp: head-to-head](https://www.bleague.jp/record/?club1=706&club2=701)
- [basketballking: Jerrett injury](https://basketballking.jp/news/japan/20260918/633213.html)
- [basketballking: Alvark imports](https://basketballking.jp/news/japan/20260714/623880.html)
- [r-tabe: Ryukyu signings](https://r-tabe.com/2026/07/05/%E3%80%902026-27%E3%82%B7%E3%83%BC%E3%82%BA%E3%83%B3%E3%80%91%E7%90%89%E7%90%83%E3%82%B4%E3%83%BC%E3%83%AB%E3%83%87%E3%83%B3%E3%82%AD%E3%83%B3%E3%82%B0%E3%82%B9%E3%81%AE%E6%96%B0%E5%8A%A0%E5%85%A5/)
- [Wikipedia: 2025–26 B1 season](https://en.wikipedia.org/wiki/2025%E2%80%9326_B1_League_season)
