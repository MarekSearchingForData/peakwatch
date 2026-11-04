"""Generate art through Codex CLI's built-in image tool, using a ChatGPT subscription (no API key).

One-time setup:  npm i -g @openai/codex && codex login --device-auth   (enable device-code sign-in in ChatGPT security settings)

    python3 tools/gen_codex.py greymark_overview vex_mill      # items from data/art_prompts.json
    python3 tools/gen_codex.py --refs greymark_overview         # attach the style reference images
    python3 tools/gen_codex.py --all

Outputs: out/ai/<id>-codex-<n>.png. Runs items in parallel (3 at a time).
"""
import concurrent.futures as cf
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
spec = json.load(open(os.path.join(ROOT, 'data', 'art_prompts.json')))
want = [a for a in args if not a.startswith('--')]
items = [i for i in spec['items'] if '--all' in args or i['id'] in want]
out_dir = os.path.join(ROOT, 'out', 'ai'); os.makedirs(out_dir, exist_ok=True)
gen_dir = os.path.expanduser('~/.codex/generated_images')


def run(item):
    work = tempfile.mkdtemp(prefix='codex-img-')
    w, h = item['size'].split('x')
    shape = 'landscape (wide)' if int(w) > int(h) else 'square'
    prompt = (f"Use your built-in image generation tool to create exactly one {shape} image. Do not write code and do not call any API yourself.\n\n"
              f"Image description: {item['prompt']}\n\nStyle: {spec['style']}\n\n"
              + ("Match the art style of the attached reference images, not their content.\n\n" if '--refs' in args else '')
              + "When the image is generated, copy it into the current directory as result.png and reply only with OK.")
    cmd = ['codex', 'exec', '--skip-git-repo-check', '--sandbox', 'workspace-write', '-C', work]
    if '--refs' in args:
        for r in spec['references']: cmd += ['-i', os.path.join(ROOT, r)]
    before = set(glob.glob(os.path.join(gen_dir, '*', '*.png')))
    p = subprocess.run(cmd + [prompt], capture_output=True, text=True, timeout=900)
    src = os.path.join(work, 'result.png')
    if not os.path.exists(src):  # fall back to whatever the tool wrote
        new = sorted(set(glob.glob(os.path.join(gen_dir, '*', '*.png'))) - before, key=os.path.getmtime)
        src = new[-1] if new else None
    if not src:
        return item['id'], 'FAILED: ' + (p.stdout + p.stderr)[-400:]
    n = len(glob.glob(os.path.join(out_dir, f"{item['id']}-codex-*.png"))) + 1
    dst = os.path.join(out_dir, f"{item['id']}-codex-{n}.png"); shutil.copy(src, dst)
    shutil.rmtree(work, ignore_errors=True)
    return item['id'], os.path.relpath(dst, ROOT)


with cf.ThreadPoolExecutor(3) as ex:
    for iid, res in ex.map(run, items):
        print(iid, '->', res)
