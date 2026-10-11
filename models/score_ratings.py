"""Opponent-adjusted score ratings fitted to sourced results, with time holdout."""
import math
from collections import Counter
import numpy as np


def _fit(games, cutoff):
    names = sorted({g[s + "_team"] for g in games for s in ("home", "away")})
    index = {n: i for i, n in enumerate(names)}
    n = len(names)
    rows, values, weights = [], [], []
    for g in games:
        age_season = int(cutoff[:4]) - int(g["date"][:4])
        weight = 0.5 if age_season > 0 else 1.0
        for side, other, sign in (("home", "away", 0.5), ("away", "home", -0.5)):
            x = np.zeros(2*n + 2)
            x[0] = 1
            x[1] = 0 if g.get("neutral_site") else sign
            x[2 + index[g[side + "_team"]]] = 1
            x[2 + n + index[g[other + "_team"]]] = 1
            rows.append(x)
            values.append(g[side + "_score"])
            weights.append(weight)
    x, y, w = np.array(rows), np.array(values), np.array(weights)
    penalty = np.eye(2*n+2) * 10.0
    penalty[0, 0] = 0
    penalty[1, 1] = 1
    beta = np.linalg.solve(x.T @ (x*w[:, None]) + penalty, x.T @ (y*w))
    return index, beta


def _project(fit, home, away, neutral=False):
    index, beta = fit
    if home not in index or away not in index:
        raise ValueError("Team has no eligible match history")
    n = len(index)
    hfa = 0 if neutral else beta[1]/2
    return (float(beta[0]+beta[2+index[home]]+beta[2+n+index[away]]+hfa),
            float(beta[0]+beta[2+index[away]]+beta[2+n+index[home]]-hfa))


class ScoreRatings:
    def __init__(self, games, cutoff, min_games=4):
        self.cutoff = cutoff
        self.games = sorted([g for g in games if g.get("completed") and g["date"] < cutoff
                             and g.get("home_score") is not None and g.get("away_score") is not None],
                            key=lambda g: (g["date"], g["game_id"]))
        if len(self.games) < 80:
            raise ValueError("Need at least 80 completed, pre-fixture games to fit and validate ratings")
        if any(not math.isfinite(float(g[s+"_score"])) or float(g[s+"_score"]) < 0
               for g in self.games for s in ("home", "away")):
            raise ValueError("Invalid score in history")
        self.counts = Counter(g[s+"_team"] for g in self.games for s in ("home", "away"))
        self.min_games = min_games
        split = max(50, int(len(self.games)*0.8))
        boundary = self.games[split]["date"]
        train = [g for g in self.games if g["date"] < boundary]
        test = [g for g in self.games if g["date"] >= boundary]
        if len(train) < 50:
            raise ValueError("Insufficient earlier dates for chronological validation")
        fit = _fit(train, boundary)
        margins, totals, correct = [], [], []
        for g in test:
            try:
                h, a = _project(fit, g["home_team"], g["away_team"], g.get("neutral_site", False))
            except ValueError:
                continue
            margins.append((g["home_score"]-g["away_score"])-(h-a))
            totals.append((g["home_score"]+g["away_score"])-(h+a))
            correct.append((h > a) == (g["home_score"] > g["away_score"]))
        if len(margins) < 20:
            raise ValueError("Insufficient chronological holdout games to estimate scoring uncertainty")
        self.margin_sd = float(np.std(margins, ddof=1))
        self.total_sd = float(np.std(totals, ddof=1))
        if self.margin_sd <= 0 or self.total_sd <= 0:
            raise ValueError("Degenerate residual distribution")
        self.validation = {"method": "chronological 80/20 holdout, whole dates separated",
                           "games": len(margins), "winner_accuracy": sum(correct)/len(correct),
                           "margin_rmse": float(np.sqrt(np.mean(np.square(margins)))),
                           "total_rmse": float(np.sqrt(np.mean(np.square(totals)))),
                           "note": "Historical holdout, not proof of a current betting edge"}
        self.fit = _fit(self.games, cutoff)

    def predict(self, home, away, neutral=False):
        if home == away:
            raise ValueError("A team cannot play itself")
        for name in (home, away):
            if self.counts[name] < self.min_games:
                raise ValueError(f"{name}: {self.counts[name]} eligible games; need {self.min_games}")
            latest = max(g["date"] for g in self.games if name in (g["home_team"], g["away_team"]))
            import datetime as dt
            if (dt.date.fromisoformat(self.cutoff)-dt.date.fromisoformat(latest)).days > 400:
                raise ValueError(f"{name}: history is stale ({latest})")
        h, a = _project(self.fit, home, away, neutral)
        return {"home_points": round(max(0, h), 2), "away_points": round(max(0, a), 2),
                "margin_sd": self.margin_sd, "total_sd": self.total_sd,
                "home_games": self.counts[home], "away_games": self.counts[away],
                "fitted_hfa": float(self.fit[1][1]), "validation": self.validation,
                "training_cutoff": self.cutoff,
                "note": "Opponent-adjusted ridge scoring model; prior calendar year receives 0.5 weight. Probabilities use normal residuals."}


def market_probability(mean, sd, line, spread=False):
    if not all(math.isfinite(float(v)) for v in (mean, sd, line)) or sd <= 0:
        raise ValueError("Line, mean and positive uncertainty must be finite")
    if abs(line*2-round(line*2)) > 1e-8:
        raise ValueError("Only whole/half market lines are supported")
    center = -line if spread else line
    cdf = lambda v: 0.5*(1+math.erf((v-mean)/(sd*math.sqrt(2))))
    if float(center).is_integer():
        lose = cdf(center-0.5)
        win = 1-cdf(center+0.5)
        push = 1-win-lose
    else:
        lose = cdf(center)
        win, push = 1-lose, 0.0
    return win, lose, push


def price_market(kind, line, probabilities, price_a=None, price_b=None):
    win, lose, push = probabilities
    evs = []
    for p, loss, odds in ((win, lose, price_a), (lose, win, price_b)):
        if odds is None:
            evs.append(None)
        else:
            odds = float(odds)
            if not math.isfinite(odds) or abs(odds) < 100:
                raise ValueError("American odds must be <= -100 or >= +100")
            evs.append(p*(odds/100 if odds > 0 else 100/-odds)-loss)
    pick = None
    if any(v is not None for v in evs):
        best = max(range(2), key=lambda i: evs[i] if evs[i] is not None else -math.inf)
        if evs[best] >= 0.05:
            pick = ("OVER" if best == 0 else "UNDER") if kind == "total" else ("HOME" if best == 0 else "AWAY")
    return {"kind": kind, "line": line, "prob_a": win, "prob_b": lose, "push_prob": push,
            "price_a": price_a, "price_b": price_b, "ev_a": evs[0], "ev_b": evs[1],
            "pick": pick, "recommendation": f"LEAN {pick}" if pick else "PASS — no priced model value",
            "note": "Uncalibrated model EV; LEAN threshold 5%, not an established betting record"}
