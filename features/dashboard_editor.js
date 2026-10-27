'use strict';
(async () => {
  const L=window.KaneLayout, $=id=>document.getElementById(id), canvas=$('editor-canvas');
  let data={report:JSON.parse($('data').textContent||'{}'),api:{}}, design, mode='desktop', tileId=null, elementId=null;
  let dirty=false, preview=false, undo=[], redo=[], catalog=[], busy=false;
  const current=()=>design[mode], selectedTile=()=>current().tiles.find(t=>t.id===tileId), selectedElement=()=>selectedTile()?.elements.find(e=>e.id===elementId);
  const status=(text,error=false)=>{$('editor-status').textContent=text;$('editor-status').className=error?'editor-error':'';};
  const request=(path,body)=>L.json(path,{method:'POST',headers:{'Content-Type':'application/json','X-Advisor-Token':window.KICKBASE_DASHBOARD.csrf},body:JSON.stringify(body)});
  const remember=()=>{undo.push(JSON.stringify(design));if(undo.length>40)undo.shift();redo=[];};
  const changed=()=>{dirty=true;$('undo').disabled=!undo.length;$('redo').disabled=!redo.length;status('Ungespeicherte Änderungen · '+(mode==='mobile'?'Mobil':'Desktop'));};
  function edit(action){if(busy)return;remember();action();changed();render();}
  function overlaps(a,b){return a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;}
  function makeRoom(moved){
    const placed=[moved];
    for(const tile of current().tiles.filter(t=>t!==moved).sort((a,b)=>a.y-b.y||a.x-b.x)){
      let hit;while((hit=placed.find(t=>overlaps(t,tile))))tile.y=hit.y+hit.h;
      placed.push(tile);
    }
  }
  function appendTile(tile){tile.y=Math.max(0,...current().tiles.map(t=>t.y+t.h));tile.w=Math.min(tile.w,current().columns);current().tiles.push(tile);tileId=tile.id;elementId=null;}
  function select(t,e=null){tileId=t; elementId=e; updateSelection();properties();sourceOptions();}
  function updateSelection(){
    canvas.querySelectorAll('.layout-tile').forEach(n=>n.classList.toggle('editor-tile-selected',n.dataset.tile===tileId));
    canvas.querySelectorAll('.layout-element').forEach(n=>{const selected=n.dataset.element===elementId&&n.closest('.layout-tile').dataset.tile===tileId;
      n.classList.toggle('editor-element-selected',selected);n.querySelector('.resize-handle')?.remove();
      if(selected&&!preview){const handle=document.createElement('button');handle.className='resize-handle';handle.setAttribute('aria-label','Elementgröße ziehen');n.append(handle);}});
  }
  function renderCanvas(){
    canvas.classList.toggle('editor-editing',!preview);document.body.classList.toggle('editor-preview',preview);
    L.render(canvas,current(),data,(node,t)=>{
      const tools=document.createElement('div');tools.className='editor-tile-tools';
      const grip=document.createElement('button');grip.className='tile-grip';grip.textContent='⠿ '+t.title;grip.title='Kachel verschieben';tools.append(grip);node.append(tools);
      const handle=document.createElement('button');handle.className='resize-handle tile-resize';handle.setAttribute('aria-label','Kachelgröße ziehen');node.append(handle);
    });updateSelection();
  }
  function render(){
    $('mode-desktop').setAttribute('aria-pressed',String(mode==='desktop'));$('mode-mobile').setAttribute('aria-pressed',String(mode==='mobile'));
    $('design-enabled').checked=design.enabled;
    $('grid-columns').value=current().columns;$('grid-row-height').value=current().rowHeight;$('grid-gap').value=current().gap;
    $('stage-label').textContent=(mode==='mobile'?'Mobil':'Desktop')+' · '+$('preview-width').value+' px';
    $('preview').textContent=preview?'Bearbeiten':'Vorschau';$('undo').disabled=!undo.length;$('redo').disabled=!redo.length;
    renderCanvas();$('tile-list').replaceChildren();current().tiles.forEach(t=>{const b=document.createElement('button');b.textContent=t.title;b.setAttribute('aria-pressed',String(t.id===tileId));b.onclick=()=>select(t.id);$('tile-list').append(b);});properties();sourceOptions();
  }
  function field(parent,label,value,callback,options={}){
    const wrap=document.createElement('label'), name=document.createElement('span');name.textContent=label;wrap.append(name);
    const input=document.createElement(options.choices?'select':'input');
    if(options.choices){for(const [key,title]of options.choices){const option=document.createElement('option');option.value=key;option.textContent=title;input.append(option);}}
    else {input.type=options.type||'text';for(const k of ['min','max','step'])if(options[k]!==undefined)input[k]=options[k];}
    input.dataset.property=options.key||label;
    if(input.type==='checkbox')input.checked=value;else input.value=value??'';
    input.onchange=()=>{const v=input.type==='checkbox'?input.checked:input.type==='number'||input.type==='range'?Number(input.value):input.value;
      if(!input.checkValidity()){input.reportValidity();return;}edit(()=>callback(v));};
    wrap.append(input);parent.append(wrap);return input;
  }
  function button(parent,label,action){const b=document.createElement('button');b.textContent=label;b.onclick=action;parent.append(b);return b;}
  function divider(parent){const hr=document.createElement('hr');hr.className='property-divider';parent.append(hr);}
  const collections=()=>catalog.filter(item=>Array.isArray(item.value));
  function properties(){
    const root=$('properties');root.replaceChildren();const t=selectedTile();
    if(!t){root.textContent='Kachel auswählen oder hinzufügen.';return;}
    field(root,'Kacheltitel',t.title,v=>t.title=v,{key:'tile-title'});
    field(root,'Kachelfarbe',t.color,v=>t.color=v,{type:'color',key:'tile-color'});
    field(root,'Kachel-Deckkraft',t.opacity,v=>t.opacity=v,{type:'range',min:0,max:1,step:.01,key:'tile-opacity'});
    for(const [key,label,min,max]of [['x','Spalte (ab 0)',0,current().columns-t.w],['y','Zeile (ab 0)',0,1000],['w','Breite (Spalten)',1,current().columns],['h','Höhe (Zeilen)',1,30]]){
      field(root,label,t[key],v=>{t[key]=v;t.x=Math.min(t.x,current().columns-t.w);makeRoom(t);},{type:'number',min,max,step:1,key:'tile-'+key});
    }
    if(t.section){
      const note=document.createElement('p');note.className='editor-hint';note.textContent='Eine Vorlage für alle Spieler dieses Bereichs. Im Dashboard: '+L.sectionItems(data,t.section).length+' passende Datensätze. Die Kachelanzahl wird automatisch bestimmt.';root.append(note);
      field(root,'Spielerkacheln je Zeile',t.cardColumns,v=>t.cardColumns=v,{type:'number',min:1,max:8,step:1,key:'cardColumns'});
      field(root,'Spielerkachelhöhe (px)',t.cardHeight,v=>{t.cardHeight=v;t.h=Math.ceil((v+76+current().gap)/(current().rowHeight+current().gap));makeRoom(t);},{type:'number',min:80,max:600,step:1,key:'cardHeight'});
      field(root,'Spielerkachelabstand (px)',t.cardGap,v=>t.cardGap=v,{type:'number',min:0,max:40,step:1,key:'cardGap'});
      field(root,'Spielerkachelfarbe',t.cardColor,v=>t.cardColor=v,{type:'color',key:'cardColor'});
      field(root,'Spielerkachel-Deckkraft',t.cardOpacity,v=>t.cardOpacity=v,{type:'range',min:0,max:1,step:.01,key:'cardOpacity'});
    }else{
    const rows=collections();field(root,'Datensatz-Liste',t.collection,v=>{t.collection=v;const entries=L.valueAt(data,v);t.record=entries?.length?L.rowKey(entries[0],0):'';},
      {choices:[['','Kein Spieler / Datensatz'],...rows.map(c=>[c.path,c.label])],key:'collection'});
    const entries=L.valueAt(data,t.collection);
    if(Array.isArray(entries))field(root,'Datensatz',t.record,v=>t.record=v,{choices:entries.map((r,i)=>[L.rowKey(r,i),String(r?.name||r?.playerName||r?.id||'Eintrag '+(i+1))]),key:'record'});
    }
    const actions=document.createElement('div');actions.className='editor-buttons';root.append(actions);
    if(!t.section)button(actions,'Kachel duplizieren',()=>edit(()=>{const copy=L.clone(t);copy.id=L.id();copy.elements.forEach(e=>e.id=L.id());appendTile(copy);}));
    button(actions,'Kachel löschen',()=>edit(()=>{current().tiles=current().tiles.filter(v=>v!==t);tileId=null;elementId=null;}));
    divider(root);
    const elements=document.createElement('div');elements.className='property-elements';root.append(elements);
    t.elements.forEach((e,i)=>{const label=e.source.startsWith('/item/')?e.source.slice(6).replace(/~1/g,'/').replace(/~0/g,'~'):e.text||e.source||e.type;const b=button(elements,(i+1)+'. '+label.slice(0,40),()=>select(t.id,e.id));b.setAttribute('aria-pressed',String(e.id===elementId));});
    const add=document.createElement('div');add.className='editor-buttons';root.append(add);
    for(const[type,label]of [['text','+ Text'],['data','+ Daten'],['image','+ Grafik']])button(add,label,()=>edit(()=>{const e=L.element(type);t.elements.push(e);elementId=e.id;}));
    const e=selectedElement();if(!e)return;divider(root);
    field(root,e.type==='data'?'Text vor dem Wert':e.type==='image'?'Bildbeschreibung':'Text',e.text,v=>e.text=v,{key:'text'});
    if(e.type!=='text'){
      if(t.section)field(root,'Platzhalter',e.source,v=>e.source=v,{key:'source',choices:[['','Kein Platzhalter'],...templateFields(t).map(f=>[f.path,f.label]) ,...(!e.source.startsWith('/item/')&&e.source?[[e.source,'Globale Quelle']]:[])]});
      else field(root,'Datenpfad',e.source,v=>e.source=v,{key:'source'});
      if(e.type==='data')field(root,'Format',e.format,v=>e.format=v,{key:'format',choices:[['auto','Originalwert'],['number','Zahl'],['euro','Euro'],['million','Millionen €'],['percent','Prozent'],['date','Datum / Uhrzeit']]});
    }
    if(e.type==='image'){
      field(root,'Bildadresse',e.url,v=>e.url=v,{key:'url'});
      button(root,'Grafik hochladen …',()=>$('image-file').click());
      field(root,'Bildanpassung',e.fit,v=>e.fit=v,{key:'fit',choices:[['contain','Vollständig'],['cover','Fläche ausfüllen']]});
      field(root,'Zoom',e.zoom,v=>e.zoom=v,{type:'number',min:1,max:5,step:.1,key:'zoom'});
      field(root,'Bildanker vertikal (%)',e.imageY,v=>e.imageY=v,{type:'number',min:0,max:100,key:'imageY'});
    }else{
      field(root,'Schriftfarbe',e.color,v=>e.color=v,{type:'color',key:'color'});
      field(root,'Schriftgröße (px)',e.fontSize,v=>e.fontSize=v,{type:'number',min:8,max:120,key:'fontSize'});
      field(root,'Fett',e.bold,v=>e.bold=v,{type:'checkbox',key:'bold'});
      field(root,'Ausrichtung',e.align,v=>e.align=v,{key:'align',choices:[['left','Links'],['center','Mitte'],['right','Rechts']]});
    }
    field(root,'Element-Deckkraft',e.opacity,v=>e.opacity=v,{type:'range',min:0,max:1,step:.01,key:'opacity'});
    field(root,'Element-Hintergrund',e.background,v=>e.background=v,{type:'color',key:'background'});
    field(root,'Hintergrund-Deckkraft',e.backgroundOpacity,v=>e.backgroundOpacity=v,{type:'range',min:0,max:1,step:.01,key:'backgroundOpacity'});
    field(root,'Rundung (px)',e.radius,v=>e.radius=v,{type:'number',min:0,max:100,key:'radius'});
    for(const[key,label]of [['x','Links (%)'],['y','Oben (%)'],['w','Breite (%)'],['h','Höhe (%)']])field(root,label,e[key],v=>{
      e[key]=v;e.x=Math.min(e.x,100-e.w);e.y=Math.min(e.y,100-e.h);e.w=Math.min(e.w,100-e.x);e.h=Math.min(e.h,100-e.y);
    },{type:'number',min:key==='w'||key==='h'?1:0,max:100,step:.1,key});
    const ea=document.createElement('div');ea.className='editor-buttons';root.append(ea);
    button(ea,'Nach vorne',()=>edit(()=>{t.elements=t.elements.filter(v=>v!==e);t.elements.push(e);}));
    button(ea,'Nach hinten',()=>edit(()=>{t.elements=t.elements.filter(v=>v!==e);t.elements.unshift(e);}));
    button(ea,'Duplizieren',()=>edit(()=>{const copy=L.clone(e);copy.id=L.id();copy.x=Math.min(100-copy.w,copy.x+3);copy.y=Math.min(100-copy.h,copy.y+3);t.elements.push(copy);elementId=copy.id;}));
    button(ea,'Element löschen',()=>edit(()=>{t.elements=t.elements.filter(v=>v!==e);elementId=null;}));
  }
  function templateFields(t){
    const fields=L.aliases.map(name=>({path:'/item/'+L.escapeToken(name),label:name,value:'{'+name+'}'})),seen=new Set(fields.map(f=>f.path));
    function walk(value,path,label,depth=0){if(depth>24)return;if(value&&typeof value==='object'&&!Array.isArray(value)){for(const [key,v]of Object.entries(value))walk(v,path+'/'+L.escapeToken(key),label+' › '+key,depth+1);}else if(!seen.has(path)){seen.add(path);fields.push({path,label,value:'{'+label+'}'});}}
    for(const item of L.sectionItems(data,t.section))walk(item.Rohdaten,'/item/Rohdaten','Weitere Spielerdaten');return fields;
  }
  function buildCatalog(){
    L.enrich(data);catalog=[];
    function walk(value,path,label,depth=0){
      if(depth>32)return;
      if(value==null||typeof value!=='object'||Array.isArray(value))catalog.push({path,label,value});
      if(value&&typeof value==='object')Object.entries(value).forEach(([key,v])=>{
        const name=Array.isArray(value)?'['+(v?.name||v?.playerName||key)+']':key;
        walk(v,path+'/'+L.escapeToken(key),label+' › '+name,depth+1);
      });
    }
    walk(data.dashboard,'/dashboard','Dashboard-Kennzahlen');walk(data.report,'/report','Report');walk(data.api,'/api','API');
  }
  function sourceOptions(){
    if(!design)return;const t=selectedTile(),ctx=t?L.context(data,t):data;
    const options=t?.section?[...templateFields(t),...catalog.filter(c=>!/^\/(report\/(players|marketPlayers)|api\/)/.test(c.path))]:catalog.slice();
    function walkItem(value,path,label){if(value&&typeof value==='object'){Object.entries(value).forEach(([k,v])=>walkItem(v,path+'/'+L.escapeToken(k),label+' › '+k));}else options.unshift({path,label,value});}
    if(ctx.item&&!t?.section)walkItem(ctx.item,'/item','Gewählter Datensatz');
    const query=$('source-search').value.toLocaleLowerCase('de');const selected=$('source-picker').value||selectedElement()?.source;
    const filtered=options.filter(c=>(c.label+' '+String(c.value)).toLocaleLowerCase('de').includes(query));
    $('source-picker').replaceChildren();for(const c of filtered.slice(0,600)){const opt=document.createElement('option');opt.value=c.path;opt.textContent=c.label+' = '+(Array.isArray(c.value)?'Liste mit '+c.value.length+' Einträgen':L.format(c.value,'auto').slice(0,100));$('source-picker').append(opt);}
    if([...$('source-picker').options].some(o=>o.value===selected))$('source-picker').value=selected;
    $('source-status').textContent=options.length+' Datenfelder verfügbar'+(filtered.length>600?' · Suche eingrenzen (erste 600 Treffer angezeigt).':'.');showSource();
  }
  function showSource(){const path=$('source-picker').value,t=selectedTile();$('source-value').textContent=path?(t?.section&&path.startsWith('/item/')?'Platzhalter: '+path.slice(6).replace(/~1/g,'/').replace(/~0/g,'~')+' · Wird je Spielerkachel automatisch ersetzt.':'Pfad: '+path+' · Wert: '+L.format(L.valueAt(t?L.context(data,t):data,path),'auto').slice(0,500)):$('source-picker').options.length?'Eine Datenquelle aus der Liste auswählen.':'Keine passende Quelle im aktuellen Datenstand.';}
  async function refresh(){
    $('refresh-sources').disabled=true;status('Datenquellen werden aktualisiert …');
    try{data.report=await L.json('api/dashboard-data');const errors=await L.liveData(data);buildCatalog();render();status(errors.length?'Report geladen; einzelne Live-Quellen nicht verfügbar: '+errors.join(' · '):(dirty?'Daten aktualisiert · Entwurf noch nicht gespeichert.':'Datenquellen aktualisiert.'));}
    catch(error){status(error.message,true);}finally{$('refresh-sources').disabled=false;}
  }
  function gesture(event){
    if(preview||busy||event.button!==0)return;
    const node=event.target.closest('.layout-tile');if(!node)return;
    const t=current().tiles.find(t=>t.id===node.dataset.tile), en=event.target.closest('.layout-element');
    const isTile=!!event.target.closest('.tile-grip,.tile-resize'), resize=!!event.target.closest('.resize-handle');
    if(!isTile&&!en){select(t.id);return;}
    const e=en?t.elements.find(e=>e.id===en.dataset.element):null;
    select(t.id,isTile?null:e?.id);event.preventDefault();
    const target=isTile?node:en, rect=node.querySelector('.tile-surface').getBoundingClientRect();
    const start={x:event.clientX,y:event.clientY,value:L.clone(isTile?t:e)}, before=JSON.stringify(design);
    const cw=(canvas.clientWidth-(current().columns-1)*current().gap)/current().columns, rh=current().rowHeight+current().gap;
    let moved=false;node.setPointerCapture(event.pointerId);
    const move=ev=>{
      let dx=ev.clientX-start.x,dy=ev.clientY-start.y;if(Math.abs(dx)+Math.abs(dy)<3&&!moved)return;moved=true;
      const obj=isTile?t:e,v=start.value;
      if(isTile){dx=Math.round(dx/(cw+current().gap));dy=Math.round(dy/rh);
        if(resize){obj.w=Math.max(1,Math.min(current().columns-obj.x,v.w+dx));obj.h=Math.max(1,Math.min(30,v.h+dy));}
        else{obj.x=Math.max(0,Math.min(current().columns-obj.w,v.x+dx));obj.y=Math.max(0,Math.min(1000,v.y+dy));}
        L.gridStyle(canvas,current());L.positionTile(target,obj);
      }else{dx=100*dx/rect.width;dy=100*dy/rect.height;
        if(resize){obj.w=Math.max(1,Math.min(100-obj.x,v.w+dx));obj.h=Math.max(1,Math.min(100-obj.y,v.h+dy));}
        else{obj.x=Math.max(0,Math.min(100-obj.w,v.x+dx));obj.y=Math.max(0,Math.min(100-obj.h,v.y+dy));}
        for(const key of ['x','y','w','h'])obj[key]=Math.round(obj[key]*100)/100;L.positionElement(target,obj);
      }
    };
    const finish=ev=>{node.removeEventListener('pointermove',move);node.removeEventListener('pointerup',finish);node.removeEventListener('pointercancel',cancel);
      if(node.hasPointerCapture(event.pointerId))node.releasePointerCapture(event.pointerId);
      if(moved){undo.push(before);if(undo.length>40)undo.shift();redo=[];if(isTile)makeRoom(t);changed();}render();};
    const cancel=ev=>{design=JSON.parse(before);moved=false;finish(ev);};
    node.addEventListener('pointermove',move);node.addEventListener('pointerup',finish);node.addEventListener('pointercancel',cancel);
  }
  canvas.addEventListener('pointerdown',gesture);
  $('source-search').oninput=sourceOptions;$('source-picker').onchange=showSource;
  $('apply-source').onclick=()=>{const e=selectedElement(),source=$('source-picker').value;if(!e||!source){status('Zuerst ein Daten- oder Bildelement und eine Quelle auswählen.',true);return;}if(e.type==='text'){status('Bitte ein Daten- oder Bildelement wählen.',true);return;}edit(()=>e.source=source);};
  $('add-source').onclick=()=>{const t=selectedTile(),source=$('source-picker').value;if(!t||!source){status('Zuerst eine Kachel und eine Quelle auswählen.',true);return;}edit(()=>{const e=L.element('data',{source});t.elements.push(e);elementId=e.id;});};
  $('add-tile').onclick=()=>edit(()=>appendTile(L.tile({w:mode==='mobile'?current().columns:Math.min(3,current().columns),elements:[L.element('text')]})));
  $('add-section').onclick=()=>{const section=$('section-type').value;if(current().tiles.some(t=>t.section===section)){status('Für diesen Hauptbereich gibt es bereits eine Vorlage. Bitte links auswählen.',true);return;}edit(()=>appendTile(L.sectionTile(section,mode==='mobile')));};
  $('dashboard-template').onclick=()=>{if(confirm('Diese Ansicht durch die fünf Hauptbereiche des bestehenden Dashboards ersetzen? Ungespeicherte Änderungen lassen sich danach rückgängig machen.'))edit(()=>{design[mode]=L.seed(data,mode==='mobile');tileId=null;elementId=null;});};
  for(const m of ['desktop','mobile'])$('mode-'+m).onclick=()=>{mode=m;tileId=current().tiles.find(t=>t.section)?.id||null;elementId=null;$('preview-width').value=m==='mobile'?390:1200;canvas.style.width=$('preview-width').value+'px';render();};
  $('preview-width').onchange=()=>{const width=Math.max(280,Math.min(1920,Number($('preview-width').value)||390));$('preview-width').value=width;canvas.style.width=width+'px';$('stage-label').textContent=(mode==='mobile'?'Mobil':'Desktop')+' · '+width+' px';};
  $('design-enabled').onchange=()=>edit(()=>design.enabled=$('design-enabled').checked);
  for(const [input,key]of [['grid-columns','columns'],['grid-row-height','rowHeight'],['grid-gap','gap']])$(input).onchange=()=>{
    if(!$(input).checkValidity()){$(input).reportValidity();return;}edit(()=>{current()[key]=Number($(input).value);if(key==='columns'){
      current().tiles.forEach(t=>{t.w=Math.min(t.w,current().columns);t.x=Math.min(t.x,current().columns-t.w);});
      const placed=[];for(const t of current().tiles){let hit;while((hit=placed.find(p=>overlaps(p,t))))t.y=hit.y+hit.h;placed.push(t);}
    }});
  };
  $('undo').onclick=()=>{if(busy||!undo.length)return;redo.push(JSON.stringify(design));design=JSON.parse(undo.pop());changed();render();};
  $('redo').onclick=()=>{if(busy||!redo.length)return;undo.push(JSON.stringify(design));design=JSON.parse(redo.pop());changed();render();};
  $('preview').onclick=()=>{preview=!preview;render();};
  $('save-design').onclick=async()=>{if(busy)return;busy=true;$('save-design').disabled=true;status('Layout wird gespeichert …');
    // Disable editing during the request so the response cannot overwrite a newer local edit.
    const controls=[...document.querySelectorAll('.editor-workspace input,.editor-workspace button,.editor-workspace select,.editor-header input,.editor-modes button,#preview')];
    const states=controls.map(c=>c.disabled);controls.forEach(c=>c.disabled=true);canvas.inert=true;
    try{const saved=await request('api/dashboard-layout',design);design=saved;dirty=false;undo=[];redo=[];status('Beide Ansichten gespeichert. '+(design.enabled?'Mein Layout ist im Dashboard aktiv.':'Aktuell bleibt die Standardansicht aktiv.'));}
    catch(error){status(error.message,true);}finally{controls.forEach((c,i)=>c.disabled=states[i]);canvas.inert=false;busy=false;$('save-design').disabled=false;render();}};
  $('export-design').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(design,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='kickbase-dashboard-layout.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  $('import-design').onclick=()=>$('import-file').click();
  $('import-file').onchange=async()=>{const file=$('import-file').files[0];if(!file)return;try{if(file.size>1_800_000)throw new Error('Layout-Datei ist zu groß.');
    const imported=await request('api/dashboard-layout/validate',JSON.parse(await file.text()));edit(()=>{imported.revision=design.revision;design=imported;for(const m of ['desktop','mobile'])design[m] ||= L.seed(data,m==='mobile');tileId=null;elementId=null;});status('Layout importiert. Zum Übernehmen speichern.');
    }catch(error){status('Import fehlgeschlagen: '+error.message,true);}finally{$('import-file').value='';}};
  $('copy-layout').onclick=()=>{if(!confirm('Aktuelles '+(mode==='mobile'?'Mobil':'Desktop')+'-Layout mit der anderen Ansicht ersetzen?'))return;
    edit(()=>{const source=L.clone(design[mode==='mobile'?'desktop':'mobile']);design[mode]=source;tileId=null;elementId=null;});};
  $('reset-layout').onclick=()=>{if(confirm('Diese Ansicht auf die Vorlagen zurücksetzen?'))edit(()=>{design[mode]=L.seed(data,mode==='mobile');tileId=null;elementId=null;});};
  $('image-file').onchange=async()=>{const file=$('image-file').files[0],e=selectedElement();if(!file||!e)return;
    try{if(!['image/png','image/jpeg','image/webp','image/gif'].includes(file.type)||file.size>10_000_000)throw new Error('Bitte PNG, JPEG, WebP oder GIF bis 10 MB wählen.');
      const img=await createImageBitmap(file);try{const c=document.createElement('canvas');const scale=Math.min(1,1000/Math.max(img.width,img.height));c.width=Math.max(1,Math.round(img.width*scale));c.height=Math.max(1,Math.round(img.height*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);
        let encoded=c.toDataURL('image/webp',.8);if(encoded.length>250000)encoded=c.toDataURL('image/webp',.45);if(encoded.length>250000)throw new Error('Grafik ist zu detailreich. Bitte eine kleinere Datei wählen.');
        edit(()=>{e.url=encoded;e.source='';});status('Grafik im Entwurf hinterlegt. Zum Übernehmen speichern.');
      }finally{img.close();}
    }catch(error){status(error.message,true);}finally{$('image-file').value='';}};
  $('refresh-sources').onclick=refresh;
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  try{design=await L.json('api/dashboard-layout');const fresh=!design.desktop&&!design.mobile;
    design.desktop ||= L.seed(data);design.mobile ||= L.seed(data,true);buildCatalog();
    for(const [key,title]of Object.entries(L.sections)){const option=document.createElement('option');option.value=key;option.textContent=title;$('section-type').append(option);}tileId=current().tiles.find(t=>t.section)?.id||null;render();
    status(fresh?'Bereichsvorlagen geladen. Je Hauptbereich eine Spielerkachel mit Platzhaltern gestalten und speichern.':current().tiles.some(t=>t.section)?'Gespeichertes Layout mit Bereichsvorlagen geladen.':'Gespeichertes Layout geladen. Über „Bestehendes Dashboard als Vorlage“ die fünf Bereichsvorlagen laden.');
    const errors=await L.liveData(data);await Promise.all([L.boundData(data,design.desktop),L.boundData(data,design.mobile)]);buildCatalog();properties();sourceOptions();
    if(errors.length)$('source-status').textContent+=' Einige API-Quellen sind momentan nicht verfügbar; der Report bleibt nutzbar.';
  }catch(error){status('Editor konnte nicht geladen werden: '+error.message,true);document.querySelectorAll('button,input,select').forEach(c=>c.disabled=true);}
})();
