'use strict';
/* Shared renderer: designs contain values and bindings, never executable markup. */
window.KaneLayout = (() => {
  const id = () => crypto.randomUUID ? crypto.randomUUID() : 'k'+Date.now().toString(36)+Math.random().toString(36).slice(2);
  const clone = value => JSON.parse(JSON.stringify(value));
  const escapeToken = value => String(value).replace(/~/g,'~0').replace(/\//g,'~1');
  const rowKey = (row, index) => row && row.id != null ? 'id:'+row.id : row && row.name ? 'name:'+row.name : 'index:'+index;
  function valueAt(root, path) {
    if (!path || path[0] !== '/') return undefined;
    return path.slice(1).split('/').map(v=>v.replace(/~1/g,'/').replace(/~0/g,'~')).reduce((value,key) =>
      value != null && Object.prototype.hasOwnProperty.call(Object(value),key) ? value[key] : undefined, root);
  }
  function context(data, tile) {
    if(tile.section)return {...data,item:placeholderItem(),template:true};
    const rows = valueAt(data,tile.collection);
    const item = Array.isArray(rows) ? rows.find((row,index)=>rowKey(row,index)===tile.record) : undefined;
    return {...data,item};
  }
  const sections={transfers:'Letzte Transfers',chances:'Beste Chancen vor MW-Update',roster:'Wertentwicklung',risks:'Handlungsbedarf',market:'Transfermarkt'};
  const aliases=['Name','Nachname','Vereinswappen','Spielerbild','Verein','Position','Marktwert','Erw. 1T','LI','Durchschnittspunkte','Gesamtpunkte','Status','Gewinn/Verlust','Letzte MW-Änderung','Bezahlt','Overpay','G/V des Verkäufers','Verkauf an Kickbase','Verkäufer','Käufer','Transferzeit','Ablauf','Restlaufzeit (Std.)','Handlungsgrund','Nächste Begegnung','Form 1','Form 2','Form 3'];
  const pick=(row,...keys)=>keys.map(k=>row?.[k]).find(v=>v!==undefined&&v!==null&&v!=='')??null;
  const numeric=v=>v===null||v===undefined||v===''||typeof v==='boolean'||!Number.isFinite(Number(v))?null:Number(v);
  const forecast=p=>numeric(pick(p,'change','predicted_mv_target','prediction1T','predictedChange'));
  function stamp(value){if(value==null||value==='')return Infinity;const n=Number(value);return Number.isFinite(n)?n*(n<1e12?1000:1):Date.parse(value)||Infinity;}
  function nextUpdate(now=Date.now()){
    const formatter=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
    const parts=time=>Object.fromEntries(formatter.formatToParts(time).map(p=>[p.type,p.value]));
    const p=parts(now),day=new Date(Date.UTC(+p.year,+p.month-1,+p.day+(+p.hour>=22?1:0),22));
    const target=+day,q=parts(target),offset=Date.UTC(+q.year,+q.month-1,+q.day,+q.hour,+q.minute,+q.second)-target;
    return target-offset;
  }
  function normalizeItem(row,section,data){
    const playerId=pick(row,'playerId','id');
    const player=[...(data.report.players||[]),...(data.report.marketPlayers||[])].find(p=>String(p.id)===String(playerId));
    // Historic transfer values always take priority over today's player profile.
    const p={...player,...row}, transfer=section==='transfers',name=pick(p,'playerName','name')||'Unbekannter Spieler';
    const mv=transfer?pick(row,'marketValue'):pick(p,'mv','marketValue','market_value');
    const expires=pick(p,'expiresAt','expires_at','expiry','expiration');
    const form=pick(p,'recentForm','form')||[];
    const fixture=Array.isArray(p.fixtures)?p.fixtures[0]:p.nextFixture;
    const venue=fixture?.venue==='Heim'?'H':fixture?.venue==='Auswärts'?'A':fixture?.venue||'';
    return {'Name':name,'Nachname':String(name).trim().split(/\s+/).pop(),'Vereinswappen':pick(p,'teamImage','teamImageUrl','team_image_url','teamLogo'),
      'Spielerbild':pick(p,'image','imageUrl','profileImage'),'Verein':pick(p,'team','club','teamName'),
      'Position':({1:'TW',2:'ABW',3:'MIT',4:'ANG'}[pick(p,'position','pos')]||pick(p,'position','pos')),
      'Marktwert':mv,'Erw. 1T':forecast(p),'LI':pick(p,'li','liPercent','startingProbability'),
      'Durchschnittspunkte':pick(p,'season','l3','average','avgPoints','pointsAverage'),'Gesamtpunkte':pick(p,'totalPoints','total_points','pointsTotal'),
      'Status':pick(p,'status','playerStatus'),'Gewinn/Verlust':pick(p,'profitLoss','profit_loss'),
      'Letzte MW-Änderung':pick(p,'lastMvChange','last_market_change','latestMarketChange'),'Bezahlt':pick(row,'price'),
      'Overpay':row.isKickbaseSale?null:pick(row,'overpay'),'G/V des Verkäufers':row.isKickbaseSale?pick(row,'profitLoss'):null,'Verkauf an Kickbase':!!row.isKickbaseSale,
      'Verkäufer':pick(row,'from'),'Käufer':pick(row,'to'),'Transferzeit':pick(row,'transferredAt'),'Ablauf':expires,
      'Restlaufzeit (Std.)':Number.isFinite(stamp(expires))?Math.max(0,(stamp(expires)-Date.now())/3600000):null,
      'Handlungsgrund':row._reason||null,'Nächste Begegnung':fixture?([fixture.opponent,venue,fixture.rank?'('+fixture.rank+'.)':''].filter(Boolean).join(' ')):null,
      'Form 1':form[0]??null,'Form 2':form[1]??null,'Form 3':form[2]??null,'Rohdaten':p};
  }
  function placeholderItem(){return Object.fromEntries(aliases.map(name=>[name,'{'+name+'}']));}
  function sectionItems(data,section,now=Date.now()){
    const players=data.report.players||[],market=(data.report.marketPlayers||[]).filter(p=>!p.owned),update=nextUpdate(now);
    let rows=[];
    if(section==='transfers')rows=data.api.transfers?.transfers||[];
    if(section==='roster')rows=[...players].sort((a,b)=>(forecast(b)||0)-(forecast(a)||0));
    if(section==='market')rows=[...market].sort((a,b)=>(forecast(b)||0)-(forecast(a)||0));
    if(section==='chances')rows=market.filter(p=>forecast(p)!==null&&forecast(p)>=100000&&stamp(pick(p,'expiresAt','expires_at','expiry','expiration'))<update).sort((a,b)=>forecast(b)-forecast(a));
    if(section==='risks'){
      rows=[...players].filter(p=>forecast(p)!==null&&forecast(p)<0).sort((a,b)=>forecast(a)-forecast(b)).map(p=>({...p,_reason:'Drohender MW-Verlust'}));
      rows.push(...market.filter(p=>forecast(p)!==null&&forecast(p)>=100000&&stamp(pick(p,'expiresAt','expires_at','expiry','expiration'))<=update+11*3600000)
        .sort((a,b)=>forecast(b)-forecast(a)).map(p=>({...p,_reason:stamp(pick(p,'expiresAt','expires_at','expiry','expiration'))<=update?'Top-Chance vor 22 Uhr':'Nachtgebot 22–09 Uhr'})));
    }
    return rows.map(row=>normalizeItem(row,section,data));
  }
  function enrich(data) {
    const report=data.report||{},players=report.players||[],market=report.marketPlayers||[];
    const number=value=>value==null||value===''||typeof value==='boolean'||!Number.isFinite(Number(value))?null:Number(value);
    const field=(row,keys)=>number(keys.map(key=>row[key]).find(v=>v!=null&&v!==''));
    const total=keys=>{const values=players.map(p=>field(p,keys)).filter(v=>v!==null);return values.length?values.reduce((a,b)=>a+b,0):null;};
    const budget=field(report,['budget','availableBudget','cash']),mv=total(['mv','marketValue','market_value'])||0;
    data.dashboard={'Budget':budget,'Kaderwert':mv,'Bereinigter Kaderwert':mv+Math.min(budget??0,0),
      'Kadergröße':players.length,'Kaderlimit':16,'Erwartete MW-Änderung (1T)':total(['change','predicted_mv_target','prediction1T','predictedChange']),
      'Letzte MW-Änderung':total(['lastMvChange','last_market_change','latestMarketChange']),
      'Kaufkraft':number(report.buyingPower),'Offene Gebote':number(report.openBidTotal)||0,'Marktangebote':market.filter(p=>!p.owned).length};
  }
  const safeImage = value => typeof value==='string' && (/^https?:\/\//i.test(value) || /^data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+$/.test(value)) ? value : '';
  const rgba = (hex, opacity) => /^#[0-9a-f]{6}$/i.test(hex||'') ? `rgba(${parseInt(hex.slice(1,3),16)},${parseInt(hex.slice(3,5),16)},${parseInt(hex.slice(5,7),16)},${opacity})` : 'transparent';
  function format(value, kind) {
    if (value == null || value === '') return '–';
    if (typeof value==='object') return JSON.stringify(value);
    if (kind==='date') {const date=new Date(value);return Number.isNaN(+date)?String(value):date.toLocaleString('de-DE');}
    if (typeof value==='boolean') return value?'Ja':'Nein';
    if (kind==='auto') return String(value);
    const n = Number(value); if (!Number.isFinite(n)) return String(value);
    if (kind==='euro') return n.toLocaleString('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:0});
    if (kind==='million') return (n/1e6).toLocaleString('de-DE',{maximumFractionDigits:1})+' Mio. €';
    if (kind==='percent') return n.toLocaleString('de-DE',{maximumFractionDigits:1})+' %';
    return n.toLocaleString('de-DE',{maximumFractionDigits:1});
  }
  function element(type, patch={}) {
    return {id:id(),type,text:type==='text'?'Neuer Text':'',source:'',url:'',x:8,y:12,w:84,h:20,
      color:'#ffffff',background:'#0d1d2c',backgroundOpacity:0,opacity:1,fontSize:18,bold:false,
      radius:0,zoom:1,imageY:50,align:'left',fit:'contain',format:'auto',...patch};
  }
  function tile(patch={}) {
    return {id:id(),title:'Neue Kachel',x:0,y:0,w:3,h:6,color:'#102231',opacity:1,collection:'',record:'',elements:[],...patch};
  }
  function playerTile(player, index, mobile=false, collection='/report/players') {
    const imageKey = ['image','imageUrl','profileImage'].find(k=>player[k])||'image';
    const crestKey = ['teamImage','teamImageUrl','teamLogo'].find(k=>player[k])||'teamImage';
    return tile({title:player.name||'Spieler',collection,record:rowKey(player,index),w:mobile?4:3,h:7,elements:[
      element('image',{source:'/item/'+crestKey,x:0,y:0,w:100,h:100,opacity:.05,fit:'cover'}),
      element('image',{source:'/item/'+imageKey,x:6,y:8,w:38,h:42,radius:100,fit:'cover',zoom:1.6,imageY:10}),
      element('data',{source:'/item/name',x:47,y:12,w:49,h:20,fontSize:20,bold:true}),
      element('data',{text:'LI: ',source:'/item/li',format:'percent',x:47,y:33,w:49,h:15,color:'#24d99a',fontSize:14}),
      element('data',{text:'MW: ',source:'/item/mv',format:'million',x:7,y:57,w:90,h:17,fontSize:19,bold:true}),
      element('data',{text:'Ø Punkte: ',source:'/item/season',format:'number',x:7,y:78,w:90,h:15,fontSize:14})]});
  }
  function seed(data, mobile=false) {
    if(window.KaneNative)return window.KaneNative.seed(data,mobile);
    const columns=mobile?4:12;
    const layout={columns,rowHeight:32,gap:12,tiles:[]};
    for(const [index,key]of Object.keys(sections).entries()){
      const t=sectionTile(key,mobile);t.y=index*8;t.w=columns;
      if(!mobile){if(key==='roster'){t.w=7;t.y=16;}if(key==='risks'){t.x=7;t.w=5;t.y=16;}if(key==='market')t.y=24;}
      layout.tiles.push(t);
    }
    return layout;
  }
  function sectionTile(section,mobile=false){
    const transfer=section==='transfers',narrow=section==='roster'||section==='risks';
    const bind=(name,patch={})=>element(name==='Vereinswappen'||name==='Spielerbild'?'image':'data',{source:'/item/'+escapeToken(name),...patch});
    const elements=[bind('Vereinswappen',{x:0,y:0,w:43,h:100,opacity:.3,fit:'cover'}),
      bind('Spielerbild',{x:0,y:23,w:42,h:77,fit:'contain',imageY:100}),
      bind('Name',{x:45,y:8,w:52,h:17,fontSize:18,bold:true}),
      bind(transfer?'Verkäufer':'Verein',{x:45,y:28,w:52,h:12,fontSize:12,color:'#a9bacd'})];
    if(transfer){
      elements.push(bind('Käufer',{text:'→ ',x:45,y:41,w:52,h:12,fontSize:12,color:'#a9bacd'}),
        bind('Bezahlt',{text:'Bezahlt: ',format:'euro',x:45,y:57,w:52,h:13,fontSize:13,bold:true}),
        bind('Overpay',{text:'Overpay: ',format:'euro',x:45,y:72,w:52,h:9,fontSize:11}),
        bind('G/V des Verkäufers',{text:'G/V: ',format:'euro',x:45,y:82,w:52,h:9,fontSize:11}),
        bind('Marktwert',{text:'MW: ',format:'euro',x:45,y:92,w:52,h:8,fontSize:10,color:'#a9bacd'}));
    }else{
      elements.push(bind('Position',{x:45,y:42,w:17,h:11,fontSize:12}),bind('LI',{text:'LI ',format:'percent',x:64,y:42,w:33,h:11,fontSize:12,color:'#24d99a'}),
        bind('Marktwert',{text:'MW: ',format:'euro',x:45,y:58,w:52,h:14,fontSize:14,bold:true}),
        bind('Erw. 1T',{text:'Erw. 1T: ',format:'euro',x:45,y:77,w:52,h:13,fontSize:13,color:'#24d99a'}));
      if(section==='risks')elements.push(bind('Handlungsgrund',{x:3,y:3,w:94,h:12,fontSize:11,color:'#ffc36b'}));
    }
    return tile({title:sections[section],section,x:0,y:0,w:mobile?4:12,h:8,
      cardColumns:mobile?1:narrow?1:3,cardHeight:240,cardGap:12,cardColor:'#0b1927',cardOpacity:1,elements});
  }
  function positionElement(node, e) {Object.assign(node.style,{left:e.x+'%',top:e.y+'%',width:e.w+'%',height:e.h+'%'});}
  function renderElement(e, ctx) {
    const node=document.createElement('div');node.className='layout-element';node.dataset.element=e.id;
    positionElement(node,e);
    Object.assign(node.style,{color:e.color,background:rgba(e.background,e.backgroundOpacity),opacity:e.opacity,
      fontSize:e.fontSize+'px',fontWeight:e.bold?'700':'400',textAlign:e.align,borderRadius:e.radius+'px'});
    const bound=e.source?valueAt(ctx,e.source):undefined;
    // Transfer templates may contain both alternatives in the same place.
    if(!ctx.template&&((e.source==='/item/Overpay'&&ctx.item?.['Verkauf an Kickbase'])||(e.source==='/item/G~1V des Verkäufers'&&!ctx.item?.['Verkauf an Kickbase']))){node.hidden=true;return node;}
    if (e.type==='image') {
      node.classList.add('layout-image');
      if(ctx.template&&e.source.startsWith('/item/')){node.classList.add('missing-image','template-image');node.textContent='{'+e.source.slice(6).replace(/~1/g,'/').replace(/~0/g,'~')+'}';return node;}
      const src=safeImage(e.source?valueAt(ctx,e.source):e.url);
      if(src){const img=document.createElement('img');img.src=src;img.alt=e.text||'';img.draggable=false;img.loading='lazy';img.referrerPolicy='no-referrer';
        Object.assign(img.style,{objectFit:e.fit,objectPosition:'50% '+e.imageY+'%',transform:`scale(${e.zoom})`,transformOrigin:'50% '+e.imageY+'%'});
        img.onerror=()=>{img.remove();node.classList.add('missing-image');node.textContent=e.text||'Bild nicht verfügbar';};node.append(img);
      } else {node.classList.add('missing-image');node.textContent=e.text||'Bild';}
    } else node.textContent=e.type==='text'?e.text:e.text+(ctx.template&&e.source.startsWith('/item/')?'{'+e.source.slice(6).replace(/~1/g,'/').replace(/~0/g,'~')+'}':format(bound,e.format));
    return node;
  }
  function gridStyle(canvas,layout) {
    const rows=Math.max(1,...layout.tiles.map(t=>t.y+t.h));
    Object.assign(canvas.style,{gridTemplateColumns:`repeat(${layout.columns}, minmax(0,1fr))`,
      gridTemplateRows:`repeat(${rows}, ${layout.rowHeight}px)`,gap:layout.gap+'px'});
  }
  function positionTile(node,t) {node.style.gridColumn=`${t.x+1} / span ${t.w}`;node.style.gridRow=`${t.y+1} / span ${t.h}`;}
  function runtimeLayout(layout,data,heights={}){
    if(!layout.tiles.some(t=>t.section))return layout;
    const result={...layout,tiles:[]},bottom=Array(layout.columns).fill(null);
    for(const original of [...layout.tiles].sort((a,b)=>a.y-b.y||a.x-b.x)){
      const t={...original};
      if(t.section){const count=sectionItems(data,t.section).length,rows=Math.ceil(count/t.cardColumns);
        const height=heights[t.id]??(76+(rows?rows*t.cardHeight+(rows-1)*t.cardGap:40));
        t.h=Math.ceil((height+layout.gap)/(layout.rowHeight+layout.gap));}
      t.y=0;
      for(let col=t.x;col<t.x+t.w;col++){const previous=bottom[col];t.y=Math.max(t.y,previous?previous.y+previous.h+Math.max(0,original.y-previous.original.y-previous.original.h):original.y);}
      for(let col=t.x;col<t.x+t.w;col++)bottom[col]={...t,original};
      result.tiles.push(t);
    }
    return result;
  }
  function render(canvas,layout,data,decorate) {
    enrich(data);const visual=decorate?layout:runtimeLayout(layout,data);canvas.replaceChildren();canvas.classList.add('layout-canvas');gridStyle(canvas,visual);
    visual.tiles.forEach(t=>{
      const node=document.createElement('article');node.className='layout-tile';node.dataset.tile=t.id;node.setAttribute('aria-label',t.title);positionTile(node,t);
      node.style.background=rgba(t.color,t.opacity);
      if(t.section){
        node.classList.add('layout-section');node.dataset.section=t.section;
        const heading=document.createElement('h2');heading.className='layout-section-title';heading.textContent=t.title;node.append(heading);
        const grid=document.createElement('div');grid.className='section-player-grid';grid.style.gridTemplateColumns=`repeat(${t.cardColumns},minmax(0,1fr))`;grid.style.gap=t.cardGap+'px';node.append(grid);
        const items=decorate?[placeholderItem()]:sectionItems(data,t.section);
        items.forEach(item=>{const card=document.createElement('div');card.className='section-player-card';card.style.height=t.cardHeight+'px';card.style.background=rgba(t.cardColor,t.cardOpacity);
          const surface=document.createElement('div');surface.className='tile-surface';card.append(surface);
          const ctx={...data,item,template:!!decorate};
          t.elements.forEach(e=>surface.append(renderElement(e,ctx)));grid.append(card);
        });
        if(!items.length){const empty=document.createElement('p');empty.className='section-empty';empty.textContent='Keine passenden Daten im aktuellen Stand.';grid.append(empty);}
      }else{
        const surface=document.createElement('div');surface.className='tile-surface';node.append(surface);
        const ctx=context(data,t);t.elements.forEach(e=>surface.append(renderElement(e,ctx)));
      }
      if(decorate)decorate(node,t);canvas.append(node);
    });
    if(!decorate&&layout.tiles.some(t=>t.section)){
      // Long headings can wrap on a phone. Fit the actual rendered content,
      // then flow subsequent sections without clipping the last player card.
      const heights={};
      for(const node of canvas.children)if(node.dataset.section){
        const heading=node.querySelector('.layout-section-title'),grid=node.querySelector('.section-player-grid'),style=getComputedStyle(node),hs=getComputedStyle(heading);
        heights[node.dataset.tile]=heading.offsetHeight+parseFloat(hs.marginTop)+parseFloat(hs.marginBottom)+grid.offsetHeight+
          parseFloat(style.paddingTop)+parseFloat(style.paddingBottom)+parseFloat(style.borderTopWidth)+parseFloat(style.borderBottomWidth);
      }
      const fitted=runtimeLayout(layout,data,heights);gridStyle(canvas,fitted);
      const nodes=new Map([...canvas.children].map(n=>[n.dataset.tile,n]));for(const t of fitted.tiles)positionTile(nodes.get(t.id),t);
    }
  }
  async function json(path,options={}) {
    const response=await fetch(path,{cache:'no-store',...options});const body=await response.json();
    if(!response.ok)throw new Error(body.error||'Daten konnten nicht geladen werden.');return body;
  }
  async function liveData(data) {
    const sources={'managerBudgets':'api/manager-budgets','transfers':'api/recent-transfers','squadHistory':'api/squad-value-history','lineup':'api/current-lineup'};
    const errors=[];await Promise.all(Object.entries(sources).map(async([name,path])=>{try{data.api[name]=await json(path);}catch(error){errors.push(name+': '+error.message);}}));return errors;
  }
  async function boundData(data,layout) {
    const requests=new Map();
    for(const tile of layout.tiles)for(const element of tile.elements){
      const match=element.source.match(/^\/api\/(playerDetails|playerMarketHistory)\/([^/]+)/);
      if(!match)continue;const [,kind,token]=match, player=token.replace(/~1/g,'/').replace(/~0/g,'~');
      const endpoint=kind==='playerDetails'?'player-details':'player-market-history';
      requests.set(kind+':'+player,async()=>{try{data.api[kind] ||= {};data.api[kind][player]=await json('api/'+endpoint+'/'+encodeURIComponent(player));}catch{/* Missing bindings render as an explicit dash. */}});
    }
    await Promise.all([...requests.values()].map(run=>run()));
  }
  return {id,clone,escapeToken,rowKey,valueAt,context,enrich,sections,aliases,sectionItems,sectionTile,normalizeItem,placeholderItem,runtimeLayout,safeImage,rgba,format,element,tile,playerTile,seed,render,renderElement,positionTile,positionElement,gridStyle,json,liveData,boundData};
})();
