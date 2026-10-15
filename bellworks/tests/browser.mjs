import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {mkdir,writeFile,rm} from 'node:fs/promises';

const base=process.env.TEST_URL||'http://127.0.0.1:4173';
const executablePath=process.env.CHROME_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined);
await mkdir('artifacts',{recursive:true});
await rm('artifacts/browser-results.json',{force:true});
const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});
const external=[],errors=[],consoleErrors=[],checks=[],runs=[];
await context.route('**/*',route=> {
  const url=new URL(route.request().url());
  if(['127.0.0.1','localhost'].includes(url.hostname))return route.continue();
  external.push(url.href);return route.abort('internetdisconnected');
});
const page=await context.newPage();
page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text());});
const report=()=>page.evaluate(()=>window.__bellworks.report());
function pass(name){checks.push(name);console.log('PASS',name);}
try {
  await page.goto(`${base}/?test=1`);
  await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
  await page.waitForTimeout(300);
  const initial=await report();
  assert.equal(initial.time,0);
  assert.equal((await report()).stages.filter(Boolean).length,0);
  await page.screenshot({path:'artifacts/initial.png'});
  pass('Production build initializes without any external network requests');

  await page.locator('#start').click();
  await page.waitForFunction(()=>window.__bellworks.report().time>.5);
  await page.locator('#pause').click();
  const paused=await report();
  await page.waitForTimeout(650);
  assert.deepEqual(await report(),paused);pass('Pause freezes the solver and all body positions');
  await page.locator('#pause').click();
  await page.waitForFunction(()=>window.__bellworks.report().time>5,null,{timeout:90000});
  await page.locator('#pause').click();
  await page.screenshot({path:'artifacts/in-motion.png'});
  await page.locator('#pause').click();
  await page.waitForFunction(()=>window.__bellworks.report().stages[8],null,{timeout:120000});
  const first=await report();assert.ok(first.stages.every(Boolean));assert.ok(first.bellHits>=1);
  assert.ok(first.stageTimes.every((t,i,a)=>i===0||t>a[i-1]));
  await page.locator('#pause').click();
  await page.screenshot({path:'artifacts/completed.png'});
  runs.push({run:1,mode:'real animation loop, normal speed, pause/resume',...first});
  pass(`Complete real-time browser run, physical bell impact at ${first.stageTimes[8].toFixed(3)}s`);

  for(let run=2;run<=3;run++) {
    await page.locator('#reset').click();
    const reset=await report();assert.equal(reset.time,0);assert.ok(reset.stages.every(v=>!v));assert.equal(reset.bellHits,0);assert.deepEqual(reset.position,initial.position);
    assert.equal(await page.locator('#start').isEnabled(),true);
    if(run===3)await page.locator('[data-speed="0.25"]').click();
    await page.locator('#start').click();
    const result=await page.evaluate(()=>window.__bellworks.advance(18));
    assert.ok(result.stages.every(Boolean));assert.ok(result.bellHits>=1);
    assert.deepEqual(result.stageTimes,first.stageTimes);
    runs.push({run,mode:run===3?'reset, slow-mode selected, accelerated fixed-step validation':'reset, accelerated fixed-step validation',...result});
    pass(`Reset and complete run ${run}: all nine stages and mallet/bell collision`);
  }
  await page.locator('#reset').click();
  await page.locator('[data-speed="1"]').click();
  await page.locator('#start').click();
  let before=(await report()).time;
  await page.waitForTimeout(1800);
  const normal=(await report()).time-before;
  await page.locator('[data-speed="0.25"]').click();
  before=(await report()).time;
  await page.waitForTimeout(1800);
  const slow=(await report()).time-before;
  assert.ok(slow>0&&normal>slow*1.7,`time scaling: normal ${normal}, slow ${slow}`);
  pass(`Slow motion changes simulated elapsed time (normal ${normal.toFixed(3)}s, slow ${slow.toFixed(3)}s over equal wall intervals)`);
  await page.locator('#pause').click();
  const initialCamera=await page.evaluate(()=>window.__bellworks.camera);
  await page.mouse.move(720,550);await page.mouse.down();await page.mouse.move(860,600,{steps:8});await page.mouse.up();
  await page.waitForTimeout(300);
  assert.notDeepEqual(await page.evaluate(()=>window.__bellworks.camera),initialCamera);pass('Orbit camera responds to pointer drag');
  const orbitCamera=await page.evaluate(()=>window.__bellworks.camera);
  await page.mouse.wheel(0,250);await page.waitForTimeout(350);
  assert.notDeepEqual(await page.evaluate(()=>window.__bellworks.camera),orbitCamera);pass('Camera zoom responds to scroll');
  const zoomCamera=await page.evaluate(()=>window.__bellworks.camera);
  await page.mouse.move(700,550);await page.mouse.down({button:'right'});await page.mouse.move(760,550,{steps:6});await page.mouse.up({button:'right'});await page.waitForTimeout(350);
  assert.notDeepEqual(await page.evaluate(()=>window.__bellworks.camera),zoomCamera);pass('Camera pan responds to right-drag');
  await page.locator('#view-top').click();await page.waitForTimeout(150);
  assert.ok((await page.evaluate(()=>window.__bellworks.camera))[1]>35);pass('Overhead view');
  await page.locator('#follow').click();assert.equal(await page.locator('#follow').getAttribute('aria-pressed'),'true');
  await page.locator('#sound').click();assert.equal(await page.locator('#sound').getAttribute('aria-pressed'),'false');pass('Ball-follow and mute controls');
  await page.locator('#view-home').click();await page.locator('#reset').click();
  await page.setViewportSize({width:390,height:844});await page.reload();await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});await page.waitForTimeout(300);
  await page.screenshot({path:'artifacts/mobile.png'});
  const startBox=await page.locator('#start').boundingBox();assert.ok(startBox.x>=0&&startBox.x+startBox.width<=390);pass('Mobile viewport: start control remains inside screen');
  assert.deepEqual(errors,[]);assert.deepEqual(consoleErrors,[]);assert.deepEqual(external,[]);pass('No browser exceptions, console errors, or external runtime requests');
  await writeFile('artifacts/browser-results.json',JSON.stringify({generatedAt:new Date().toISOString(),base,checks,runs,errors,consoleErrors,external},null,2));
}finally{await browser.close();}
