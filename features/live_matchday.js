'use strict';
(() => {
  const $ = id => document.getElementById(id), dialog = $('actions-dialog');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const n = value => value === null || value === undefined || !Number.isFinite(Number(value)) ? '–' : Number(value).toLocaleString('de-DE', {maximumFractionDigits:1});
  const euro = value => value === null || value === undefined ? '–' : Number(value).toLocaleString('de-DE', {style:'currency',currency:'EUR',maximumFractionDigits:0});
  const tone = value => value > 0 ? 'positive' : value < 0 ? 'negative' : '';
  const signed = value => (value > 0 ? '+' : '') + n(value);
  const date = value => {const d=new Date(value);return Number.isNaN(d.getTime())?'Termin offen':d.toLocaleString('de-DE',{timeZone:'Europe/Berlin',weekday:'short',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});};
  const picture = (src, className='') => src ? '<img class="'+className+'" src="'+esc(src)+'" alt="" loading="lazy">' : '';
  let snapshot = null, day = null, view = 'league', sort = 'seasonPoints', actionView = 'chronological', actionPayload = null, selectedPlayer = null, selectedPlayerName = '', loading = false, actionLoading = false, requestId = 0, actionRequestId = 0;
  const avatar = manager => '<span class="manager-avatar">'+(manager.image?picture(manager.image):esc(manager.name.slice(0,1).toUpperCase()))+'</span>';
  const matchResult = game => (game.live || game.finished) && game.homeGoals !== null && game.awayGoals !== null ? n(game.homeGoals)+' : '+n(game.awayGoals) : 'VS';
  function hero(){
    if(!snapshot)return;
    const ordered=[...snapshot.fixtures].sort((a,b)=>new Date(a.kickoff)-new Date(b.kickoff));
    const game=ordered.find(g=>g.live)||ordered.find(g=>!g.finished)||ordered.at(-1);
    if(!game){$('hero-content').innerHTML='<span>Keine Begegnungen für diesen Spieltag verfügbar.</span>';return;}
    let detail=game.live?(game.minute?n(game.minute)+'. Minute':'Spiel läuft'):game.finished?'Beendet':date(game.kickoff);
    const seconds=Math.floor((new Date(game.kickoff)-Date.now())/1000);
    const countdown=!game.live&&!game.finished&&seconds>0?'<span class="countdown">'+[Math.floor(seconds/3600),Math.floor(seconds/60)%60,seconds%60].map(v=>String(v).padStart(2,'0')).join(':')+'</span><small>BIS ANPFIFF</small>':'';
    $('hero-content').innerHTML='<div class="hero-match"><div class="hero-team">'+picture(game.homeImage)+'<span>'+esc(game.home)+'</span></div><div class="hero-center"><small>'+esc(detail)+'</small><strong>'+matchResult(game)+'</strong>'+countdown+'</div><div class="hero-team">'+picture(game.awayImage)+'<span>'+esc(game.away)+'</span></div></div>';
  }
  function render(){
    if(!snapshot)return;
    const scrollPositions=new Map([...document.querySelectorAll('.manager-row')].map(row=>[row.dataset.manager,row.querySelector('.player-strip').scrollLeft]));
    $('league-name').textContent=snapshot.league;
    $('day-select').innerHTML=snapshot.days.map(d=>'<option value="'+d+'"'+(d===snapshot.day?' selected':'')+'>'+d+'</option>').join('');
    $('day-select').disabled=false;
    $('data-notes').textContent=snapshot.notes.join(' ');$('data-notes').hidden=!snapshot.notes.length;
    const league=[...snapshot.managers].sort((a,b)=>{const av=a[sort],bv=b[sort];return av===null?bv===null?a.name.localeCompare(b.name):1:bv===null?-1:sort==='seasonRank'?av-bv:bv-av;});
    $('league-rows').innerHTML=league.map(m=>'<tr data-manager="'+esc(m.id)+'"><td>'+n(m.seasonRank)+'</td><td><div class="manager-label">'+avatar(m)+'<span>'+esc(m.name)+'</span></div></td><td>'+n(m.squadSize)+'</td><td>'+esc(m.formation||'–')+(m.provisional?'<small>vorläufig</small>':'')+'</td><td>'+euro(m.squadValue)+'</td><td>'+n(m.lineupAverage)+'</td><td class="'+tone(m.valueChange)+'">'+(m.valueChange>0?'+':'')+euro(m.valueChange)+'</td><td>'+n(m.wins)+'</td><td><strong>'+n(m.dayPoints)+'</strong><small>'+m.lineup.length+'/11'+(m.provisional?' · vorläufig':'')+'</small></td><td><strong>'+n(m.seasonPoints)+'</strong><small>Ø '+n(m.seasonAverage)+'</small></td></tr>').join('')||'<tr><td colspan="10">Keine Manager verfügbar.</td></tr>';
    const managers=[...snapshot.managers].sort((a,b)=>a.dayPoints===null?b.dayPoints===null?a.name.localeCompare(b.name):1:b.dayPoints===null?-1:b.dayPoints-a.dayPoints||a.name.localeCompare(b.name));
    $('manager-rows').innerHTML=managers.map((m,index)=>'<article class="manager-row" data-manager="'+esc(m.id)+'"><div class="manager-info"><span class="manager-rank">'+(index+1)+'</span>'+avatar(m)+'<div><h2>'+esc(m.name)+'</h2><strong>'+n(m.dayPoints)+'</strong><small>'+m.lineup.length+'/11 Spieler'+(m.provisional?' · vorläufige Aufstellung':'')+'</small></div></div><div class="player-strip">'+(m.lineup.map(p=>'<button class="live-player" data-player="'+esc(p.id)+'" data-name="'+esc(p.name)+'" aria-label="'+esc(p.name)+': '+n(p.points)+' Punkte, Aktionen öffnen"><span class="score '+tone(p.points)+'">'+n(p.points)+'</span>'+(p.image?picture(p.image):'<span class="player-silhouette" aria-hidden="true"></span>')+'<span class="player-name">'+esc(p.name)+'</span></button>').join('')||'<span class="lineup-empty">Startelf derzeit nicht verfügbar.</span>')+'</div></article>').join('')||'<p class="empty">Keine Manager verfügbar.</p>';
    for(const row of document.querySelectorAll('.manager-row'))row.querySelector('.player-strip').scrollLeft=scrollPositions.get(row.dataset.manager)||0;
    const fixtures=snapshot.fixtures.map(g=>'<div class="fixture-item">'+picture(g.homeImage)+'<span>'+esc(g.home)+'</span><b>'+matchResult(g)+'</b>'+picture(g.awayImage)+'<span>'+esc(g.away)+'</span><small>'+esc(g.live?(g.minute?n(g.minute)+"′":'LIVE'):g.finished?'Beendet':date(g.kickoff))+'</small></div>').join('');
    const signature=JSON.stringify(snapshot.fixtures);
    if($('ticker-track').dataset.signature!==signature){$('ticker-track').innerHTML='<div class="ticker-group">'+fixtures+'</div><div class="ticker-group" aria-hidden="true">'+fixtures+'</div>';$('ticker-track').dataset.signature=signature;}
    $('live-status').textContent='Kickbase · Stand '+new Date(snapshot.fetchedAt).toLocaleTimeString('de-DE',{timeZone:'Europe/Berlin'})+' · Aktualisierung alle 20 s';
    hero();
  }
  function setView(value){
    view=value;
    document.body.dataset.activeView=view;
    for(const key of ['league','matchday']){const active=key===view;$('tab-'+key).setAttribute('aria-selected',String(active));$('tab-'+key).tabIndex=active?0:-1;$(key+'-view').hidden=!active;}
    $('section-title').textContent=view==='league'?'LIGA':'LIVESCORE';
  }
  async function refresh(force=false){
    if(loading&&!force)return;
    const current=++requestId;loading=true;$('refresh').disabled=true;
    try{
      const response=await fetch('api/live-matchday'+(day===null?'':'?day='+day),{cache:'no-store'}),payload=await response.json();
      if(!response.ok)throw Error(payload.error||'Live-Spieltag derzeit nicht abrufbar.');
      if(current!==requestId)return;
      snapshot=payload;day=payload.day;$('live-error').hidden=true;render();
    }catch(error){if(current===requestId){$('live-error').textContent=error.message+(snapshot?' Angezeigt wird der letzte erfolgreiche Abruf; dessen Zeit steht oben.':'');$('live-error').hidden=false;$('live-status').textContent=snapshot?'Letzter erfolgreicher Abruf: '+date(snapshot.fetchedAt):'Kein erfolgreicher Live-Abruf.';}}
    finally{if(current===requestId){loading=false;$('refresh').disabled=false;}}
  }
  function renderActions(){
    if(!actionPayload)return;
    $('actions-title').textContent=actionPayload.name;$('actions-points').textContent=n(actionPayload.points);
    const delta=actionPayload.difference;
    $('actions-status').textContent=!actionPayload.available?'Kickbase liefert derzeit keine Punkteaktionen.':!actionPayload.complete?'Einzelne Buchungen haben keinen Punktewert; Summe möglicherweise unvollständig.':delta!==null&&delta!==0?'Buchungssumme '+n(actionPayload.bookedPoints)+' · Differenz zum Punktestand '+signed(delta)+' (Datenstand/Korrekturen).':'Buchungssumme '+n(actionPayload.bookedPoints)+' · inklusive Korrekturen';
    const rows=actionPayload[actionView];
    $('actions-list').innerHTML=rows.length?rows.map(row=>'<div class="action-row"><small>'+(actionView==='grouped'?row.count+'×':row.minute===null?'–':n(row.minute)+"′")+'</small><div>'+esc(row.label)+(row.correction?'<br><small>Korrekturbuchung</small>':'')+(row.corrections?'<br><small>'+row.corrections+' Korrekturbuchung(en)</small>':'')+'</div><strong class="'+tone(row.points)+'">'+signed(row.points)+'</strong></div>').join(''):'<p class="empty">Noch keine Punkteaktionen für diesen Spieltag verfügbar.</p>';
  }
  async function refreshActions(){
    if(actionLoading||!dialog.open||selectedPlayer===null)return;
    const current=++actionRequestId, player=selectedPlayer, requestedDay=day;actionLoading=true;
    try{
      const response=await fetch('api/live-matchday/player/'+encodeURIComponent(player)+'?day='+requestedDay,{cache:'no-store'}),payload=await response.json();
      if(!response.ok)throw Error(payload.error||'Punkteaktionen derzeit nicht abrufbar.');
      if(current!==actionRequestId||player!==selectedPlayer||requestedDay!==day)return;
      actionPayload=payload;renderActions();
    }catch(error){if(current===actionRequestId){$('actions-status').textContent=error.message+(actionPayload?' Letzter erfolgreicher Aktionsstand bleibt sichtbar.':'');if(!actionPayload)$('actions-list').innerHTML='<p class="empty">Keine Aktionsdaten verfügbar.</p>';}}
    finally{if(current===actionRequestId)actionLoading=false;}
  }
  function closeActions(){dialog.close();selectedPlayer=null;actionRequestId++;actionLoading=false;}
  document.addEventListener('click',event=>{
    const tab=event.target.closest('[data-view]');if(tab){setView(tab.dataset.view);return;}
    const order=event.target.closest('[data-sort]');if(order){sort=order.dataset.sort;render();return;}
    const actions=event.target.closest('[data-actions-view]');if(actions){actionView=actions.dataset.actionsView;for(const button of document.querySelectorAll('[data-actions-view]')){const active=button===actions;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;}$('actions-list').setAttribute('aria-labelledby',actions.id);renderActions();return;}
    const player=event.target.closest('[data-player]');if(player){selectedPlayer=player.dataset.player;selectedPlayerName=player.dataset.name;actionRequestId++;actionLoading=false;actionPayload=null;$('actions-title').textContent=selectedPlayerName;$('actions-day').textContent='Spieltag '+day;$('actions-points').textContent='–';$('actions-status').textContent='Lade Punkteaktionen …';$('actions-list').innerHTML='';dialog.showModal();refreshActions();}
  });
  for(const tabs of document.querySelectorAll('[role=tablist]'))tabs.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const buttons=[...tabs.querySelectorAll('[role=tab]')],index=buttons.indexOf(document.activeElement);const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowLeft'?-1:1)+buttons.length)%buttons.length;buttons[next].click();buttons[next].focus();});
  $('close-actions').onclick=closeActions;dialog.addEventListener('click',event=>{if(event.target===dialog)closeActions();});dialog.addEventListener('cancel',()=>{selectedPlayer=null;actionRequestId++;actionLoading=false;});
  $('day-select').onchange=()=>{day=Number($('day-select').value);if(dialog.open)closeActions();snapshot=null;$('league-rows').innerHTML='';$('manager-rows').innerHTML='<p class="empty">Spieltag wird geladen …</p>';$('ticker-track').innerHTML='';delete $('ticker-track').dataset.signature;$('hero-content').innerHTML='<span>Spieltag wird geladen …</span>';refresh(true);};
  $('refresh').onclick=()=>refresh();
  $('ticker-toggle').onclick=()=>{const paused=document.querySelector('.fixture-ticker').classList.toggle('paused');$('ticker-toggle').setAttribute('aria-pressed',String(paused));$('ticker-toggle').setAttribute('aria-label',paused?'Laufband fortsetzen':'Laufband pausieren');$('ticker-toggle').textContent=paused?'▶':'Ⅱ';};
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){refresh();if(dialog.open)refreshActions();}});
  setInterval(()=>{if(!document.hidden){refresh();if(dialog.open)refreshActions();}},20000);
  setInterval(()=>{if(!document.hidden)hero();},1000);
  setView(view);refresh();
})();
