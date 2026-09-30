"""Basketball module for MultiSportPredict"""

import sys
from pathlib import Path

# Add archive/legacy-modules to sys.path if MultiSportModel is not in path
try:
    from MultiSportModel import (
        GameContext,
        TeamMetrics,
        eu_build_full_game,
        project_basketball_q1,
        process_basketball_game,
    )
except ImportError:
    legacy_dir = str(Path(__file__).resolve().parent.parent / "archive" / "legacy-modules")
    if legacy_dir not in sys.path:
        sys.path.insert(0, legacy_dir)
    from MultiSportModel import (
        GameContext,
        TeamMetrics,
        eu_build_full_game,
        project_basketball_q1,
        process_basketball_game,
    )

__all__ = [
    "GameContext",
    "TeamMetrics",
    "eu_build_full_game",
    "project_basketball_q1",
    "process_basketball_game",
]
