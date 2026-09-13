if __name__ == "__main__":
    print("--- FBRef Shots on Target Prop Analysis ---")

    from soccer.fbref_shooting_scraper import (
        engineer_shot_prop_features,
        get_fallback_data,
        scrape_fbref_squad_shooting,
    )

    target_url = "https://fbref.com/en/squads/b8fd03ef/2023-2024/Manchester-City-Stats"

    raw_squad_df = scrape_fbref_squad_shooting(target_url)

    if raw_squad_df is None:
        raise SystemExit("Unable to obtain squad shooting data.")

    if raw_squad_df.equals(get_fallback_data()):
        print("NOTE: Using fallback/historical dataset for this run.\n")

    opp_style = "Low Block"
    opp_sot_allowed = 5.5

    final_projections = engineer_shot_prop_features(
        raw_squad_df,
        opponent_style=opp_style,
        opponent_sot_allowed_90=opp_sot_allowed,
    )

    output_cols = [
        'Player', 'Pos', '90s', 'Sh/90', 'SoT/90', 'Dist',
        'proj_total_shots', 'proj_sot', 'edge_rating',
    ]
    available_cols = [c for c in output_cols if c in final_projections.columns]
    print(final_projections[available_cols].head(10).to_string(index=False))

    print("\n* Edge Rating > 7.0: Elite value for 1+ SoT")
    print("* Note: 'Dist' = average shot distance in yards. Higher distance = lower SoT probability against low blocks.")