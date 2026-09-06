"""the PC NFH2 trick amounts off the anger gauge: the gauge's jumps in a 100 %
run (Badinfos', tools/pcref/README.md), each labelled with the neighbour's
activity at that second (the HUD bubble spans in docs/PC_LAPS_DETAIL.md — a
trick pays when he uses the tricked item) and scaled so that the bar's
full reading (92 % of the crop's rows) is 100; the mobile AngerAmount of the
level's TrickItems is printed beside for the overlay (levels/pc/<Level>.
overlay.json, the `set AngerAmount` op).

usage: python3 tools/pcref/amounts.py <video> [episode ...]   (1-14)"""
import json, os, re, subprocess, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
video = sys.argv[1]
eps = json.load(open(os.path.join(ROOT, 'tools', 'pcref', 'episodes_nfh2.json')))
want = [int(a) for a in sys.argv[2:]] or list(range(1, 15))
doc = open(os.path.join(ROOT, 'docs', 'PC_LAPS_DETAIL.md')).read()
spans = {}
for sec in re.split(r'^### ', doc, flags=re.M)[1:]:
    m = re.search(r'mobile Level(\d+)\)', sec)
    if not m: continue
    line = next((l for l in sec.splitlines() if l.startswith('PC (bubble')), '')
    out = []
    for part in line.split(':', 1)[1].split('>'):
        mm = re.match(r'\s*(.+?)\s+(\d+)-(\d+)\s*$', part)
        if mm: out.append((mm.group(1).strip(), int(mm.group(2)), int(mm.group(3))))
    spans[int(m.group(1))] = out
FULL = 92.0
def fill_series(start, dur):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(start), '-t', str(dur), '-i', video,
                          '-vf', 'fps=1,crop=22:480:8:60', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    n = len(raw) // (480 * 22 * 3)
    f = np.frombuffer(raw[:n * 480 * 22 * 3], dtype=np.uint8).reshape(n, 480, 22, 3).astype(int)
    out = []
    for i in range(n):
        r, g, b = f[i, :, :, 0], f[i, :, :, 1], f[i, :, :, 2]
        orange = (r > 180) & (g > 80) & (g < 230) & (b < 120)
        rows = orange.mean(axis=1) > 0.5
        ys = np.nonzero(rows)[0]
        out.append(0.0 if len(ys) == 0 else 100.0 * (480 - ys.min()) / 480)
    return out
def activity(L, t):
    for name, a, b in spans.get(L, []):
        if a <= t <= b + 1: return name
    return '?'
for k in want:
    e = eps[k - 1]; L = 200 + k
    fill = fill_series(e['start'], e['len'])
    jumps = []; i = 1
    while i < len(fill):
        if fill[i] - fill[i - 1] > 1.5:
            j = i; tot = 0.0
            while j < len(fill) and fill[j] - fill[j - 1] > 1.5:
                tot += fill[j] - fill[j - 1]; j += 1
            capped = fill[j - 1] >= FULL - 1.0
            jumps.append((i, tot, fill[i - 1], fill[j - 1], capped)); i = j
        else:
            i += 1
    lv = json.load(open(os.path.join(ROOT, 'levels', 's2', 'Level%d.json' % L)))
    mobile = []
    def walk(o):
        if isinstance(o, dict):
            d = o.get('data')
            if isinstance(d, dict) and 'AngerAmount' in d and d.get('AngerAmount'):
                mobile.append(((d.get('m_GameObject') or {}).get('name'), d['AngerAmount']))
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(lv)
    print('== E%02d / Level%d  (%d s, gauge max %.0f)' % (k, L, len(fill), max(fill) if fill else 0))
    for t, tot, f0, f1, capped in jumps:
        print('   %4d s  +%5.1f raw = %5.1f scaled  (%.0f -> %.0f)%s  during %s' % (t, tot, tot * 100.0 / FULL, f0, f1, '  CAPPED' if capped else '', activity(L, t)))
    print('   mobile AngerAmount: ' + ', '.join('%s %s' % m for m in mobile))
