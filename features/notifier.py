from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape
from numbers import Number
from zoneinfo import ZoneInfo
import json
import smtplib
import os

COLUMN_LABELS = {
    "recommendation": "Action",
    "buy_type": "Kaufart",
    "buy_priority": "Priorität",
    "team_limit_warning": "Limit",
    "player_display": "Spieler",
    "last_name": "Spieler",
    "position": "Pos",
    "team_name": "Team",
    "mv": "Marktwert",
    "max_bid": "Max. Gebot",
    "mv_change_yesterday": "Letzte MW",
    "predicted_mv_target": "Erw. 1T",
    "expected_change_pct": "Erw. %",
    "top_player_tag": "Klasse",
    "last_season_points": "Pkt. Vors.",
    "last_season_avg_points": "Ø Pkt.",
    "mv_trend": "MW-Tendenz",
    "starter_rate": "LI %",
    "hours_to_exp": "Resth.",
    "expires_at": "Ablauf",
    "risk": "Risiko",
    "User": "Manager",
    "Budget": "Cash",
    "Avg Overpay": "Ø Overpay",
    "Team Value": "Kaderwert",
    "Max Negative": "Minuslimit",
    "Available Budget": "Kaufkraft",
}

DISPLAY_LABELS = {
    "Strong buy": "Top-Kauf",
    "Buy": "Kaufen",
    "Watch": "Beobachten",
    "Keep": "Behalten",
    "Hold": "Halten",
    "Consider sell": "Verkauf prüfen",
    "Sell": "Verkaufen",
    "Normal": "Normal",
    "Before MV update": "Vor MW-Update",
    "Night expiry": "Nacht-Ablauf",
    "LI-Startelf": "LI-Startelf",
    "LI-Kader": "LI-Kader",
    "LI-Bundesliga": "LI-Bundesliga",
    "Startelf": "Startelf",
    "Startelfquote": "Startelfquote",
    "Kader": "Kader",
    "Nicht gefunden": "Nicht gefunden",
    "Kein Treffer": "Kein Treffer",
    "LI-Fehler": "LI-Fehler",
    "Keine LI-Daten": "Keine LI-Daten",
    "Deaktiviert": "Deaktiviert",
    "trend_up": "steigend",
    "trend_flat": "gleich",
    "trend_down": "sinkend",
    "Elite-Spieler": "Elite",
    "Top-Spieler": "Top",
    "Kader-Kauf": "Kader-Kauf",
    "Trading-Kauf": "Trading-Kauf",
    "Hoch": "Hoch",
    "Mittel": "Mittel",
    "Niedrig": "Niedrig",
    "Vereinslimit voll": "Limit voll",
    "füllt 3/3": "füllt 3/3",
}

BADGE_STYLES = {
    "Strong buy": ("#dcfce7", "#166534"),
    "Buy": ("#e0f2fe", "#075985"),
    "Watch": ("#f3f4f6", "#374151"),
    "Keep": ("#dcfce7", "#166534"),
    "Hold": ("#f3f4f6", "#374151"),
    "Consider sell": ("#fef3c7", "#92400e"),
    "Sell": ("#fee2e2", "#991b1b"),
    "Normal": ("#f3f4f6", "#374151"),
    "Before MV update": ("#ffedd5", "#9a3412"),
    "Night expiry": ("#fee2e2", "#991b1b"),
    "LI-Startelf": ("#dcfce7", "#166534"),
    "LI-Kader": ("#fef3c7", "#92400e"),
    "LI-Bundesliga": ("#dcfce7", "#166534"),
    "Startelf": ("#dcfce7", "#166534"),
    "Startelfquote": ("#dcfce7", "#166534"),
    "Kader": ("#fef3c7", "#92400e"),
    "Nicht gefunden": ("#f3f4f6", "#374151"),
    "Kein Treffer": ("#f3f4f6", "#374151"),
    "LI-Fehler": ("#fee2e2", "#991b1b"),
    "Keine LI-Daten": ("#fef3c7", "#92400e"),
    "Deaktiviert": ("#f3f4f6", "#374151"),
    "trend_up": ("#dcfce7", "#166534"),
    "trend_flat": ("#f3f4f6", "#374151"),
    "trend_down": ("#fee2e2", "#991b1b"),
    "Elite-Spieler": ("#fef3c7", "#854d0e"),
    "Top-Spieler": ("#e0f2fe", "#075985"),
    "Kader-Kauf": ("#dcfce7", "#166534"),
    "Trading-Kauf": ("#eef2ff", "#3730a3"),
    "Hoch": ("#dcfce7", "#166534"),
    "Mittel": ("#fef3c7", "#92400e"),
    "Niedrig": ("#f3f4f6", "#374151"),
    "Vereinslimit voll": ("#fee2e2", "#991b1b"),
    "füllt 3/3": ("#ffedd5", "#9a3412"),
}

