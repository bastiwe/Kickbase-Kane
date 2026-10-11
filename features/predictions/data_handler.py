from kickbase_api.player import (
    get_all_players,
    get_player_info,
    get_player_market_value,
    get_player_performance,
)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import concurrent.futures
import pandas as pd
import sqlite3

def create_player_data_table():
    """Create the player_data_1d table in the SQLite database if it doesn't exist"""

    conn = sqlite3.connect("player_data_total.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_data_1d (
        player_id INTEGER,
        team_id INTEGER,
        team_name TEXT,
        first_name TEXT,
        last_name TEXT,
        position TEXT,
        image_url TEXT,
        team_image_url TEXT,
        md DATE,
        date DATE,
        p REAL,
        mp INTEGER,
        ppm REAL,
        t1 INTEGER,
        t2 INTEGER,
        t1g INTEGER,
        t2g INTEGER,
        won INTEGER,
        k TEXT,
        mv REAL
    );
    """)

    conn.commit()

def check_if_data_reload_needed():
    """Check if data reload is needed based on the last entry with null market value"""

    now = datetime.now(ZoneInfo("Europe/Berlin"))
    today_date = now.date()

    # Get nearest entry to today where mv is null
    with sqlite3.connect("player_data_total.db") as conn:
        cursor = conn.cursor()

        # Get the most recent date where mv is NULL
        cursor.execute("SELECT date FROM player_data_1d WHERE mv IS NULL ORDER BY date DESC LIMIT 1;")
        last_null_entry = cursor.fetchone()

        # convert last_null_entry (timestamp) to date
        if last_null_entry is not None:
            last_null_entry = datetime.fromisoformat(last_null_entry[0]).date()

        # Get the most recent date where mv is NOT NULL and at least 100 rows have this date
        # Hardcoded 100, bc if a player transfers on day x, he immediately has a mv value on day x and we dont want that
        cursor.execute("""
            SELECT date
            FROM player_data_1d
            WHERE mv IS NOT NULL
            GROUP BY date
            HAVING COUNT(*) >= 100
            ORDER BY date DESC
            LIMIT 1;
        """)
        last_non_null_entry = cursor.fetchone()

        # convert last_non_null_entry (timestamp) to date
        if last_non_null_entry is not None:
            last_non_null_entry = datetime.fromisoformat(last_non_null_entry[0]).date()

        # If there are no entries with null mv or no entries with non-null mv, we need to reload
        if last_null_entry is None or last_non_null_entry is None:
            return True

        # Cutoff-Time: Kickbase market values usually update around 22:00.
        cutoff = now.replace(hour=22, minute=0, second=0, microsecond=0)

        # Before the market value update, yesterday should exist with a mv value or today with a null mv value.
        if now < cutoff and (last_non_null_entry == today_date - timedelta(days=1) or last_null_entry == today_date):
            return False

        # After the market value update, today should exist with a mv value.
        elif now >= cutoff and last_non_null_entry == today_date:
            return False
        
        # Any other case we need to reload
        else:
            print("\nData reload needed, this takes a few minutes...")
            return True


def save_player_data_to_db(token, competition_ids, last_mv_values, last_pfm_values, reload_data):
    """Fetch player data and save to SQLite database if reload_data is needed"""

    if reload_data:
        all_competitions_dfs = []

        for competition_id in competition_ids:
            players = get_all_players(token, competition_id)

            def process_player(player_id):
                player_info = get_player_info(token, competition_id, player_id)
                player_team_id = player_info["team_id"]
                player_df = pd.DataFrame([player_info])

                # Market Value
                mv_df = pd.DataFrame(get_player_market_value(token, competition_id, player_id, last_mv_values))
                if not mv_df.empty:
                    mv_df["date"] = pd.to_datetime(mv_df["date"])
                    mv_df = mv_df.sort_values("date")

                # Special case for players with 500k market value and no change, manually add them
                #if (mv_df["date"].max() < pd.Timestamp(datetime.now(ZoneInfo("Europe/Berlin")).date())) and mv_df["mv"].iloc[-1] == 500_000:
                #    print("Testing special case")
                #    last_row = mv_df.iloc[-1].copy()
                #    last_row["date"] = pd.Timestamp(datetime.now(ZoneInfo("Europe/Berlin")).date())
                #    mv_df = pd.concat([mv_df, pd.DataFrame([last_row])], ignore_index=True)

                # Performance
                p_df = pd.DataFrame(get_player_performance(token, competition_id, player_id, last_pfm_values, player_team_id))
                if not p_df.empty:
                    p_df["date"] = pd.to_datetime(p_df["date"])
                    p_df = p_df.sort_values("date")
                else:
                    p_df = pd.DataFrame({"date": pd.to_datetime([])})

                # Ensure date columns are in datetime64[us] format, see problem #6
                p_df["date"] = p_df["date"].astype("datetime64[us]")

                # Merge DataFrames
                merged_df = (
                    pd.merge_asof(mv_df, p_df, on="date", direction="backward")
                    if not mv_df.empty else pd.DataFrame()
                )

                # Get p_df values where p_df.date > max(mv_df.date) and append to merged_df
                if not p_df.empty and not mv_df.empty:
                    max_mv_date = mv_df["date"].max()
                    additional_p_df = p_df[p_df["date"] > max_mv_date]
                    merged_df = pd.concat([merged_df, additional_p_df], ignore_index=True) 

                if not merged_df.empty:
                    merged_df = player_df.merge(merged_df, how="cross")
                    merged_df["competition_id"] = competition_id

                return merged_df

            # Use ThreadPoolExecutor to parallelize player fetching
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                comp_dfs = list(executor.map(process_player, players))
            
            comp_final_df = pd.concat(
                [df.dropna(how="all", axis=1) for df in comp_dfs if df is not None and not df.empty],
                ignore_index=True
            )

            all_competitions_dfs.append(comp_final_df)

        # Combine all competitions
        final_df = pd.concat(all_competitions_dfs, ignore_index=True)

        # Convert k column to string
        final_df["k"] = final_df["k"].apply(
            lambda x: ",".join(map(str, x)) if isinstance(x, list) else (None if x is None else str(x))
        )

        # Save to SQLite
        with sqlite3.connect("player_data_total.db") as conn:
            final_df.to_sql("player_data_1d", conn, if_exists="replace", index=False)

def load_player_data_from_db():
    """Load player data from SQLite database into a dataframe"""
    
    conn = sqlite3.connect("player_data_total.db")
    df = pd.read_sql("SELECT * FROM player_data_1d", conn)
    conn.close()

    return df


def hydrate_missing_live_players(token, competition_id, player_df, player_ids,
                                 last_mv_values=365, last_pfm_values=50):
    """Add current market/squad players absent from the local history cache.

    A player can join the Bundesliga or become relevant on the market after a
    previous full cache refresh. Without this small live repair, that player is
    invisible to the model despite Kickbase already having market history.
    """
    if player_df is None:
        player_df = pd.DataFrame()

    known_ids = set()
    latest_market_dates = {}
    if not player_df.empty and "player_id" in player_df:
        known_ids = {
            str(int(value))
            for value in pd.to_numeric(player_df["player_id"], errors="coerce").dropna()
        }
        if {"date", "mv"}.issubset(player_df.columns):
            usable = player_df.dropna(subset=["mv"]).copy()
            usable["date"] = pd.to_datetime(usable["date"], errors="coerce")
            latest_market_dates = {
                str(int(player_id)): stamp.date()
                for player_id, stamp in usable.groupby("player_id")["date"].max().items()
                if pd.notna(player_id) and pd.notna(stamp)
            }

    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    cutoff = datetime.now(ZoneInfo("Europe/Berlin")).replace(hour=22, minute=0, second=0, microsecond=0)
    expected_market_date = today if datetime.now(ZoneInfo("Europe/Berlin")) >= cutoff else today - timedelta(days=1)
    requested_ids = {str(player_id) for player_id in player_ids if player_id is not None}
    missing_ids = sorted(
        player_id for player_id in requested_ids
        if player_id not in known_ids or latest_market_dates.get(player_id, today) < expected_market_date
    )
    if not missing_ids:
        return player_df

    def fetch(player_id):
        info = get_player_info(token, competition_id, player_id)
        mv_df = pd.DataFrame(get_player_market_value(token, competition_id, player_id, last_mv_values))
        if mv_df.empty:
            return pd.DataFrame()
        mv_df["date"] = pd.to_datetime(mv_df["date"])
        mv_df = mv_df.sort_values("date")

        performance = get_player_performance(
            token, competition_id, player_id, last_pfm_values, info.get("team_id")
        )
        p_df = pd.DataFrame(performance)
        if p_df.empty:
            p_df = pd.DataFrame({"date": pd.to_datetime([])})
        else:
            p_df["date"] = pd.to_datetime(p_df["date"])
            p_df = p_df.sort_values("date")

        merged = pd.merge_asof(mv_df, p_df, on="date", direction="backward")
        if not p_df.empty:
            additional = p_df[p_df["date"] > mv_df["date"].max()]
            merged = pd.concat([merged, additional], ignore_index=True)
        if merged.empty:
            return merged
        result = pd.DataFrame([info]).merge(merged, how="cross")
        result["competition_id"] = competition_id
        return result

    rows = []
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(missing_ids))) as executor:
        futures = {executor.submit(fetch, player_id): player_id for player_id in missing_ids}
        for future in concurrent.futures.as_completed(futures):
            player_id = futures[future]
            try:
                frame = future.result()
            except Exception as exc:
                failures += 1
                print(f"Warning: Could not hydrate live player {player_id}: {exc}")
                continue
            if frame is not None and not frame.empty:
                rows.append(frame)

    if not rows:
        print(f"Live player hydration found no usable rows for {len(missing_ids)} players.")
        return player_df

    hydrated = pd.concat(rows, ignore_index=True)
    for column in ("date", "md"):
        if column in hydrated:
            hydrated[column] = pd.to_datetime(hydrated[column], errors="coerce")
    result = pd.concat([player_df, hydrated], ignore_index=True, sort=False)
    for column in ("date", "md"):
        if column in result:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    print(
        f"Live player hydration: {len(rows)}/{len(missing_ids)} missing players added"
        + (f", {failures} failed." if failures else ".")
    )
    return result
