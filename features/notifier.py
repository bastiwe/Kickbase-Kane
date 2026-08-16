from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape
from numbers import Number
from zoneinfo import ZoneInfo
import smtplib
import os

COLUMN_LABELS = {
    "recommendation": "Action",
    "player_display": "Player",
    "last_name": "Player",
    "team_name": "Team",
    "mv": "Market Value",
    "max_bid": "Max Bid",
    "mv_change_yesterday": "Yesterday",
    "predicted_mv_target": "Expected Change",
    "expected_change_pct": "Expected %",
    "s_11_prob": "Lineup %",
    "hours_to_exp": "Hours Left",
    "risk": "Risk",
    "User": "Manager",
    "Budget": "Cash",
    "Team Value": "Team Value",
    "Max Negative": "Debt Limit",
    "Available Budget": "Buying Power",
}

BADGE_STYLES = {
    "Strong buy": ("#dcfce7", "#166534"),
    "Buy": ("#e0f2fe", "#075985"),
    "Keep": ("#dcfce7", "#166534"),
    "Hold": ("#f3f4f6", "#374151"),
    "Consider sell": ("#fef3c7", "#92400e"),
    "Sell": ("#fee2e2", "#991b1b"),
    "Normal": ("#f3f4f6", "#374151"),
    "Expires soon": ("#ffedd5", "#9a3412"),
    "Low lineup prob": ("#fee2e2", "#991b1b"),
}

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

    def format_number(value):
        if isinstance(value, bool):
            return "Yes" if value else "No"
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
        label = escape(str(value))
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

    def prepare_df(df):
        result = df.copy()
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
                return (
                    '<div style="white-space:nowrap;display:flex;align-items:center;">'
                    f'{image}<span style="font-weight:600;color:#1f2933;">{name}</span></div>'
                )

            result.insert(1, "player_display", result.apply(player_display, axis=1))
            result = result.drop(columns=["first_name", "last_name", "image_url"], errors="ignore")

        for col in result.columns:
            if col in {"recommendation", "risk"}:
                result[col] = result[col].map(badge)
            elif col == "expected_change_pct":
                result[col] = result[col].map(lambda value: colored_number(value, format_percent(value)))
            elif col in {"mv_change_yesterday", "predicted_mv_target"}:
                result[col] = result[col].map(lambda value: colored_number(value, format_number(value)))
            elif col == "Available Budget":
                result[col] = result[col].map(lambda value: budget_value(value, format_number(value)))
            elif col in {"mv", "max_bid", "Budget", "Team Value", "Max Negative"}:
                result[col] = result[col].map(format_number)
            elif col == "hours_to_exp":
                result[col] = result[col].map(hours_value)
            elif col == "s_11_prob":
                result[col] = result[col].map(lambda value: format_number(value) if value == value else "-")

        return result.rename(columns=COLUMN_LABELS)

    def style_df(df):
        if df.empty:
            return '<p style="font-size:14px;color:#555;">No matching players today.</p>'

        return prepare_df(df).to_html(index=False, border=0, classes="dataframe", escape=False).replace(
            "<table",
            '<table style="width:100%;border-collapse:collapse;font-size:13px;margin:16px 0 24px 0;"'
        ).replace(
            "<th>",
            '<th style="background:#2c3e50;color:white;padding:8px;text-align:left;border-bottom:1px solid #ddd;">'
        ).replace(
            "<td>",
            '<td style="padding:8px;border-bottom:1px solid #eee;">'
        ).replace(
            '<tr style="text-align: right;">',
            '<tr style="background-color:#fefefe;">'
        )

    action_legend = f"""
        <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin:0 0 24px 0;">
            <h3 style="color:#1f2933;margin:0 0 10px 0;font-size:16px;">Action legend</h3>
            <p style="font-size:13px;color:#4b5563;margin:0 0 8px 0;">
                The action is derived from the model's expected next-day market value change, both absolute and relative to the player's current market value.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Market:</b>
                {badge("Strong buy")} expected change >= 200.000 or >= 2.00%;
                {badge("Buy")} expected change >= 75.000 or >= 0.75%.
                Other market players are hidden as Watch.
            </p>
            <p style="font-size:13px;color:#374151;margin:0;">
                <b>Squad:</b>
                {badge("Sell")} expected change <= -200.000 or <= -2.00%;
                {badge("Consider sell")} expected change <= -75.000 or <= -0.75%;
                {badge("Keep")} expected change >= 100.000 or >= 1.00%;
                {badge("Hold")} neutral range.
            </p>
        </div>
    """

    # Set email content
    msg.set_content("Sorry, results only via html visible.", subtype="plain")
    msg.add_alternative(f"""\
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">
        <div style="max-width: 1120px; margin: auto; background: #ffffff; padding: 22px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); overflow-x: auto;">
        
        <h2 style="color: #1f2933; text-align: center; margin-top: 0;">Kickbase Report for {today}</h2>
        
        <div style="display:block;margin:16px 0 24px 0;">
            <span style="display:inline-block;background:#edf7ed;color:#1f6f3d;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;"><b>{market_buy_count}</b> strong buys</span>
            <span style="display:inline-block;background:#fff4e5;color:#8a4b00;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;"><b>{squad_sell_count}</b> sell checks</span>
            <span style="display:inline-block;background:#eef2ff;color:#263a8b;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;">Top buying power: <b>{top_budget}</b></span>
        </div>

        {action_legend}

        <h3 style="color: #2c3e50; margin-top: 30px;">Manager Budgets</h3>
        <p style="font-size: 14px; color: #333;">Estimated cash and buying power after visible transfers, points, login and achievement estimates.</p>
        {style_df(budget_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Current Market Predictions</h3>
        <p style="font-size: 14px; color: #333;">Players with a positive expected next-day value change. Max Bid keeps roughly 35% of the predicted upside as margin.</p>

        {style_df(market_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Your Squad Predictions</h3>
        <p style="font-size: 14px; color: #333;">Your squad sorted by predicted value change, including sell and hold signals.</p>

        {style_df(squad_df)}

        <p style="margin-top: 20px; font-size: 14px;">Best regards, <br><b>Your KickAdvisor Bot</b></p>
        
        <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
        <p style="font-size: 11px; color: gray; text-align: center;">
            This email was generated by the 
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
