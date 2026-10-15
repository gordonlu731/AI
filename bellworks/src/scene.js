import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export class WorkshopScene {
  constructor(canvas) {
    this.renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    this.renderer.shadowMap.enabled=true;
    this.renderer.shadowMap.type=THREE.PCFShadowMap;
    this.renderer.toneMapping=THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure=1.1;
    this.scene=new THREE.Scene();
    this.scene.background=new THREE.Color('#eeeae1');
    this.scene.fog=new THREE.Fog('#eeeae1',65,120);
    const pmrem=new THREE.PMREMGenerator(this.renderer),room=new RoomEnvironment();
    const env=pmrem.fromScene(room,.04);
    this.scene.environment=env.texture;
    this.env=env;room.dispose();pmrem.dispose();
    this.camera=new THREE.PerspectiveCamera(36,1,.1,160);
    this.controls=new OrbitControls(this.camera,canvas);
    this.controls.enableDamping=true;this.controls.dampingFactor=.065;
    this.controls.minDistance=8;this.controls.maxDistance=75;
    this.controls.maxPolarAngle=Math.PI*.48;
    this.controls.target.set(0,5,0);
    this.scene.add(new THREE.HemisphereLight('#fff7e1','#b5b9aa',1.7));
    const key=new THREE.DirectionalLight('#fff4dc',3.0);
    key.position.set(-10,25,8);key.castShadow=true;
    key.shadow.mapSize.set(1024,1024);
    key.shadow.camera.left=-23;key.shadow.camera.right=23;
    key.shadow.camera.top=23;key.shadow.camera.bottom=-23;
    key.shadow.camera.near=1;key.shadow.camera.far=65;
    key.shadow.normalBias=.035;key.shadow.bias=-.0001;
    key.shadow.radius=4;this.scene.add(key);
    const fill=new THREE.DirectionalLight('#d5e6e7',1.1);fill.position.set(15,12,-15);this.scene.add(fill);
    const ground=new THREE.Mesh(new THREE.PlaneGeometry(250,250),new THREE.MeshStandardMaterial({color:'#e7e4da',roughness:1}));
    ground.rotation.x=-Math.PI/2;ground.position.y=-1.12;ground.receiveShadow=true;this.scene.add(ground);
    this.mat={
      wood:new THREE.MeshStandardMaterial({color:'#bb8a54',roughness:.62,metalness:.05}),
      rail:new THREE.MeshStandardMaterial({color:'#b68f51',roughness:.28,metalness:.75}),
      brass:new THREE.MeshStandardMaterial({color:'#c69d51',roughness:.27,metalness:.78}),
      copper:new THREE.MeshStandardMaterial({color:'#c57e55',roughness:.3,metalness:.65}),
      ivory:new THREE.MeshStandardMaterial({color:'#f5e7c8',roughness:.45,metalness:.08}),
      teal:new THREE.MeshStandardMaterial({color:'#36786b',roughness:.38,metalness:.36}),
      bucket:new THREE.MeshStandardMaterial({color:'#c27b4b',roughness:.4,metalness:.45}),
      ball:new THREE.MeshStandardMaterial({color:'#e1ebdc',roughness:.12,metalness:1}),
      steel:new THREE.MeshStandardMaterial({color:'#717d78',roughness:.28,metalness:.9}),
      dark:new THREE.MeshStandardMaterial({color:'#20483c',roughness:.45,metalness:.25}),
      base:new THREE.MeshStandardMaterial({color:'#315447',roughness:.6,metalness:.12}),
      black:new THREE.MeshStandardMaterial({color:'#364039',roughness:.4,metalness:.4}),
    };
    this.content=new THREE.Group();this.scene.add(this.content);this.dynamic=[];
    this.labels=[];this.follow=false;
    this.home();this.resize();
    window.addEventListener('resize',()=>this.resize());
  }
  resize() {
    const w=innerWidth,h=innerHeight;
    this.renderer.setSize(w,h,false);this.camera.aspect=w/h;
    this.camera.clearViewOffset();
    if(w>760)this.camera.setViewOffset(w,h,w*.03,h*.025,w,h);
    this.camera.updateProjectionMatrix();
  }
  home() {
    this.follow=false;
    if(innerWidth<760){this.camera.position.set(42,35,55);this.controls.target.set(0,5.7,0);this.camera.fov=50;}
    else {this.camera.position.set(29.5,25.85,39.35);this.controls.target.set(0,5.2,0);this.camera.fov=36;}
    this.camera.updateProjectionMatrix();this.controls.update();
  }
  top() {this.follow=false;this.camera.position.set(.01,40,5);this.controls.target.set(0,4,0);this.controls.update();}
  mesh(geometry,mat,p,parent=this.content) {
    const mesh=new THREE.Mesh(geometry,this.mat[mat]||this.mat.brass);
    if(p)mesh.position.copy(p);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
  }
  box(size,p,mat='brass',parent=this.content,r=.035) {return this.mesh(new RoundedBoxGeometry(...size,2,r),mat,p,parent);}
  rod(a,b,r=.055,mat='brass',parent=this.content) {
    const d=b.clone().sub(a),m=this.mesh(new THREE.CylinderGeometry(r,r,d.length(),12),mat,a.clone().add(b).multiplyScalar(.5),parent);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());return m;
  }
  text(text,width=3,height=.5,color='#e0c596',bg='#28483b') {
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=128;
    const ctx=canvas.getContext('2d');if(bg){ctx.fillStyle=bg;ctx.fillRect(0,0,1024,128);}
    ctx.font='44px Georgia';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=color;ctx.fillText(text,512,68);
    const tex=new THREE.CanvasTexture(canvas);tex.colorSpace=THREE.SRGBColorSpace;
    return new THREE.Mesh(new THREE.PlaneGeometry(width,height),new THREE.MeshBasicMaterial({map:tex,transparent:!bg}));
  }
  setMachine(machine) {
    // Dispose only per-machine geometry and textures. Shared studio materials survive reset.
    this.content.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.userData.ownMaterial){o.material.map?.dispose();o.material.dispose();}});
    this.content.clear();this.dynamic=[];this.labels=[];
    this.machine=machine;
    for(const piece of machine.pieces) {
      if(piece.hidden)continue;
      let mesh;
      if(piece.shape==='bell') {
        const points=[[.05,.62],[.17,.61],[.20,.51],[.27,.42],[.33,.19],[.43,-.10],[.58,-.32],[.68,-.38],[.69,-.45],[.59,-.48],[.49,-.38],[.32,-.19],[.20,.18],[.12,.44]].map(p=>new THREE.Vector2(...p));
        mesh=this.mesh(new THREE.LatheGeometry(points,48),'brass',piece.offset);
        const rim=this.mesh(new THREE.TorusGeometry(.63,.055,10,48),'brass',new THREE.Vector3(0,-.44,0),mesh);rim.rotation.x=Math.PI/2;
      } else if(piece.shape==='sphere') {
        mesh=this.mesh(new THREE.SphereGeometry(piece.size[0],28,20),piece.mat,piece.offset);
      } else if(piece.mat==='base') {
        mesh=this.box([29,.80,16],piece.offset,'base',this.content,.28);
        const trim=this.box([28.9,.10,15.9],new THREE.Vector3(0,.32,0),'brass',mesh,.06);
        this.box([28.6,.13,15.6],new THREE.Vector3(0,.44,0),'wood',mesh,.08);
        for(const x of [-13.8,13.8])for(const z of [-7.3,7.3]) {
          this.mesh(new THREE.CylinderGeometry(.35,.48,.4,24),'dark',new THREE.Vector3(x,-.55,z),mesh);
          const screw=this.mesh(new THREE.CylinderGeometry(.12,.12,.035,16),'brass',new THREE.Vector3(x,.53,z),mesh);
          this.box([.13,.012,.018],new THREE.Vector3(0,.02,0),'dark',screw,.003);
        }
        const plaque=this.text('T H E   B E L L W O R K S     /     0 0 1',8,.52);plaque.position.set(0,0,8.012);plaque.userData.ownMaterial=true;mesh.add(plaque);
      } else {
        const radius=piece.mat==='rail'?.04:Math.min(.045,...piece.size.map(x=>x/4));
        mesh=piece.body.isFixed()?this.mesh(new THREE.BoxGeometry(...piece.size),piece.mat,piece.offset):this.box(piece.size,piece.offset,piece.mat,this.content,radius);
      }
      mesh.quaternion.copy(piece.q);
      const group=new THREE.Group();this.content.remove(mesh);group.add(mesh);this.content.add(group);
      group.position.copy(piece.body.translation());group.quaternion.copy(piece.body.rotation());
      if(piece.body.isDynamic())this.dynamic.push({group,body:piece.body});
      if(piece.body===machine.ball)this.ballMesh=group;
    }
    // Decorative structure is visible, passive, and positioned clear of all travel paths.
    for(const d of machine.decor) {
      if(d.kind==='support') {
        const {p}=d;
        for(const z of [-.78,.78]) {
          const side=new THREE.Vector3(0,0,z).applyAxisAngle(new THREE.Vector3(0,1,0),d.yaw);
          const top=p.clone().add(side).add(new THREE.Vector3(0,-.16,0)),bottom=top.clone().setY(-.12);
          this.rod(bottom,top,.072,'dark');
          this.box([.37,.13,.37],bottom.clone(),'brass');
          this.box([.22,.16,.22],top.clone().add(new THREE.Vector3(0,-.2,0)),'brass');
        }
        const side=new THREE.Vector3(0,0,.78).applyAxisAngle(new THREE.Vector3(0,1,0),d.yaw);
        const lo=p.clone().addScaledVector(side,-1).setY(Math.max(.1,p.y-3));
        const hi=p.clone().add(side).setY(p.y-.5);
        this.rod(lo,hi,.033,'brass');
      } else if(d.kind==='frame') {
        const g=new THREE.Group();g.position.copy(d.p);g.rotation.y=d.yaw;this.content.add(g);
        const z=d.width/2;
        if(d.height>0) {
          for(const sign of [-1,1]) {
            this.box([.20,d.height+.18,.20],new THREE.Vector3(0,d.height/2,sign*z),'dark',g);
            this.box([.5,.16,.48],new THREE.Vector3(0,.04,sign*z),'brass',g);
            this.mesh(new THREE.SphereGeometry(.14,16,12),'brass',new THREE.Vector3(0,d.height+.18,sign*z),g);
          }
          this.rod(new THREE.Vector3(0,d.height,-z-.08),new THREE.Vector3(0,d.height,z+.08),.09,'brass',g);
          if(d.style==='wheel')for(const sign of [-1,1]) {
            const ring=this.mesh(new THREE.TorusGeometry(.77,.042,8,48),'brass',new THREE.Vector3(0,d.height,sign*.77),g);
            ring.rotation.y=Math.PI/2;
          }
        } else {
          for(const sign of [-1,1]) {
            const geo=new THREE.CylinderGeometry(.40,.40,.15,3);geo.rotateZ(Math.PI/2);
            this.mesh(geo,'brass',new THREE.Vector3(0,-.23,sign*z),g);
            this.rod(new THREE.Vector3(0,0,-z),new THREE.Vector3(0,0,z),.08,'steel',g);
          }
        }
      } else if(d.kind==='launcher') {
        const g=new THREE.Group();g.position.copy(d.p);this.content.add(g);
        this.box([.3,1.2,2.5],new THREE.Vector3(-.25,.3,0),'dark',g);
        this.mesh(new THREE.CylinderGeometry(.3,.3,.25,24),'brass',new THREE.Vector3(-.25,1.02,0),g);
        this.box([1,.1,1.5],new THREE.Vector3(-.5,.05,0),'brass',g);
      } else if(d.kind==='curve') {
        // A radial architectural drum makes the descending 3D return leg legible.
        for(let i=0;i<11;i++) {
          const t=-Math.PI/2+i*Math.PI/10,r=2.05;
          const x=8+r*Math.cos(t),z=r*Math.sin(t),h=8.4-2*i/10-.3;
          this.rod(new THREE.Vector3(x,-.1,z),new THREE.Vector3(x,h,z),.05,'dark');
        }
        for(const h of [.25,4,6.2]) {
          const curve=new THREE.EllipseCurve(8,0,2.04,2.04,-Math.PI/2,Math.PI/2,false,0);
          const pts=curve.getPoints(60).map(p=>new THREE.Vector3(p.x,h,p.y));
          this.mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),60,.035,6,false),'brass');
        }
      }
    }
    // In-world stage tags, generated with the system font; no remote assets.
    machine.markers.forEach((p,i)=> {
      const c=document.createElement('canvas');c.width=128;c.height=128;const ctx=c.getContext('2d');
      ctx.fillStyle='#f5efdc';ctx.beginPath();ctx.arc(64,64,53,0,Math.PI*2);ctx.fill();
      ctx.strokeStyle='#bda472';ctx.lineWidth=3;ctx.stroke();ctx.font='43px Georgia';ctx.fillStyle='#355645';ctx.textAlign='center';ctx.fillText(String(i+1).padStart(2,'0'),64,80);
      const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;
      const material=new THREE.SpriteMaterial({map:texture,depthTest:true});
      const tag=new THREE.Sprite(material);tag.position.copy(p).add(new THREE.Vector3(0,1.05,i<3?-1.2:1.3));tag.scale.set(.62,.62,1);this.content.add(tag);
      tag.userData.ownMaterial=true;this.labels.push(tag);
    });
    // Small technical direction arrows on the wooden bed.
    for(const x of [-7,0,7]) {
      const label=this.text('→',.7,.5,'#d9b67c',null);label.position.set(x,-.155,6.7);label.rotation.x=-Math.PI/2;label.rotation.z=Math.PI;label.userData.ownMaterial=true;this.content.add(label);
    }
    const plate=this.box([2.6,.09,1.3],new THREE.Vector3(-10,-.08,-6),'dark');
    const inscription=this.text('01 / POTENTIAL',2.2,.4,'#e0c697',null);inscription.rotation.x=-Math.PI/2;inscription.position.set(-10,-.02,-6);inscription.userData.ownMaterial=true;this.content.add(inscription);
    this.batchStaticGeometry();
    this.sync();
  }
  batchStaticGeometry() {
    // Bake the stationary architecture into one draw per material. Moving bodies
    // keep individual transforms, so batching never changes the physics world.
    this.content.updateMatrixWorld(true);
    const moving=new Set(this.dynamic.map(d=>d.group));moving.add(this.ballMesh);
    const batches=new Map(),remove=[];
    this.content.traverse(o=> {
      if(!o.isMesh||o.userData.ownMaterial||!Object.values(this.mat).includes(o.material))return;
      for(let parent=o;parent;parent=parent.parent)if(moving.has(parent))return;
      let geometry=o.geometry.clone().applyMatrix4(o.matrixWorld);
      if(geometry.index){const old=geometry;geometry=geometry.toNonIndexed();old.dispose();}
      if(!batches.has(o.material))batches.set(o.material,[]);
      batches.get(o.material).push(geometry);remove.push(o);
    });
    for(const o of remove){for(const child of [...o.children])this.content.attach(child);o.parent.remove(o);o.geometry.dispose();}
    for(const [material,geometries] of batches){
      const merged=mergeGeometries(geometries,false);
      const mesh=new THREE.Mesh(merged,material);mesh.castShadow=true;mesh.receiveShadow=true;this.content.add(mesh);
      geometries.forEach(g=>g.dispose());
    }
  }
  sync() {
    for(const {group,body} of this.dynamic){group.position.copy(body.translation());group.quaternion.copy(body.rotation());}
    // Ball is initially fixed but becomes dynamic on release.
    if(this.ballMesh){this.ballMesh.position.copy(this.machine.ball.translation());this.ballMesh.quaternion.copy(this.machine.ball.rotation());}
  }
  render() {
    this.sync();
    if(this.follow&&this.machine.started) {
      const p=this.machine.ball.translation();
      const target=new THREE.Vector3(p.x,p.y,p.z);
      const delta=target.clone().sub(this.controls.target).multiplyScalar(.055);
      this.controls.target.add(delta);this.camera.position.add(delta);
    }
    this.controls.update();this.renderer.render(this.scene,this.camera);
  }
}
