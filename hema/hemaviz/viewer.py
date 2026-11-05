"""Self-contained three.js viewer for a simulated exchange.

Python hands over frames (joint positions in metres), events and phase
timings; the page draws jointed gray capsule figures, turns a hitbox red
from the moment it is hit, flashes binds, and keeps a beat-gridded
timeline under the scene in sync with the playhead.
"""
from __future__ import annotations

import json

from .kinematics import HITBOXES

THREE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"

EXTRA_SEGMENTS = [  # visual only, never hit-tested
    ("shoulders", "sh_l", "sh_r", 0.045),
    ("hips", "hp_l", "hp_r", 0.075),
    ("neck", "neck", "head", 0.045),
    ("foot L", "an_l", "toe_l", 0.04),
    ("foot R", "an_r", "toe_r", 0.04),
]


def render_html(result_json: dict, *, weapons: list, labels: list,
                beat_ms: float, height: int = 640, autoplay: bool = True,
                show_hitboxes: bool = False, b_origin: float = 2.4) -> str:
    data = {
        **result_json,
        "hitboxes": [list(h) for h in HITBOXES],
        "extras": [list(e) for e in EXTRA_SEGMENTS],
        "weapons": weapons,
        "labels": labels,
        "beat_ms": beat_ms,
        "autoplay": autoplay,
        "show_hitboxes": show_hitboxes,
        "height": height,
        "b_origin": b_origin,
    }
    payload = json.dumps(data, separators=(",", ":"))
    return _TEMPLATE.replace("__THREE_URL__", THREE_URL) \
                    .replace("__DATA__", payload) \
                    .replace("__H__", str(height))


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
:root{--bg:#16181c;--panel:#1f2228;--ink:#e8e8ea;--mute:#9aa0a8;--line:#30343b;
--a:#7aa7d8;--b:#d8a77a;--hit:#e5484d;--cover:#4c8bf5;--attack:#e5484d;--idle:#5b616b;--bind:#f5c542}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.35 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;overflow:hidden}
#wrap{position:relative;width:100%;height:__H__px;display:flex;flex-direction:column}
#stage{position:relative;flex:1;min-height:200px}
canvas#gl{display:block;width:100%;height:100%;cursor:grab}
.hud{position:absolute;left:10px;top:8px;pointer-events:none;font-variant-numeric:tabular-nums}
.hud .t{font-size:20px;font-weight:600}
.hud .ph{margin-top:2px;color:var(--mute)}
.hud .ph b.a{color:var(--a)} .hud .ph b.b{color:var(--b)}
.cams{position:absolute;right:8px;top:8px;display:flex;gap:4px}
button{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 9px;font:inherit;cursor:pointer}
button:hover{border-color:#4a505a} button.on{border-color:var(--a);color:#fff}
#log{position:absolute;right:8px;bottom:8px;max-width:46%;max-height:45%;overflow:auto;font-size:12px;
background:rgba(22,24,28,.78);border:1px solid var(--line);border-radius:8px;padding:6px 8px}
#log div{opacity:.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#log div.past{opacity:1}
#log .hit{color:#ff8a8d} #log .displace{color:#9fc1ff} #log .bind{color:var(--bind)}
#bar{display:flex;gap:6px;align-items:center;padding:6px 8px;background:var(--panel);border-top:1px solid var(--line);flex-wrap:wrap}
#scrub{flex:1;min-width:120px;accent-color:var(--a)}
select{background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:3px}
#tl{display:block;width:100%;height:78px;background:var(--panel);cursor:pointer}
.err{padding:20px;color:#ffb4b4}
</style></head><body>
<div id="wrap">
  <div id="stage">
    <canvas id="gl"></canvas>
    <div class="hud"><div class="t" id="tt">0 ms</div><div class="ph" id="ph"></div></div>
    <div class="cams">
      <button data-cam="side" class="on">Side</button><button data-cam="top">Top</button>
      <button data-cam="a">A's eyes</button><button data-cam="b">B's eyes</button>
      <button id="hbx">Hitboxes</button>
    </div>
    <div id="log"></div>
  </div>
  <div id="bar">
    <button id="play">Pause</button><button id="back">|&lt;</button>
    <button id="stepb">&lt;</button><button id="stepf">&gt;</button>
    <input id="scrub" type="range" min="0" value="0" step="1">
    <select id="spd"><option value="1">1x</option><option value="0.5">0.5x</option>
    <option value="0.25" selected>0.25x</option><option value="0.1">0.1x</option></select>
    <label style="color:var(--mute)"><input type="checkbox" id="loop" checked> loop</label>
  </div>
  <canvas id="tl"></canvas>
</div>
<script src="__THREE_URL__"></script>
<script>
const D = __DATA__;
(function(){
if (typeof THREE === 'undefined') {
  document.getElementById('stage').innerHTML = '<div class="err">Could not load three.js from the CDN. Check your internet connection.</div>';
  return;
}
const J = {}; D.joints.forEach((n,i)=>J[n]=i);
const F = D.frames, N = F.length;
const css = getComputedStyle(document.documentElement);
const C = k => css.getPropertyValue(k).trim();

// ---------- scene
const cv = document.getElementById('gl');
const renderer = new THREE.WebGLRenderer({canvas:cv, antialias:true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x16181c);
scene.fog = new THREE.Fog(0x16181c, 9, 18);
const cam = new THREE.PerspectiveCamera(40, 1, 0.05, 50);
scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2d33, 0.85));
const sun = new THREE.DirectionalLight(0xffffff, 0.75); sun.position.set(2,5,4); scene.add(sun);
const grid = new THREE.GridHelper(10, 20, 0x3a3f47, 0x262a30); grid.position.set(D.b_origin/2,0,0); scene.add(grid);
// centre line
const lineMat = new THREE.LineBasicMaterial({color:0x4a505a});
scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-2,0.002,0),new THREE.Vector3(4.5,0.002,0)]), lineMat));

