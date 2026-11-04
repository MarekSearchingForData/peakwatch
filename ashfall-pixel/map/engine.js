// Ashfall isometric pixel engine.
// Draws a data-driven world (see world.js) as an isometric pixel-art diorama
// on a low-resolution canvas, then scales it up with nearest-neighbour so
// every pixel stays crisp. No build step, no dependencies.
(function () {
  'use strict';

  // ---------- palette (dark fantasy: moss, ember, ash, old stone) ----------
  const P = {
    ink: '#0e0b12', night: '#141019', night2: '#1d1724',
    deep: '#16243a', water: '#22405a', waterL: '#3a6a84', foam: '#9cc4cc',
    red0: '#4a141c', red1: '#7e2229', red2: '#b8423a', red3: '#ef7a5a',
    sand: '#b49868', sandD: '#86704c',
    g0: '#15291c', g1: '#1f3a26', g2: '#2d5432', g3: '#3f6e3a', g4: '#6a9a48', g5: '#a2c45e',
    a0: '#4a1c14', a1: '#7a2e1c', a2: '#b4471f', a3: '#e0762b', a4: '#f4ae4c',
    ash0: '#2a2629', ash1: '#3d3638', ash2: '#5d5352', ash3: '#857873', ash4: '#b3a69c',
    s0: '#2c3036', s1: '#454b53', s2: '#646c74', s3: '#8f979e', s4: '#c3c9cb',
    sn0: '#8796a4', sn1: '#b8c6d0', sn2: '#e6eef2',
    w0: '#2e1c12', w1: '#5a3820', w2: '#8a5c34', w3: '#b88850',
    soil0: '#1e1410', soil1: '#33221a', soil2: '#4a3324',
    e0: '#fff0a0', e1: '#ffc94a', e2: '#ff8a2a', e3: '#d8401e',
    v0: '#24133c', v1: '#4d2680', v2: '#8a4fd0', v3: '#d6a4ff',
    gold: '#d9b350', bone: '#e9dfc4', roofR: '#7c2d24', roofR2: '#a8432f',
    roofB: '#2f3b52', roofB2: '#46587a', marsh: '#3a4a2c', marsh2: '#55663a',
  };

  // ---------- geometry ----------
  const TW = 16, TH = 8, HALF = 8, HZ = 4, BASE = 12; // tile width/height, step height, slab depth

  // ---------- deterministic noise ----------
  function hash(x, y, s) {
    let h = (x * 374761393 + y * 668265263 + (s | 0) * 2147483647) | 0;
    h = (h ^ (h >>> 13)) * 1274126177 | 0;
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }
  function vnoise(x, y, s) {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  }
  function fbm(x, y, s) { return vnoise(x, y, s) * 0.55 + vnoise(x * 2.1, y * 2.1, s + 7) * 0.3 + vnoise(x * 4.3, y * 4.3, s + 13) * 0.15; }

  // ---------- terrain catalogue ----------
  // top: [base, alt, light, dark], side: [left, right]
  const TERRAIN = {
    deep:   { top: [P.deep, P.water, P.waterL, P.ink], side: [P.ink, P.deep], water: true },
    water:  { top: [P.water, P.waterL, P.foam, P.deep], side: [P.deep, P.water], water: true },
    blood:  { top: [P.red1, P.red0, P.red3, P.red0], side: [P.red0, P.red1], water: true },
    sand:   { top: [P.sand, P.sandD, '#d0b888', P.sandD], side: [P.soil1, P.soil2] },
    grass:  { top: [P.g3, P.g2, P.g4, P.g1], side: [P.g1, P.g2] },
    meadow: { top: [P.g4, P.g3, P.g5, P.g2], side: [P.g2, P.g3] },
    forest: { top: [P.g2, P.g1, P.g3, P.g0], side: [P.g0, P.g1] },
    autumn: { top: [P.g3, P.a1, P.a3, P.g1], side: [P.g1, P.a0] },
    marsh:  { top: [P.marsh, P.g1, P.marsh2, P.water], side: [P.soil1, P.marsh] },
    ash:    { top: [P.ash2, P.ash1, P.ash3, P.ash0], side: [P.ash0, P.ash1] },
    cinder: { top: [P.ash1, P.ash0, P.e3, P.ash0], side: [P.ash0, P.soil1] },
    stone:  { top: [P.s2, P.s1, P.s3, P.s0], side: [P.s0, P.s1] },
    snow:   { top: [P.sn1, P.sn0, P.sn2, P.s2], side: [P.s1, P.s2] },
    road:   { top: [P.w2, P.w1, P.w3, P.w1], side: [P.soil1, P.soil2] },
    plaza:  { top: [P.s3, P.s2, P.s4, P.s1], side: [P.s0, P.s1] },
    street: { top: ['#6e6258', '#5a4f47', '#8a7d70', '#463c36'], side: [P.soil1, P.soil2] },
    flax:   { top: ['#4f7a52', '#6c8fb0', '#7fa070', '#2d5432'], side: [P.soil1, P.soil2], rows: true },
    vines:  { top: ['#3f6e3a', '#5a2a4a', '#6a9a48', '#2d3a1e'], side: [P.soil1, P.soil2], rows: true },
    wheat:  { top: ['#b89a48', '#8a7a34', '#d8c070', '#6a5a2a'], side: [P.soil1, P.soil2], rows: true },
  };

  // ---------- sprite helper: ascii pixel maps ----------
  function sprite(rows, map) {
    const w = Math.max(...rows.map(r => r.length));
    return { w, h: rows.length, rows: rows.map(r => r.padEnd(w, '.')), map };
  }
  function drawSprite(ctx, sp, x, y, override) {
    // x,y = bottom-centre anchor
    const map = override ? Object.assign({}, sp.map, override) : sp.map;
    const ox = Math.round(x - sp.w / 2), oy = Math.round(y - sp.h);
    for (let r = 0; r < sp.h; r++) {
      const row = sp.rows[r];
      for (let c = 0; c < sp.w; c++) {
        const ch = row[c];
        if (ch === '.' || ch === ' ') continue;
        const col = map[ch]; if (!col) continue;
        ctx.fillStyle = col; ctx.fillRect(ox + c, oy + r, 1, 1);
      }
    }
  }

  const SPR = {
    pine: sprite([
      '....d....', '...dgd...', '...dGd...', '..dggGd..', '...dgd...', '..dgGgd..',
      '.dggggGd.', '..dgggd..', '.dgggGgd.', 'dggggggGd', '.ddddddd.', '....t....', '....t....'],
      { d: P.g0, g: P.g1, G: P.g3, t: P.w0 }),
    round: sprite([
      '...dddd....', '..dgGGgd...', '.dgGGgggd..', 'dgGgggggGd.', 'dggggGggggd', 'dgggggggGgd',
      '.dggggggggd', '..ddggggdd.', '....dtd....', '.....t.....', '.....t.....'],
      { d: P.g1, g: P.g2, G: P.g4, t: P.w0 }),
    dead: sprite([
      'd...d..d', '.d..d.d.', '..d.dd..', 'd..dd...', '.d.dd..d', '..ddd.d.', '...dd...', '...dd...', '..dddd..'],
      { d: P.ash0 }),
    bush: sprite(['.dgd.', 'dgGgd', '.ddd.'], { d: P.g1, g: P.g2, G: P.g4 }),
    rock: sprite(['.lll.', 'lsssd', 'sssdd'], { l: P.s3, s: P.s2, d: P.s1 }),
    reed: sprite(['g.g', 'g.g', '.gg', '.g.'], { g: P.marsh2 }),
    stump: sprite(['wWw', 'www'], { w: P.w1, W: P.w3 }),
    kethA: sprite([
      '..h..', '.hfh.', '..c..', '.cCc.', 'ccCcs', '.cCc.', '.c.c.', '.b..b'],
      { h: P.ink, f: '#d9a77c', c: '#3b2a3a', C: '#5e3a4a', s: P.s4, b: P.w0 }),
    kethB: sprite([
      '..h..', '.hfh.', '..c..', '.cCc.', 'ccCcs', '.cCc.', '..cc.', '..bb.'],
      { h: P.ink, f: '#d9a77c', c: '#3b2a3a', C: '#5e3a4a', s: P.s4, b: P.w0 }),
    tent: sprite([
      '.....b.....', '....bBb....', '...bBBBb...', '..bBBdBBb..', '.bBBBddBBb.', 'bBBBBddBBBb'],
      { b: '#a88a52', B: '#d8bf7c', d: P.w0 }),
    banner: sprite(['p', 'pr', 'prr', 'pr', 'p', 'p', 'p'], { p: P.w0, r: P.roofR2 }),
  };

  // ---------- fast pixel buffer with a tiny canvas-like API ----------
  const colourCache = new Map();
  function rgba(hex) {
    let v = colourCache.get(hex);
    if (v === undefined) {
      const n = parseInt(hex.slice(1, 7), 16);
      v = (0xff << 24) | ((n & 255) << 16) | (n & 0xff00) | (n >> 16);
      colourCache.set(hex, v >>> 0);
      v = v >>> 0;
    }
    return v;
  }
  function PixelBuf(w, h) {
    this.w = w; this.h = h; this.img = new ImageData(w, h);
    this.px = new Uint32Array(this.img.data.buffer); this._c = 0;
  }
  Object.defineProperty(PixelBuf.prototype, 'fillStyle', { set(c) { this._c = rgba(c); }, get() { return ''; } });
  PixelBuf.prototype.blit = function (src, sw, sh, dx, dy) {  // RGBA pixels, alpha-tested
    const px = this.px, W = this.w, H = this.h, s32 = new Uint32Array(src.buffer);
    dx = Math.round(dx); dy = Math.round(dy);
    for (let y = 0; y < sh; y++) {
      const ty = y + dy; if (ty < 0 || ty >= H) continue;
      for (let x = 0; x < sw; x++) {
        const tx = x + dx; if (tx < 0 || tx >= W) continue;
        const v = s32[y * sw + x]; if ((v >>> 24) < 128) continue;
        px[ty * W + tx] = v | 0xff000000;
      }
    }
  };
  PixelBuf.prototype.fillRect = function (x, y, w, h) {
    x |= 0; y |= 0;
    const x1 = Math.min(this.w, x + w), y1 = Math.min(this.h, y + h), c = this._c, px = this.px, W = this.w;
    for (let yy = Math.max(0, y); yy < y1; yy++) for (let xx = Math.max(0, x); xx < x1; xx++) px[yy * W + xx] = c;
  };

  // ---------- column rasteriser (the heart of crisp iso pixels) ----------
  // Fills an iso diamond of half-width a centred at (cx,cy), optional vertical
  // extrusion `depth` below it. colFn(u, isLeft, part, px, py) -> colour.
  function isoPrism(ctx, cx, cy, a, depth, colFn) {
    for (let x = cx - a; x < cx + a; x++) {
      const u = x - cx + 0.5, left = u < 0;
      const span = (a - Math.abs(u)) / 2;
      const yt = Math.round(cy - span), yb = Math.round(cy + span);
      for (let y = yt; y < yb; y++) { ctx.fillStyle = colFn(u, left, 'top', x, y, y - yt, yb - y); ctx.fillRect(x, y, 1, 1); }
      for (let y = yb; y < yb + depth; y++) { ctx.fillStyle = colFn(u, left, 'side', x, y, y - yb, depth); ctx.fillRect(x, y, 1, 1); }
    }
  }

  // Box building: footprint half-width a, wall height hgt, sitting on ground (cx,gy)
  function box(ctx, cx, gy, a, hgt, cL, cR, cTop) {
    isoPrism(ctx, cx, gy - hgt, a, hgt, (u, left, part, x, y, d) => {
      if (part === 'top') return cTop;
      if (d === 0 && part === 'side') return left ? shade(cL, 0.15) : shade(cR, 0.15);
      return left ? cL : cR;
    });
  }
  function roof(ctx, cx, gy, a, cL, cR, peak) {
    // stacked shrinking diamonds -> hip roof
    const steps = peak || a;
    for (let k = 0; k <= steps; k++) {
      const aa = a + 1 - Math.round(k * (a + 1) / (steps + 1));
      if (aa <= 0) break;
      isoPrism(ctx, cx, gy - k, aa, 0, (u, left) => left ? cL : cR);
    }
  }
  function shade(hex, amt) {
    const n = parseInt(hex.slice(1), 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const f = amt >= 0 ? (c) => Math.round(c + (255 - c) * amt) : (c) => Math.round(c * (1 + amt));
    return '#' + ((1 << 24) | (f(r) << 16) | (f(g) << 8) | f(b)).toString(16).slice(1);
  }

  // ---------- building kits ----------
  function house(ctx, cx, gy, seed, opts) {
    const a = 4 + (seed > 0.6 ? 1 : 0), h = 5 + Math.round(seed * 2);
    const wall = opts && opts.wall || (seed > 0.5 ? P.bone : '#c8b08a');
    box(ctx, cx, gy, a, h, shade(wall, -0.35), wall, wall);
    const rf = opts && opts.roof || (seed > 0.4 ? [P.roofR, P.roofR2] : [P.w1, P.w2]);
    roof(ctx, cx, gy - h, a, rf[0], rf[1], a + 1);
    // door + window
    ctx.fillStyle = P.w0; ctx.fillRect(cx + 2, gy - 3 + 1, 1, 2);
    ctx.fillStyle = P.e1; ctx.fillRect(cx - 3, gy - h + 2, 1, 1);
  }
  function tower(ctx, cx, gy, a, h, stone, roofCols) {
    box(ctx, cx, gy, a, h, shade(stone, -0.3), stone, shade(stone, 0.15));
    if (roofCols) roof(ctx, cx, gy - h, a, roofCols[0], roofCols[1], a * 2 + 2);
    else { // crenellations
      ctx.fillStyle = shade(stone, 0.2);
      for (let i = -a; i < a; i += 2) ctx.fillRect(cx + i, gy - h - a / 2 - 1, 1, 1);
    }
    ctx.fillStyle = P.ink; ctx.fillRect(cx + 1, gy - Math.round(h * 0.6), 1, 2);
  }
  function wallSeg(ctx, cx, gy, stone) { box(ctx, cx, gy, 3, 5, shade(stone, -0.3), stone, shade(stone, 0.2)); }

  const KITS = {
    city(ctx, cx, gy, pl) {
      const s = pl.stone || P.s3;
      for (const [dx, dy] of [[-12, 0], [12, 0], [0, -6], [0, 6]]) tower(ctx, cx + dx, gy + dy - 6 + 6, 3, 12, s, null);
      for (let i = -9; i <= 9; i += 3) { wallSeg(ctx, cx + i, gy - 6 + Math.abs(i) / 2 + 0, s); }
      house(ctx, cx - 5, gy - 2, 0.7); house(ctx, cx + 5, gy - 1, 0.3);
      tower(ctx, cx, gy - 1, 4, 18, s, pl.roof || [P.roofB, P.roofB2]);
      for (let i = -9; i <= 9; i += 3) { wallSeg(ctx, cx + i, gy + 6 - Math.abs(i) / 2, s); }
      drawSprite(ctx, SPR.banner, cx + 1, gy - 26);
    },
    town(ctx, cx, gy, pl) {
      const pts = [[-7, -2], [5, -4], [-1, 1], [8, 2], [-8, 4], [2, 6]];
      pts.forEach(([dx, dy], i) => house(ctx, cx + dx, gy + dy, hash(i, pl.x, 3), pl.houses));
    },
    village(ctx, cx, gy, pl) {
      [[-5, 0], [4, -2], [1, 4]].forEach(([dx, dy], i) => house(ctx, cx + dx, gy + dy, hash(i, pl.y, 9), pl.houses));
    },
    church(ctx, cx, gy, pl) {
      box(ctx, cx - 2, gy + 1, 6, 8, shade(P.bone, -0.3), P.bone, P.bone);
      roof(ctx, cx - 2, gy - 7, 6, P.s1, P.s2, 7);
      tower(ctx, cx + 5, gy - 2, 3, 16, P.bone, [P.s1, P.s3]);
      ctx.fillStyle = P.gold; ctx.fillRect(cx + 5, gy - 27, 1, 3); ctx.fillRect(cx + 4, gy - 26, 3, 1);
    },
    ruin(ctx, cx, gy, pl) {
      const s = P.s2;
      box(ctx, cx - 6, gy + 1, 2, 9, P.s1, s, P.s3);
      box(ctx, cx + 4, gy - 3, 2, 12, P.s1, s, P.s3);
      box(ctx, cx - 1, gy - 9, 6, 3, P.s1, s, P.s3); // lintel
      ctx.fillStyle = P.ink; ctx.fillRect(cx - 3, gy - 6, 5, 6);
      box(ctx, cx + 7, gy + 4, 2, 3, P.s1, s, P.s3);
      drawSprite(ctx, SPR.rock, cx - 8, gy + 6);
      ctx.fillStyle = P.g3; ctx.fillRect(cx - 6, gy - 9, 2, 1); ctx.fillRect(cx + 3, gy - 15, 3, 1);
    },
    fountain(ctx, cx, gy) {
      box(ctx, cx, gy, 5, 3, P.s2, P.s3, P.s4);
      isoPrism(ctx, cx, gy - 3, 4, 0, () => P.waterL);
      ctx.fillStyle = P.s3; ctx.fillRect(cx, gy - 9, 1, 6); ctx.fillStyle = P.foam; ctx.fillRect(cx - 1, gy - 10, 3, 1);
    },
    well(ctx, cx, gy) {
      box(ctx, cx, gy, 4, 3, P.s1, P.s2, P.s3);
      isoPrism(ctx, cx, gy - 3, 2, 0, () => P.red1);
      ctx.fillStyle = P.w1; ctx.fillRect(cx - 4, gy - 10, 1, 8); ctx.fillRect(cx + 3, gy - 10, 1, 8);
      ctx.fillStyle = P.w2; ctx.fillRect(cx - 4, gy - 11, 8, 1);
    },
    mill(ctx, cx, gy, pl) {
      box(ctx, cx, gy, 5, 9, shade(P.w2, -0.3), P.w2, P.w3);
      roof(ctx, cx, gy - 9, 5, P.w0, P.w1, 6);
    },
    tavern(ctx, cx, gy, pl) {
      house(ctx, cx, gy, 0.9, { wall: '#b89a70', roof: [P.w0, P.w1] });
      ctx.fillStyle = P.w2; ctx.fillRect(cx + 6, gy - 8, 1, 6); ctx.fillStyle = P.gold; ctx.fillRect(cx + 6, gy - 8, 3, 2);
    },
    orphanage(ctx, cx, gy) {
      box(ctx, cx, gy, 6, 8, shade('#a89272', -0.3), '#a89272', '#a89272');
      roof(ctx, cx, gy - 8, 6, P.s1, P.s2, 6);
      ctx.fillStyle = P.e1; [-4, -2, 2, 4].forEach(dx => ctx.fillRect(cx + dx, gy - 4, 1, 1));
    },
    keep(ctx, cx, gy, pl) { tower(ctx, cx, gy, 5, 16, pl.stone || P.s2, pl.roof || null); house(ctx, cx + 8, gy + 3, 0.2); },
    vault(ctx, cx, gy, pl) {
      box(ctx, cx, gy, 7, 6, P.s0, P.s1, P.s2);
      box(ctx, cx, gy - 6, 5, 6, P.s0, P.s1, P.s2);
      box(ctx, cx, gy - 12, 3, 6, P.s0, P.s1, P.s2);
      ctx.fillStyle = P.v2; ctx.fillRect(cx, gy - 20, 1, 2);
    },
    camp(ctx, cx, gy) { drawSprite(ctx, SPR.tent, cx - 4, gy + 1); drawSprite(ctx, SPR.stump, cx + 6, gy + 3); },
    rift() {}, // fully animated, see drawAnimated
    gate(ctx, cx, gy, pl) {
      tower(ctx, cx - 7, gy, 3, 14, P.s2, null); tower(ctx, cx + 7, gy, 3, 14, P.s2, null);
      box(ctx, cx, gy - 9, 5, 3, P.s1, P.s2, P.s3);
    },
    battlefield(ctx, cx, gy) {
      for (let i = 0; i < 7; i++) { const dx = Math.round((hash(i, 1, 4) - 0.5) * 18), dy = Math.round((hash(i, 2, 4) - 0.5) * 8); ctx.fillStyle = P.w1; ctx.fillRect(cx + dx, gy + dy - 4, 1, 4); ctx.fillRect(cx + dx - 1, gy + dy - 3, 3, 1); }
    },
    bigtree(ctx, cx, gy, pl) {
      if (pl && pl.scale > 1) { const s2 = pl.scale; for (let i = -6; i <= 6; i++) { ctx.fillStyle = i < 0 ? P.w0 : P.w1; ctx.fillRect(cx + i, gy - 40, 1, 40 - Math.abs(i)); }
        const bl = [[0, -62, 22], [-18, -50, 15], [18, -52, 15], [-8, -74, 13], [11, -72, 13], [0, -46, 16]];
        for (const [bx, by, r] of bl) for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) { if (x * x + y * y * 1.6 > r * r) continue; const h = hash(cx + bx + x, gy + by + y, 8); const si = (y > r * 0.3) ? 0 : (x - y < -r * 0.6 ? 2 : 1); ctx.fillStyle = h < 0.05 ? P.gold : [P.g1, P.g2, P.g4][si]; ctx.fillRect(cx + bx + x, gy + by + y, 1, 1); }
        return; }
      // colossal baobab-like tree: fat trunk, roots, layered crown
      for (let i = -3; i <= 3; i++) { ctx.fillStyle = i < 0 ? P.w0 : P.w1; ctx.fillRect(cx + i, gy - 22, 1, 22 - Math.abs(i)); }
      ctx.fillStyle = P.w0; ctx.fillRect(cx - 7, gy - 1, 15, 1); ctx.fillRect(cx - 5, gy - 2, 11, 1);
      const blobs = [[0, -34, 11], [-9, -28, 8], [9, -29, 8], [-4, -40, 7], [6, -39, 7], [0, -26, 9]];
      for (const [bx, by, r] of blobs) for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) {
        if (x * x + y * y * 1.6 > r * r) continue;
        const h = hash(cx + bx + x, gy + by + y, 8);
        const shadeIdx = (y > r * 0.3) ? 0 : (x - y < -r * 0.6 ? 2 : 1);
        ctx.fillStyle = h < 0.06 ? P.gold : [P.g1, P.g2, P.g4][shadeIdx];
        ctx.fillRect(cx + bx + x, gy + by + y, 1, 1);
      }
    },
    marker(ctx, cx, gy) { ctx.fillStyle = P.s3; ctx.fillRect(cx, gy - 7, 2, 7); ctx.fillStyle = P.s4; ctx.fillRect(cx, gy - 7, 1, 1); },
  };

  // ---------- world generation ----------
  const ROOFS = {
    rowhouse: [['#7a6232', '#a08646'], ['#6a5428', '#8e7438'], ['#806838', '#a8904e'], ['#5e4a26', '#82683a']],
    house: [['#6a2a20', '#8e3a28'], ['#5a3a22', '#7a5230'], ['#4e3a2e', '#6e5444'], ['#6a2a20', '#8e3a28'], ['#7a5a30', '#9a7a44']],
    cottage: [['#7a6232', '#9a8246']], shack: [['#4a3a2a', '#625040']], barn: [['#5e2a1e', '#7e3a28']], farmhouse: [['#7a6232', '#9a8246']],
    church: [['#2c3036', '#454b53']], keep: [['#2f3b52', '#46587a']], hall: [['#3a4256', '#525c74']], manor: [['#3a4256', '#525c74']],
    warehouse: [['#3e2a1c', '#5a3e28']], mill: [['#3e2a1c', '#5a3e28']], tavern: [['#5a2a1e', '#7e3e28']],
  };
  const WALLS = { rowhouse: '#a0503a', church: P.bone, keep: '#9aa0a6', hall: '#c8b08a', manor: '#d8cbb0', tavern: '#b89a70', shack: '#7a6a58', barn: '#8a5c34' };
  function buildGrid(spec) {
    const g = spec.grid, W = g.w, H = g.h, tiles = new Array(W * H);
    const blds = {}; for (const b of g.buildings) blds[b.id] = b;
    const fieldT = g.fields === 'vines' ? 'vines' : g.fields === 'flax' ? 'flax' : 'wheat';
    for (let k = 0; k < W * H; k++) {
      const x = k % W, y = (k / W) | 0, c = g.cells[k];
      const tl = { x, y, h: 1, t: 'grass', prop: null, place: null, road: false };
      const n = hash(x, y, 31);
      switch (c) {
        case 'r': tl.t = 'street'; break;
        case 'p': tl.t = 'plaza'; break;
        case 'f': tl.t = fieldT; break;
        case 'F': tl.t = fieldT === 'wheat' ? 'meadow' : 'wheat'; break;
        case 'm': tl.t = 'meadow'; tl.prop = n < 0.25 ? 'round' : null; break;
        case '~': tl.t = 'water'; tl.h = 0; break;
        case 'w': tl.t = 'stone'; tl.raise = 7; tl.wall = true; break;
        case 'T': tl.t = 'stone'; tl.raise = 12; tl.wall = true; tl.tower = true; break;
        case 'W': tl.t = 'plaza'; tl.well = true; break;
        case 'U': tl.t = 'plaza'; tl.well = true; tl.fountain = true; break;
        case 'k': tl.t = 'forest'; tl.prop = n < 0.55 ? 'round' : n < 0.85 ? 'pine' : 'autumn'; break;
        case 'Y': tl.t = n < 0.5 ? 'meadow' : 'grass'; tl.prop = n < 0.04 ? 'bush' : null; break;
        case 'd': tl.t = 'road'; break;
        case 'b': {
          const b = blds[g.bid[k]];
          tl.t = 'street'; tl.bld = b; tl.raise = b.art ? 0 : b.h;   // buildings with finished art are drawn as sprites
          const pal = ROOFS[b.type] || ROOFS.house;
          const r = pal[b.id % pal.length];
          b.roof = b.roof || r; b.wallc = b.wallc || WALLS[b.type] || (b.id % 3 ? '#c8b08a' : P.bone);
          break;
        }
        default: tl.t = 'grass'; tl.prop = n < 0.035 ? 'round' : n < 0.05 ? 'bush' : n < 0.055 ? 'pine' : null;
      }
      if (g.hgt) tl.h = parseInt(g.hgt[k], 36);   // terrain height in levels (base 36: the church hill is tall)
      tiles[k] = tl;
    }
    const T = (x, y) => (x >= 0 && y >= 0 && x < W && y < H) ? tiles[y * W + x] : null;
    // gable roofs: ridge along each building's long axis, roof rises toward it
    const bb = {};
    for (const tl of tiles) if (tl.bld) {
      const r = bb[tl.bld.id] || (bb[tl.bld.id] = { x0: tl.x, x1: tl.x, y0: tl.y, y1: tl.y });
      r.x0 = Math.min(r.x0, tl.x); r.x1 = Math.max(r.x1, tl.x); r.y0 = Math.min(r.y0, tl.y); r.y1 = Math.max(r.y1, tl.y);
    }
    for (const tl of tiles) if (tl.bld) {
      const r = bb[tl.bld.id], alongX = (r.x1 - r.x0) >= (r.y1 - r.y0);
      const v = alongX ? tl.y : tl.x, c = alongX ? (r.y0 + r.y1) / 2 : (r.x0 + r.x1) / 2, half = (alongX ? r.y1 - r.y0 : r.x1 - r.x0) / 2 + 0.5;
      const d = Math.abs(v - c), slope = tl.bld.type === 'keep' ? 1.5 : 2.5;
      tl.roofLift = Math.min(12, Math.max(0, Math.round((half - d) * slope)));
      tl.roofSide = d < 0.5 ? 0 : (v < c ? -1 : 1);
      tl.wallH = tl.bld.h; tl.raise = tl.bld.h + tl.roofLift;
    }
    const byId = {};
    for (const pl of spec.places || []) { // snap each place onto the nearest open square tile
      byId[pl.id] = pl; let best = null, bd = 1e9;
      for (let dy = -12; dy <= 12; dy++) for (let dx = -12; dx <= 12; dx++) {
        const tl = T(pl.x + dx, pl.y + dy); if (!tl || tl.t !== 'plaza' || tl.well || tl.raise) continue;
        const d = dx * dx + dy * dy; if (d < bd) { bd = d; best = tl; }
      }
      if (best) { pl.x = best.x; pl.y = best.y; best.place = pl; }
    }
    return { W, H, tiles, T, byId, roads: [], spec, buildings: g.buildings, blds };
  }

  function buildWorld(spec) {
    if (spec.grid) return buildGrid(spec);
    const W = spec.w, H = spec.h, ns = spec.noise || 1;
    const tiles = [];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const n = fbm(x / (7 * ns), y / (7 * ns), spec.seed);
      const coast = spec.coast;
      let land = true;
      if (coast) {
        const dx = (x - coast.cx) / coast.rx, dy = (y - coast.cy) / coast.ry;
        land = Math.sqrt(dx * dx + dy * dy) + (fbm(x / (5 * ns), y / (5 * ns), spec.seed + 99) - 0.5) * 0.55 < 1;
      }
      let t = land ? (n > 0.62 ? 'meadow' : 'grass') : 'deep', h = land ? 1 + Math.round(n * 2) : 0;
      if (!land && n > 0.5) t = 'water';
      tiles.push({ x, y, t, h, prop: null, place: null, road: false });
    }
    const T = (x, y) => (x >= 0 && y >= 0 && x < W && y < H) ? tiles[y * W + x] : null;

    for (const r of spec.regions) {
      for (const tl of tiles) {
        const dx = (tl.x - r.cx) / r.rx, dy = (tl.y - r.cy) / r.ry;
        const d = Math.sqrt(dx * dx + dy * dy) + (fbm(tl.x / (4 * ns), tl.y / (4 * ns), spec.seed + Math.round(r.cx * 3 + r.cy)) - 0.5) * (r.wobble ?? 0.6);
        if (d >= 1) continue;
        if (!r.overSea && TERRAIN[tl.t].water && tl.t !== 'water') continue;
        tl.t = r.t;
        if (r.h != null) {
          const hn = fbm(tl.x / (3 * ns), tl.y / (3 * ns), spec.seed + 5);
          const lift = r.peak ? (1 - d) * r.peak : 0;
          tl.h = Math.round(r.h + hn * (r.hv || 0) + lift);
        }
        if (r.snowAbove != null && tl.h >= r.snowAbove) tl.t = 'snow';
        tl.region = r.name || tl.region;
      }
    }
    // rivers: polylines in grid space, carved to water level
    for (const rv of spec.rivers || []) {
      for (let i = 0; i < rv.pts.length - 1; i++) {
        const [x0, y0] = rv.pts[i], [x1, y1] = rv.pts[i + 1];
        const steps = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) * 2;
        for (let s = 0; s <= steps; s++) {
          const x = Math.round(x0 + (x1 - x0) * s / steps), y = Math.round(y0 + (y1 - y0) * s / steps);
          for (let w = 0; w < (rv.width || 1); w++) {
            const tl = T(x + w, y); if (!tl) continue;
            tl.t = rv.t || 'water'; tl.h = 0; tl.river = rv.name;
          }
        }
      }
    }
    // places flatten their ground
    const byId = {};
    for (const pl of spec.places) {
      byId[pl.id] = pl;
      const tl = T(pl.x, pl.y); if (!tl) continue;
      tl.place = pl;
      if (TERRAIN[tl.t].water && pl.kind !== 'rift') { tl.t = 'grass'; tl.h = 1; }
      if (pl.ground) tl.t = pl.ground;
      if (pl.kind === 'city' || pl.kind === 'town') for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const n = T(pl.x + dx, pl.y + dy); if (n && !TERRAIN[n.t].water) { n.h = tl.h; n.t = pl.ground || 'plaza'; n.occupied = true; }
      }
    }
    // roads: A* between named places
    const roads = [];
    for (const [a, b] of spec.roads || []) {
      const A = byId[a], B = byId[b]; if (!A || !B) continue;
      const path = astar(tiles, W, H, A, B);
      for (const tl of path) {
        if (TERRAIN[tl.t].water) tl.bridge = true;
        else if (!tl.place && !tl.occupied && tl.t !== 'snow') tl.t = 'road';
        tl.road = true;
      }
      roads.push({ a, b, path });
    }
    // scatter props
    for (const tl of tiles) {
      if (tl.place || tl.road || tl.occupied) continue;
      const r = hash(tl.x, tl.y, spec.seed + 21);
      const t = tl.t;
      if (t === 'forest') tl.prop = r < 0.85 ? (r < 0.5 ? 'pine' : 'round') : (r < 0.93 ? 'bush' : null);
      else if (t === 'autumn') tl.prop = r < 0.8 ? 'autumn' : (r < 0.9 ? 'bush' : null);
      else if (t === 'grass' || t === 'meadow') tl.prop = r < 0.06 ? 'round' : r < 0.12 ? 'bush' : r < 0.15 ? 'rock' : null;
      else if (t === 'ash') tl.prop = r < 0.2 ? 'dead' : r < 0.26 ? 'rock' : null;
      else if (t === 'cinder') tl.prop = r < 0.1 ? 'dead' : null;
      else if (t === 'snow') tl.prop = r < 0.35 ? 'snowpine' : r < 0.42 ? 'rock' : null;
      else if (t === 'stone') tl.prop = r < 0.25 ? 'rock' : r < 0.3 ? 'pine' : null;
      else if (t === 'marsh') tl.prop = r < 0.4 ? 'reed' : r < 0.5 ? 'dead' : null;
    }
    return { W, H, tiles, T, byId, roads, spec };
  }

  function astar(tiles, W, H, A, B) {
    const key = (x, y) => y * W + x;
    const cost = (tl) => {
      if (!tl) return Infinity;
      if (tl.road) return 0.4;
      const tr = TERRAIN[tl.t];
      if (tl.t === 'deep') return 60;
      if (tr.water) return 9;
      if (tl.t === 'snow') return 5; if (tl.t === 'stone') return 3.5;
      if (tl.t === 'forest' || tl.t === 'autumn' || tl.t === 'marsh') return 2.2;
      return 1 + tl.h * 0.2;
    };
    const open = new Map(), g = new Map(), from = new Map();
    const s = key(A.x, A.y), goal = key(B.x, B.y);
    g.set(s, 0); open.set(s, Math.abs(A.x - B.x) + Math.abs(A.y - B.y));
    while (open.size) {
      let cur = null, best = Infinity;
      for (const [k, f] of open) if (f < best) { best = f; cur = k; }
      if (cur === goal) break;
      open.delete(cur);
      const cx = cur % W, cy = (cur / W) | 0;
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nx = cx + dx, ny = cy + dy; if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
        const nk = key(nx, ny), tl = tiles[nk];
        const step = (tiles[nk].place && nk !== goal) ? 3 : cost(tl);
        const ng = g.get(cur) + step + Math.abs(tl.h - tiles[cur].h) * 0.6;
        if (ng < (g.has(nk) ? g.get(nk) : Infinity)) {
          g.set(nk, ng); from.set(nk, cur); open.set(nk, ng + Math.abs(nx - B.x) + Math.abs(ny - B.y));
        }
      }
    }
    const out = []; let k = goal;
    while (k !== undefined) { out.push(tiles[k]); k = from.get(k); }
    return out.reverse();
  }

  // ---------- projection ----------
  function makeView(world) {
    const { W, H } = world;
    const maxH = Math.max(...world.tiles.map(t => t.h));
    const pad = 40;
    const ox = H * HALF + pad, oy = maxH * HZ + pad + 30;
    const width = (W + H) * HALF + pad * 2, height = (W + H) * (TH / 2) + maxH * HZ + BASE + pad * 2 + 40;
    const proj = (x, y, h) => [ox + (x - y) * HALF, oy + (x + y) * (TH / 2) - h * HZ];
    return { width, height, proj, maxH };
  }

  // ---------- static layer ----------
  function drawStatic(ctx, world, view) {
    const { tiles, W, H } = world;
    ctx.fillStyle = P.night; ctx.fillRect(0, 0, view.width, view.height);
    const order = tiles.slice().sort((a, b) => (a.x + a.y) - (b.x + b.y) || a.x - b.x);
    // finished art fitted onto layout slots: drawn right after the slot's front corner tile
    const spriteAt = {};
    for (const sp of (world.spec.grid && world.spec.grid.sprites) || []) {
      const art = (world.spec.spriteArt || {})[sp.id]; if (!art) continue;
      const [lx, ly0] = view.proj(sp.x0, sp.y1, sp.h || 1), [rx, ry0] = view.proj(sp.x1, sp.y0, sp.h || 1);
      const L = [lx - HALF, ly0 + TH / 2], R = [rx + HALF, ry0 + TH / 2], m = art.meta;
      const s = (R[0] - L[0]) / (m.right[0] - m.left[0]);
      const w = Math.round(m.w * s), h = Math.round(m.h * s);
      const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
      const c2 = cv.getContext('2d'); c2.imageSmoothingEnabled = true; c2.imageSmoothingQuality = 'high'; c2.drawImage(art.img, 0, 0, w, h);
      const data = c2.getImageData(0, 0, w, h).data;
      const dx = L[0] - m.left[0] * s, dy = (L[1] + R[1]) / 2 - ((m.left[1] + m.right[1]) / 2) * s;
      spriteAt[sp.x1 + ',' + sp.y1] = () => ctx.blit(data, w, h, dx, dy);
    }
    // per-building art from a sprite set (row houses): fitted by footprint width, standing on its front corner
    const setCache = {};
    function scaled(set, k, flip, s) {
      const key = set + k + flip + s.toFixed(3);
      if (setCache[key]) return setCache[key];
      const art = world.spec.spriteArt[set].variants[k], m = art.meta;
      const w = Math.max(1, Math.round(m.w * s)), h = Math.max(1, Math.round(m.h * s));
      const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
      const c2 = cv.getContext('2d'); c2.imageSmoothingEnabled = true; c2.imageSmoothingQuality = 'high';
      if (flip) { c2.translate(w, 0); c2.scale(-1, 1); }
      c2.drawImage(art.img, 0, 0, w, h);
      return (setCache[key] = { data: c2.getImageData(0, 0, w, h).data, w, h });
    }
    for (const b of world.buildings || []) {
      if (!b.art || !world.spec.spriteArt || !world.spec.spriteArt[b.art]) continue;
      const v = world.spec.spriteArt[b.art].variants[b.variant || 0]; if (!v) continue;
      const m = v.meta, x1 = b.x0 + b.w - 1, y1 = b.y0 + b.d - 1, gh = b.gh || 1;
      const span = (b.w + b.d) * HALF;                                     // footprint width on screen
      const s = Math.round(span * 1.1 / (m.right[0] - m.left[0]) * 200) / 200;
      const bx = b.flip ? m.w - m.bottom[0] : m.bottom[0];
      const [cx, cy0] = view.proj(x1, y1, gh);
      const key = x1 + ',' + y1, prev = spriteAt[key];
      spriteAt[key] = () => { if (prev) prev(); const sc = scaled(b.art, b.variant || 0, !!b.flip, s);
        ctx.blit(sc.data, sc.w, sc.h, cx - bx * s, cy0 + TH - m.bottom[1] * s); };
    }
    for (const tl of order) {
      const tr = TERRAIN[tl.t];
      const [cx, cy0] = view.proj(tl.x, tl.y, tl.h);
      const cy = cy0 + TH / 2; // diamond centre
      const raise = tl.raise || 0;
      const depth = tl.h * HZ + BASE + raise;
      const bld = tl.bld;
      const edge = tl.x === W - 1 || tl.y === H - 1;
      const nb = (dx, dy) => world.T(tl.x + dx, tl.y + dy);
      const back = nb(-1, 0), front = nb(1, 0);
      const cliffBack = back && back.h < tl.h, cliffFront = !front || front.h < tl.h;
      const patch = 0.06 + fbm(tl.x / 3.5, tl.y / 3.5, 41) * 0.3; // soft large-scale colour patches
      const same = (dx, dy) => { const n = nb(dx, dy); return n && ((bld && n.bld === bld) || (tl.wall && n.wall && !bld)); };
      const edgeBL = !same(-1, 0), edgeBR = !same(0, -1), edgeFL = !same(0, 1), edgeFR = !same(1, 0);
      const outer = edgeBL || edgeBR || edgeFL || edgeFR;
      isoPrism(ctx, cx, cy - raise, HALF, depth, (u, left, part, x, y, dTop, rem) => {
        if (raise && part === 'top') {
          if (bld) {
            const [rd, rl] = bld.roof;
            const base = tl.roofSide < 0 ? rl : tl.roofSide > 0 ? rd : shade(rl, 0.12);
            if (rem === 1 && ((left && edgeFL) || (!left && edgeFR))) return shade(base, -0.3); // eaves shadow
            if (((x + y * 2) & 3) === 0) return shade(base, -0.08);                          // shingle rows
            return hash(x, y, 9) < 0.08 ? shade(base, 0.1) : base;
          }
          // wall walk / tower top with crenellations
          if (dTop === 0 || rem === 1) return ((x + y) & 1) ? P.s4 : P.s1;
          return tl.tower ? P.s2 : P.s3;
        }
        if (raise && part === 'side' && dTop < raise) {
          if (bld && dTop < tl.roofLift) { // gable end / stepped roof face
            const [rd, rl] = bld.roof; const f = tl.roofSide < 0 ? rl : rd;
            return left ? shade(f, -0.3) : shade(f, -0.15);
          }
          if (bld) {
            dTop -= tl.roofLift;
            const w = bld.wallc, wall = left ? shade(w, -0.35) : shade(w, -0.1);
            if (dTop === 0) return left ? shade(w, -0.2) : w;
            const visible = left ? edgeFL : edgeFR;
            if (visible && tl.wallH >= 6 && (dTop === 2 || dTop === 3) && ((x & 3) === 1)) return hash(x, bld.id, 4) < 0.35 ? P.e1 : P.ink;
            if (dTop === tl.wallH - 1) return shade(wall, -0.2);
            return wall;
          }
          const st = left ? P.s1 : P.s2;
          return (dTop % 3 === 0 && ((x + (dTop / 3 | 0)) & 1)) ? P.s0 : st;
        }
        if (part === 'side' && raise) dTop -= raise;
        if (part === 'top') {
          const r = hash(x, y, 77);
          if (tr.water) {
            return r < 0.08 ? tr.top[1] : tr.top[0];
          }
          if (dTop === 0 && left && cliffBack) return tr.top[2];   // lit lip of a raised tile
          if (rem === 1 && !left && cliffFront) return tr.top[3];  // shadowed lip toward a drop
          if (tr.rows) { const row = ((x + 2 * y) >> 1) & 3; return row === 0 ? tr.top[3] : row === 2 ? (r < 0.5 ? tr.top[1] : tr.top[2]) : tr.top[0]; }
          if (r < patch) return tr.top[1];
          if (r > 0.95 - patch * 0.3) return tr.top[2];
          return tr.top[0];
        }
        // side
        const sideTop = tl.h * HZ;
        if (dTop >= sideTop) { // below sea-level: soil strata, visible on diorama edge
          const k = dTop - sideTop;
          if (!edge) return left ? P.soil0 : P.soil1;
          const band = k < 3 ? P.soil2 : k < 7 ? P.soil1 : P.soil0;
          return left ? shade(band, -0.25) : band;
        }
        if (dTop === 0) return left ? shade(tr.side[0], 0.12) : shade(tr.side[1], 0.18);
        return left ? tr.side[0] : tr.side[1];
      });
      if (tl.well) (tl.fountain ? KITS.fountain : KITS.well)(ctx, cx, cy + 1);
      if (bld && bld.story && Math.abs(tl.x - Math.round(bld.tx)) + Math.abs(tl.y - Math.round(bld.ty)) === 0) {
        if (bld.type === 'church') { tower(ctx, cx, cy - raise + 2, 3, 14, P.bone, [P.s1, P.s3]); ctx.fillStyle = P.gold; ctx.fillRect(cx, cy - raise - 22, 1, 3); ctx.fillRect(cx - 1, cy - raise - 21, 3, 1); }
        if (bld.type === 'keep') { tower(ctx, cx, cy - raise + 2, 4, 14, '#9aa0a6', [P.roofB, P.roofB2]); }
        if (bld.type === 'mill') { ctx.fillStyle = P.w0; for (let k = -7; k <= 7; k++) { ctx.fillRect(cx + k, cy - raise - 4 + (k >> 2), 1, 1); ctx.fillRect(cx + (k >> 1), cy - raise - 4 + k, 1, 1); } }
        if (bld.type === 'tavern') { ctx.fillStyle = P.w2; ctx.fillRect(cx + 5, cy - raise + 2, 1, 5); ctx.fillStyle = P.gold; ctx.fillRect(cx + 5, cy - raise + 2, 3, 2); }
      }
      // bridge planks
      if (tl.bridge) {
        isoPrism(ctx, cx, cy - 1, 4, 1, (u, left, part, x) => part === 'side' ? P.w0 : ((x & 1) ? P.w2 : P.w3));
      }
      // road ruts
      if (tl.t === 'road') { ctx.fillStyle = P.w1; ctx.fillRect(cx - 1, cy, 2, 1); }
      // props
      if (tl.prop) drawProp(ctx, tl, cx, cy);
      const spr = spriteAt[tl.x + ',' + tl.y]; if (spr) spr();
      if (tl.place) {
        const kit = KITS[tl.place.kind] || KITS.marker;
        kit(ctx, cx, cy + 1, tl.place);
      }
    }
  }

  function drawProp(ctx, tl, cx, cy) {
    const r = hash(tl.x, tl.y, 5), jx = Math.round((r - 0.5) * 6), jy = Math.round((hash(tl.x, tl.y, 6) - 0.5) * 3);
    switch (tl.prop) {
      case 'pine': drawSprite(ctx, SPR.pine, cx + jx, cy + 2 + jy); break;
      case 'round': drawSprite(ctx, SPR.round, cx + jx, cy + 2 + jy); break;
      case 'autumn': {
        const pal = r < 0.5 ? { d: P.a1, g: P.a2, G: P.a4 } : { d: P.a0, g: P.a1, G: P.a3 };
        drawSprite(ctx, SPR.round, cx + jx, cy + 2 + jy, pal); break;
      }
      case 'snowpine': drawSprite(ctx, SPR.pine, cx + jx, cy + 2 + jy, { G: P.sn2, g: P.g1, d: P.g0 }); break;
      case 'dead': drawSprite(ctx, SPR.dead, cx + jx, cy + 2 + jy); break;
      case 'bush': drawSprite(ctx, SPR.bush, cx + jx, cy + 2 + jy); break;
      case 'rock': drawSprite(ctx, SPR.rock, cx + jx, cy + 2 + jy, tl.t === 'snow' ? { l: P.sn2 } : null); break;
      case 'reed': drawSprite(ctx, SPR.reed, cx + jx, cy + 1 + jy); break;
    }
  }

  // ---------- animated layer ----------
  function drawAnimated(ctx, world, view, t, state) {
    const { tiles } = world;
    // water shimmer
    for (const tl of state.waterTiles) {
      const [cx, cy0] = view.proj(tl.x, tl.y, tl.h); const cy = cy0 + TH / 2;
      const ph = (t * 1.3 + hash(tl.x, tl.y, 1) * 6) % 6;
      if (ph < 1.6) {
        ctx.fillStyle = tl.t === 'blood' ? P.red3 : P.foam;
        const dx = Math.round(Math.sin(t * 0.8 + tl.x) * 3);
        ctx.fillRect(cx + dx - 1, cy + (tl.x % 2) - 1, 2, 1);
      }
    }
    for (const tl of state.wells || []) { const [cx, cy0] = view.proj(tl.x, tl.y, tl.h); if (Math.sin(t * 2 + tl.x) > 0.2) { ctx.fillStyle = P.red3; ctx.fillRect(cx, cy0 + TH / 2 - 3, 1, 1); } }
    for (const tl of state.smokers || []) { const [cx, cy0] = view.proj(tl.x, tl.y, tl.h); drawSmoke(ctx, cx, cy0 + TH / 2 - tl.raise - 2, t, tl.x * 31 + tl.y); }
    for (const pl of world.spec.places || []) {
      const tl = world.T(pl.x, pl.y); if (!tl) continue;
      const [cx, cy0] = view.proj(pl.x, pl.y, tl.h); const gy = cy0 + TH / 2 + 1;
      const fx = pl.fx || {};
      if (pl.kind === 'rift' || fx.rift) drawRift(ctx, cx, gy, t, pl);
      if (pl.kind === 'camp' || fx.fire) drawFire(ctx, cx + (pl.kind === 'camp' ? 3 : 0), gy + 2, t);
      if (pl.kind === 'mill') drawWheel(ctx, cx + 7, gy - 2, t);
      if (pl.kind === 'well') { if (Math.sin(t * 2 + pl.x) > 0.2) { ctx.fillStyle = P.red3; ctx.fillRect(cx, gy - 4, 1, 1); } }
      if (fx.smoke || pl.kind === 'town' || pl.kind === 'village' || pl.kind === 'city' || pl.kind === 'tavern' || pl.kind === 'camp')
        drawSmoke(ctx, cx + (pl.kind === 'camp' ? 3 : -3), gy - (pl.kind === 'camp' ? 2 : 12), t, pl.x * 7 + pl.y);
      if (fx.glow) { const a = 0.5 + 0.5 * Math.sin(t * 3 + pl.x); ctx.fillStyle = a > 0.5 ? P.e1 : P.e2; ctx.fillRect(cx - 1, gy - 6, 1, 1); }
      if (pl.kind === 'city' || pl.kind === 'keep') { // flag flutter
        const f = Math.floor(t * 4) % 2; ctx.fillStyle = pl.flag || P.roofR2; ctx.fillRect(cx + 2, gy - 32 + f, 3, 1); ctx.fillRect(cx + 2, gy - 31, 2 + f, 1);
      }
    }
    // highlighted buildings (by type / story) and pins over key buildings
    if (state.highlight && state.highlight.size && world.blds) {
      const on = Math.floor(t * 3) % 2 === 0;
      for (const tl of state.hlTiles) { // roof sparkle
        const [cx, cy0] = view.proj(tl.x, tl.y, tl.h); const cy = cy0 + TH / 2 - tl.raise;
        ctx.fillStyle = on ? P.e1 : P.e2; ctx.fillRect(cx - 1, cy - 1, 2, 2);
      }
      for (const b of state.hlBlds) { // bouncing arrow over each building
        const [cx, cy0] = view.proj(b.tx, b.ty, 1); const cy = cy0 - b.h - 14 + Math.round(Math.sin(t * 5 + b.id) * 2);
        ctx.fillStyle = P.ink; ctx.fillRect(cx - 4, cy - 1, 9, 7);
        ctx.fillStyle = on ? P.e1 : P.e2; ctx.fillRect(cx - 3, cy, 7, 2); ctx.fillRect(cx - 2, cy + 2, 5, 1); ctx.fillRect(cx - 1, cy + 3, 3, 1); ctx.fillRect(cx, cy + 4, 1, 1);
      }
    }
    for (const b of state.pins || []) {
      const [cx, cy0] = view.proj(b.tx, b.ty, 1); const cy = cy0 + TH / 2 - b.h - (b.type === 'church' || b.type === 'keep' ? 30 : 10);
      const bob = Math.round(Math.sin(t * 3 + b.id) * 1.5);
      ctx.fillStyle = P.ink; ctx.fillRect(cx - 2, cy - 6 + bob, 5, 5);
      ctx.fillStyle = b.importance === 'key' ? P.e1 : P.s4; ctx.fillRect(cx - 1, cy - 5 + bob, 3, 3);
      ctx.fillStyle = P.ink; ctx.fillRect(cx, cy - 1 + bob, 1, 3);
    }
    // weather particles (screen-space)
    for (const p of state.particles) {
      const x = (p.x + t * p.vx) % view.width, y = (p.y + t * p.vy) % view.height;
      const xx = (x + view.width) % view.width, yy = (y + view.height) % view.height;
      ctx.fillStyle = p.c; ctx.fillRect(Math.round(xx + Math.sin(t * p.w + p.x) * 2), Math.round(yy), 1, 1);
    }
    // Kethric walking the route
    if (state.walker) drawWalker(ctx, world, view, t, state.walker);
  }

  function drawFire(ctx, x, y, t) {
    const f = Math.floor(t * 10) % 3;
    ctx.fillStyle = P.w0; ctx.fillRect(x - 2, y, 5, 1);
    const shapes = [[[0, -1, P.e2], [1, -1, P.e3], [-1, -1, P.e3], [0, -2, P.e1], [0, -3, P.e0]],
                    [[0, -1, P.e2], [1, -1, P.e2], [-1, -1, P.e3], [1, -2, P.e1], [1, -3, P.e0]],
                    [[0, -1, P.e3], [-1, -1, P.e2], [1, -1, P.e3], [-1, -2, P.e1], [0, -3, P.e1], [-1, -4, P.e0]]];
    for (const [dx, dy, c] of shapes[f]) { ctx.fillStyle = c; ctx.fillRect(x + dx, y + dy, 1, 1); }
    ctx.globalAlpha = 0.15 + 0.05 * f; ctx.fillStyle = P.e1; ctx.fillRect(x - 4, y - 3, 9, 5); ctx.globalAlpha = 1;
  }
  function drawSmoke(ctx, x, y, t, seed) {
    for (let i = 0; i < 4; i++) {
      const life = ((t * 0.5 + i / 4 + hash(seed, i, 2)) % 1);
      const px = x + Math.round(Math.sin(life * 5 + seed) * 2 + life * 4), py = y - Math.round(life * 14);
      ctx.fillStyle = life < 0.5 ? P.ash3 : P.ash2; ctx.globalAlpha = 1 - life;
      ctx.fillRect(px, py, life < 0.4 ? 1 : 2, life < 0.4 ? 1 : 2);
    }
    ctx.globalAlpha = 1;
  }
  function drawWheel(ctx, x, y, t) {
    const f = Math.floor(t * 4) % 4;
    ctx.fillStyle = P.w0;
    const spokes = [[[0, -4], [0, 4], [-4, 0], [4, 0]], [[-3, -3], [3, 3], [-3, 3], [3, -3]]][f % 2];
    for (const [dx, dy] of spokes) { const n = 4; for (let k = 0; k <= n; k++) ctx.fillRect(x + Math.round(dx * k / n), y + Math.round(dy * k / n), 1, 1); }
    ctx.fillStyle = P.w2;
    for (let a = 0; a < 16; a++) { const an = a / 16 * Math.PI * 2; ctx.fillRect(x + Math.round(Math.cos(an) * 4), y + Math.round(Math.sin(an) * 4), 1, 1); }
  }
  function drawRift(ctx, cx, gy, t, pl) {
    const pulse = 0.5 + 0.5 * Math.sin(t * 2.2 + pl.x);
    const big = pl.size || 1;
    ctx.globalAlpha = 0.18 + pulse * 0.22; ctx.fillStyle = pl.glow || P.red2;
    isoPrism(ctx, cx, gy, Math.round(9 * big), 0, () => pl.glow || P.red2); ctx.globalAlpha = 1;
    isoPrism(ctx, cx, gy, Math.round(5 * big), 0, () => P.ink);
    const shards = [[-4, 0, 9], [3, -1, 12], [0, 2, 7], [6, 2, 6], [-7, 2, 5]];
    for (const [dx, dy, h] of shards) {
      const hh = Math.round(h * big);
      for (let k = 0; k < hh; k++) {
        const w = k < hh - 2 ? 2 : 1;
        ctx.fillStyle = k > hh - 3 ? P.v3 : (k % 3 === 0 ? P.v2 : P.v1);
        ctx.fillRect(cx + dx, gy + dy - k, w, 1);
      }
    }
    for (let i = 0; i < 6; i++) { // rising motes
      const life = (t * 0.35 + i / 6) % 1;
      ctx.fillStyle = i % 2 ? P.v3 : P.red3; ctx.globalAlpha = 1 - life;
      ctx.fillRect(cx + Math.round(Math.sin(i * 2 + t) * 6 * big), gy - Math.round(life * 24 * big), 1, 1);
    }
    ctx.globalAlpha = 1;
  }
  function drawWalker(ctx, world, view, t, w) {
    const pts = w.path; if (!pts.length) return;
    const speed = w.speed || 2.2; // tiles per second
    const total = pts.length - 1;
    let pos = (t * speed) % (total + 6); // pause at end
    if (pos > total) pos = total;
    const i = Math.floor(pos), f = pos - i;
    const a = pts[i], b = pts[Math.min(i + 1, total)];
    const [ax, ay] = view.proj(a.x, a.y, a.h), [bx, by] = view.proj(b.x, b.y, b.h);
    const x = ax + (bx - ax) * f, y = ay + (by - ay) * f + TH / 2 + 2;
    const frame = pos < total ? Math.floor(t * 6) % 2 : 0;
    // shadow + thurible glow
    ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.fillRect(Math.round(x) - 2, Math.round(y) - 1, 5, 1);
    drawSprite(ctx, frame ? SPR.kethA : SPR.kethB, x, y - 1);
    const g = Math.sin(t * 5) > 0;
    ctx.fillStyle = g ? P.e1 : P.e2; ctx.fillRect(Math.round(x) + 3, Math.round(y) - 4, 1, 1);
    w.current = { x, y, tile: a };
  }

  // ---------- public API ----------
  function create(canvas, spec, opts) {
    opts = opts || {};
    const world = buildWorld(spec);
    const view = makeView(world);
    canvas.width = view.width; canvas.height = view.height;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    const stat = document.createElement('canvas');
    stat.width = view.width; stat.height = view.height;
    const buf = new PixelBuf(view.width, view.height);
    drawStatic(buf, world, view);
    stat.getContext('2d').putImageData(buf.img, 0, 0);

    const particles = [];
    const rnd = (i, s) => hash(i, s, spec.seed + 400);
    const nPart = Math.round((spec.ashfall || 120) * Math.max(1, view.width * view.height / 1.2e6));
    for (let i = 0; i < nPart; i++) particles.push({ x: rnd(i, 1) * view.width, y: rnd(i, 2) * view.height, vx: -3 - rnd(i, 3) * 4, vy: 6 + rnd(i, 4) * 6, w: 1 + rnd(i, 5) * 2, c: rnd(i, 6) < 0.15 ? P.e2 : (rnd(i, 7) < 0.5 ? P.ash3 : P.ash4) });
    const state = {
      particles,
      waterTiles: world.tiles.filter(tl => TERRAIN[tl.t].water && hash(tl.x, tl.y, 3) < 0.45),
      walker: null,
      wells: world.tiles.filter(tl => tl.well),
      smokers: world.blds ? world.buildings.filter(b => hash(b.id, 1, 2) < 0.06 || b.type === 'smithy' || b.type === 'tavern' || b.type === 'bakery')
        .map(b => world.T(Math.round(b.tx), Math.round(b.ty))).filter(tl => tl && tl.bld) : [],
      highlight: null, hlTiles: [], hlBlds: [], pins: [],
    };
    // Kethric's journey: chain roads between consecutive route stops
    if (spec.route && spec.route.length > 1) {
      let path = [];
      for (let i = 0; i < spec.route.length - 1; i++) {
        const A = world.byId[spec.route[i]], B = world.byId[spec.route[i + 1]];
        if (!A || !B) continue;
        const seg = astar(world.tiles, world.W, world.H, A, B);
        path = path.concat(i ? seg.slice(1) : seg);
      }
      state.walker = { path, speed: opts.walkSpeed || 2.2 };
    }

    let raf = null, t0 = performance.now(), paused = false, frozenT = 0;
    function frame(now) {
      const t = paused ? frozenT : Math.max(0, (now - t0) / 1000);
      ctx.drawImage(stat, 0, 0);
      drawAnimated(ctx, world, view, t, state);
      if (opts.onFrame) opts.onFrame(t, state);
      raf = requestAnimationFrame(frame);
    }
    function renderAt(t) { ctx.drawImage(stat, 0, 0); drawAnimated(ctx, world, view, t, state); }
    return {
      world, view, state, palette: P,
      start() { if (!raf) raf = requestAnimationFrame(frame); },
      stop() { cancelAnimationFrame(raf); raf = null; },
      pause(p) { paused = p; frozenT = (performance.now() - t0) / 1000; },
      renderAt,
      restartWalk() { t0 = performance.now(); },
      highlight(ids) {
        state.highlight = new Set(ids || []);
        state.hlTiles = world.tiles.filter(tl => tl.bld && state.highlight.has(tl.bld.id) && ((tl.x + tl.y) % 2 === 0));
        state.hlBlds = world.blds ? [...state.highlight].map(id => world.blds[id]).filter(Boolean) : [];
      },
      setPins(list) { state.pins = list || []; },
      screenOfTile(x, y, raise) { const [sx, sy] = view.proj(x, y, 1); return [sx, sy + TH / 2 - (raise || 0)]; },
      screenOf(id) { const pl = world.byId[id]; const tl = world.T(pl.x, pl.y); const [x, y] = view.proj(pl.x, pl.y, tl.h); return [x, y + TH / 2]; },
      tileAt(px, py) { // reverse projection, best effort (top-most tile under the pixel)
        let best = null;
        for (const tl of world.tiles) {
          const [cx, cy0] = view.proj(tl.x, tl.y, tl.h); const cy = cy0 + TH / 2;
          if (Math.abs(px - cx) / HALF + Math.abs(py - cy) / (TH / 2) <= 1) if (!best || tl.x + tl.y > best.x + best.y) best = tl;
        }
        return best;
      },
    };
  }

  window.AshfallIso = { create, palette: P, TERRAIN };
})();
