const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const origin=process.env.EDITOR_TEST_URL,errors=[];
  const context=await browser.newContext({viewport:{width:1600,height:1000}});
  await context.route('https://editor.test/**',route=>route.fulfill({contentType:'image/svg+xml',body:route.request().url().includes('crest')?
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="47" fill="#d11b40"/><circle cx="50" cy="50" r="32" fill="#2874ba" stroke="white" stroke-width="7"/></svg>':
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M8 100V75Q50 48 92 75V100" fill="#e43150"/><ellipse cx="50" cy="36" rx="22" ry="28" fill="#ddb791"/><path d="M28 30Q24 0 50 4Q79 2 73 30L65 14H37Z" fill="#503823"/></svg>'}));
  const mocks={'manager-budgets':{managers:[{name:'Sebastian',cash:11480895}],note:'Test'},'recent-transfers':{transfers:[]},'squad-value-history':{series:[]},'current-lineup':{players:[]},'player-details/kane':{status:'Fit',goals:12}};
  await context.route('**/api/**',route=>{const path=new URL(route.request().url()).pathname.replace('/api/','');return mocks[path]?route.fulfill({contentType:'application/json',body:JSON.stringify(mocks[path])}):route.continue();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const prop=key=>page.locator(`[data-property="${key}"]`);
  const value=async(key,v)=>{await prop(key).fill(String(v));await prop(key).dispatchEvent('change');};
  const selected=()=>page.locator('.editor-element-selected');
  const rect=async locator=>{await locator.scrollIntoViewIfNeeded();const box=await locator.boundingBox();assert(box);return box;};
  const drag=async(locator,dx,dy)=>{const box=await rect(locator);await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+dx,box.y+box.height/2+dy,{steps:8});await page.mouse.up();};
  try{
    await page.goto(origin+'/editor');await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Vorlagen'));
    assert.equal(await page.evaluate(()=>{const d={report:{players:[{mv:100,change:0},{mv:200,change:20}],budget:-50}};KaneLayout.enrich(d);return d.dashboard['Bereinigter Kaderwert'];}),250);
    assert.equal(await page.evaluate(()=>{const d={report:{players:[{mv:100,change:null}]}};KaneLayout.enrich(d);return d.dashboard['Erwartete MW-Änderung (1T)'];}),null);
    assert.equal(await page.evaluate(()=>{const n=KaneLayout.element('text',{text:'<script>window.bad=true</script>'});const host=document.createElement('div');KaneLayout.render(host,{columns:1,rowHeight:30,gap:0,tiles:[KaneLayout.tile({w:1,h:3,elements:[n]})]},{report:{players:[]}});return host.querySelectorAll('script').length;}),0);
    assert.equal(await page.locator('.layout-tile').count(),4);
    await page.locator('#tile-list button').first().click();await page.locator('.property-elements button').first().click();
    await value('text','Mein Budget');await value('fontSize',25);await value('color','#ffdd44');
    assert.equal(await selected().textContent(),'Mein Budget');
    assert.equal(await selected().evaluate(n=>getComputedStyle(n).color),'rgb(255, 221, 68)');
    const before=await selected().evaluate(n=>({x:parseFloat(n.style.left),y:parseFloat(n.style.top),h:parseFloat(n.style.height)}));
    await drag(selected(),8,15);const after=await selected().evaluate(n=>({x:parseFloat(n.style.left),y:parseFloat(n.style.top)}));
    assert(after.y>before.y,'Element moves within the tile');
    await drag(selected().locator('.resize-handle'),0,12);assert(await selected().evaluate(n=>parseFloat(n.style.height))>before.h,'Element border resizes');
    const tile=page.locator('.editor-tile-selected'),start=await tile.evaluate(n=>n.style.gridRow);
    await drag(tile.locator('.tile-grip'),0,45);assert.notEqual(await page.locator('.editor-tile-selected').evaluate(n=>n.style.gridRow),start,'Tile snaps to grid');
    const width=await page.locator('.editor-tile-selected').evaluate(n=>n.style.gridColumn);
    await drag(page.locator('.editor-tile-selected .tile-resize'),80,0);assert.notEqual(await page.locator('.editor-tile-selected').evaluate(n=>n.style.gridColumn),width,'Tile resize changes column span');
    await page.getByRole('button',{name:'+ Daten',exact:true}).click();
    await page.locator('#source-search').fill('customField');await page.locator('#source-picker').selectOption('/report/customField/value');await page.locator('#apply-source').click();
    assert.equal(await selected().textContent(),'Aus dem Vollreport');
    await page.getByRole('button',{name:'+ Grafik',exact:true}).click();
    // A real PNG upload is converted to a self-contained, persisted image.
    const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=30;c.height=30;const g=c.getContext('2d');g.fillStyle='#ffcc44';g.fillRect(0,0,30,30);return c.toDataURL('image/png').split(',')[1];});
    await page.locator('#image-file').setInputFiles({name:'pixel.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});
    await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Grafik im Entwurf'));
    assert.match(await selected().locator('img').getAttribute('src'),/^data:image\//);
    // Add a record-bound player blueprint, including image and crest.
    await page.locator('#blueprint-player').selectOption('players:0');await page.locator('#add-player').click();
    assert.equal(await page.locator('.editor-tile-selected img').count(),2);
    assert.equal(await page.evaluate(()=>KaneLayout.context({report:{players:[{id:'other',name:'Other'},{id:'kane',name:'Kane'}]}},{collection:'/report/players',record:'id:kane'}).item.name),'Kane');
    await page.locator('#load-player-details').click();await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Spielerdetails für'));
    await page.locator('#source-search').fill('goals');assert(await page.locator('#source-picker option').count()>0);
    // Desktop and mobile remain independently editable.
    await page.locator('#mode-mobile').click();assert.equal(await page.locator('.layout-tile').count(),4);
    await page.locator('#add-tile').click();await value('tile-title','Nur Mobil');
    await page.locator('#mode-desktop').click();assert.equal(await page.locator('.layout-tile[aria-label="Nur Mobil"]').count(),0);
    await page.locator('#design-enabled').check();await page.locator('#save-design').click();
    await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Beide Ansichten gespeichert'));
    const saved=await page.evaluate(()=>fetch('api/dashboard-layout').then(r=>r.json()));assert(saved.enabled);assert.equal(saved.desktop.tiles.length,5);assert.equal(saved.mobile.tiles.length,5);
    assert(saved.mobile.tiles.some(t=>t.title==='Nur Mobil'));assert(!saved.desktop.tiles.some(t=>t.title==='Nur Mobil'));
    // Export/import validates and keeps a draft until saved.
    fs.mkdirSync('test-output',{recursive:true});const downloadPromise=page.waitForEvent('download');await page.locator('#export-design').click();const download=await downloadPromise;await download.saveAs('test-output/editor-layout.json');
    assert.equal(JSON.parse(fs.readFileSync('test-output/editor-layout.json')).revision,1);
    await page.locator('#import-file').setInputFiles('test-output/editor-layout.json');await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Layout importiert'));
    await page.locator('#undo').click();await page.locator('#redo').click();
    await page.locator('#save-design').click();await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Beide Ansichten gespeichert'));
    await page.reload();await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Gespeichertes Layout'));
    assert.equal(await page.locator('.layout-tile').count(),5);
    await page.locator('#preview').click();await page.screenshot({path:'test-output/dashboard-editor-desktop.png'});
    // Published view uses the same design, with a working switch back to standard.
    await page.goto(origin+'/');await page.locator('#custom-dashboard').waitFor({state:'visible'});
    assert.equal(await page.locator('#custom-dashboard .layout-tile').count(),5);
    assert.equal(await page.locator('.metrics').isVisible(),false);
    await page.locator('#toggle-custom-layout').click();assert.equal(await page.locator('.metrics').isVisible(),true);
    await page.locator('#toggle-custom-layout').click();
    await page.screenshot({path:'test-output/dashboard-custom-desktop.png',fullPage:true});
    for(const w of [320,390,768,899,900,1280]){
      await page.setViewportSize({width:w,height:900});
      await page.waitForFunction(expected=>!!document.querySelector('#custom-dashboard [aria-label="Nur Mobil"]')===expected,w<900);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No dashboard overflow at '+w);
    }
    await page.setViewportSize({width:390,height:900});await page.screenshot({path:'test-output/dashboard-custom-mobile.png',fullPage:true});
    await page.goto(origin+'/editor');await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Gespeichertes Layout'));
    await page.locator('#mode-mobile').click();assert(await page.locator('.layout-tile[aria-label="Nur Mobil"]').count());
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Editor fits mobile screen; canvas scrolls internally');
    // Ingress strips a nested URL prefix before forwarding to the add-on.
    // Assets, API calls, saving, and navigation must all stay relative to it.
    await context.route(origin+'/ingress/test/**',async route=>{
      const url=new URL(route.request().url());const response=await route.fetch({url:origin+url.pathname.replace('/ingress/test','')+url.search});await route.fulfill({response});
    });
    await page.goto(origin+'/ingress/test/editor');await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Gespeichertes Layout'));
    await page.locator('#save-design').click();await page.waitForFunction(()=>document.querySelector('#editor-status').textContent.includes('Beide Ansichten gespeichert'));
    await page.locator('.editor-home').click();await page.locator('#custom-dashboard').waitFor({state:'visible'});
    assert.equal(new URL(page.url()).pathname,'/ingress/test/');
    assert.deepEqual(errors,[]);console.log('Editor browser: drag/resize, styling, binding, blueprint, upload, API fields, separate views, save/reload, import/export, undo/redo, dashboard at 6 widths OK');
  }catch(error){console.error('Editor status:',await page.locator('#editor-status').textContent().catch(()=>''),'Page errors:',errors);fs.mkdirSync('test-output',{recursive:true});await page.screenshot({path:'test-output/editor-failure.png'});throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
