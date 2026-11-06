/* HEMA Studio engine: poses, IK, timeline layout, exchange simulation.
 *
 * Pure math, no three.js -- runs in the browser (window.HEMA) and in Node
 * (require) so the tests can check outcomes.
 *
 * Fencer-local frame: x = toward the opponent, y = up, z = fencer's right.
 * Metres, degrees, milliseconds.
 *
 * Body dimensions are read off the Quaternius base characters' skeletons
 * (CC0), so the IK limbs are exactly the mesh's bones: nothing can stretch.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.HEMA = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Bone lengths of the Quaternius "Universal Base Characters" (metres).
  // hipUp: hip joints relative to the pelvis bone; sh*: shoulder joint
  // relative to spine_03; cl*: clavicle root; hand: wrist -> middle of grip.
  const BODIES = {
    male: {
      key: 'male', name: 'Male (1.81 m)', model: 'models/quaternius-male.glb',
      hipUp: 0.022, hipHalf: 0.114, thigh: 0.429, shin: 0.459, ankleY: 0.086, toeFwd: 0.143, toeDrop: 0.071,
      sp1: 0.128, sp2: 0.107, sp3: 0.133, neck: 0.213, headJ: 0.084, headUp: 0.10,
      shUp: 0.144, shHalf: 0.212, shFwd: -0.07, clUp: 0.184, clHalf: 0.031,
      upper: 0.251, fore: 0.243, hand: 0.105, palm: 0.033, hb: 1.0,
      // Finger flexion (deg per joint) solved to wrap a 3.2 cm handle; the
      // thumb is placed by IK in the Studio (placeThumb).
      grip: { index: [65, 65, 65], middle: [65, 75, 75], ring: [55, 70, 75], pinky: [25, 65, 60] },
    },
    female: {
      key: 'female', name: 'Female (1.77 m)', model: 'models/quaternius-female.glb',
      hipUp: 0.012, hipHalf: 0.111, thigh: 0.409, shin: 0.465, ankleY: 0.071, toeFwd: 0.139, toeDrop: 0.056,
      sp1: 0.127, sp2: 0.109, sp3: 0.127, neck: 0.194, headJ: 0.065, headUp: 0.10,
      shUp: 0.127, shHalf: 0.152, shFwd: -0.052, clUp: 0.139, clHalf: 0.029,
      upper: 0.240, fore: 0.249, hand: 0.080, palm: 0.033, hb: 0.88,
      grip: { index: [55, 60, 65], middle: [60, 65, 75], ring: [45, 65, 70], pinky: [20, 55, 60] },
    },
  };
  const DIMS = BODIES.male;
  const GRIP_DIAG = 22;   // handle across the palm (deg)
  const bodyOf = k => BODIES[k] || BODIES.male;

  const WEAPONS = {
    longsword: { key: 'longsword', name: 'Longsword (Feder)', blade: 0.95, grip: 0.29, hand_sep: 0.15, guard_half: 0.135, nagel: false, width: 0.034, curve: 0 },
    messer: { key: 'messer', name: 'Kriegsmesser', blade: 0.80, grip: 0.28, hand_sep: 0.13, guard_half: 0.10, nagel: true, width: 0.042, curve: 0.022 },
  };

  // Strength / pace vocabulary for the bars.
  const strengthLabel = s => (s < 0.34 ? 'weak' : s > 0.66 ? 'strong' : 'medium');
  const paceLabel = p => (p < 0.88 ? 'fast' : p > 1.15 ? 'slow' : 'medium');

  // ------------------------------------------------------------ vectors
  const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const len = a => Math.sqrt(dot(a, a));
  const norm = a => { const l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
  const lerp = (a, b, u) => a + (b - a) * u;
  const lerp3 = (a, b, u) => [lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u)];
  const rad = d => d * Math.PI / 180;
  const smooth = u => { u = Math.min(Math.max(u, 0), 1); return u * u * (3 - 2 * u); };
  function rotY(v, deg) { // + brings +z (right) toward +x (forward)
    const c = Math.cos(rad(deg)), s = Math.sin(rad(deg));
    return [v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c];
  }
  function slerp(a, b, u) {
    a = norm(a); b = norm(b);
    const d = Math.min(Math.max(dot(a, b), -1), 1);
    if (d > 0.9995) return norm(lerp3(a, b, u));
    if (d < -0.9995) { const m = [0, 1, 0]; return u < 0.5 ? slerp(a, m, u * 2) : slerp(m, b, u * 2 - 1); }
    const th = Math.acos(d), s = Math.sin(th);
    return add(mul(a, Math.sin((1 - u) * th) / s), mul(b, Math.sin(u * th) / s));
  }
  function bladeDir(elev, az) {
    const e = rad(elev), a = rad(az);
    return [Math.cos(e) * Math.cos(a), Math.sin(e), Math.cos(e) * Math.sin(a)];
  }

  // ------------------------------------------------------------ poses
  const DEFAULT_POSE = {
    hip: [0, 0.88, 0], yaw: -20, lean: 0,
    lfoot: [0.30, -0.13], rfoot: [-0.30, 0.15],
    grip: [0.30, 1.0, 0.14], blade: bladeDir(28, -6), left_on: true, roll: 0,
  };
  const clonePose = p => JSON.parse(JSON.stringify(p));

  function lerpPose(a, b, u) {
    return {
      hip: lerp3(a.hip, b.hip, u), yaw: lerp(a.yaw, b.yaw, u), lean: lerp(a.lean, b.lean, u),
      lfoot: [lerp(a.lfoot[0], b.lfoot[0], u), lerp(a.lfoot[1], b.lfoot[1], u)],
      rfoot: [lerp(a.rfoot[0], b.rfoot[0], u), lerp(a.rfoot[1], b.rfoot[1], u)],
      grip: lerp3(a.grip, b.grip, u), blade: slerp(a.blade, b.blade, u),
      left_on: u > 0.5 ? b.left_on : a.left_on,
      roll: lerp(a.roll || 0, b.roll || 0, u),
    };
  }
  function footLift(a, b, u) {
    const tr = Math.hypot(a[0] - b[0], a[1] - b[1]);
    return tr < 0.08 ? 0 : 0.10 * Math.sin(Math.PI * u) * Math.min(1, tr / 0.3);
  }

  function twoBone(rootP, target, l1, l2, pole) {
    const dv = sub(target, rootP);
    let d = len(dv);
    const axis = d > 1e-9 ? mul(dv, 1 / d) : [1, 0, 0];
    d = Math.min(Math.max(d, Math.abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4);
    const a = (l1 * l1 - l2 * l2 + d * d) / (2 * d);
    const h = Math.sqrt(Math.max(l1 * l1 - a * a, 0));
    let p = sub(pole, mul(axis, dot(pole, axis)));
    if (len(p) < 1e-6) p = cross(axis, [0, 0, 1]);
    return add(add(rootP, mul(axis, a)), mul(norm(p), h));
  }
  function clampReach(from, to, r) {
    const v = sub(to, from), d = len(v);
    return d > r ? add(from, mul(v, r / d)) : to;
  }

  /** Pelvis height that keeps both feet on the ground (legs can't stretch). */
  function maxPelvisY(pose, body) {
    const D = body || DIMS, legMax = (D.thigh + D.shin) * 0.995;
    let best = Infinity;
    for (const [foot, side] of [[pose.lfoot, -1], [pose.rfoot, 1]]) {
      const hj = add(pose.hip, rotY([0, 0, side * D.hipHalf], pose.yaw * 0.5));
      const h = Math.hypot(hj[0] - foot[0], hj[2] - foot[1]);
      const v = h < legMax ? Math.sqrt(legMax * legMax - h * h) : 0.05;
      best = Math.min(best, D.ankleY - D.hipUp + v);
    }
    return best;
  }

  /** Joint positions in the fencer's local frame. */
  function skeleton(pose, weapon, lift, body, hint) {
    const D = body || DIMS; lift = lift || [0, 0];
    const hip = [pose.hip[0], Math.min(pose.hip[1], maxPelvisY(pose, D)), pose.hip[2]];
    const fwd = rotY([1, 0, 0], pose.yaw), right = rotY([0, 0, 1], pose.yaw);
    const hfwd = rotY([1, 0, 0], pose.yaw * 0.5);
    const L = rad(pose.lean);
    const up = add(mul([0, 1, 0], Math.cos(L)), mul(fwd, Math.sin(L)));
    const sp1 = add(hip, mul(up, D.sp1));
    const sp2 = add(sp1, mul(up, D.sp2));
    const chest = add(sp2, mul(up, D.sp3));
    const neck = add(chest, mul(up, D.neck));
    const headJ = add(neck, mul(up, D.headJ));
    const head = add(headJ, mul(up, D.headUp));
    const shoulder = side => add(add(add(chest, mul(up, D.shUp)), mul(right, side * D.shHalf)), mul(fwd, D.shFwd));
    const clav = side => add(add(chest, mul(up, D.clUp)), mul(right, side * D.clHalf));
    const sh_r = shoulder(1), sh_l = shoulder(-1);
    const bodyObs = { list: bodyObstacles({ pelvis: hip, chest, headJ, head, up, right }, D), chestPt: chest };
    const hp_r = add(hip, rotY([0, D.hipUp, D.hipHalf], pose.yaw * 0.5));
    const hp_l = add(hip, rotY([0, D.hipUp, -D.hipHalf], pose.yaw * 0.5));

    const d = norm(pose.blade);
    const reach = D.upper + D.fore + D.hand - 0.004;
    let hand_r = clampReach(sh_r, pose.grip, reach), hand_l;
    if (pose.left_on) {
      hand_l = sub(hand_r, mul(d, weapon.hand_sep));
      const fixed = clampReach(sh_l, hand_l, reach);
      if (len(sub(fixed, hand_l)) > 1e-6) {
        hand_r = clampReach(sh_r, add(hand_r, sub(fixed, hand_l)), reach);
        hand_l = sub(hand_r, mul(d, weapon.hand_sep));
      }
    } else {
      hand_l = add(sh_l, add(mul(up, -0.5), add(mul(fwd, 0.10), mul(right, -0.08))));
    }
    // Self-collision repair: a pose may ask for the hilt inside the head or
    // the belly. Push the hands just clear (head: hand + head radius, trunk:
    // hand + trunk radius) so arms and fists never go through the body.
    {
      const nearPt = (p, a, b) => { const ab = sub(b, a), l2 = dot(ab, ab); const u = l2 ? Math.max(0, Math.min(1, dot(sub(p, a), ab) / l2)) : 0; return add(a, mul(ab, u)); };
      const hiltA = () => pose.left_on ? sub(hand_l, mul(d, 0.04)) : hand_r, hiltB = () => add(hand_r, mul(d, 0.04));
      const shift = v => { hand_r = add(hand_r, v); if (pose.left_on) hand_l = add(hand_l, v); };
      for (let it = 0; it < 2; it++) {
        const ph = nearPt(head, hiltA(), hiltB()), dh = len(sub(ph, head));
        if (dh < 0.2) { const dir = dh > 1e-4 ? norm(sub(ph, head)) : fwd; shift(mul(dir, 0.2 - dh)); }
        const [dt, sa, sb] = segSegInline(hiltA(), hiltB(), hip, neck);   // trunk and neck
        if (dt < 0.22) {
          const pa = add(hiltA(), mul(sub(hiltB(), hiltA()), sa)), pb = add(hip, mul(sub(neck, hip), sb));
          let dir = sub(pa, pb); dir = sub(dir, mul(up, dot(dir, up)));    // push out horizontally
          dir = len(dir) > 1e-3 ? norm(dir) : fwd;
          shift(mul(dir, 0.22 - dt));
        }
      }
    }
    // Grip frame per hand: knuckle line (index -> pinky) runs toward the
    // pommel, fingers point along the arm's reach (square to the hilt), and
    // the palm side follows from which hand it is (mirror images). The wrist
    // is placed so the hilt axis sits where the solved finger curl wraps it:
    // D.hand along the fingers and D.palm toward the palm.
    // The true edge lines up with the front hand's knuckles. By default it
    // faces along the front arm's reach (square to the blade); pose.roll turns
    // it about the blade. Both hands grip along the same edge line.
    const rotAbout = (v, axis, deg) => {   // Rodrigues
      const c = Math.cos(rad(deg)), s2 = Math.sin(rad(deg));
      return add(add(mul(v, c), mul(cross(axis, v), s2)), mul(axis, dot(axis, v) * (1 - c)));
    };
    let edge;
    const pe = pose.edge ? sub(pose.edge, mul(d, dot(pose.edge, d))) : null;
    if (pe && len(pe) > 0.15) edge = norm(pe);           // stored / interpolated edge
    else {
    edge = sub(hand_r, sh_r); edge = sub(edge, mul(d, dot(edge, d)));
    if (len(edge) < 1e-4) edge = sub(fwd, mul(d, dot(fwd, d)));
    edge = norm(rotAbout(norm(edge), d, pose.roll || 0));
    }
    const gripFrame = (sh, hand, side, Fin) => {
      const K = mul(d, -1);
      let F = Fin;
      if (!F) { F = sub(hand, sh); F = sub(F, mul(d, dot(F, d))); if (len(F) < 1e-4) F = sub(fwd, mul(d, dot(fwd, d))); F = norm(F); }
      const palm = mul(cross(F, K), side);          // side: +1 right, -1 left
      // The handle lies diagonally across the palm (index base -> heel of the
      // hand), so the hand's own axes are turned ~22 deg about the palm normal:
      // the fingers lean toward the blade and the forearm comes in from the
      // pommel side, as in a real sword grip.
      const ct = Math.cos(rad(GRIP_DIAG)), st = Math.sin(rad(GRIP_DIAG));
      const Fd = norm(add(mul(F, ct), mul(d, st)));
      const Kd = norm(sub(K, mul(Fd, dot(K, Fd))));
      const wrist = sub(sub(hand, mul(Fd, D.hand)), mul(palm, D.palm));
      return { F: Fd, K: Kd, palm, wrist };
    };
    // ---- Arms: analytical IK with anatomical joint limits -------------
    // After Kallmann, "Analytical inverse kinematics with body posture
    // control" (CAVW 2008): the elbow lies on a circle around the
    // shoulder-wrist line (the swivel angle phi). Start from the natural
    // elbow (down and a little out) and move away from it only as far as
    // needed for every joint to stay inside its range of motion and the arm
    // to stay out of the body. Each hand may also roll a little on the
    // handle (psi). If nothing is valid, take the least-bad arm and report
    // the violation so the pose can be flagged.
    const torso = { up, fwd, right };
    const evalArm = (sh, wrist, side, gf, phi, avoid) => {
      const L1 = D.upper, L2 = D.fore;
      const w = clampReach(sh, wrist, L1 + L2 - 0.002), n = norm(sub(w, sh));
      let dd = len(sub(w, sh)); dd = Math.min(Math.max(dd, Math.abs(L1 - L2) + 1e-4), L1 + L2 - 1e-4);
      const a = (L1 * L1 - L2 * L2 + dd * dd) / (2 * dd), h = Math.sqrt(Math.max(L1 * L1 - a * a, 0));
      const c0 = add(sh, mul(n, a));
      const lat = mul(right, side);
      let u = sub(mul(up, -1), mul(n, -dot(up, n))); if (len(u) < 1e-3) u = sub(lat, mul(n, dot(lat, n)));
      u = norm(u);
      let v = cross(n, u); if (dot(v, lat) < 0) v = mul(v, -1);
      const t = rad(phi), el = add(c0, add(mul(u, h * Math.cos(t)), mul(v, h * Math.sin(t))));
      const viol = armViolation(sh, el, w, side, gf, torso, obsBody, avoid);
      return { el, wr: w, viol };
    };
    if (hint) hint.n = (hint.n || 0) + 1;
    const solveArm = (sh, hand, side, Fedge, psiMax, avoid, slot) => {
      const tryPsi = (psi, phi) => {
        const gf = gripFrame(sh, hand, side, Fedge ? norm(rotAbout(Fedge, d, psi)) : null);
        const r = evalArm(sh, gf.wrist, side, gf, phi, avoid);
        return { ...r, gf, psi, phi };
      };
      const prev = hint && hint[slot];
      if (prev && hint.reuse && hint.n % 4 !== 0) return tryPsi(prev.psi, prev.phi);   // between solves on the sim clock
      let best = null;
      for (const [psi, phi] of SEARCH_COARSE) {            // nearest to the natural arm first
        if (Math.abs(psi) > psiMax || (!Fedge && psi)) continue;
        const r = tryPsi(psi, phi);
        if (r.viol.total === 0) { best = r; break; }      // first valid arm wins
        if (!best || r.viol.total < best.viol.total) best = r;
      }
      if (best.viol.total > 0) {                          // nothing valid: polish the least-bad arm
        for (const dpsi of [-10, 0, 10]) for (const dphi of [-7.5, 0, 7.5]) {
          const psi = best.psi + dpsi; if (Math.abs(psi) > psiMax || (!Fedge && psi)) continue;
          const r = tryPsi(psi, best.phi + dphi); if (r.viol.total < best.viol.total) best = r;
        }
      }
      if (hint) hint[slot] = { psi: best.psi, phi: best.phi };
      return best;
    };
    const obsBody = bodyObs;
    let R_ = solveArm(sh_r, hand_r, 1, edge, 30, null, 'r');
    let L_ = solveArm(sh_l, hand_l, -1, pose.left_on ? edge : null, 60, [[R_.el, R_.wr], [sh_r, R_.el]], 'l');
    // The hands never let go: if a wrist could not reach where the grip needs
    // it (hilt posed beyond arm's length), bring the whole sword back to it.
    for (let it = 0; it < 3; it++) {
      const shortR = sub(R_.wr, R_.gf.wrist), shortL = pose.left_on ? sub(L_.wr, L_.gf.wrist) : [0, 0, 0];
      const pull = len(shortR) >= len(shortL) ? shortR : shortL;
      if (len(pull) < 0.002) break;
      hand_r = add(hand_r, pull); hand_l = add(hand_l, pose.left_on ? pull : [0, 0, 0]);
      R_ = solveArm(sh_r, hand_r, 1, edge, 30, null, 'r');
      L_ = solveArm(sh_l, hand_l, -1, pose.left_on ? edge : null, 60, [[R_.el, R_.wr], [sh_r, R_.el]], 'l');
    }
    const gr = R_.gf, gl = L_.gf, wr_r = R_.wr, wr_l = L_.wr, el_r = R_.el, el_l = L_.el;

    const an_l = [pose.lfoot[0], D.ankleY + lift[0], pose.lfoot[1]];
    const an_r = [pose.rfoot[0], D.ankleY + lift[1], pose.rfoot[1]];
    const kn_l = twoBone(hp_l, an_l, D.thigh, D.shin, sub(hfwd, rotY([0, 0, 0.3], pose.yaw * 0.5)));
    const kn_r = twoBone(hp_r, an_r, D.thigh, D.shin, add(hfwd, rotY([0, 0, 0.3], pose.yaw * 0.5)));
    const toe = an => add(an, [hfwd[0] * D.toeFwd, -D.toeDrop, hfwd[2] * D.toeFwd]);

    // wrist angles actually used (deg): flexion toward the palm, sideways deviation
    const wristAng = (wr, el, gf) => { const v = norm(sub(wr, el)), fF = dot(v, gf.F);
      return [Math.atan2(dot(v, gf.palm), fF) * 57.3, Math.atan2(dot(v, gf.K), fF) * 57.3]; };
    const guard = add(hand_r, mul(d, 0.055));
    return {
      pelvis: hip, sp1, sp2, chest, neck, headJ, head, cl_l: clav(-1), cl_r: clav(1),
      sh_l, sh_r, el_l, el_r, wr_l, wr_r,
      hand_l, hand_r, hp_l, hp_r, kn_l, kn_r, an_l, an_r, toe_l: toe(an_l), toe_r: toe(an_r),
      guard, tip: add(guard, mul(d, weapon.blade)), pommel: sub(guard, mul(d, weapon.grip)),
      fwd, up, right, hfwd,
      hF_r: gr.F, hK_r: gr.K, hF_l: gl.F, hK_l: gl.K, edge, armCost: [R_.viol.total, L_.viol.total], armViol: [R_.viol, L_.viol], wristDeg: [wristAng(wr_r, el_r, gr), wristAng(wr_l, el_l, gl)],
    };
  }

  // Radii measured from the skinned Quaternius male (the female uses body.hb).
  const HITBOXES = [
    ['head', 'head', 'head', 0.11], ['torso', 'pelvis', 'neck', 0.16],
    ['upper arm R', 'sh_r', 'el_r', 0.07], ['upper arm L', 'sh_l', 'el_l', 0.07],
    ['forearm R', 'el_r', 'wr_r', 0.055], ['forearm L', 'el_l', 'wr_l', 0.055],
    ['hand R', 'hand_r', 'hand_r', 0.065], ['hand L', 'hand_l', 'hand_l', 0.065],
    ['thigh R', 'hp_r', 'kn_r', 0.095], ['thigh L', 'hp_l', 'kn_l', 0.095],
    ['shin R', 'kn_r', 'an_r', 0.06], ['shin L', 'kn_l', 'an_l', 0.06],
  ];

  function toWorld(v, origin, facing) {
    return facing === 1 ? [origin + v[0], v[1], v[2]] : [origin - v[0], v[1], -v[2]];
  }
  function toLocal(v, origin, facing) {
    return facing === 1 ? [v[0] - origin, v[1], v[2]] : [origin - v[0], v[1], -v[2]];
  }
  const DIR_KEYS = new Set(['fwd', 'up', 'right', 'hfwd', 'hF_r', 'hK_r', 'hF_l', 'hK_l', 'edge']);
  function skeletonWorld(sk, origin, facing) {
    const out = {};
    for (const k in sk) {
      const v = sk[k];
      out[k] = k === 'armCost' || k === 'wristDeg' || k === 'armViol' ? v : DIR_KEYS.has(k) ? (facing === 1 ? v.slice() : [-v[0], v[1], -v[2]]) : toWorld(v, origin, facing);
    }
    return out;
  }

  function segSegInline(a, b, c, e) { return segSeg(a, b, c, e); }

  // ---- Range of motion (degrees), from standard clinical tables (AAOS /
  // Physiopedia "Range of Motion Normative Values"): shoulder flexion and
  // abduction ~180, extension ~60, external rotation ~90, internal rotation
  // ~70 (more with the arm across the body); elbow flexion ~145; wrist
  // flexion ~80, extension ~70, radial deviation ~20, ulnar ~35-40.
  //
  // Shoulder elevation limit as a function of the plane of elevation:
  // 0 = straight out to the side, +90 = straight forward, +180 = across the
  // body, -90 = straight back. Full elevation is only possible around the
  // scapular plane; behind the body and across it the limit drops.
  const SHOULDER_MAX_ELEV = [[-180, 30], [-150, 35], [-120, 45], [-90, 60], [-60, 100], [-30, 150], [0, 170],
    [30, 180], [60, 180], [90, 175], [120, 145], [140, 115], [160, 60], [180, 30]];
  const ROM = { erMax: 90, irMax: 90, elbowMax: 145, flexMax: 75, extMax: 70, radMax: 25, ulnMax: 40 };
  function maxElev(plane) {
    const T = SHOULDER_MAX_ELEV;
    for (let i = 1; i < T.length; i++) if (plane <= T[i][0]) {
      const [p0, e0] = T[i - 1], [p1, e1] = T[i]; return e0 + (e1 - e0) * (plane - p0) / (p1 - p0);
    }
    return T[T.length - 1][1];
  }
  const rotMin = (from, to, v) => {             // minimal rotation taking unit `from` to unit `to`, applied to v
    const k = cross(from, to), s = len(k), c = dot(from, to);
    if (s < 1e-6) return c > 0 ? v.slice() : mul(v, -1);
    const kn = mul(k, 1 / s);
    return add(add(mul(v, c), mul(cross(kn, v), s)), mul(kn, dot(kn, v) * (1 - c)));
  };
  /** Shoulder, elbow and wrist angles of an arm, in degrees. */
  function armAngles(sh, el, wr, side, gf, T) {
    const lat = mul(T.right, side), a = norm(sub(el, sh));
    const elev = Math.acos(Math.max(-1, Math.min(1, -dot(a, T.up)))) * 57.2958;
    const plane = Math.atan2(dot(a, T.fwd), dot(a, lat)) * 57.2958;
    const f = norm(sub(wr, el));
    const elbow = Math.acos(Math.max(-1, Math.min(1, dot(a, f)))) * 57.2958;   // 0 = straight
    // humeral rotation: zero when, with the arm out to the side, the forearm
    // points forward; + = external (forearm turning up/back)
    let rot = 0;
    if (elbow > 25) {
      const ref = rotMin(lat, a, T.fwd), fp = norm(sub(f, mul(a, dot(f, a)))), rp = norm(sub(ref, mul(a, dot(ref, a))));
      rot = side * Math.atan2(dot(cross(rp, fp), a), dot(rp, fp)) * 57.2958;
    }
    const fF = dot(f, gf.F);
    const wFlex = Math.atan2(dot(f, gf.palm), fF) * 57.2958, wDev = Math.atan2(dot(f, gf.K), fF) * 57.2958;
    return { elev, plane, elbow, rot, wFlex, wDev };
  }
  /** How far an arm is outside its range of motion or inside the body
   *  (0 = valid). Units: degrees/10 and cm. */
  function armViolation(sh, el, wr, side, gf, T, obs, avoid) {
    const A = armAngles(sh, el, wr, side, gf, T), v = {};
    const over = (x, m) => Math.max(0, x - m) / 10;
    v.shoulder = A.elev > 20 ? over(A.elev, maxElev(A.plane)) : 0;
    v.rotation = over(A.rot, ROM.erMax) + over(-A.rot, ROM.irMax);
    v.elbow = over(A.elbow, ROM.elbowMax);
    v.wrist = over(A.wFlex, ROM.flexMax) + over(-A.wFlex, ROM.extMax) + over(A.wDev, ROM.radMax) + over(-A.wDev, ROM.ulnMax);
    // the arm must stay out of the trunk, upper chest, neck and head
    let body = 0;
    const lat = mul(T.right, side);
    const samples = [[sh, el, 0.055, [0.5, 1]], [el, wr, 0.045, [0.33, 0.66, 0.9]]];
    for (let si = 0; si < 2; si++) {
      const [p0, p1, rArm, ks] = samples[si];
      for (const k of ks) {
        const p = add(p0, mul(sub(p1, p0), k));
        const crossing = dot(sub(p, obs.chestPt), lat) < 0.08;
        for (const [nm, oa, ob, or] of obs.list) {
          if (si === 0 && (nm === 'chest' || nm === 'neck') && !crossing) continue;   // the upper arm starts at the shoulder
          const pen = or + rArm - segSeg(p, p, oa, ob)[0];
          if (pen > 0.01) body = Math.max(body, (pen - 0.01) * 100);
        }
        if (avoid && si === 1 && k < 0.8) for (const [oa, ob] of avoid) {
          const pen = 0.085 - segSeg(p, p, oa, ob)[0]; if (pen > 0) body = Math.max(body, pen * 100);
        }
      }
    }
    v.body = body;
    v.total = v.shoulder + v.rotation + v.elbow + v.wrist + v.body;
    v.angles = A;
    return v;
  }
  // Candidate (psi, phi) pairs, nearest to the natural arm first: hand on
  // the edge line (psi 0), elbow down and slightly out (phi 25).
  const SEARCH_ORDER = (() => {
    const c = [];
    for (let psi = -60; psi <= 60; psi += 10) for (let phi = -40; phi <= 170; phi += 7.5) c.push([psi, phi]);
    return c.sort((a, b) => (Math.abs(a[0]) / 15 + Math.abs(a[1] - 25) / 15) - (Math.abs(b[0]) / 15 + Math.abs(b[1] - 25) / 15));
  })();
  const SEARCH_COARSE = SEARCH_ORDER.filter(([psi, phi]) => psi % 20 === 0 && (phi + 40) % 15 === 0);

  /** The fencer's own upper body as capsules the arms must stay out of:
   *  [name, a, b, radius]. Lower trunk, a wide bar across the upper chest
   *  and shoulders, the neck, and the head. */
  function bodyObstacles(j, body) {
    const k = (body && body.hb) || 1, { pelvis, chest, headJ, head, up, right } = j;
    const cb = add(chest, mul(up, 0.07));
    return [
      ['trunk', pelvis, chest, 0.14 * k],
      ['chest', sub(cb, mul(right, 0.12 * k)), add(cb, mul(right, 0.12 * k)), 0.11 * k],
      ['neck', add(chest, mul(up, 0.12)), headJ, 0.065 * k],
      ['head', head, head, 0.11 * k],
    ];
  }
  function segSeg(p1, q1, p2, q2) {
    const d1 = sub(q1, p1), d2 = sub(q2, p2), r = sub(p1, p2);
    const a = dot(d1, d1), e = dot(d2, d2), f = dot(d2, r), eps = 1e-12;
    let s, t;
    if (a <= eps && e <= eps) return [len(r), 0, 0];
    if (a <= eps) { s = 0; t = Math.min(Math.max(f / e, 0), 1); }
    else {
      const c = dot(d1, r);
      if (e <= eps) { t = 0; s = Math.min(Math.max(-c / a, 0), 1); }
      else {
        const b = dot(d1, d2), den = a * e - b * b;
        s = den > eps ? Math.min(Math.max((b * f - c * e) / den, 0), 1) : 0;
        t = (b * s + f) / e;
        if (t < 0) { t = 0; s = Math.min(Math.max(-c / a, 0), 1); }
        else if (t > 1) { t = 1; s = Math.min(Math.max((b - c) / a, 0), 1); }
      }
    }
    return [len(sub(add(p1, mul(d1, s)), add(p2, mul(d2, t)))), s, t];
  }
  /** Crossguard bar endpoints: the quillons lie in the plane of the edges. */
  function crossEnds(guard, tip, half, edge) {
    const d = norm(sub(tip, guard));
    let ax = edge ? sub(edge, mul(d, dot(edge, d))) : cross(d, [0, 1, 0]);
    if (len(ax) < 0.2) ax = cross(d, [0, 1, 0]);
    if (len(ax) < 0.2) ax = [0, 0, 1];
    ax = norm(ax);
    return [sub(guard, mul(ax, half)), add(guard, mul(ax, half))];
  }

  // ------------------------------------------------------------ timeline
  /** Real times of a fencer's keys. Keys store `at` in base beats (as
   *  recorded); an action's pace stretches or squeezes its span, and
   *  everything after it moves with it. */
  function layout(ex, f) {
    const keys = (ex.tracks[f].keys || []).slice().sort((a, b) => a.at - b.at);
    const idx = {}; keys.forEach((k, i) => { idx[k.id] = i; });
    const acts = (ex.actions || []).filter(a => a.fencer === f && a.from in idx && a.to in idx && idx[a.from] < idx[a.to])
      .map(a => ({ ...a, i0: idx[a.from], i1: idx[a.to] }));
    const segAct = new Array(keys.length).fill(null);
    for (const a of acts) for (let i = a.i0 + 1; i <= a.i1; i++) segAct[i] = a;
    const real = [];
    const B = ex.beat_ms;
    keys.forEach((k, i) => {
      if (i === 0) real.push(k.at * B);
      else {
        const pace = segAct[i] ? (segAct[i].pace || 1) : 1;
        real.push(real[i - 1] + (k.at - keys[i - 1].at) * B * pace);
      }
    });
    for (const a of acts) { a.t0 = real[a.i0]; a.t1 = real[a.i1]; }
    return { keys, real, segAct, acts, idx, f };
  }
  function realToBase(L, t, beat) {
    const { keys, real, segAct } = L;
    if (!keys.length || t <= real[0]) return t / beat - (keys.length ? (real[0] / beat - keys[0].at) : 0);
    for (let i = 1; i < keys.length; i++) {
      if (t <= real[i]) {
        const pace = segAct[i] ? (segAct[i].pace || 1) : 1;
        return keys[i - 1].at + (t - real[i - 1]) / beat / pace;
      }
    }
    const n = keys.length - 1;
    return keys[n].at + (t - real[n]) / beat;
  }

  // Pose repair: a key may ask for the hilt somewhere the arms cannot reach
  // within their range of motion. Move the hilt (and turn the edge a little
  // if needed) to the nearest place the body can actually hold it. Greedy
  // search: shrinking steps along the six axis directions and +-15 deg of
  // edge, minimising violation first, then how far the hilt moved.
  const repairCache = new WeakMap();
  function violationOf(pose, W, B) {
    const sk = skeleton(pose, W, null, B);
    return sk.armViol[0].total + (pose.left_on ? sk.armViol[1].total : 0);
  }
  function repairPose(pose, W, B) {
    if (!pose || pose.repaired) return pose;
    const hit = repairCache.get(pose); if (hit) return hit;
    let best = { off: [0, 0, 0], roll: 0 }, v0 = violationOf(pose, W, B);
    const score = (v, o, r) => v * 100 + len(o) * 10 + Math.abs(r) / 30;
    let bestScore = score(v0, best.off, 0), bestV = v0;
    if (v0 > 0.05) {
      const make = (o, r) => Object.assign({}, pose, { grip: add(pose.grip, o), roll: (pose.roll || 0) + r, edge: undefined });
      for (const step of [0.08, 0.04, 0.02]) {
        let improved = true, guard = 0;
        while (improved && guard++ < 6) {
          improved = false;
          const cands = [[step, 0, 0], [-step, 0, 0], [0, step, 0], [0, -step, 0], [0, 0, step], [0, 0, -step]].map(dv => [add(best.off, dv), best.roll]);
          cands.push([best.off, best.roll + 15], [best.off, best.roll - 15]);
          for (const [o, r] of cands) {
            if (Math.abs(r) > 30 || len(o) > 0.25) continue;
            const v = violationOf(make(o, r), W, B), sc = score(v, o, r);
            if (sc < bestScore - 1e-6) { bestScore = sc; bestV = v; best = { off: o, roll: r }; improved = true; }
          }
          if (bestV <= 0.05) break;
        }
      }
    }
    const out = Object.assign({}, pose, { grip: add(pose.grip, best.off), roll: (pose.roll || 0) + best.roll, repaired: true,
      repair: { moved: +len(best.off).toFixed(3), roll: best.roll, before: +v0.toFixed(2), after: +bestV.toFixed(2) } });
    if (best.roll || len(best.off) > 1e-6) delete out.edge;   // edge re-derived for the moved hilt
    repairCache.set(pose, out);
    return out;
  }

  // Edges between keys: each key's edge is fixed (stored, or derived once
  // from its own pose), and in between the edge turns smoothly from one to
  // the next. Deriving it every frame from the arm would flip it whenever
  // the blade points along the arm.
  const edgeCache = new WeakMap();
  function edgeOf(pose, weapon, body) {
    if (pose.edge) return pose.edge;
    let e = edgeCache.get(pose);
    if (!e) { e = skeleton(Object.assign({}, pose, { edge: null }), weapon, null, body).edge; edgeCache.set(pose, e); }
    return e;
  }
  function blendEdge(p0, p1, u, out, weapon, body) {
    const e0 = edgeOf(p0, weapon, body), e1 = edgeOf(p1, weapon, body);
    const e = slerp(e0, e1, u), d = norm(out.blade);
    const pe = sub(e, mul(d, dot(e, d)));
    out.edge = len(pe) > 1e-3 ? norm(pe) : e;
    return out;
  }

  /** Pose of fencer f at time t (ms). `ov` = displacement overrides. */
  function poseAt(ex, L, t, ov, guardPose) {
    const { keys, real, segAct } = L;
    const fc = ex.fencers[L.f == null ? 0 : L.f] || {}, Wp = WEAPONS[fc.weapon] || WEAPONS.longsword, Bp = bodyOf(fc.body);
    if (!keys.length) return { pose: guardPose || DEFAULT_POSE, lift: [0, 0] };
    const kp = i => {
      let p = repairPose(keys[i].pose, Wp, Bp);
      if (ov) for (const o of ov) if (o.endIdx === i) p = o.endPose;
      return p;
    };
    if (ov) for (const o of ov) {
      if (t >= o.tc && t <= real[o.endIdx]) {
        const u = smooth((t - o.tc) / Math.max(real[o.endIdx] - o.tc, 1));
        return { pose: blendEdge(o.poseTc, o.endPose, u, lerpPose(o.poseTc, o.endPose, u), Wp, Bp), lift: [0, 0] };
      }
    }
    if (t <= real[0]) return { pose: kp(0), lift: [0, 0] };
    const n = keys.length - 1;
    if (t >= real[n]) return { pose: kp(n), lift: [0, 0] };
    let i = 1; while (i < n && t > real[i]) i++;
    let j = i, u;
    const a = segAct[i];
    if (a) {   // ease across the whole action, then map back to its keys
      const t2 = a.t0 + smooth((t - a.t0) / Math.max(a.t1 - a.t0, 1)) * (a.t1 - a.t0);
      j = a.i0 + 1; while (j < a.i1 && t2 > real[j]) j++;
      u = (t2 - real[j - 1]) / Math.max(real[j] - real[j - 1], 1e-6);
    } else {
      u = smooth((t - real[i - 1]) / Math.max(real[i] - real[i - 1], 1e-6));
    }
    u = Math.min(Math.max(u, 0), 1);
    const p0 = kp(j - 1), p1 = kp(j);
    return { pose: blendEdge(p0, p1, u, lerpPose(p0, p1, u), Wp, Bp), lift: [footLift(p0.lfoot, p1.lfoot, u), footLift(p0.rfoot, p1.rfoot, u)] };
  }

  function actionAt(L, t) {
    for (const a of L.acts) if (t >= a.t0 && t < a.t1) return a;
    return null;
  }

  // ------------------------------------------------------------ fight
  const BLADE_HIT_FROM = 0.12, BLADE_HALF = 0.012, BIND_DIST = 0.03;

  function origins(ex) { return [[0, 1], [ex.distance, -1]]; }

  /** Blade force at a contact: strength, leverage (near the hilt is
   *  stronger) and whether the blade is doing something on purpose. */
  function bladeForce(act, frac) {
    const s = act ? (act.strength == null ? 0.5 : act.strength) : 0.3;
    const purpose = act && (act.attack || act.cover) ? 1 : 0.5;
    const coverBonus = act && act.cover ? 1.15 : 1;
    return (0.5 + s) * (1.25 - frac) * purpose * coverBonus;
  }

  function simulate(ex, opts) {
    opts = opts || {};
    const window = opts.doubleWindow == null ? 150 : opts.doubleWindow;
    const W = ex.fencers.map(f => WEAPONS[f.weapon] || WEAPONS.longsword);
    const BD = ex.fencers.map(f => bodyOf(f.body));
    const Ls = [layout(ex, 0), layout(ex, 1)];
    const O = origins(ex);
    const ov = [[], []];
    const dead = [new Set(), new Set()], landed = [new Set(), new Set()];
    const events = [], first = [null, null];
    const hitParts = [new Set(), new Set()];
    const guards = opts.guards || [null, null];
    let end = 0;
    Ls.forEach(L => { if (L.real.length) end = Math.max(end, L.real[L.real.length - 1]); });
    end = Math.min(end + 400, 12000);
    let lastContact = -1e9;
    const hints = [{ reuse: true }, { reuse: true }];
    const dt = opts.dt || 1;

    // a continuation inherits "dead"/"landed" from the action it follows
    const chainOf = (L, a) => { let c = a; while (c && c.cont) { const prev = L.acts.find(p => p.i1 === c.i0); if (!prev) break; c = prev; } return c; };

    for (let t = 0; t <= end; t += dt) {
      const P = [0, 1].map(f => poseAt(ex, Ls[f], t, ov[f], guards[f]));
      const SK = [0, 1].map(f => skeletonWorld(skeleton(P[f].pose, W[f], P[f].lift, BD[f], hints[f]), O[f][0], O[f][1]));
      const A = [0, 1].map(f => actionAt(Ls[f], t));
      const root = [0, 1].map(f => A[f] && chainOf(Ls[f], A[f]));
      const isDead = f => root[f] && dead[f].has(root[f].id);

      // --- weapon contact
      if (t - lastContact > 250) {
        const c = contact(SK, W);
        if (c) {
          lastContact = t;
          const [fa, fb, pa, pb] = c;
          const point = mul(add(pa, pb), 0.5).map(v => +v.toFixed(3));
          const frac = [fa, fb];
          const force = [0, 1].map(f => isDead(f) ? 0.2 : bladeForce(A[f], frac[f]));
          const active = [0, 1].map(f => !!(A[f] && (A[f].attack || A[f].cover) && !isDead(f)));
          let win = null;
          for (const [i, j] of [[0, 1], [1, 0]]) if (active[i] && force[i] > force[j] * 1.2) win = i;
          if (win !== null) {
            const lose = 1 - win;
            let n = norm(lose === 0 ? sub(pa, pb) : sub(pb, pa));
            displace(lose, t, n, true);
            events.push({ t, kind: 'displace', by: win, on: lose, point,
              note: `${strengthLabel(A[win] ? A[win].strength : 0.5)} blade, ${Math.round(frac[win] * 100)}% up the blade, on ${Math.round(frac[lose] * 100)}% (force ${force[win].toFixed(2)} vs ${force[lose].toFixed(2)})` });
          } else if (active[0] && active[1]) {
            displace(0, t, [0, 0, 0], false); displace(1, t, [0, 0, 0], false);
            events.push({ t, kind: 'bind', by: 0, on: 1, point,
              note: `crossed at ${Math.round(fa * 100)}% / ${Math.round(fb * 100)}%, forces ${force[0].toFixed(2)} vs ${force[1].toFixed(2)}: nobody wins the bind` });
          } else {
            events.push({ t, kind: 'bind', by: 0, on: 1, point, note: `blades touch at ${Math.round(fa * 100)}% / ${Math.round(fb * 100)}%` });
          }
        }
      }

      // --- hits
      for (const i of [0, 1]) {
        const j = 1 - i, a = A[i];
        if (!a || !a.attack || isDead(i) || landed[i].has(root[i].id)) continue;
        const g = SK[i].guard, tip = SK[i].tip;
        const from = add(g, mul(sub(tip, g), BLADE_HIT_FROM));
        for (const [name, ja, jb, r] of HITBOXES) {
          if (hitParts[j].has(name)) continue;
          const [d, s] = segSeg(from, tip, SK[j][ja], SK[j][jb]);
          if (d < r * BD[j].hb + BLADE_HALF) {
            hitParts[j].add(name); landed[i].add(root[i].id);
            const ev = { t, kind: 'hit', by: i, on: j, part: name, action: a.name,
              severity: strengthLabel(a.strength == null ? 0.5 : a.strength),
              point: add(from, mul(sub(tip, from), s)).map(v => +v.toFixed(3)) };
            events.push(ev); if (!first[i]) first[i] = ev;
            break;
          }
        }
      }

      function displace(f, tc, n, hard) {
        const a = A[f]; if (!a) return;
        const L = Ls[f], cur = P[f].pose;
        const nl = O[f][1] === 1 ? n : [-n[0], n[1], -n[2]];
        let endPose = clonePose(L.keys[a.i1].pose);
        for (const o of ov[f]) if (o.endIdx === a.i1) endPose = clonePose(o.endPose);
        if (hard) {
          endPose.blade = norm(add(add(cur.blade, mul(nl, 1.1)), [0, -0.35, 0]));
          endPose.grip = add(cur.grip, mul(nl, 0.10));
        } else { endPose.blade = cur.blade.slice(); endPose.grip = cur.grip.slice(); }
        if (cur.edge) endPose.edge = cur.edge.slice();   // a knocked-aside blade keeps its edge orientation
        ov[f].push({ tc, poseTc: clonePose(cur), endIdx: a.i1, endPose });
        dead[f].add(chainOf(L, a).id);
      }
    }
    const [verdict, detail] = judge(first, window, ex);
    return { events, overrides: ov, first, verdict, detail, end, layouts: Ls };
  }

  function contact(SK, W) {
    const ag = SK[0].guard, at = SK[0].tip, bg = SK[1].guard, bt = SK[1].tip;
    let best = null;
    let [d, sa, sb] = segSeg(ag, at, bg, bt);
    if (d < BIND_DIST) best = [d, sa, sb, add(ag, mul(sub(at, ag), sa)), add(bg, mul(sub(bt, bg), sb))];
    const [ca0, ca1] = crossEnds(ag, at, W[0].guard_half, SK[0].edge), [cb0, cb1] = crossEnds(bg, bt, W[1].guard_half, SK[1].edge);
    let r = segSeg(ca0, ca1, bg, bt);
    if (r[0] < BIND_DIST && (!best || r[0] < best[0])) best = [r[0], 0, r[2], add(ca0, mul(sub(ca1, ca0), r[1])), add(bg, mul(sub(bt, bg), r[2]))];
    r = segSeg(ag, at, cb0, cb1);
    if (r[0] < BIND_DIST && (!best || r[0] < best[0])) best = [r[0], r[1], 0, add(ag, mul(sub(at, ag), r[1])), add(cb0, mul(sub(cb1, cb0), r[2]))];
    return best ? best.slice(1) : null;
  }

  function judge(first, window, ex) {
    const N = [ex.fencers[0].label || 'A', ex.fencers[1].label || 'B'];
    const [ha, hb] = first;
    if (!ha && !hb) return ['No hit', 'Nobody landed. Look at the binds and displacements.'];
    if (ha && hb) {
      const gap = hb.t - ha.t, f = gap >= 0 ? 0 : 1, h = first[f];
      if (Math.abs(gap) <= window) return ['Double hit', `${N[f]} hit ${h.part} first (${h.severity}), but ${N[1 - f]} answered ${Math.abs(gap).toFixed(0)} ms later, inside the ${window} ms double-hit window.`];
      return [`${N[f]} wins (afterblow too late)`, `${N[f]} hit ${h.part} (${h.severity}) ${Math.abs(gap).toFixed(0)} ms before ${N[1 - f]}'s answer.`];
    }
    const w = ha ? 0 : 1, h = first[w];
    return [`${N[w]} wins clean`, `${N[w]} hit the ${h.part} (${h.severity}) at ${h.t.toFixed(0)} ms; ${N[1 - w]} never landed.`];
  }

  // ------------------------------------------------------------ plausibility
  /** Flags for one action. `measured` = {timingKey: {median, label}}. */
  function checkAction(ex, f, actId, measured) {
    const L = layout(ex, f), a = L.acts.find(x => x.id === actId);
    if (!a) return [];
    const W = WEAPONS[ex.fencers[f].weapon] || WEAPONS.longsword, BD = bodyOf(ex.fencers[f].body);
    const out = [], dur = a.t1 - a.t0;
    let vHand = 0, vTip = 0, prev = null, strained = 0, n = 0; const joints = new Set();
    const hint = { reuse: true };
    for (let t = a.t0; t <= a.t1; t += 4) {
      const p = poseAt(ex, L, t, null);
      const sk = skeleton(p.pose, W, p.lift, BD, hint);
      n++; const vv = sk.armViol.filter((x, i) => i === 0 || p.pose.left_on);
      if (vv.some(x => x.total > 0.05)) { strained++; for (const x of vv) for (const j of ['shoulder', 'rotation', 'elbow', 'wrist', 'body']) if (x[j] > 0.05) joints.add(j); }
      if (prev) { vHand = Math.max(vHand, len(sub(sk.hand_r, prev.hand_r)) / 0.004); vTip = Math.max(vTip, len(sub(sk.tip, prev.tip)) / 0.004); }
      prev = sk;
    }
    const s = a.strength == null ? 0.5 : a.strength;
    if (vTip > 30) out.push({ level: 'bad', text: `Tip speed ${vTip.toFixed(0)} m/s. Fast cuts measure about 15–25 m/s at the tip.` });
    else if (vTip > 24) out.push({ level: 'warn', text: `Tip speed ${vTip.toFixed(0)} m/s, at the very top of what people manage.` });
    if (vHand > 11) out.push({ level: 'bad', text: `Hands move at ${vHand.toFixed(1)} m/s. Above ~10 m/s isn't humanly plausible.` });
    if (strained / Math.max(n, 1) > 0.2) out.push({ level: 'warn', text: `For ${Math.round(100 * strained / n)}% of this action the arms are outside their range of motion (${[...joints].join(', ')}). Re-pose the in-between keys or capture the move from video.` });
    if (s > 0.66 && dur < 220 && a.attack) out.push({ level: 'warn', text: `A strong blow in ${dur.toFixed(0)} ms: strong cuts need body mechanics and rarely take under ~250 ms.` });
    if (a.measure && measured && measured[a.measure]) {
      const m = measured[a.measure];
      if (dur < m.median * 0.85) out.push({ level: 'bad', text: `${dur.toFixed(0)} ms is faster than your own measured ${m.label} (${m.median.toFixed(0)} ms).` });
      else out.push({ level: 'ok', text: `Your measured ${m.label}: ${m.median.toFixed(0)} ms, this action ${dur.toFixed(0)} ms.` });
    }
    out.unshift({ level: 'info', text: `${dur.toFixed(0)} ms (${(dur / ex.beat_ms).toFixed(2)} beats) · peak tip ${vTip.toFixed(1)} m/s · hands ${vHand.toFixed(1)} m/s` });
    return out;
  }

  return { DIMS, BODIES, bodyOf, WEAPONS, repairPose, bodyObstacles, armAngles, armViolation, maxElev, ROM, DEFAULT_POSE, HITBOXES, strengthLabel, paceLabel,
    bladeDir, lerpPose, clonePose, skeleton, skeletonWorld, toWorld, toLocal, maxPelvisY,
    layout, realToBase, poseAt, actionAt, simulate, checkAction, segSeg, crossEnds, origins,
    vec: { add, sub, mul, dot, cross, len, norm, slerp, rotY } };
});
