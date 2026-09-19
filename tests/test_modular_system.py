#!/usr/bin/env python
"""
Comprehensive Test Suite for Modular MultiSportPredict System
==============================================================
Tests the new modular architecture including:
- Base predictor abstract class
- Sport-specific predictors (Basketball, Soccer, Baseball)
- KBO integration and auto-detection
- CLI functionality
- Backward compatibility with existing modules
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_base_predictor():
    """Test the abstract base class and factory function."""
    print("\n" + "="*60)
    print("TEST 1: Base Predictor and Factory Function")
    print("="*60)
    
    try:
        from base_predictor import SportPredictorBase, get_predictor, quick_predict
        
        # Test factory function for each sport
        sports = ['basketball', 'soccer', 'baseball', 'mlb', 'kbo']
        for sport in sports:
            try:
                predictor = get_predictor(sport)
                print(f"[PASS] {sport}: {predictor}")
            except Exception as e:
                print(f"[FAIL] {sport}: FAILED - {e}")
                return False
        
        print("\n[PASS] Base predictor tests PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Base predictor tests FAILED: {e}")
        return False


def test_basketball_predictor():
    """Test the FIBA/European basketball predictor."""
    print("\n" + "="*60)
    print("TEST 2: Basketball Predictor (FIBA/European)")
    print("="*60)
    
    try:
        from models.basketball_predictor import BasketballPredictor, FIBATeamMetrics, FIBAContext
        
        # Test instantiation
        predictor = BasketballPredictor(league="EuroLeague")
        print(f"[PASS] Created BasketballPredictor for {predictor.league}")
        
        # Test prediction
        result = predictor.predict(
            features=None,
            model=None,
            home_team="Real Madrid",
            away_team="FC Barcelona",
            market_line=5.5,
            current_line=6.0,
            open_line=5.0,
        )
        
        # Validate result structure
        assert 'sport' in result, "Missing 'sport' field"
        assert result['sport'] == 'basketball', "Wrong sport"
        assert 'full_game' in result, "Missing 'full_game' field"
        assert 'projected_home_score' in result['full_game'], "Missing projected_home_score"
        
        print(f"[PASS] Prediction generated successfully")
        print(f"  Projected: {result['full_game']['projected_home_score']:.1f} - {result['full_game']['projected_away_score']:.1f}")
        print(f"  Total: {result['full_game']['projected_total']:.1f}")
        print(f"  Lean: {result['full_game']['lean']}")
        
        print("\n[PASS] Basketball predictor tests PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Basketball predictor tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_soccer_predictor():
    """Test the soccer predictor with xG-based predictions."""
    print("\n" + "="*60)
    print("TEST 3: Soccer Predictor (xG + Poisson)")
    print("="*60)
    
    try:
        from models.soccer_predictor import SoccerPredictor, get_league_config
        
        # Test league configurations
        leagues = ['Premier League', 'La Liga', 'Bundesliga', 'Serie A']
        for league in leagues:
            config = get_league_config(league)
            print(f"[PASS] {league}: avg_goals={config['avg_goals_per_game']}, home_adv={config['home_advantage']}")
        
        # Test prediction
        predictor = SoccerPredictor(league="Premier League")
        result = predictor.predict(
            features=None,
            model=None,
            home_team="Liverpool",
            away_team="Aston Villa",
            market_line=0.25,
            market_total=2.5,
        )
        
        # Validate result structure
        assert 'sport' in result, "Missing 'sport' field"
        assert result['sport'] == 'soccer', "Wrong sport"
        assert 'game' in result, "Missing 'game' field"
        assert 'projected_home_goals' in result['game'], "Missing projected_home_goals"
        
        print(f"\n[PASS] Prediction generated successfully")
        print(f"  Projected: {result['home_team']} {result['game']['projected_home_goals']:.2f} - {result['game']['projected_away_goals']:.2f} {result['away_team']}")
        print(f"  Home Win: {result['game']['home_win_prob']:.1%}, Draw: {result['game']['draw_prob']:.1%}, Away Win: {result['game']['away_win_prob']:.1%}")
        
        print("\n[PASS] Soccer predictor tests PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Soccer predictor tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_baseball_predictor():
    """Test the unified MLB/KBO baseball predictor."""
    print("\n" + "="*60)
    print("TEST 4: Baseball Predictor (MLB + KBO)")
    print("="*60)
    
    try:
        from models.baseball_predictor import BaseballPredictor, detect_league, get_league_config
        
        # Test league auto-detection
        test_cases = [
            ("Yankees", "MLB"),
            ("Red Sox", "MLB"),
            ("Doosan Bears", "KBO"),
            ("LG Twins", "KBO"),
            ("Unknown Team", "MLB"),  # Default to MLB
        ]
        
        print("Testing league auto-detection:")
        for team, expected in test_cases:
            detected = detect_league(team)
            status = "[PASS]" if detected == expected else "[FAIL]"
            print(f"  {status} '{team}' -> {detected} (expected: {expected})")
            if detected != expected:
                return False
        
        # Test league configurations
        for league in ['MLB', 'KBO']:
            config = get_league_config(league)
            print(f"\n[PASS] {league}: avg_runs={config['avg_runs_per_game']}, env_factor={config['run_environment_factor']}")
        
        # Test MLB prediction
        predictor = BaseballPredictor()
        mlb_data = predictor.load_data(league="MLB", home_team="Yankees", away_team="Red Sox")
        mlb_features = predictor.feature_engineering(mlb_data)
        mlb_result = predictor.predict(mlb_features, None, "Yankees", "Red Sox", "MLB")
        
        assert mlb_result['sport'] == 'baseball'
        assert mlb_result['league'] == 'MLB'
        print(f"\n[PASS] MLB prediction: {mlb_result['game']['projected_total_runs']:.2f} total runs")
        
        # Test KBO prediction
        kbo_data = predictor.load_data(league="KBO", home_team="Doosan Bears", away_team="LG Twins")
        kbo_features = predictor.feature_engineering(kbo_data)
        kbo_result = predictor.predict(kbo_features, None, "Doosan Bears", "LG Twins", "KBO")
        
        assert kbo_result['sport'] == 'baseball'
        assert kbo_result['league'] == 'KBO'
        print(f"[PASS] KBO prediction: {kbo_result['game']['projected_total_runs']:.2f} total runs")
        
        # Verify KBO has higher projected total (due to higher run environment)
        if kbo_result['game']['projected_total_runs'] > mlb_result['game']['projected_total_runs']:
            print("[PASS] KBO correctly shows higher run environment than MLB")
        
        print("\n[PASS] Baseball predictor tests PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Baseball predictor tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_integration():
    """Test the CLI integration."""
    print("\n" + "="*60)
    print("TEST 5: CLI Integration")
    print("="*60)
    
    try:
        # Test that predict_match.py can be imported and has the right functions
        from predict_match import run_basketball_game, run_soccer_game, run_baseball_game
        
        print("[PASS] CLI functions imported successfully")
        
        # Test basketball CLI (quick test)
        result = run_basketball_game("Real Madrid", "FC Barcelona", league="EuroLeague")
        if result and 'full_game' in result:
            print("[PASS] Basketball CLI test passed")
        else:
            print("[FAIL] Basketball CLI test failed")
            return False
        
        # Test soccer CLI (quick test)
        result = run_soccer_game("Liverpool", "Aston Villa", league="Premier League")
        if result and 'game' in result:
            print("[PASS] Soccer CLI test passed")
        else:
            print("[FAIL] Soccer CLI test failed")
            return False
        
        # Test baseball CLI (quick test)
        result = run_baseball_game("Yankees", "Red Sox", league="MLB")
        if result and 'moneyline_and_side' in result:
            print("[PASS] Baseball CLI test passed")
        else:
            print("[FAIL] Baseball CLI test failed")
            return False
        
        print("\n[PASS] CLI integration tests PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] CLI integration tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """Test backward compatibility with existing modules."""
    print("\n" + "="*60)
    print("TEST 6: Backward Compatibility")
    print("="*60)
    
    try:
        # Test that old modules still work
        from core import init_db, store_prediction, confidence_score, bet_recommendation
        print("[PASS] Core modules imported successfully")
        
        # Test database initialization
        init_db()
        print("[PASS] Database initialized")
        
        # Test confidence engine
        score = confidence_score(2.5, volatility=0.35)
        rec = bet_recommendation(score)
        print(f"[PASS] Confidence engine: edge=2.5 -> score={score}, rec={rec}")
        
        # Test that old sport-specific modules still exist
        from basketball.basketball_predict_game import run_basketball_game as old_basketball
        from soccer.soccer_predict_game import run_soccer_game as old_soccer
        print("[PASS] Old sport-specific modules still accessible")
        
        print("\n[PASS] Backward compatibility tests PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Backward compatibility tests FAILED: {e}")
        return False


def test_output_generation():
    """Test that output files are generated correctly."""
    print("\n" + "="*60)
    print("TEST 7: Output Generation")
    print("="*60)
    
    try:
        from models.basketball_predictor import BasketballPredictor
        from models.soccer_predictor import SoccerPredictor
        from models.baseball_predictor import BaseballPredictor
        
        # Generate test predictions and save to output
        output_dir = Path("output/test_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Basketball
        bball_predictor = BasketballPredictor()
        bball_result = bball_predictor.predict(
            features=None, model=None,
            home_team="Test Home", away_team="Test Away",
            market_line=5.5
        )
        with open(output_dir / "test_basketball.json", 'w') as f:
            json.dump(bball_result, f, indent=2, default=str)
        print("[PASS] Basketball output generated")
        
        # Soccer
        soccer_predictor = SoccerPredictor()
        soccer_result = soccer_predictor.predict(
            features=None, model=None,
            home_team="Test Home", away_team="Test Away",
            market_line=0.0, market_total=2.5
        )
        with open(output_dir / "test_soccer.json", 'w') as f:
            json.dump(soccer_result, f, indent=2, default=str)
        print("[PASS] Soccer output generated")
        
        # Baseball
        baseball_predictor = BaseballPredictor()
        baseball_data = baseball_predictor.load_data(league="MLB", home_team="Test Home", away_team="Test Away")
        baseball_features = baseball_predictor.feature_engineering(baseball_data)
        baseball_result = baseball_predictor.predict(baseball_features, None, "Test Home", "Test Away", "MLB")
        with open(output_dir / "test_baseball.json", 'w') as f:
            json.dump(baseball_result, f, indent=2, default=str)
        print("[PASS] Baseball output generated")
        
        print("\n[PASS] Output generation tests PASSED")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Output generation tests FAILED: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("MULTISPORT PREDICT - MODULAR SYSTEM TEST SUITE")
    print("="*60)
    
    tests = [
        test_base_predictor,
        test_basketball_predictor,
        test_soccer_predictor,
        test_baseball_predictor,
        test_cli_integration,
        test_backward_compatibility,
        test_output_generation,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test crashed: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n*** ALL TESTS PASSED! ***")
        return 0
    else:
        print(f"\n*** {total - passed} TEST(S) FAILED ***")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)