POSITION_LABELS = {
    1: "TW",
    2: "ABW",
    3: "MIT",
    4: "ST",
    "1": "TW",
    "2": "ABW",
    "3": "MIT",
    "4": "ST",
}

FORMATIONS = [
    ("4-4-2", {1: 1, 2: 4, 3: 4, 4: 2}),
    ("3-4-3", {1: 1, 2: 3, 3: 4, 4: 3}),
    ("5-3-2", {1: 1, 2: 5, 3: 3, 4: 2}),
    ("5-4-1", {1: 1, 2: 5, 3: 4, 4: 1}),
    ("3-6-1", {1: 1, 2: 3, 3: 6, 4: 1}),
    ("4-2-4", {1: 1, 2: 4, 3: 2, 4: 4}),
    ("4-3-3", {1: 1, 2: 4, 3: 3, 4: 3}),
    ("3-5-2", {1: 1, 2: 3, 3: 5, 4: 2}),
    ("4-5-1", {1: 1, 2: 4, 3: 5, 4: 1}),
    ("5-2-3", {1: 1, 2: 5, 3: 2, 4: 3}),
]

BACKTEST_SUMMARY_PATH = "model_backtest_summary.json"


def load_backtest_summary():
    if not os.path.exists(BACKTEST_SUMMARY_PATH):
        return None

    try:
        with open(BACKTEST_SUMMARY_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        print(f"\nWarning: Could not read model backtest summary: {error}")
        return None

def send_mail(budget_df, market_df, squad_df, email):
    """Sends an email with the provided DataFrames as HTML tables."""

    if not email:
        print("\nNo email provided, skipping email sending.")
        return

    EMAIL_ADDRESS = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASS")
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("\nEmail credentials are incomplete, skipping email sending.")
        return

    # If it's 22:00 or later, show tomorrow's date; else today
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    date_to_show = now + timedelta(days=1) if now.hour >= 22 else now
    today = date_to_show.strftime("%d-%m-%Y")

    # Metadata for the email
    msg = EmailMessage()
    msg["Subject"] = f"Kickbase: {today}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = email

    market_buy_count = int((market_df.get("recommendation") == "Strong buy").sum()) if "recommendation" in market_df else 0
    squad_sell_count = int(squad_df.get("recommendation", []).isin(["Sell", "Consider sell"]).sum()) if "recommendation" in squad_df else 0
    top_budget = budget_df.iloc[0]["User"] if not budget_df.empty and "User" in budget_df else "-"

    backtest_summary = load_backtest_summary()

    def format_number(value):
        if isinstance(value, bool):
            return "Ja" if value else "Nein"
        if isinstance(value, Number) and not isinstance(value, bool):
            if value != value:
                return "-"
            return f"{value:,.0f}".replace(",", ".")
        return value

    def format_percent(value):
        if isinstance(value, Number) and value == value:
            return f"{value:.2f}%"
        return "-"

    def badge(value):
        if value is None or str(value) == "":
            return ""
        label = escape(DISPLAY_LABELS.get(str(value), str(value)))
        background, color = BADGE_STYLES.get(str(value), ("#f3f4f6", "#374151"))
        return (
            f'<span style="display:inline-block;background:{background};color:{color};'
            'font-weight:700;border-radius:999px;padding:4px 9px;white-space:nowrap;">'
            f'{label}</span>'
        )

    def colored_number(value, formatted, positive_good=True):
        if not isinstance(value, Number) or value != value or value == 0:
            return formatted
        is_good = value > 0 if positive_good else value < 0
        color = "#166534" if is_good else "#991b1b"
        background = "#f0fdf4" if is_good else "#fef2f2"
        return (
            f'<span style="display:inline-block;background:{background};color:{color};'
            'font-weight:700;border-radius:6px;padding:3px 7px;white-space:nowrap;">'
            f'{formatted}</span>'
        )

    def budget_value(value, formatted):
        if not isinstance(value, Number) or value != value:
            return formatted
        if value >= 120_000_000:
            background, color = "#dcfce7", "#166534"
        elif value >= 100_000_000:
            background, color = "#fef3c7", "#92400e"
        else:
            background, color = "#fee2e2", "#991b1b"
        return (
            f'<span style="display:inline-block;background:{background};color:{color};'
            'font-weight:700;border-radius:6px;padding:3px 7px;white-space:nowrap;">'
            f'{formatted}</span>'
        )

    def hours_value(value):
        formatted = f"{value:.1f}" if isinstance(value, Number) and value == value else "-"
        if not isinstance(value, Number) or value != value:
            return formatted
        if value <= 3:
            background, color = "#fee2e2", "#991b1b"
        elif value <= 12:
            background, color = "#ffedd5", "#9a3412"
        else:
            return formatted
        return (
            f'<span style="display:inline-block;background:{background};color:{color};'
            'font-weight:700;border-radius:6px;padding:3px 7px;white-space:nowrap;">'
            f'{formatted}</span>'
        )

    def expiry_value(value):
        if value is None or value != value:
            return "-"
        try:
            expires_at = value.astimezone(ZoneInfo("Europe/Berlin"))
        except AttributeError:
            return escape(str(value))

        today_date = now.date()
        if expires_at.date() == today_date:
            day_label = "Heute"
        elif expires_at.date() == (today_date + timedelta(days=1)):
            day_label = "Morgen"
        else:
            day_label = expires_at.strftime("%d.%m.")
        return f"{day_label} {expires_at:%H:%M}"

    def starter_rate_value(value, starts=None, apps=None):
        formatted = format_percent(value) if isinstance(value, Number) and value == value else "-"
        if isinstance(starts, Number) and starts == starts and isinstance(apps, Number) and apps == apps:
            formatted = f"{formatted} ({format_number(starts)}/{format_number(apps)})"
        if not isinstance(value, Number) or value != value:
            return formatted
        if value >= 80:
            background, color = "#dcfce7", "#166534"
        elif value >= 50:
            background, color = "#fef3c7", "#92400e"
        else:
            background, color = "#fee2e2", "#991b1b"
        return (
            f'<span style="display:inline-block;background:{background};color:{color};'
            'font-weight:700;border-radius:6px;padding:3px 7px;white-space:nowrap;">'
            f'{formatted}</span>'
        )

    def trend_value(value):
        if not isinstance(value, Number) or value != value:
            return "-"
        if value > 25_000:
            symbol, label, key = "↑", "erwartet steigend", "trend_up"
        elif value < -25_000:
            symbol, label, key = "↓", "erwartet sinkend", "trend_down"
        else:
            symbol, label, key = "→", "nahezu stabil erwartet", "trend_flat"
        background, color = BADGE_STYLES[key]
        return (
            f'<span title="{label}" style="display:inline-block;background:{background};color:{color};'
            'font-weight:800;border-radius:999px;padding:3px 8px;white-space:nowrap;font-size:14px;line-height:1;">'
            f'{symbol}</span>'
        )

    def position_label(value):
        return POSITION_LABELS.get(value, POSITION_LABELS.get(str(value), "-"))

    def player_name(row):
        first_name = "" if row.get("first_name") != row.get("first_name") else str(row.get("first_name", ""))
        last_name = "" if row.get("last_name") != row.get("last_name") else str(row.get("last_name", ""))
        return f"{first_name} {last_name}".strip() or "-"

    def player_url(row):
        ligainsider_url = row.get("ligainsider_url")
        if ligainsider_url == ligainsider_url and ligainsider_url:
            return str(ligainsider_url)
        return ""

    def player_image(row, size=78):
        image_url = row.get("image_url")
        if image_url == image_url and image_url:
            return (
                f'<img src="{escape(str(image_url), quote=True)}" alt="{escape(player_name(row), quote=True)}" '
                f'width="{size}" height="{size}" '
                f'style="width:{size}px;height:{size}px;border-radius:10px;object-fit:cover;background:#e5e7eb;display:block;">'
            )
        return (
            f'<span style="display:block;width:{size}px;height:{size}px;border-radius:10px;'
            'background:#e5e7eb;"></span>'
        )

    def action_card(row, title, value, value_positive_good=True, accent="#991b1b"):
        name = escape(player_name(row))
        url = player_url(row)
        image = player_image(row)
        name_html = (
            f'<a href="{escape(url, quote=True)}" target="_blank" style="color:#111827;text-decoration:none;">{name}</a>'
            if url else name
        )
        meta = f'{position_label(row.get("position"))} · {escape(str(row.get("team_name", "-")))}'
        expires = expiry_value(row.get("expires_at")) if "expires_at" in row else ""
        expires_html = (
            f'<div style="font-size:12px;color:#6b7280;margin-top:5px;">Ablauf: <b>{expires}</b></div>'
            if expires and expires != "-" else ""
        )
        return (
            '<td style="vertical-align:top;padding:0 8px 10px 0;width:33.33%;">'
            f'<div style="border:1px solid #e5e7eb;border-left:5px solid {accent};border-radius:8px;'
            'background:#ffffff;padding:10px;min-height:118px;">'
            '<table role="presentation" style="border-collapse:collapse;width:100%;"><tr>'
            f'<td style="width:88px;vertical-align:top;">{image}</td>'
            '<td style="vertical-align:top;padding-left:10px;">'
            f'<div style="font-size:12px;color:#6b7280;font-weight:700;text-transform:uppercase;">{escape(title)}</div>'
            f'<div style="font-size:15px;font-weight:800;color:#111827;margin-top:3px;">{name_html}</div>'
            f'<div style="font-size:12px;color:#6b7280;margin-top:3px;">{meta}</div>'
            f'<div style="font-size:14px;margin-top:7px;">{colored_number(value, format_number(value), positive_good=value_positive_good)}</div>'
            f'{expires_html}'
            '</td></tr></table>'
            '</div></td>'
        )

    def card_row(cards):
        if not cards:
            return '<p style="font-size:13px;color:#6b7280;margin:6px 0 0 0;">Kein akuter Handlungsbedarf im aktuellen Report.</p>'
        return (
            '<table role="presentation" style="width:100%;border-collapse:collapse;table-layout:fixed;"><tr>'
            + "".join(cards)
            + "</tr></table>"
        )

    def build_action_overview():
        squad_cards = []
        if not squad_df.empty and "predicted_mv_target" in squad_df:
            loss_candidates = squad_df[squad_df["predicted_mv_target"] < -25_000].copy()
            loss_candidates = loss_candidates.sort_values("predicted_mv_target", ascending=True).head(3)
            for _, row in loss_candidates.iterrows():
                squad_cards.append(
                    action_card(
                        row,
                        "Drohender MW-Verlust",
                        row.get("predicted_mv_target"),
                        value_positive_good=True,
                        accent="#991b1b",
                    )
                )

        market_cards = []
        if not market_df.empty and "predicted_mv_target" in market_df:
            market_candidates = market_df.copy()
            if "expires_before_mv_update" in market_candidates:
                market_candidates = market_candidates[market_candidates["expires_before_mv_update"].fillna(False).astype(bool)]
            elif "risk" in market_candidates:
                market_candidates = market_candidates[market_candidates["risk"] == "Before MV update"]
            else:
                market_candidates = market_candidates.iloc[0:0]
            market_candidates = market_candidates.sort_values("predicted_mv_target", ascending=False).head(3)
            for _, row in market_candidates.iterrows():
                market_cards.append(
                    action_card(
                        row,
                        "Top-Chance vor MW-Update",
                        row.get("predicted_mv_target"),
                        value_positive_good=True,
                        accent="#166534",
                    )
                )

        return f"""
            <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin:8px 0 20px 0;">
                <h3 style="color:#1f2933;margin:0 0 12px 0;font-size:17px;">Heute handeln</h3>
                {build_model_quality_card()}
                <p style="font-size:13px;color:#374151;margin:0 0 8px 0;"><b>Dein Kader: drohender MW-Verlust um 22 Uhr</b></p>
                {card_row(squad_cards)}
                <p style="font-size:13px;color:#374151;margin:8px 0 8px 0;"><b>Markt: Top 3 erwartete MW-Steigerungen mit Ablauf vor der nächsten Neuberechnung</b></p>
                {card_row(market_cards)}
            </div>
        """

    def build_model_quality_card():
        if not backtest_summary:
            return ""

        generated_at = escape(str(backtest_summary.get("generated_at", "-")))
        direction = backtest_summary.get("direction_accuracy_pct")
        mae = backtest_summary.get("mae")
        hit_rate = backtest_summary.get("top_trade_hit_rate_pct")
        avg_profit = backtest_summary.get("top_trade_avg_profit")
        test_days = backtest_summary.get("test_days", "-")
        test_rows = backtest_summary.get("test_rows", "-")

        return (
            '<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:10px 12px;margin:0 0 12px 0;">'
            '<div style="font-size:12px;color:#6b7280;font-weight:700;text-transform:uppercase;margin-bottom:6px;">Modellgüte letzter Backtest</div>'
            '<span style="display:inline-block;background:#eef2ff;color:#3730a3;padding:6px 9px;border-radius:6px;margin:2px;font-size:13px;">'
            f'Richtung: <b>{format_percent(direction)}</b></span>'
            '<span style="display:inline-block;background:#f8fafc;color:#374151;padding:6px 9px;border-radius:6px;margin:2px;font-size:13px;">'
            f'Ø Fehler: <b>{format_number(mae)}</b></span>'
            '<span style="display:inline-block;background:#ecfdf5;color:#166534;padding:6px 9px;border-radius:6px;margin:2px;font-size:13px;">'
            f'Top-Trade Treffer: <b>{format_percent(hit_rate)}</b></span>'
            '<span style="display:inline-block;background:#f8fafc;color:#374151;padding:6px 9px;border-radius:6px;margin:2px;font-size:13px;">'
            f'Ø Top-Trade: <b>{format_number(avg_profit)}</b></span>'
            f'<div style="font-size:11px;color:#6b7280;margin-top:5px;">Test: {test_days} Tage, n={test_rows}, Stand {generated_at}</div>'
            '</div>'
        )

    def build_squad_change_summary():
        if squad_df.empty or "mv_change_yesterday" not in squad_df:
            return ""
        total_change = squad_df["mv_change_yesterday"].sum()
        player_count = len(squad_df)
        return (
            '<div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:12px 14px;margin:8px 0 12px 0;font-size:14px;color:#374151;">'
            f'<b>Kader-Gewinn/Verlust gegenüber Vortagesmarktwert:</b> '
            f'{colored_number(total_change, format_number(total_change))} '
            f'<span style="color:#6b7280;">über {player_count} Spieler</span>'
            '</div>'
        )

    def build_lineup_advice():
        if squad_df.empty or "position" not in squad_df:
            return ""

        counts = {pos: int((squad_df["position"].astype(str) == str(pos)).sum()) for pos in [1, 2, 3, 4]}
        possible = []
        missing_by_formation = []
        for name, required in FORMATIONS:
            missing = {pos: max(0, required[pos] - counts.get(pos, 0)) for pos in required}
            missing_total = sum(missing.values())
            if missing_total == 0:
                possible.append(name)
            missing_by_formation.append((name, missing_total, missing))

        best_options = sorted(missing_by_formation, key=lambda item: (item[1], item[0]))[:3]
        possible_text = ", ".join(possible) if possible else "noch keine"
        counts_text = " / ".join(f"{POSITION_LABELS[pos]} {counts.get(pos, 0)}" for pos in [1, 2, 3, 4])
        squad_size = len(squad_df)
        squad_slots_left = max(0, 16 - squad_size)
        if squad_size >= 16:
            squad_size_style = "background:#fee2e2;color:#991b1b;"
        elif squad_size >= 14:
            squad_size_style = "background:#fef3c7;color:#92400e;"
        else:
            squad_size_style = "background:#dcfce7;color:#166534;"

        team_limit_html = ""
        if "team_name" in squad_df:
            team_counts = squad_df["team_name"].dropna().astype(str).value_counts().sort_index()
            team_chips = []
            for team, amount in team_counts.items():
                if amount >= 3:
                    style = "background:#fee2e2;color:#991b1b;"
                elif amount == 2:
                    style = "background:#fef3c7;color:#92400e;"
                else:
                    style = "background:#f3f4f6;color:#374151;"
                team_chips.append(
                    f'<span style="display:inline-block;{style}font-weight:700;border-radius:999px;'
                    f'padding:4px 9px;margin:2px;white-space:nowrap;">{escape(team)} {amount}/3</span>'
                )
            team_limit_html = "".join(team_chips)

        needs = []
        for _, _, missing in best_options:
            for pos, amount in missing.items():
                needs.extend([pos] * amount)
        needed_positions = []
        for pos in [1, 2, 3, 4]:
            if pos in needs:
                needed_positions.append(pos)

        market_rows = []
        if not market_df.empty and "position" in market_df:
            candidates = market_df.copy()
            if "top_player_tag" not in candidates:
                candidates["top_player_tag"] = ""
            if needed_positions:
                position_match = candidates["position"].astype(str).isin([str(pos) for pos in needed_positions])
                top_player_match = candidates["top_player_tag"].astype(str).ne("")
                candidates = candidates[position_match | top_player_match]
            candidates["recommendation_rank"] = candidates["recommendation"].map({"Strong buy": 0, "Buy": 1}).fillna(2)
            candidates["top_player_rank"] = candidates["top_player_tag"].astype(str).eq("").map({True: 1, False: 0})
            candidates = candidates.sort_values(["top_player_rank", "recommendation_rank", "predicted_mv_target"], ascending=[True, True, False]).head(4)
            for _, row in candidates.iterrows():
                top_label = f' {badge(row.get("top_player_tag"))}' if row.get("top_player_tag") else ""
                market_rows.append(
                    f'<li><b>{escape(player_name(row))}</b> ({position_label(row.get("position"))}, {escape(str(row.get("team_name", "-")))}) '
                    f'- {badge(row.get("recommendation", "Buy"))}{top_label} '
                    f'erwartet {colored_number(row.get("predicted_mv_target"), format_number(row.get("predicted_mv_target")))}'
                    '</li>'
                )

        option_rows = []
        for name, missing_total, missing in best_options:
            if missing_total == 0:
                status = '<span style="color:#166534;font-weight:700;">vollständig möglich</span>'
            else:
                missing_text = ", ".join(f"{amount} {POSITION_LABELS[pos]}" for pos, amount in missing.items() if amount)
                status = f'<span style="color:#92400e;font-weight:700;">es fehlen {missing_text}</span>'
            option_rows.append(f"<li><b>{name}</b>: {status}</li>")

        market_html = (
            '<ul style="margin:8px 0 0 18px;padding:0;font-size:13px;color:#374151;">'
            + "".join(market_rows)
            + "</ul>"
            if market_rows else
            '<p style="font-size:13px;color:#6b7280;margin:8px 0 0 0;">Keine direkte Ergänzung unter den aktuellen Kaufempfehlungen.</p>'
        )

        return f"""
            <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin:0 0 24px 0;">
                <h3 style="color:#1f2933;margin:0 0 10px 0;font-size:16px;">Aufstellungsplaner</h3>
                <p style="font-size:13px;color:#4b5563;margin:0 0 8px 0;">
                    Kaderpositionen: <b>{counts_text}</b>. Mögliche Formationen mit aktuellem Kader: <b>{possible_text}</b>.
                </p>
                <p style="font-size:13px;color:#4b5563;margin:0 0 8px 0;">
                    Kadergröße:
                    <span style="display:inline-block;{squad_size_style}font-weight:700;border-radius:999px;padding:4px 9px;white-space:nowrap;">{squad_size}/16</span>
                    <span style="color:#6b7280;">({squad_slots_left} Plätze frei)</span>
                    <span style="margin-left:10px;">Max. 3 Spieler pro Verein:</span>
                    {team_limit_html}
                </p>
                <p style="font-size:13px;color:#374151;margin:0 0 6px 0;"><b>Nächstliegende Formationen:</b></p>
                <ul style="margin:0 0 10px 18px;padding:0;font-size:13px;color:#374151;">{''.join(option_rows)}</ul>
                <p style="font-size:13px;color:#374151;margin:0 0 4px 0;"><b>Sinnvolle Markt-Ergänzungen:</b></p>
                {market_html}
            </div>
        """

    def prepare_df(df):
        result = df.copy()
        if {"predicted_mv_target", "mv_change_yesterday"}.issubset(result.columns):
            insert_at = result.columns.get_loc("predicted_mv_target") + 1
            result.insert(insert_at, "mv_trend", result["predicted_mv_target"])

        if {"starter_rate", "recent_starts", "recent_apps"}.issubset(result.columns):
            result["starter_rate"] = result.apply(
                lambda row: starter_rate_value(
                    row.get("starter_rate"),
                    row.get("recent_starts"),
                    row.get("recent_apps"),
                ),
                axis=1,
            )
            result = result.drop(columns=["recent_starts", "recent_apps"], errors="ignore")

        if {"first_name", "last_name"}.issubset(result.columns):
            def player_display(row):
                first_name = "" if row.get("first_name") != row.get("first_name") else str(row.get("first_name", ""))
                last_name = "" if row.get("last_name") != row.get("last_name") else str(row.get("last_name", ""))
                name = escape(f"{first_name} {last_name}".strip() or "-")
                image_url = row.get("image_url")
                if image_url == image_url and image_url:
                    image = (
                        f'<img src="{escape(str(image_url), quote=True)}" alt="{name}" '
                        'width="42" height="42" '
                        'style="width:42px;height:42px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:10px;background:#e5e7eb;">'
                    )
                else:
                    image = (
                        '<span style="display:inline-block;width:42px;height:42px;border-radius:50%;'
                        'background:#e5e7eb;vertical-align:middle;margin-right:10px;"></span>'
                    )
                content = (
                    '<div style="display:flex;align-items:center;min-width:145px;">'
                    f'{image}<span style="font-weight:600;color:#1f2933;">{name}</span></div>'
                )
                ligainsider_url = row.get("ligainsider_url")
                if ligainsider_url == ligainsider_url and ligainsider_url:
                    return (
                        f'<a href="{escape(str(ligainsider_url), quote=True)}" '
                        'style="text-decoration:none;color:inherit;" target="_blank">'
                        f"{content}</a>"
                    )
                return content

            result.insert(1, "player_display", result.apply(player_display, axis=1))
            result = result.drop(columns=["first_name", "last_name", "image_url"], errors="ignore")

        result = result.drop(
            columns=[
                "lineup_scope",
                "li_status",
                "ligainsider_url",
                "predicted_mv_target_3d",
                "predicted_mv_target_7d",
                "expected_change_pct_3d",
                "expected_change_pct_7d",
            ],
            errors="ignore",
        )

        for col in result.columns:
            if col in {"recommendation", "risk", "top_player_tag", "buy_type", "buy_priority", "team_limit_warning"}:
                result[col] = result[col].map(badge)
            elif col == "mv_trend":
                result[col] = result[col].map(trend_value)
            elif col in {"expected_change_pct", "expected_change_pct_3d", "expected_change_pct_7d"}:
                result[col] = result[col].map(lambda value: colored_number(value, format_percent(value)))
            elif col == "starter_rate" and not result[col].astype(str).str.contains("<span", regex=False).any():
                result[col] = result[col].map(starter_rate_value)
            elif col in {"mv_change_yesterday", "predicted_mv_target", "predicted_mv_target_3d", "predicted_mv_target_7d"}:
                result[col] = result[col].map(lambda value: colored_number(value, format_number(value)))
            elif col == "Available Budget":
                result[col] = result[col].map(lambda value: budget_value(value, format_number(value)))
            elif col == "Avg Overpay":
                result[col] = result[col].map(lambda value: colored_number(value, format_number(value), positive_good=False))
            elif col in {"mv", "max_bid", "Budget", "Team Value", "Max Negative", "recent_starts", "recent_apps", "last_season_points", "last_season_avg_points"}:
                result[col] = result[col].map(format_number)
            elif col == "hours_to_exp":
                result[col] = result[col].map(hours_value)
            elif col == "expires_at":
                result[col] = result[col].map(expiry_value)
            elif col == "position":
                result[col] = result[col].map(position_label)

        return result.rename(columns=COLUMN_LABELS)

    def style_df(df):
        if df.empty:
            return '<p style="font-size:14px;color:#555;">Heute gibt es keine passenden Spieler.</p>'

        result = prepare_df(df)
        hidden_cols = {"has_open_bid", "is_listed_for_sale", "buy_priority_score", "position_needed"}
        visible_cols = [col for col in result.columns if col not in hidden_cols]
        header_html = "".join(
            '<th style="background:#2c3e50;color:white;padding:6px;text-align:left;'
            f'border-bottom:1px solid #ddd;white-space:nowrap;">{escape(str(col))}</th>'
            for col in visible_cols
        )
        rows = []
        for _, row in result.iterrows():
            if bool(row.get("has_open_bid", False)):
                row_style = "background:#ecfdf5;"
            elif bool(row.get("is_listed_for_sale", False)):
                row_style = "background:#fff7ed;"
            elif "Elite" in str(row.get("Klasse", "")):
                row_style = "background:#fffbeb;"
            else:
                row_style = "background:#fefefe;"
            cells = "".join(
                '<td style="padding:6px;border-bottom:1px solid #eee;vertical-align:middle;">'
                f'{"" if row.get(col) is None else row.get(col)}</td>'
                for col in visible_cols
            )
            rows.append(f'<tr style="{row_style}">{cells}</tr>')

        return (
            '<table style="width:100%;min-width:2050px;border-collapse:collapse;font-size:12px;'
            f'margin:16px 0 24px 0;table-layout:auto;"><thead><tr>{header_html}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )

    action_legend = f"""
        <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin:0 0 24px 0;">
            <h3 style="color:#1f2933;margin:0 0 10px 0;font-size:16px;">Action-Legende</h3>
            <p style="font-size:13px;color:#4b5563;margin:0 0 8px 0;">
                Die Action ergibt sich aus der vom Modell erwarteten Marktwertänderung für den nächsten Tag, absolut und relativ zum aktuellen Marktwert.
                Erw. 1T zeigt die geschätzte Änderung für den nächsten Marktwertsprung.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Markt:</b>
                {badge("Strong buy")} erwartete Änderung >= 200.000 oder >= 2,00%;
                {badge("Buy")} erwartete Änderung >= 75.000 oder >= 0,75%.
                Zusätzlich bleiben offene Gebote, Topspieler und Spieler mit hoher oder mittlerer Kaufpriorität sichtbar.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Kaufart & Priorität:</b>
                {badge("Kader-Kauf")} meint langfristige Kaderverstärkung, vor allem durch Vorsaisonklasse, hohe LI-Startelfquote oder passende Position.
                {badge("Trading-Kauf")} ist primär ein Marktwert-Trade.
                Die Priorität {badge("Hoch")} / {badge("Mittel")} / {badge("Niedrig")} kombiniert Vorsaisonklasse, LI %, mittelfristiges Marktwertsignal und deinen Positionsbedarf.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Klasse:</b>
                {badge("Elite-Spieler")} und {badge("Top-Spieler")} basieren auf deduplizierten Kickbase-Punkten der Vorsaison.
                Elite-Marktspieler werden gold hinterlegt, damit langfristige Kaderverstärker nicht zwischen Trading-Käufen untergehen.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Max. Gebot:</b>
                Trading-Käufe bleiben konservativ. Bei {badge("Kader-Kauf")} und besonders bei {badge("Elite-Spieler")}
                wird mehr vom 1T/3T/7T-Upside eingepreist, danach auf psychologisch sinnvolle Gebotsstufen aufgerundet
                und mit kleinem Overbid versehen, um runde Konkurrenzgebote zu schlagen.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Ø Overpay:</b>
                Durchschnitt aus gezahltem Transferpreis minus Marktwert zum Transferdatum für Käufe seit Saisonstart.
                Positive Werte bedeuten im Schnitt über Marktwert gekauft, negative Werte bedeuten unter Marktwert gekauft.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>MW-Tendenz:</b>
                <span style="display:inline-block;background:#dcfce7;color:#166534;font-weight:800;border-radius:999px;padding:3px 8px;">↑</span> erwarteter Marktwert steigt,
                <span style="display:inline-block;background:#f3f4f6;color:#374151;font-weight:800;border-radius:999px;padding:3px 8px;">→</span> nahezu stabil,
                <span style="display:inline-block;background:#fee2e2;color:#991b1b;font-weight:800;border-radius:999px;padding:3px 8px;">↓</span> erwarteter Marktwert sinkt.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Risiko:</b>
                {badge("Before MV update")} bedeutet, dass das Angebot vor der nächsten Marktwert-Neuberechnung um 22:00 Uhr abläuft.
                Dann kaufst du noch ohne den neuen Marktwert zu kennen.
                {badge("Night expiry")} bedeutet, dass das Angebot in der kommenden Nacht bis 09:00 Uhr ausläuft; solche Gebote solltest du am Vorabend erledigen.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>LI-Signal:</b>
                Bevorzugt aus der öffentlichen LigaInsider-Spielerseite im Bereich Einsatzquote abgeleitet.
                {badge("LI-Bundesliga")} bedeutet: LI % ist die historische Startelfquote nur im Bundesliga-Wettbewerb.
                Falls keine Spielerseite/Quote gefunden wird, bleibt {badge("LI-Startelf")} oder {badge("LI-Kader")} als Teamseiten-Fallback.
                Das ist eine Historienquote, keine offizielle Kickbase- oder LigaInsider-Prognose für den nächsten Spieltag.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Kaderlimits:</b>
                Maximal 16 Spieler insgesamt und maximal 3 Spieler pro Verein.
                {badge("füllt 3/3")} warnt, dass der Kauf deinen dritten Spieler dieses Vereins belegt.
                {badge("Vereinslimit voll")} bedeutet, dass der Verein in deinem Kader bereits bei 3/3 steht.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Zeilenfarben:</b>
                <span style="display:inline-block;background:#ecfdf5;color:#166534;font-weight:700;border-radius:6px;padding:3px 7px;">grün</span>
                bedeutet: Du hast aktuell ein Gebot auf den Marktspieler platziert.
                <span style="display:inline-block;background:#fff7ed;color:#92400e;font-weight:700;border-radius:6px;padding:3px 7px;">orange</span>
                bedeutet: Der Kaderspieler ist aktuell zum Transfer angeboten.
            </p>
            <p style="font-size:13px;color:#374151;margin:0;">
                <b>Eigener Kader:</b>
                {badge("Sell")} erwartete Änderung <= -200.000 oder <= -2,00%;
                {badge("Consider sell")} erwartete Änderung <= -75.000 oder <= -0,75%;
                {badge("Keep")} erwartete Änderung >= 100.000 oder >= 1,00%;
                {badge("Hold")} neutraler Bereich.
            </p>
        </div>
    """
    action_overview = build_action_overview()
    lineup_advice = build_lineup_advice()
    squad_change_summary = build_squad_change_summary()

    # Set email content
    msg.set_content("Sorry, results only via html visible.", subtype="plain")
    msg.add_alternative(f"""\
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 8px;">
        <div style="max-width: 2200px; width: 100%; margin: auto; background: #ffffff; padding: 14px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); overflow-x: auto; box-sizing: border-box;">
        
        <h2 style="color: #1f2933; text-align: center; margin-top: 0;">Kickbase Report für {today}</h2>

        {action_overview}
        
        <div style="display:block;margin:16px 0 24px 0;">
            <span style="display:inline-block;background:#edf7ed;color:#1f6f3d;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;"><b>{market_buy_count}</b> Top-Käufe</span>
            <span style="display:inline-block;background:#fff4e5;color:#8a4b00;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;"><b>{squad_sell_count}</b> Verkaufschecks</span>
            <span style="display:inline-block;background:#eef2ff;color:#263a8b;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;">Höchste Kaufkraft: <b>{top_budget}</b></span>
        </div>

        {lineup_advice}

        <h3 style="color: #2c3e50; margin-top: 30px;">Manager-Budgets</h3>
        <p style="font-size: 14px; color: #333;">Geschätztes Cash und Kaufkraft nach sichtbaren Transfers, Punkten sowie geschätzten Login- und Achievement-Boni.</p>
        {style_df(budget_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Aktuelle Markt-Empfehlungen</h3>
        <p style="font-size: 14px; color: #333;">Spieler mit Trading- oder Kaderwert. Das maximale Gebot ist je nach Kaufart konservativer oder aggressiver berechnet.</p>

        {style_df(market_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Dein Kader</h3>
        <p style="font-size: 14px; color: #333;">Dein Kader sortiert nach letzter Marktwertänderung, mit den stärksten Verlusten zuerst, inklusive Verkaufs- und Haltesignalen.</p>
        {squad_change_summary}

        {style_df(squad_df)}

        {action_legend}

        <p style="margin-top: 20px; font-size: 14px;">Viele Grüße<br><b>Dein KickAdvisor Bot</b></p>
        
        <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
        <p style="font-size: 11px; color: gray; text-align: center;">
            Diese E-Mail wurde generiert vom 
            <a href="https://github.com/LennardFe/Kickbase-Trading-Advisor" 
            style="color: #888; text-decoration: none; font-weight: bold;">
            Kickbase Trading Advisor
            </a>
        </p>
        </div>
    </body>
    </html>
    """, subtype="html")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        print("\nEmail authentication failed, skipping email sending. Check EMAIL_USER and EMAIL_PASS.")
        return
    except smtplib.SMTPException as e:
        print(f"\nEmail sending failed, skipping email sending: {e}")
        return

    print("\nEmail sent successfully!")
