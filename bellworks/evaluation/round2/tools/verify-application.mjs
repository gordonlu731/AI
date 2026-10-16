// Smoke-test the extracted application archive's two fully local entry pages.
import {chromium} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const base=process.env.TEST_URL||'http://127.0.0.1:4193',root=new URL('../',import.meta.url);
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
const errors=[],external=[],pages=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/*',r=>{if(['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname))return r.continue();external.push(r.request().url());return r.abort();});
 await page.goto(base+'/?test=1');await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});assert.equal((await page.evaluate(()=>window.__bellworks.report())).time,0);
 await page.click('#start');const original=await page.evaluate(()=>window.__bellworks.advance(18));assert.ok(original.stages.every(Boolean));pages.push({entry:'index.html',report:original});
 await page.goto(base+'/round2.html?test=1&case=Y4');await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 const initial=await page.evaluate(()=>window.__bellworks.report());assert.equal(initial.time,0);assert.equal(initial.experiment,'Y4');assert.ok(Math.abs(initial.ballMass-.329419881105423)<1e-7);
 await page.click('#start');const experimental=await page.evaluate(()=>window.__bellworks.advance(30));const key=JSON.parse(await readFile(new URL('operator/ground-truth.json',root),'utf8')).cases.find(c=>c.id==='Y4');assert.deepEqual(experimental.stages,key.stages);pages.push({entry:'round2.html',initial,report:experimental});
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 await writeFile(new URL('operator/application-archive-validation.json',root),JSON.stringify({generated_at:new Date().toISOString(),success:true,note:'Both entry points served from a freshly extracted Bellworks.zip; no npm install in the extracted project and all external browser requests blocked.',pages,errors,external},null,2)+'\n');
}finally{await browser.close();}
console.log('PASS: freshly extracted application ZIP runs both original and experimental pages without npm install or external runtime assets.');
