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

    payload = {
        "generatedAt": datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M"),
        "players": players,
        "managers": managers,
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
    <p class="sub">Generiert am <span id="generatedAt"></span>. Modelliert aus bisherigem Bietverhalten, Marktwert-Segmenten und Spielerklasse.</p>

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

    <section class="panel" id="playerPanel"></section>
    <section class="panel">
      <h2 style="font-size:18px;margin:0 0 10px;">Erwarteter Gegner-Overpay</h2>
      <div id="opponentTable"></div>
    </section>
    <section class="panel">
      <h2 style="font-size:18px;margin:0 0 10px;">Manager-Profil</h2>
      <div id="managerTable"></div>
    </section>
  </main>
  <script>
    const DATA = {data};
    const fmt = new Intl.NumberFormat('de-DE', {{ maximumFractionDigits: 0 }});
    const money = value => value === null || Number.isNaN(value) ? '-' : fmt.format(value) + ' €';
    const plusMoney = value => value === null || Number.isNaN(value) ? '-' : '+' + money(value);
    const signedMoney = value => value === null || Number.isNaN(value) ? '-' : (value > 0 ? '+' : '') + money(value);
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

    byId('generatedAt').textContent = DATA.generatedAt;
    byId('search').addEventListener('input', () => fillSelect());
    byId('playerSelect').addEventListener('change', renderSelected);
    fillSelect();
    renderManagers();
  </script>
</body>
</html>
"""


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
