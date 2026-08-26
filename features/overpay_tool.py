from datetime import datetime
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


def write_overpay_tool(market_df, budget_df, output_path="overpay_forecast.html"):
    """Write a standalone HTML tool for inspecting opponent overpay forecasts."""

    output_path = Path(output_path)
    players = build_player_payload(market_df)
    managers = build_manager_payload(budget_df)
    recent_purchases = build_recent_purchase_payload(budget_df)

    payload = {
        "generatedAt": datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M"),
        "players": players,
        "managers": managers,
        "recentPurchases": recent_purchases,
    }

    html = render_overpay_tool(payload)
    output_path.write_text(html, encoding="utf-8")
    print(f"Overpay forecast tool written to {output_path}.")
    return output_path


def build_player_payload(market_df):
    if market_df is None or market_df.empty:
        return []

    result = []
    for _, row in market_df.iterrows():
        first_name = clean_value(row.get("first_name"), "")
        last_name = clean_value(row.get("last_name"), "")
        name = f"{first_name} {last_name}".strip() or clean_value(row.get("player_display"), "Unbekannt")
        breakdown = row.get("opponent_overpay_breakdown")
        if not isinstance(breakdown, list):
            breakdown = []

        result.append({
            "name": name,
            "team": clean_value(row.get("team_name"), "-"),
            "position": position_label(row.get("position")),
            "status": clean_value(row.get("player_status"), "Fit"),
            "imageUrl": clean_value(row.get("image_url"), ""),
            "marketValue": number_value(row.get("mv")),
            "maxBid": number_value(row.get("max_bid")),
            "winningBid": number_value(row.get("winning_bid")),
            "bidGap": number_value(row.get("bid_gap")),
            "expectedChange": number_value(row.get("predicted_mv_target")),
            "buyType": clean_value(row.get("buy_type"), "-"),
            "priority": clean_value(row.get("buy_priority"), "-"),
            "classTag": clean_value(row.get("top_player_tag"), ""),
            "pressure": clean_value(row.get("opponent_pressure"), "Unklar"),
            "opponentOverpay": number_value(row.get("opponent_overpay_forecast")),
            "opponentDetails": clean_value(row.get("opponent_overpay_details"), ""),
            "opponents": [
                {
                    "name": clean_value(item.get("name"), "-"),
                    "overpay": number_value(item.get("overpay")),
                    "availableBudget": number_value(item.get("available_budget")),
                    "rosterNote": clean_value(item.get("roster_note"), ""),
                    "squadSize": number_value(item.get("squad_size")),
                    "teamCount": number_value(item.get("team_count")),
                    "aggressionScore": number_value(item.get("aggression_score")),
                    "archetype": clean_value(item.get("archetype"), ""),
                    "pattern": clean_value(item.get("pattern"), ""),
                    "explain": build_explain_payload(item.get("explain")),
                }
                for item in breakdown
            ],
        })

    return sorted(result, key=lambda item: (item["pressure"] != "Hoch", -(item["opponentOverpay"] or 0), item["name"]))


def build_manager_payload(budget_df):
    if budget_df is None or budget_df.empty:
        return []

    managers = []
    profiles = getattr(budget_df, "attrs", {}).get("overpay_profiles") or {}
    for _, row in budget_df.iterrows():
        profile = profiles.get(row.get("User")) or {}
        managers.append({
            "name": clean_value(row.get("User"), "-"),
            "avgOverpay": number_value(row.get("Avg Overpay")),
            "availableBudget": number_value(row.get("Available Budget")),
            "teamValue": number_value(row.get("Team Value")),
            "aggressionScore": number_value(profile.get("aggression_score")),
            "archetype": clean_value(profile.get("archetype"), ""),
            "samples": number_value(profile.get("samples")),
        })
    return managers


