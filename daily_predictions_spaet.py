from features.predictions.predictions import (
    enrich_market_decisions_with_context,
    live_data_predictions,
    join_current_market,
    join_current_squad,
)
from features.predictions.preprocessing import preprocess_player_data, split_data
from features.predictions.modeling import train_model, evaluate_model
from kickbase_api.league import get_league_id
from kickbase_api.user import get_user_id, login
from features.notifier import send_mail
from features.overpay_tool import write_overpay_tool
from features.predictions.data_handler import (
    create_player_data_table,
    check_if_data_reload_needed,
    save_player_data_to_db,
    load_player_data_from_db,
)
from features.budgets import calc_manager_budgets
from features.ligainsider_signals import enrich_reports_with_ligainsider_signals
from IPython.display import display
from dotenv import load_dotenv
import os, pandas as pd

# Load environment variables from .env file
load_dotenv() 

# ----------------- Notes & TODOs -----------------

# TODO Fix the UTC timezone problems in the github actions scheduling
# TODO Add prediction of 3, 7 days, to give more context
# TODO Based upon the overpay of the other users, calculate a max price to pay for a player
# TODO Add features like starting 11 probability, injuries, ...
# TODO Improve budget calculation, weird bug that for me the budgets is 513929 off, idk why, checked everything

# ----------------- SYSTEM PARAMETERS -----------------
# Should be left unchanged unless you know what you're doing

last_mv_values = 365    # in days, max 365
last_pfm_values = 50    # in matchdays, max idk

# which features to use for training and prediction
features = [
    "p", "mv", "days_to_next", 
    "mv_change_1d", "mv_trend_1d", 
    "mv_change_3d", "mv_vol_3d",
    "mv_trend_7d", "market_divergence"
]

# what columns to learn and predict on
prediction_targets = {
    "predicted_mv_target": "mv_target_clipped",
    "predicted_mv_target_7d": "mv_target_7d_clipped",
}

# Set dot as thousands separator for better readability
pd.options.display.float_format = lambda x: '{:,.0f}'.format(x).replace(',', '.')

# Show all columns when displaying dataframes
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.width", 1000)

# ----------------- USER SETTINGS -----------------
# Adjust these settings to your preferences

competition_ids = [1]                   # 1 = Bundesliga, 2 = 2. Bundesliga, 3 = La Liga
league_name = "Die Spätzünder"          # Name of your league, must be exact match, can be done via env or hardcoded
start_budget = 80_000_000               # Starting budget of your league, used to calculate current budgets of other managers
league_start_date = "2026-08-15"        # Start date of your league, used to filter activities, format: YYYY-MM-DD
email = os.getenv("EMAIL_USER")         # Email to send recommendations to, can be the same as EMAIL_USER 
# No Kane, no gain\u26BD\uFE0F
# Die Spätzünder
# ---------------------------------------------------

# Load environment variables and login to kickbase
USERNAME = os.getenv("KICK_USER") # DO NOT CHANGE THIS, YOU MUST SET THOSE IN GITHUB SECRETS OR A .env FILE
PASSWORD = os.getenv("KICK_PASS") # DO NOT CHANGE THIS, YOU MUST SET THOSE IN GITHUB SECRETS OR A .env FILE
token = login(USERNAME, PASSWORD)
print("\nLogged in to Kickbase.")
current_user_id = get_user_id(token)

# Get league ID
league_id = get_league_id(token, league_name)

# Data handling
create_player_data_table()
reload_data = check_if_data_reload_needed()
save_player_data_to_db(token, competition_ids, last_mv_values, last_pfm_values, reload_data)
player_df = load_player_data_from_db()
print("\nData loaded from database.")

# Calculate (estimated) budgets of all managers in the league
manager_budgets_df = calc_manager_budgets(token, league_id, league_start_date, start_budget)
print("\n=== Manager Budgets ===")
display(manager_budgets_df)

# Preprocess the data and split the data
proc_player_df, today_df = preprocess_player_data(player_df)
print("\nData preprocessed.")

# Train and evaluate the models
models = {}
print("\nModel evaluation:")
for prediction_column, target in prediction_targets.items():
    X_train, X_test, y_train, y_test = split_data(proc_player_df, features, target)
    model = train_model(X_train, y_train)
    models[prediction_column] = model
    signs_percent, rmse, mae, r2 = evaluate_model(model, X_test, y_test)
    print(
        f"{prediction_column}: "
        f"Signs correct: {signs_percent:.2f}% | RMSE: {rmse:.2f} | MAE: {mae:.2f} | R2: {r2:.2f}"
    )

# Make live data predictions
live_predictions_df = live_data_predictions(today_df, models, features, proc_player_df, league_start_date)

# Join with current available players on the market
market_recommendations_df = join_current_market(token, league_id, live_predictions_df, current_user_id)

# Join with current players on the team
squad_recommendations_df = join_current_squad(token, league_id, live_predictions_df, current_user_id, league_start_date)

market_recommendations_df, squad_recommendations_df = enrich_reports_with_ligainsider_signals(
    market_recommendations_df,
    squad_recommendations_df,
)
market_recommendations_df = enrich_market_decisions_with_context(
    market_recommendations_df,
    squad_recommendations_df,
    manager_budgets_df,
)

print("\n=== Market Recommendations ===")
display(market_recommendations_df)

print("\n=== Squad Recommendations ===")
display(squad_recommendations_df)

overpay_tool_path = write_overpay_tool(market_recommendations_df, manager_budgets_df)

# Send email with recommendations
send_mail(manager_budgets_df, market_recommendations_df, squad_recommendations_df, email, overpay_tool_path)
