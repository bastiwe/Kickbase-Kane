from features.fast_notifier import send_fast_mail
from features.predictions.data_handler import (
    check_if_data_reload_needed,
    create_player_data_table,
    load_player_data_from_db,
    save_player_data_to_db,
)
from features.predictions.modeling import evaluate_model, train_model
from features.predictions.predictions import live_data_predictions, join_current_market, join_current_squad
from features.predictions.preprocessing import preprocess_player_data, split_data
from kickbase_api.league import get_league_id
from kickbase_api.user import get_user_id, login
from dotenv import load_dotenv
from IPython.display import display
import os
import pandas as pd


load_dotenv()

competition_ids = [1]
league_name = "Die Spätzünder"
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

token = login(os.getenv("KICK_USER"), os.getenv("KICK_PASS"))
print("\nLogged in to Kickbase.")
current_user_id = get_user_id(token)
league_id = get_league_id(token, league_name)

create_player_data_table()
reload_data = check_if_data_reload_needed()
save_player_data_to_db(token, competition_ids, last_mv_values, last_pfm_values, reload_data)
player_df = load_player_data_from_db()
print("\nData loaded from database.")

proc_player_df, today_df = preprocess_player_data(player_df)
print("\nData preprocessed.")

X_train, X_test, y_train, y_test = split_data(proc_player_df, features, "mv_target_clipped")
model = train_model(X_train, y_train)
signs_percent, rmse, mae, r2 = evaluate_model(model, X_test, y_test)
print(
    "\n1T model evaluation: "
    f"Signs correct: {signs_percent:.2f}% | RMSE: {rmse:.2f} | MAE: {mae:.2f} | R2: {r2:.2f}"
)

live_predictions_df = live_data_predictions(
    today_df,
    {"predicted_mv_target": model},
    features,
    None,
)

market_df = join_current_market(token, league_id, live_predictions_df, current_user_id)
squad_df = join_current_squad(token, league_id, live_predictions_df, current_user_id)

market_count_before_filter = len(market_df)
market_df = market_df[market_df["predicted_mv_target"].fillna(0) > min_market_prediction].copy()
print(
    "\nFast market filter: "
    f"{len(market_df)} of {market_count_before_filter} players kept "
    f"with expected 1T change > {min_market_prediction:,.0f} EUR.".replace(",", ".")
)

market_df = market_df.sort_values("predicted_mv_target", ascending=False, ignore_index=True)
squad_df = squad_df.sort_values("predicted_mv_target", ascending=False, ignore_index=True)

print("\n=== Fast Market 1T Predictions ===")
display(market_df)

print("\n=== Fast Squad 1T Predictions ===")
display(squad_df)

send_fast_mail(market_df, squad_df, email)
