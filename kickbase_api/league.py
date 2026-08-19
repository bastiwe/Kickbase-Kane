from kickbase_api.config import BASE_URL, get_json_with_token

# All functions related to league data

def get_league_id(token, league_name):
    """Get the league ID based on the league name."""

    league_infos = get_leagues_infos(token)

    if not league_infos:
        print("Warning: You are not part of any league.")
        return None

    # Try to find leagues matching the given name
    selected_league = [league for league in league_infos if league["name"] == league_name]

    # If no exact match found, fall back to the first available league
    if not selected_league:
        fallback_league = league_infos[0]
        print(
            f"Warning: No league found with name '{league_name}'. "
            f"Falling back to the first available league: '{fallback_league['name']}'"
        )
        return fallback_league["id"]

    return selected_league[0]["id"]

def get_leagues_infos(token):
    """Get information about all leagues the user is part of."""

    url = f"{BASE_URL}/leagues/selection"
    data = get_json_with_token(url, token)

    result = []

    for item in data.get("it", []):
        result.append({
            "id": item.get("i"),
            "name": item.get("n")
        })

    return result

def get_league_activities(token, league_id, league_start_date):
    """Get league activities such as trades, logins, and achievements since the league start date."""

    # TODO magic number with 5000, have to find a better solution
    url = f"{BASE_URL}/leagues/{league_id}/activitiesFeed?max=5000"
    data = get_json_with_token(url, token)

    # Filter out entries prior to reset_Date
    filtered_activities = []
    for entry in data["af"]:
        entry_date = entry.get("dt", "")
        if entry_date >= league_start_date:
            filtered_activities.append(entry)

    login = [entry for entry in filtered_activities if entry.get("t") == 22]
    achievements = [entry for entry in filtered_activities if entry.get("t") == 26]
    trade = [entry for entry in filtered_activities if entry.get("t") == 15]
    trading = []
    missing_trade_fields_logged = False
    for entry in trade:
        data = entry.get("data", {})
        item = {
            "byr": first_existing(data, "byr", "buyer", "buyerName", "buyer_name", "bu"),
            "slr": first_existing(data, "slr", "seller", "sellerName", "seller_name", "su"),
            "pi": first_existing(data, "pi", "player", "p", "playerId", "player_id", "pId", "id", prefer_id=True),
            "pn": first_existing(data, "pn", "playerName", "player_name", "name", "n"),
            "tid": first_existing(data, "tid", "team", "teamId", "team_id", prefer_id=True),
            "trp": first_existing(data, "trp", "prc", "price", "amount", "bid", "value", prefer_value=True),
            "mv": first_existing(data, "mv", "marketValue", "market_value", prefer_value=True),
            "mvo": first_existing(data, "mvo", "marketValueOld", "market_value_old", prefer_value=True),
            "prc": first_existing(data, "prc", "price", "amount", "bid", "value", prefer_value=True),
        }
        item["dt"] = entry.get("dt")
        if not missing_trade_fields_logged and not any(item.get(key) is not None for key in ["byr", "pi", "trp", "prc"]):
            print(f"Warning: Could not parse transfer activity fields. Available keys: {sorted(data.keys())}")
            missing_trade_fields_logged = True
        trading.append(item)

    return trading, login, achievements

def first_existing(data, *keys, prefer_id=False, prefer_value=False):
    """Return the first non-empty value from possible Kickbase activity fields."""

    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            if prefer_id:
                nested_keys = ("i", "id", "pi", "playerId", "tid", "teamId", "v", "value", "n", "name")
            elif prefer_value:
                nested_keys = ("v", "value", "amount", "price", "trp", "mv", "mvo", "id", "i")
            else:
                nested_keys = ("n", "name", "u", "id", "i", "v", "value")
            nested_value = next((value.get(nested_key) for nested_key in nested_keys if value.get(nested_key) is not None), None)
            if nested_value is not None:
                return nested_value
        elif value != "":
            return value
    return None

def get_league_players_on_market(token, league_id, current_user_id=None):
    """Get all players currently available on the market in the league."""

    url = f"{BASE_URL}/leagues/{league_id}/market"
    data = get_json_with_token(url, token)

    result = []

    for player in data.get('it', []):
        result.append({
            'id': player.get('i'),
            'prob': player.get('prob'),
            "exp": player.get("exs"),
            "has_open_bid": has_user_market_offer(player, current_user_id),
            "is_own_listing": is_user_market_listing(player, current_user_id),
        })

    return result

def has_user_market_offer(item, current_user_id=None):
    """Best-effort detection for bids placed by the logged-in user."""

    explicit_fields = ("hasBid", "has_bid", "bidPlaced", "ownBid", "ownOffer", "uob", "hb")
    for field in explicit_fields:
        if field in item and bool(item.get(field)):
            return True

    if current_user_id is None:
        return False

    current_user_id = str(current_user_id)
    offer_keys = ("of", "ofs", "offers", "bids")
    for key in offer_keys:
        offers = item.get(key)
        if isinstance(offers, dict):
            offers = offers.values()
        if not isinstance(offers, list):
            continue
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            offer_user = offer.get("ui") or offer.get("u") or offer.get("userId") or offer.get("user_id")
            if offer_user is not None and str(offer_user) == current_user_id:
                return True
    return False

def is_user_market_listing(item, current_user_id=None):
    """Best-effort detection for players listed for sale by the logged-in user."""

    explicit_fields = ("isOwn", "is_own", "own", "mine", "isMine", "selling")
    for field in explicit_fields:
        if field in item and bool(item.get(field)):
            return True

    if current_user_id is None:
        return False

    current_user_id = str(current_user_id)
    seller_fields = ("ui", "u", "sellerId", "seller_id", "ownerId", "owner_id", "usr")
    for field in seller_fields:
        if item.get(field) is not None and str(item.get(field)) == current_user_id:
            return True

    seller = item.get("seller") or item.get("owner")
    if isinstance(seller, dict):
        seller_id = seller.get("i") or seller.get("id") or seller.get("ui")
        return seller_id is not None and str(seller_id) == current_user_id
    return False

def get_league_ranking(token, league_id):
    """Get the overall league ranking."""
    
    url = f"{BASE_URL}/leagues/{league_id}/ranking"
    data = get_json_with_token(url, token)

    players = [(user["n"], user["sp"]) for user in data["us"]]

    # Sort by score (descending)
    ranked = sorted(players, key=lambda x: x[1], reverse=True)

    return ranked
