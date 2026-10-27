const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true}),origin=process.env.EDITOR_TEST_URL,errors=[];
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  await context.route('https://editor.test/**',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#e63950"/><circle cx="50" cy="35" r="22" fill="#ddb791"/></svg>'}));
  const transfers=[{playerId:'kane',playerName:'Harry Kane',marketValue:10001,price:11001,overpay:1000,from:'Kickbase',to:'Sebastian'},
    {playerId:'kimmich',playerName:'Joshua Kimmich',marketValue:20000,price:22000,isKickbaseSale:true,profitLoss:500,from:'Johannes',to:'Kickbase'}];
  const mocks={'manager-budgets':{managers:[{name:'Sebastian',cash:11480895}]},'recent-transfers':{transfers},'squad-value-history':{series:[]},'current-lineup':{players:[]}};
  await context.route('**/api/**',r=>{const key=new URL(r.request().url()).pathname.replace('/api/','');return mocks[key]?r.fulfill({contentType:'application/json',body:JSON.stringify(mocks[key])}):r.continue();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const prop=key=>page.locator('[data-property="'+key+'"]'),selected=()=>page.locator('.editor-element-selected');
  const value=async(key,v)=>{await prop(key).fill(String(v));await prop(key).dispatchEvent('change');};
  const cards=key=>page.locator('#custom-dashboard [data-section="'+key+'"] .section-player-card');
  const saved=()=>page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Beide Ansichten gespeichert'));
  const drag=async(loc,dx,dy)=>{await loc.scrollIntoViewIfNeeded();const b=await loc.boundingBox();assert(b);await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2+dx,b.y+b.height/2+dy,{steps:8});await page.mouse.up();};
  try{
    await page.goto(origin+'/editor');await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Bereichsvorlagen'));
    assert.equal(await page.locator('.layout-section').count(),5);assert.equal(await page.locator('.section-player-card').count(),5);
    const text=await page.locator('#editor-canvas').innerText();assert(!text.includes('Harry Kane'));assert(text.includes('{Spielerbild}')&&text.includes('{Vereinswappen}')&&text.includes('{Name}'));
    const checks=await page.evaluate(()=>{
      const now=Date.parse('2026-10-27T12:00:00Z'),end=Date.parse('2026-10-27T20:00:00Z');
      const d={report:{players:[{id:'p',name:'Test Player',mv:999,change:-10,recentForm:[0,271,195]}],marketPlayers:[{id:'m',change:150000,expiresAt:end},{id:'n',change:50000,expiresAt:end},{id:'u',change:null,expiresAt:end}]},api:{transfers:{transfers:[{playerId:'p',marketValue:123,price:133,overpay:10}]}}};
      return Object.fromEntries(['roster','chances','risks','market','transfers'].map(k=>[k,KaneLayout.sectionItems(d,k,now)]));
    });
    assert.equal(checks.roster[0]['Form 1'],0);assert.equal(checks.transfers[0].Marktwert,123);assert.equal(checks.chances.length,1);assert.equal(checks.risks.length,2);assert.equal(checks.market.length,3);
    await page.locator('#tile-list button').filter({hasText:'Wertentwicklung'}).click();assert.equal(await prop('record').count(),0);
    await value('cardColumns',2);await value('cardGap',18);await value('cardHeight',250);
    await page.locator('.property-elements button').filter({hasText:/3\. Name$/}).click();await value('color','#ffdd44');await value('fontSize',20);
    const before=await selected().evaluate(n=>({y:parseFloat(n.style.top),h:parseFloat(n.style.height)}));await drag(selected(),-8,7);assert(await selected().evaluate(n=>parseFloat(n.style.top))>before.y);
    await drag(selected().locator('.resize-handle'),0,6);assert(await selected().evaluate(n=>parseFloat(n.style.height))>before.h);
    await page.getByRole('button',{name:'+ Daten',exact:true}).click();await page.locator('#source-search').fill('Durchschnittspunkte');await page.locator('#source-picker').selectOption('/item/Durchschnittspunkte');await page.locator('#apply-source').click();assert.equal(await selected().textContent(),'{Durchschnittspunkte}');
    assert((await prop('source').locator('option:checked').textContent()).includes('Durchschnittspunkte'));
    await page.getByRole('button',{name:'+ Grafik',exact:true}).click();const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=c.height=30;c.getContext('2d').fillRect(0,0,30,30);return c.toDataURL().split(',')[1];});
    await page.locator('#image-file').setInputFiles({name:'pixel.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Grafik im Entwurf'));assert.match(await selected().locator('img').getAttribute('src'),/^data:image\//);
    await page.locator('#mode-mobile').click();await page.locator('#tile-list button').filter({hasText:'Wertentwicklung'}).click();assert.equal(await prop('cardColumns').inputValue(),'1');
    await page.locator('#add-section').click();assert.equal(await page.locator('.layout-section').count(),5,'No duplicate sections');
    await page.locator('#mode-desktop').click();await page.locator('#design-enabled').check();await page.locator('#save-design').click();await saved();
    const design=await page.evaluate(()=>fetch('api/dashboard-layout').then(r=>r.json()));assert(design.desktop.tiles.every(t=>t.record===''&&t.collection===''));assert.equal(design.desktop.tiles.find(t=>t.section==='roster').cardColumns,2);assert.equal(design.mobile.tiles.find(t=>t.section==='roster').cardColumns,1);
    fs.mkdirSync('test-output',{recursive:true});const downloading=page.waitForEvent('download');await page.locator('#export-design').click();await(await downloading).saveAs('test-output/editor-layout.json');
    await page.locator('#import-file').setInputFiles('test-output/editor-layout.json');await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Layout importiert'));await page.locator('#undo').click();await page.locator('#redo').click();await page.locator('#save-design').click();await saved();
    await page.reload();await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Gespeichertes Layout'));assert.equal(await page.locator('.section-player-card').count(),5);await page.screenshot({path:'test-output/dashboard-editor-sections.png'});
    await page.goto(origin+'/');await page.waitForFunction(()=>document.querySelectorAll('#custom-dashboard [data-section="transfers"] .section-player-card').length===2);
    for(const [key,count]of Object.entries({transfers:2,chances:2,roster:2,risks:4,market:4}))assert.equal(await cards(key).count(),count,key);
    assert(await page.locator('.metrics').isVisible());assert(await page.locator('.value-history').isVisible());assert(await page.locator('.manager-budget-panel').isVisible());
    const names=cards('roster').locator('.layout-element').filter({hasText:/^(Harry Kane|Joshua Kimmich)$/});assert.equal(await names.count(),2);for(const n of await names.all())assert.equal(await n.evaluate(n=>getComputedStyle(n).color),'rgb(255, 221, 68)');
    assert((await cards('transfers').first().innerText()).includes('10.001'));assert(!(await cards('transfers').nth(1).innerText()).includes('Overpay'));assert((await cards('transfers').nth(1).innerText()).includes('G/V: 500'));
    const boxes=await page.locator('#custom-dashboard .layout-section').evaluateAll(nodes=>nodes.map(n=>({x:n.offsetLeft,y:n.offsetTop,w:n.offsetWidth,h:n.offsetHeight})));
    for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){const a=boxes[i],b=boxes[j];assert(!(a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y),'No overlap after dynamic expansion');}
    await page.screenshot({path:'test-output/dashboard-sections-desktop.png',fullPage:true});
    mocks['recent-transfers'].transfers=[...transfers,{...transfers[0],playerName:'Neuer Transfer'}];await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#custom-dashboard [data-section="transfers"] .section-player-card').length===3);
    mocks['recent-transfers'].transfers=[];await page.reload();await page.waitForFunction(()=>document.querySelector('#custom-dashboard [data-section="transfers"] .section-empty'));assert.equal(await cards('transfers').count(),0);mocks['recent-transfers'].transfers=transfers;
    await page.reload();await page.locator('#custom-dashboard').waitFor({state:'visible'});
    for(const width of [1280,1024,900,899,768,390,320]){await page.setViewportSize({width,height:900});await page.waitForFunction(expected=>getComputedStyle(document.querySelector('#custom-dashboard [data-section="roster"] .section-player-grid')).gridTemplateColumns.split(' ').length===expected,width<900?1:2);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No overflow at '+width);
      await page.waitForFunction(()=>[...document.querySelectorAll('#custom-dashboard .layout-section')].every(n=>n.querySelector('.section-player-grid').getBoundingClientRect().bottom<=n.getBoundingClientRect().bottom+1));}
    await page.setViewportSize({width:390,height:900});await page.screenshot({path:'test-output/dashboard-sections-mobile.png',fullPage:true});
    await page.locator('#toggle-custom-layout').click();assert(await page.locator('#roster-movers').isVisible());await page.locator('#toggle-custom-layout').click();
    await context.route(origin+'/ingress/test/**',async r=>{const u=new URL(r.request().url());const response=await r.fetch({url:origin+u.pathname.replace('/ingress/test','')+u.search});await r.fulfill({response});});
    await page.goto(origin+'/ingress/test/editor');await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Gespeichertes Layout'));await page.locator('#mode-mobile').click();assert.equal(await page.locator('.section-player-card').count(),5);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.locator('#save-design').click();await saved();await page.locator('.editor-home').click();await page.locator('#custom-dashboard').waitFor({state:'visible'});assert.equal(new URL(page.url()).pathname,'/ingress/test/');assert.deepEqual(errors,[]);
    console.log('Section templates OK: one placeholder per heading, filters/zeros, shared styles, dynamic counts/heights, historical transfers, per-section grids, mobile/desktop, upload, persistence, import/export, undo/redo, Ingress, seven widths.');
  }catch(error){console.error('Status:',await page.locator('#editor-status').textContent().catch(()=>''),'Errors:',errors);fs.mkdirSync('test-output',{recursive:true});await page.screenshot({path:'test-output/editor-failure.png'});throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
