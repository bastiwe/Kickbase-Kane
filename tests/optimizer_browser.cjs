const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async()=>{
 const players=Array.from({length:20},(_,i)=>({id:String(i),name:'Testspieler '+i,owned:i<16,position:i<2?1:i<8?2:i<15?3:4,team:'Verein '+i%8,teamId:String(i%8),mv:1000000,bid:1200000,image:'',status:'Fit',l3:100+i,season:200+i,previous:1000,average:80,recent:[30,40,50],li:null}));
 players.forEach((p,i)=>{p.change=i===0?null:i%2?-50000:100000;p.matchdayChange=i===0?null:i%2?-60000:125000;});
 const payload={players,budget:5000000,league:'test',user:'test',generated:'TESTDATEN',forecast:{generatedAt:'2026-09-09T12:00:00+02:00',source:'Fast 1T'},forecastHorizon:{date:'2026-09-11',updates:2}};
 const html=fs.readFileSync('features/lineup_optimizer.html','utf8').replace('__PAYLOAD__',JSON.stringify(payload));
 fs.mkdirSync('test-output',{recursive:true});fs.writeFileSync('test-output/optimizer-test.html',html);
 const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'msedge'});const page=await browser.newPage({viewport:{width:1600,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.resolve('test-output/optimizer-test.html')).href);
 assert.equal(await page.locator('[data-formation]').count(),10);
 assert.equal(await page.locator('.pitch .player').count(),11);
 async function checkBankForecast(){
  const expected=await page.evaluate(()=>{
   const bank=players.filter(p=>!state.selection.includes(p.id)&&(p.owned||state.plans[p.id].action==='buy'));
   const sum=bank.reduce((s,p)=>s+(p.change??0),0);
   return [changeMoney(sum),changeMoney(bank.reduce((s,p)=>s+(p.matchdayChange??0),0))];
  });
  assert.deepEqual(await page.locator('#bank-forecast strong').allTextContents(),expected);
 }
 await checkBankForecast();
 assert.match(await page.locator('#bank-forecast').textContent(),/Teilsumme/);
 await page.locator('#search').fill('nonexistent');await checkBankForecast();await page.locator('#search').fill('');

 assert.match(await page.locator('#endbudget').textContent(),/5.000.000/);
 assert.match(await page.locator('[data-formation="4-4-2"]').getAttribute('class'),/incomplete/);
 await page.locator('#planbids').check();
 await page.locator('#best').click();
 await checkBankForecast();
 assert.match(await page.locator('#endbudget').textContent(),/200.000/);
 assert.doesNotMatch(await page.locator('[data-formation="4-4-2"]').getAttribute('class'),/incomplete|overbudget/);
 await page.locator('#budget').fill('-1000000');await page.locator('#budget').dispatchEvent('change');
 assert.match(await page.locator('[data-formation="4-4-2"]').getAttribute('class'),/overbudget/);
 await page.locator('#budget').fill('5000000');await page.locator('#budget').dispatchEvent('change');
 const selected=await page.evaluate(()=>state.selection.filter(Boolean));
 for(const id of selected)assert.equal(await page.locator('#roster [data-player="'+id+'"]').count(),0);
 // A bank defender replaces a selected defender, without duplicating either.
 const defender=await page.evaluate(()=>players.find(p=>p.position===2&&!state.selection.includes(p.id)).id);
 const replaced=await page.evaluate(()=>state.selection[1]);
 await page.locator('#roster [data-player="'+defender+'"]').dragTo(page.locator('[data-slot="1"]'));
 assert.equal(await page.evaluate(()=>state.selection[1]),defender);
 assert.equal(await page.locator('#roster [data-player="'+replaced+'"]').count(),1);
 await checkBankForecast();
 // A goalkeeper cannot be dropped onto a midfield slot.
 const keeper=await page.evaluate(()=>players.find(p=>p.position===1&&!state.selection.includes(p.id)).id);
 const unchanged=await page.evaluate(()=>[...state.selection]);
 await page.locator('#roster [data-player="'+keeper+'"]').dragTo(page.locator('[data-slot="5"]'));
 assert.deepEqual(await page.evaluate(()=>state.selection),unchanged);
 await page.locator('[data-slot="1"]').dragTo(page.locator('aside h2'));
 assert.equal(await page.evaluate(()=>state.selection[1]),null);
 await page.locator('#best').click();

 await page.locator('#sellbench').check();
 // Lock a bank player: bank sales must leave it in the retained roster.
 const bankPlayer=await page.evaluate(()=>players.find(p=>p.owned&&!state.selection.includes(p.id)).id);
 await page.locator('#roster [data-player="'+bankPlayer+'"] [data-lock]').click();
 assert.equal(await page.evaluate(id=>accounting().retained.some(p=>p.id===id),bankPlayer),true);
 await page.locator('#roster [data-player="'+bankPlayer+'"] [data-lock]').click();
 const end=await page.evaluate(()=>accounting());assert.equal(end.end,5000000-end.buys+end.sales);
 await page.locator('#sellbench').uncheck();
 await page.locator('[data-price="16"]').fill('');await page.locator('[data-price="16"]').dispatchEvent('change');assert.equal(await page.locator('#endbudget').textContent(),'Unbekannt');
 await page.locator('#reset').click();await page.locator('#planbids').check();await page.locator('#bench').click();assert.equal(await page.locator('.empty').count(),11);
 await page.locator('[data-slot="0"]').click();await page.locator('[data-pick="0"]').click();assert.equal(await page.locator('.empty').count(),10);
 await page.locator('#best').click();await page.locator('#save').click();await page.locator('#bench').click();await page.locator('#load').click();assert.equal(await page.locator('.empty').count(),0);

 // Formation-specific budget must use that formation's proposed sales.
 await page.locator('#sellbench').check();
 const budgets=new Set();
 for(const f of ['4-4-2','4-3-3','3-4-3','3-5-2','5-3-2','4-5-1','5-4-1','4-2-4','5-2-3','3-6-1']){
  const expected=await page.evaluate(f=>money(accounting(f===state.formation?state.selection:optimal(f)).end),f);
  assert.equal(await page.locator(`[data-formation="${f}"]`).getAttribute('title'),'Endbudget: '+expected);
  await page.locator(`[data-formation="${f}"]`).click();
  assert.equal(await page.locator('.pitch .player').count(),11);
  const ids=await page.evaluate(()=>state.selection.filter(Boolean));
  assert.equal(new Set(ids).size,ids.length);
  assert.equal(await page.locator('#endbudget').textContent(),expected);
  budgets.add(expected);
 }
 assert.ok(budgets.size>1,'Different lineups must have different simulated sale proceeds');

 await page.locator('#planbids').uncheck();
 assert.equal(await page.evaluate(()=>state.selection.some(id=>id&&!byId.get(id).owned)),false);
 assert.equal(await page.evaluate(()=>accounting().buys),0);
 await page.locator('#planbids').check();await page.locator('#best').click();
 await page.evaluate(()=>{window.scrollTo(0,0);document.querySelector('aside').scrollTop=0;});
 await page.screenshot({path:'test-output/optimizer-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:'test-output/optimizer-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);await browser.close();console.log('Optimizer browser tests passed: formation colors, candidate budgets, bench-only list, drag/drop, optional bids, persistence, mobile.');
})().catch(e=>{console.error(e);process.exit(1);});
