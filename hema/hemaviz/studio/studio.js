/* HEMA Studio UI: pose the rigged figures, record keys on a beat timeline,
 * modulate actions by dragging their bars, and fight the result. */
(function () {
'use strict';
const H = window.HEMA, V = H.vec;
const $ = id => document.getElementById(id);
const clone = o => JSON.parse(JSON.stringify(o));
const uid = p => p + Math.random().toString(36).slice(2, 9);
const FRAME_H = 880;

// =================================================================== state
const S = {
  lib: null, libVersion: null, exId: null, fencer: 0, mode: 'edit',
  t: 0, playing: false, hold: 0,
  sel: { keys: [], action: null },
  work: [null, null],
  sim: null, flags: {}, needSim: true,
  guards: {}, measured: {}, timingLabels: {},
  undo: [], showHB: false, noModel: false,
};
const ex = () => S.lib.exchanges.find(e => e.id === S.exId) || S.lib.exchanges[0];
const weaponOf = f => H.WEAPONS[ex().fencers[f].weapon] || H.WEAPONS.longsword;
const origin = f => (f === 0 ? [0, 1] : [ex().distance, -1]);

// ======================================================== streamlit bridge
const inFrame = window.parent !== window;
function stSend(type, data) { if (inFrame) window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type }, data || {}), '*'); }
window.addEventListener('message', ev => {
  const d = ev.data;
  if (d && d.type === 'streamlit:render') onArgs(d.args || {});
});
stSend('streamlit:componentReady', { apiVersion: 1 });
stSend('streamlit:setFrameHeight', { height: FRAME_H });

function onArgs(a) {
  S.guards = a.guards || S.guards;
  S.measured = a.measured || {};
  S.timingLabels = a.timing_labels || S.timingLabels;
  if (S.lib === null || a.lib_version !== S.libVersion) {
    S.libVersion = a.lib_version;
    start(a.library);
  }
  fillMeasure();
  S.needSim = true;
}
setTimeout(() => {  // standalone (outside Streamlit): dev library or local copy
  if (S.lib) return;
  fetch('dev_library.json').then(r => r.json()).then(j => {
    S.guards = j.guards || {}; S.measured = j.measured || {}; S.timingLabels = j.timing_labels || {};
    start(j.library);
  }).catch(() => {
    let lib = null;
    try { lib = JSON.parse(localStorage.getItem('hema-studio-lib')); } catch (e) { /* none */ }
    start(lib || { version: 1, exchanges: [], moves: [] });
  });
}, 1200);

let saveTimer = null;
function scheduleSave() {
  $('saved').textContent = 'Saving…';
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { localStorage.setItem('hema-studio-lib', JSON.stringify(S.lib)); } catch (e) { /* private mode */ }
    stSend('streamlit:setComponentValue', { value: { library: S.lib, nonce: Date.now() }, dataType: 'json' });
    $('saved').textContent = inFrame ? 'Saved' : 'Saved locally';
  }, 700);
}

function start(lib) {
  S.lib = lib && lib.exchanges ? lib : { version: 1, exchanges: [], moves: [] };
  if (!S.lib.exchanges.length) S.lib.exchanges.push(newExchange('My first exchange'));
  if (!S.exId || !S.lib.exchanges.find(e => e.id === S.exId)) S.exId = S.lib.exchanges[0].id;
  S.sel = { keys: [], action: null }; S.work = [null, null]; S.t = 0; S.undo = [];
  buildFigures();
  refreshAll();
}

// ================================================================ mutations
function pushUndo() { S.undo.push(JSON.stringify(S.lib)); if (S.undo.length > 80) S.undo.shift(); }
function mutate(fn, undoable = true) {
  if (undoable) pushUndo();
  fn();
  changed();
}
function changed() { S.needSim = true; scheduleSave(); syncActionUI(); syncTopUI(); }
function undo() {
  if (!S.undo.length) return;
  S.lib = JSON.parse(S.undo.pop());
  if (!S.lib.exchanges.find(e => e.id === S.exId)) S.exId = S.lib.exchanges[0].id;
  S.sel = { keys: [], action: null };
  refreshAll(); scheduleSave();
}

function guardPose(weapon, name) {
  const g = (S.guards[weapon] || {});
  return clone(g[name] || Object.values(g)[0] || H.DEFAULT_POSE);
}
function newExchange(name) {
  return {
    id: uid('ex-'), name, notes: '', beat_ms: 360, distance: 2.6,
    fencers: [{ weapon: 'longsword', label: 'A' }, { weapon: 'messer', label: 'B' }],
    tracks: [{ keys: [{ id: uid('k'), at: 0, pose: guardPose('longsword', 'Vom Tag') }] },
             { keys: [{ id: uid('k'), at: 0, pose: guardPose('messer', 'Zornhut') }] }],
    actions: [],
  };
}

// ============================================================ simulation
function runSim() {
  S.needSim = false;
  const e = ex();
  S.sim = H.simulate(e, { guards: [guardPose(e.fencers[0].weapon), guardPose(e.fencers[1].weapon)] });
  S.flags = {};
  for (const a of e.actions) S.flags[a.id] = H.checkAction(e, a.fencer, a.id, S.measured);
  renderEvents();
  syncActionUI();
}
const layoutOf = f => (S.sim ? S.sim.layouts[f] : H.layout(ex(), f));

function displayPose(f, t) {
  if (S.mode === 'edit' && S.work[f]) return { pose: S.work[f], lift: [0, 0] };
  const ov = S.mode === 'fight' && S.sim ? S.sim.overrides[f] : null;
  return H.poseAt(ex(), layoutOf(f), t, ov, guardPose(ex().fencers[f].weapon));
}
function authoredPose(f, t) { return H.poseAt(ex(), layoutOf(f), t, null, guardPose(ex().fencers[f].weapon)).pose; }

// ================================================================== three
const cv = $('gl');
const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputEncoding = THREE.sRGBEncoding;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x15171b);
scene.fog = new THREE.Fog(0x15171b, 10, 20);
const cam = new THREE.PerspectiveCamera(40, 1, 0.05, 60);
scene.add(new THREE.HemisphereLight(0xffffff, 0x30343b, 0.9));
const sun = new THREE.DirectionalLight(0xffffff, 0.8); sun.position.set(2, 6, 4); scene.add(sun);
const grid = (() => {   // floor grid, 0.5 m squares, centre line along the fencing line
  const pts = [], cols = [], c1 = new THREE.Color(0x2a2e36), c2 = new THREE.Color(0x4a505a);
  for (let i = -12; i <= 12; i++) {
    const v = i * 0.5, c = i === 0 ? c2 : c1;
    pts.push(-6, 0, v, 6, 0, v, v, 0, -6, v, 0, 6); for (let k = 0; k < 4; k++) cols.push(c.r, c.g, c.b);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
  const l = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true })); scene.add(l); return l;
})();
const UP = new THREE.Vector3(0, 1, 0);
const v3 = a => new THREE.Vector3(a[0], a[1], a[2]);

