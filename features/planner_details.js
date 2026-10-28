'use strict';
(() => {
  const planner = window.KICKBASE_PLANNER_VIEW;
  if (!planner) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const finite = value => value != null && value !== '' && Number.isFinite(Number(value));
  const number = (value, decimals = 0) => finite(value) ? Number(value).toLocaleString('de-DE', {maximumFractionDigits: decimals}) : '–';
  const money = value => finite(value) ? number(value) + ' €' : '–';
  const signed = value => finite(value) ? (Number(value) >= 0 ? '+' : '') + money(value) : '–';
  const tone = value => !finite(value) ? '' : Number(value) >= 0 ? 'green' : 'red';
  const detailCache = new Map(), marketCache = new Map(), teamCache = new Map();
  const ttl = 5 * 60 * 1000;
  async function request(path) {
    const response = await fetch('./api/' + path, {cache: 'no-store'});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Daten derzeit nicht abrufbar.');
    return payload;
  }
  function cached(cache, key, path) {
    const entry = cache.get(key);
    if (entry && Date.now() - entry.time < ttl) return entry.promise;
    const item = {time: Date.now(), promise: request(path)};
    cache.set(key, item);
    item.promise.catch(() => { if (cache.get(key) === item) cache.delete(key); });
    return item.promise;
  }
  const details = id => cached(detailCache, id, 'player-details/' + encodeURIComponent(id));
  const market = id => cached(marketCache, id, 'player-market-history/' + encodeURIComponent(id) + '?limit=365');

  function updateCandidate(player, fixtures, error = false) {
    for (const target of document.querySelectorAll('[data-fixtures-id]')) {
      if (target.dataset.fixturesId !== player.id) continue;
      target.innerHTML = '<b>Nächste Gegner</b>' + (fixtures.length ? planner.nextOpponents(fixtures) :
        '<span class="meta">' + (error ? 'Gegnerdaten derzeit nicht abrufbar.' : 'Keine kommenden Gegner verfügbar.') + '</span>');
    }
  }
  async function loadCandidates(players) {
    // One schedule per team, at most two outstanding requests. Closing the picker
    // stops new work; successful requests are reused when it is opened again.
    const groups = new Map();
    for (const player of players) {
      const key = player.teamId || player.id;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(player);
    }
    const queue = [...groups.entries()];
    async function worker() {
      while (queue.length && document.getElementById('candidate-dialog').open) {
        const [key, group] = queue.shift();
        const known = group.find(p => Array.isArray(p.fixtures) && p.fixtures.length >= 3);
        if (known) { group.forEach(p => updateCandidate(p, known.fixtures)); continue; }
        let entry = teamCache.get(key);
        if (!entry || Date.now() - entry.time >= ttl) {
          entry = {time: Date.now(), promise: details(group[0].id).then(data => Array.isArray(data.fixtures) ? data.fixtures : [])};
          teamCache.set(key, entry);
        }
        try {
          const fixtures = await entry.promise;
          group.forEach(p => updateCandidate(p, fixtures));
        } catch {
          if (teamCache.get(key) === entry) teamCache.delete(key);
          group.forEach(p => updateCandidate(p, p.fixtures || [], true));
        }
      }
    }
    await Promise.all([worker(), worker()]);
  }

  const dialog = document.createElement('dialog');
  dialog.id = 'player-details-dialog';
  dialog.className = 'player-details-dialog';
  dialog.setAttribute('aria-labelledby', 'player-details-title');
  dialog.innerHTML = '<header class="pd-heading"><span>Spielerdetails</span><button type="button" data-close-details aria-label="Spielerdetails schließen">×</button></header><div id="player-details-body"></div>';
  document.body.appendChild(dialog);
  const body = dialog.querySelector('#player-details-body');
  let generation = 0, current = null, marketDays = 30, performanceWindow = 8;
  function close() { generation++; dialog.close(); current = null; }
  dialog.querySelector('[data-close-details]').onclick = close;
  dialog.addEventListener('cancel', () => { generation++; current = null; });
  dialog.addEventListener('click', event => { if (event.target === dialog) close(); });

  function fixtureTiles(fixtures) {
    const games = Array.isArray(fixtures) ? fixtures.slice(0, 3) : [];
    return games.length ? '<div class="pd-fixtures">' + games.map(f => '<article><small>' + esc(f.venue || 'Spielort offen') +
      '<b class="pd-rank">' + (finite(f.rank) ? 'Pl. ' + number(f.rank) : 'Pl. –') + '</b></small><strong>' + esc(f.opponent || 'Gegner offen') +
      '</strong><small>' + esc(f.date || 'Termin offen') + '</small></article>').join('') + '</div>' : '<p class="pd-empty">Keine kommenden Gegner verfügbar.</p>';
  }
  function performanceChart(rows) {
    const games = rows.filter(game => finite(game.points));
    if (!games.length) return '<p class="pd-empty">Noch keine Leistungsdaten verfügbar.</p>';
    const max = Math.max(100, ...games.map(g => Number(g.points))), min = Math.min(0, ...games.map(g => Number(g.points)));
    const width = Math.max(640, games.length * 64), height = 252, top = 28, bottom = 184;
    const y = value => top + (max - value) / (max - min || 1) * (bottom - top);
    const baseline = y(0), cell = (width - 44) / games.length;
    return '<div class="pd-chart-scroll"><svg class="pd-performance" viewBox="0 0 ' + width + ' ' + height + '" style="min-width:' + Math.min(width, games.length * 48) + 'px" role="group" aria-label="Punkte je erfasstem Spiel, chronologisch">' +
      [0, max / 2, max].map(value => '<line x1="28" x2="' + (width - 10) + '" y1="' + y(value) + '" y2="' + y(value) + '" class="pd-grid"/>').join('') +
      games.map((game, i) => {
        const points = Number(game.points), x = 30 + i * cell, barY = Math.min(y(points), baseline), barHeight = Math.max(2, Math.abs(y(points) - baseline));
        const title = (game.date || 'Datum unbekannt') + ' · ' + (game.opponent || 'Gegner unbekannt') + ' · ' + points + ' Punkte · ' + number(game.minutes) + ' Min. · Tore ' + number(game.goals) + ' · Vorlagen ' + number(game.assists);
        return '<g role="button" tabindex="0" aria-label="' + esc(title) + '" data-game-summary="' + esc(title) + '"><title>' + esc(title) + '</title><rect x="' + x + '" y="' + barY + '" width="' + (cell * .65) + '" height="' + barHeight + '" rx="3" fill="' + (points >= 100 ? '#24c997' : points >= 0 ? '#f6bd37' : '#f35f67') + '"/>' +
          '<text x="' + (x + cell * .325) + '" y="' + Math.max(14, barY - 7) + '" text-anchor="middle" class="pd-point-label">' + number(points) + '</text>' +
          '<text x="' + (x + cell * .325) + '" y="203" text-anchor="middle">' + esc(game.date || '') + '</text>' +
          '<text x="' + (x + cell * .325) + '" y="220" text-anchor="middle">' + esc((game.opponent || '–').slice(0, 11)) + '</text>' +
          '<text x="' + (x + cell * .325) + '" y="238" text-anchor="middle">' + number(game.minutes) + '′</text></g>';
      }).join('') + '</svg></div>';
  }
  function marketChart(changes) {
    const all = changes.filter(row => finite(row.marketValue) && /^\d{4}-\d{2}-\d{2}$/.test(row.date)).sort((a, b) => a.date.localeCompare(b.date));
    if (!all.length) return '<p class="pd-empty">Keine Marktwerthistorie verfügbar.</p>';
    const lastDay = Date.parse(all[all.length - 1].date + 'T00:00:00Z');
    const rows = all.filter(row => Date.parse(row.date + 'T00:00:00Z') >= lastDay - (marketDays - 1) * 86400000);
    const low = Math.min(...rows.map(row => Number(row.marketValue))), high = Math.max(...rows.map(row => Number(row.marketValue)));
    const spread = high - low || Math.max(1000, high * .01);
    const firstDay = Date.parse(rows[0].date + 'T00:00:00Z');
    const width = window.matchMedia('(max-width:699px)').matches ? 460 : 720, right = width - 30;
    const x = row => 74 + (Date.parse(row.date + 'T00:00:00Z') - firstDay) / (lastDay - firstDay || 1) * (right - 74);
    const y = row => 188 - (Number(row.marketValue) - low) / spread * 150;
    const change = Number(rows[rows.length - 1].marketValue) - Number(rows[0].marketValue);
    return '<p class="pd-chart-note ' + tone(change) + '">' + signed(change) + ' im dargestellten Zeitraum</p><svg class="pd-market-chart" viewBox="0 0 ' + width + ' 228" role="img" aria-label="Marktwertverlauf für ' + marketDays + ' Tage">' +
      [0, .5, 1].map(f => '<line class="pd-grid" x1="74" x2="' + right + '" y1="' + (188 - f * 150) + '" y2="' + (188 - f * 150) + '"/><text x="66" y="' + (192 - f * 150) + '" text-anchor="end">' + number((low + f * spread) / 1e6, 2) + ' Mio.</text>').join('') +
      '<polyline points="' + rows.map(row => x(row) + ',' + y(row)).join(' ') + '" fill="none" stroke="#24c997" stroke-width="3"/>' +
      rows.map(row => '<circle cx="' + x(row) + '" cy="' + y(row) + '" r="3" fill="#24c997"><title>' + esc(row.date) + ': ' + money(row.marketValue) + '</title></circle>').join('') +
      '<text x="74" y="217">' + esc(rows[0].date) + '</text><text x="' + right + '" y="217" text-anchor="end">' + esc(rows[rows.length - 1].date) + '</text></svg>';
  }
  function metric(label, value, detail = '') {
    return '<article class="pd-metric"><small>' + esc(label) + '</small><strong>' + esc(value) + '</strong>' + (detail ? '<small>' + esc(detail) + '</small>' : '') + '</article>';
  }
  function paint() {
    if (!current) return;
    const {player: p, data, changes, loading, detailError, marketError} = current;
    const probability = planner.probability(p.li), fixtures = data.fixtures || p.fixtures || [];
    const performance = Array.isArray(data.performance) ? data.performance : [...(data.history || p.history || [])].reverse();
    const visiblePerformance = performanceWindow ? performance.slice(-performanceWindow) : performance;
    const average = data.season ?? p.season, mv = p.mv;
    const probabilityLabel = '<span class="pd-prob ' + probability.tone + '"><b>' + probability.icon + '</b> ' + esc(probability.title) + '</span>';
    body.innerHTML = '<div class="pd-layout"><aside class="pd-profile"><section class="pd-panel pd-identity">' +
      '<div class="pd-portrait">' + (p.teamImage ? '<img class="pd-crest" src="' + esc(p.teamImage) + '" alt="">' : '') +
      (p.image ? '<img class="pd-player-image" src="' + esc(p.image) + '" alt="' + esc(p.name) + '">' : '<span class="pd-photo-placeholder">Kein Spielerbild</span>') + '</div>' +
      '<small>' + esc(p.team || 'Verein unbekannt') + ' · ' + ({1: 'Torwart', 2: 'Abwehr', 3: 'Mittelfeld', 4: 'Angriff'}[p.position] || '') + '</small>' +
      '<h2 id="player-details-title">' + esc(p.name) + '</h2><p class="pd-status">' + esc(p.status || 'Status unbekannt') + '</p>' + probabilityLabel + '</section>' +
      '<section class="pd-panel"><h3>Nächste Gegner</h3>' + fixtureTiles(fixtures) + '</section></aside>' +
      '<div class="pd-main"><section class="pd-panel"><div class="pd-section-head"><h3>Performance</h3><span>' + esc(data.seasonLabel || 'Erfasste Spiele') + '</span></div>' +
      '<div class="pd-controls">' + [[8, 'Letzte 8'], [0, 'Saison']].map(([value, label]) => '<button type="button" data-performance-window="' + value + '" aria-pressed="' + (performanceWindow === value) + '">' + label + '</button>').join('') + '</div>' + performanceChart(visiblePerformance) +
      '<p id="pd-game-summary" class="pd-chart-note" aria-live="polite">Punkte je Spiel · Minuten unter den Balken · Balken für Spieldetails antippen</p></section>' +
      '<section class="pd-panel"><div class="pd-section-head"><h3>Marktwertentwicklung</h3><span>' + money(mv) + '</span></div><div class="pd-controls">' +
      [7, 14, 30, 90, 180, 365].map(days => '<button type="button" data-market-days="' + days + '" aria-pressed="' + (marketDays === days) + '">' + (days === 365 ? '1 Jahr' : days + 'T') + '</button>').join('') + '</div>' + marketChart(changes) +
      (marketError ? '<p class="pd-error">Marktwerthistorie derzeit nicht abrufbar. Erneutes Öffnen versucht es erneut.</p>' : '') + '</section></div>' +
      '<aside class="pd-side"><section class="pd-metrics">' + metric('Gesamtpunkte', number(data.totalPoints ?? p.totalPoints)) + metric('Ø Punkte', number(average, 1)) +
      metric('Ø letzte 3', number(data.l3 ?? p.l3, 1)) + metric('Minuten gesamt', number(data.minutes)) +
      metric('Tore / Vorlagen', number(data.goals) + ' / ' + number(data.assists)) + metric('Karten', data.cards ?? '–') +
      metric('Marktwert', money(mv)) + metric('Punkte / Mio. €', finite(average) && finite(mv) && mv > 0 ? number(average / (mv / 1e6), 1) : '–') +
      metric('Erw. 1T', signed(p.change)) + metric('Gewinn / Verlust', signed(p.profitLoss)) + '</section>' +
      '<section class="pd-panel"><h3>Entwicklung · letzte 7 Tage</h3><div class="pd-daily">' + (changes.length ? [...changes].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 7).map(row =>
        '<div><span>' + esc(row.date) + '</span><strong class="' + tone(row.change) + '">' + signed(row.change) + '</strong><small class="' + tone(row.change) + '">' + (finite(row.percent) ? (row.percent >= 0 ? '+' : '') + number(row.percent, 2) + ' %' : '–') + '</small></div>').join('') : '<p class="pd-empty">Keine Tagesänderungen verfügbar.</p>') + '</div></section></aside></div>' +
      '<p class="pd-data-status" role="status">' + (loading ? 'Live-Daten werden geladen …' : detailError ? 'Live-Spielerdetails derzeit nicht abrufbar. Verfügbare Reportdaten werden angezeigt.' : 'Verfügbare Kickbase-Daten · fehlende Werte: –') + '</p>';
  }
  async function open(id) {
    const player = planner.getPlayer(id);
    if (!player) return;
    const version = ++generation;
    marketDays = 30;
    performanceWindow = 8;
    current = {player, data: {}, changes: [], loading: true};
    paint();
    if (!dialog.open) dialog.showModal();
    // Keep the selected lineup intact; all detail requests are read-only.
    await Promise.all([
      details(id).then(data => { if (generation === version && current) { current.data = data; paint(); } })
        .catch(() => { if (generation === version && current) { current.detailError = true; paint(); } }),
      market(id).then(data => { if (generation === version && current) { current.changes = Array.isArray(data.changes) ? data.changes : []; paint(); } })
        .catch(() => { if (generation === version && current) { current.marketError = true; paint(); } }),
    ]);
    if (generation === version && current) { current.loading = false; paint(); }
  }
  dialog.addEventListener('click', event => {
    const days = event.target.closest('[data-market-days]'), windowButton = event.target.closest('[data-performance-window]');
    const game = event.target.closest('[data-game-summary]');
    if (game) dialog.querySelector('#pd-game-summary').textContent = game.dataset.gameSummary;
    if (days) { marketDays = Number(days.dataset.marketDays); paint(); }
    if (windowButton) { performanceWindow = Number(windowButton.dataset.performanceWindow); paint(); }
  });
  dialog.addEventListener('keydown', event => {
    const game = event.target.closest('[data-game-summary]');
    if (game && ['Enter', ' '].includes(event.key)) { event.preventDefault(); game.dispatchEvent(new MouseEvent('click', {bubbles: true})); }
  });
  document.addEventListener('click', event => {
    const target = event.target.closest('[data-player-details]');
    if (!target) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    open(target.dataset.playerDetails);
  }, true);
  document.addEventListener('keydown', event => {
    if (!['Enter', ' '].includes(event.key)) return;
    const detail = event.target.closest('[data-player-details]');
    const candidate = event.target.closest('[data-candidate]');
    if (detail || candidate) { event.preventDefault(); event.target.click(); }
  });
  window.KICKBASE_PLAYER_DETAILS = {loadCandidates};
})();
