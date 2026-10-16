import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const base=process.env.TEST_URL||'http://127.0.0.1:4192',dir=new URL('../input/',import.meta.url);
await mkdir(dir,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
const captures=[],errors=[],external=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/*',r=>{if(['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname))return r.continue();external.push(r.request().url());return r.abort();});
 await page.goto(base+'/round2.html?test=1');await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 async function shot(file,id,angle){
  await page.selectOption('#experiment-case',id);
  const r=await page.evaluate(()=>window.__bellworks.report());
  assert.equal(r.experiment,id);assert.equal(r.time,0);assert.equal(r.bellHits,0);assert.ok(r.stages.every(v=>!v));
  const geometry=await page.evaluate(a=>window.__bellworks.inspect(a),angle);
  assert.equal(geometry.visibleDominoes,id==='Y3'?7:8);assert.equal(geometry.visibleObstacle,['Y1','Y2'].includes(id));
  const hide=await page.addStyleTag({content:'#app > :not(canvas){visibility:hidden!important}'});
  await page.screenshot({path:new URL(file,dir).pathname});await hide.evaluate(e=>e.remove());
  captures.push({file,case:id,angle,time:r.time,stages:r.stages,geometry});
 }
 await shot('00_REFERENCE_OVERVIEW.png','REF','home');
 await shot('01_REFERENCE_RAMP.png','REF','ramp');
 await shot('02_REFERENCE_DOMINOES.png','REF','dominoes');
 await shot('03_Y1_INITIAL.png','Y1','ramp');
 await shot('04_Y2_INITIAL.png','Y2','ramp');
 await shot('05_Y3_INITIAL.png','Y3','dominoes');
 await shot('06_Y4_INITIAL.png','Y4','home');
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 await writeFile(new URL('../operator/capture-validation.json',import.meta.url),JSON.stringify({generated_at:new Date().toISOString(),captures,errors,external},null,2)+'\n');
 console.log('PASS: seven real-browser initial screenshots; time=0, all stage flags false, mesh/collider counts checked, no errors/external requests.');
}finally{await browser.close();}