// ---- capsules (hitboxes and the no-model fallback)
const cylG = new THREE.CylinderGeometry(1, 1, 1, 14, 1, true), sphG = new THREE.SphereGeometry(1, 14, 10);
function capsule(r, mat) {
  const g = new THREE.Group(), c = new THREE.Mesh(cylG, mat), a = new THREE.Mesh(sphG, mat), b = new THREE.Mesh(sphG, mat);
  a.scale.setScalar(r); b.scale.setScalar(r); g.add(c, a, b); g.userData = { c, a, b, r }; return g;
}
const tA = new THREE.Vector3(), tB = new THREE.Vector3(), tD = new THREE.Vector3();
function placeCapsule(g, p, q) {
  const u = g.userData; tA.set(...p); tB.set(...q);
  u.a.position.copy(tA); u.b.position.copy(tB); tD.subVectors(tB, tA);
  const L = tD.length(); u.c.visible = L > 1e-4;
  if (L > 1e-4) { u.c.position.addVectors(tA, tB).multiplyScalar(0.5); u.c.quaternion.setFromUnitVectors(UP, tD.normalize()); u.c.scale.set(u.r, L, u.r); }
}

// ---- swords
function makeSword(w) {
  const g = new THREE.Group();
  const steel = new THREE.MeshStandardMaterial({ color: 0xd5dae0, metalness: 0.85, roughness: 0.28, side: THREE.DoubleSide });
  const dark = new THREE.MeshStandardMaterial({ color: 0x3a3028, roughness: 0.85 });
  const W = w.width, L = w.blade, sh = new THREE.Shape();
  if (w.key === 'messer') {   // single edge, straight back, clipped point
    sh.moveTo(-W * 0.35, 0); sh.lineTo(W * 0.65, 0); sh.lineTo(W * 0.62, L * 0.72);
    sh.quadraticCurveTo(W * 0.5, L * 0.93, -W * 0.15, L); sh.lineTo(-W * 0.35, L * 0.86); sh.lineTo(-W * 0.35, 0);
  } else {
    sh.moveTo(-W / 2, 0); sh.lineTo(W / 2, 0); sh.lineTo(W * 0.28, L * 0.9); sh.lineTo(0, L); sh.lineTo(-W * 0.28, L * 0.9); sh.lineTo(-W / 2, 0);
  }
  const bg = new THREE.ExtrudeGeometry(sh, { depth: 0.005, bevelEnabled: false }); bg.translate(0, 0, -0.0025);
  const blade = new THREE.Mesh(bg, steel);
  const crossM = new THREE.Mesh(new THREE.BoxGeometry(w.guard_half * 2, 0.018, 0.02), steel);
  const gl = w.grip - 0.04;
  const grip = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.017, gl, 10), dark); grip.position.y = -gl / 2;
  const pommel = new THREE.Mesh(new THREE.SphereGeometry(0.027, 12, 10), steel); pommel.position.y = -w.grip + 0.01;
  g.add(blade, crossM, grip, pommel);
  if (w.nagel) { const n = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.012, 0.06), steel); n.position.set(0, 0.006, 0.035); g.add(n); }
  g.userData.steel = steel;
  scene.add(g);
  return g;
}
const mBasis = new THREE.Matrix4();
function placeSword(g, sk) {
  const d = V.norm(V.sub(sk.tip, sk.guard));
  let ax = V.cross(d, [0, 1, 0]); if (V.len(ax) < 0.2) ax = [0, 0, 1]; ax = V.norm(ax);
  const z = V.cross(ax, d);
  mBasis.makeBasis(v3(ax), v3(d), v3(z));
  g.quaternion.setFromRotationMatrix(mBasis); g.position.set(...sk.guard);
}

// ---- rigged figure
const AIM = [   // bone, target joint, child bone used as the aim axis
  ['torso_joint_2', 'chest', 'torso_joint_3'], ['torso_joint_3', 'neck', 'neck_joint_1'], ['neck_joint_1', 'neck2', 'neck_joint_2'],
  ['arm_joint_L_1', 'el_l', 'arm_joint_L_2', 'sh_l'], ['arm_joint_L_2', 'wr_l', 'arm_joint_L_3'], ['arm_joint_L_3', 'hand_l', null],
  ['arm_joint_R_1', 'el_r', 'arm_joint_R_2', 'sh_r'], ['arm_joint_R_2', 'wr_r', 'arm_joint_R_3'], ['arm_joint_R_3', 'hand_r', null],
  ['leg_joint_L_1', 'kn_l', 'leg_joint_L_2', 'hp_l'], ['leg_joint_L_2', 'an_l', 'leg_joint_L_3'], ['leg_joint_L_3', 'toe_l', 'leg_joint_L_5'],
  ['leg_joint_R_1', 'kn_r', 'leg_joint_R_2', 'hp_r'], ['leg_joint_R_2', 'an_r', 'leg_joint_R_3'], ['leg_joint_R_3', 'toe_r', 'leg_joint_R_5'],
];
const COLORS = [0x9fb0c4, 0xc4ad96];
const loader = THREE.GLTFLoader ? new THREE.GLTFLoader() : null;
let figures = [];

function buildFigures() {
  for (const f of figures) { scene.remove(f.root); scene.remove(f.sword); f.hb.forEach(h => scene.remove(h.g)); f.handles && Object.values(f.handles).forEach(h => scene.remove(h)); }
  figures = [0, 1].map(makeFigure);
}
function makeFigure(f) {
  const fig = { f, root: new THREE.Group(), bones: null, sword: makeSword(weaponOf(f)), weaponKey: weaponOf(f).key };
  scene.add(fig.root);
  const hbMat = new THREE.MeshStandardMaterial({ color: COLORS[f], transparent: true, opacity: 0.35, roughness: 0.8, depthWrite: false });
  fig.hb = H.HITBOXES.map(([name, a, b, r]) => {
    const m = hbMat.clone(); const g = capsule(r, m); g.visible = false; scene.add(g);
    return { name, a, b, g, m };
  });
  makeHandles(fig);
  if (loader && !S.noModel) {
    loader.load('models/RiggedFigure.glb', gltf => setupModel(fig, gltf), undefined, () => { S.noModel = true; showErr(''); });
  } else S.noModel = true;
  return fig;
}
function setupModel(fig, gltf) {
  const holder = fig.root;
  holder.add(gltf.scene);
  holder.scale.setScalar(H.DIMS.scale);
  const bones = {};
  gltf.scene.traverse(o => {
    if (o.isBone) bones[o.name] = o;
    if (o.isMesh) {
      o.material = new THREE.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, roughness: 0.65, metalness: 0.05, skinning: !!o.isSkinnedMesh });
      o.frustumCulled = false;
      if (o.isSkinnedMesh) setupPartColors(fig, o);
    }
  });
  for (const b of Object.values(bones)) b.userData.restQ = b.quaternion.clone();
  // the stock figure has a very large box head and long box hands
  bones.neck_joint_2.scale.setScalar(H.DIMS.headScale);
  bones.arm_joint_L_3.scale.setScalar(H.DIMS.handScale);
  bones.arm_joint_R_3.scale.setScalar(H.DIMS.handScale);
  for (const [name, , child] of AIM) {
    const b = bones[name];
    if (child) b.userData.aim = bones[child].position.clone().normalize();
    else b.userData.aim = b.position.clone().normalize().applyQuaternion(b.userData.restQ.clone().invert());
  }
  fig.bones = bones;
}

