from features.fast_notifier import send_fast_mail
from features.predictions.snapshot import write_prediction_snapshot
from features.predictions.online_correction import (
    apply_online_correction,
    online_correction_status,
    record_online_forecasts,
    settle_online_forecasts,
)
from features.predictions.data_handler import (
    check_if_data_reload_needed,
    create_player_data_table,
    create_market_snapshot_table,
    save_market_snapshot,
    load_player_data_from_db,
    save_player_data_to_db,
    hydrate_missing_live_players,
)
from features.predictions.modeling import evaluate_model, train_model
from features.predictions.predictions import (
    hydrate_report_points_from_kickbase,
    join_current_market,
    join_current_squad,
    live_data_predictions,
)
from features.predictions.preprocessing import preprocess_player_data, split_data
from features.lineup_optimizer import write_lineup_optimizer
from kickbase_api.league import get_league_id, get_league_players_on_market
from kickbase_api.user import get_user_id, get_players_in_squad, login
from dotenv import load_dotenv
from IPython.display import display
import os
import pandas as pd


load_dotenv()

competition_ids = [1]
league_name = os.getenv("KICK_LEAGUE_NAME", "Die Spätzünder")
league_start_date = "2026-08-15"
last_mv_values = 365
last_pfm_values = 50
email = os.getenv("EMAIL_USER")
min_market_prediction = 50_000

features = [
    "p", "mv", "days_to_next",
    "mv_change_1d", "mv_trend_1d",
    "mv_change_3d", "mv_vol_3d",
    "mv_trend_7d", "market_divergence",
]

pd.options.display.float_format = lambda x: "{:,.0f}".format(x).replace(",", ".")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.width", 1000)


def generate_fast_report_data(source="Fast 1T"):
    """Reuse the fresh 1T pipeline without building the full mail layout."""
    token = login(os.getenv("KICK_USER"), os.getenv("KICK_PASS"))
    print("\nLogged in to Kickbase.")
    current_user_id = get_user_id(token)
    league_id = get_league_id(token, league_name)
    if os.getenv("REPORT_USER_ID") and str(current_user_id) != os.environ["REPORT_USER_ID"]:
        raise RuntimeError("Report-Konto passt nicht zum Dashboard.")
    league_id = os.getenv("REPORT_LEAGUE_ID") or league_id

    create_player_data_table()
    create_market_snapshot_table()
    reload_data = check_if_data_reload_needed()
    save_player_data_to_db(token, competition_ids, last_mv_values, last_pfm_values, reload_data)
    player_df = load_player_data_from_db()

    market_players = get_league_players_on_market(token, league_id, current_user_id)
    save_market_snapshot(league_id, market_players)
    live_player_ids = {item.get("id") for item in market_players}
    live_player_ids.update(item.get("i") for item in get_players_in_squad(token, league_id).get("it", []))
    player_df = hydrate_missing_live_players(
        token, competition_ids[0], player_df, live_player_ids, last_mv_values, last_pfm_values
    )
    settled = settle_online_forecasts(player_df)
    if settled:
        print(f"Online calibration settled {settled} previous forecasts.")
    print("\nData loaded from database.")

    proc_player_df, today_df = preprocess_player_data(player_df)
    print("\nData preprocessed.")
    x_train, x_test, y_train, y_test = split_data(proc_player_df, features, "mv_target_clipped")
    model = train_model(x_train, y_train)
    signs_percent, rmse, mae, r2 = evaluate_model(model, x_test, y_test)
    print(
        "\n1T model evaluation: "
        f"Signs correct: {signs_percent:.2f}% | RMSE: {rmse:.2f} | MAE: {mae:.2f} | R2: {r2:.2f}"
    )

    predictions_df = live_data_predictions(
        today_df, {"predicted_mv_target": model}, features, None, report_only=True
    )
    record_online_forecasts(predictions_df)
    predictions_df = apply_online_correction(predictions_df)
    print(f"Online calibration status: {online_correction_status()}")
    forecast_snapshot = write_prediction_snapshot(predictions_df, source, competition_ids[0])

    market_df = join_current_market(
        token, league_id, predictions_df, current_user_id, report_only=True, include_player_id=True
    )
    squad_df = join_current_squad(
        token, league_id, predictions_df, current_user_id, league_start_date,
        competition_ids[0], report_only=True, include_player_id=True,
    )
    market_df, squad_df = hydrate_report_points_from_kickbase(
        token, competition_ids[0], market_df, squad_df
    )
    # Keep the dashboard's player names, clubs, images and current market
    # in sync without running the slower full mail rendering.
    write_lineup_optimizer(
        token, league_id, current_user_id, squad_df, predictions_df,
        history_df=player_df, forecast_snapshot=forecast_snapshot, market_df=market_df,
    )
    return {
        "token": token,
        "league_id": league_id,
        "user_id": current_user_id,
        "market_df": market_df,
        "squad_df": squad_df,
        "predictions_df": predictions_df,
        "history_df": player_df,
        "forecast_snapshot": forecast_snapshot,
    }


def main():
    report = generate_fast_report_data()
    market_df, squad_df = report["market_df"], report["squad_df"]
    before_filter = len(market_df)
    market_df = market_df[market_df["predicted_mv_target"].fillna(0) > min_market_prediction].copy()
    print(
        "\nFast market filter: "
        f"{len(market_df)} of {before_filter} players kept with expected 1T change "
        f"> {min_market_prediction:,.0f} EUR.".replace(",", ".")
    )
    market_df = market_df.sort_values("predicted_mv_target", ascending=False, ignore_index=True)
    squad_df = squad_df.sort_values("predicted_mv_target", ascending=False, ignore_index=True)
    print("\n=== Fast Market 1T Predictions ===")
    display(market_df)
    print("\n=== Fast Squad 1T Predictions ===")
    display(squad_df)
    send_fast_mail(market_df, squad_df, email)


if __name__ == "__main__":
    main()
