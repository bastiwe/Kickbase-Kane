'use strict';
(() => {
  const data = JSON.parse(document.getElementById('data').textContent || '{}');
  const settings = window.KICKBASE_DASHBOARD || {};
  const $ = id => document.getElementById(id);
  const apiPath = path => path.replace(/^\//, '');
  const euros = value => new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(Number(value)||0);
  const signed = value => { const n=Number(value)||0; return (n>0?'+':'')+euros(n); };
  const number = value => value === null || value === undefined || value === '' || typeof value === 'boolean'
    ? null : Number.isFinite(Number(value)) ? Number(value) : null;
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
  const teamImage = p => field(p,'teamImage','teamImageUrl','team_image_url','teamLogo') || '';
  const club = p => {
    const value = field(p,'team','club','teamName');
    return value && value !== 'Unbekannt' ? value : 'Verein nicht geladen';
  };
  const position = p => ({1:'TW',2:'ABW',3:'MIT',4:'ANG'}[Number(field(p,'position','pos'))] || '–');
  const name = p => field(p,'name','playerName') || 'Unbekannt';
  const cls = value => value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const avatar = p => '<span class="player-art" aria-hidden="true">'
    +(teamImage(p)?'<img class="club-crest" src="'+escapeHtml(teamImage(p))+'" alt="" loading="lazy">':'')
    +(image(p)?'<img class="player-cutout" src="'+escapeHtml(image(p))+'" alt="" loading="lazy">':'<span class="player-cutout placeholder"></span>')
    +'</span>';
  const liBadge = (p,label='LI') => {
    const value=li(p);
    const tone=value===null?'unknown':value>=85?'high':value>=45?'medium':'low';
    const text=value===null?'–':Math.round(value)+' %';
    return '<span class="li-badge '+tone+'" title="LigaInsider-Startelfwahrscheinlichkeit">'+(label?escapeHtml(label)+' ':'')+text+'</span>';
  };
  const playerLabel = (p,includeArt=true) => '<div class="player">'+(includeArt?avatar(p):'')+'<div><div class="name">'+escapeHtml(name(p))+'</div><div class="player-subline"><span class="sub">'+escapeHtml(club(p))+' · '+escapeHtml(position(p))+'</span>'+liBadge(p)+'</div></div></div>';
  const timeValue = value => { if (!value) return Infinity; if (typeof value === 'string' && Number.isNaN(Number(value))) { const parsed = Date.parse(value); return Number.isNaN(parsed) ? Infinity : parsed; } const numeric = Number(value); return numeric > 1e12 ? numeric : numeric * 1000; };
  const formatTime = value => { const stamp=timeValue(value); if(!Number.isFinite(stamp))return '–'; return new Date(stamp).toLocaleString('de-DE',{timeZone:'Europe/Berlin',dateStyle:'short',timeStyle:'short'});};
  const relativeTime = value => {
    const stamp=timeValue(value);
    if(!Number.isFinite(stamp))return 'Zeit unbekannt';
    const minutes=Math.max(0,Math.floor((Date.now()-stamp)/60000));
    if(minutes<60)return 'vor '+minutes+' '+(minutes===1?'Minute':'Minuten');
    const hours=Math.floor(minutes/60);
    if(hours<24)return 'vor '+hours+' '+(hours===1?'Stunde':'Stunden');
    const days=Math.floor(hours/24);
    return 'vor '+days+' '+(days===1?'Tag':'Tagen');
  };
  const trendArrow = p => {
    const expected=prediction(p), previous=lastMarketChange(p);
    if(expected===null || previous===null)return '';
    const direction=expected>previous ? ['↑','positive','Prognose höher als letzte MW-Änderung']
      : expected<previous ? ['↓','negative','Prognose niedriger als letzte MW-Änderung']
      : ['→','neutral','Prognose entspricht letzter MW-Änderung'];
    return '<span class="trend-arrow '+direction[1]+'" title="'+direction[2]+'" aria-label="'+direction[2]+'">'+direction[0]+'</span>';
  };
  const expiryDetails = p => {
    const stamp=timeValue(deadline(p));
    if(!Number.isFinite(stamp))return '<span class="risk-expiry">Ablauf – · Restlaufzeit –</span>';
    const hours=Math.max(0,(stamp-Date.now())/3600000).toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1});
    return '<span class="risk-expiry">Ablauf '+escapeHtml(formatTime(deadline(p)))+' · Restlaufzeit '+hours+' Std.</span>';
  };

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
    const rosterLimit=16;
    const rosterCountClass=players.length<rosterLimit?'positive':players.length===rosterLimit?'neutral':'negative';
    $('metric-roster-change-note').innerHTML=realisedChanges.length
      ? 'Letztes MW-Update: '+signed(realisedChange)+' · <span class="'+rosterCountClass+'">'+players.length+'/'+rosterLimit+' Spieler</span>'
      : '<span class="'+rosterCountClass+'">'+players.length+'/'+rosterLimit+' Spieler</span> · Letztes MW-Update wird geladen';
    $('metric-roster-change-note').className='';
    $('market-count').textContent=market.length+' Angebote';
  }
  function renderTopChances(){
    const nextUpdate=nextMarketUpdate();
    const chosen=[...market]
      .filter(p=>prediction(p)!==null && prediction(p)>=TRADING_THRESHOLD && timeValue(deadline(p))<nextUpdate)
      .sort((a,b)=>change(b)-change(a))
      .slice(0,6);
    $('top-chances').innerHTML=chosen.length?chosen.map(p=>'<details class="chance market-history-player" data-player-id="'+escapeHtml(p.id)+'"><summary>'+avatar(p)+'<div class="chance-content"><div class="chance-top">'+playerLabel(p,false)+'<span class="tag">'+escapeHtml(position(p))+'</span></div><div class="chance-change"><span>Erw. MW in 1T</span><strong class="positive">'+forecastText(p)+'</strong></div><div class="chance-details"><span>MW '+euros(mv(p))+'</span><span>Ablauf '+escapeHtml(formatTime(deadline(p)))+'</span></div></div></summary><div class="player-history"><p class="empty">Aufklappen lädt die Tagesänderungen.</p></div></details>').join(''):'<p class="empty">Keine passende Chance vor dem nächsten MW-Update.</p>';
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
    const rosterLabel=p=>{
      const profit=number(field(p,'profitLoss','profit_loss'));
      const total=number(field(p,'totalPoints','total_points','pointsTotal'));
      const average=number(field(p,'season','average','avgPoints','pointsAverage'));
      const profitText=profit===null?'G/V –':'G/V '+signed(profit);
      const pointsText=total===null?'Pkt. –':'Pkt. '+Math.round(total).toLocaleString('de-DE');
      const averageText=average===null?'Ø –':'Ø '+average.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1});
      return '<div class="player">'+avatar(p)+'<div><div class="name">'+escapeHtml(name(p))+'</div><div class="sub">'+escapeHtml(club(p))+' · '+escapeHtml(position(p))+'</div><div class="roster-statline"><span class="'+(profit===null?'':cls(profit))+'">'+profitText+'</span><span>'+pointsText+'</span><span>'+averageText+'</span></div></div></div>';
    };
    $('roster-movers').innerHTML=chosen.length?chosen.map(p=>'<details class="roster-player" data-player-id="'+escapeHtml(p.id)+'"><summary><div class="list-row">'+rosterLabel(p)+'<div class="roster-values"><span class="sub">Erw. 1T</span><strong class="list-value '+cls(change(p))+'">'+forecastText(p)+trendArrow(p)+'</strong></div></div></summary><div class="player-history"><p class="empty">Aufklappen lädt die Tagesänderungen.</p></div></details>').join(''):'<p class="empty">Noch kein Kader geladen.</p>';
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
    const riskRow=(player, tone, label, dot) =>
      '<details class="risk-player market-history-player" data-player-id="'+escapeHtml(player.id)+'"><summary><div class="list-row">'
      +playerLabel(player)+'<div class="risk-values"><span class="list-value '+tone+'"><span class="risk-dot '+dot+'"></span>'+label+' '+forecastText(player)+'</span>'+expiryDetails(player)+'</div></div></summary>'
      +'<div class="player-history"><p class="empty">Aufklappen lädt die Tagesänderungen.</p></div></details>';
    const rows=[];
    risky.forEach(p=>rows.push(riskRow(p,'negative','Drohender MW-Verlust','red')));
    beforeUpdate.forEach(p=>rows.push(riskRow(p,'positive','Top-Chance vor 22 Uhr','green')));
    overnight.forEach(p=>rows.push(riskRow(p,'neutral','Nachtgebot 22–09 Uhr','')));
    $('timing-risks').innerHTML=rows.length?rows.join(''):'<p class="empty">Kein unmittelbarer Handlungsbedarf erkannt.</p>';
    document.querySelectorAll('.risk-player').forEach(details=>details.addEventListener('toggle',()=>{if(details.open)loadPlayerHistory(details);}));
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
  async function renderManagerBudgets(){
    try{
      const response=await fetch(apiPath('/api/manager-budgets'),{cache:'no-store'});
      if(!response.ok)throw new Error('Abruf fehlgeschlagen');
      const payload=await response.json();
      const managers=Array.isArray(payload.managers)?payload.managers:[];
      $('manager-budget-note').textContent=payload.note||'';
      if(payload.cashFetchedAt||payload.generatedAt){
        const cashLive=Boolean(payload.cashFetchedAt), stamp=new Date(payload.cashFetchedAt||payload.generatedAt);
        $('manager-budget-updated').textContent=Number.isNaN(stamp.getTime())?'':((cashLive?'Eigener Cash live · ':'Stand ')+stamp.toLocaleString('de-DE',{timeZone:'Europe/Berlin',dateStyle:'short',timeStyle:'short'}));
      }
      $('manager-budgets').innerHTML=managers.length?managers.map(manager=>{
        const cash=number(manager.cash)||0, buyingPower=number(manager.buyingPower)||0;
        const basis=String(manager.basis||'').startsWith('API')?'API':'Schätzung';
        return '<article class="manager-budget-card"><div class="manager-budget-head"><span class="name">'+escapeHtml(manager.name)+'</span><span class="manager-budget-basis">'+basis+'</span></div>'
          +'<div class="manager-budget-values"><div class="manager-budget-value"><span>Cash</span><strong class="'+cls(cash)+'" title="'+escapeHtml(euros(cash))+'">'+euros(cash)+'</strong></div>'
          +'<div class="manager-budget-value"><span>Kaderwert</span><strong title="'+escapeHtml(euros(manager.squadValue))+'">'+euros(manager.squadValue)+'</strong></div>'
          +'<div class="manager-budget-value"><span>Kaufkraft</span><strong class="'+cls(buyingPower)+'" title="'+escapeHtml(euros(buyingPower))+'">'+euros(buyingPower)+'</strong></div></div></article>';
      }).join(''):'<p class="empty">Noch kein Managerbudget vorhanden. Bitte einmal einen Vollreport ausführen.</p>';
    }catch(error){
      $('manager-budget-note').textContent='Stand des letzten Vollreports';
      $('manager-budgets').innerHTML='<p class="empty">Managerbudgets derzeit nicht verfügbar.</p>';
    }
  }
  async function renderRecentTransfers(){
    const container=$('recent-transfers');
    try{
      const response=await fetch(apiPath('/api/recent-transfers'),{cache:'no-store'});
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.error||'Abruf fehlgeschlagen');
      const transfers=Array.isArray(payload.transfers)?payload.transfers.slice(0,5):[];
      const stamp=new Date(payload.fetchedAt);
      $('recent-transfers-updated').textContent=Number.isNaN(stamp.getTime())?'Live aus Kickbase':'Live · '+stamp.toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit'})+' Uhr';
      container.innerHTML=transfers.length?transfers.map(transfer=>{
        const overpay=number(transfer.overpay);
        const marketValue=number(transfer.marketValue);
        const profitLoss=number(transfer.profitLoss);
        const secondary=transfer.isKickbaseSale
          ? '<div><span>G/V des Verkäufers</span><strong class="'+(profitLoss===null?'neutral':cls(profitLoss))+'">'+(profitLoss===null?'–':signed(profitLoss))+'</strong></div>'
          : '<div><span>Overpay</span><strong class="'+(overpay===null?'neutral':overpay>0?'negative':overpay<0?'positive':'neutral')+'">'+(overpay===null?'–':signed(overpay))+'</strong></div>';
        return '<article class="recent-transfer-card">'+avatar({image:transfer.image,teamImage:transfer.teamImage})+'<div class="recent-transfer-content"><div class="recent-transfer-player">'
          +'<div class="recent-transfer-identity"><div class="name">'+escapeHtml(transfer.playerName||'Unbekannter Spieler')+'</div><div class="transfer-route"><span>'+escapeHtml(transfer.from||'Kickbase')+'</span><b aria-hidden="true">›</b><span>'+escapeHtml(transfer.to||'Kickbase')+'</span></div></div></div>'
          +'<div class="recent-transfer-money"><div><span>Bezahlt</span><strong>'+(number(transfer.price)===null?'–':euros(transfer.price))+'</strong></div>'+secondary+'</div>'
          +'<div class="recent-transfer-footer"><span>'+escapeHtml(relativeTime(transfer.transferredAt))+'</span><span title="Marktwert beim Transfer">MW '+(marketValue===null?'–':euros(marketValue))+'</span></div></div></article>';
      }).join(''):'<p class="empty">Im Kickbase-Aktivitätenfeed wurden noch keine Transfers gefunden.</p>';
    }catch(error){
      $('recent-transfers-updated').textContent='nicht verfügbar';
      container.innerHTML='<p class="empty">Letzte Transfers konnten nicht live aus Kickbase geladen werden.</p>';
    }
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
    const rows=sortedMarket().slice(0,50);
    $('market-table').innerHTML=rows.map(p=>
      '<tr class="market-row" data-player-id="'+escapeHtml(p.id)+'" aria-expanded="false" tabindex="0">'
      +'<td><div class="table-player">'+avatar(p)+'<div><div class="name">'+escapeHtml(name(p))+'</div><div class="sub">'+escapeHtml(club(p))+'</div></div></div></td><td>'+escapeHtml(position(p))+'</td><td>'+euros(mv(p))+'</td><td class="'+cls(change(p))+'">'+signed(change(p))+trendArrow(p)+'</td><td>'+liBadge(p,'')+'</td><td>'+escapeHtml(formatTime(deadline(p)))+'</td></tr>'
      +'<tr class="market-history-row" hidden><td colspan="6"><div class="player-history"><p class="empty">Aufklappen lädt die Tagesänderungen.</p></div></td></tr>'
    ).join('')||'<tr><td colspan="6" class="empty">Keine Marktangebote im aktuellen Stand.</td></tr>';
    document.querySelectorAll('.market-row').forEach(row=>{
      const toggle=()=> {
        const historyRow=row.nextElementSibling;
        const isOpening=historyRow.hidden;
        historyRow.hidden=!isOpening;
        row.setAttribute('aria-expanded',String(isOpening));
        if(isOpening) loadPlayerHistory({dataset:{playerId:row.dataset.playerId},querySelector:selector=>historyRow.querySelector(selector)});
      };
      row.addEventListener('click',toggle);
      row.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();toggle();}});
    });
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
  async function startGitHubReport(kind, button){
    const buttons=[...document.querySelectorAll('.report-actions .button')];
    buttons.forEach(item=>item.disabled=true);
    $('live-status').textContent=(kind==='full'?'Vollreport':'Fast 1T')+' wird in GitHub gestartet …';
    try{
      const response=await fetch(apiPath('/api/github-report'),{
        method:'POST',
        headers:{'Content-Type':'application/json','X-Advisor-Token':settings.csrf},
        body:JSON.stringify({kind}),
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.error||'Start fehlgeschlagen');
      $('live-status').textContent=(kind==='full'?'Vollreport':'Fast 1T')+' in GitHub gestartet. Der Snapshot wird anschließend automatisch übernommen.';
    }catch(error){
      $('live-status').textContent='GitHub-Report nicht gestartet: '+(error.message||'Unbekannter Fehler');
    }finally{
      buttons.forEach(item=>item.disabled=false);
    }
  }
  $('market-sort').onchange=renderTable;
  $('run-full-report').onclick=()=>startGitHubReport('full',$('run-full-report'));
  $('run-fast-report').onclick=()=>startGitHubReport('fast',$('run-fast-report'));
  $('live-status').textContent=settings.liveMessage||data.generated||'Reportstand geladen';
  renderForecastStatus();render();renderValueHistory();renderManagerBudgets();renderRecentTransfers();
  // Custom designs use exactly the same renderer as the editor preview.
  (async()=>{
    const L=window.KaneLayout, host=$('custom-dashboard'),toggle=$('toggle-custom-layout');
    if(!L||!host||!toggle)return;
    try{
      const design=await L.json('api/dashboard-layout');if(!design.enabled)return;
      const source={report:data,api:{}},mobile=matchMedia('(max-width:899px)');let custom=true;
      const layout=()=>design[mobile.matches?'mobile':'desktop'];
      const paint=()=>{if(!layout())return;const sections=layout().tiles.some(t=>t.section),shell=document.querySelector('.app-shell');
        // Preserve the existing metrics, history chart and manager budgets around the five editable sections.
        if(sections)document.querySelector('.dashboard-grid').append(host);else shell.insertBefore(host,shell.querySelector('.metrics'));
        host.hidden=!custom;shell.classList.toggle('custom-layout-active',custom);shell.classList.toggle('section-layout-active',custom&&sections);
        toggle.textContent=custom?'Standardansicht':'Mein Layout';L.render(host,layout(),source);};
      if(!layout())return;toggle.hidden=false;toggle.onclick=()=>{custom=!custom;paint();};paint();
      mobile.addEventListener('change',paint);
      let lastWidth=0;
      const resizeObserver=new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(width>0&&Math.abs(width-lastWidth)>.5){lastWidth=width;requestAnimationFrame(paint);}});
      resizeObserver.observe(host);
      await L.liveData(source);await Promise.all([design.desktop&&L.boundData(source,design.desktop),design.mobile&&L.boundData(source,design.mobile)]);paint();
      // Refresh visible bindings without disturbing the stored layout.
      let refreshing=false;
      setInterval(async()=>{if(document.hidden||!custom||refreshing)return;refreshing=true;
        try{source.report=await L.json('api/dashboard-data');await L.liveData(source);await L.boundData(source,layout());paint();}
        catch{/* Keep the last successful data if the add-on is temporarily offline. */}finally{refreshing=false;}
      },60000);
    }catch(error){$('live-status').textContent+=' · Eigenes Layout nicht geladen: '+error.message;}
  })();
})();
