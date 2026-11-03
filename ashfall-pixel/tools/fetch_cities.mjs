// Fetch city layouts from watabou's Medieval Fantasy City Generator (MFCG)
// https://watabou.itch.io/medieval-fantasy-city-generator  (free, browser-based)
// MFCG exports GeoJSON-like data: buildings, walls, roads, squares, fields, districts.
// We drive it headlessly with ?export=json and save to cities/<id>.mfcg.json,
// then tools/bake_city.py turns that into an isometric tile grid.
//
//   node tools/fetch_cities.mjs            (all)
//   node tools/fetch_cities.mjs greymark   (one)
//
// Change `seed` to reroll a layout you don't like; tweak the flags to taste.
import { createRequire } from 'module';
import { mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dir = path.join(root, 'cities');
mkdirSync(dir, { recursive: true });

export const CITIES = {
  // Small border town: palisade, a church on the high point, a square with the well.
  greymark: { size: 14, seed: 2121, citadel: 0, urban_castle: 0, walls: 1, temple: 1, plaza: 1, river: 0, coast: 0, shantytown: 1, greens: 0 },
  // Large basin city: House Deveraux's keep (citadel), walls, a stream, gardens, vineyards around it.
  valencourt: { size: 36, seed: 7777, citadel: 1, urban_castle: 0, walls: 1, temple: 1, plaza: 1, river: 1, coast: 0, shantytown: 1, greens: 1 },
};

const want = process.argv.slice(2);
const browser = await chromium.launch();
for (const [id, opts] of Object.entries(CITIES)) {
  if (want.length && !want.includes(id)) continue;
  const q = new URLSearchParams(Object.assign({}, opts, { export: 'json' }));
  const ctx = await browser.newContext({ acceptDownloads: true });
  const page = await ctx.newPage();
  const dl = page.waitForEvent('download', { timeout: 90000 });
  await page.goto('https://watabou.github.io/city-generator/?' + q, { waitUntil: 'load', timeout: 90000 });
  const file = await dl;
  const out = path.join(dir, `${id}.mfcg.json`);
  await file.saveAs(out);
  console.log(id, '->', path.relative(root, out));
  await ctx.close();
}
await browser.close();