const UP = new THREE.Vector3(0,1,0);
const cyl = new THREE.CylinderGeometry(1,1,1,14,1,true);
const sph = new THREE.SphereGeometry(1,16,12);
const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3(), tmpD = new THREE.Vector3();

function capsule(r, mat){
  const g = new THREE.Group();
  const c = new THREE.Mesh(cyl, mat), s1 = new THREE.Mesh(sph, mat), s2 = new THREE.Mesh(sph, mat);
  s1.scale.setScalar(r); s2.scale.setScalar(r);
  g.add(c, s1, s2); g.userData = {c, s1, s2, r}; scene.add(g); return g;
}
function place(g, a, b){
  const u = g.userData;
  tmpA.set(a[0],a[1],a[2]); tmpB.set(b[0],b[1],b[2]);
  u.s1.position.copy(tmpA); u.s2.position.copy(tmpB);
  tmpD.subVectors(tmpB,tmpA); const L = tmpD.length();
  u.c.visible = L > 1e-4;
  if (L > 1e-4){
    u.c.position.addVectors(tmpA,tmpB).multiplyScalar(0.5);
    u.c.quaternion.setFromUnitVectors(UP, tmpD.normalize());
    u.c.scale.set(u.r, L, u.r);
  }
}

const bodyCol = [0x9aa3ad, 0xb0a597];
const fig = [0,1].map(k=>{
  const parts = {};
  const base = new THREE.MeshStandardMaterial({color:bodyCol[k], roughness:.75, metalness:0});
  D.hitboxes.forEach(([name,a,b,r])=>{
    const m = base.clone(); m.transparent = true; m.opacity = 1;
    parts[name] = {g:capsule(r, m), a, b, m};
  });
  const extras = D.extras.map(([name,a,b,r])=>({g:capsule(r, base), a, b}));
  const W = D.weapons[k];
  const steel = new THREE.MeshStandardMaterial({color:0xd6dbe1, roughness:.25, metalness:.85});
  const dark = new THREE.MeshStandardMaterial({color:0x3b3127, roughness:.8});
  const bw = W.key === 'messer' ? 0.02 : 0.015;
  const blade = capsule(bw, steel), grip = capsule(0.016, dark), cross = capsule(0.011, steel);
  const nagel = W.nagel ? capsule(0.008, steel) : null;
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.17,0.012,8,40), new THREE.MeshBasicMaterial({color: k?0xd8a77a:0x7aa7d8}));
  ring.rotation.x = Math.PI/2; scene.add(ring);
  return {parts, extras, blade, grip, cross, nagel, steel, ring, W};
});

