const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true}),origin=process.env.EDITOR_TEST_URL,errors=[];
  const context=await browser.newContext({viewport:{width:1800,height:1000}});
  await context.route('https://editor.test/**',r=>r.fulfill({contentType:'image/svg+xml',body:r.request().url().includes('crest')?'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="48" fill="#245aa5" stroke="#df2947" stroke-width="15"/></svg>':'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120"><ellipse cx="50" cy="40" rx="24" ry="30" fill="#dab590"/><path d="M5 120V95Q50 65 95 95V120Z" fill="#e32945"/></svg>'}));
  const art={image:'https://editor.test/player.png',teamImage:'https://editor.test/crest.png'};
  const transfers=[{...art,playerId:'kane',playerName:'Harry Kane',marketValue:10001,price:11001,overpay:1000,from:'Kickbase',to:'Sebastian',transferredAt:'2026-10-27T10:00:00Z'},
    {...art,playerId:'kimmich',playerName:'Joshua Kimmich',marketValue:20000,price:22000,isKickbaseSale:true,profitLoss:500,from:'Johannes',to:'Kickbase',transferredAt:'2026-10-27T09:00:00Z'}];
  const mocks={'manager-budgets':{managers:[{name:'Sebastian',cash:11480895,squadValue:100000000,buyingPower:44480895}]},'recent-transfers':{transfers,fetchedAt:'2026-10-27T12:00:00Z'},'squad-value-history':{series:[{date:'2026-10-25',value:123000000},{date:'2026-10-26',value:124800000}]},'current-lineup':{players:[]}};
  await context.route('**/api/**',r=>{const key=new URL(r.request().url()).pathname.replace('/api/','');return mocks[key]?r.fulfill({contentType:'application/json',body:JSON.stringify(mocks[key])}):r.continue();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const prop=key=>page.locator('[data-property="'+key+'"]');const value=async(key,v)=>{await prop(key).fill(String(v));await prop(key).dispatchEvent('change');};
  const frame=()=>page.frameLocator('#native-editor-frame'),preview=()=>page.frameLocator('#dashboard-preview-frame');
  const selectTile=async title=>page.locator('#tile-list button').filter({hasText:title}).first().click();
  const selectElement=async label=>page.locator('.property-elements button').filter({hasText:new RegExp('\\. '+label+'$')}).click();
  const drag=async(loc,dx,dy)=>{await loc.scrollIntoViewIfNeeded();const box=await loc.boundingBox();assert(box);await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+dx,box.y+box.height/2+dy,{steps:8});await page.mouse.up();};
  try{
    await page.goto(origin+'/editor');await frame().locator('.native-block-grip').nth(9).waitFor();
    assert.equal(await page.locator('#tile-list button').count(),10,'Every standard block is editable');
    for(const sel of ['#recent-transfers .recent-transfer-card','#top-chances .chance','#roster-movers .roster-player','#timing-risks .risk-player','#market-table .market-row'])assert.equal(await frame().locator(sel+':visible').count(),1,'One template per player section: '+sel);
    await page.waitForFunction(()=>[...document.querySelector('#native-editor-frame').contentDocument.querySelectorAll('.roster-player img')].some(n=>n.complete&&n.naturalWidth>0));
    const baseline=await context.newPage();await baseline.setViewportSize({width:1480,height:1000});baseline.on('pageerror',e=>errors.push(e.message));await baseline.goto(origin+'/');await baseline.locator('#recent-transfers .recent-transfer-card').nth(1).waitFor();
    const geometry=locator=>locator.evaluate(n=>{const r=n.getBoundingClientRect(),c=getComputedStyle(n);return{w:r.width,h:r.height,font:c.fontSize,color:c.color,bg:c.background,padding:c.padding,border:c.borderRadius};});
    for(const sel of ['.metric-budget','.metric-squad','.metric-forecast','.value-history','.manager-budget-panel','#recent-transfers .recent-transfer-card:first-child','#roster-movers .roster-player:first-child'])assert.deepEqual(await geometry(frame().locator(sel)),await geometry(baseline.locator(sel)),'Original styling: '+sel);
    // A pristine preview must use the original DOM and match the standard page.
    await page.bringToFront();await page.locator('#preview').click();await preview().locator('#recent-transfers .recent-transfer-card').nth(1).waitFor();
    for(const sel of ['.metric-budget','.metric-squad','.value-history','.manager-budget-panel','.recent-transfers-panel','.roster-panel','.action-panel'])assert.deepEqual(await geometry(preview().locator(sel)),await geometry(baseline.locator(sel)),'Pristine preview matches standard: '+sel);
    // Compare complete layout and computed styles, including portions clipped
    // by the editor's scrolling preview window (nested screenshots omit them).
    await baseline.evaluate(()=>document.querySelectorAll('img').forEach(img=>img.loading='eager'));await baseline.waitForFunction(()=>[...document.querySelectorAll('img')].every(img=>img.complete));await page.waitForFunction(()=>[...document.querySelector('#dashboard-preview-frame').contentDocument.querySelectorAll('img')].every(img=>img.complete));await page.waitForTimeout(250);
    const fingerprint=loc=>loc.evaluate(shell=>{const outer=shell.getBoundingClientRect();return [...shell.querySelectorAll('.topbar,.metrics,.metric,.panel,.recent-transfer-card,.chance,.roster-player,.risk-player,.market-row,.player-cutout,.club-crest,.name')].map(n=>{const r=n.getBoundingClientRect(),c=getComputedStyle(n);return{tag:n.tagName,cls:n.className,x:r.left-outer.left,y:r.top-outer.top,w:r.width,h:r.height,display:c.display,font:c.font,fontSize:c.fontSize,color:c.color,background:c.background,border:c.border,padding:c.padding,gap:c.gap,transform:c.transform,objectFit:c.objectFit,objectPosition:c.objectPosition};});});
    const fp=await fingerprint(preview().locator('.app-shell')),fb=await fingerprint(baseline.locator('.app-shell'));
    if(JSON.stringify(fp)!==JSON.stringify(fb))console.log('Metric diagnostics',await preview().locator('.metric-budget').evaluate(n=>({inline:n.getAttribute('style'),line:getComputedStyle(n).getPropertyValue('--line'),border:getComputedStyle(n).border,borderColor:getComputedStyle(n).borderColor,body:document.body.className,html:n.outerHTML.slice(0,500)})));
    assert.deepEqual(fp,fb,'Complete original dashboard geometry and styles are identical');
    assert.equal(await preview().locator('.native-edit-overlay').count(),0);await page.locator('#preview').click();
    // Metric and non-player widgets, text, colors, and real image movement.
    await selectTile('Verfügbares Budget');await selectElement('Budget');await value('color','#ffdd44');await value('fontSize',28);
    await frame().locator('#metric-budget').waitFor();await page.waitForFunction(()=>getComputedStyle(document.querySelector('#native-editor-frame').contentDocument.querySelector('#metric-budget')).color==='rgb(255, 221, 68)');
    await selectTile('Kaderwert');await selectElement('Titel');await value('text','Mein Kaderwert');
    await selectTile('Entwicklung seit Saisonstart');await selectElement('Überschrift');await value('color','#55ccff');
    await selectTile('Wertentwicklung');await selectElement('Spielerbild');await value('x',-7);await value('w',110);await value('h',110);
    assert((await frame().locator('#roster-movers .player-cutout').first().evaluate(n=>n.style.transform)).includes('scale(1.1'));
    await drag(frame().locator('.native-element-frame'),6,4);await page.waitForFunction(()=>Number(document.querySelector('[data-property="x"]').value)>-7);
    const beforeWidth=Number(await prop('w').inputValue());await drag(frame().locator('.native-resize-handle'),8,6);await page.waitForFunction(previous=>Number(document.querySelector('[data-property="w"]').value)>previous,beforeWidth);
    await selectElement('Name');await value('color','#ff7799');
    await page.getByRole('button',{name:'+ Text',exact:true}).click();await value('text','Meine Notiz');
    const before=await page.evaluate(()=>fetch('api/dashboard-layout').then(r=>r.json()));assert.equal(before.revision,0);
    await page.locator('#preview').click();await preview().locator('#roster-movers .roster-player').nth(1).waitFor();
    assert.equal(await preview().locator('#metric-budget').evaluate(n=>getComputedStyle(n).color),'rgb(255, 221, 68)');assert((await preview().locator('.metric-squad').innerText()).includes('Mein Kaderwert'));
    for(const n of await preview().locator('#roster-movers .name').all())assert.equal(await n.evaluate(n=>getComputedStyle(n).color),'rgb(255, 119, 153)');
    assert.equal(await preview().getByText('Meine Notiz',{exact:true}).count(),2,'Extra element repeated for every player');
    assert.deepEqual(await page.evaluate(()=>fetch('api/dashboard-layout').then(r=>r.json())),before,'Preview never saves');
    await page.locator('#mode-mobile').click();await page.waitForFunction(()=>document.querySelector('#dashboard-preview-frame').getBoundingClientRect().width===390);
    await preview().locator('#roster-movers .roster-player').first().waitFor();await page.waitForFunction(()=>{const doc=document.querySelector('#dashboard-preview-frame').contentDocument;return getComputedStyle(doc.querySelector('#metric-budget')).color!=='rgb(255, 221, 68)';});
    await page.locator('#mode-desktop').click();await page.locator('#preview').click();await page.locator('#design-enabled').check();await page.locator('#save-design').click();await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Beide Ansichten gespeichert'));
    const stored=await page.evaluate(()=>fetch('api/dashboard-layout').then(r=>r.json()));assert(stored.desktop.native);assert.equal(stored.desktop.tiles.length,10);assert(stored.desktop.tiles.every(t=>!t.record&&!t.collection));assert(stored.desktop.tiles.find(t=>t.nativeKey==='budget').elements.find(e=>e.nativeKey==='value').changed.includes('color'));
    await selectTile('Kaderwert');await value('tile-w',6);await frame().locator('.native-custom-flow').waitFor();assert(await frame().locator('.native-custom-flow .metric-squad').count());await page.locator('#undo').click();await page.waitForFunction(()=>!document.querySelector('#native-editor-frame').contentDocument.querySelector('.native-custom-flow'));await page.locator('#save-design').click();await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Beide Ansichten gespeichert'));
    fs.mkdirSync('test-output',{recursive:true});await page.screenshot({path:'test-output/native-editor-desktop.png'});
    await page.goto(origin+'/');await page.waitForFunction(()=>getComputedStyle(document.querySelector('#metric-budget')).color==='rgb(255, 221, 68)');
    assert.equal(await page.getByText('Meine Notiz',{exact:true}).count(),2);await page.locator('#toggle-custom-layout').click();assert.equal(await page.getByText('Meine Notiz',{exact:true}).count(),0);await page.locator('#toggle-custom-layout').click();
    for(const width of [1480,1280,1024,900,899,768,390,320]){await page.setViewportSize({width,height:900});await page.waitForTimeout(80);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No overflow at '+width);}
    await context.route(origin+'/ingress/test/**',async r=>{const u=new URL(r.request().url());const response=await r.fetch({url:origin+u.pathname.replace('/ingress/test','')+u.search});await r.fulfill({response});});
    await page.goto(origin+'/ingress/test/editor');await frame().locator('.native-block-grip').nth(9).waitFor();await page.locator('#mode-mobile').click();await frame().locator('.metric-budget').waitFor();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.locator('#preview').click();await preview().locator('.metric-budget').waitFor();assert.equal(new URL(await page.locator('#dashboard-preview-frame').evaluate(n=>n.contentWindow.location.href)).pathname,'/ingress/test/preview');
    // Older free layouts remain on disk while the new standard layout opens
    // as a reversible draft, so upgrading never silently overwrites them.
    await page.locator('#preview').click();
    await page.evaluate(async()=>{const stored=await fetch('api/dashboard-layout').then(r=>r.json());const tile=KaneLayout.tile({w:4,h:3,elements:[KaneLayout.element('text',{text:'Altes Layout'})]});const layout={columns:12,rowHeight:32,gap:12,tiles:[tile]};const result=await fetch('api/dashboard-layout',{method:'POST',headers:{'Content-Type':'application/json','X-Advisor-Token':KICKBASE_DASHBOARD.csrf},body:JSON.stringify({version:1,revision:stored.revision,enabled:true,desktop:layout,mobile:{...layout,columns:4}})});if(!result.ok)throw Error(await result.text());});
    await page.reload();await frame().locator('.native-block-grip').nth(9).waitFor();assert.equal(await page.locator('#tile-list button').count(),10);assert.equal(await page.evaluate(()=>fetch('api/dashboard-layout').then(r=>r.json()).then(d=>d.desktop.tiles[0].elements[0].text)),'Altes Layout');await page.locator('#undo').click();assert(await page.locator('#editor-canvas').innerText().then(s=>s.includes('Altes Layout')));
    assert.deepEqual(errors,[]);await baseline.close();console.log('Native dashboard editor OK: original metrics/cards/styles and pristine preview identical; one real-image template per section; metric/chart/text/graphic editing; shared player styles; unsaved preview; persistence; standard restore; responsive widths and Ingress.');
  }catch(error){console.error('Editor status:',await page.locator('#editor-status').textContent().catch(()=>''),'Errors:',errors);fs.mkdirSync('test-output',{recursive:true});await page.screenshot({path:'test-output/native-editor-failure.png'});throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