// Each vertex belongs to the body part of the bone that moves it most, so a
// hit paints that part of the mannequin red.
function partOfBone(n) {
  const side = n.includes('_L') ? 'L' : 'R';
  if (n === 'neck_joint_2') return 'head';
  if (n.startsWith('torso') || n === 'neck_joint_1') return 'torso';
  if (n.startsWith('arm')) return { 1: 'upper arm ', 2: 'forearm ', 3: 'hand ' }[n.slice(-1)] + side;
  if (n.startsWith('leg')) return (n.endsWith('_1') ? 'thigh ' : 'shin ') + side;
  return null;
}
function setupPartColors(fig, mesh) {
  const g = mesh.geometry, si = g.attributes.skinIndex, sw = g.attributes.skinWeight, n = g.attributes.position.count;
  const names = mesh.skeleton.bones.map(b => b.name);
  fig.vparts = new Array(n);
  for (let i = 0; i < n; i++) {
    const w = [sw.getX(i), sw.getY(i), sw.getZ(i), sw.getW(i)], j = [si.getX(i), si.getY(i), si.getZ(i), si.getW(i)];
    fig.vparts[i] = partOfBone(names[j[w.indexOf(Math.max(...w))]]);
  }
  g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  fig.mesh = mesh; fig.paintKey = null;
}
const HIT_RGB = new THREE.Color(0xe5484d).convertSRGBToLinear();
function paintFigure(fig, hitParts) {
  if (!fig.mesh) return;
  const key = [...hitParts].sort().join('|');
  if (key === fig.paintKey) return;
  fig.paintKey = key;
  const base = new THREE.Color(COLORS[fig.f]).convertSRGBToLinear(), col = fig.mesh.geometry.attributes.color;
  for (let i = 0; i < fig.vparts.length; i++) { const c = hitParts.has(fig.vparts[i]) ? HIT_RGB : base; col.setXYZ(i, c.r, c.g, c.b); }
  col.needsUpdate = true;
}

const qA = new THREE.Quaternion(), qB = new THREE.Quaternion(), qS = new THREE.Quaternion(), qY = new THREE.Quaternion();
const pW = new THREE.Vector3(), vCur = new THREE.Vector3(), vWant = new THREE.Vector3();
function setBoneWorldPos(b, p) { b.position.copy(b.parent.worldToLocal(v3(p))); b.updateMatrixWorld(true); }
function aimBone(b, target, extraYaw) {
  b.parent.getWorldQuaternion(qA);
  qB.copy(qA).multiply(b.userData.restQ);
  if (extraYaw) { qY.setFromAxisAngle(UP, extraYaw); qB.premultiply(qY); }
  vCur.copy(b.userData.aim).applyQuaternion(qB);
  b.getWorldPosition(pW);
  vWant.set(...target).sub(pW).normalize();
  qS.setFromUnitVectors(vCur.normalize(), vWant);
  qB.premultiply(qS);
  b.quaternion.copy(qA.invert().multiply(qB));
  b.updateMatrixWorld(true);
}
function poseFigure(fig, pose, sk) {
  const [o, facing] = origin(fig.f);
  fig.root.position.set(0, 0, 0);
  fig.root.rotation.set(0, facing === 1 ? Math.PI / 2 : -Math.PI / 2, 0);
  fig.root.updateMatrixWorld(true);
  const B = fig.bones;
  if (B) {
    const pel = B.torso_joint_1;
    pel.quaternion.setFromAxisAngle(UP, pose.yaw * 0.5 * Math.PI / 180).multiply(pel.userData.restQ);
    setBoneWorldPos(pel, sk.pelvis);
    for (const [name, joint, , rootJoint] of AIM) {
      const b = B[name];
      if (rootJoint) setBoneWorldPos(b, sk[rootJoint]);
      aimBone(b, sk[joint], name === 'torso_joint_2' ? pose.yaw * 0.5 * Math.PI / 180 : 0);
    }
  }
  placeSword(fig.sword, sk);
}

// ---- handles
const HANDLE_DEF = { grip: 0xf5c542, tip: 0xf08a3c, pelvis: 0x5cc8d6, lfoot: 0x58c47c, rfoot: 0x58c47c };
function makeHandles(fig) {
  fig.handles = {};
  for (const [k, c] of Object.entries(HANDLE_DEF)) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(k === 'tip' ? 0.04 : 0.05, 16, 12),
      new THREE.MeshBasicMaterial({ color: c, depthTest: false, transparent: true, opacity: 0.9 }));
    m.renderOrder = 10; m.userData = { handle: k, f: fig.f }; scene.add(m); fig.handles[k] = m;
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.3, 0.018, 8, 48), new THREE.MeshBasicMaterial({ color: fig.f ? 0xe4b07f : 0x7fb0e6, depthTest: false, transparent: true, opacity: 0.85 }));
  ring.rotation.x = Math.PI / 2; ring.renderOrder = 9; ring.userData = { handle: 'ring', f: fig.f }; scene.add(ring); fig.handles.ring = ring;
}

const spark = new THREE.Mesh(new THREE.SphereGeometry(0.04, 16, 12), new THREE.MeshBasicMaterial({ color: 0xf5c542 }));
spark.visible = false; scene.add(spark);

function updateScene() {
  if (!S.lib) return;
  const t = S.t, e = ex();
  for (const fig of figures) {
    if (fig.weaponKey !== weaponOf(fig.f).key) { scene.remove(fig.sword); fig.sword = makeSword(weaponOf(fig.f)); fig.weaponKey = weaponOf(fig.f).key; }
    const { pose, lift } = displayPose(fig.f, t);
    const [o, facing] = origin(fig.f);
    const sk = H.skeletonWorld(H.skeleton(pose, weaponOf(fig.f), lift), o, facing);
    fig.sk = sk;
    poseFigure(fig, pose, sk);
    fig.root.visible = !S.noModel;
    const hitParts = new Set(S.mode === 'fight' && S.sim ? S.sim.events.filter(ev => ev.kind === 'hit' && ev.on === fig.f && ev.t <= t).map(ev => ev.part) : []);
    paintFigure(fig, hitParts);
    for (const h of fig.hb) {
      placeCapsule(h.g, sk[h.a], sk[h.b]);
      const hit = hitParts.has(h.name);
      h.m.color.setHex(hit ? 0xe5484d : COLORS[fig.f]);
      h.m.opacity = S.noModel ? 1 : 0.3; h.m.transparent = !S.noModel; h.m.depthTest = S.noModel;
      h.g.visible = S.showHB || S.noModel;
      h.g.renderOrder = 5;
    }
    fig.sword.userData.steel.color.setHex(0xd5dae0);
    const show = S.mode === 'edit' && fig.f === S.fencer;
    const hp = { grip: sk.hand_r, tip: sk.tip, pelvis: sk.pelvis, lfoot: sk.an_l, rfoot: sk.an_r };
    for (const [k, m] of Object.entries(fig.handles)) {
      m.visible = show;
      if (k === 'ring') m.position.set(sk.pelvis[0], 0.012, sk.pelvis[2]);
      else m.position.set(...hp[k]);
    }
  }
  spark.visible = false;
  if (S.mode === 'fight' && S.sim) for (const ev of S.sim.events) {
    if ((ev.kind === 'bind' || ev.kind === 'displace') && t >= ev.t && t - ev.t < 250) {
      spark.visible = true; spark.position.set(...ev.point);
      if (ev.kind === 'displace') figures[ev.on].sword.userData.steel.color.setHex(0xf59e42);
    }
  }
  grid.position.set(e.distance / 2, 0, 0);
}

