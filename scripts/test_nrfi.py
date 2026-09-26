#!/usr/bin/env python
"""Quick smoke test for the NRFI CLI module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.nrfi_yrfi_cli import BatterSplit, NRFIResult, PitcherSplit, calc_nrfi_edge


def build_sample_result() -> NRFIResult:
    result = NRFIResult(home_team="NYY", away_team="BOS")
    result.home_pitcher = PitcherSplit("Gerrit Cole", "NYY", 3.20, 6.5, 14.2, 28.0, 1.2, 6.0)
    result.away_pitcher = PitcherSplit("Brayan Bello", "BOS", 4.50, 9.8, 9.5, 20.0, 1.4, 6.0)
    result.home_top3_batters = [
        BatterSplit("Aaron Judge", "NYY", 165, 18.2, 0.310, 24),
        BatterSplit("Juan Soto", "NYY", 155, 14.0, 0.280, 18),
        BatterSplit("Giancarlo Stanton", "NYY", 130, 16.5, 0.260, 28),
    ]
    result.away_top3_batters = [
        BatterSplit("Rafael Devers", "BOS", 145, 15.0, 0.270, 20),
        BatterSplit("Wilyer Abreu", "BOS", 112, 10.2, 0.190, 22),
        BatterSplit("Triston Casas", "BOS", 128, 12.8, 0.230, 25.5),
    ]
    result.park_hr_factor = 1.08
    result.market_nrfi_price = -115
    return calc_nrfi_edge(result)


def test_nrfi_sample_recommends_non_pass():
    result = build_sample_result()
    assert result.lean != "PASS", f"Expected a real NRFI/YRFI lean, got {result.lean!r}"
    assert result.model_prob > 0, "Expected a valid model probability"


def main() -> int:
    result = build_sample_result()
    print("=" * 60)
    print("NRFI / YRFI TEST: BOS @ NYY")
    print("=" * 60)
    print(f"  Lean:          {result.lean}")
    print(f"  Confidence:    {result.model_prob:.1f}%")
    print(f"  Market NRFI:   {result.market_nrfi_price:+,d}")
    print(f"  Park HR:       {result.park_hr_factor:.2f}")
    print()
    print("  Pitchers (1st-inning splits):")
    print(f"    BOS  xFIP={result.away_pitcher.xfip_1st:.2f}  BB%={result.away_pitcher.bb_pct_1st:.1f}  SwStr%={result.away_pitcher.swstr_pct:.1f}  K%={result.away_pitcher.k_pct:.1f}")
    print(f"    NYY  xFIP={result.home_pitcher.xfip_1st:.2f}  BB%={result.home_pitcher.bb_pct_1st:.1f}  SwStr%={result.home_pitcher.swstr_pct:.1f}  K%={result.home_pitcher.k_pct:.1f}")
    print()
    print("  Top-3 Batters wRC+:")
    print(f"    BOS: {[b.wrc_plus for b in result.away_top3_batters]}")
    print(f"    NYY: {[b.wrc_plus for b in result.home_top3_batters]}")
    print()
    print(f"  Summary: {result.summary}")
    print("=" * 60)

    try:
        from scripts.nrfi_yrfi_cli import print_result
        print_result(result)
    except Exception as exc:  # pragma: no cover - display is optional
        print(f"Rich display skipped: {exc}")

    return 0 if result.lean != "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())