const spark = new THREE.Mesh(new THREE.SphereGeometry(0.035,16,12), new THREE.MeshBasicMaterial({color:0xf5c542}));
spark.visible = false; scene.add(spark);

function poseFrame(fi){
  const fr = F[fi];
  [0,1].forEach(k=>{
    const P = fr.p[k], f = fig[k];
    for (const name in f.parts){ const q = f.parts[name]; place(q.g, P[J[q.a]], P[J[q.b]]); }
    f.extras.forEach(q=>place(q.g, P[J[q.a]], P[J[q.b]]));
    const g = P[J.guard], tip = P[J.tip], pm = P[J.pommel];
    place(f.blade, g, tip); place(f.grip, pm, g);
    // crossguard perpendicular to the blade, roughly horizontal
    const d = new THREE.Vector3(tip[0]-g[0], tip[1]-g[1], tip[2]-g[2]).normalize();
    let ax = new THREE.Vector3().crossVectors(d, UP); if (ax.length()<0.2) ax.set(0,0,1); ax.normalize();
    const h = f.W.guard_half;
    place(f.cross, [g[0]-ax.x*h, g[1]-ax.y*h, g[2]-ax.z*h], [g[0]+ax.x*h, g[1]+ax.y*h, g[2]+ax.z*h]);
    if (f.nagel){ const n = new THREE.Vector3().crossVectors(d, ax).normalize().multiplyScalar(0.05);
      place(f.nagel, g, [g[0]+n.x, g[1]+n.y, g[2]+n.z]); }
    const pv = P[J.pelvis]; f.ring.position.set(pv[0], 0.004, pv[2]);
  });
  const t = fr.t*1000;
  // hits: red from the moment of impact
  [0,1].forEach(k=>{ for (const name in fig[k].parts){ fig[k].parts[name].m.color.setHex(bodyCol[k]); } });
  fig.forEach(f=>f.steel.color.setHex(0xd6dbe1));
  let sparkOn = false;
  D.events.forEach(e=>{
    const et = e.t*1000;
    if (e.kind === 'hit' && et <= t) fig[e.on].parts[e.part].m.color.setHex(0xe5484d);
    if ((e.kind === 'bind' || e.kind === 'displace') && t >= et && t - et < 220){
      sparkOn = true; spark.position.set(e.point[0], e.point[1], e.point[2]);
      if (e.kind === 'displace') fig[e.on].steel.color.setHex(0xf59e42);
    }
  });
  spark.visible = sparkOn;
  // HUD
  const beats = t / D.beat_ms;
  document.getElementById('tt').textContent = `${t.toFixed(0)} ms  ·  ${beats.toFixed(2)} beats`;
  document.getElementById('ph').innerHTML = `<b class="a">A</b> ${D.labels[0]}: ${fr.ph[0]}<br><b class="b">B</b> ${D.labels[1]}: ${fr.ph[1]}`;
  logDivs.forEach(([d,et])=>d.classList.toggle('past', et<=t));
  scrub.value = fi; drawTL(t);
}

// ---------- hitbox toggle (translucent bodies)
let showHB = D.show_hitboxes;
function applyHB(){ fig.forEach(f=>{ for (const n in f.parts){ f.parts[n].m.opacity = showHB ? 0.45 : 1; f.parts[n].m.depthWrite = !showHB; } });
  document.getElementById('hbx').classList.toggle('on', showHB); }
document.getElementById('hbx').onclick = ()=>{ showHB=!showHB; applyHB(); };
applyHB();