// ================================================================= camera
const cam0 = { target: new THREE.Vector3(1.3, 1.1, 0), rad: 5, th: Math.PI / 2, phi: 1.3 };
function camUpdate() {
  const c = cam0;
  cam.position.set(c.target.x + c.rad * Math.sin(c.phi) * Math.cos(c.th), c.target.y + c.rad * Math.cos(c.phi), c.target.z + c.rad * Math.sin(c.phi) * Math.sin(c.th));
  cam.lookAt(c.target);
}
function camPreset(k) {
  const d = S.lib ? ex().distance : 2.6, c = cam0;
  if (k === 'side') { c.target.set(d / 2, 1.1, 0); c.rad = 3.6 + d * 0.5; c.th = Math.PI / 2; c.phi = 1.32; }
  if (k === 'top') { c.target.set(d / 2, 0.8, 0); c.rad = 5.5; c.th = Math.PI / 2; c.phi = 0.12; }
  if (k === 'a' || k === 'b') {   // behind one fencer's shoulder, looking at the other
    const me = figures[k === 'a' ? 0 : 1], other = figures[k === 'a' ? 1 : 0];
    const pm = me && me.sk ? me.sk.pelvis : [k === 'a' ? 0 : d, 0.9, 0], po = other && other.sk ? other.sk.head : [k === 'a' ? d : 0, 1.6, 0];
    c.target.set(po[0], po[1] - 0.15, po[2]);
    const back = Math.abs(po[0] - pm[0]) + 2.3, rise = 0.75;
    c.rad = Math.hypot(back, rise); c.th = (k === 'a' ? Math.PI : 0) + (k === 'a' ? 0.3 : -0.3); c.phi = Math.atan2(back, rise);
  }
  document.querySelectorAll('[data-cam]').forEach(b => b.classList.toggle('on', b.dataset.cam === k));
  camUpdate();
}
document.querySelectorAll('[data-cam]').forEach(b => { b.onclick = () => camPreset(b.dataset.cam); });
$('hbx').onclick = () => { S.showHB = !S.showHB; $('hbx').classList.toggle('on', S.showHB); };

// ========================================================= 3D interaction
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
let drag = null;
function pick(ev) {
  const r = cv.getBoundingClientRect();
  ndc.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ndc, cam);
}
cv.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('pointerdown', ev => {
  if (!S.lib) return;
  cv.setPointerCapture(ev.pointerId); pick(ev);
  if (S.mode === 'edit' && ev.button === 0) {
    const hs = Object.values(figures[S.fencer].handles).filter(h => h.visible);
    const hit = ray.intersectObjects(hs)[0];
    if (hit) {
      const k = hit.object.userData.handle, f = S.fencer;
      if (S.playing) togglePlay(false);
      if (!S.work[f]) S.work[f] = clone(authoredPose(f, S.t));
      const p = hit.object.position.clone();
      let normal;
      if (k === 'grip' || k === 'tip') normal = cam.getWorldDirection(new THREE.Vector3()).negate();
      else normal = UP.clone();
      const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(normal, k === 'ring' ? new THREE.Vector3(p.x, 0.012, p.z) : p);
      const startHit = ray.ray.intersectPlane(plane, new THREE.Vector3());
      drag = { kind: 'handle', k, f, plane, start: startHit, pose0: clone(S.work[f]) };
      cv.style.cursor = 'grabbing';
      return;
    }
  }
  drag = { kind: ev.button === 2 || ev.shiftKey ? 'pan' : 'orbit', x: ev.clientX, y: ev.clientY };
  cv.style.cursor = 'grabbing';
});
cv.addEventListener('pointermove', ev => {
  if (!drag) return;
  if (drag.kind === 'orbit') {
    cam0.th += (ev.clientX - drag.x) * 0.008; cam0.phi = Math.min(1.56, Math.max(0.06, cam0.phi - (ev.clientY - drag.y) * 0.008));
    drag.x = ev.clientX; drag.y = ev.clientY; camUpdate(); return;
  }
  if (drag.kind === 'pan') {
    const right = new THREE.Vector3().setFromMatrixColumn(cam.matrix, 0), up = new THREE.Vector3().setFromMatrixColumn(cam.matrix, 1);
    const s = cam0.rad * 0.0015;
    cam0.target.addScaledVector(right, -(ev.clientX - drag.x) * s).addScaledVector(up, (ev.clientY - drag.y) * s);
    drag.x = ev.clientX; drag.y = ev.clientY; camUpdate(); return;
  }
  pick(ev);
  const w = ray.ray.intersectPlane(drag.plane, new THREE.Vector3());
  if (!w) return;
  const [o, facing] = origin(drag.f);
  const L = H.toLocal([w.x, w.y, w.z], o, facing), P = S.work[drag.f], W = weaponOf(drag.f);
  if (drag.k === 'grip') { P.grip = L; P.grip = H.skeleton(P, W).hand_r; }
  else if (drag.k === 'tip') { const g = H.skeleton(P, W).guard; P.blade = V.norm(V.sub(L, g)); }
  else if (drag.k === 'pelvis') { P.hip[0] = L[0]; P.hip[2] = L[2]; }
  else if (drag.k === 'lfoot') P.lfoot = [L[0], L[2]];
  else if (drag.k === 'rfoot') P.rfoot = [L[0], L[2]];
  else if (drag.k === 'ring') {
    const L0 = H.toLocal([drag.start.x, drag.start.y, drag.start.z], o, facing);
    const dx = L[0] - L0[0], dz = L[2] - L0[2], p0 = drag.pose0;
    P.hip = [p0.hip[0] + dx, p0.hip[1], p0.hip[2] + dz];
    P.grip = [p0.grip[0] + dx, p0.grip[1], p0.grip[2] + dz];
    P.lfoot = [p0.lfoot[0] + dx, p0.lfoot[1] + dz]; P.rfoot = [p0.rfoot[0] + dx, p0.rfoot[1] + dz];
  }
  syncPoseUI();
});
cv.addEventListener('pointerup', () => { drag = null; cv.style.cursor = 'grab'; });
cv.addEventListener('wheel', e => { e.preventDefault(); cam0.rad = Math.min(14, Math.max(1, cam0.rad * (1 + Math.sign(e.deltaY) * 0.08))); camUpdate(); }, { passive: false });

// ================================================================ pose UI
function curPose() { const f = S.fencer; return S.work[f] || authoredPose(f, S.t); }
function editPose(fn) { const f = S.fencer; if (!S.work[f]) S.work[f] = clone(authoredPose(f, S.t)); fn(S.work[f]); syncPoseUI(); }
function syncPoseUI() {
  if (!S.lib) return;
  const p = curPose();
  $('yaw').value = p.yaw; $('lean').value = p.lean;
  $('crouch').value = Math.max(0, H.maxPelvisY(p) - p.hip[1]);
  $('leftOn').checked = !!p.left_on;
  const dirty = !!S.work[S.fencer];
  $('rec').classList.toggle('dirty', dirty);
  const k = keyAtPlayhead(S.fencer);
  $('recInfo').textContent = (dirty ? 'Unrecorded changes. ' : '') +
    (k ? `Recording overwrites the key at ${(layoutOf(S.fencer).real[layoutOf(S.fencer).keys.indexOf(k)] / ex().beat_ms).toFixed(2)} beats.`
       : `Recording adds a key at ${(S.t / ex().beat_ms).toFixed(2)} beats.`);
  $('delKey').disabled = !(S.sel.keys.length || k);
}
$('yaw').oninput = e => editPose(p => { p.yaw = +e.target.value; });
$('lean').oninput = e => editPose(p => { p.lean = +e.target.value; });
$('crouch').oninput = e => editPose(p => { p.hip[1] = H.maxPelvisY(p) - +e.target.value; });
$('leftOn').onchange = e => editPose(p => { p.left_on = e.target.checked; });
function renderGuards() {
  const w = ex().fencers[S.fencer].weapon, box = $('guards'); box.innerHTML = '';
  for (const name of Object.keys(S.guards[w] || {})) {
    const b = document.createElement('button'); b.textContent = name;
    b.onclick = () => editPose(p => {
      const g = guardPose(w, name), dx = p.hip[0] - g.hip[0], dz = p.hip[2] - g.hip[2];
      Object.assign(p, g, { hip: [g.hip[0] + dx, g.hip[1], g.hip[2] + dz], grip: [g.grip[0] + dx, g.grip[1], g.grip[2] + dz],
        lfoot: [g.lfoot[0] + dx, g.lfoot[1] + dz], rfoot: [g.rfoot[0] + dx, g.rfoot[1] + dz] });
    });
    box.appendChild(b);
  }
  $('fWeapon').textContent = H.WEAPONS[w].name;
}
function setFencer(f) {
  S.fencer = f; $('fA').classList.toggle('on', f === 0); $('fB').classList.toggle('on', f === 1);
  renderGuards(); syncPoseUI();
}
$('fA').onclick = () => setFencer(0); $('fB').onclick = () => setFencer(1);

