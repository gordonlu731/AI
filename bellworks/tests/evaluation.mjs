import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,mkdtemp,cp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {ROOT,sha,parseResponse,validatePrediction,scorePrediction,freezePrediction,scoreAttempt,verifyInputDataset} from '../evaluation/tools/lib.mjs';
const truth=JSON.parse(await readFile(join(ROOT,'operator/ground-truth.json'),'utf8'));
const perfect=()=>({protocol_id:truth.protocol_id,cases:truth.cases.map(c=>({id:c.id,bell_by_30s:c.bell_by_30s,p_bell_by_30s:c.bell_by_30s?.9:.1,stages:[...c.stages],contacts:{...c.contacts},predicted_first_bell_seconds:null,reasoning:'SYNTHETIC TEST FIXTURE, NOT A MODEL PREDICTION'}))});
test('perfect synthetic fixture scores 100; Brier is 0.01; order does not matter',()=>{
 const p=perfect(),r=scorePrediction(p,truth);assert.equal(r.total_100,100);assert.ok(Math.abs(r.brier_score-.01)<1e-12);p.cases.reverse();assert.equal(scorePrediction(p,truth).total_100,100);
});
test('fully inverted synthetic fixture scores zero',()=>{
 const p=perfect();for(const c of p.cases){c.bell_by_30s=!c.bell_by_30s;c.p_bell_by_30s=1-c.p_bell_by_30s;c.stages=c.stages.map(v=>!v);for(const k of Object.keys(c.contacts))c.contacts[k]=!c.contacts[k];}const r=scorePrediction(p,truth);assert.equal(r.total_100,0);assert.ok(Math.abs(r.brier_score-.81)<1e-12);
});
test('predeclared individual weights are respected',()=>{
 let p=perfect();p.cases[0].bell_by_30s=!p.cases[0].bell_by_30s;assert.equal(scorePrediction(p,truth).total_100,90);
 p=perfect();p.cases[0].contacts.barrier=!p.cases[0].contacts.barrier;assert.equal(scorePrediction(p,truth).total_100,98.5);
 p=perfect();p.cases[0].stages[0]=!p.cases[0].stages[0];assert.ok(Math.abs(scorePrediction(p,truth).total_100-(100-24/36))<1e-12);
});
test('optional time is not scored and contradictions are reported',()=>{
 const p=perfect();p.cases[0].predicted_first_bell_seconds=1;assert.equal(scorePrediction(p,truth).total_100,100);p.cases[0].stages[8]=!p.cases[0].bell_by_30s;p.cases[0].p_bell_by_30s=1-p.cases[0].p_bell_by_30s;assert.equal(scorePrediction(p,truth).details[0].consistency_warnings.length,2);
});
test('reject missing cases, duplicates, null flags and invalid probabilities',()=>{
 let p=perfect();p.cases.pop();assert.throws(()=>validatePrediction(p));p=perfect();p.cases[1].id=p.cases[0].id;assert.throws(()=>validatePrediction(p));p=perfect();p.cases[0].stages[0]=null;assert.throws(()=>validatePrediction(p));for(const bad of [NaN,Infinity,1.01,-.1,'0.5']){p=perfect();p.cases[0].p_bell_by_30s=bad;assert.throws(()=>validatePrediction(p));}
});
test('UTF-8 BOM and a single JSON fence can be parsed',()=>{assert.equal(parseResponse('\uFEFF```json\n'+JSON.stringify(perfect())+'\n```').cases.length,4);});
test('input hashes detect a modified attachment',async()=>{
 await verifyInputDataset();const tmp=await mkdtemp(join(tmpdir(),'bellworks-input-test-'));try{await cp(join(ROOT,'input'),tmp,{recursive:true});await writeFile(join(tmp,'SCENE.zh-CN.md'),'MODIFIED');await assert.rejects(()=>verifyInputDataset(tmp),/modified/);}finally{await rm(tmp,{recursive:true,force:true});}
});
test('freeze-score round trip, no overwrite, prediction tamper detection and dataset mismatch',async()=>{
 const tmp=await mkdtemp(join(tmpdir(),'bellworks-score-test-'));try{
  const source=join(tmp,'synthetic.json');await writeFile(source,JSON.stringify(perfect()));const out=join(tmp,'attempts');await mkdir(out);
  const dir=await freezePrediction(source,{outputRoot:out,id:'fixture',model:'SYNTHETIC_NOT_A_MODEL'});assert.equal((await scoreAttempt(dir)).total_100,100);
  await assert.rejects(()=>scoreAttempt(dir),/EEXIST/);await assert.rejects(()=>freezePrediction(source,{outputRoot:out,id:'fixture'}),/EEXIST/);
  await writeFile(join(dir,'prediction.json'),'{}');await assert.rejects(()=>scoreAttempt(dir),/modified/);
  const other=await freezePrediction(source,{outputRoot:out,id:'mismatch'});const wrong=join(tmp,'wrong-key.json');await writeFile(wrong,JSON.stringify({...truth,input_manifest_sha256:'wrong'}));await assert.rejects(()=>scoreAttempt(other,wrong),/another input/);
 }finally{await rm(tmp,{recursive:true,force:true});}
});
test('answer key is backed by 15 consistent real solver runs and zero-time captures',async()=>{
 const e=JSON.parse(await readFile(join(ROOT,'operator/solver-evidence.json'),'utf8')),c=JSON.parse(await readFile(join(ROOT,'operator/capture-validation.json'),'utf8'));assert.equal(e.runs.length,15);assert.equal(e.source_sha256,sha(await readFile(new URL('../src/machine.js',import.meta.url))));
 for(const id of ['REF','X1','X2','X3','X4']){const runs=e.runs.filter(r=>r.case===id);assert.equal(runs.length,3);assert.ok(runs.every(r=>r.time>=30));assert.deepEqual(runs[0].stageTimes,runs[1].stageTimes);assert.deepEqual(runs[1].stageTimes,runs[2].stageTimes);if(id==='REF')assert.ok(runs.every(r=>r.stages.every(Boolean)));}
 assert.equal(c.captures.length,4);assert.ok(c.captures.every(r=>r.time===0&&r.stages.every(v=>!v)));assert.deepEqual(c.errors,[]);assert.deepEqual(c.external,[]);
});
test('input has only allowlisted files, empty answers, and no measured result payloads',async()=>{
 const manifest=JSON.parse(await verifyInputDataset());assert.equal(Object.keys(manifest.files).length,8);
 const spec=JSON.parse(await readFile(join(ROOT,'input/PHYSICS.json'),'utf8'));assert.equal(spec.objects.length,15);assert.equal(spec.joints.length,6);assert.ok(!('stageTimes' in spec)&&!('bellHits' in spec));
 const blank=JSON.parse(await readFile(join(ROOT,'input/RESPONSE_TEMPLATE.json'),'utf8'));assert.ok(blank.cases.every(c=>c.bell_by_30s===null&&c.stages.every(v=>v===null)));
 for(const name of Object.keys(manifest.files).filter(n=>!n.endsWith('.png'))){const text=await readFile(join(ROOT,'input',name),'utf8');for(const t of truth.cases.map(c=>c.first_bell_seconds).filter(v=>v!==null))assert.ok(!text.includes(String(t)),`Measured time leaked into ${name}`);assert.ok(!text.includes('stageTimes'));assert.ok(!text.includes('github.com'));}
});
