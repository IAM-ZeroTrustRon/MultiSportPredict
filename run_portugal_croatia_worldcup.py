#!/usr/bin/env python
"""
2026 World Cup Analysis: Portugal vs Croatia
============================================
Uses real squad metrics for Portugal and Croatia.
"""
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from run_world_cup_2026_analysis import analyze_world_cup_match

if __name__ == "__main__":
    print("=" * 80)
    print("2026 WORLD CUP ANALYSIS — Portugal vs Croatia")
    print("=" * 80)
    
    result = analyze_world_cup_match("Portugal", "Croatia", league="World_Cup")
    
    if result:
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        
        # Save to JSON
        out_dir = Path("output/world_cup")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "portugal_vs_croatia.json"
        with open(out_path, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResults saved to: {out_path}")
    else:
        print("Error: Analysis failed to produce results")
        sys.exit(1)