function keyAtPlayhead(f) {
  const L = layoutOf(f), tol = ex().beat_ms / 24;
  for (let i = 0; i < L.keys.length; i++) if (Math.abs(L.real[i] - S.t) <= tol) return L.keys[i];
  return null;
}
function record() {
  const f = S.fencer, pose = clone(curPose());
  mutate(() => {
    const e = ex(), k = keyAtPlayhead(f);
    if (k) { e.tracks[f].keys.find(x => x.id === k.id).pose = pose; S.sel = { keys: [k.id], action: null }; }
    else {
      const at = Math.max(0, H.realToBase(H.layout(e, f), S.t, e.beat_ms));
      const nk = { id: uid('k'), at: +at.toFixed(4), pose };
      e.tracks[f].keys.push(nk); e.tracks[f].keys.sort((a, b) => a.at - b.at);
      S.sel = { keys: [nk.id], action: null };
    }
  });
  S.work[f] = null; runSim(); syncPoseUI();
}
$('rec').onclick = record;
function deleteKeys() {
  const f = S.fencer, k = keyAtPlayhead(f);
  const ids = S.sel.keys.length ? S.sel.keys : (k ? [k.id] : []);
  if (!ids.length) return;
  mutate(() => {
    const e = ex();
    for (const tr of e.tracks) tr.keys = tr.keys.filter(x => !ids.includes(x.id));
    e.actions = e.actions.filter(a => !ids.includes(a.from) && !ids.includes(a.to));
  });
  S.sel = { keys: [], action: null }; S.work = [null, null]; syncPoseUI();
}
$('delKey').onclick = deleteKeys;

// ============================================================== actions
function keyFencer(id) { const e = ex(); return e.tracks[0].keys.some(k => k.id === id) ? 0 : e.tracks[1].keys.some(k => k.id === id) ? 1 : -1; }
function makeAction() {
  const ids = S.sel.keys; if (!ids.length) return;
  const f = keyFencer(ids[0]), L = H.layout(ex(), f);
  let i0, i1;
  if (ids.length === 1) { i1 = L.idx[ids[0]]; i0 = i1 - 1; }
  else { const ii = ids.map(id => L.idx[id]).sort((a, b) => a - b); i0 = ii[0]; i1 = ii[ii.length - 1]; }
  if (i0 < 0) { flash('Record a key before this one first: an action spans from one key to a later one.'); return; }
  if (L.acts.some(a => a.i0 < i1 && a.i1 > i0)) { flash('That span overlaps an existing action. Delete or shorten it first.'); return; }
  const a = { id: uid('a'), fencer: f, from: L.keys[i0].id, to: L.keys[i1].id, name: 'cut', strength: 0.5, pace: 1, attack: true, cover: false, cont: false, measure: null };
  mutate(() => { ex().actions.push(a); });
  S.sel = { keys: [], action: a.id }; syncActionUI();
  setTimeout(() => { $('aName').focus(); $('aName').select(); }, 0);
}
$('mkAct').onclick = makeAction;
function selAction() { return S.sel.action ? ex().actions.find(a => a.id === S.sel.action) : null; }
function syncActionUI() {
  if (!S.lib) return;
  const a = selAction();
  $('actBox').style.display = a ? '' : 'none';
  $('actNone').style.display = a ? 'none' : '';
  $('mkAct').disabled = !S.sel.keys.length;
  if (!a) return;
  if (document.activeElement !== $('aName')) $('aName').value = a.name;
  $('aStr').value = a.strength; $('aStrL').textContent = H.strengthLabel(a.strength);
  $('aPace').value = a.pace; $('aPaceL').textContent = `${H.paceLabel(a.pace)} ×${a.pace.toFixed(2)}`;
  $('aAtk').checked = !!a.attack; $('aCov').checked = !!a.cover; $('aCont').checked = !!a.cont;
  $('aMeas').value = a.measure || '';
  const fl = S.flags[a.id] || [];
  $('aFlags').innerHTML = fl.map(x => `<div class="flag ${x.level}">${x.text}</div>`).join('');
}
function fillMeasure() {
  const sel = $('aMeas'); const cur = sel.value; sel.innerHTML = '<option value="">(no check)</option>';
  for (const [k, lab] of Object.entries(S.timingLabels)) {
    const o = document.createElement('option'); o.value = k; o.textContent = lab + (S.measured[k] ? ' ✓' : ''); sel.appendChild(o);
  }
  sel.value = cur;
}
let editingAction = false;
function actEdit(fn, live) {
  const a = selAction(); if (!a) return;
  if (!editingAction) { pushUndo(); editingAction = true; }
  fn(a); S.needSim = true; scheduleSave(); syncActionUI();
  if (!live) editingAction = false;
}
$('aName').oninput = e => actEdit(a => { a.name = e.target.value; }, true);
$('aName').onchange = () => { editingAction = false; };
$('aStr').oninput = e => actEdit(a => { a.strength = +e.target.value; }, true);
$('aStr').onchange = () => { editingAction = false; };
$('aPace').oninput = e => actEdit(a => { a.pace = +e.target.value; }, true);
$('aPace').onchange = () => { editingAction = false; };
$('aAtk').onchange = e => actEdit(a => { a.attack = e.target.checked; });
$('aCov').onchange = e => actEdit(a => { a.cover = e.target.checked; });
$('aCont').onchange = e => actEdit(a => { a.cont = e.target.checked; });
$('aMeas').onchange = e => actEdit(a => { a.measure = e.target.value || null; });
$('aDel').onclick = () => { const a = selAction(); if (!a) return; mutate(() => { ex().actions = ex().actions.filter(x => x.id !== a.id); }); S.sel.action = null; syncActionUI(); };

