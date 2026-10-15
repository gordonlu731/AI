import './style.css';
import {initPhysics,Machine,STAGES} from './machine.js';
import {WorkshopScene} from './scene.js';

const $=id=>document.getElementById(id);
let machine,view,running=false,speed=1,accumulator=0,previous=0,completed=false,sound=true,audio,master;
let lastCount=-1,toastDeadline=0;
const rows=STAGES.map(([name,description,type],i)=> {
  const li=document.createElement('li');
  li.title=description;
  li.innerHTML=`<span class="stage-number">${String(i+1).padStart(2,'0')}</span><span class="stage-name">${name}<span class="stage-type">${type}</span></span><span class="stage-time"></span>`;
  $('stages').appendChild(li);return li;
});
function toast(message){$('toast').textContent=message;$('toast').classList.add('visible');toastDeadline=performance.now()+4200;}
function soundBell() {
  if(!sound||!audio)return;
  const now=audio.currentTime;
  for(const [frequency,gain,decay] of [[523.25,.22,3.6],[1048,.10,2.5],[1409,.06,1.8],[2078,.035,1.1],[2819,.016,.65]]) {
    const osc=audio.createOscillator(),amp=audio.createGain();osc.type='sine';osc.frequency.value=frequency;
    amp.gain.setValueAtTime(0,now);amp.gain.linearRampToValueAtTime(gain,now+.006);amp.gain.exponentialRampToValueAtTime(.0001,now+decay);
    osc.connect(amp).connect(master);osc.start(now);osc.stop(now+decay+.1);
  }
}
function updateUI() {
  const count=machine.stages.filter(Boolean).length;
  if(count!==lastCount) {
    const firstUnfinished=machine.stages.findIndex(v=>!v);
    rows.forEach((li,i)=> {
      li.classList.toggle('done',machine.stages[i]);
      li.classList.toggle('current',running&&i===firstUnfinished);
      li.querySelector('.stage-number').textContent=machine.stages[i]?'✓':String(i+1).padStart(2,'0');
      li.querySelector('.stage-time').textContent=machine.stages[i]?`${machine.stageTimes[i].toFixed(1)}s`:'';
    });
    $('progress-number').textContent=`${String(count).padStart(2,'0')} / 09`;
    $('progress-fill').style.width=`${count/9*100}%`;
    lastCount=count;
  }
  const t=machine.stageTimes[8]??machine.time;
  $('elapsed').textContent=`${String(Math.floor(t/60)).padStart(2,'0')}:${(t%60).toFixed(1).padStart(4,'0')}`;
  if(machine.stages[8]&&!completed) {
    completed=true;soundBell();toast('Nine moments. One perfect little finale.');
    $('state-label').textContent='A chain reaction, beautifully complete.';
    $('start').innerHTML='<span>✓</span> Bell rung';
  }
}
function setRunning(value) {
  running=value;document.body.classList.toggle('running',value);
  $('pause').innerHTML=value?'<span>Ⅱ</span> Pause':'<span>▶</span> Resume';
  if(!completed)$('state-label').textContent=value?'A little motion goes a long way.':'A moment of suspended possibility.';
  rows.forEach(li=>li.classList.remove('current'));lastCount=-1;accumulator=0;
}
$('start').addEventListener('click',()=> {
  if(machine.started)return;
  try{audio??=new AudioContext();if(!master){master=audio.createGain();master.gain.value=sound?1:0;master.connect(audio.destination);}audio.resume();}catch{/* Audio is optional. */}
  machine.release();setRunning(true);$('start').disabled=true;$('start').innerHTML='<span>●</span> In motion';$('pause').disabled=false;
});
$('pause').addEventListener('click',()=> {if(machine.started)setRunning(!running);});
$('reset').addEventListener('click',()=> {
  running=false;accumulator=0;completed=false;lastCount=-1;document.body.classList.remove('running');
  const old=machine;machine=new Machine();view.setMachine(machine);old.dispose();
  $('start').disabled=false;$('start').innerHTML='<span>▶</span> Release the ball';
  $('pause').disabled=true;$('pause').innerHTML='<span>Ⅱ</span> Pause';
  $('state-label').textContent='Wound up. Ready to wonder.';
  view.follow=false;$('follow').setAttribute('aria-pressed','false');
  $('toast').classList.remove('visible');updateUI();
});
document.querySelectorAll('[data-speed]').forEach(button=>button.addEventListener('click',()=> {
  speed=Number(button.dataset.speed);document.querySelectorAll('[data-speed]').forEach(b=>b.classList.toggle('active',b===button));
}));
$('sound').addEventListener('click',()=> {sound=!sound;if(master)master.gain.value=sound?1:0;$('sound').setAttribute('aria-pressed',String(sound));$('sound').title=sound?'Mute bell sound':'Enable bell sound';});
$('view-home').addEventListener('click',()=> {view.home();$('follow').setAttribute('aria-pressed','false');});
$('view-top').addEventListener('click',()=> {view.top();$('follow').setAttribute('aria-pressed','false');});
$('follow').addEventListener('click',()=> {view.follow=!view.follow;$('follow').setAttribute('aria-pressed',String(view.follow));if(view.follow)toast('Following the ball. Drag to change your angle.');});
window.addEventListener('keydown',e=> {
  if(e.code==='Space'&&!/BUTTON|INPUT|SELECT|TEXTAREA/.test(e.target.tagName)){e.preventDefault();if(!machine.started)$('start').click();else $('pause').click();}
});
document.addEventListener('visibilitychange',()=> {previous=performance.now();accumulator=0;});
$('world').addEventListener('webglcontextlost',e=> {e.preventDefault();running=false;toast('Graphics context lost. Reload this page to rebuild the workshop.');});
function tick(now) {
  const delta=Math.min((now-previous)/1000,.1);previous=now;
  if(running) {
    accumulator+=delta*speed;
    while(accumulator>=1/120){machine.step();accumulator-=1/120;}
  }
  updateUI();view.render();
  if(now>toastDeadline)$('toast').classList.remove('visible');
  requestAnimationFrame(tick);
}
try {
  await initPhysics();machine=new Machine();view=new WorkshopScene($('world'));view.setMachine(machine);
  updateUI();$('loading').classList.add('hidden');previous=performance.now();requestAnimationFrame(tick);
  // Read-only diagnostics for inspection. Acceleration is exposed only in explicit test mode;
  // it executes the identical fixed-step solver and never assigns a stage or body position.
  window.__bellworks={report:()=>machine.report(),get running(){return running;},get speed(){return speed;},get camera(){return view.camera.position.toArray();},get renderInfo(){return {...view.renderer.info.render};}};
  if(new URLSearchParams(location.search).has('test')) {
    window.__bellworks.advance=(seconds)=> {
      if(!running)return machine.report();
      for(let i=0;i<Math.round(seconds*120);i++)machine.step();
      updateUI();view.render();return machine.report();
    };
  }
}catch(error){
  console.error(error);$('loading').querySelector('p').textContent=`Could not assemble the workshop: ${error.message}. Use Chrome with WebGL enabled.`;
}
