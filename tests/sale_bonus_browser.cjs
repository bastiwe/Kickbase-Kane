const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
 const positions = [1,2,2,2,2,3,3,3,3,4,4,2];
 const players = positions.map((position,i) => ({id:String(i),name:'Spieler '+i,position,owned:true,
  mv:i===11?4000000:1000000,l3:i===11?1:100,team:'Verein '+i,teamId:String(i),image:'',li:null}));
 const payload = {players,budget:0,league:'bonus-test',user:'test',generated:'Test',saleBonus:{
  rules:[{id:701,name:'Bronzenes Händchen',threshold:3000000,reward:250000,repeatable:true,earned:true}],
  purchases:{'11':{price:1000000,market:true}}}};
 const html = fs.readFileSync('features/lineup_optimizer.html','utf8').replace('__PAYLOAD__',JSON.stringify(payload));
 fs.mkdirSync('test-output',{recursive:true});
 fs.writeFileSync('test-output/sale-bonus-test.html',html);
 const browser = await chromium.launch({headless:true,channel:'msedge'});
 try {
  const page = await browser.newPage({viewport:{width:1600,height:1100}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve('test-output/sale-bonus-test.html')).href);
  assert.equal(await page.evaluate(()=>accounting().end),4000000);
  await page.locator('#bonus-enabled').check();
  assert.equal(await page.evaluate(()=>accounting().end),4250000);
  assert.match(await page.locator('#bonus-players').textContent(),/Bronzenes Händchen/);
  await page.locator('[data-lock="11"]').click();
  assert.equal(await page.evaluate(()=>accounting().end),0);
  await page.locator('[data-lock="11"]').click();
  await page.locator('[data-price="11"]').fill('3999999');
  await page.locator('[data-price="11"]').dispatchEvent('change');
  assert.equal(await page.evaluate(()=>accounting().bonus),0);
  await page.locator('[data-price="11"]').fill('4000000');
  await page.locator('[data-price="11"]').dispatchEvent('change');
  await page.locator('#save').click();
  await page.locator('#bonus-enabled').uncheck();
  await page.locator('#load').click();
  assert.equal(await page.evaluate(()=>accounting().bonus),250000);
  await page.evaluate(()=>{placePlayer('11',1);render();});
  assert.equal(await page.evaluate(()=>accounting().bonus),0);
  await page.screenshot({path:'test-output/sale-bonus-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'test-output/sale-bonus-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);
  console.log('Sale bonus browser checks passed: amounts, thresholds, locks, lineup, persistence, mobile.');
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
