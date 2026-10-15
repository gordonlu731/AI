import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {mkdir,writeFile,rm} from 'node:fs/promises';
const base=process.env.TEST_URL||'http://127.0.0.1:4173';
await mkdir('artifacts',{recursive:true});await rm('artifacts/intervention-browser.json',{force:true});
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
const context=await browser.newContext({viewport:{width:960,height:720}});
const errors=[],external=[],runs=[],checks=[];
await context.route('**/*',r=>{if(['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname))return r.continue();external.push(r.request().url());return r.abort();});
const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
const report=()=>page.evaluate(()=>window.__bellworks.report());
const geometry=()=>page.evaluate(()=>window.__bellworks.interventionGeometry());
function pass(s){checks.push(s);console.log('PASS',s);}
async function capture(name){await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:`artifacts/intervention-${name}.png`});await page.setViewportSize({width:960,height:720});}
async function configure(removeDomino,addObstacle){
 await page.locator('#remove-domino').setChecked(removeDomino);await page.locator('#add-obstacle').setChecked(addObstacle);await page.locator('#reset').click();
 const r=await report();assert.equal(r.time,0);assert.deepEqual(r.interventions,{removeDomino,addObstacle});
 assert.deepEqual(await geometry(),{dominoes:removeDomino?7:8,obstacle:addObstacle});
}
async function run(scenario,repeat,blocked){
 await page.locator('#start').click();const r=await page.evaluate(()=>window.__bellworks.advance(30));
 await page.locator('#pause').click();
 if(blocked){assert.ok(r.obstacleHits>0);assert.equal(r.bellHits,0);assert.deepEqual(r.stages,[true,false,false,false,false,false,false,false,false]);assert.ok(r.position.x < -8.32);}
 else {assert.ok(r.stages.every(Boolean));assert.ok(r.bellHits>0);}
 assert.ok(r.time>=30);assert.equal(await page.locator('#stages li.done').count(),blocked?1:9);
 const paused=await report();await page.waitForTimeout(100);assert.deepEqual(await report(),paused);
 runs.push({scenario,repeat,mode:'browser UI plus 30s fixed-step acceleration',...r});pass(`${scenario} ${repeat}: ${r.stages.filter(Boolean).length}/9; real obstacle contacts ${r.obstacleHits}`);
 return r;
}
try {
 await page.goto(`${base}/?test=1`);await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 assert.deepEqual((await report()).interventions,{removeDomino:false,addObstacle:false});
 await capture('ready');
 for(let repeat=1;repeat<=3;repeat++){
  await configure(false,false);const baseline=await run('A baseline',repeat,false);assert.equal(baseline.stageTimes[8],14.825000773184001);
  await configure(false,true);await run('B obstacle enabled',repeat,true);
  if(repeat===1){
   await capture('obstacle-contact');
   const active=await report();await page.locator('#add-obstacle').uncheck();
   assert.deepEqual(await report(),active);assert.equal((await geometry()).obstacle,true);
   assert.match(await page.locator('#intervention-note').innerText(),/queued/);
   pass('A mid-run toggle queues for Reset and leaves the paused physical world and visible barrier intact');
  }
  await configure(false,false);const restored=await run('C obstacle disabled',repeat,false);assert.deepEqual(restored.stageTimes,baseline.stageTimes);
 }
 await configure(true,false);assert.deepEqual(await geometry(),{dominoes:7,obstacle:false});await capture('domino-removed');
 const removed=await run('D final domino removed',1,false);assert.equal(removed.dominoCount,7);assert.equal(removed.stageTimes[8],12.966667342931032);
 await configure(true,true);await run('Both options independent',1,true);
 await configure(false,false);assert.deepEqual(await geometry(),{dominoes:8,obstacle:false});pass('One-click restoration before release recreates all eight visible dominoes and removes the barrier');
 await page.locator('#add-obstacle').check();assert.equal((await report()).interventions.addObstacle,true);assert.equal((await geometry()).obstacle,true);
 await page.locator('#add-obstacle').uncheck();assert.equal((await report()).interventions.addObstacle,false);assert.equal((await geometry()).obstacle,false);
 pass('Pre-release obstacle toggles immediately add and remove the rendered physical barrier');
 await page.setViewportSize({width:390,height:844});await page.reload();await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 await page.locator('#add-obstacle').check();assert.equal((await geometry()).obstacle,true);await page.locator('#remove-domino').check();assert.equal((await geometry()).dominoes,7);
 await page.screenshot({path:'artifacts/intervention-mobile.png'});pass('Both intervention switches are operable on mobile');
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);pass('No browser errors or external network requests');
 await writeFile('artifacts/intervention-browser.json',JSON.stringify({generatedAt:new Date().toISOString(),base,runs,checks,errors,external},null,2));
}finally{await browser.close();}