// ================================================================ moves
function renderMoves() {
  const sel = $('mvSel'), cur = sel.value; sel.innerHTML = '';
  for (const m of S.lib.moves) { const o = document.createElement('option'); o.value = m.id; o.textContent = `${m.name} [${H.WEAPONS[m.weapon] ? H.WEAPONS[m.weapon].name : m.weapon}]`; sel.appendChild(o); }
  if (cur && S.lib.moves.some(m => m.id === cur)) sel.value = cur;
  moveInfo();
}
function moveInfo() {
  const m = S.lib.moves.find(x => x.id === $('mvSel').value);
  $('mvInfo').textContent = m ? (m.summary || '') + (m.weapon !== ex().fencers[S.fencer].weapon ? ` (recorded with a ${m.weapon}; the current fencer has a ${ex().fencers[S.fencer].weapon})` : '') : 'No saved moves yet.';
}
$('mvSel').onchange = moveInfo;
$('aSave').onclick = () => {
  const a = selAction(); if (!a) return;
  const e = ex(), f = a.fencer, L = H.layout(e, f);
  // include continuation actions that follow
  let last = L.acts.find(x => x.id === a.id), chain = [last];
  for (;;) { const nx = L.acts.find(x => x.cont && x.i0 === last.i1); if (!nx) break; chain.push(nx); last = nx; }
  const i0 = chain[0].i0, i1 = last.i1, keys = L.keys.slice(i0, i1 + 1);
  const name = prompt('Name this move', a.name); if (!name) return;
  const move = { id: uid('mv-'), name, weapon: e.fencers[f].weapon, summary: '', source: 'recorded in the Studio',
    keys: keys.map(k => ({ id: k.id, at: +(k.at - keys[0].at).toFixed(4), pose: clone(k.pose) })),
    actions: chain.map(c => { const o = clone(e.actions.find(x => x.id === c.id)); delete o.fencer; return o; }) };
  mutate(() => { S.lib.moves.push(move); }); renderMoves(); $('mvSel').value = move.id; moveInfo();
};
$('mvIns').onclick = () => {
  const m = S.lib.moves.find(x => x.id === $('mvSel').value); if (!m) return;
  const f = S.fencer, e = ex(), L = H.layout(e, f);
  const at0 = Math.max(0, H.realToBase(L, S.t, e.beat_ms));
  const span = m.keys[m.keys.length - 1].at;
  const here = authoredPose(f, S.t), dx = here.hip[0] - m.keys[0].pose.hip[0], dz = here.hip[2] - m.keys[0].pose.hip[2];
  const shift = p => Object.assign(clone(p), { hip: [p.hip[0] + dx, p.hip[1], p.hip[2] + dz], grip: [p.grip[0] + dx, p.grip[1], p.grip[2] + dz],
    lfoot: [p.lfoot[0] + dx, p.lfoot[1] + dz], rfoot: [p.rfoot[0] + dx, p.rfoot[1] + dz] });
  mutate(() => {
    const tr = e.tracks[f];
    for (const k of tr.keys) if (k.at > at0 + 1e-6) k.at = +(k.at + span).toFixed(4);
    const map = {};
    for (const k of m.keys) {
      const ex0 = tr.keys.find(x => Math.abs(x.at - (at0 + k.at)) < 1e-3);
      if (ex0 && k.at === 0) { map[k.id] = ex0.id; ex0.pose = shift(k.pose); continue; }
      const id = uid('k'); map[k.id] = id; tr.keys.push({ id, at: +(at0 + k.at).toFixed(4), pose: shift(k.pose) });
    }
    tr.keys.sort((a, b) => a.at - b.at);
    for (const a of m.actions) e.actions.push(Object.assign(clone(a), { id: uid('a'), fencer: f, from: map[a.from], to: map[a.to] }));
  });
  flash(`Inserted “${m.name}” for ${'AB'[f]}. Later keys moved back by ${span.toFixed(2)} beats.`);
};
$('mvDel').onclick = () => {
  const id = $('mvSel').value; if (!id || !confirm('Delete this move from the library?')) return;
  mutate(() => { S.lib.moves = S.lib.moves.filter(m => m.id !== id); }); renderMoves();
};

// ============================================================ top bar
function syncTopUI() {
  const sel = $('exSel'); sel.innerHTML = '';
  for (const e of S.lib.exchanges) { const o = document.createElement('option'); o.value = e.id; o.textContent = e.name; sel.appendChild(o); }
  sel.value = ex().id;
  for (const [id, f] of [['wA', 0], ['wB', 1]]) {
    const s = $(id); if (!s.options.length) for (const w of Object.values(H.WEAPONS)) { const o = document.createElement('option'); o.value = w.key; o.textContent = w.name; s.appendChild(o); }
    s.value = ex().fencers[f].weapon;
  }
  if (document.activeElement !== $('dist')) $('dist').value = ex().distance;
  if (document.activeElement !== $('beat')) $('beat').value = ex().beat_ms;
  $('undo').disabled = !S.undo.length;
  $('exNotes').textContent = ex().notes || '';
}
$('exSel').onchange = e => { S.exId = e.target.value; S.sel = { keys: [], action: null }; S.work = [null, null]; S.t = 0; refreshAll(); };
$('exNew').onclick = () => { const n = prompt('Name of the new exchange', 'New exchange'); if (!n) return; const e = newExchange(n); mutate(() => S.lib.exchanges.push(e)); S.exId = e.id; refreshAll(); };
$('exDup').onclick = () => { const e = clone(ex()); e.id = uid('ex-'); e.name += ' (copy)'; mutate(() => S.lib.exchanges.push(e)); S.exId = e.id; refreshAll(); };
$('exRen').onclick = () => { const n = prompt('Rename exchange', ex().name); if (n) mutate(() => { ex().name = n; }); };
$('exDel').onclick = () => {
  if (S.lib.exchanges.length < 2) { flash('Keep at least one exchange.'); return; }
  if (!confirm(`Delete “${ex().name}”?`)) return;
  const id = ex().id; mutate(() => { S.lib.exchanges = S.lib.exchanges.filter(e => e.id !== id); }); S.exId = S.lib.exchanges[0].id; refreshAll();
};
$('wA').onchange = e => mutate(() => { ex().fencers[0].weapon = e.target.value; renderGuards(); });
$('wB').onchange = e => mutate(() => { ex().fencers[1].weapon = e.target.value; renderGuards(); });
$('dist').onchange = e => mutate(() => { ex().distance = Math.min(6, Math.max(1, +e.target.value || 2.6)); });
$('beat').onchange = e => mutate(() => { ex().beat_ms = Math.min(2000, Math.max(100, +e.target.value || 360)); });
$('undo').onclick = undo;
function setMode(m) {
  S.mode = m; $('mEdit').classList.toggle('on', m === 'edit'); $('mFight').classList.toggle('on', m === 'fight');
  if (m === 'fight') S.work = [null, null];
  $('help').textContent = m === 'edit' ? 'Drag the coloured handles to pose · drag empty space to orbit · right-drag to pan · scroll to zoom'
    : 'Fight mode: strength, leverage and timing decide who is displaced and who gets hit';
  syncPoseUI();
}
$('mEdit').onclick = () => setMode('edit'); $('mFight').onclick = () => setMode('fight');

function refreshAll() {
  syncTopUI(); renderGuards(); renderMoves(); fillMeasure(); runSim(); syncPoseUI(); syncActionUI(); camPreset('side');
  buildFiguresIfWeaponChanged();
}
function buildFiguresIfWeaponChanged() { /* swords are swapped lazily in updateScene */ }

