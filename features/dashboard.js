'use strict';
(() => {
  const data = JSON.parse(document.getElementById('data').textContent || '{}');
  const settings = window.KICKBASE_DASHBOARD || {};
  const $ = id => document.getElementById(id);
  const apiPath = path => path.replace(/^\//, '');
  const euros = value => new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(Number(value)||0);
  const signed = value => { const n=Number(value)||0; return (n>0?'+':'')+euros(n); };
  const number = value => Number.isFinite(Number(value)) ? Number(value) : null;
  const field = (player,...names) => { for(const name of names){if(player && player[name] !== undefined && player[name] !== null && player[name] !== '') return player[name];} return null; };
  const players = Array.isArray(data.players) ? data.players : [];
  const market = (Array.isArray(data.marketPlayers) ? data.marketPlayers : []).filter(p => !p.owned);
  const TRADING_THRESHOLD = 100000;
  const mv = p => number(field(p,'mv','marketValue','market_value')) || 0;
  const prediction = p => number(field(p,'change','predicted_mv_target','prediction1T','predictedChange'));
  const change = p => prediction(p) ?? 0;
  const forecastText = p => prediction(p) === null ? '–' : signed(prediction(p));
  const points = p => number(field(p,'season','l3','average','avgPoints','pointsAverage','points_avg','seasonAverage'));
  const li = p => number(field(p,'li','liPercent','startingProbability'));
  const deadline = p => field(p,'expiresAt','expires_at','expiry','expiration');
  const lastMarketChange = p => number(field(p,'lastMvChange','last_market_change','latestMarketChange'));
  const image = p => field(p,'image','imageUrl','profileImage') || '';
  const club = p => {
    const value = field(p,'team','club','teamName');
    return value && value !== 'Unbekannt' ? value : 'Verein nicht geladen';
  };
  const position = p => ({1:'TW',2:'ABW',3:'MIT',4:'ANG'}[Number(field(p,'position','pos'))] || '–');
  const name = p => field(p,'name','playerName') || 'Unbekannt';
  const cls = value => value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';
  const avatar = p => image(p) ? '<img class="avatar" src="'+escapeHtml(image(p))+'" alt="" loading="lazy">' : '<span class="avatar"></span>';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const playerLabel = p => '<div class="player">'+avatar(p)+'<div><div class="name">'+escapeHtml(name(p))+'</div><div class="sub">'+escapeHtml(club(p))+' · '+escapeHtml(position(p))+'</div></div></div>';
  const timeValue = value => { if (!value) return Infinity; if (typeof value === 'string' && Number.isNaN(Number(value))) { const parsed = Date.parse(value); return Number.isNaN(parsed) ? Infinity : parsed; } const numeric = Number(value); return numeric > 1e12 ? numeric : numeric * 1000; };
  const formatTime = value => { const stamp=timeValue(value); if(!Number.isFinite(stamp))return '–'; return new Date(stamp).toLocaleString('de-DE',{timeZone:'Europe/Berlin',dateStyle:'short',timeStyle:'short'});};

  function renderMetrics(){
    const budget=number(data.budget) ?? number(data.availableBudget) ?? number(data.cash);
    const rosterValue=players.reduce((sum,p)=>sum+mv(p),0);
    const adjustedRosterValue=rosterValue+Math.min(budget ?? 0,0);
    const availableForecasts=players.map(prediction).filter(value=>value!==null);
    const rosterChange=availableForecasts.reduce((sum,value)=>sum+value,0);
    const realisedChanges=players.map(lastMarketChange).filter(value=>value!==null);
    const realisedChange=realisedChanges.reduce((sum,value)=>sum+value,0);
    const buyingPower=number(data.buyingPower);
    const openBidTotal=number(data.openBidTotal) || 0;
    $('metric-budget').textContent=budget===null?'–':euros(budget);$('metric-budget').className=cls(budget||0);
    $('metric-budget-note').textContent=buyingPower===null?'Kaufkraft wird geladen':'Kaufkraft nach offenen Geboten: '+signed(buyingPower)+(openBidTotal?' · Gebote '+euros(openBidTotal):'');
    $('metric-budget-note').className=buyingPower===null?'':' '+cls(buyingPower);
    $('metric-roster-value').textContent=euros(rosterValue);$('metric-roster-count').textContent=(budget!==null && budget<0?'Bereinigt: '+euros(adjustedRosterValue)+' · ':'')+players.length+'/16 Spieler';
    $('metric-roster-change').textContent=availableForecasts.length ? signed(rosterChange) : '–';
    $('metric-roster-change').className=availableForecasts.length ? cls(rosterChange) : 'neutral';
    $('metric-roster-change-note').textContent=realisedChanges.length ? 'Letztes MW-Update: '+signed(realisedChange)+' · '+realisedChanges.length+'/'+players.length+' Spieler' : 'Letztes MW-Update wird geladen';
    $('metric-roster-change-note').className=realisedChanges.length ? cls(realisedChange) : 'neutral';
    $('market-count').textContent=market.length+' Angebote';
  }
  function renderTopChances(){
    const nextUpdate=nextMarketUpdate();
    const chosen=[...market]
      .filter(p=>prediction(p)!==null && prediction(p)>=TRADING_THRESHOLD && timeValue(deadline(p))<nextUpdate)
      .sort((a,b)=>change(b)-change(a))
      .slice(0,6);
    $('top-chances').innerHTML=chosen.length?chosen.map(p=>'<details class="chance market-history-player" data-player-id="'+escapeHtml(p.id)+'"><summary><div class="chance-top">'+playerLabel(p)+'<span class="tag">'+escapeHtml(position(p))+'</span></div><div class="chance-change"><span>Erw. MW in 1T</span><strong class="positive">'+forecastText(p)+'</strong></div><div class="chance-details"><span>MW '+euros(mv(p))+'</span><span>Ablauf '+escapeHtml(formatTime(deadline(p)))+'</span></div></summary><div class="player-history"><p class="empty">Aufklappen lädt die Tagesänderungen.</p></div></details>').join(''):'<p class="empty">Keine passende Chance vor dem nächsten MW-Update.</p>';
    document.querySelectorAll('.market-history-player').forEach(details=>details.addEventListener('toggle',()=>{if(details.open)loadPlayerHistory(details);}));
  }
  const historyCache=new Map();
  const berlinDay=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin'}).format(new Date());
  function historyLabel(date){
    const today=new Date(berlinDay()+'T12:00:00Z');
    const target=new Date(date+'T12:00:00Z');
    const diff=Math.round((today-target)/86400000);
    if(diff===0)return 'Heute';
    if(diff===1)return 'Gestern';
    if(diff===2)return 'Vor 2 Tagen';
    if(diff===3)return 'Vor 3 Tagen';
    return target.toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'});
  }
  function historyMarkup(entries){
    if(!entries.length)return '<p class="empty">Keine täglichen Marktwertänderungen verfügbar.</p>';
    const maximum=Math.max(...entries.map(entry=>Math.abs(Number(entry.change)||0)),1);
    return '<div class="daily-changes">'+entries.map(entry=>{
      const value=Number(entry.change)||0;
      const width=Math.max(3,Math.round(Math.abs(value)/maximum*100));
      const percent=number(entry.percent);
      return '<div class="daily-change"><div class="daily-change-head"><span>'+escapeHtml(historyLabel(entry.date))+'</span><strong class="'+cls(value)+'">'+signed(value)+(percent===null?'':' <small>('+percent.toLocaleString('de-DE',{maximumFractionDigits:1,signDisplay:'always'})+' %)</small>')+'</strong></div><div class="daily-bar"><span class="'+cls(value)+'" style="width:'+width+'%"></span></div></div>';
    }).join('')+'</div>';
  }
  async function loadPlayerHistory(details){
    const playerId=details.dataset.playerId;
    const target=details.querySelector('.player-history');
    if(historyCache.has(playerId)){target.innerHTML=historyMarkup(historyCache.get(playerId));return;}
    target.innerHTML='<p class="empty">Marktwerthistorie wird von Kickbase geladen …</p>';
    try{
      const response=await fetch(apiPath('/api/player-market-history/'+encodeURIComponent(playerId)),{cache:'no-store'});
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.error||'Nicht verfügbar');
      const entries=Array.isArray(payload.changes)?payload.changes:[];
      historyCache.set(playerId,entries);
      target.innerHTML=historyMarkup(entries);
    }catch(error){target.innerHTML='<p class="empty">Marktwerthistorie derzeit nicht verfügbar.</p>';}
  }
  function renderRoster(){
    const chosen=[...players].sort((a,b)=>change(b)-change(a));
    $('roster-count').textContent=chosen.length+' Spieler';
    $('roster-movers').innerHTML=chosen.length?chosen.map(p=>'<details class="roster-player" data-player-id="'+escapeHtml(p.id)+'"><summary><div class="list-row">'+playerLabel(p)+'<div class="roster-values"><span class="sub">Erw. 1T</span><strong class="list-value '+cls(change(p))+'">'+forecastText(p)+'</strong></div></div></summary><div class="player-history"><p class="empty">Aufklappen lädt die Tagesänderungen.</p></div></details>').join(''):'<p class="empty">Noch kein Kader geladen.</p>';
    document.querySelectorAll('.roster-player').forEach(details=>details.addEventListener('toggle',()=>{if(details.open)loadPlayerHistory(details);}));
  }
  function nextMarketUpdate(){
    const update=new Date(); update.setHours(22,0,0,0);
    if(update.getTime()<=Date.now()) update.setDate(update.getDate()+1);
    return update.getTime();
  }
  function renderRisks(){
    const update=nextMarketUpdate();
    const nightEnd=update+11*60*60*1000;
    const risky=[...players].filter(p=>prediction(p)!==null && change(p)<0).sort((a,b)=>change(a)-change(b)).slice(0,3);
    const beforeUpdate=[...market].filter(p=>prediction(p)!==null && change(p)>=TRADING_THRESHOLD && timeValue(deadline(p))<=update).sort((a,b)=>change(b)-change(a)).slice(0,2);
    const overnight=[...market].filter(p=>prediction(p)!==null && change(p)>=TRADING_THRESHOLD && timeValue(deadline(p))>update && timeValue(deadline(p))<=nightEnd).sort((a,b)=>change(b)-change(a)).slice(0,2);
    const rows=[];
    risky.forEach(p=>rows.push('<div class="list-row">'+playerLabel(p)+'<div class="list-value negative"><span class="risk-dot red"></span>Drohender MW-Verlust '+forecastText(p)+'</div></div>'));
    beforeUpdate.forEach(p=>rows.push('<div class="list-row">'+playerLabel(p)+'<div class="list-value positive"><span class="risk-dot green"></span>Top-Chance vor 22 Uhr '+forecastText(p)+'</div></div>'));
    overnight.forEach(p=>rows.push('<div class="list-row">'+playerLabel(p)+'<div class="list-value neutral"><span class="risk-dot"></span>Nachtgebot 22–09 Uhr '+forecastText(p)+'</div></div>'));
    $('timing-risks').innerHTML=rows.length?rows.join(''):'<p class="empty">Kein unmittelbarer Handlungsbedarf erkannt.</p>';
  }
  async function renderValueHistory(){
    try{
      const response=await fetch(apiPath('/api/squad-value-history'),{cache:'no-store'});
      const history=await response.json();
      const series=Array.isArray(history.series)?history.series:[];
      $('history-note').textContent=history.note||'';
      if(series.length<2){$('value-chart').innerHTML='<div class="chart-empty">Noch nicht genügend historische Daten verfügbar.</div>';return;}
      const width=1000, height=190, pad={left:8,right:8,top:16,bottom:24};
      const values=series.map(item=>Number(item.value));
      const low=Math.min(...values), high=Math.max(...values), spread=Math.max(high-low,1);
      const x=index=>pad.left+(width-pad.left-pad.right)*index/(series.length-1);
      const y=value=>pad.top+(height-pad.top-pad.bottom)*(1-(value-low)/spread);
      const line=series.map((item,index)=>x(index).toFixed(1)+','+y(Number(item.value)).toFixed(1)).join(' ');
      const area=line+' '+x(series.length-1).toFixed(1)+','+(height-pad.bottom)+' '+x(0).toFixed(1)+','+(height-pad.bottom);
      const first=series[0], last=series[series.length-1], delta=Number(last.value)-Number(first.value);
      const labelDate=value=>new Date(value+'T12:00:00').toLocaleDateString('de-DE',{day:'2-digit',month:'2-digit'});
      $('history-summary').textContent=signed(delta)+' seit '+labelDate(first.date);
      $('history-summary').className='panel-meta '+cls(delta);
      $('value-chart').innerHTML='<svg viewBox="0 0 '+width+' '+height+'" preserveAspectRatio="none" aria-hidden="true"><line class="chart-grid" x1="0" x2="'+width+'" y1="'+(height-pad.bottom)+'" y2="'+(height-pad.bottom)+'"/><polygon class="chart-area" points="'+area+'"/><polyline class="chart-line" points="'+line+'"/><text class="chart-label" x="'+pad.left+'" y="'+(height-4)+'">'+labelDate(first.date)+'</text><text class="chart-label" text-anchor="end" x="'+(width-pad.right)+'" y="'+(height-4)+'">'+labelDate(last.date)+'</text><text class="chart-label" text-anchor="end" x="'+(width-pad.right)+'" y="12">'+euros(last.value)+'</text></svg>';
    }catch(error){$('value-chart').innerHTML='<div class="chart-empty">Kaderwertverlauf derzeit nicht verfügbar.</div>';}
  }
  function sortedMarket(){
    const mode=$('market-sort').value;
    return [...market].sort((a,b)=>{
      if(mode==='expiry')return timeValue(deadline(a))-timeValue(deadline(b));
      if(mode==='mv')return mv(b)-mv(a);
      if(mode==='points')return (points(b)||-Infinity)-(points(a)||-Infinity);
      return change(b)-change(a);
    });
  }
  function renderTable(){
    $('market-table').innerHTML=sortedMarket().slice(0,50).map(p=>'<tr><td><div class="table-player">'+avatar(p)+'<div><div class="name">'+escapeHtml(name(p))+'</div><div class="sub">'+escapeHtml(club(p))+'</div></div></div></td><td>'+escapeHtml(position(p))+'</td><td>'+euros(mv(p))+'</td><td class="'+cls(change(p))+'">'+signed(change(p))+'</td><td>'+((li(p)===null)?'–':Math.round(li(p))+' %')+'</td><td>'+escapeHtml(formatTime(deadline(p)))+'</td></tr>').join('')||'<tr><td colspan="6" class="empty">Keine Marktangebote im aktuellen Stand.</td></tr>';
  }
  function render(){renderMetrics();renderTopChances();renderRoster();renderRisks();renderTable();}
  function renderForecastStatus(){
    const forecast=data.forecast||{};
    const source=forecast.source||'noch nicht synchronisiert';
    const raw=forecast.generatedAt;
    let stamp='–';
    if(raw){
      const parsed=new Date(raw);
      if(!Number.isNaN(parsed.getTime())) stamp=parsed.toLocaleString('de-DE',{timeZone:'Europe/Berlin',dateStyle:'short',timeStyle:'short'});
    }
    $('forecast-status').textContent=raw?'Prognose: '+source+' · '+stamp:'Prognose: '+source;
  }
  $('market-sort').onchange=renderTable;
  $('live-status').textContent=settings.liveMessage||data.generated||'Reportstand geladen';
  renderForecastStatus();render();renderValueHistory();
})();