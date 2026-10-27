from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape
from numbers import Number
from zoneinfo import ZoneInfo
import json
import smtplib
import os
import pandas as pd
from features.predictions.predictions import REMOVED_REPORT_COLUMNS
from features.report_lineup import attachment_payload, best_budget_lineup, number

COLUMN_LABELS = {
    "recommendation": "Action",
    "buy_type": "Kaufart",
    "buy_priority": "Priorität",
    "prediction_confidence": "Vertrauen",
    "sell_advice": "Verkaufsampel",
    "team_limit_warning": "Limit",
    "opponent_pressure": "Gegnerdruck",
    "opponent_overpay_forecast": "Erw. Gegner-Overpay",
    "winning_bid": "Sieggebot",
    "bid_gap": "Gap",
    "opponent_overpay_details": "Overpay-Gegner",
    "player_display": "Spieler",
    "last_name": "Spieler",
    "position": "Pos",
    "team_name": "Team",
    "player_status": "Status",
    "mv": "Marktwert",
    "purchase_price": "Kaufpreis",
    "squad_profit_loss": "G/V",
    "max_bid": "Max. Gebot",
    "mv_change_yesterday": "Letzte MW",
    "predicted_mv_target": "Erw. 1T",
    "expected_change_pct": "Erw. %",
    "top_player_tag": "Klasse",
    "last_season_points": "Pkt. Vors.",
    "last_season_avg_points": "Ø Pkt.",
    "kickbase_average_points": "Ø Pkt. (KB)",
    "mv_trend": "MW-Tendenz",
    "starter_rate": "LI %",
    "hours_to_exp": "Resth.",
    "expires_at": "Ablauf",
    "risk": "Risiko",
    "User": "Manager",
    "Budget": "Cash / Schätzung",
    "Avg Overpay": "Ø Overpay",
    "Team Value": "Kaderwert",
    "Max Negative": "Minuslimit",
    "Available Budget": "Kaufkraft",
    "Cash Basis": "Cash-Basis",
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
    "LI-Spielerseite": "LI-Spielerseite",
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
    "Vor 22 Uhr verkaufen": "Vor 22 verkaufen",
    "Verkauf prüfen": "Verkauf prüfen",
    "Kaderkern/Halten": "Kaderkern",
    "Halten": "Halten",
    "Unklar": "Unklar",
    "Vereinslimit voll": "Limit voll",
    "füllt 3/3": "füllt 3/3",
    "Fit": "Fit",
    "Verletzt": "Verletzt",
    "Angeschlagen": "Angeschlagen",
    "Reha": "Reha",
    "Rotgesperrt": "Rot",
    "Gelb-Rot-Sperre": "Gelb-Rot",
    "Gelbsperre": "Gelbsperre",
    "Nicht im Kader": "Nicht im Kader",
    "Nicht in Liga": "Nicht in Liga",
    "Abwesend": "Abwesend",
    "Unbekannt": "Unbekannt",
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
    "LI-Spielerseite": ("#dcfce7", "#166534"),
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
    "Vor 22 Uhr verkaufen": ("#fee2e2", "#991b1b"),
    "Verkauf prüfen": ("#fef3c7", "#92400e"),
    "Kaderkern/Halten": ("#dcfce7", "#166534"),
    "Halten": ("#f3f4f6", "#374151"),
    "Unklar": ("#f3f4f6", "#374151"),
    "Vereinslimit voll": ("#fee2e2", "#991b1b"),
    "füllt 3/3": ("#ffedd5", "#9a3412"),
    "Fit": ("#dcfce7", "#166534"),
    "Verletzt": ("#fee2e2", "#991b1b"),
    "Angeschlagen": ("#fef3c7", "#92400e"),
    "Reha": ("#ffedd5", "#9a3412"),
    "Rotgesperrt": ("#fee2e2", "#991b1b"),
    "Gelb-Rot-Sperre": ("#fee2e2", "#991b1b"),
    "Gelbsperre": ("#ffedd5", "#9a3412"),
    "Nicht im Kader": ("#fee2e2", "#991b1b"),
    "Nicht in Liga": ("#fee2e2", "#991b1b"),
    "Abwesend": ("#fee2e2", "#991b1b"),
    "Unbekannt": ("#f3f4f6", "#374151"),
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

def send_mail(budget_df, market_df, squad_df, email, attachment_path=None):
    """Send the compact HTML report; optional optimizer paths supply analysis data only."""

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

    def numeric_sum(values):
        total = 0
        for value in values:
            if isinstance(value, Number) and not isinstance(value, bool) and value == value:
                total += value
        return total

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
        if value > 0:
            symbol, label, key = "↑", "Erw. 1T höher als Letzte MW", "trend_up"
        elif value < 0:
            symbol, label, key = "↓", "Erw. 1T niedriger als Letzte MW", "trend_down"
        else:
            symbol, label, key = "→", "Erw. 1T ähnlich wie Letzte MW", "trend_flat"
        background, color = BADGE_STYLES[key]
        return (
            f'<span title="{label}" style="display:inline-block;background:{background};color:{color};'
            'font-weight:800;border-radius:999px;padding:3px 8px;white-space:nowrap;font-size:14px;line-height:1;">'
            f'{symbol}</span>'
        )

    def position_label(value):
        canonical = canonical_position(value)
        return POSITION_LABELS.get(canonical, POSITION_LABELS.get(str(canonical), "-"))

    def canonical_position(value):
        if isinstance(value, Number) and value == value:
            return int(value)
        try:
            numeric = float(str(value).strip())
            if numeric == numeric:
                return int(numeric)
        except (TypeError, ValueError):
            return value
        return value

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
            '<td class="report-card" style="vertical-align:top;padding:0 8px 10px 0;width:33.33%;">'
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
            '<table class="report-cards" role="presentation" style="width:100%;border-collapse:collapse;table-layout:fixed;"><tr>'
            + "".join(cards)
            + "</tr></table>"
        )

    def top_pick_card(row, rank):
        accent = "#166534"
        title = f"#{rank} Marktwert-Pick"
        name = escape(player_name(row))
        url = player_url(row)
        image = player_image(row, size=96)
        name_html = (
            f'<a href="{escape(url, quote=True)}" target="_blank" style="color:#111827;text-decoration:none;">{name}</a>'
            if url else name
        )
        expires = expiry_value(row.get("expires_at")) if "expires_at" in row else "-"
        starter_rate = row.get("starter_rate")
        starter_text = format_percent(starter_rate) if isinstance(starter_rate, Number) and starter_rate == starter_rate else "-"
        limit_badge = badge(row.get("team_limit_warning"))
        status_badge = badge(row.get("player_status"))
        return (
            '<td class="report-card" style="vertical-align:top;padding:0 10px 12px 0;width:33.33%;">'
            f'<div style="border:1px solid #e5e7eb;border-top:5px solid {accent};border-radius:8px;'
            'background:#ffffff;padding:12px;min-height:196px;">'
            '<table role="presentation" style="border-collapse:collapse;width:100%;"><tr>'
            f'<td style="width:108px;vertical-align:top;">{image}</td>'
            '<td style="vertical-align:top;padding-left:12px;">'
            f'<div style="font-size:12px;color:#6b7280;font-weight:800;text-transform:uppercase;">{escape(title)}</div>'
            f'<div style="font-size:17px;font-weight:900;color:#111827;margin-top:4px;">{name_html}</div>'
            f'<div style="font-size:12px;color:#6b7280;margin-top:3px;">{position_label(row.get("position"))} · {escape(str(row.get("team_name", "-")))}</div>'
            f'<div style="margin-top:8px;">{status_badge} {limit_badge}</div>'
            '</td></tr></table>'
            '<div style="border-top:1px solid #eef2f7;margin-top:10px;padding-top:9px;">'
            '<table role="presentation" style="border-collapse:collapse;width:100%;font-size:12px;color:#374151;">'
            '<tr>'
            f'<td style="padding:3px 4px 3px 0;color:#6b7280;">Erw. 1T</td><td style="padding:3px 0;text-align:right;">{colored_number(row.get("predicted_mv_target"), format_number(row.get("predicted_mv_target")))}</td>'
            '</tr><tr>'
            f'<td style="padding:3px 4px 3px 0;color:#6b7280;">Marktwert</td><td style="padding:3px 0;text-align:right;">{format_number(row.get("mv"))}</td>'
            '</tr><tr>'
            f'<td style="padding:3px 4px 3px 0;color:#6b7280;">LI %</td><td style="padding:3px 0;text-align:right;">{starter_text}</td>'
            '</tr><tr>'
            f'<td style="padding:3px 4px 3px 0;color:#6b7280;">Ablauf</td><td style="padding:3px 0;text-align:right;">{expires}</td>'
            '</tr>'
            '</table>'
            '</div>'
            '</div></td>'
        )

    def top_market_candidates(frame, require_pre_update=False):
        """Keep headline market cards useful, not merely mathematically positive."""
        if frame.empty or "predicted_mv_target" not in frame:
            return frame.iloc[0:0].copy()

        candidates = frame.copy()
        candidates = candidates[
            pd.to_numeric(candidates["predicted_mv_target"], errors="coerce").fillna(0) >= 50_000
        ]
        if require_pre_update:
            if "expires_before_mv_update" in candidates:
                candidates = candidates[candidates["expires_before_mv_update"].fillna(False).astype(bool)]
            elif "risk" in candidates:
                candidates = candidates[candidates["risk"] == "Before MV update"]
            else:
                return candidates.iloc[0:0].copy()
        if "player_status" in candidates:
            candidates = candidates[~candidates["player_status"].isin([
                "Verletzt", "Reha", "Rotgesperrt", "Gelb-Rot-Sperre",
                "Gelbsperre", "Nicht im Kader", "Nicht in Liga", "Abwesend",
            ])]
        if "team_limit_warning" in candidates:
            candidates = candidates[candidates["team_limit_warning"] != "Vereinslimit voll"]
        return candidates

    def build_top_buy_picks():
        if market_df.empty or "predicted_mv_target" not in market_df:
            return ""

        candidates = top_market_candidates(market_df)
        candidates = candidates.sort_values("predicted_mv_target", ascending=False).head(3)
        if candidates.empty:
            return ""

        cards = [top_pick_card(row, rank) for rank, (_, row) in enumerate(candidates.iterrows(), start=1)]
        return f"""
            <p style="font-size:13px;color:#374151;margin:10px 0 8px 0;"><b>Top 3 Marktwert-Picks nach erwarteter 1T-Steigerung</b></p>
            {card_row(cards)}
        """

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
            market_candidates = top_market_candidates(market_df, require_pre_update=True)
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
                {build_top_buy_picks()}
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
        phase_key = backtest_summary.get("current_market_phase", "gesamt")
        phase_summary = backtest_summary.get("phases", {}).get(phase_key, backtest_summary)
        phase_label = {
            "saisonstart": "Saisonstart",
            "saisonbetrieb": "Saisonbetrieb",
            "gesamt": "Gesamt",
        }.get(str(phase_key), str(phase_key))
        direction = phase_summary.get("direction_accuracy_pct")
        mae = phase_summary.get("mae")
        hit_rate = phase_summary.get("top_trade_hit_rate_pct")
        avg_profit = phase_summary.get("top_trade_avg_profit")
        test_days = phase_summary.get("days", backtest_summary.get("test_days", "-"))
        test_rows = phase_summary.get("rows", backtest_summary.get("test_rows", "-"))

        return (
            '<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:10px 12px;margin:0 0 12px 0;">'
            '<div style="font-size:12px;color:#6b7280;font-weight:700;text-transform:uppercase;margin-bottom:6px;">Modellgüte letzter Backtest</div>'
            '<span style="display:inline-block;background:#ffedd5;color:#9a3412;padding:6px 9px;border-radius:6px;margin:2px;font-size:13px;">'
            f'Marktphase: <b>{escape(phase_label)}</b></span>'
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
        payload = attachment_payload(attachment_path)
        if payload is not None:
            pool, cash = payload["players"], payload.get("budget")
        else:
            pool = []
            for index, row in squad_df.iterrows():
                pool.append({
                    "id": str(row.get("player_id", index)), "name": player_name(row),
                    "owned": True, "position": canonical_position(row.get("position")),
                    "mv": number(row.get("mv")),
                    "season": number(row.get("kickbase_average_points")),
                    "l3": number(row.get("last_3_points")),
                    "li": number(row.get("starter_rate")),
                    "change": number(row.get("predicted_mv_target")), "fixtures": [],
                })
            own_name = budget_df.attrs.get("own_user")
            own = budget_df[budget_df["User"] == own_name] if own_name and "User" in budget_df else budget_df.iloc[:0]
            if own.empty and "Cash Basis" in budget_df:
                own = budget_df[budget_df["Cash Basis"].astype(str).str.startswith("API")]
            if own.empty and len(budget_df) == 1:
                own = budget_df
            cash = number(own.iloc[0].get("Budget")) if len(own) == 1 else None
        choice = best_budget_lineup(pool, cash)
        if choice is None:
            message = ("Keine vollständige Startelf mit Restbudget ≥ 0 € nach Bankverkäufen möglich."
                       if number(cash) is not None else
                       "Beste Elf nicht berechenbar: eigener Kontostand fehlt.")
            content = '<p style="font-size:13px;">' + message + '</p>'
        else:
            players_html = "".join(
                '<span style="display:inline-block;background:#fff;border:1px solid #e5e7eb;'
                'border-radius:6px;padding:5px 7px;margin:3px;font-size:12px;">'
                + position_label(p.get("position")) + ' <b>' + escape(str(p.get("name") or "Spieler"))
                + '</b></span>' for p in choice["players"]
            )
            sales = ", ".join(str(p.get("name") or "Spieler") for p in choice["sales"])
            content = (
                '<p style="font-size:14px;"><b>Beste Elf: ' + escape(choice["formation"]) + '</b>'
                ' · Dashboard-Bewertung: ' + format_number(choice["score"]) + '</p>'
                '<div>' + players_html + '</div>'
                '<p style="font-size:13px;"><b>Restbudget nach Bankverkäufen: '
                + format_number(choice["budget"]) + ' €</b></p>'
                '<p style="font-size:12px;color:#6b7280;">'
                + ('Eingeplante Verkäufe zum Marktwert: ' + escape(sales) + '.'
                   if sales else 'Keine Bankverkäufe erforderlich.') + '</p>'
            )
        return (
            '<div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;'
            'padding:14px 16px;margin:0 0 24px 0;">'
            '<h3 style="color:#1f2933;margin:0 0 10px 0;font-size:16px;">Kaderanalyse</h3>'
            '<p style="font-size:12px;color:#6b7280;">Bewertung wie im HA-Startelfplaner; '
            'Restbudget mindestens 0 €. Nicht aufgestellte Spieler werden als Verkäufe zum Marktwert eingeplant.</p>'
            + content + '</div>'
        )

    def prepare_df(df):
        result = df.drop(columns=REMOVED_REPORT_COLUMNS + ["top_player_tag", "player_id", "Cash Basis"], errors="ignore").copy()

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
                        'width="34" height="34" '
                        'style="width:34px;height:34px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:7px;background:#e5e7eb;">'
                    )
                else:
                    image = (
                        '<span style="display:inline-block;width:34px;height:34px;border-radius:50%;'
                        'background:#e5e7eb;vertical-align:middle;margin-right:7px;"></span>'
                    )
                content = (
                    '<div style="display:flex;align-items:center;min-width:118px;max-width:170px;">'
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
                "last_3_points",
                "current_season_points",
                # Historical averages support internal ranking only. The
                # visible report uses the live Kickbase average instead.
                "last_season_avg_points",
                "lineup_score",
                "lineup_score_basis",
            ],
            errors="ignore",
        )

        if "player_status" in result and "starter_rate" in result:
            columns = [col for col in result.columns if col != "starter_rate"]
            columns.insert(columns.index("player_status") + 1, "starter_rate")
            result = result[columns]

        for col in result.columns:
            if col in {"recommendation", "risk", "top_player_tag", "buy_type", "buy_priority", "prediction_confidence", "sell_advice", "team_limit_warning", "opponent_pressure", "player_status"}:
                result[col] = result[col].map(badge)
            elif col == "mv_trend":
                result[col] = result[col].map(trend_value)
            elif col in {"expected_change_pct", "expected_change_pct_3d", "expected_change_pct_7d"}:
                result[col] = result[col].map(lambda value: colored_number(value, format_percent(value)))
            elif col == "starter_rate" and not result[col].astype(str).str.contains("<span", regex=False).any():
                result[col] = result[col].map(starter_rate_value)
            elif col in {"mv_change_yesterday", "predicted_mv_target", "predicted_mv_target_3d", "predicted_mv_target_7d", "squad_profit_loss"}:
                result[col] = result[col].map(lambda value: colored_number(value, format_number(value)))
            elif col == "Available Budget":
                result[col] = result[col].map(lambda value: budget_value(value, format_number(value)))
            elif col == "Avg Overpay":
                result[col] = result[col].map(lambda value: colored_number(value, format_number(value), positive_good=False))
            elif col == "bid_gap":
                result[col] = result[col].map(lambda value: colored_number(value, format_number(value)))
            elif col in {"mv", "purchase_price", "max_bid", "winning_bid", "opponent_overpay_forecast", "Budget", "Team Value", "Max Negative", "recent_starts", "recent_apps", "last_season_points", "last_season_avg_points", "kickbase_average_points", "kickbase_total_points"}:
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
        hidden_cols = {
            "has_open_bid",
            "is_listed_for_sale",
            "buy_priority_score",
            "position_needed",
            "opponent_overpay_breakdown",
            "Erw. Gegner-Overpay",
            "Sieggebot",
            "Gap",
            "Overpay-Gegner",
        }
        visible_cols = [col for col in result.columns if col not in hidden_cols]

        def column_style(col, is_header=False):
            base = "background:#2c3e50;color:white;" if is_header else ""
            if col == "Action":
                return base + "padding:4px;text-align:center;width:76px;max-width:76px;white-space:nowrap;"
            if col == "Spieler":
                return base + "padding:4px 5px;text-align:left;width:180px;max-width:180px;"
            if col == "MW-Tendenz":
                return base + "padding:4px;text-align:center;width:54px;max-width:54px;white-space:nowrap;"
            return base + "padding:6px;text-align:left;white-space:nowrap;"

        header_html = "".join(
            f'<th style="{column_style(col, is_header=True)}'
            f'border-bottom:1px solid #ddd;">{escape(str(col))}</th>'
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
                f'<td style="{column_style(col)}border-bottom:1px solid #eee;vertical-align:middle;">'
                f'{"" if row.get(col) is None else row.get(col)}</td>'
                for col in visible_cols
            )
            rows.append(f'<tr style="{row_style}">{cells}</tr>')

        footer_html = ""
        if {"mv", "squad_profit_loss"}.issubset(df.columns):
            total_market_value = numeric_sum(df["mv"])
            total_profit_loss = numeric_sum(df["squad_profit_loss"])
            total_last_mv_change = numeric_sum(df.get("mv_change_yesterday", []))
            total_expected_change = numeric_sum(df.get("predicted_mv_target", []))
            footer_cells = []
            for index, col in enumerate(visible_cols):
                if index == 0:
                    value = "<strong>Summe</strong>"
                elif col == "Marktwert":
                    value = f"<strong>{format_number(total_market_value)}</strong>"
                elif col == "G/V":
                    value = colored_number(total_profit_loss, format_number(total_profit_loss))
                elif col == "Letzte MW":
                    value = colored_number(total_last_mv_change, format_number(total_last_mv_change))
                elif col == "Erw. 1T":
                    value = colored_number(total_expected_change, format_number(total_expected_change))
                else:
                    value = ""
                footer_cells.append(
                    f'<td style="{column_style(col)}border-top:2px solid #cbd5e1;'
                    f'background:#f8fafc;vertical-align:middle;">{value}</td>'
                )
            footer_html = f'<tfoot><tr>{"".join(footer_cells)}</tr></tfoot>'

        return (
            '<div style="max-width:100%;overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;font-size:12px;'
            f'margin:16px 0 24px 0;table-layout:auto;"><thead><tr>{header_html}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>{footer_html}</table></div>'
        )

    action_overview = build_action_overview()
    lineup_advice = build_lineup_advice()
    squad_change_summary = build_squad_change_summary()

    # Set email content
    msg.set_content("Sorry, results only via html visible.", subtype="plain")
    msg.add_alternative(f"""\
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        @media (max-width: 700px) {{
          .report-card {{ display:block !important; width:100% !important; padding:0 0 12px !important; box-sizing:border-box; }}
          .report-cards, .report-cards > tbody, .report-cards > tbody > tr {{ display:block !important; width:100% !important; }}
        }}
      </style>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 8px;">
        <div style="max-width: 1500px; width: 100%; margin: auto; background: #ffffff; padding: 14px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); overflow-x: auto; box-sizing: border-box;">
        
        <h2 style="color: #1f2933; text-align: center; margin-top: 0;">Kickbase Report für {today}</h2>

        {action_overview}
        
        {lineup_advice}

        <h3 style="color: #2c3e50; margin-top: 30px;">Manager-Budgets</h3>
        <p style="font-size: 14px; color: #333;">Nur dein eigener Kontostand stammt direkt aus der API. Fremde Kontostände werden aus 80 Mio. Startcash, 100 Mio. Startkader, Transferhistorie, Profilgewinn und nachvollziehbaren Bonusannahmen geschätzt. Die Erfolgsberechnung erfolgt im Hintergrund.</p>
        {style_df(budget_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Aktuelle Markt-Empfehlungen</h3>
        <p style="font-size: 14px; color: #333;">Fremde Marktangebote, sortiert nach Ablauf. Erw. 1T zeigt die erwartete nächste Marktwertänderung.</p>

        {style_df(market_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Dein Kader</h3>
        <p style="font-size: 14px; color: #333;">Dein Kader sortiert nach letzter Marktwertänderung, mit den stärksten Verlusten zuerst, inklusive Verkaufs- und Haltesignalen.</p>
        {squad_change_summary}

        {style_df(squad_df)}


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
        print("\nEmail sent successfully!")
    except smtplib.SMTPAuthenticationError:
        print("\nEmail authentication failed, skipping email sending. Check EMAIL_USER and EMAIL_PASS.")
        return
    except smtplib.SMTPException as e:
        print(f"\nEmail sending failed, skipping email sending: {e}")
        return
