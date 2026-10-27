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
    const rows = valueAt(data,tile.collection);
    const item = Array.isArray(rows) ? rows.find((row,index)=>rowKey(row,index)===tile.record) : undefined;
    return {...data,item};
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
    const columns=mobile?4:12;
    const layout={columns,rowHeight:32,gap:12,tiles:[]};
    const metrics=[['Budget','/dashboard/Budget','euro'],['Reportstand','/report/generated','auto']];
    metrics.forEach(([title,source,kind],i)=>layout.tiles.push(tile({title,x:mobile?0:i*6,y:mobile?i*3:0,w:mobile?4:6,h:3,elements:[
      element('text',{text:title,x:6,y:8,w:88,h:26,fontSize:13,color:'#a9bacd'}),
      element('data',{source,format:kind,x:6,y:40,w:88,h:48,fontSize:24,bold:true})]})));
    (data.report.players||[]).filter(p=>p.owned!==false).slice(0,30).forEach((p,i)=>{
      const t=playerTile(p,i,mobile);t.record=rowKey(p,(data.report.players||[]).indexOf(p));
      t.x=mobile?0:(i%4)*3;t.y=(mobile?6:3)+Math.floor(i/(mobile?1:4))*7;layout.tiles.push(t);
    });
    return layout;
  }
  function positionElement(node, e) {Object.assign(node.style,{left:e.x+'%',top:e.y+'%',width:e.w+'%',height:e.h+'%'});}
  function renderElement(e, ctx) {
    const node=document.createElement('div');node.className='layout-element';node.dataset.element=e.id;
    positionElement(node,e);
    Object.assign(node.style,{color:e.color,background:rgba(e.background,e.backgroundOpacity),opacity:e.opacity,
      fontSize:e.fontSize+'px',fontWeight:e.bold?'700':'400',textAlign:e.align,borderRadius:e.radius+'px'});
    if (e.type==='image') {
      node.classList.add('layout-image');
      const src=safeImage(e.source?valueAt(ctx,e.source):e.url);
      if(src){const img=document.createElement('img');img.src=src;img.alt=e.text||'';img.draggable=false;img.loading='lazy';img.referrerPolicy='no-referrer';
        Object.assign(img.style,{objectFit:e.fit,objectPosition:'50% '+e.imageY+'%',transform:`scale(${e.zoom})`,transformOrigin:'50% '+e.imageY+'%'});
        img.onerror=()=>{img.remove();node.classList.add('missing-image');node.textContent=e.text||'Bild nicht verfügbar';};node.append(img);
      } else {node.classList.add('missing-image');node.textContent=e.text||'Bild';}
    } else node.textContent=e.type==='text'?e.text:e.text+format(valueAt(ctx,e.source),e.format);
    return node;
  }
  function gridStyle(canvas,layout) {
    const rows=Math.max(1,...layout.tiles.map(t=>t.y+t.h));
    Object.assign(canvas.style,{gridTemplateColumns:`repeat(${layout.columns}, minmax(0,1fr))`,
      gridTemplateRows:`repeat(${rows}, ${layout.rowHeight}px)`,gap:layout.gap+'px'});
  }
  function positionTile(node,t) {node.style.gridColumn=`${t.x+1} / span ${t.w}`;node.style.gridRow=`${t.y+1} / span ${t.h}`;}
  function render(canvas,layout,data,decorate) {
    enrich(data);canvas.replaceChildren();canvas.classList.add('layout-canvas');gridStyle(canvas,layout);
    layout.tiles.forEach(t=>{
      const node=document.createElement('article');node.className='layout-tile';node.dataset.tile=t.id;node.setAttribute('aria-label',t.title);positionTile(node,t);
      node.style.background=rgba(t.color,t.opacity);
      const surface=document.createElement('div');surface.className='tile-surface';node.append(surface);
      const ctx=context(data,t);t.elements.forEach(e=>surface.append(renderElement(e,ctx)));
      if(decorate)decorate(node,t);canvas.append(node);
    });
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
  return {id,clone,escapeToken,rowKey,valueAt,context,enrich,safeImage,rgba,format,element,tile,playerTile,seed,render,positionTile,positionElement,gridStyle,json,liveData,boundData};
})();
