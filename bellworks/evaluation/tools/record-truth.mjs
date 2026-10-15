// OPERATOR ONLY. This executes the actual machine; never give this to the model.
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {verifyInputDataset} from './lib.mjs';
import {Machine,initPhysics} from '../../src/machine.js';
import {CASES,CONTACTS,PROTOCOL_ID,HORIZON,REPEATS} from './protocol.mjs';
const sha=b=>createHash('sha256').update(b).digest('hex');
const dir=new URL('../',import.meta.url);const inputManifest=await verifyInputDataset();
const sourceHash=sha(await readFile(new URL('../../src/machine.js',import.meta.url)));
const suppliedPhysics=JSON.parse(await readFile(new URL('input/PHYSICS.json',dir),'utf8'));
if(suppliedPhysics.source_sha256!==sourceHash)throw Error('Input physics was exported from another source revision');
await initPhysics();
const evidence=[],cases=[];
for(const def of [{id:'REF',options:{removeDomino:false,addObstacle:false}},...CASES]){
 let reference;
 for(let repeat=1;repeat<=REPEATS;repeat++){
  const m=new Machine(def.options);try{
   m.release();for(let i=0;i<HORIZON*120;i++)m.step();const r=m.report();
   const observed={bell_by_30s:r.bellHits>0,stages:r.stages,contacts:Object.fromEntries(CONTACTS.map(k=>[k,r.contacts.includes(k==='barrier'?'obstacle':k)])),first_bell_seconds:r.stageTimes[8]};
   if(reference&&JSON.stringify(observed)!==JSON.stringify(reference))throw Error(`${def.id}: repeats disagree; dataset is not ready for deterministic scoring`);
   if(def.id==='REF'&&!observed.stages.every(Boolean))throw Error('Reference calibration no longer holds');
   reference=observed;evidence.push({case:def.id,repeat,...r});
  }finally{m.dispose();}
 }
 if(def.id!=='REF')cases.push({id:def.id,...reference});
 console.log(`Recorded ${def.id}: ${REPEATS} real solver runs, no injected stage outcomes`);
}
if(sourceHash!==sha(await readFile(new URL('../../src/machine.js',import.meta.url))))throw Error('Machine source changed during collection');
const provenance={protocol_id:PROTOCOL_ID,generated_at:new Date().toISOString(),source_sha256:sourceHash,input_manifest_sha256:sha(inputManifest),engine:'@dimforge/rapier3d-compat 0.20.0',repeats:REPEATS,horizon_seconds:HORIZON};
await writeFile(new URL('operator/ground-truth.json',dir),JSON.stringify({...provenance,cases},null,2)+'\n');
await writeFile(new URL('operator/solver-evidence.json',dir),JSON.stringify({...provenance,runs:evidence},null,2)+'\n');
