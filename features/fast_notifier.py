from datetime import datetime
from email.message import EmailMessage
from html import escape
from numbers import Number
from zoneinfo import ZoneInfo
import os
import smtplib


STATUS_STYLES = {
    "Fit": ("#dcfce7", "#166534"),
    "Angeschlagen": ("#fef3c7", "#92400e"),
    "Gelbsperre": ("#ffedd5", "#9a3412"),
    "Verletzt": ("#fee2e2", "#991b1b"),
    "Reha": ("#ffedd5", "#9a3412"),
    "Rotgesperrt": ("#fee2e2", "#991b1b"),
    "Gelb-Rot-Sperre": ("#fee2e2", "#991b1b"),
    "Nicht im Kader": ("#fee2e2", "#991b1b"),
    "Nicht in Liga": ("#fee2e2", "#991b1b"),
    "Abwesend": ("#fee2e2", "#991b1b"),
}

POSITION_LABELS = {1: "TW", 2: "ABW", 3: "MIT", 4: "ST", "1": "TW", "2": "ABW", "3": "MIT", "4": "ST"}


def send_fast_mail(market_df, squad_df, email):
    if not email:
        print("Fast mail skipped: EMAIL_USER is not set.")
        return

    market_df = sort_fast_market(market_df)
    squad_df = sort_fast_squad(squad_df)
    now = datetime.now(ZoneInfo("Europe/Berlin"))

    msg = EmailMessage()
    msg["Subject"] = f"Kickbase Fast Report 1T - {now:%d.%m.%Y %H:%M}"
    msg["From"] = os.getenv("EMAIL_USER")
    msg["To"] = email
    msg.set_content("Fast Report ist als HTML-Mail verfügbar.", subtype="plain")
    msg.add_alternative(f"""
    <html>
      <body style="margin:0;background:#eef2f7;font-family:Arial,Helvetica,sans-serif;color:#111827;">
        <div style="max-width:1500px;margin:0 auto;background:#ffffff;padding:16px;">
          <h2 style="margin:0 0 4px 0;">Kickbase Fast Report 1T</h2>
          <p style="margin:0 0 16px 0;color:#6b7280;font-size:13px;">
            Fokus auf schnelle Ausführung: nur 1-Tages-Prognose, aktueller Transfermarkt und eigener Kader.
          </p>

          <h3 style="margin:18px 0 8px 0;">Transfermarkt: beste erwartete MW-Steigerungen</h3>
          {table_html(market_df, is_market=True)}

          <h3 style="margin:18px 0 8px 0;">Mein Kader: 1T-Prognose</h3>
          {table_html(squad_df, is_market=False)}
        </div>
      </body>
    </html>
    """, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
        smtp.send_message(msg)
    print("Fast report email sent.")


def sort_fast_market(df):
    if df is None or df.empty:
        return df
    result = df.copy()
    result["sort_predicted"] = result["predicted_mv_target"].fillna(0)
    return result.sort_values("sort_predicted", ascending=False).drop(columns=["sort_predicted"], errors="ignore")


def sort_fast_squad(df):
    if df is None or df.empty:
        return df
    result = df.copy()
    result["sort_predicted"] = result["predicted_mv_target"].fillna(0)
    return result.sort_values("sort_predicted", ascending=False).drop(columns=["sort_predicted"], errors="ignore")


def table_html(df, is_market):
    if df is None or df.empty:
        return '<p style="font-size:13px;color:#6b7280;">Keine Daten verfügbar.</p>'

    columns = [
        ("Spieler", player_cell),
        ("Pos", lambda row: escape(position_label(row.get("position")))),
        ("Team", lambda row: escape(str(row.get("team_name", "-")))),
        ("Status", lambda row: status_badge(row.get("player_status"))),
        ("Marktwert", lambda row: format_number(row.get("mv"))),
        ("Letzte MW", lambda row: colored_number(row.get("mv_change_yesterday"))),
        ("Erw. 1T", lambda row: colored_number(row.get("predicted_mv_target"))),
        ("Erw. %", lambda row: colored_pct(row.get("expected_change_pct"))),
    ]
    if is_market:
        columns.extend([
            ("Ablauf", lambda row: expiry_value(row.get("expires_at"))),
            ("Gebot", lambda row: "ja" if bool(row.get("has_open_bid", False)) else "-"),
        ])
    else:
        columns.append(("Angeboten", lambda row: "ja" if bool(row.get("is_listed_for_sale", False)) else "-"))

    head = "".join(
        f'<th style="background:#1f2937;color:white;text-align:left;padding:7px;border-bottom:1px solid #d1d5db;white-space:nowrap;">{title}</th>'
        for title, _ in columns
    )
    rows = []
    for _, row in df.iterrows():
        cells = "".join(
            f'<td style="padding:7px;border-bottom:1px solid #e5e7eb;vertical-align:middle;">{renderer(row)}</td>'
            for _, renderer in columns
        )
        rows.append(f'<tr style="background:#ffffff;">{cells}</tr>')

    return (
        '<div style="overflow-x:auto;">'
        '<table style="width:100%;min-width:1050px;border-collapse:collapse;font-size:12px;">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def player_cell(row):
    first_name = "" if row.get("first_name") != row.get("first_name") else str(row.get("first_name", ""))
    last_name = "" if row.get("last_name") != row.get("last_name") else str(row.get("last_name", ""))
    name = escape(f"{first_name} {last_name}".strip() or "-")
    image_url = row.get("image_url")
    if image_url == image_url and image_url:
        image = (
            f'<img src="{escape(str(image_url), quote=True)}" alt="{name}" '
            'style="width:34px;height:34px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:8px;background:#e5e7eb;">'
        )
    else:
        image = '<span style="display:inline-block;width:34px;height:34px;border-radius:50%;background:#e5e7eb;vertical-align:middle;margin-right:8px;"></span>'
    return f"{image}<strong>{name}</strong>"


def status_badge(value):
    value = "Fit" if value is None or value != value or str(value) == "" else str(value)
    bg, color = STATUS_STYLES.get(value, ("#f3f4f6", "#374151"))
    return f'<span style="display:inline-block;background:{bg};color:{color};border-radius:999px;padding:3px 8px;font-weight:700;white-space:nowrap;">{escape(value)}</span>'


def colored_number(value):
    if not isinstance(value, Number) or value != value:
        return "-"
    color = "#166534" if value > 0 else "#991b1b" if value < 0 else "#374151"
    return f'<span style="color:{color};font-weight:800;">{format_number(value)}</span>'


def colored_pct(value):
    if not isinstance(value, Number) or value != value:
        return "-"
    color = "#166534" if value > 0 else "#991b1b" if value < 0 else "#374151"
    return f'<span style="color:{color};font-weight:800;">{value:.2f}%</span>'


def format_number(value):
    if not isinstance(value, Number) or value != value:
        return "-"
    return f"{value:,.0f}".replace(",", ".")


def position_label(value):
    return POSITION_LABELS.get(value, POSITION_LABELS.get(str(value), "-"))


def expiry_value(value):
    if value is None or value != value:
        return "-"
    try:
        value = value.astimezone(ZoneInfo("Europe/Berlin"))
        return f"{value:%d.%m. %H:%M}"
    except Exception:
        return escape(str(value))
