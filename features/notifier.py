from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape
from numbers import Number
from zoneinfo import ZoneInfo
import smtplib
import os

COLUMN_LABELS = {
    "recommendation": "Action",
    "player_display": "Spieler",
    "last_name": "Spieler",
    "position": "Pos",
    "team_name": "Team",
    "mv": "Marktwert",
    "max_bid": "Max. Gebot",
    "mv_change_yesterday": "Gestern",
    "predicted_mv_target": "Erwartete Änderung",
    "expected_change_pct": "Erwartet %",
    "s_11_prob": "Startelf %",
    "hours_to_exp": "Reststunden",
    "risk": "Risiko",
    "User": "Manager",
    "Budget": "Cash",
    "Team Value": "Kaderwert",
    "Max Negative": "Minuslimit",
    "Available Budget": "Kaufkraft",
}

DISPLAY_LABELS = {
    "Strong buy": "Top-Kauf",
    "Buy": "Kaufen",
    "Keep": "Behalten",
    "Hold": "Halten",
    "Consider sell": "Verkauf prüfen",
    "Sell": "Verkaufen",
    "Normal": "Normal",
    "Expires soon": "Läuft bald ab",
    "Low lineup prob": "Geringe Startelfchance",
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

    def lineup_probability(value):
        formatted = format_number(value) if isinstance(value, Number) and value == value else "-"
        if not isinstance(value, Number) or value != value:
            return formatted
        if value >= 70:
            background, color = "#dcfce7", "#166534"
        elif value >= 40:
            background, color = "#fef3c7", "#92400e"
        else:
            background, color = "#fee2e2", "#991b1b"
        return (
            f'<span style="display:inline-block;background:{background};color:{color};'
            'font-weight:700;border-radius:6px;padding:3px 7px;white-space:nowrap;">'
            f'{formatted}</span>'
        )

    def position_label(value):
        return POSITION_LABELS.get(value, POSITION_LABELS.get(str(value), "-"))

    def player_name(row):
        first_name = "" if row.get("first_name") != row.get("first_name") else str(row.get("first_name", ""))
        last_name = "" if row.get("last_name") != row.get("last_name") else str(row.get("last_name", ""))
        return f"{first_name} {last_name}".strip() or "-"

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
            if needed_positions:
                candidates = candidates[candidates["position"].astype(str).isin([str(pos) for pos in needed_positions])]
            candidates["recommendation_rank"] = candidates["recommendation"].map({"Strong buy": 0, "Buy": 1}).fillna(2)
            candidates = candidates.sort_values(["recommendation_rank", "predicted_mv_target"], ascending=[True, False]).head(4)
            for _, row in candidates.iterrows():
                market_rows.append(
                    f'<li><b>{escape(player_name(row))}</b> ({position_label(row.get("position"))}, {escape(str(row.get("team_name", "-")))}) '
                    f'- {badge(row.get("recommendation", "Buy"))} '
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
                <p style="font-size:13px;color:#374151;margin:0 0 6px 0;"><b>Nächstliegende Formationen:</b></p>
                <ul style="margin:0 0 10px 18px;padding:0;font-size:13px;color:#374151;">{''.join(option_rows)}</ul>
                <p style="font-size:13px;color:#374151;margin:0 0 4px 0;"><b>Sinnvolle Markt-Ergänzungen:</b></p>
                {market_html}
            </div>
        """

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
                result[col] = result[col].map(lineup_probability)
            elif col == "position":
                result[col] = result[col].map(position_label)

        return result.rename(columns=COLUMN_LABELS)

    def style_df(df):
        if df.empty:
            return '<p style="font-size:14px;color:#555;">Heute gibt es keine passenden Spieler.</p>'

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
            <h3 style="color:#1f2933;margin:0 0 10px 0;font-size:16px;">Action-Legende</h3>
            <p style="font-size:13px;color:#4b5563;margin:0 0 8px 0;">
                Die Action ergibt sich aus der vom Modell erwarteten Marktwertänderung für den nächsten Tag, absolut und relativ zum aktuellen Marktwert.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Markt:</b>
                {badge("Strong buy")} erwartete Änderung >= 200.000 oder >= 2,00%;
                {badge("Buy")} erwartete Änderung >= 75.000 oder >= 0,75%.
                Schwächere Marktspieler werden ausgeblendet.
            </p>
            <p style="font-size:13px;color:#374151;margin:0 0 6px 0;">
                <b>Max. Gebot:</b>
                Marktwert + 65% des erwarteten Upsides, danach auf sinnvolle Gebotsstufen aufgerundet
                und mit kleinem Overbid versehen, um runde Konkurrenzgebote zu schlagen.
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
    lineup_advice = build_lineup_advice()

    # Set email content
    msg.set_content("Sorry, results only via html visible.", subtype="plain")
    msg.add_alternative(f"""\
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">
        <div style="max-width: 1120px; margin: auto; background: #ffffff; padding: 22px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); overflow-x: auto;">
        
        <h2 style="color: #1f2933; text-align: center; margin-top: 0;">Kickbase Report für {today}</h2>
        
        <div style="display:block;margin:16px 0 24px 0;">
            <span style="display:inline-block;background:#edf7ed;color:#1f6f3d;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;"><b>{market_buy_count}</b> Top-Käufe</span>
            <span style="display:inline-block;background:#fff4e5;color:#8a4b00;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;"><b>{squad_sell_count}</b> Verkaufschecks</span>
            <span style="display:inline-block;background:#eef2ff;color:#263a8b;padding:8px 10px;border-radius:6px;margin:4px;font-size:13px;">Höchste Kaufkraft: <b>{top_budget}</b></span>
        </div>

        {action_legend}

        {lineup_advice}

        <h3 style="color: #2c3e50; margin-top: 30px;">Manager-Budgets</h3>
        <p style="font-size: 14px; color: #333;">Geschätztes Cash und Kaufkraft nach sichtbaren Transfers, Punkten sowie geschätzten Login- und Achievement-Boni.</p>
        {style_df(budget_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Aktuelle Markt-Empfehlungen</h3>
        <p style="font-size: 14px; color: #333;">Spieler mit positiver erwarteter Marktwertänderung für den nächsten Tag. Das maximale Gebot lässt grob 35% des prognostizierten Upsides als Puffer.</p>

        {style_df(market_df)}

        <h3 style="color: #2c3e50; margin-top: 30px;">Dein Kader</h3>
        <p style="font-size: 14px; color: #333;">Dein Kader sortiert nach prognostizierter Marktwertänderung, inklusive Verkaufs- und Haltesignalen.</p>

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
    except smtplib.SMTPAuthenticationError:
        print("\nEmail authentication failed, skipping email sending. Check EMAIL_USER and EMAIL_PASS.")
        return
    except smtplib.SMTPException as e:
        print(f"\nEmail sending failed, skipping email sending: {e}")
        return

    print("\nEmail sent successfully!")
