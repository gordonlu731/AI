// OPERATOR ONLY: verify production build against the separately collected key.
import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
const root=new URL('../',import.meta.url),base=process.env.TEST_URL||'http://127.0.0.1:4192';
const key=JSON.parse(await readFile(new URL('operator/ground-truth.json',root),'utf8'));
const expected=new Map([key.reference,...key.cases].map(c=>[c.id,c]));
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
const errors=[],external=[],runs=[],controls={};let success=false,realtimeReport=null,failure=null;
await mkdir(new URL('operator/screenshots/',root),{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/*',r=>{if(['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname))return r.continue();external.push(r.request().url());return r.abort();});
 await page.goto(base+'/round2.html?test=1');await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 for(const id of ['REF','Y1','Y2','Y3','Y4']){
  await page.selectOption('#experiment-case',id);await page.click('#reset');
  for(let repeat=1;repeat<=3;repeat++){
   if(repeat>1)await page.click('#reset');
   const initial=await page.evaluate(()=>({r:window.__bellworks.report(),g:window.__bellworks.geometry()}));
   assert.equal(initial.r.time,0);assert.ok(initial.r.stages.every(v=>!v));assert.equal(initial.r.experiment,id);
   assert.equal(initial.g.visibleDominoes,id==='Y3'?7:8);assert.equal(initial.g.visibleObstacle,['Y1','Y2'].includes(id));assert.equal(initial.g.ballRadius,Math.fround(.32));
   if(id==='Y3')assert.deepEqual(initial.g.dominoes.map(d=>d.ordinal),[1,2,3,5,6,7,8]);
   if(id==='Y4')assert.ok(Math.abs(initial.r.ballMass-.329419881105423)<1e-7);
   await page.click('#start');
   const report=await page.evaluate(()=>window.__bellworks.advance(30)),target=expected.get(id);
   assert.ok(report.time>=30);assert.deepEqual(report.stages,target.stages);
   assert.equal(report.bellHits>0,target.bell_by_30s);assert.equal(report.stageTimes[8],target.first_bell_seconds);
   for(const [k,v] of Object.entries(target.contacts))assert.equal(report.contacts.includes(k==='barrier'?'obstacle':k),v,`${id} contact ${k}`);
   assert.equal((await page.locator('#progress-number').textContent()).trim(),`${String(report.stages.filter(Boolean).length).padStart(2,'0')} / 09`);
   runs.push({case:id,repeat,initial,...report});
   if(repeat===3)await page.screenshot({path:new URL(`operator/screenshots/${id}_30s.png`,root).pathname});
   console.log(`PASS browser ${id} #${repeat}: real solver agrees with key, UI counts and geometry checked.`);
  }
 }
 // Changes made during a run queue until a full reset, including while paused.
 await page.selectOption('#experiment-case','REF');await page.click('#reset');await page.click('#start');
 await page.evaluate(()=>window.__bellworks.advance(1));await page.click('#pause');
 const paused=await page.evaluate(()=>window.__bellworks.report());await page.evaluate(()=>window.__bellworks.advance(2));
 assert.deepEqual(await page.evaluate(()=>window.__bellworks.report()),paused);
 await page.selectOption('#experiment-case','Y4');assert.match(await page.locator('#intervention-note').textContent(),/queued/);
 assert.equal((await page.evaluate(()=>window.__bellworks.report())).experiment,'REF');
 await page.click('#reset');const reset=await page.evaluate(()=>window.__bellworks.report());assert.equal(reset.time,0);assert.equal(reset.experiment,'Y4');assert.ok(reset.stages.every(v=>!v));
 controls.pauseAndReset=true;controls.queuedConfiguration=true;
 await page.click('[data-speed="0.25"]');assert.equal(await page.evaluate(()=>window.__bellworks.speed),.25);
 await page.click('[data-speed="1"]');assert.equal(await page.evaluate(()=>window.__bellworks.speed),1);controls.speedButtons=true;
 // Resume advances the unchanged solver in manual test mode.
 await page.click('#start');await page.evaluate(()=>window.__bellworks.advance(.5));await page.click('#pause');await page.click('#pause');
 const resumed=await page.evaluate(()=>window.__bellworks.advance(.5));assert.ok(resumed.time>=1);controls.resume=true;
 // Camera controls: home, overhead, orbit, zoom and pan.
 await page.click('#view-home');const home=await page.evaluate(()=>window.__bellworks.camera);await page.click('#view-top');assert.notDeepEqual(await page.evaluate(()=>window.__bellworks.camera),home);
 await page.click('#view-home');await page.mouse.move(850,480);await page.mouse.down();await page.mouse.move(960,530,{steps:8});await page.mouse.up();await page.waitForTimeout(150);assert.notDeepEqual(await page.evaluate(()=>window.__bellworks.camera),home);
 const orbit=await page.evaluate(()=>window.__bellworks.camera);await page.mouse.wheel(0,-300);await page.waitForTimeout(150);assert.notDeepEqual(await page.evaluate(()=>window.__bellworks.camera),orbit);
 const zoom=await page.evaluate(()=>window.__bellworks.camera);await page.mouse.down({button:'right'});await page.mouse.move(880,570,{steps:8});await page.mouse.up({button:'right'});await page.waitForTimeout(150);assert.notDeepEqual(await page.evaluate(()=>window.__bellworks.camera),zoom);controls.camera=true;
 // A normal, non-test page must advance through wall-clock execution as well.
 await page.goto(base+'/round2.html?case=REF');await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 await page.click('#start');
 const deadline=Date.now()+180000;let lastProgress=-1;
 while(Date.now()<deadline){
  realtimeReport=await page.evaluate(()=>window.__bellworks.report());
  const progress=Math.floor(realtimeReport.time/3);
  if(progress!==lastProgress){console.log(`Wall-clock baseline progress: ${realtimeReport.time.toFixed(2)} simulated seconds`);lastProgress=progress;}
  if(realtimeReport.stages.every(Boolean))break;
  await page.waitForTimeout(1000);
 }
 assert.ok(realtimeReport.stages.every(Boolean),'Normal animation baseline did not complete within 180 wall-clock seconds');
 const realtime=realtimeReport;assert.equal(realtime.stageTimes[8],expected.get('REF').first_bell_seconds);controls.realtimeBaseline=true;
 await page.screenshot({path:new URL('operator/screenshots/REF_realtime_complete.png',root).pathname});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);success=true;
}catch(error){failure=String(error);throw error;}finally{
 await writeFile(new URL('operator/browser-validation.json',root),JSON.stringify({generated_at:new Date().toISOString(),success,controls,runs,realtime_report:realtimeReport,failure,errors,external},null,2)+'\n');await browser.close();
}
console.log('PASS: 15 production-browser runs + one wall-clock baseline; reset, pause/resume, queued settings, speed buttons, camera, no errors/external assets.');
