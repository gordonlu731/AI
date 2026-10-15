import RAPIER from '@dimforge/rapier3d-compat';
import { Quaternion, Vector3 } from 'three';

export const STAGES = [
  ['The first descent', 'Gravity takes the lead', 'Ramp'],
  ['The domino effect', 'A ripple of falling brass', 'Dominoes'],
  ['A passing pendulum', 'Momentum opens the way', 'Pendulum'],
  ['Around the bend', 'A descending, railed return', 'Gravity spiral'],
  ['A turn of the wheel', 'Steel meets a copper turbine', 'Paddle wheel'],
  ['A delicate balance', 'One small ball tips the scales', 'Seesaw'],
  ['The tipping point', 'A loaded tray gives way', 'Tipping bucket'],
  ['The final swing', 'Motion finds its last messenger', 'Hammer'],
  ['Ring it home', 'A physical strike. A little joy.', 'Bell'],
];
const V = (x=0,y=0,z=0) => new Vector3(x,y,z);
const Q = () => new Quaternion();
const axisY = V(0,1,0), axisZ = V(0,0,1);
export async function initPhysics() { await RAPIER.init(); }

/** There are no timeline events, motors, forces after release, or stage callbacks
 * that alter the world. Only gravity, contacts, and passive revolute joints. */
