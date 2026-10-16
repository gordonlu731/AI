// OPERATOR ONLY. Actual 120 Hz Rapier steps; no outcome assignments or tuning.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {initPhysics,Machine} from '../../../src/machine.js';
import {ExperimentMachine,REFERENCE,CASES,PROTOCOL_ID,CONTACTS,HORIZON,REPEATS} from '../config/experiments.mjs';
import {verifyInputDataset} from './lib.mjs';
const root=new URL('../',import.meta.url),sha=b=>createHash('sha256').update(b).digest('hex');
const manifest=await verifyInputDataset(),spec=JSON.parse(await readFile(new URL('input/PHYSICS.json',root),'utf8')),lock=JSON.parse(await readFile(new URL('operator/design-lock.json',root),'utf8'));
for(const [path,hash] of Object.entries(spec.source_sha256))if(hash!==sha(await readFile(new URL('../../../'+path,import.meta.url)))||hash!==lock.source_sha256[path])throw Error(`Initial configuration/source changed since lock: ${path}`);
await initPhysics();await mkdir(new URL('operator/runs/',root),{recursive:true});
function observe(m){const r=m.report();return {bell_by_30s:r.bellHits>0,stages:r.stages,contacts:Object.fromEntries(CONTACTS.map(k=>[k,r.contacts.includes(k==='barrier'?'obstacle':k)])),first_bell_seconds:r.stageTimes[8]};}
// Read-only tap of the queue's real events. Original Machine callback still
// receives every event unchanged. No body, collider, stage or force is altered.
function recordContacts(m){
 const events=[],names=new Map([[m.ball.handle,'ball'],...m.dominoes.map(b=>[b.handle,`domino_${String(m.dominoOrdinals.get(b.handle)).padStart(2,'0')}`]),...['gate','wheel','lever','bucket','hammer','bell'].map(k=>[m[k].handle,k]),...(m.obstacle?[[m.obstacle.handle,'barrier']]:[])]);
 const drain=m.events.drainCollisionEvents.bind(m.events);
 m.events.drainCollisionEvents=callback=>drain((a,b,started)=>{
  callback(a,b,started);
  const ca=m.world.getCollider(a),cb=m.world.getCollider(b),ba=ca?.parent(),bb=cb?.parent();
  const pair=[names.get(ba?.handle),names.get(bb?.handle)];
  if(pair.every(Boolean)&&(pair.includes('ball')||(pair.includes('hammer')&&pair.includes('bell'))))events.push({time:m.time,event:started?'collision-start':'collision-end',bodies:pair,ball_position:{...m.ball.translation()},ball_velocity:{...m.ball.linvel()}});
 });return events;
}
// Untouched original constructor establishes an additional baseline comparator.
const original=new Machine();original.release();for(let n=0;n<HORIZON*120;n++)original.step();const originalReport=original.report();original.dispose();
const runs=[],cases=[];let referenceOK=true;
for(const def of [REFERENCE,...CASES]){
 const observations=[];
 for(let repeat=1;repeat<=REPEATS;repeat++){
  const m=new ExperimentMachine(def.id);try{
   const contactEvents=recordContacts(m),trajectory=[{time:0,position:{...m.ball.translation()},velocity:{...m.ball.linvel()}}];
   m.release();for(let n=1;n<=HORIZON*120;n++){m.step();if(n%30===0)trajectory.push({time:m.time,position:{...m.ball.translation()},velocity:{...m.ball.linvel()}});}
   const report=m.report(),observed=observe(m),run={case:def.id,repeat,steps:HORIZON*120,...report,observed,contact_events:contactEvents,trajectory};
   observations.push(observed);runs.push(run);
   await writeFile(new URL(`operator/runs/${def.id}_${String(repeat).padStart(2,'0')}.json`,root),JSON.stringify(run,null,2)+'\n',{flag:'wx'});
   if(def.id==='REF'&&(!report.stages.every(Boolean)||JSON.stringify(report.stageTimes)!==JSON.stringify(originalReport.stageTimes)))referenceOK=false;
   console.log(`Recorded ${def.id} #${repeat}: ${report.stages.filter(Boolean).length}/9; bell=${observed.bell_by_30s}; first=${observed.first_bell_seconds}; real contact events=${contactEvents.length}`);
  }finally{m.dispose();}
 }
 const signatures=observations.map(o=>JSON.stringify(o)),stable=signatures.every(s=>s===signatures[0]);
 cases.push({id:def.id,stable,repeats:REPEATS,...(stable?observations[0]:{observations,warning:'Repeats disagree. Do not use a single deterministic label or silently discard runs.'})});
}
const metadata={protocol_id:PROTOCOL_ID,generated_at:new Date().toISOString(),source_sha256:spec.source_sha256,input_manifest_sha256:sha(manifest),design_lock_sha256:sha(await readFile(new URL('operator/design-lock.json',root))),engine:'@dimforge/rapier3d-compat 0.20.0',horizon_seconds:HORIZON,repeats:REPEATS,reference_matches_original:referenceOK,scoring_ready:referenceOK&&cases.every(c=>c.stable)};
await writeFile(new URL('operator/ground-truth.json',root),JSON.stringify({...metadata,reference:cases[0],cases:cases.slice(1)},null,2)+'\n',{flag:'wx'});
await writeFile(new URL('operator/solver-evidence.json',root),JSON.stringify({...metadata,original_constructor_report:originalReport,runs},null,2)+'\n',{flag:'wx'});
if(!metadata.scoring_ready){console.error('Evidence preserved, but baseline or repeat consistency failed. Deterministic scoring disabled.');process.exitCode=1;}
else console.log('All 15 fresh-world experimental runs are stable; baseline matches the untouched original. Evidence preserved.');