// ============================================================== events
function renderEvents() {
  const box = $('events'); box.innerHTML = '';
  const e = ex(), B = e.beat_ms, N = ['A', 'B'];
  const v = $('verdict');
  if (S.sim) v.innerHTML = `<b>${S.sim.verdict}</b><br><span class="muted">${S.sim.detail}</span>`;
  if (!S.sim || !S.sim.events.length) { box.innerHTML = '<div class="muted">No contact.</div>'; return; }
  for (const ev of S.sim.events) {
    const d = document.createElement('div'); d.className = ev.kind;
    const at = `${ev.t.toFixed(0)} ms · ${(ev.t / B).toFixed(2)} b`;
    d.textContent = ev.kind === 'hit' ? `${at}  ${N[ev.by]} hits ${N[ev.on]}: ${ev.part} (${ev.severity}, ${ev.action})`
      : ev.kind === 'displace' ? `${at}  ${N[ev.by]} displaces ${N[ev.on]}: ${ev.note}` : `${at}  bind: ${ev.note}`;
    d.title = d.textContent;
    d.onclick = () => { setMode('fight'); seek(ev.t); togglePlay(false); };
    box.appendChild(d);
  }
}
let flashTimer = null;
function flash(msg) { const r = $('recInfo'); r.textContent = msg; r.style.color = '#f5c542'; clearTimeout(flashTimer); flashTimer = setTimeout(() => { r.style.color = ''; syncPoseUI(); }, 3500); }
function showErr(msg) { if (!msg) return; const e = $('err'); e.style.display = 'flex'; e.textContent = msg; }

// ============================================================= timeline
const tl = $('tl'), tc = tl.getContext('2d');
const ROW = [{ top: 24 }, { top: 86 }], BAR_MAX = 40, LEFT = 30;
const rowOf = f => ROW[f];
function viewMs() {
  let end = 0; for (const f of [0, 1]) { const r = layoutOf(f).real; if (r.length) end = Math.max(end, r[r.length - 1]); }
  return Math.max(end + ex().beat_ms * 1.5, ex().beat_ms * 4);
}
const xOf = t => LEFT + (tl.clientWidth - LEFT - 10) * t / viewMs();
const tOf = x => (x - LEFT) / (tl.clientWidth - LEFT - 10) * viewMs();
const barBottom = f => rowOf(f).top + 44, keyY = f => rowOf(f).top + 52;
const barH = s => 5 + s * BAR_MAX * 0.95;
const KIND_COL = a => (a.attack && a.cover ? '#8a5bc4' : a.attack ? '#c2474c' : a.cover ? '#3f73cc' : '#4d535d');

function drawTimeline() {
  const dpr = window.devicePixelRatio || 1, w = tl.clientWidth, h = tl.clientHeight;
  if (tl.width !== Math.round(w * dpr) || tl.height !== Math.round(h * dpr)) { tl.width = Math.round(w * dpr); tl.height = Math.round(h * dpr); }
  tc.setTransform(dpr, 0, 0, dpr, 0, 0); tc.clearRect(0, 0, w, h);
  const e = ex(), B = e.beat_ms, T = viewMs();
  tc.font = '11px system-ui'; tc.textBaseline = 'middle';
  for (let q = 0; q * B / 4 <= T; q++) {
    const x = xOf(q * B / 4), major = q % 4 === 0;
    tc.strokeStyle = major ? '#3a404a' : '#262a31'; tc.beginPath(); tc.moveTo(x, major ? 4 : 12); tc.lineTo(x, h - 4); tc.stroke();
    if (major) { tc.fillStyle = '#9aa1ab'; tc.textAlign = 'center'; tc.fillText(`${q / 4}`, x, 8); }
  }
  for (const f of [0, 1]) {
    const L = layoutOf(f), r = rowOf(f);
    tc.fillStyle = f ? '#e4b07f' : '#7fb0e6'; tc.textAlign = 'left'; tc.font = '600 12px system-ui';
    tc.fillText('AB'[f], 8, r.top + 22); tc.font = '11px system-ui';
    if (f === S.fencer) { tc.fillStyle = 'rgba(127,176,230,.06)'; tc.fillRect(LEFT, r.top - 2, w - LEFT, 58); }
    for (const a of L.acts) {
      const x0 = xOf(a.t0), x1 = xOf(a.t1), bh = barH(a.strength == null ? 0.5 : a.strength), y0 = barBottom(f) - bh;
      tc.fillStyle = KIND_COL(a); tc.globalAlpha = 0.9; tc.fillRect(x0, y0, Math.max(2, x1 - x0 - 1), bh); tc.globalAlpha = 1;
      if (S.sel.action === a.id) { tc.strokeStyle = '#fff'; tc.lineWidth = 1.5; tc.strokeRect(x0 + 0.5, y0 + 0.5, x1 - x0 - 2, bh - 1); tc.lineWidth = 1; }
      tc.fillStyle = 'rgba(255,255,255,.55)'; tc.fillRect(x1 - 4, y0, 3, bh);       // pace grip
      tc.fillRect(x0, y0, Math.max(2, x1 - x0 - 1), 2);                             // strength grip
      tc.save(); tc.beginPath(); tc.rect(x0, r.top - 4, x1 - x0 - 5, 50); tc.clip();
      tc.fillStyle = '#fff'; tc.textAlign = 'left';
      const bad = (S.flags[a.id] || []).some(x => x.level === 'bad');
      tc.fillText(`${bad ? '⚠ ' : ''}${a.name}`, x0 + 4, Math.min(y0 - 7, barBottom(f) - 8) < r.top ? barBottom(f) - 8 : y0 - 7);
      tc.fillStyle = 'rgba(255,255,255,.75)';
      tc.fillText(`${H.strengthLabel(a.strength)} · ${H.paceLabel(a.pace)}`, x0 + 4, barBottom(f) - 7 > y0 + 6 ? barBottom(f) - 7 : y0 + 6);
      tc.restore();
    }
    tc.strokeStyle = '#3a404a'; tc.beginPath(); tc.moveTo(LEFT, keyY(f)); tc.lineTo(w - 10, keyY(f)); tc.stroke();
    L.keys.forEach((k, i) => {
      const x = xOf(L.real[i]), y = keyY(f), sel = S.sel.keys.includes(k.id);
      tc.fillStyle = sel ? '#ffffff' : (f ? '#e4b07f' : '#7fb0e6');
      tc.beginPath(); tc.moveTo(x, y - 6); tc.lineTo(x + 6, y); tc.lineTo(x, y + 6); tc.lineTo(x - 6, y); tc.closePath(); tc.fill();
    });
  }
  if (S.sim) for (const ev of S.sim.events) {
    const x = xOf(ev.t), y = ev.kind === 'hit' ? rowOf(ev.on).top - 3 : 14;
    tc.fillStyle = ev.kind === 'hit' ? '#ff5c61' : ev.kind === 'displace' ? '#9fc1ff' : '#f5c542';
    tc.beginPath(); tc.moveTo(x, y + 6); tc.lineTo(x - 5, y - 2); tc.lineTo(x + 5, y - 2); tc.fill();
  }
  const px = xOf(S.t); tc.strokeStyle = '#fff'; tc.lineWidth = 1.5; tc.beginPath(); tc.moveTo(px, 2); tc.lineTo(px, h - 2); tc.stroke(); tc.lineWidth = 1;
}

