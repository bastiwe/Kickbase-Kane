'use strict';
/* Edit the existing dashboard DOM. An empty override list changes no styles. */
window.KaneNative=(()=>{
  const L=window.KaneLayout;
  const field=(key,label,selector,type='text',source='',scope='tile')=>({key,label,selector,type,source,scope});
  const heading=[field('title','Überschrift','.panel-heading h2'),field('eyebrow','Bereichslabel','.panel-heading .eyebrow'),field('description','Beschreibung','.panel-description')];
  const art=[field('crest','Vereinswappen','.club-crest','image','/item/Vereinswappen','row'),field('image','Spielerbild','.player-cutout','image','/item/Spielerbild','row')];
  const player=[...art,field('name','Name','.name','data','/item/Name','row')];
  const defs={
    budget:{title:'Verfügbares Budget',selector:'.metric-budget',span:4,fields:[field('label','Titel','.metric-label'),field('value','Budget','#metric-budget','data','/dashboard/Budget'),field('note','Kaufkraft / Hinweis','#metric-budget-note','data')]},
    squad:{title:'Kaderwert',selector:'.metric-squad',span:4,fields:[field('label','Titel','.metric-label'),field('value','Kaderwert','#metric-roster-value','data','/dashboard/Kaderwert'),field('note','Kadergröße / Hinweis','#metric-roster-count','data')]},
    forecast:{title:'Erw. Kader-MW in 1T',selector:'.metric-forecast',span:4,fields:[field('label','Titel','.metric-label'),field('value','Erw. Kader-MW in 1T','#metric-roster-change','data','/dashboard/Erwartete MW-Änderung (1T)'),field('note','Letztes MW-Update / Hinweis','#metric-roster-change-note','data')]},
    history:{title:'Entwicklung seit Saisonstart',selector:'.value-history',span:12,fields:[...heading,field('chart','Kaderwertgrafik','#value-chart','data','/api/squadHistory/series'),field('summary','Zusammenfassung','#history-summary','data'),field('note','Hinweis','#history-note','data')]},
    managers:{title:'Managerbudgets',selector:'.manager-budget-panel',span:12,fields:[...heading,field('budgets','Managerbudgets','#manager-budgets','data','/api/managerBudgets/managers')]},
    transfers:{title:'Letzte Transfers',selector:'.recent-transfers-panel',span:12,rows:'#recent-transfers .recent-transfer-card',grid:'#recent-transfers',fields:[...heading,...player,field('route','Verkäufer → Käufer','.transfer-route','data','','row'),field('paid','Bezahlt','.recent-transfer-money>div:first-child strong','data','/item/Bezahlt','row'),field('resultLabel','Overpay / G/V Überschrift','.recent-transfer-money>div:nth-child(2)>span','data','','row'),field('result','Overpay / G/V','.recent-transfer-money>div:nth-child(2)>strong','data','','row'),field('time','Transferzeit','.recent-transfer-footer>span:first-child','data','/item/Transferzeit','row'),field('mv','Marktwert','.recent-transfer-footer>span:last-child','data','/item/Marktwert','row')]},
    chances:{title:'Beste Chancen vor MW-Update',selector:'#top-chances',parent:'.panel',span:12,rows:'#top-chances .chance',grid:'#top-chances',fields:[...heading,...player,field('club','Verein / Position','.player-subline .sub','data','/item/Verein','row'),field('li','LI','.li-badge','data','/item/LI','row'),field('position','Position','.tag','data','/item/Position','row'),field('change','Erw. 1T','.chance-change strong','data','/item/Erw. 1T','row'),field('mv','Marktwert','.chance-details>span:first-child','data','/item/Marktwert','row'),field('expiry','Ablauf','.chance-details>span:last-child','data','/item/Ablauf','row')]},
    roster:{title:'Wertentwicklung',selector:'.roster-panel',span:7,rows:'#roster-movers .roster-player',grid:'#roster-movers',fields:[...heading,...player,field('club','Verein / Position','.player .sub','data','/item/Verein','row'),field('profit','Gewinn/Verlust','.roster-statline>span:nth-child(1)','data','/item/Gewinn~1Verlust','row'),field('points','Gesamtpunkte','.roster-statline>span:nth-child(2)','data','/item/Gesamtpunkte','row'),field('average','Durchschnittspunkte','.roster-statline>span:nth-child(3)','data','/item/Durchschnittspunkte','row'),field('changeLabel','Prognose-Überschrift','.roster-values>.sub','text','','row'),field('change','Erw. 1T','.roster-values .list-value','data','/item/Erw. 1T','row')]},
    risks:{title:'Handlungsbedarf',selector:'.action-panel',span:5,rows:'#timing-risks .risk-player',grid:'#timing-risks',fields:[...heading,...player,field('club','Verein / Position','.player-subline .sub','data','/item/Verein','row'),field('li','LI','.li-badge','data','/item/LI','row'),field('reason','Handlungsgrund / Erw. 1T','.risk-values .list-value','data','','row'),field('expiry','Ablauf / Restlaufzeit','.risk-expiry','data','','row')]},
    market:{title:'Transfermarkt',selector:'#market-table',parent:'.panel',span:12,rows:'#market-table .market-row',grid:'#market-table',fields:[...heading,...player,field('club','Verein','.table-player .sub','data','/item/Verein','row'),field('position','Position','td:nth-child(2)','data','/item/Position','row'),field('mv','Marktwert','td:nth-child(3)','data','/item/Marktwert','row'),field('change','Erw. 1T','td:nth-child(4)','data','/item/Erw. 1T','row'),field('li','LI','td:nth-child(5) .li-badge','data','/item/LI','row'),field('expiry','Ablauf','td:nth-child(6)','data','/item/Ablauf','row')]}
  };
  function seed(data,mobile=false){
    return {native:true,columns:12,rowHeight:32,gap:18,tiles:Object.entries(defs).map(([key,def],order)=>L.tile({
      id:'standard-'+key,title:def.title,nativeKey:key,order,changed:[],w:mobile?12:def.span,h:3,
      ...(L.sections[key]?{section:key,cardColumns:mobile?1:['transfers','chances'].includes(key)?3:1,cardHeight:220,cardGap:12,cardColor:'#0b1927',cardOpacity:1}:{}),
      elements:def.fields.map(f=>L.element(f.type,{id:key+'-'+f.key,nativeKey:f.key,label:f.label,scope:f.scope,changed:[],source:f.source,text:f.type==='text'?(f.key==='title'||f.key==='label'?def.title:''):'',x:0,y:0,w:100,h:100,fontSize:14}))
    }))};
  }
  function block(doc,def){const n=doc.querySelector(def.selector);return def.parent?n?.closest(def.parent):n;}
  function create(doc,data,send=()=>{}){
    const win=doc.defaultView,shell=doc.querySelector('.app-shell');let layout=null,editor=false,selection={},pending=false,flow=null,overlay=null,disposed=false,dragging=false;
    const restore=[],origins=new Map();
    for(const [key,def]of Object.entries(defs)){const n=block(doc,def);if(n)origins.set(key,{node:n,parent:n.parentNode,next:n.nextSibling});}
    function style(node,key,value){const previous=node.style.getPropertyValue(key);const priority=node.style.getPropertyPriority(key);restore.push(()=>previous?node.style.setProperty(key,previous,priority):node.style.removeProperty(key));node.style.setProperty(key,value,'important');}
    function text(node,value){
      const direct=[...node.childNodes].find(n=>n.nodeType===3&&n.textContent.trim());
      if(direct){const previous=direct.textContent;restore.push(()=>direct.textContent=previous);direct.textContent=value;}
      else{const children=[...node.childNodes];restore.push(()=>node.replaceChildren(...children));node.textContent=value;}
    }
    function imageFallback(row){
      const p=[...(data.report.players||[]),...(data.report.marketPlayers||[])].find(p=>p.image&&p.teamImage);if(!p)return;
      const art=row.querySelector('.player-art');if(!art)return;
      for(const [cls,src]of [['player-cutout',p.image],['club-crest',p.teamImage]]){
        const old=art.querySelector('.'+cls);if(old?.tagName==='IMG'&&old.getAttribute('src'))continue;
        const img=doc.createElement('img');img.className=cls;img.src=src;img.alt='Beispielgrafik';if(old)old.replaceWith(img);else art.append(img);
        restore.push(()=>old?img.replaceWith(old):img.remove());
      }
    }
    function nodesFor(tile,e,rows){const f=defs[tile.nativeKey]?.fields.find(f=>f.key===e.nativeKey);if(!f)return[];const roots=f.scope==='row'?rows:[block(doc,defs[tile.nativeKey])];return roots.flatMap(root=>[...root.querySelectorAll(f.selector)]);}
    function rowItem(tile,node,rows){
      const row=rows.find(r=>r===node||r.contains(node)),id=row?.dataset.playerId;
      const items=L.sectionItems(data,tile.section);return items.find(p=>String(p.Rohdaten?.id??p.Rohdaten?.playerId)===id)||items[rows.indexOf(row)]||L.normalizeItem(data.report.players?.[0]||{},tile.section,data);
    }
    function applyElement(node,e,tile,rows){
      const changes=new Set(e.changed||[]),base=win.getComputedStyle(node),r=node.getBoundingClientRect(),row=rows.find(row=>row===node||row.contains(node));
      const container=(row||block(doc,defs[tile.nativeKey])).getBoundingClientRect();
      const scalar={color:e.color,opacity:e.opacity,'font-size':e.fontSize+'px','font-weight':e.bold?'700':'400','text-align':e.align,'border-radius':e.radius+'px','object-fit':e.fit,'object-position':'50% '+e.imageY+'%'};
      for(const [key,property]of Object.entries({color:'color',opacity:'opacity',fontSize:'font-size',bold:'font-weight',align:'text-align',radius:'border-radius',fit:'object-fit',imageY:'object-position'}))if(changes.has(key))style(node,property,String(scalar[property]));
      if(changes.has('background')||changes.has('backgroundOpacity'))style(node,'background',L.rgba(e.background,e.backgroundOpacity));
      if(changes.has('order')){const z=String(tile.elements.indexOf(e)+1);style(node,'z-index',z);if(base.position==='static')style(node,'position','relative');const art=node.closest('.player-art');if(art)style(art,'z-index',z);}
      if(['x','y','w','h','zoom'].some(k=>changes.has(k))){
        const image=node.tagName==='IMG',transform=base.transform==='none'?'':base.transform;
        const dx=(e.x||0)*container.width/100,dy=(e.y||0)*container.height/100;
        if(!image&&(changes.has('w')||changes.has('h'))){if(base.display==='inline')style(node,'display','inline-block');if(changes.has('w'))style(node,'width',r.width*e.w/100+'px');if(changes.has('h'))style(node,'height',r.height*e.h/100+'px');}
        style(node,'transform',`translate(${dx}px,${dy}px) ${image?`scale(${e.w/100*e.zoom},${e.h/100*e.zoom})`:''} ${transform}`);
      }
      if(changes.has('source')||changes.has('format')||changes.has('text')||changes.has('url')){
        const context={...data,item:tile.section?rowItem(tile,node,rows):null};
        if(e.type==='image'){const src=L.safeImage(e.source?L.valueAt(context,e.source):e.url);if(src){const old=node.getAttribute('src');restore.push(()=>old===null?node.removeAttribute('src'):node.setAttribute('src',old));node.setAttribute('src',src);}}
        else if(e.type==='text'||e.source||changes.has('text'))text(node,e.type==='text'||!e.source?e.text:e.text+L.format(L.valueAt(context,e.source),e.format));
      }
    }
    function redraw(){
      if(disposed||dragging)return;observer.disconnect();overlay?.remove();overlay=null;
      doc.body.classList.toggle('native-editor-active',!!layout&&editor);doc.body.classList.toggle('native-dashboard-active',!!layout);
      doc.body.classList.toggle('dashboard-preview',!!win.KICKBASE_DASHBOARD?.preview&&!layout);
      if(layout&&win.KICKBASE_DASHBOARD?.preview)doc.querySelectorAll('.report-actions button').forEach(button=>button.disabled=false);
      if(layout&&win.KICKBASE_DASHBOARD?.preview)doc.querySelectorAll('img').forEach(img=>img.loading='eager');
      while(restore.length)restore.pop()();
      if(flow){for(const entry of [...origins.values()].reverse())entry.parent.insertBefore(entry.node,entry.next?.parentNode===entry.parent?entry.next:null);flow.remove();flow=null;}
      if(!layout){observer.observe(shell,{childList:true,subtree:true});return;}
      L.enrich(data);
      const tiles=new Map(layout.tiles.filter(t=>t.nativeKey).map(t=>[t.nativeKey,t]));
      if(layout.gap!==18){style(doc.querySelector('.dashboard-grid'),'gap',layout.gap+'px');style(doc.querySelector('.metrics'),'gap',layout.gap+'px');}
      const useFlow=layout.tiles.some(t=>(t.changed||[]).some(k=>['order','w','x','y'].includes(k)));
      if(useFlow){flow=doc.createElement('section');flow.className='native-custom-flow';flow.style.cssText='display:grid;grid-template-columns:repeat('+layout.columns+',minmax(0,1fr));gap:'+layout.gap+'px;margin-top:22px';shell.append(flow);
        style(doc.querySelector('.metrics'),'display','none');style(doc.querySelector('.dashboard-grid'),'display','none');
        for(const tile of [...tiles.values()].sort((a,b)=>a.order-b.order)){const node=block(doc,defs[tile.nativeKey]);if(node){flow.append(node);style(node,'grid-column','span '+Math.min(tile.w,layout.columns));style(node,'margin','0');}}
      }
      for(const [key,def]of Object.entries(defs)){
        const node=block(doc,def),tile=tiles.get(key);if(!node)continue;if(!tile){style(node,'display','none');continue;}
        const changed=new Set(tile.changed||[]),rows=def.rows?[...node.querySelectorAll(def.rows)]:[],grid=def.grid?node.querySelector(def.grid):null;
        if(editor&&rows.length){
          const originalHeight=rows[0].getBoundingClientRect().height;
          if(key==='market'){const table=grid.closest('table'),widths=[...table.querySelectorAll('thead th')].map(n=>n.getBoundingClientRect().width);style(table,'table-layout','fixed');[...table.querySelectorAll('thead th')].forEach((n,i)=>style(n,'width',widths[i]+'px'));}
          imageFallback(rows[0]);rows.slice(1).forEach(row=>style(row,'display','none'));style(rows[0],key==='market'?'height':'min-height',originalHeight+'px');
        }
        if(changed.has('color')||changed.has('opacity'))style(node,'background',L.rgba(tile.color,tile.opacity));
        if(changed.has('h'))style(node,'min-height',tile.h*layout.rowHeight+'px');
        if(changed.has('title')){const title=node.querySelector('.panel-heading h2,.metric-label');if(title)text(title,tile.title);}
        if(grid&&(changed.has('cardColumns')||changed.has('cardGap'))&&key!=='market'){
          style(grid,'display','grid');style(grid,'grid-template-columns','repeat('+tile.cardColumns+',minmax(0,1fr))');style(grid,'gap',tile.cardGap+'px');
        }
        if(grid&&key==='market'&&changed.has('cardColumns')){
          const table=grid.closest('table');style(table,'display','block');style(table.querySelector('thead'),'display','none');style(grid,'display','grid');style(grid,'grid-template-columns','repeat('+tile.cardColumns+',minmax(0,1fr))');style(grid,'gap',tile.cardGap+'px');
          rows.forEach(row=>{style(row,'display','grid');style(row,'grid-template-columns','minmax(0,1fr)');});
        }
        for(const row of rows){
          if(changed.has('cardColor')||changed.has('cardOpacity'))style(row,'background',L.rgba(tile.cardColor,tile.cardOpacity));
          if(changed.has('cardHeight')){style(row,'min-height',tile.cardHeight+'px');if(key==='market')style(row,'height',tile.cardHeight+'px');}
        }
        const present=new Set(tile.elements.map(e=>e.nativeKey).filter(Boolean));
        for(const f of def.fields)if(!present.has(f.key))for(const n of nodesFor(tile,{nativeKey:f.key},rows))style(n,'display','none');
        for(const e of tile.elements){
          if(e.nativeKey){for(const n of nodesFor(tile,e,rows))applyElement(n,e,tile,rows);}
          else{const roots=tile.section?rows:[node];for(const root of roots){const n=L.renderElement(e,{...data,item:tile.section?rowItem(tile,root,rows):null});n.classList.add('native-extra-element');n.dataset.nativeExtra=e.id;if((e.changed||[]).includes('order'))n.style.zIndex=String(tile.elements.indexOf(e)+1);if(win.getComputedStyle(root).position==='static')style(root,'position','relative');root.append(n);restore.push(()=>n.remove());}}
        }
      }
      if(editor)decorate();observer.observe(shell,{childList:true,subtree:true});
    }
    function schedule(){if(!pending){pending=true;win.requestAnimationFrame(()=>{pending=false;redraw();});}}
    const observer=new win.MutationObserver(schedule);
    function snapshot(tile,e,node){
      const c=win.getComputedStyle(node),hex=value=>{const rgb=value.match(/[\d.]+/g)||[255,255,255];return'#'+rgb.slice(0,3).map(v=>Math.round(+v).toString(16).padStart(2,'0')).join('');};
      const result={fontSize:Math.max(8,Math.min(120,parseFloat(c.fontSize)||14)),color:hex(c.color),opacity:+c.opacity,bold:+c.fontWeight>=600,align:['left','center','right'].includes(c.textAlign)?c.textAlign:'left'};
      if(e.type==='image'){result.fit=['contain','cover'].includes(c.objectFit)?c.objectFit:'contain';result.imageY=Math.max(0,Math.min(100,parseFloat(c.objectPosition.split(' ').pop())||0));result.radius=Math.max(0,Math.min(100,parseFloat(c.borderRadius)||0));}
      if(e.type==='text'){const direct=[...node.childNodes].find(n=>n.nodeType===3&&n.textContent.trim());result.text=(direct?.textContent||node.textContent).trim();}
      send({type:'kane-native-select',tileId:tile.id,elementId:e.id,values:result});
    }
    function decorate(){
      overlay=doc.createElement('div');overlay.className='native-edit-overlay';doc.body.append(overlay);
      for(const tile of layout.tiles){const def=defs[tile.nativeKey];if(!def)continue;const node=block(doc,def);if(!node)continue;
        const box=node.getBoundingClientRect(),grip=doc.createElement('button');grip.className='native-block-grip';grip.textContent='⠿ '+tile.title;grip.dataset.nativeTile=tile.id;
        grip.style.cssText=`left:${box.left+win.scrollX}px;top:${Math.max(0,box.top+win.scrollY)}px`;
        grip.onclick=event=>{event.preventDefault();selection={tileId:tile.id,elementId:null};send({type:'kane-native-select',...selection});schedule();};overlay.append(grip);
        grip.onpointerdown=event=>moveGesture(event,tile,node,null);
        if(selection.tileId===tile.id){const e=tile.elements.find(e=>e.id===selection.elementId),rows=def.rows?[...node.querySelectorAll(def.rows)]:[];
          const target=e?.nativeKey?nodesFor(tile,e,rows)[0]:e?[...node.querySelectorAll('[data-native-extra]')].find(n=>n.dataset.nativeExtra===e.id):node;
          if(target){const raw=target.getBoundingClientRect(),container=(e&&def.rows?rows[0]:node)?.getBoundingClientRect()||box;
            if(e)snapshot(tile,e,target);
            const clipped={left:Math.max(raw.left,container.left),top:Math.max(raw.top,container.top),right:Math.min(raw.right,container.right),bottom:Math.min(raw.bottom,container.bottom)};
            const outline=doc.createElement('div');outline.className='native-selection-frame'+(e?' native-element-frame':'');outline.style.cssText=`left:${clipped.left+win.scrollX}px;top:${clipped.top+win.scrollY}px;width:${Math.max(16,clipped.right-clipped.left)}px;height:${Math.max(16,clipped.bottom-clipped.top)}px`;
            const resize=doc.createElement('button');resize.className='native-resize-handle';resize.title=e?'Element skalieren':'Hauptkachel skalieren';outline.append(resize);overlay.append(outline);resize.onpointerdown=event=>moveGesture(event,tile,target,e,true);
            if(e)outline.onpointerdown=event=>{if(event.target!==resize)moveGesture(event,tile,target,e);};
          }
        }
      }
    }
    function moveGesture(event,tile,node,e,resize=false){
      if(event.button!==0)return;event.preventDefault();event.stopPropagation();
      const start={x:event.clientX,y:event.clientY},target=event.currentTarget instanceof win.Element?event.currentTarget:node,def=defs[tile.nativeKey],row=def.rows?[...block(doc,def).querySelectorAll(def.rows)].find(row=>row===node||row.contains(node)):null;
      const rect=(row||block(doc,def)).getBoundingClientRect(),original=e?{x:e.x,y:e.y,w:e.w,h:e.h}:{w:tile.w,h:tile.h};let dx=0,dy=0;
      dragging=true;target.setPointerCapture(event.pointerId);
      const move=ev=>{dx=ev.clientX-start.x;dy=ev.clientY-start.y;};
      const finish=()=>{dragging=false;target.removeEventListener('pointermove',move);target.removeEventListener('pointerup',finish);target.removeEventListener('pointercancel',cancel);
        if(Math.abs(dx)+Math.abs(dy)>3){
          if(e)send({type:'kane-native-change',tileId:tile.id,elementId:e.id,patch:resize?{w:Math.max(1,Math.min(600,original.w+dx/Math.max(1,node.getBoundingClientRect().width)*100)),h:Math.max(1,Math.min(600,original.h+dy/Math.max(1,node.getBoundingClientRect().height)*100))}:{x:Math.max(-300,Math.min(300,original.x+dx/rect.width*100)),y:Math.max(-300,Math.min(300,original.y+dy/rect.height*100))}});
          else if(resize)send({type:'kane-native-change',tileId:tile.id,patch:{w:Math.max(1,Math.min(layout.columns,original.w+Math.round(dx/shell.clientWidth*layout.columns))),h:Math.max(1,Math.min(30,original.h+Math.round(dy/layout.rowHeight)))}});
          else{const ordered=[...layout.tiles].sort((a,b)=>a.order-b.order),index=ordered.indexOf(tile);send({type:'kane-native-reorder',tileId:tile.id,index:Math.max(0,Math.min(ordered.length-1,index+(dy>0?1:-1)))});}
        }
        schedule();
      };
      const cancel=()=>{dx=dy=0;finish();};target.addEventListener('pointermove',move);target.addEventListener('pointerup',finish);target.addEventListener('pointercancel',cancel);
    }
    function click(event){if(!editor||event.target.closest('.native-edit-overlay'))return;
      for(const tile of layout?.tiles||[]){const def=defs[tile.nativeKey],node=def&&block(doc,def);if(!node?.contains(event.target))continue;
        event.preventDefault();event.stopPropagation();const rows=def.rows?[...node.querySelectorAll(def.rows)]:[];
        const matches=tile.elements.flatMap(e=>(e.nativeKey?nodesFor(tile,e,rows):[...node.querySelectorAll('[data-native-extra]')].filter(n=>n.dataset.nativeExtra===e.id)).map(n=>({e,n}))).filter(({n})=>n===event.target||n.contains(event.target));
        const match=matches.sort((a,b)=>a.n.getBoundingClientRect().width*a.n.getBoundingClientRect().height-b.n.getBoundingClientRect().width*b.n.getBoundingClientRect().height)[0];
        if(match){snapshot(tile,match.e,match.n);selection={tileId:tile.id,elementId:match.e.id};if(match.e.type==='image')moveGesture(event,tile,match.n,match.e);}
        else{selection={tileId:tile.id,elementId:null};send({type:'kane-native-select',...selection});}schedule();return;
      }
    }
    doc.addEventListener('pointerdown',click,true);doc.addEventListener('click',event=>{if(editor&&!event.target.closest('.native-edit-overlay')){event.preventDefault();event.stopPropagation();}},true);win.addEventListener('resize',schedule);
    return {update(next,options={}){layout=next;editor=!!options.editor;selection=options.selection||selection;redraw();},dispose(){disposed=true;layout=null;observer.disconnect();overlay?.remove();while(restore.length)restore.pop()();doc.removeEventListener('pointerdown',click,true);win.removeEventListener('resize',schedule);}};
  }
  return {defs,seed,create};
})();
