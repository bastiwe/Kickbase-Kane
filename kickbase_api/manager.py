from kickbase_api.config import BASE_URL, get_json_with_token

# All functions related to manager data

def get_managers(token, league_id):
    """Get a list of all managers in the league with their IDs and names."""

    url = f"{BASE_URL}/leagues/{league_id}/ranking"
    data = get_json_with_token(url, token)

    user_info = [(user["n"], user["i"]) for user in data["us"]]

    return user_info

def get_manager_info(token, league_id, manager_id):
    """Get detailed information about a specific manager in the league."""

    url = f"{BASE_URL}/leagues/{league_id}/managers/{manager_id}/dashboard"
    data = get_json_with_token(url, token)

    return data

def get_manager_performance(token, league_id, manager_id, manager_name):
    """Get performance data for a specific manager in the league."""

    url = f"{BASE_URL}/leagues/{league_id}/managers/{manager_id}/performance"
    data = get_json_with_token(url, token)
    
    seasons = data.get("it", [])
    if not seasons:
        print(f"Warning: No performance data found for {manager_name}")
        tp_value = 0
    else:
        def season_id(season):
            try:
                return int(season.get("sid", 0))
            except (TypeError, ValueError):
                return 0

        current_season = max(seasons, key=season_id)
        tp_value = current_season.get("tp", 0)
    

    return {
        "name": manager_name,
        "tp": tp_value
    }
