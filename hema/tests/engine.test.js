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

test('Zwerch catches the Oberhau on the cross and hits', () => {
  const r = H.simulate(exOf('seed-zwerch'));
  assert.ok(r.events.some(e => e.kind === 'displace' && e.by === 1));
  assert.strictEqual(r.verdict, 'B wins clean');
  const disp = r.events.find(e => e.kind === 'displace');
  assert.ok(!r.events.some(e => e.kind === 'hit' && e.by === 0 && e.t > disp.t), 'displaced action cannot score');
});

test('a slow Zwerch fails', () => {
  const ex = exOf('seed-zwerch'); act(ex, 1, 'Zwerch').pace = 1.4;
  assert.notStrictEqual(H.simulate(ex).verdict, 'B wins clean');
});

test('strength decides the bind: a weak Zwerch no longer displaces a strong Oberhau', () => {
  const ex = exOf('seed-zwerch');
  act(ex, 1, 'Zwerch').strength = 0.0; act(ex, 0, 'Oberhau').strength = 1.0;
  const r = H.simulate(ex);
  assert.ok(!r.events.some(e => e.kind === 'displace' && e.by === 1));
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