def build_recent_purchase_payload(budget_df, limit=80):
    if budget_df is None:
        return []

    overpay_rows = getattr(budget_df, "attrs", {}).get("overpay_rows")
    if overpay_rows is None or overpay_rows.empty:
        return []

    rows = overpay_rows.copy()
    own_user = getattr(budget_df, "attrs", {}).get("own_user")
    if own_user and "User" in rows:
        rows = rows[rows["User"] != own_user]
    if rows.empty:
        return []

    rows["_sort_date"] = pd.to_datetime(rows.get("Date"), errors="coerce")
    rows = rows.sort_values(["User", "_sort_date"], ascending=[True, False]).head(limit)

    purchases = []
    for _, row in rows.iterrows():
        purchases.append({
            "date": format_purchase_date(row.get("Date")),
            "manager": clean_value(row.get("User"), "-"),
            "player": clean_value(row.get("Player"), "Unbekannt"),
            "position": clean_value(row.get("Position"), "-"),
            "price": number_value(row.get("Price")),
            "marketValue": number_value(row.get("MarketValue")),
            "overpay": number_value(row.get("Overpay")),
            "overpayPct": number_value(row.get("OverpayPct")),
            "marketValueBucket": clean_value(row.get("MarketValueBucket"), "-"),
            "momentumBucket": clean_value(row.get("MomentumBucket"), "-"),
            "qualityBucket": clean_value(row.get("QualityBucket"), "-"),
        })
    return purchases


def format_purchase_date(value):
    if value is None or pd.isna(value):
        return "-"
    try:
        parsed = pd.to_datetime(value)
        if pd.isna(parsed):
            return clean_value(value, "-")
        return parsed.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return clean_value(value, "-")


def build_explain_payload(explain):
    if not isinstance(explain, dict):
        return {}
    keys = [
        "base",
        "bucket",
        "manager_avg",
        "manager_segment",
        "league_avg",
        "league_segment",
        "segment_weight",
        "manager_weight",
        "quality_factor",
        "pattern_factor",
        "escalation_factor",
        "position_factor",
        "momentum_factor",
        "class_factor",
        "position_key",
        "momentum_key",
        "quality_key",
    ]
    return {key: clean_explain_value(explain.get(key)) for key in keys if explain.get(key) is not None}


def clean_explain_value(value):
    if isinstance(value, (int, float)):
        return number_value(value)
    return clean_value(value, "")


