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
  const mv = p => number(field(p,'mv','marketValue','market_value')) || 0;
  const change = p => number(field(p,'change','predicted_mv_target','prediction1T','predictedChange')) || 0;
  const points = p => number(field(p,'season','l3','average','avgPoints','pointsAverage','points_avg','seasonAverage'));
  const li = p => number(field(p,'li','liPercent','startingProbability'));
  const deadline = p => field(p,'expiresAt','expires_at','expiry','expiration');
  const image = p => field(p,'image','imageUrl','profileImage') || '';
  const club = p => field(p,'team','club','teamName') || '–';
  const position = p => field(p,'position','pos') || '–';
  const name = p => field(p,'name','playerName') || 'Unbekannt';
  const cls = value => value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';
  const avatar = p => image(p) ? '<img class="avatar" src="'+escapeHtml(image(p))+'" alt="" loading="lazy">' : '<span class="avatar"></span>';
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const playerLabel = p => '<div class="player">'+avatar(p)+'<div><div class="name">'+escapeHtml(name(p))+'</div><div class="sub">'+escapeHtml(club(p))+' · '+escapeHtml(position(p))+'</div></div></div>';
  const timeValue = value => { if (!value) return Infinity; if (typeof value === 'string' && Number.isNaN(Number(value))) { const parsed = Date.parse(value); return Number.isNaN(parsed) ? Infinity : parsed; } const numeric = Number(value); return numeric > 1e12 ? numeric : numeric * 1000; };\n  const formatTime = value => { const stamp=timeValue(value); if(!Number.isFinite(stamp))return '–'; return new Date(stamp).toLocaleString('de-DE',{timeZone:'Europe/Berlin',dateStyle:'short',timeStyle:'short'});};

  function renderMetrics(){
    const budget=number(data.budget) ?? number(data.availableBudget) ?? number(data.cash);
    const rosterValue=players.reduce((sum,p)=>sum+mv(p),0);
    const rosterChange=players.reduce((sum,p)=>sum+change(p),0);
    const opportunities=market.filter(p=>change(p)>=50000).length;
    $('metric-budget').textContent=budget===null?'–':euros(budget);$('metric-budget').className=cls(budget||0);
    $('metric-roster-value').textContent=euros(rosterValue);$('metric-roster-count').textContent=players.length+'/16 Spieler';
    $('metric-roster-change').textContent=signed(rosterChange);$('metric-roster-change').className=cls(rosterChange);
    $('metric-opportunities').textContent=String(opportunities);$('market-count').textContent=market.length+' Angebote';
  }
  function renderTopChances(){
    const chosen=[...market].filter(p=>change(p)>=50000).sort((a,b)=>change(b)-change(a)).slice(0,3);
    $('top-chances').innerHTML=chosen.length?chosen.map(p=>'<article class="chance"><div class="chance-top">'+playerLabel(p)+'<span class="tag">'+escapeHtml(position(p))+'</span></div><div class="chance-change"><span>Erw. MW in 1T</span><strong class="positive">'+signed(change(p))+'</strong></div><div class="chance-details"><span>MW '+euros(mv(p))+'</span><span>Ablauf '+escapeHtml(formatTime(deadline(p)))+'</span></div></article>').join(''):'<p class="empty">Keine positive Marktwertchance über der gewählten Schwelle.</p>';
  }
  function renderRoster(){
    const chosen=[...players].sort((a,b)=>change(b)-change(a)).slice(0,5);
    $('roster-movers').innerHTML=chosen.length?chosen.map(p=>'<div class="list-row">'+playerLabel(p)+'<div class="list-value '+cls(change(p))+'">'+signed(change(p))+'</div></div>').join(''):'<p class="empty">Noch kein Kader geladen.</p>';
  }
  function renderRisks(){
    const risky=[...players].filter(p=>change(p)<0).sort((a,b)=>change(a)-change(b)).slice(0,3);
    const expiring=[...market].filter(p=>deadline(p)).sort((a,b)=>timeValue(deadline(a))-timeValue(deadline(b))).slice(0,2);
    const rows=[];
    risky.forEach(p=>rows.push('<div class="list-row">'+playerLabel(p)+'<div class="list-value negative"><span class="risk-dot red"></span>'+signed(change(p))+'</div></div>'));
    expiring.forEach(p=>rows.push('<div class="list-row">'+playerLabel(p)+'<div class="list-value neutral"><span class="risk-dot"></span>'+escapeHtml(formatTime(deadline(p)))+'</div></div>'));
    $('timing-risks').innerHTML=rows.length?rows.join(''):'<p class="empty">Aktuell keine auffälligen Risiken.</p>';
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
  async function report(kind){
    $('run-fast').disabled=$('run-full').disabled=true;
    $('report-status').textContent=(kind==='fast'?'Schnellreport':'Vollreport')+' läuft …';
    try{
      const response=await fetch(apiPath('/api/report-job'),{method:'POST',headers:{'Content-Type':'application/json','X-Advisor-Token':settings.csrf},body:JSON.stringify({kind})});
      const result=await response.json();if(!response.ok)throw Error(result.error||'Report konnte nicht gestartet werden.');
      pollJob();
    }catch(error){$('report-status').textContent=error.message;$('run-fast').disabled=$('run-full').disabled=false;}
  }
  async function pollJob(){
    try{const response=await fetch(apiPath('/api/report-job'),{cache:'no-store'});const job=await response.json();
      if(job.status==='running'){ $('report-status').textContent=(job.kind==='fast'?'Schnellreport':'Vollreport')+' läuft …';setTimeout(pollJob,5000);return;}
      if(job.status==='done'){ $('report-status').textContent='Report fertig. Dashboard wird aktualisiert …';location.reload();return;}
      if(job.status==='failed')throw Error(job.error||'Report fehlgeschlagen.');
      $('run-fast').disabled=$('run-full').disabled=false;
    }catch(error){$('report-status').textContent=error.message;$('run-fast').disabled=$('run-full').disabled=false;}
  }
  $('run-fast').onclick=()=>report('fast');$('run-full').onclick=()=>report('full');$('market-sort').onchange=renderTable;
  $('live-status').textContent=settings.liveMessage||data.generated||'Reportstand geladen';
  render();pollJob();
})();