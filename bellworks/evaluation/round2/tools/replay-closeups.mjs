// OPERATOR ONLY. Post-run pictures are excluded from the AI input allowlist.
import {chromium} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url),base=process.env.TEST_URL||'http://127.0.0.1:4192';
const key=JSON.parse(await readFile(new URL('operator/ground-truth.json',root),'utf8'));
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||(process.platform==='linux'?'/usr/bin/chromium':undefined),headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
const records=[],errors=[],external=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route('**/*',r=>{if(['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname))return r.continue();external.push(r.request().url());return r.abort();});
 await page.goto(base+'/round2.html?test=1');await page.waitForFunction(()=>window.__bellworks,null,{timeout:60000});
 for(const id of ['Y1','Y4']){
  await page.selectOption('#experiment-case',id);await page.click('#reset');await page.click('#start');
  const report=await page.evaluate(()=>window.__bellworks.advance(30));assert.deepEqual(report.stages,key.cases.find(c=>c.id===id).stages);
  await page.evaluate(()=>window.__bellworks.inspect('dominoes'));
  const hide=await page.addStyleTag({content:'#app > :not(canvas){visibility:hidden!important}'});
  const file=`screenshots/${id}_30s_CLOSEUP.png`;await page.screenshot({path:new URL('operator/'+file,root).pathname});await hide.evaluate(e=>e.remove());records.push({case:id,file,...report});
 }
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 await writeFile(new URL('operator/closeup-validation.json',root),JSON.stringify({generated_at:new Date().toISOString(),records,errors,external},null,2)+'\n');
}finally{await browser.close();}
console.log('Verified two additional browser diagnostic replays and saved final close-ups in operator only.');
