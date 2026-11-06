// Engine tests. Run through pytest (tests/test_hema.py), which writes the
// seed library to HEMA_SEEDS; or: HEMA_SEEDS=lib.json node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const H = require('../hemaviz/studio/engine.js');
const lib = require(process.env.HEMA_SEEDS);
const clone = o => JSON.parse(JSON.stringify(o));
const exOf = id => clone(lib.exchanges.find(e => e.id === id));
const act = (ex, f, name) => ex.actions.find(a => a.fencer === f && a.name.startsWith(name));

test('IK keeps bone lengths and both feet on the ground', () => {
  const D = H.DIMS, V = H.vec;
  const pose = clone(lib.exchanges[0].tracks[0].keys[0].pose);
  pose.hip[1] = 1.2;   // asked to stand impossibly tall
  const sk = H.skeleton(pose, H.WEAPONS.longsword);
  assert.ok(Math.abs(V.len(V.sub(sk.el_r, sk.sh_r)) - D.upper) < 1e-6);
  assert.ok(Math.abs(V.len(V.sub(sk.wr_r, sk.el_r)) - D.fore) < 1e-3);
  assert.ok(Math.abs(V.len(V.sub(sk.kn_l, sk.hp_l)) - D.thigh) < 1e-6);
  assert.ok(Math.abs(V.len(V.sub(sk.an_l, sk.kn_l)) - D.shin) < 2e-3, 'shin reaches the ankle');
  assert.ok(sk.pelvis[1] < 1.2, 'pelvis lowered so the legs do not stretch');
});

test('pace stretches an action and moves everything after it', () => {
  const ex = exOf('seed-mutual');
  const before = H.layout(ex, 0);
  act(ex, 0, 'Oberhau').pace = 0.5;
  const after = H.layout(ex, 0);
  const a0 = before.acts.find(a => a.name === 'Oberhau'), a1 = after.acts.find(a => a.name === 'Oberhau');
  assert.ok(Math.abs((a1.t1 - a1.t0) - (a0.t1 - a0.t0) / 2) < 1);
  const n = before.real.length - 1;
  assert.ok(Math.abs((before.real[n] - after.real[n]) - (a0.t1 - a0.t0) / 2) < 1);
});

test('mutual Zornhau: the longsword reaches the head first', () => {
  const r = H.simulate(exOf('seed-mutual'));
  assert.ok(r.first[0] && r.first[0].part === 'head');
  assert.ok(!r.first[1] || r.first[1].t > r.first[0].t);
});

test('a displaced action can never score afterwards', () => {
  let seen = 0;
  for (const e0 of lib.exchanges) {
    const ex = clone(e0), r = H.simulate(ex);
    for (const d of r.events.filter(e => e.kind === 'displace')) {
      seen++;
      const L = H.layout(ex, d.on), a = H.actionAt(L, d.t);
      assert.ok(!r.events.some(e => e.kind === 'hit' && e.by === d.on && e.t > d.t && e.t < a.t1),
        `${ex.id}: ${'AB'[d.on]} scored with a displaced action`);
    }
  }
  assert.ok(seen > 0, 'the examples contain displacements');
});

test('timing decides: a slower Zornhau against the thrust changes the result', () => {
  const ex = exOf('seed-thrust'), base = H.simulate(ex).verdict;
  act(ex, 1, 'Zornhau').pace = 1.4;
  assert.notStrictEqual(H.simulate(ex).verdict, base);
});

test('strength decides the bind: swapping strengths swaps who is displaced', () => {
  const ex = exOf('seed-mutual'), r = H.simulate(ex), d = r.events.find(e => e.kind === 'displace');
  assert.ok(d, 'the mutual Zornhau ends in a bind with a displacement');
  const aw = H.actionAt(H.layout(ex, d.by), d.t), al = H.actionAt(H.layout(ex, d.on), d.t);
  ex.actions.find(a => a.id === aw.id).strength = 0; ex.actions.find(a => a.id === al.id).strength = 1;
  const d2 = H.simulate(ex).events.find(e => e.kind === 'displace' && Math.abs(e.t - d.t) < 30);
  assert.ok(d2 && d2.by === d.on, 'the stronger blade now wins the bind');
});

test('Nachreisen hits the rising hands first', () => {
  const r = H.simulate(exOf('seed-nachreisen'));
  assert.ok(r.first[1] && /hand|forearm/.test(r.first[1].part));
  assert.ok(!r.first[0] || r.first[0].t > r.first[1].t);
});