// ---------- event log
const log = document.getElementById('log');
const NM = ['A','B'];
const logDivs = D.events.map(e=>{
  const d = document.createElement('div'); d.className = e.kind;
  const ms = (e.t*1000).toFixed(0), bt = (e.t*1000/D.beat_ms).toFixed(2);
  if (e.kind==='hit') d.textContent = `${ms} ms (${bt}b)  ${NM[e.by]} hits ${NM[e.on]}: ${e.part}`;
  else if (e.kind==='displace') d.textContent = `${ms} ms (${bt}b)  ${NM[e.by]} displaces ${NM[e.on]} — ${e.note}`;
  else d.textContent = `${ms} ms (${bt}b)  bind — ${e.note}`;
  log.appendChild(d); return [d, e.t*1000];
});
if (!D.events.length){ log.innerHTML = '<div class="past" style="color:var(--mute)">no contact</div>'; }

// ---------- timeline
const tl = document.getElementById('tl'), tctx = tl.getContext('2d');
const T = D.duration*1000;
function drawTL(t){
  const dpr = window.devicePixelRatio||1, w = tl.clientWidth, h = tl.clientHeight;
  if (tl.width !== w*dpr){ tl.width = w*dpr; tl.height = h*dpr; }
  tctx.setTransform(dpr,0,0,dpr,0,0); tctx.clearRect(0,0,w,h);
  const L = 26, R = 8, X = ms => L + (w-L-R)*ms/T;
  tctx.font = '11px system-ui'; tctx.textBaseline = 'middle';
  // beat grid
  for (let b=0; b*D.beat_ms <= T; b++){
    const x = X(b*D.beat_ms); tctx.strokeStyle = '#30343b'; tctx.beginPath(); tctx.moveTo(x,4); tctx.lineTo(x,h-14); tctx.stroke();
    tctx.fillStyle = '#9aa0a8'; tctx.textAlign = 'center'; tctx.fillText(b+'', x, h-6);
  }
  const rows = [14, 40], colors = {attack:'#b8474b', cover:'#3f6fc4', both:'#8a5bc4', idle:'#4a4f58'};
  [0,1].forEach(k=>{
    tctx.fillStyle = k? '#d8a77a':'#7aa7d8'; tctx.textAlign='left'; tctx.fillText(NM[k], 6, rows[k]+9);
    D.phases[k].forEach(([name,a,b,action,kind])=>{
      const x0 = X(a*1000), x1 = X(b*1000);
      tctx.fillStyle = colors[kind]||colors.idle; tctx.fillRect(x0, rows[k], Math.max(1,x1-x0-1), 18);
      tctx.save(); tctx.beginPath(); tctx.rect(x0, rows[k], x1-x0-2, 18); tctx.clip();
      tctx.fillStyle = '#fff'; tctx.textAlign='left'; tctx.fillText(name, x0+4, rows[k]+9); tctx.restore();
    });
  });
  D.events.forEach(e=>{
    const x = X(e.t*1000), y = rows[e.kind==='hit'? e.on : 0];
    tctx.fillStyle = e.kind==='hit' ? '#ff5c61' : (e.kind==='displace' ? '#9fc1ff' : '#f5c542');
    tctx.beginPath(); tctx.moveTo(x, rows[0]-3); tctx.lineTo(x-4, rows[0]-9); tctx.lineTo(x+4, rows[0]-9); tctx.fill();
    if (e.kind==='hit'){ tctx.fillRect(x-1, rows[e.on], 2, 18); }
  });
  const px = X(t); tctx.strokeStyle = '#fff'; tctx.lineWidth = 1.5; tctx.beginPath(); tctx.moveTo(px,2); tctx.lineTo(px,h-14); tctx.stroke(); tctx.lineWidth = 1;
}
tl.addEventListener('click', ev=>{
  const r = tl.getBoundingClientRect(), L = 26, Rr = 8;
  const ms = (ev.clientX - r.left - L) / (r.width - L - Rr) * T;
  seek(Math.round(ms/1000/(F[1]?F[1].t-F[0].t:1)));
});

