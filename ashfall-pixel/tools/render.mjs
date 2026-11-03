// Headless renderer: screenshots the map and exports an animated GIF.
//   node tools/render.mjs            -> out/kingdom.png, out/kingdom-245.png, out/kingdom.gif
//   node tools/render.mjs --png-only
// Uses the pre-installed Playwright + Chromium and ffmpeg.
import { createRequire } from 'module';
import { execFileSync } from 'child_process';
import { mkdirSync, rmSync } from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'out');
mkdirSync(out, { recursive: true });
const page_url = (q) => pathToFileURL(path.join(root, 'map', 'index.html')).href + q;

const browser = await chromium.launch();
async function shot(query, file, size = { width: 1600, height: 1000 }) {
  const page = await browser.newPage({ viewport: size, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(page_url(query));
  await page.waitForSelector('body[data-ready]', { timeout: 120000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(out, file) });
  if (errors.length) console.error(file, 'ERRORS:', errors);
  await page.close();
  return errors;
}

const errs = [];
errs.push(...await shot('?tab=build', 'kingdom.png'));
errs.push(...await shot('?v=245&ev=21', 'kingdom-245.png'));
errs.push(...await shot('?view=greymark&tab=build', 'greymark.png'));
errs.push(...await shot('?view=greymark&ev=9&z=3', 'greymark-well.png'));
errs.push(...await shot('?view=valencourt&tab=build', 'valencourt.png'));
errs.push(...await shot('?view=valencourt&type=tavern&z=1', 'valencourt-taverns.png'));

if (!process.argv.includes('--png-only')) {
  // GIF: capture the bare canvas over time via the ?t= hook
  const frames = path.join(out, 'frames');
  rmSync(frames, { recursive: true, force: true }); mkdirSync(frames, { recursive: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const N = Number(process.env.FRAMES || 60), DT = 1 / 12;
  for (let i = 0; i < N; i++) {
    await page.goto(page_url(`?t=${(i * DT + 3).toFixed(3)}&z=1&labels=0`));
    await page.waitForSelector('body[data-ready]');
    const el = await page.$('#map');
    await el.screenshot({ path: path.join(frames, `f${String(i).padStart(3, '0')}.png`) });
  }
  await page.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '12', '-i', path.join(frames, 'f%03d.png'),
    '-vf', 'scale=iw*2:ih*2:flags=neighbor,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=none',
    '-loop', '0', path.join(out, 'kingdom.gif')]);
  rmSync(frames, { recursive: true, force: true });
}
await browser.close();
console.log('done', errs.length ? 'with errors' : 'ok');
