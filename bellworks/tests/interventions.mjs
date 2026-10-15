import assert from 'node:assert/strict';
import {mkdir,writeFile,rm} from 'node:fs/promises';
import {initPhysics,Machine} from '../src/machine.js';
await initPhysics();await mkdir('artifacts',{recursive:true});
await rm('artifacts/intervention-physics.json',{force:true});
// Recorded from the recoverable, successful pre-intervention revision 0f8d6c0.
const baselineTimes=[.9916667183861136,3.1250001629814506,4.241666887886822,9.133333809673786,10.975000572390854,12.066667295992374,13.525000705383718,14.716667434200644,14.825000773184001];
const runs=[];
function run(scenario,number,options) {
  const m=new Machine(options);
  try {
    assert.equal(m.time,0);assert.equal(m.dominoes.length,options.removeDomino?7:8);
    if(options.removeDomino){
      assert.equal(m.removedDomino.index,7);
      // Rapier's JS lookup may return a newly allocated occupant of the same
      // slot; compare the full generation-bearing handle, not slot presence.
      assert.notEqual(m.world.getRigidBody(m.removedDomino.bodyHandle)?.handle,m.removedDomino.bodyHandle);
      assert.notEqual(m.world.getCollider(m.removedDomino.colliderHandle)?.handle,m.removedDomino.colliderHandle);
      assert.ok(m.pieces.every(p=>p.body.handle!==m.removedDomino.bodyHandle));
    }
    assert.equal(!!m.obstacle,!!options.addObstacle);
    if(m.obstacle){assert.ok(m.obstacle.isFixed());assert.equal(m.obstacle.numColliders(),1);}
    m.release();let maxX=-Infinity;
    for(let i=0;i<120*30;i++){m.step();if(m.obstacle)maxX=Math.max(maxX,m.ball.translation().x);}
    const report=m.report();assert.ok(report.time>=30); // an obstruction never freezes time
    if(options.addObstacle){
      assert.ok(report.obstacleHits>=1);assert.ok(report.contacts.includes('obstacle'));
      assert.ok(maxX<=-8.32,`Ball bypassed barrier: ${maxX}`);
      assert.deepEqual(report.stages,[true,false,false,false,false,false,false,false,false]);
      assert.equal(report.bellHits,0);
      let contacts=0;m.world.contactPair(m.ballCollider,m.obstacleCollider,manifold=>{contacts+=manifold.numContacts();});
      assert.ok(contacts>0,'Ball must remain in actual Rapier contact with barrier');
    }else{
      assert.ok(report.stages.every(Boolean));assert.ok(report.bellHits>0);assert.equal(report.obstacleHits,0);
      if(!options.removeDomino)assert.deepEqual(report.stageTimes,baselineTimes);
    }
    const result={scenario,run:number,secondsSimulated:30,...report};
    if(options.addObstacle)result.maxBallX=maxX;
    runs.push(result);console.log(`PASS ${scenario} run ${number}: ${report.stages.filter(Boolean).length}/9, bell ${report.stageTimes[8]}, obstacle contacts ${report.obstacleHits}`);
  } finally {m.dispose();}
}
for(let i=1;i<=3;i++) {
  run('A default',i,{});
  run('B obstacle enabled',i,{addObstacle:true});
  run('C obstacle disabled again',i,{addObstacle:false});
  run('D final domino removed',i,{removeDomino:true});
  run('Independent options combined',i,{removeDomino:true,addObstacle:true});
}
await writeFile('artifacts/intervention-physics.json',JSON.stringify({generatedAt:new Date().toISOString(),baselineCommit:'0f8d6c03d0709106674becd4b4abb721bd360e39',runs},null,2));