// ---------- camera (simple orbit)
let target = new THREE.Vector3(D.b_origin/2,1.15,0), rad = 4.6, th = Math.PI/2, phi = 1.32;
function camUpdate(){ cam.position.set(target.x + rad*Math.sin(phi)*Math.cos(th), target.y + rad*Math.cos(phi), target.z + rad*Math.sin(phi)*Math.sin(th)); cam.lookAt(target); }
const presets = {
  side:()=>{target.set(D.b_origin/2,1.15,0); rad=4.2+D.b_origin*0.2; th=Math.PI/2; phi=1.32;},
  top:()=>{target.set(D.b_origin/2,0.8,0); rad=5.2; th=Math.PI/2; phi=0.12;},
  a:()=>{target.set(2.2,1.25,0); rad=3.7; th=Math.PI+0.18; phi=1.27;},
  b:()=>{target.set(D.b_origin-2.2,1.25,0); rad=3.7; th=-0.18; phi=1.27;},
};
document.querySelectorAll('[data-cam]').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('[data-cam]').forEach(x=>x.classList.remove('on')); b.classList.add('on');
  presets[b.dataset.cam](); camUpdate(); render(); });
let drag = null;
cv.addEventListener('pointerdown', e=>{drag=[e.clientX,e.clientY]; cv.setPointerCapture(e.pointerId); cv.style.cursor='grabbing';});
cv.addEventListener('pointerup', e=>{drag=null; cv.style.cursor='grab';});
cv.addEventListener('pointermove', e=>{ if(!drag) return; th += (e.clientX-drag[0])*0.008; phi = Math.min(1.55, Math.max(0.08, phi-(e.clientY-drag[1])*0.008)); drag=[e.clientX,e.clientY]; camUpdate(); render(); });
cv.addEventListener('wheel', e=>{ e.preventDefault(); rad = Math.min(12, Math.max(1.2, rad*(1+Math.sign(e.deltaY)*0.08))); camUpdate(); render(); }, {passive:false});

// ---------- playback
const scrub = document.getElementById('scrub'); scrub.max = N-1;
const playBtn = document.getElementById('play'), spdSel = document.getElementById('spd');
let playing = D.autoplay, simT = 0, last = performance.now(), fi = 0, hold = 0;
function seek(i){ fi = Math.max(0, Math.min(N-1, i)); simT = F[fi].t; poseFrame(fi); render(); }
scrub.oninput = ()=>{ playing=false; playBtn.textContent='Play'; seek(+scrub.value); };
playBtn.onclick = ()=>{ playing=!playing; playBtn.textContent = playing?'Pause':'Play'; if (playing && fi>=N-1) seek(0); last=performance.now(); };
document.getElementById('back').onclick = ()=>seek(0);
document.getElementById('stepb').onclick = ()=>{playing=false; playBtn.textContent='Play'; seek(fi-1);};
document.getElementById('stepf').onclick = ()=>{playing=false; playBtn.textContent='Play'; seek(fi+1);};
playBtn.textContent = playing ? 'Pause' : 'Play';

function resize(){ const w = cv.clientWidth, h = cv.clientHeight; renderer.setSize(w, h, false); cam.aspect = w/h; cam.updateProjectionMatrix(); render(); drawTL(F[fi].t*1000); }
function render(){ renderer.render(scene, cam); }
window.addEventListener('resize', resize);

function tick(now){
  const dt = (now-last)/1000; last = now;
  if (playing){
    if (hold > 0){ hold -= dt; if (hold <= 0) seek(0); }
    else {
      simT += dt * (+spdSel.value);
      let i = fi; while (i < N-1 && F[i+1].t <= simT) i++;
      if (i !== fi){ fi = i; poseFrame(fi); render(); }
      if (fi >= N-1){
        if (document.getElementById('loop').checked) hold = 1.2;
        else { playing=false; playBtn.textContent='Play'; }
      }
    }
  }
  requestAnimationFrame(tick);
}
presets.side(); camUpdate(); poseFrame(0); resize();
requestAnimationFrame(tick);
window.__ready = true; window.__seek = seek;
})();
</script></body></html>"""
