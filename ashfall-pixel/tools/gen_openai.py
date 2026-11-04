"""Generate art with OpenAI's image model (the one ChatGPT uses).

Needs OPENAI_API_KEY in the environment (add it in the environment settings; never paste it into chat).

    python3 tools/gen_openai.py                      # every item in data/art_prompts.json
    python3 tools/gen_openai.py greymark_square      # one item
    python3 tools/gen_openai.py --refs greymark_square   # also send the style reference images (edits endpoint)
    options: --quality low|medium|high  --n 2  --model gpt-image-1

Outputs go to out/ai/<id>-<n>.png with the prompt saved next to them.
"""
import base64
import json
import os
import sys
import time
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
MODEL, QUALITY, N = opt('--model', 'gpt-image-1'), opt('--quality', 'medium'), int(opt('--n', '1'))
USE_REFS = '--refs' in args
skip = {opt('--model', None), opt('--quality', None), opt('--n', None)}
want = [a for a in args if not a.startswith('--') and a not in skip]
KEY = os.environ.get('OPENAI_API_KEY')
if not KEY:
    sys.exit('OPENAI_API_KEY is not set: add it in the environment settings and start a new session.')
spec = json.load(open(os.path.join(ROOT, 'data', 'art_prompts.json')))
out_dir = os.path.join(ROOT, 'out', 'ai'); os.makedirs(out_dir, exist_ok=True)


def post_json(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=300))


def post_multipart(url, fields, files):
    b = uuid.uuid4().hex; parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, path in files:
        mime = 'image/png' if path.endswith('.png') else 'image/jpeg'
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
                     + open(path, 'rb').read() + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    req = urllib.request.Request(url, b''.join(parts), {'Authorization': f'Bearer {KEY}', 'Content-Type': f'multipart/form-data; boundary={b}'})
    return json.load(urllib.request.urlopen(req, timeout=300))


for item in spec['items']:
    if want and item['id'] not in want: continue
    prompt = item['prompt'] + '\n\nStyle: ' + spec['style']
    t0 = time.time()
    try:
        if USE_REFS:
            refs = [os.path.join(ROOT, r) for r in spec['references']]
            res = post_multipart('https://api.openai.com/v1/images/edits',
                                 {'model': MODEL, 'prompt': prompt + '\nMatch the art style of the attached reference images; do not copy their content.',
                                  'size': item['size'], 'quality': QUALITY, 'n': str(N)}, [('image[]', r) for r in refs])
        else:
            res = post_json('https://api.openai.com/v1/images/generations',
                            {'model': MODEL, 'prompt': prompt, 'size': item['size'], 'quality': QUALITY, 'n': N})
    except urllib.error.HTTPError as e:
        print('!!', item['id'], e.code, e.read()[:400].decode(errors='replace')); continue
    for i, d in enumerate(res['data'], start=1):
        p = os.path.join(out_dir, f"{item['id']}-{i}.png")
        open(p, 'wb').write(base64.b64decode(d['b64_json']))
        print('saved', os.path.relpath(p, ROOT), f'{time.time() - t0:.0f}s')
    open(os.path.join(out_dir, f"{item['id']}.prompt.txt"), 'w').write(prompt)
