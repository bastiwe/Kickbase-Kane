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
    
    # Look for season ID "34" (current season 2025/2026)
    tp_value = 0
    for season in data["it"]:
        if season["sid"] == "34":
            tp_value = season["tp"]
            break
    else:
        # Fallback to first season if sid "34" not found
        tp_value = data["it"][0]["tp"]
        print(f"Warning: Season ID '34' not found for {manager_name}, using first season")
    

    return {
        "name": manager_name,
        "tp": tp_value
    }