test('plausibility flags an impossibly fast strong cut', () => {
  const ex = exOf('seed-mutual'); const a = act(ex, 0, 'Oberhau');
  a.pace = 0.4; a.strength = 1;
  const flags = H.checkAction(ex, 0, a.id, {});
  assert.ok(flags.some(f => f.level === 'bad' || f.level === 'warn'), JSON.stringify(flags));
  const ok = H.checkAction(exOf('seed-mutual'), 0, a.id, {});
  assert.ok(!ok.some(f => f.level === 'bad'), JSON.stringify(ok));
});

test('measured times flag actions faster than you have done them', () => {
  const ex = exOf('seed-mutual'); const a = act(ex, 0, 'Oberhau');
  const flags = H.checkAction(ex, 0, a.id, { [a.measure]: { median: 500, label: 'Oberhau' } });
  assert.ok(flags.some(f => f.level === 'bad'));
});

test('arms stay anatomical: wrists in range, elbows outside the body', () => {
  const V = H.vec, deg = x => x * 180 / Math.PI;
  let frames = 0, wristOk = 0;
  for (const ex of lib.exchanges) for (const f of [0, 1]) {
    const L = H.layout(ex, f), W = H.WEAPONS[ex.fencers[f].weapon], B = H.bodyOf(ex.fencers[f].body), hint = {};
    for (let t = 0; t <= L.real[L.real.length - 1]; t += 10) {
      const p = H.poseAt(ex, L, t, null), sk = H.skeleton(p.pose, W, p.lift, B, hint);
      for (const [sd, side] of [['r', 1], ['l', -1]]) {
        const v = V.norm(V.sub(sk['wr_' + sd], sk['el_' + sd])), F = sk['hF_' + sd], K = sk['hK_' + sd], P = V.mul(V.cross(F, K), side);
        const flex = deg(Math.atan2(V.dot(v, P), V.dot(v, F))), dev = deg(Math.atan2(V.dot(v, K), V.dot(v, F)));
        frames++; if (Math.abs(flex) <= 75 && Math.abs(dev) <= 45) wristOk++;
        const a = sk.pelvis, ab = V.sub(sk.chest, a);
        let u = V.dot(V.sub(sk['el_' + sd], a), ab) / V.dot(ab, ab); u = Math.max(0, Math.min(1, u));
        const dist = V.len(V.sub(sk['el_' + sd], V.add(a, V.mul(ab, u))));
        assert.ok(dist > 0.13, `${ex.id} ${'AB'[f]} ${sd} elbow inside the torso at ${t} ms (${dist.toFixed(2)} m from its axis)`);
      }
    }
  }
  assert.ok(wristOk / frames > 0.9, `only ${(100 * wristOk / frames).toFixed(0)}% of frames have the wrists in range`);
});

test('arms go around the head and the hilt stays out of the body', () => {
  const V = H.vec;
  for (const ex of lib.exchanges) for (const f of [0, 1]) {
    const L = H.layout(ex, f), W = H.WEAPONS[ex.fencers[f].weapon], B = H.bodyOf(ex.fencers[f].body), hint = {};
    for (let t = 0; t <= L.real[L.real.length - 1]; t += 10) {
      const p = H.poseAt(ex, L, t, null), sk = H.skeleton(p.pose, W, p.lift, B, hint);
      for (const sd of ['r', 'l']) {
        const dF = H.segSeg(sk.head, sk.head, sk['el_' + sd], sk['wr_' + sd])[0], dU = H.segSeg(sk.head, sk.head, sk['sh_' + sd], sk['el_' + sd])[0];
        assert.ok(Math.min(dF, dU) > 0.13, `${ex.id} ${'AB'[f]} ${sd} arm through the head at ${t} ms`);
      }
      const dH = H.segSeg(sk.hand_l, sk.hand_r, sk.pelvis, sk.chest)[0];
      assert.ok(dH > 0.15, `${ex.id} ${'AB'[f]} hilt inside the body at ${t} ms`);
    }
  }
});

test('every example key is held within the joints\' range of motion (after repair)', () => {
  for (const ex of lib.exchanges) for (const f of [0, 1]) {
    const W = H.WEAPONS[ex.fencers[f].weapon], B = H.bodyOf(ex.fencers[f].body);
    for (const k of ex.tracks[f].keys) {
      const p = H.repairPose(k.pose, W, B), sk = H.skeleton(p, W, null, B);
      const v = sk.armViol[0].total + (p.left_on ? sk.armViol[1].total : 0);
      assert.ok(v <= 0.05, `${ex.id} ${'AB'[f]} key ${k.id} still outside range (${v.toFixed(2)})`);
    }
  }
});