def render_overpay_tool(payload):
    data = json.dumps(payload, ensure_ascii=False)
    generated_at = escape(clean_value(payload.get("generatedAt"), "-"))
    first_player = (payload.get("players") or [None])[0]
    static_player_panel = render_static_player_panel(first_player)
    static_opponent_table = render_static_opponent_table(first_player)
    static_manager_table = render_static_manager_table(payload.get("managers") or [])
    static_purchase_table = render_static_purchase_table(payload.get("recentPurchases") or [])
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kickbase Overpay-Prognose</title>
  <style>
    :root {{
      --ink: #111827;
      --muted: #6b7280;
      --line: #e5e7eb;
      --soft: #f8fafc;
      --green: #166534;
      --amber: #92400e;
      --red: #991b1b;
      --blue: #075985;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #eef2f7;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
    }}
    h1 {{
      margin: 0 0 4px;
      font-size: 26px;
    }}
    .sub {{
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 14px;
    }}
    .panel {{
      background: white;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) minmax(280px, 2fr);
      gap: 12px;
    }}
    label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
      margin-bottom: 5px;
      text-transform: uppercase;
    }}
    input, select {{
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 7px;
      padding: 10px 11px;
      font-size: 15px;
      background: white;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 108px 1fr;
      gap: 16px;
      align-items: center;
    }}
    .photo {{
      width: 108px;
      height: 108px;
      border-radius: 8px;
      background: #e5e7eb;
      object-fit: cover;
    }}
    .photoFallback {{
      width: 108px;
      height: 108px;
      border-radius: 8px;
      background: #dbeafe;
      color: var(--blue);
      display: grid;
      place-items: center;
      font-weight: 900;
      font-size: 32px;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }}
    .chip {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 12px;
      font-weight: 800;
      background: #f3f4f6;
      color: #374151;
    }}
    .high {{ background: #fee2e2; color: var(--red); }}
    .mid {{ background: #fef3c7; color: var(--amber); }}
    .low {{ background: #dcfce7; color: var(--green); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      margin-top: 14px;
    }}
    .metric {{
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
    }}
    .metric span {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 5px;
    }}
    .metric strong {{
      font-size: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 9px 7px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
    }}
    th {{
      color: #374151;
      background: var(--soft);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .barWrap {{
      height: 9px;
      background: #e5e7eb;
      border-radius: 999px;
      overflow: hidden;
      min-width: 130px;
    }}
    .bar {{
      height: 100%;
      background: #0ea5e9;
    }}
    .muted {{ color: var(--muted); }}
    .pos {{ color: var(--green); font-weight: 800; }}
    .neg {{ color: var(--red); font-weight: 800; }}
    .tableScroll {{ overflow-x: auto; }}
    .groupRow td {{
      background: #eef2ff;
      color: #1e3a8a;
      font-weight: 900;
      border-top: 2px solid #c7d2fe;
      border-bottom: 1px solid #c7d2fe;
    }}
    @media (max-width: 780px) {{
      main {{ padding: 12px; }}
      .controls, .hero, .grid {{ grid-template-columns: 1fr; }}
      table {{ font-size: 12px; }}
      .photo, .photoFallback {{ width: 86px; height: 86px; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Kickbase Overpay-Prognose</h1>
    <p class="sub">Generiert am <span id="generatedAt">{generated_at}</span>. Modelliert aus bisherigem Bietverhalten, Marktwert-Segmenten und Spielerklasse.</p>

    <section class="panel">
      <div class="controls">
        <div>
          <label for="search">Spieler suchen</label>
          <input id="search" type="search" placeholder="Name, Team oder Position">
        </div>
        <div>
          <label for="playerSelect">Spieler auswählen</label>
          <select id="playerSelect"></select>
        </div>
      </div>
    </section>

    <section class="panel" id="playerPanel">{static_player_panel}</section>
    <section class="panel">
      <h2 style="font-size:18px;margin:0 0 10px;">Erwarteter Gegner-Overpay</h2>
      <div id="opponentTable">{static_opponent_table}</div>
    </section>
    <section class="panel">
      <h2 style="font-size:18px;margin:0 0 10px;">Manager-Profil</h2>
      <div id="managerTable">{static_manager_table}</div>
    </section>
    <section class="panel">
      <h2 style="font-size:18px;margin:0 0 10px;">Letzte Käufe der Mitmanager</h2>
      <p class="sub" style="margin-bottom:10px;">Tatsächlicher Overpay = gezahlter Kaufpreis minus Marktwert zum Transferzeitpunkt.</p>
      <div id="purchaseTable">{static_purchase_table}</div>
    </section>
  </main>
  <script>
    const DATA = {data};
    const fmt = new Intl.NumberFormat('de-DE', {{ maximumFractionDigits: 0 }});
    const money = value => value === null || Number.isNaN(value) ? '-' : fmt.format(value) + ' €';
    const plusMoney = value => value === null || Number.isNaN(value) ? '-' : '+' + money(value);
    const signedMoney = value => value === null || Number.isNaN(value) ? '-' : (value > 0 ? '+' : '') + money(value);
    const signedClass = value => value === null || Number.isNaN(value) ? '' : value < 0 ? 'neg' : value > 0 ? 'pos' : '';
    const pct = value => value === null || Number.isNaN(value) ? '-' : Number(value).toFixed(1).replace('.', ',') + '%';
    const factor = value => value === undefined || value === null || Number.isNaN(value) ? '-' : 'x' + Number(value).toFixed(2);
    const byId = id => document.getElementById(id);

    function pressureClass(value) {{
      if (value === 'Hoch') return 'high';
      if (value === 'Mittel') return 'mid';
      if (value === 'Niedrig') return 'low';
      return '';
    }}

    function statusClass(value) {{
      if (value === 'Fit') return 'low';
      if (['Angeschlagen', 'Reha', 'Gelbsperre'].includes(value)) return 'mid';
      if (value && value !== '-') return 'high';
      return '';
    }}

    function gapClass(value) {{
      if (value === null || Number.isNaN(value)) return '';
      if (value >= 0) return 'low';
      if (value >= -500000) return 'mid';
      return 'high';
    }}

    function initials(name) {{
      return (name || '?').split(/\\s+/).slice(0, 2).map(part => part[0] || '').join('').toUpperCase();
    }}

    function formula(item) {{
      const explain = item.explain || {{}};
      if (!explain.base) return '-';
      return `${{money(explain.base)}} × Qualität ${{factor(explain.quality_factor)}} × Muster ${{factor(explain.pattern_factor)}} × Eskalation ${{factor(explain.escalation_factor)}}`;
    }}

    function formulaTitle(item) {{
      const explain = item.explain || {{}};
      if (!explain.base) return '';
      return [
        `Basis: ${{money(explain.base)}}`,
        `Segment: ${{explain.bucket || '-'}}`,
        `Manager Ø: ${{money(explain.manager_avg)}}`,
        `Manager Segment: ${{money(explain.manager_segment)}}`,
        `Liga Ø: ${{money(explain.league_avg)}}`,
        `Liga Segment: ${{money(explain.league_segment)}}`,
        `Position ${{explain.position_key || '-'}}: ${{factor(explain.position_factor)}}`,
        `Trend ${{explain.momentum_key || '-'}}: ${{factor(explain.momentum_factor)}}`,
        `Klasse ${{explain.quality_key || '-'}}: ${{factor(explain.class_factor)}}`
      ].join('\\n');
    }}

    function filteredPlayers() {{
      const query = byId('search').value.trim().toLowerCase();
      if (!query) return DATA.players;
      return DATA.players.filter(player =>
        [player.name, player.team, player.position, player.status, player.buyType, player.classTag]
          .join(' ').toLowerCase().includes(query)
      );
    }}

    function fillSelect(selectedName) {{
      const select = byId('playerSelect');
      const players = filteredPlayers();
      select.innerHTML = players.map((player, index) =>
        `<option value="${{index}}">${{player.name}} · ${{player.team}} · ${{plusMoney(player.opponentOverpay)}}</option>`
      ).join('');
      if (selectedName) {{
        const index = players.findIndex(player => player.name === selectedName);
        if (index >= 0) select.value = String(index);
      }}
      renderSelected();
    }}

    function renderSelected() {{
      const players = filteredPlayers();
      const player = players[Number(byId('playerSelect').value)] || players[0];
      if (!player) {{
        byId('playerPanel').innerHTML = '<p class="muted">Keine Spieler im aktuellen Report.</p>';
        byId('opponentTable').innerHTML = '';
        return;
      }}

      const photo = player.imageUrl
        ? `<img class="photo" src="${{player.imageUrl}}" alt="${{player.name}}">`
        : `<div class="photoFallback">${{initials(player.name)}}</div>`;
      byId('playerPanel').innerHTML = `
        <div class="hero">
          ${{photo}}
          <div>
            <h2 style="margin:0;font-size:24px;">${{player.name}}</h2>
            <div class="muted">${{player.position}} · ${{player.team}}</div>
            <div class="chips">
              <span class="chip ${{statusClass(player.status)}}">Status: ${{player.status}}</span>
              <span class="chip ${{pressureClass(player.pressure)}}">Gegnerdruck: ${{player.pressure}}</span>
              <span class="chip">${{player.buyType}}</span>
              <span class="chip">Priorität: ${{player.priority}}</span>
              ${{player.classTag ? `<span class="chip">${{player.classTag}}</span>` : ''}}
            </div>
          </div>
        </div>
        <div class="grid">
          <div class="metric"><span>Marktwert</span><strong>${{money(player.marketValue)}}</strong></div>
          <div class="metric"><span>Max. Gebot</span><strong>${{money(player.maxBid)}}</strong></div>
          <div class="metric"><span>Sieggebot</span><strong>${{money(player.winningBid)}}</strong></div>
          <div class="metric"><span>Gap</span><strong><span class="chip ${{gapClass(player.bidGap)}}">${{signedMoney(player.bidGap)}}</span></strong></div>
          <div class="metric"><span>Erw. 1T</span><strong>${{plusMoney(player.expectedChange)}}</strong></div>
          <div class="metric"><span>Erw. Gegner-Overpay</span><strong>${{plusMoney(player.opponentOverpay)}}</strong></div>
        </div>
      `;

      const maxOverpay = Math.max(...player.opponents.map(item => item.overpay || 0), 1);
      byId('opponentTable').innerHTML = player.opponents.length
        ? `<table>
            <thead><tr><th>Manager</th><th>Erw. Overpay</th><th>Kaufkraft</th><th>Bietmuster</th><th>Rechnung</th><th>Limit-Hinweis</th><th>Relativ</th></tr></thead>
            <tbody>
              ${{player.opponents.map(item => `
                <tr>
                  <td><strong>${{item.name}}</strong></td>
                  <td>${{plusMoney(item.overpay)}}</td>
                  <td>${{money(item.availableBudget)}}</td>
                  <td>${{item.pattern || item.archetype || '-'}}</td>
                  <td title="${{formulaTitle(item)}}">${{formula(item)}}</td>
                  <td>${{item.rosterNote || '-'}}</td>
                  <td><div class="barWrap"><div class="bar" style="width:${{Math.round(((item.overpay || 0) / maxOverpay) * 100)}}%"></div></div></td>
                </tr>
              `).join('')}}
            </tbody>
          </table>`
        : '<p class="muted">Keine belastbare Gegnerprognose verfügbar.</p>';
    }}

    function renderManagers() {{
      byId('managerTable').innerHTML = DATA.managers.length
        ? `<table>
            <thead><tr><th>Manager</th><th>Ø Overpay</th><th>Aggro</th><th>Typ</th><th>Kaufkraft</th><th>Kaderwert</th></tr></thead>
            <tbody>
              ${{DATA.managers.map(manager => `
                <tr>
                  <td><strong>${{manager.name}}</strong></td>
                  <td>${{plusMoney(manager.avgOverpay)}}</td>
                  <td>${{manager.aggressionScore === null ? '-' : Math.round(manager.aggressionScore) + '/100'}}</td>
                  <td>${{manager.archetype || '-'}}</td>
                  <td>${{money(manager.availableBudget)}}</td>
                  <td>${{money(manager.teamValue)}}</td>
                </tr>
              `).join('')}}
            </tbody>
          </table>`
        : '<p class="muted">Keine Managerdaten verfügbar.</p>';
    }}

    function renderPurchases() {{
      byId('purchaseTable').innerHTML = DATA.recentPurchases && DATA.recentPurchases.length
        ? `<div class="tableScroll"><table>
            <thead><tr><th>Datum</th><th>Spieler</th><th>Pos</th><th>Kaufpreis</th><th>MW bei Kauf</th><th>Tats. Overpay</th><th>Overpay %</th><th>Segment</th><th>Form</th><th>Klasse</th></tr></thead>
            <tbody>
              ${{purchaseRows(DATA.recentPurchases)}}
            </tbody>
          </table></div>`
        : '<p class="muted">Keine Kaufhistorie der Mitmanager verfügbar.</p>';
    }}

    function purchaseRows(items) {{
      let currentManager = null;
      return items.map(item => {{
        const group = item.manager !== currentManager
          ? `<tr class="groupRow"><td colspan="10">${{item.manager}}</td></tr>`
          : '';
        currentManager = item.manager;
        return `${{group}}
          <tr>
            <td>${{item.date}}</td>
            <td>${{item.player}}</td>
            <td>${{item.position}}</td>
            <td>${{money(item.price)}}</td>
            <td>${{money(item.marketValue)}}</td>
            <td class="${{signedClass(item.overpay)}}">${{signedMoney(item.overpay)}}</td>
            <td class="${{signedClass(item.overpay)}}">${{pct(item.overpayPct)}}</td>
            <td>${{item.marketValueBucket}}</td>
            <td>${{item.momentumBucket}}</td>
            <td>${{item.qualityBucket}}</td>
          </tr>`;
      }}).join('');
    }}

    byId('generatedAt').textContent = DATA.generatedAt;
    byId('search').addEventListener('input', () => fillSelect());
    byId('playerSelect').addEventListener('change', renderSelected);
    fillSelect();
    renderManagers();
    renderPurchases();
  </script>
</body>
</html>
"""


def render_static_player_panel(player):
    if not player:
        return '<p class="muted">Keine Spieler im aktuellen Report.</p>'

    name = escape(clean_value(player.get("name"), "-"))
    image_url = clean_value(player.get("imageUrl"), "")
    if image_url:
        photo = (
            f'<img class="photo" src="{escape(image_url, quote=True)}" alt="{name}">'
        )
    else:
        photo = f'<div class="photoFallback">{escape(initials(player.get("name")))}</div>'

    class_tag = clean_value(player.get("classTag"), "")
    class_badge = f'<span class="chip">{escape(class_tag)}</span>' if class_tag else ""
    bid_gap = player.get("bidGap")
    return f"""
        <div class="hero">
          {photo}
          <div>
            <h2 style="margin:0;font-size:24px;">{name}</h2>
            <div class="muted">{escape(clean_value(player.get("position"), "-"))} · {escape(clean_value(player.get("team"), "-"))}</div>
            <div class="chips">
              <span class="chip {status_class(player.get("status"))}">Status: {escape(clean_value(player.get("status"), "-"))}</span>
              <span class="chip {pressure_class(player.get("pressure"))}">Gegnerdruck: {escape(clean_value(player.get("pressure"), "-"))}</span>
              <span class="chip">{escape(clean_value(player.get("buyType"), "-"))}</span>
              <span class="chip">Priorität: {escape(clean_value(player.get("priority"), "-"))}</span>
              {class_badge}
            </div>
          </div>
        </div>
        <div class="grid">
          <div class="metric"><span>Marktwert</span><strong>{html_money(player.get("marketValue"))}</strong></div>
          <div class="metric"><span>Max. Gebot</span><strong>{html_money(player.get("maxBid"))}</strong></div>
          <div class="metric"><span>Sieggebot</span><strong>{html_money(player.get("winningBid"))}</strong></div>
          <div class="metric"><span>Gap</span><strong><span class="chip {gap_class(bid_gap)}">{html_signed_money(bid_gap)}</span></strong></div>
          <div class="metric"><span>Erw. 1T</span><strong>{html_plus_money(player.get("expectedChange"))}</strong></div>
          <div class="metric"><span>Erw. Gegner-Overpay</span><strong>{html_plus_money(player.get("opponentOverpay"))}</strong></div>
        </div>
    """


def render_static_opponent_table(player):
    if not player:
        return '<p class="muted">Keine belastbare Gegnerprognose verfügbar.</p>'

    opponents = player.get("opponents") or []
    if not opponents:
        return '<p class="muted">Keine belastbare Gegnerprognose verfügbar.</p>'

    max_overpay = max([item.get("overpay") or 0 for item in opponents] + [1])
    rows = []
    for item in opponents:
        width = round(((item.get("overpay") or 0) / max_overpay) * 100)
        rows.append(f"""
            <tr>
              <td><strong>{escape(clean_value(item.get("name"), "-"))}</strong></td>
              <td>{html_plus_money(item.get("overpay"))}</td>
              <td>{html_money(item.get("availableBudget"))}</td>
              <td>{escape(clean_value(item.get("pattern") or item.get("archetype"), "-"))}</td>
              <td title="{escape(static_formula_title(item), quote=True)}">{escape(static_formula(item))}</td>
              <td>{escape(clean_value(item.get("rosterNote"), "-"))}</td>
              <td><div class="barWrap"><div class="bar" style="width:{width}%"></div></div></td>
            </tr>
        """)

    return (
        "<table>"
        "<thead><tr><th>Manager</th><th>Erw. Overpay</th><th>Kaufkraft</th><th>Bietmuster</th><th>Rechnung</th><th>Limit-Hinweis</th><th>Relativ</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_static_manager_table(managers):
    if not managers:
        return '<p class="muted">Keine Managerdaten verfügbar.</p>'

    rows = []
    for manager in managers:
        aggression = manager.get("aggressionScore")
        aggression_text = "-" if aggression is None else f"{round(aggression)}/100"
        rows.append(f"""
            <tr>
              <td><strong>{escape(clean_value(manager.get("name"), "-"))}</strong></td>
              <td>{html_plus_money(manager.get("avgOverpay"))}</td>
              <td>{escape(aggression_text)}</td>
              <td>{escape(clean_value(manager.get("archetype"), "-"))}</td>
              <td>{html_money(manager.get("availableBudget"))}</td>
              <td>{html_money(manager.get("teamValue"))}</td>
            </tr>
        """)

    return (
        "<table>"
        "<thead><tr><th>Manager</th><th>Ø Overpay</th><th>Aggro</th><th>Typ</th><th>Kaufkraft</th><th>Kaderwert</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_static_purchase_table(purchases):
    if not purchases:
        return '<p class="muted">Keine Kaufhistorie der Mitmanager verfügbar.</p>'

    return (
        '<div class="tableScroll"><table>'
        '<thead><tr><th>Datum</th><th>Spieler</th><th>Pos</th><th>Kaufpreis</th><th>MW bei Kauf</th><th>Tats. Overpay</th><th>Overpay %</th><th>Segment</th><th>Form</th><th>Klasse</th></tr></thead>'
        f'<tbody>{render_static_purchase_rows(purchases)}</tbody></table></div>'
    )


def render_static_purchase_rows(purchases):
    rows = []
    current_manager = None
    for item in purchases:
        manager = clean_value(item.get("manager"), "-")
        if manager != current_manager:
            rows.append(f'<tr class="groupRow"><td colspan="10">{escape(manager)}</td></tr>')
            current_manager = manager
        rows.append(f"""
            <tr>
              <td>{escape(clean_value(item.get("date"), "-"))}</td>
              <td>{escape(clean_value(item.get("player"), "-"))}</td>
              <td>{escape(clean_value(item.get("position"), "-"))}</td>
              <td>{html_money(item.get("price"))}</td>
              <td>{html_money(item.get("marketValue"))}</td>
              <td class="{signed_class(item.get("overpay"))}">{html_signed_money(item.get("overpay"))}</td>
              <td class="{signed_class(item.get("overpay"))}">{html_pct(item.get("overpayPct"))}</td>
              <td>{escape(clean_value(item.get("marketValueBucket"), "-"))}</td>
              <td>{escape(clean_value(item.get("momentumBucket"), "-"))}</td>
              <td>{escape(clean_value(item.get("qualityBucket"), "-"))}</td>
            </tr>
        """)
    return "".join(rows)


def html_money(value):
    value = number_value(value)
    if value is None:
        return "-"
    return f"{value:,.0f}".replace(",", ".") + " €"


def html_plus_money(value):
    value = number_value(value)
    if value is None:
        return "-"
    return "+" + html_money(value)


def html_signed_money(value):
    value = number_value(value)
    if value is None:
        return "-"
    prefix = "+" if value > 0 else ""
    return prefix + html_money(value)


def html_pct(value):
    value = number_value(value)
    if value is None:
        return "-"
    return f"{value:.1f}".replace(".", ",") + "%"


def signed_class(value):
    value = number_value(value)
    if value is None:
        return ""
    if value < 0:
        return "neg"
    if value > 0:
        return "pos"
    return ""


def pressure_class(value):
    if value == "Hoch":
        return "high"
    if value == "Mittel":
        return "mid"
    if value == "Niedrig":
        return "low"
    return ""


def status_class(value):
    if value == "Fit":
        return "low"
    if value in {"Angeschlagen", "Reha", "Gelbsperre"}:
        return "mid"
    if value and value != "-":
        return "high"
    return ""


def gap_class(value):
    value = number_value(value)
    if value is None:
        return ""
    if value >= 0:
        return "low"
    if value >= -500_000:
        return "mid"
    return "high"


def initials(name):
    parts = str(name or "?").split()
    return "".join(part[0] for part in parts[:2]).upper() or "?"


def static_formula(item):
    explain = item.get("explain") or {}
    if not explain.get("base"):
        return "-"
    return (
        f"{html_money(explain.get('base'))} x Qualität {static_factor(explain.get('quality_factor'))} "
        f"x Muster {static_factor(explain.get('pattern_factor'))} "
        f"x Eskalation {static_factor(explain.get('escalation_factor'))}"
    )


def static_formula_title(item):
    explain = item.get("explain") or {}
    if not explain.get("base"):
        return ""
    return "\n".join([
        f"Basis: {html_money(explain.get('base'))}",
        f"Segment: {clean_value(explain.get('bucket'), '-')}",
        f"Manager Ø: {html_money(explain.get('manager_avg'))}",
        f"Manager Segment: {html_money(explain.get('manager_segment'))}",
        f"Liga Ø: {html_money(explain.get('league_avg'))}",
        f"Liga Segment: {html_money(explain.get('league_segment'))}",
        f"Position {clean_value(explain.get('position_key'), '-')}: {static_factor(explain.get('position_factor'))}",
        f"Trend {clean_value(explain.get('momentum_key'), '-')}: {static_factor(explain.get('momentum_factor'))}",
        f"Klasse {clean_value(explain.get('quality_key'), '-')}: {static_factor(explain.get('class_factor'))}",
    ])


def static_factor(value):
    value = number_value(value)
    if value is None:
        return "-"
    return f"x{value:.2f}"


def clean_value(value, default=None):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


def number_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def position_label(value):
    labels = {1: "TW", 2: "ABW", 3: "MIT", 4: "ST", "1": "TW", "2": "ABW", "3": "MIT", "4": "ST"}
    return labels.get(value, labels.get(str(value), "-"))
