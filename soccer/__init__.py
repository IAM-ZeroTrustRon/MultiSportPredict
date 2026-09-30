"""Soccer module for MultiSportPredict"""

import sys
from pathlib import Path

# Add archive/legacy-modules to sys.path if MultiSportModel is not in path
try:
    from MultiSportModel import (
        SoccerHandicapper,
        estimate_team_goals,
        estimate_btts_prob,
        poisson_over_prob,
        process_soccer_goals,
        process_soccer_corners,
        process_soccer_btts,
    )
except ImportError:
    legacy_dir = str(Path(__file__).resolve().parent.parent / "archive" / "legacy-modules")
    if legacy_dir not in sys.path:
        sys.path.insert(0, legacy_dir)
    from MultiSportModel import (
        SoccerHandicapper,
        estimate_team_goals,
        estimate_btts_prob,
        poisson_over_prob,
        process_soccer_goals,
        process_soccer_corners,
        process_soccer_btts,
    )

__all__ = [
    "SoccerHandicapper",
    "estimate_team_goals",
    "estimate_btts_prob",
    "poisson_over_prob",
    "process_soccer_goals",
    "process_soccer_corners",
    "process_soccer_btts",
]
