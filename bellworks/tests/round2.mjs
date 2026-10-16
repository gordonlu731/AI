import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,cp,rm,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {ROOT,sha,parseResponse,validatePrediction,scorePrediction,freezePrediction,scoreAttempt,verifyInputDataset} from '../evaluation/round2/tools/lib.mjs';
import {initPhysics,Machine} from '../src/machine.js';
import {ExperimentMachine,CASES} from '../evaluation/round2/config/experiments.mjs';
const read=async p=>JSON.parse(await readFile(join(ROOT,p),'utf8'));
const key=await read('operator/ground-truth.json'),spec=await read('input/PHYSICS.json');
const synthetic=()=>({protocol_id:key.protocol_id,cases:key.cases.map(c=>({id:c.id,bell_by_30s:c.bell_by_30s,p_bell_by_30s:c.bell_by_30s?.9:.1,stages:[...c.stages],contacts:{...c.contacts},predicted_first_bell_seconds:null,first_interruption:'SYNTHETIC',reasoning:'SYNTHETIC SOFTWARE TEST ONLY; NOT A MODEL RESULT'}))});
await initPhysics();
test('experiment changes only the intended initial bodies, colliders and density',()=>{
 for(const c of CASES){const m=new ExperimentMachine(c.id),ref=new Machine();try{
  assert.equal(m.time,0);assert.equal(m.started,false);assert.equal(m.ballCollider.radius(),ref.ballCollider.radius());assert.deepEqual({...m.ball.translation()},{...ref.ball.translation()});
  assert.equal(m.dominoes.length,c.removeDominoOrdinal?7:8);
  for(const name of ['gate','wheel','lever','bucket','hammer','bell']){assert.deepEqual({...m[name].translation()},{...ref[name].translation()});assert.deepEqual({...m[name].rotation()},{...ref[name].rotation()});assert.equal(m[name].mass(),ref[name].mass());}
  for(const b of m.dominoes){const ordinal=m.dominoOrdinals.get(b.handle);assert.deepEqual({...b.translation()},{...ref.dominoes[ordinal-1].translation()});assert.equal(b.mass(),ref.dominoes[ordinal-1].mass());}
  if(c.removeDominoOrdinal){assert.equal(m.removedDomino.ordinal,4);assert.notEqual(m.world.getRigidBody(m.removedDomino.bodyHandle)?.handle,m.removedDomino.bodyHandle);assert.notEqual(m.world.getCollider(m.removedDomino.colliderHandle)?.handle,m.removedDomino.colliderHandle);assert.ok(!m.pieces.some(p=>p.body.handle===m.removedDomino.bodyHandle));}
  if(c.barrier){const p=m.obstacle.translation(),half=m.obstacleCollider.halfExtents();assert.ok(m.obstacle.isFixed());assert.equal(m.obstacleCollider.isSensor(),false);assert.ok(Math.abs(p.z-(-3.4+c.barrier.zOffset))<1e-6);assert.deepEqual([half.x*2,half.y*2,half.z*2],[.26,c.barrier.height,c.barrier.width].map(Math.fround));assert.ok(Math.abs(p.y-half.y-(m.trackA(c.barrier.x).y-.15))<1e-6);}
  assert.ok(Math.abs(m.ball.mass()/ref.ball.mass()-c.ballDensity/24)<1e-7);
  // Calling step without release cannot start a hidden mechanism.
  m.step();assert.equal(m.time,0);assert.ok(m.stages.every(v=>!v));
 }finally{m.dispose();ref.dispose();}}
});
test('initial-state export matches frozen experiment parameters and unchanged source',async()=>{
 const lock=await read('operator/design-lock.json');assert.equal(key.design_lock_sha256,sha(await readFile(join(ROOT,'operator/design-lock.json'))));
 assert.deepEqual(spec.source_sha256,lock.source_sha256);assert.deepEqual(spec.source_sha256,key.source_sha256);
 for(const [path,hash] of Object.entries(spec.source_sha256))assert.equal(sha(await readFile(new URL('../'+path,import.meta.url))),hash);
 const prior=JSON.parse(await readFile(new URL('../evaluation/input/PHYSICS.json',import.meta.url),'utf8'));assert.equal(prior.source_sha256,spec.source_sha256['src/machine.js']);
 assert.equal(spec.configurations.length,5);for(const c of spec.configurations){const ball=c.objects.find(o=>o.id==='ball');assert.equal(ball.initial_type,'fixed');assert.equal(ball.colliders[0].shape.radius,Math.fround(.32));assert.ok(ball.linear_velocity.every(v=>v===0));assert.equal(c.joints.length,6);assert.equal(c.objects.filter(o=>o.id.startsWith('domino_')).length,c.id==='Y3'?7:8);}
});
test('fifteen stable real-solver runs back the key and retain actual contact evidence',async()=>{
 const evidence=await read('operator/solver-evidence.json');assert.equal(key.scoring_ready,true);assert.equal(key.reference_matches_original,true);assert.equal(evidence.runs.length,15);
 for(const id of ['REF',...CASES.map(c=>c.id)]){
  const runs=evidence.runs.filter(r=>r.case===id),truth=id==='REF'?key.reference:key.cases.find(c=>c.id===id);assert.equal(runs.length,3);assert.equal(truth.stable,true);
  for(const r of runs){assert.equal(r.steps,3600);assert.ok(r.time>=30);assert.deepEqual(r.observed,{bell_by_30s:truth.bell_by_30s,stages:truth.stages,contacts:truth.contacts,first_bell_seconds:truth.first_bell_seconds});assert.ok(r.trajectory.length>100);assert.ok(r.contact_events.length>0);
   for(const [body,hit] of Object.entries(truth.contacts))assert.equal(r.contact_events.some(e=>e.event==='collision-start'&&e.bodies.includes('ball')&&e.bodies.includes(body)),hit);
   assert.equal(r.contact_events.some(e=>e.event==='collision-start'&&e.bodies.includes('hammer')&&e.bodies.includes('bell')),truth.bell_by_30s);
   if(id==='REF')assert.deepEqual(r.stageTimes,evidence.original_constructor_report.stageTimes);
  }
 }
 assert.equal((await readdir(join(ROOT,'operator/runs'))).length,15);
});
test('browser runs, time-zero screenshots and controls were actually verified',async()=>{
 const b=await read('operator/browser-validation.json'),c=await read('operator/capture-validation.json');assert.equal(b.success,true);assert.equal(b.runs.length,15);assert.ok(Object.values(b.controls).every(Boolean));assert.ok(b.controls.realtimeBaseline);assert.deepEqual(b.errors,[]);assert.deepEqual(b.external,[]);assert.equal(c.captures.length,7);assert.ok(c.captures.every(s=>s.time===0&&s.stages.every(v=>!v)));assert.deepEqual(c.errors,[]);assert.deepEqual(c.external,[]);
 for(const run of b.runs){const truth=run.case==='REF'?key.reference:key.cases.find(c=>c.id===run.case);assert.deepEqual(run.stages,truth.stages);assert.equal(run.stageTimes[8],truth.first_bell_seconds);}
});
test('only initial attachments and null answer placeholders are in the AI dataset',async()=>{
 const manifest=JSON.parse(await verifyInputDataset()),names=Object.keys(manifest.files);assert.equal(names.length,11);assert.equal(names.filter(n=>n.endsWith('.png')).length,7);
 assert.deepEqual((await readdir(join(ROOT,'input'))).sort(),[...names,'MANIFEST.json'].sort());
 const blank=await read('input/RESPONSE_TEMPLATE.json');assert.equal(blank.protocol_id,'BW-PREDICT-002');assert.ok(blank.cases.every(c=>c.bell_by_30s===null&&c.p_bell_by_30s===null&&c.stages.every(v=>v===null)&&Object.values(c.contacts).every(v=>v===null)));
 for(const name of names.filter(n=>!n.endsWith('.png'))){const s=await readFile(join(ROOT,'input',name),'utf8');assert.ok(!/stageTimes|bellHits|github\.com|solver-evidence|ground-truth/.test(s));for(const time of key.cases.map(c=>c.first_bell_seconds).filter(v=>v!==null))assert.ok(!s.includes(String(time)));}
 assert.ok(new Date((await read('operator/design-lock.json')).locked_at)<new Date(key.generated_at));
});
test('score weights, probability loss, optional time and unstable-run guard',()=>{
 let p=synthetic();assert.equal(scorePrediction(p,key).total_100,100);assert.ok(Math.abs(scorePrediction(p,key).brier_score-.01)<1e-12);
 p.cases.reverse();assert.equal(scorePrediction(p,key).total_100,100);
 p=synthetic();p.cases[0].bell_by_30s=!p.cases[0].bell_by_30s;assert.equal(scorePrediction(p,key).total_100,90);
 p=synthetic();p.cases[0].contacts.barrier=!p.cases[0].contacts.barrier;assert.equal(scorePrediction(p,key).total_100,98.5);
 p=synthetic();p.cases[0].stages[0]=!p.cases[0].stages[0];assert.ok(Math.abs(scorePrediction(p,key).total_100-(100-24/36))<1e-12);
 p=synthetic();p.cases[0].predicted_first_bell_seconds=1;assert.equal(scorePrediction(p,key).total_100,100);
 for(const c of p.cases){c.bell_by_30s=!c.bell_by_30s;c.p_bell_by_30s=1-c.p_bell_by_30s;c.stages=c.stages.map(v=>!v);for(const k of Object.keys(c.contacts))c.contacts[k]=!c.contacts[k];}assert.equal(scorePrediction(p,key).total_100,0);
 assert.throws(()=>scorePrediction(synthetic(),{...key,scoring_ready:false}),/unstable/);
});
test('malformed and wrong-round answers are rejected; one JSON fence can be parsed',()=>{
 assert.equal(parseResponse('\uFEFF```json\n'+JSON.stringify(synthetic())+'\n```').cases.length,4);
 for(const change of [p=>p.protocol_id='BW-PREDICT-001',p=>p.cases.pop(),p=>p.cases[1].id='Y1',p=>p.cases[0].stages[0]=null,p=>p.cases[0].p_bell_by_30s=1.1,p=>p.cases[0].contacts.barrier=null]){const p=synthetic();change(p);assert.throws(()=>validatePrediction(p));}
});
test('freeze/score preserves original bytes, prevents overwrite and detects tampering',async()=>{
 const tmp=await mkdtemp(join(tmpdir(),'bellworks-round2-test-'));try{
  const source=join(tmp,'synthetic.json');await writeFile(source,JSON.stringify(synthetic()));const dir=await freezePrediction(source,{outputRoot:join(tmp,'attempts'),id:'fixture',model:'SYNTHETIC_NOT_A_MODEL'});
  assert.equal((await scoreAttempt(dir)).total_100,100);await assert.rejects(()=>scoreAttempt(dir),/EEXIST/);await assert.rejects(()=>freezePrediction(source,{outputRoot:join(tmp,'attempts'),id:'fixture'}),/EEXIST/);
  await writeFile(join(dir,'prediction.json'),'{}');await assert.rejects(()=>scoreAttempt(dir),/modified/);
  const inputs=join(tmp,'input');await cp(join(ROOT,'input'),inputs,{recursive:true});await writeFile(join(inputs,'SCENE.zh-CN.md'),'MODIFIED');await assert.rejects(()=>verifyInputDataset(inputs),/modified/);
 }finally{await rm(tmp,{recursive:true,force:true});}
});
