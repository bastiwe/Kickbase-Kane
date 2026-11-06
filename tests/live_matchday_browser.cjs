const assert=require('node:assert/strict'), fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1600,height:1000}}), errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('https://images.test/**',route=>route.fulfill({contentType:'image/svg+xml',body:route.request().url().includes('crest')?'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><path d="M5 5H75V45Q70 65 40 78Q10 65 5 45Z" fill="#1d76b6"/><text x="40" y="47" fill="white" font-size="24" text-anchor="middle">FC</text></svg>':'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 110"><ellipse cx="50" cy="30" rx="22" ry="26" fill="#d8ac88"/><path d="M10 110V80Q50 50 90 80V110Z" fill="#cc303b"/></svg>'}));
  const origin=process.env.LIVE_TEST_URL;
  await page.goto(origin+'/matchday');await page.locator('#league-rows tr').nth(4).waitFor();
  assert.equal(await page.locator('#league-rows tr').count(),5);
  await page.locator('#tab-matchday').click();
  assert.equal(await page.locator('.live-player').count(),55);
  const points=await page.locator('.manager-row').first().locator('.score').allTextContents();
  assert.deepEqual(points.map(Number),[100,90,80,70,60,50,40,30,20,10,0]);
  assert((await page.locator('#ticker-track').innerText()).includes('2 : 1'));
  await page.locator('.live-player').first().click();
  try{await page.locator('#actions-list .action-row').nth(2).waitFor({timeout:5000});}catch(error){console.log('Actions diagnostics',await page.locator('#actions-dialog').innerText(),errors);throw error;}
  assert.equal(await page.locator('#actions-points').innerText(),'10');
  assert((await page.locator('#actions-status').innerText()).includes('Buchungssumme 10'));
  await page.locator('#actions-grouped').click();assert.equal(await page.locator('.action-row').count(),2);
  assert((await page.locator('#actions-list').innerText()).includes('Pass gespielt'));
  assert((await page.locator('#actions-list').innerText()).includes('+11'));
  await page.keyboard.press('Escape');
  fs.mkdirSync('test-output',{recursive:true});
  for(const width of [320,390,768,1024,1600]){
    await page.setViewportSize({width,height:1000});
    for(const tab of ['league','matchday']){
      await page.locator('#tab-'+tab).click();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No page overflow: '+width+' '+tab);
      if(width===390||width===1600)await page.screenshot({path:`test-output/live-${tab}-${width}.png`});
    }
  }
  await page.locator('#day-select').selectOption('9');await page.waitForFunction(()=>document.querySelector('#manager-rows').textContent.includes('vorläufige Aufstellung'));
  assert((await page.locator('.score').allTextContents()).every(text=>text==='–'));
  await page.locator('.live-player').first().click();await page.waitForFunction(()=>document.querySelector('#actions-status').textContent.includes('keine Punkteaktionen'));
  assert.equal(await page.locator('#actions-points').innerText(),'–');await page.locator('#close-actions').click();
  await page.locator('#day-select').selectOption('8');await page.waitForFunction(()=>document.querySelector('.score')?.textContent==='100');
  await page.route('**/api/live-matchday*',route=>route.fulfill({status:502,json:{error:'Test: API nicht verfügbar'}}));
  await page.locator('#refresh').click();await page.locator('#live-error').waitFor();
  assert.equal(await page.locator('.live-player').count(),55,'Keep previous successful data on error');
  await page.unroute('**/api/live-matchday*');
  // HA Ingress: every relative asset and data request must keep its prefix.
  const requests=[];
  await page.route(origin+'/ingress/test/**',async route=>{requests.push(new URL(route.request().url()).pathname);const response=await route.fetch({url:route.request().url().replace('/ingress/test','')});await route.fulfill({response});});
  await page.goto(origin+'/ingress/test/matchday');await page.locator('#league-rows tr').nth(4).waitFor();
  assert(requests.includes('/ingress/test/api/live-matchday'));
  assert(requests.includes('/ingress/test/live_matchday.css'));
  assert.deepEqual(errors,[]);await browser.close();
  console.log('Live matchday: tabs, 55 sorted starters, action sums, preview, API failure, 5 viewport widths and HA Ingress passed.');
})().catch(error=>{console.error(error);process.exit(1);});
