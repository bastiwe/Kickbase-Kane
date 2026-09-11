/* Loaded only by the local server; no key is embedded in exported reports. */
'use strict';
(() => {
  const local = window.KICKBASE_ADVISOR;
  if (!local) return;
  const element = id => document.getElementById(id);
  let history = [], pending = false, lastPlan = null;
  const shell = document.createElement('section');
  shell.className = 'advisor-shell';
  shell.id = 'advisor';
  shell.hidden = true;
  shell.setAttribute('aria-label', 'KI-Ratgeber');
  shell.innerHTML = `
    <div class="advisor-head"><h2>KI-Ratgeber</h2><button id="advisor-close" aria-label="Ratgeber schließen" title="Schließen">×</button></div>
    <div class="advisor-tools"><button id="advisor-settings-open">KI-Einstellungen</button><button id="advisor-clear">Neuer Chat</button></div>
    <div id="advisor-meta" class="advisor-meta"></div>
    <div class="advisor-tools"><button data-advisor-question="Welche drei nächsten Schritte empfiehlst du für meinen aktuellen Plan?">Nächste Schritte</button><button data-advisor-question="Welche Marktspieler verstärken meine Elf? Vergleiche finanzierbare Einzeltausch-Szenarien.">Markt prüfen</button><button data-advisor-question="Wie komme ich mit meinem aktuellen Plan ins Plus, ohne die Elf unnötig zu schwächen?">Budget verbessern</button></div>
    <div id="advisor-messages" class="advisor-messages" role="log" aria-live="polite"><div class="advisor-empty">Noch keine Unterhaltung.</div></div>
    <form id="advisor-form" class="advisor-compose">
      <div id="advisor-plan-note" class="advisor-meta"></div>
      <textarea id="advisor-question" maxlength="4000" aria-label="Frage zum Kader" placeholder="Deine Frage zum Kader …" required></textarea>
      <div class="toolbar"><span id="advisor-state" class="muted"></span><button id="advisor-send" class="advisor-send" type="submit">Senden ↑</button></div>
      <div id="advisor-feedback" class="advisor-feedback" role="status"></div>
      <p class="advisor-privacy">Beim Senden gehen Frage, Chatverlauf, Spieler- und Planungsdaten an OpenAI. Websuche für Regeln und Spielernews verfügbar. API und Websuche sind kostenpflichtig. Keine Aktionen in Kickbase.</p>
    </form>`;
  document.body.append(shell);
  const settings = document.createElement('dialog');
  settings.id = 'advisor-settings';
  settings.className = 'advisor-settings';
  settings.innerHTML = `<div class="section-title"><h2>KI-Einstellungen</h2><button id="advisor-settings-close" aria-label="Einstellungen schließen">×</button></div>
    <p>Der Schlüssel bleibt im Arbeitsspeicher des lokalen Servers bis zum Beenden. Er wird nicht in die HTML-Datei oder den Chat übernommen.</p>
    <label for="advisor-memory">Dauerhaften Hinweis speichern</label><textarea id="advisor-memory" maxlength="500" placeholder="z. B. Matsima nicht verkaufen."></textarea>
    <div class="toolbar"><button id="advisor-memory-save" type="button">Hinweis merken</button><button id="advisor-memory-clear" type="button">Alle Hinweise löschen</button></div><p id="advisor-memory-status" role="status"></p>
    <form id="advisor-key-form"><label for="advisor-key">OpenAI-API-Schlüssel</label><input id="advisor-key" type="password" autocomplete="off" spellcheck="false" placeholder="sk-…" required>
    <div class="toolbar"><button type="submit">Schlüssel übernehmen</button><button id="advisor-forget-key" type="button">Schlüssel entfernen</button></div></form><p id="advisor-key-status" role="status"></p>`;
  document.body.append(settings);
  const kickSettings = document.createElement('section');
  kickSettings.innerHTML = `<h3>Kickbase-Livezugriff</h3>
    <form id="advisor-kick-form"><label for="advisor-kick-user">Kickbase-E-Mail</label><input id="advisor-kick-user" type="email" autocomplete="off" required>
    <label for="advisor-kick-pass">Kickbase-Passwort</label><input id="advisor-kick-pass" type="password" autocomplete="off" required>
    <div class="toolbar"><button type="submit">Livezugriff aktivieren</button><button id="advisor-kick-remove" type="button">Trennen</button></div></form>
    <p id="advisor-kick-status" role="status"></p>`;
  settings.append(kickSettings);
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';
  toolbar.innerHTML = '<button id="advisor-report-open">HTML-Report laden</button><button id="advisor-apply-lineup">Startelf in Kickbase übernehmen</button><button id="advisor-list-sales">Verkaufspreise berechnen</button><button id="advisor-toggle" class="advisor-toggle">KI-Ratgeber</button><input id="advisor-report-file" class="advisor-file" type="file" accept=".html,text/html">';
  document.querySelector('header').append(toolbar);

  async function request(path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 240000);
    try {
      const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Advisor-Token': local.csrf}, body: JSON.stringify(body), signal: controller.signal});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Anfrage fehlgeschlagen.');
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Die Anfrage dauerte zu lange. Bitte erneut versuchen.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  async function status() {
    try {
      const response = await fetch('/api/status');
      if (!response.ok) throw new Error();
      const result = await response.json();
      element('advisor-state').textContent = result.configured ? result.model : 'API-Schlüssel fehlt';
      element('advisor-key-status').textContent = result.configured ? 'Schlüssel im lokalen Server hinterlegt.' : 'Noch kein Schlüssel hinterlegt.';
      element('advisor-kick-status').textContent = result.liveConfigured ? 'Liveabruf vor jeder Frage aktiviert. Zugang wird beim Abruf geprüft.' : 'Nicht verbunden. Beratung nutzt den Reportstand.';
      element('advisor-meta').textContent = `${data.generated} · ${data.players.length} Kaderspieler / Gebote · ${result.marketCount} Marktangebote`;
      if (!Object.hasOwn(data, 'marketPlayers')) element('advisor-meta').textContent += ' · Älterer Report ohne vollständigen Markt';
      element('advisor-meta').textContent += result.liveConfigured ? ' · Kickbase-Liveabruf aktiv' : ' · Reportstand';
      element('advisor-memory-status').textContent = `${result.memoryCount || 0} dauerhafte Hinweise gespeichert.`;
    } catch { element('advisor-feedback').textContent = 'Lokaler Server nicht erreichbar.'; }
  }
  function open() {
    shell.hidden = false;
    document.body.classList.add('advisor-open');
    status();
  }
  element('advisor-toggle').onclick = open;
  element('advisor-close').onclick = () => {shell.hidden = true; document.body.classList.remove('advisor-open');};
  element('advisor-settings-open').onclick = () => {status(); settings.showModal();};
  element('advisor-settings-close').onclick = () => settings.close();
  element('advisor-kick-form').onsubmit = async event => {
    event.preventDefault();
    try {
      await request('/api/kickbase', {username: element('advisor-kick-user').value.trim(), password: element('advisor-kick-pass').value});
      element('advisor-kick-user').value = ''; element('advisor-kick-pass').value = '';
      await status();
    } catch (error) {element('advisor-kick-status').textContent = error.message;}
  };
  element('advisor-kick-remove').onclick = async () => {
    try {await request('/api/kickbase', {username: '', password: ''}); await status();}
    catch (error) {element('advisor-kick-status').textContent = error.message;}
  };
  element('advisor-key-form').onsubmit = async event => {
    event.preventDefault();
    const input = element('advisor-key');
    try {await request('/api/key', {key: input.value.trim()}); input.value = ''; await status(); settings.close();}
    catch (error) {element('advisor-key-status').textContent = error.message;}
  };
  element('advisor-forget-key').onclick = async () => {
    try {await request('/api/key', {key: ''}); element('advisor-key').value = ''; await status();}
    catch (error) {element('advisor-key-status').textContent = error.message;}
  };
  element('advisor-memory-save').onclick = async () => {
    const input = element('advisor-memory');
    try { await request('/api/memory', {action: 'add', note: input.value}); input.value = ''; await status(); }
    catch (error) { element('advisor-memory-status').textContent = error.message; }
  };
  element('advisor-memory-clear').onclick = async () => {
    try { await request('/api/memory', {action: 'clear'}); await status(); }
    catch (error) { element('advisor-memory-status').textContent = error.message; }
  };
  element('advisor-report-open').onclick = () => element('advisor-report-file').click();
  element('advisor-apply-lineup').onclick = async () => {
    if (state.selection.filter(Boolean).length !== 11) { element('advisor-feedback').textContent = 'Bitte zuerst genau elf Spieler aufstellen.'; return; }
    if (!confirm('Die ausgewählte Startelf in Kickbase übernehmen?')) return;
    try { const result = await request('/api/apply-lineup', {state}); const warning = result.response?.verificationWarning; element('advisor-feedback').textContent = warning ? `Startelf übernommen. Hinweis: ${warning}` : `Startelf übernommen: ${result.formation}.`; }
    catch (error) { element('advisor-feedback').textContent = error.message; }
  };
  element('advisor-list-sales').onclick = async () => {
    const candidates = players.filter(p => p.owned && state.plans[p.id]?.action === 'sell' && Number.isFinite(Number(p.mv)) && Number.isFinite(Number(p.change)));
    if (!candidates.length) { element('advisor-feedback').textContent = 'Keine Spieler mit Status „Verkaufen“ und vollständigen Werten.'; return; }
    const prices = candidates.map(p => `${p.name}: aktueller MW ${money(Number(p.mv))} + 1T ${money(Number(p.change))} → Verkaufspreis ${money(Math.round((Number(p.mv) + Number(p.change)) * 1.2))}`).join('\n');
    element('advisor-feedback').textContent = `Berechnete Verkaufspreise (noch nicht übertragen):\n${prices}`;
  };
  element('advisor-report-file').onchange = async event => {
    const file = event.target.files[0];
    if (!file) return;
    open();
    try {
      if (file.size > 1800000) throw new Error('Der Report ist zu groß (maximal 1,8 MB).');
      element('advisor-feedback').textContent = 'Report wird geladen …';
      await request('/api/report', {html: await file.text()});
      location.reload();
    } catch (error) {element('advisor-feedback').textContent = error.message;}
    event.target.value = '';
  };
  function addMessage(role, text, sources = []) {
    const container = element('advisor-messages');
    container.querySelector('.advisor-empty')?.remove();
    const article = document.createElement('article');
    article.className = 'advisor-message ' + role;
    const label = document.createElement('label');
    label.textContent = role === 'user' ? 'DU' : 'KI-RATGEBER';
    const content = document.createElement('div');
    content.textContent = text;
    article.append(label, content);
    for (const source of sources) {
      try {
        const url = new URL(source.url);
        if (url.protocol !== 'https:') continue;
        const link = document.createElement('a');
        link.href = url.href; link.textContent = source.title || url.hostname;
        link.target = '_blank'; link.rel = 'noopener noreferrer';
        const line = document.createElement('p'); line.append(link); article.append(line);
      } catch { /* Ignore invalid citation URLs. */ }
    }
    container.append(article);
    article.scrollIntoView({block: 'nearest'});
  }
  function setPending(value) {
    pending = value;
    for (const id of ['advisor-send', 'advisor-clear', 'advisor-report-open', 'advisor-question']) element(id).disabled = value;
    shell.querySelectorAll('[data-advisor-question]').forEach(button => {button.disabled = value;});
    element('advisor-send').textContent = value ? 'Analyse läuft …' : 'Senden ↑';
  }
  element('advisor-clear').onclick = () => {
    if (pending) return;
    history = []; lastPlan = null;
    element('advisor-messages').replaceChildren();
    element('advisor-plan-note').textContent = '';
    element('advisor-feedback').textContent = '';
  };
  element('advisor-form').onsubmit = async event => {
    event.preventDefault();
    if (pending) return;
    const question = element('advisor-question').value.trim();
    if (!question) return;
    const plan = JSON.parse(JSON.stringify(state));
    const signature = JSON.stringify(plan);
    setPending(true);
    element('advisor-feedback').textContent = 'Aktueller Plan wird geprüft …';
    try {
      const result = await request('/api/chat', {revision: local.revision, state: plan, message: question, history: history.slice(-12)});
      addMessage('user', question);
      addMessage('assistant', result.answer, result.sources || []);
      history.push({role: 'user', content: question}, {role: 'assistant', content: result.answer.slice(0,16000)});
      history = history.slice(-12);
      lastPlan = signature;
      element('advisor-question').value = '';
      element('advisor-feedback').textContent = 'Geprüftes Endbudget: ' + money(result.checkedPlan.endBudget) + ' · ' + result.checkedPlan.rosterSize + '/16 Spieler';
      if (result.liveData) element('advisor-feedback').textContent += ' · Live: ' + new Date(result.liveData.fetchedAt).toLocaleString('de-DE') + ' · ' + result.liveData.marketCount + ' Marktangebote. Beratung nutzt Live-Cash und Besitz; Spielfeld bleibt dein lokaler Plan.';
      element('advisor-plan-note').textContent = JSON.stringify(state) === signature ? 'Antwort bezieht sich auf den gesendeten Plan.' : 'Aufstellung inzwischen geändert. Die nächste Frage nutzt den neuen Plan.';
    } catch (error) {element('advisor-feedback').textContent = error.message;}
    finally {setPending(false);}
  };
  element('advisor-question').onkeydown = event => {
    if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); element('advisor-form').requestSubmit();}
  };
  shell.querySelectorAll('[data-advisor-question]').forEach(button => button.onclick = () => {
    element('advisor-question').value = button.dataset.advisorQuestion;
    element('advisor-question').focus();
  });
  function planChanged() {
    if (lastPlan && JSON.stringify(state) !== lastPlan) element('advisor-plan-note').textContent = 'Plan geändert. Die nächste Frage berücksichtigt deine Änderungen.';
  }
  document.addEventListener('change', planChanged);
  document.addEventListener('kickbase-plan-change', planChanged);
  if (!data.players.length) {
    open();
    element('advisor-feedback').textContent = 'Bitte zuerst einen Startelf-HTML-Report über „HTML-Report laden“ öffnen.';
  }
  if (window.KICKBASE_ADVISOR.liveMessage) {
    const liveStatus = document.createElement('p');
    liveStatus.setAttribute('role', 'status');
    liveStatus.textContent = window.KICKBASE_ADVISOR.liveMessage;
    document.querySelector('header').append(liveStatus);
  }
})();
