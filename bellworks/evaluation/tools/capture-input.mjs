import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const base=process.env.TEST_URL||'http://127.0.0.1:4184';
const dir=new URL('../input/',import.meta.url);await mkdir(dir,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
const captures=[],errors=[],external=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/*',r=>{if(['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname))return r.continue();external.push(r.request().url());return r.abort();});
 await page.goto(base+'/?test=1');await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 async function shot(name,expected){
  const r=await page.evaluate(()=>window.__bellworks.report());
  assert.equal(r.time,0);assert.equal(r.bellHits,0);assert.ok(r.stages.every(v=>!v));assert.deepEqual(r.interventions,expected);
  const hide=await page.addStyleTag({content:'#app > :not(canvas){visibility:hidden!important}'});
  await page.screenshot({path:new URL(name,dir).pathname});
  await hide.evaluate(element=>element.remove());
  captures.push({file:name,time:r.time,stages:r.stages,initial_options:r.interventions});
 }
 await shot('01_REFERENCE_OVERVIEW.png',{removeDomino:false,addObstacle:false});
 await page.locator('#view-top').click();await shot('02_REFERENCE_OVERHEAD.png',{removeDomino:false,addObstacle:false});
 await page.locator('#view-home').click();await page.locator('#add-obstacle').check();await shot('03_BARRIER_INITIAL.png',{removeDomino:false,addObstacle:true});
 await page.locator('#add-obstacle').uncheck();await page.locator('#remove-domino').check();await shot('04_DOMINO_REMOVED_INITIAL.png',{removeDomino:true,addObstacle:false});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 await writeFile(new URL('../operator/capture-validation.json',import.meta.url),JSON.stringify({generated_at:new Date().toISOString(),captures,errors,external},null,2));
 console.log('PASS: four initial screenshots; every capture time=0, stage flags all false, no browser errors or external requests.');
}finally{await browser.close();}
