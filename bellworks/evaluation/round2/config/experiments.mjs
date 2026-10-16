import {Machine} from '../../../src/machine.js';
import {Vector3} from 'three';
import {getConfiguration} from './parameters.mjs';
export {CASES,REFERENCE,PROTOCOL_ID,HORIZON,REPEATS,CONTACTS} from './parameters.mjs';
export class ExperimentMachine extends Machine {
 constructor(id='REF'){
  const config=getConfiguration(id);
  super(); // Exact original baseline construction, before release or any step.
  this.experimentId=id;this.experimentConfig=config;
  this.dominoOrdinals=new Map(this.dominoes.map((b,i)=>[b.handle,i+1]));
  if(config.removeDominoOrdinal!==null){
   const index=config.removeDominoOrdinal-1,body=this.dominoes[index],handle=body.handle;
   this.removedDomino={index,ordinal:config.removeDominoOrdinal,bodyHandle:handle,colliderHandle:body.collider(0).handle};
   this.dominoes.splice(index,1);
   this.pieces=this.pieces.filter(p=>p.body.handle!==handle);
   this.world.removeRigidBody(body);
  }
  if(config.ballDensity!==24){
   this.ballCollider.setDensity(config.ballDensity);
   this.ball.recomputeMassPropertiesFromColliders();
  }
  if(config.barrier){
   const b=config.barrier,p=this.trackA(b.x).add(new Vector3(0,b.bottomRelativeToTrack+b.height/2,b.zOffset));
   this.obstacle=this.body(p);
   this.obstacleCollider=this.box(this.obstacle,[b.thickness,b.height,b.width],new Vector3(),'barrier');
  }
  this.interventions=Object.freeze({removeDomino:config.removeDominoOrdinal!==null,addObstacle:!!config.barrier});
 }
 report(){return {...super.report(),experiment:this.experimentId,ballDensity:this.ballCollider.density(),ballMass:this.ball.mass()};}
}