let tdrag = null;
function tlHit(x, y) {
  for (const f of [0, 1]) {
    const L = layoutOf(f);
    for (let i = 0; i < L.keys.length; i++) if (Math.abs(x - xOf(L.real[i])) < 7 && Math.abs(y - keyY(f)) < 8) return { type: 'key', f, i, key: L.keys[i] };
    for (const a of L.acts) {
      const x0 = xOf(a.t0), x1 = xOf(a.t1), y0 = barBottom(f) - barH(a.strength == null ? 0.5 : a.strength);
      if (x >= x1 - 7 && x <= x1 + 4 && y >= y0 - 4 && y <= barBottom(f)) return { type: 'pace', f, a };
      if (x >= x0 && x <= x1 && Math.abs(y - y0) < 5) return { type: 'strength', f, a };
      if (x >= x0 && x <= x1 && y >= y0 && y <= barBottom(f)) return { type: 'bar', f, a };
    }
  }
  const f = y < (ROW[1].top - 4) ? 0 : 1;
  return { type: 'empty', f };
}
const snapT = t => (!$('snap').checked ? t : Math.round(t / (ex().beat_ms / 8)) * (ex().beat_ms / 8));
tl.addEventListener('pointerdown', ev => {
  if (!S.lib) return;
  const r = tl.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top, h = tlHit(x, y);
  tl.setPointerCapture(ev.pointerId);
  if (S.playing) togglePlay(false);
  if (h.f !== S.fencer && h.type !== 'empty') setFencer(h.f);
  if (h.type === 'key') {
    if (ev.shiftKey) { if (!S.sel.keys.includes(h.key.id)) S.sel.keys.push(h.key.id); }
    else S.sel = { keys: [h.key.id], action: null };
    seek(layoutOf(h.f).real[h.i]);
    tdrag = { ...h, x0: x, moved: false };
  } else if (h.type === 'pace' || h.type === 'strength' || h.type === 'bar') {
    S.sel = { keys: [], action: h.a.id };
    if (h.type === 'bar') seek(Math.max(h.a.t0, Math.min(tOf(x), h.a.t1)));
    tdrag = { ...h, x0: x, moved: false };
  } else {
    if (h.f !== S.fencer) setFencer(h.f);
    S.sel = { keys: [], action: null }; seek(Math.max(0, snapT(tOf(x))));
    tdrag = { type: 'scrub' };
  }
  syncActionUI(); syncPoseUI();
});
tl.addEventListener('pointermove', ev => {
  const r = tl.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
  if (!tdrag) {
    const h = S.lib ? tlHit(x, y) : { type: 'empty' };
    tl.style.cursor = h.type === 'pace' ? 'ew-resize' : h.type === 'strength' ? 'ns-resize' : h.type === 'key' ? 'grab' : 'pointer';
    return;
  }
  if (tdrag.type === 'scrub') { seek(Math.max(0, snapT(tOf(x)))); return; }
  if (!tdrag.moved && Math.abs(x - tdrag.x0) < 3 && tdrag.type !== 'strength') return;
  if (!tdrag.moved) { pushUndo(); tdrag.moved = true; }
  const e = ex(), B = e.beat_ms;
  if (tdrag.type === 'key') {
    const L = H.layout(e, tdrag.f), i = L.idx[tdrag.key.id], keys = L.keys;
    const t = snapT(Math.max(0, tOf(x)));
    let at;
    if (i === 0) at = Math.min(t / B, keys.length > 1 ? keys[1].at - 0.02 : 1e9);
    else {
      const pace = L.segAct[i] ? (L.segAct[i].pace || 1) : 1;
      at = keys[i - 1].at + (t - L.real[i - 1]) / B / pace;
      at = Math.max(keys[i - 1].at + 0.02, Math.min(at, i + 1 < keys.length ? keys[i + 1].at - 0.02 : 1e9));
    }
    e.tracks[tdrag.f].keys.find(k => k.id === tdrag.key.id).at = +Math.max(0, at).toFixed(4);
    S.needSim = true; seek(H.layout(e, tdrag.f).real[i]);
  } else if (tdrag.type === 'pace') {
    const L = H.layout(e, tdrag.f), a = L.acts.find(z => z.id === tdrag.a.id);
    const base = (L.keys[a.i1].at - L.keys[a.i0].at) * B;
    const want = Math.max(40, snapT(tOf(x)) - a.t0);
    e.actions.find(z => z.id === a.id).pace = +Math.min(2.5, Math.max(0.4, want / base)).toFixed(3);
    S.needSim = true;
  } else if (tdrag.type === 'strength') {
    const s = (barBottom(tdrag.f) - y - 5) / (BAR_MAX * 0.95);
    e.actions.find(z => z.id === tdrag.a.id).strength = +Math.min(1, Math.max(0, s)).toFixed(2);
    S.needSim = true;
  }
  syncActionUI();
});
tl.addEventListener('pointerup', () => { if (tdrag && tdrag.moved) { scheduleSave(); runSim(); } tdrag = null; });

// ============================================================ transport
function seek(t) {
  if (Math.abs(t - S.t) > 0.5 && S.work.some(Boolean) && S.mode === 'edit') { S.work = [null, null]; flash('Unrecorded pose discarded. Press Record before moving the playhead to keep it.'); }
  S.t = Math.max(0, t); syncPoseUI();
}
function endT() { return S.sim ? S.sim.end : viewMs(); }
function togglePlay(on) {
  S.playing = on == null ? !S.playing : on;
  if (S.playing) { S.work = [null, null]; if (S.t >= endT() - 1) S.t = 0; }
  $('play').textContent = S.playing ? 'Pause' : 'Play';
}
$('play').onclick = () => togglePlay();
$('back').onclick = () => seek(0);
$('stepB').onclick = () => seek(snapT(S.t - ex().beat_ms / 8));
$('stepF').onclick = () => seek(snapT(S.t + ex().beat_ms / 8));
window.addEventListener('keydown', ev => {
  if (!S.lib || ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName) && document.activeElement.type !== 'range' && document.activeElement.type !== 'checkbox') return;
  if (ev.key === ' ') { ev.preventDefault(); togglePlay(); }
  else if (ev.key === 'r' || ev.key === 'R') record();
  else if (ev.key === 'Delete' || ev.key === 'Backspace') { if (S.sel.action) $('aDel').click(); else deleteKeys(); }
  else if (ev.key === 'ArrowLeft') seek(snapT(S.t - ex().beat_ms / 8));
  else if (ev.key === 'ArrowRight') seek(snapT(S.t + ex().beat_ms / 8));
  else if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'z') { ev.preventDefault(); undo(); }
});

// ============================================================ main loop
function resize() {
  const st = $('stage'), w = st.clientWidth, h = st.clientHeight;
  renderer.setSize(w, h, false); cam.aspect = w / Math.max(h, 1); cam.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
let last = performance.now();
function frame(now) {
  const dt = (now - last); last = now;
  if (S.lib) {
    if (S.needSim) runSim();
    if (S.playing) {
      if (S.hold > 0) { S.hold -= dt; if (S.hold <= 0) S.t = 0; }
      else {
        S.t += dt * +$('spd').value;
        if (S.t >= endT()) { S.t = endT(); if ($('loop').checked) S.hold = 900; else togglePlay(false); }
      }
    }
    updateScene();
    drawTimeline();
    const e = ex(), N = ['A', 'B'];
    $('tt').textContent = `${S.t.toFixed(0)} ms · ${(S.t / e.beat_ms).toFixed(2)} beats`;
    $('sub').innerHTML = [0, 1].map(f => {
      const a = H.actionAt(layoutOf(f), S.t);
      return `<span class="${f ? 'fb' : 'fa'}">${N[f]}</span> ${a ? `${a.name} (${H.strengthLabel(a.strength)}, ${H.paceLabel(a.pace)})` : '—'}`;
    }).join('<br>');
  }
  renderer.render(scene, cam);
  requestAnimationFrame(frame);
}
resize(); camUpdate();
requestAnimationFrame(frame);
window.__studio = { S, seek, setMode, record, togglePlay, figures: () => figures, cam };
})();