export class Machine {
  constructor() {
    this.world = new RAPIER.World({x:0,y:-9.81,z:0});
    this.world.timestep = 1/120;
    this.world.numSolverIterations = 12;
    this.world.numInternalPgsIterations = 4;
    this.events = new RAPIER.EventQueue(true);
    this.pieces = [];
    this.decor = [];
    this.stages = STAGES.map(() => false);
    this.stageTimes = STAGES.map(() => null);
    this.time = 0;
    this.started = false;
    this.bellHits = 0;
    this.contacts = new Set();
    this.build();
  }
  body(p, q=Q(), dynamic=false) {
    const d = dynamic ? RAPIER.RigidBodyDesc.dynamic().setCanSleep(false).setCcdEnabled(true) : RAPIER.RigidBodyDesc.fixed();
    return this.world.createRigidBody(d.setTranslation(p.x,p.y,p.z).setRotation(q));
  }
  box(body, size, offset=V(), mat='wood', opt={}) {
    const c=RAPIER.ColliderDesc.cuboid(size[0]/2,size[1]/2,size[2]/2)
      .setTranslation(offset.x,offset.y,offset.z).setFriction(opt.friction ?? .32)
      .setRestitution(0).setDensity(opt.density ?? 1)
      .setActiveEvents(RAPIER.ActiveEvents.COLLISION_EVENTS);
    if(opt.rotation) c.setRotation(opt.rotation);
    const collider=this.world.createCollider(c,body);
    this.pieces.push({body,collider,shape:'box',size,offset,mat,q:opt.rotation || Q(),...opt});
    return collider;
  }
  sphere(body, radius, offset=V(),mat='steel',opt={}) {
    const c=RAPIER.ColliderDesc.ball(radius).setTranslation(offset.x,offset.y,offset.z)
      .setDensity(opt.density ?? 1).setFriction(.35).setRestitution(.05).setActiveEvents(RAPIER.ActiveEvents.COLLISION_EVENTS);
    const collider=this.world.createCollider(c,body);
    this.pieces.push({body,collider,shape:'sphere',size:[radius],offset,mat,q:Q(),...opt});
    return collider;
  }
  fixedBox(p,size,mat='wood',q=Q(),opt={}) { return this.box(this.body(p,q),size,V(),mat,opt); }
  hinge(p, yaw, make, limits) {
    const q=Q().setFromAxisAngle(axisY,yaw);
    const anchor=this.body(p,q), body=this.body(p,q,true);
    make(body);
    const joint=this.world.createImpulseJoint(RAPIER.JointData.revolute(V(),V(),axisZ),anchor,body,true);
    joint.setContactsEnabled(false);
    if(limits) joint.setLimits(limits[0],limits[1]);
    body.setAngularDamping(.15);
    return body;
  }
  frameDecor(p,yaw,width,height,style='gate') {
    this.decor.push({kind:'frame',p:p.clone(),yaw,width,height,style});
  }
  build() {
    this.fixedBox(V(0,-.65,0),[29,.8,16],'base');
    const a=(x)=>V(x,12-(x+10)*.2,-3.4);
    const b=(x)=>V(x,6.4-(8-x)*.218-(x < -5.6 ? 1.3 : 0),3.4);
    this.trackA=a; this.trackB=b;
    this.path=[];
    for(let x=-10;x<8;x+=.45) this.path.push(a(x));
    this.path.push(a(8));
    for(let i=1;i<=48;i++) {
      const t=i/48,theta=-Math.PI/2+t*Math.PI;
      this.path.push(V(8+3.4*Math.cos(theta),8.4-2*t,3.4*Math.sin(theta)));
    }
    for(let x=7.6;x>-10.1;x-=.4) this.path.push(b(x));
    for(let i=0;i<this.path.length-1;i++) {
      const p=this.path[i],end=this.path[i+1],delta=end.clone().sub(p),center=p.clone().add(end).multiplyScalar(.5);
      const horizontal=Math.hypot(delta.x,delta.z),yaw=Math.atan2(-delta.z,delta.x);
      const q=Q().setFromAxisAngle(axisY,yaw).multiply(Q().setFromAxisAngle(axisZ,Math.atan2(delta.y,horizontal)));
      const skip=center.z>3.35 && center.x<7.9 && ((center.x<2.22 && center.x>-.22) || (center.x< -2.25 && center.x> -6.05));
      if(!skip) this.fixedBox(center.clone().add(V(0,-.09,0)),[delta.length()+.09,.18,1.9],'wood',q);
      const side=V(0,0,1).applyQuaternion(q);
      for(const sign of [-1,1]) {
        if(center.z>3.35 && center.x < -2.25 && center.x > -6.05) continue;
        const c=center.clone().addScaledVector(side,sign*1.01).add(V(0,.21,0));
        this.fixedBox(c,[delta.length()+.10,.52,.10],'rail',q);
      }
      if(i%9===0) this.decor.push({kind:'support',p:center.clone(),yaw});
    }
    this.decor.push({kind:'curve',p:V(8,0,0)});
    this.ball=this.body(a(-9.35).add(V(0,.38,0)),Q(),true);
    this.ballCollider=this.sphere(this.ball,.32,V(),'ball',{density:24});
    this.ball.setBodyType(RAPIER.RigidBodyType.Fixed,true);
    this.initialBall=this.ball.translation();

    // 01 — the released ball rolls down a sloped, railed runway.
    this.decor.push({kind:'launcher',p:a(-9.6)});
    // 02 — each tile topples into the next; the ball follows the cascade.
    this.dominoes=[];
    for(let i=0;i<8;i++) {
      const x=-6.9+i*.42,p=a(x).add(V(.076,.382,i===7?0:.43));
      const body=this.body(p,Q().setFromAxisAngle(axisZ,-Math.atan(.2)),true);
      this.box(body,[.24,.76,i===7?1.80:.58],V(),i%2?'ivory':'copper',{density:.35});
      this.dominoes.push(body);
    }
    // 03 — a free pendulum with a transverse axle is pushed aside by impact.
    const gp=a(.1).add(V(0,1.75,0));
    this.gate=this.hinge(gp,0,body=> {
      this.box(body,[.12,1.15,.17],V(0,-.59,0),'brass',{density:.4});
      this.box(body,[.18,.50,1.45],V(0,-1.38,0),'teal',{density:.4});
    });
    this.frameDecor(a(.1),0,2.55,1.75);
    // 04 — the railed half spiral redirects momentum through the third dimension.
    // 05 — a four-paddle wheel, driven only by the passing ball.
    const wp=b(5.6).add(V(0,.98,0));
    this.wheel=this.hinge(wp,Math.PI,body=> {
      this.sphere(body,.18,V(),'brass',{density:.3});
      for(let i=0;i<4;i++) {
        const t=i*Math.PI/2,rot=Q().setFromAxisAngle(axisZ,t);
        this.box(body,[.14,.73,1.35],V(0,.365,0).applyQuaternion(rot),'copper',{density:.24,rotation:rot});
      }
    });
    this.frameDecor(b(5.6),Math.PI,2.65,.98,'wheel');
    // 06 — a joint-limited balancing bridge spans a real gap in the runway.
    const lp=b(1).add(V(0,.02,0));
    this.lever=this.hinge(lp,Math.PI,body=> {
      this.box(body,[2.7,.15,1.86],V(),'teal',{density:.55});
      this.box(body,[.5,.2,1.4],V(-.9,-.22,0),'brass',{density:1.2});
    },[-.40,.04]);
    this.lever.setRotation(Q().setFromAxisAngle(axisY,Math.PI).multiply(Q().setFromAxisAngle(axisZ,-.16)),true);
    this.frameDecor(lp,Math.PI,2.4,0,'lever');
    // 07 — an off-centre tray rests on its upper joint limit. Loading the far lip
    // shifts its centre of mass and tips it downward, releasing the same ball.
    const tp=b(-4).add(V(0,.06,0));
    this.bucket=this.hinge(tp,Math.PI,body=> {
      this.box(body,[3,.13,1.65],V(.20,0,0),'bucket',{density:.7});
      this.box(body,[.12,.38,1.65],V(1.64,.21,0),'bucket',{density:.6});
      this.box(body,[.6,.22,1.2],V(-.90,-.20,0),'brass',{density:3});
      for(const z of [-.84,.84]) this.box(body,[3,.28,.08],V(.20,.13,z),'brass',{density:.2});
    },[-.85,-.12]);
    this.bucket.setRotation(Q().setFromAxisAngle(axisY,Math.PI).multiply(Q().setFromAxisAngle(axisZ,-.12)),true);
    this.frameDecor(tp,Math.PI,2.4,0,'bucket');
    // 08 — the ball hits a suspended mallet; its forward arc reaches the bell.
    const hp=b(-8.0).add(V(0,1.8,0));
    this.hammer=this.hinge(hp,Math.PI,body=> {
      this.box(body,[.12,1.20,.12],V(0,-.63,0),'wood',{density:.3});
      this.hammerCollider=this.sphere(body,.31,V(0,-1.40,0),'copper',{density:3});
    });
    this.frameDecor(b(-8),Math.PI,2.7,1.8,'hammer');
    // 09 — the bell itself is a jointed rigid body with a convex impact surface.
    const bellP=b(-9.25).add(V(0,1.15,0));
    this.bell=this.hinge(bellP.clone().add(V(0,.75,0)),Math.PI,body=> {
      const points=[];
      for(const [radius,y] of [[.05,.62],[.17,.61],[.20,.51],[.27,.42],[.33,.19],[.43,-.10],[.58,-.32],[.68,-.38],[.69,-.45]]) {
        for(let i=0;i<32;i++){const t=i/32*Math.PI*2;points.push(radius*Math.cos(t),y,radius*Math.sin(t));}
      }
      const collider=RAPIER.ColliderDesc.convexHull(new Float32Array(points));
      collider.setTranslation(0,-.78,0).setDensity(3).setFriction(.3).setRestitution(.08).setActiveEvents(RAPIER.ActiveEvents.COLLISION_EVENTS);
      this.bellCollider=this.world.createCollider(collider,body);
      this.pieces.push({body,shape:'bell',size:[.7,1.2],offset:V(0,-.78,0),q:Q(),mat:'brass'});
    },[-.28,.28]);
    this.frameDecor(b(-9.25),Math.PI,3.3,2.65,'bell');
    this.fixedBox(b(-10.05).add(V(0,.40,0)),[.2,.9,1.95],'teal');
    this.markers=[a(-9),a(-5.5),a(.1),V(11.3,7.4,0),b(5.6),b(1),b(-4),b(-8),bellP];
  }
  release() {
    if(this.started) return;
    this.started=true;
    this.ball.setBodyType(RAPIER.RigidBodyType.Dynamic,true);
    this.ball.wakeUp();
  }
  mark(i) { if(!this.stages[i]) {this.stages[i]=true;this.stageTimes[i]=this.time;} }
  step() {
    if(!this.started) return;
    this.world.step(this.events);
    this.time+=this.world.timestep;
    this.events.drainCollisionEvents((a,b,started)=> {
      if(!started) return;
      const ca=this.world.getCollider(a),cb=this.world.getCollider(b);
      const ba=ca?.parent(),bb=cb?.parent();
      if(!ba||!bb) return;
      const hits=(x,y)=> (ba.handle===x.handle&&bb.handle===y.handle)||(ba.handle===y.handle&&bb.handle===x.handle);
      if(hits(this.ball,this.gate)) this.contacts.add('gate');
      if(hits(this.ball,this.wheel)) this.contacts.add('wheel');
      if(hits(this.ball,this.lever)) this.contacts.add('lever');
      if(hits(this.ball,this.bucket)) this.contacts.add('bucket');
      if(hits(this.ball,this.hammer)) this.contacts.add('hammer');
      if(hits(this.hammer,this.bell)) { this.mark(8);this.bellHits++; }
    });
    const p=this.ball.translation();
    if(p.x> -8.7) this.mark(0);
    if(this.dominoes.filter(b=>Math.abs(b.rotation().z)>.30).length>=6) this.mark(1);
    if(this.contacts.has('gate')&&Math.abs(this.gate.rotation().z)>.1) this.mark(2);
    if(p.z>2.7&&p.x>7.3) this.mark(3);
    if(this.contacts.has('wheel')&&this.wheel.angvel().z**2>.04) this.mark(4);
    if(this.contacts.has('lever')&&Math.abs(this.lever.angvel().z)>.04) this.mark(5);
    if(this.contacts.has('bucket')&&Math.abs(this.bucket.rotation().x)>.12) this.mark(6);
    if(this.contacts.has('hammer')&&Math.abs(this.hammer.angvel().z)>.1) this.mark(7);
  }
  report() { return {time:this.time,position:this.ball.translation(),velocity:this.ball.linvel(),stages:[...this.stages],stageTimes:[...this.stageTimes],bellHits:this.bellHits,contacts:[...this.contacts]}; }
  dispose() { this.events.free();this.world.free(); }
}
