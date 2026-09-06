"""the PC HUD's neighbour-activity bubble as a routine signal.
usage: bubble.py <video> <start> <dur> <x0> <y0> <w> <h> <out_prefix> [fps=1]
crops the bubble icon per frame, clusters the crops greedily (L2 on a 24x24
RGB thumbnail, threshold T), writes <prefix>.json {rows: [t, cluster]} and
<prefix>_icons.png (one exemplar per cluster, labelled by id)."""
import sys, json, subprocess, numpy as np
from PIL import Image, ImageDraw
video, start, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
x0, y0, w, h = map(int, sys.argv[4:8]); prefix = sys.argv[8]
fps = float(sys.argv[9]) if len(sys.argv) > 9 else 1.0
cmd = ['ffmpeg', '-loglevel', 'error', '-ss', str(start), '-t', str(dur), '-i', video,
       '-vf', 'fps=%g,crop=%d:%d:%d:%d,scale=48:48' % (fps, w, h, x0, y0), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
raw = subprocess.run(cmd, capture_output=True).stdout
n = len(raw) // (48 * 48 * 3)
crops = np.frombuffer(raw[:n * 48 * 48 * 3], dtype=np.uint8).reshape(n, 48, 48, 3)
feat = crops.reshape(n, 2, 24, 2, 24, 3).mean(axis=(1, 3)).reshape(n, -1).astype(np.float32)
T = float(sys.argv[10]) if len(sys.argv) > 10 else 900.0
centers = []; members = []; rows = []
for i in range(n):
    f = feat[i]; best = None; bd = 1e18
    for k, c in enumerate(centers):
        d = float(np.sqrt(((f - c) ** 2).sum()))
        if d < bd: bd, best = d, k
    if best is None or bd > T:
        centers.append(f.copy()); members.append([i]); best = len(centers) - 1
    else:
        members[best].append(i); m = members[best]
        centers[best] = feat[m].mean(axis=0)
    rows.append([round(start + i / fps, 1), best])
# exemplar montage
K = len(centers); cols = min(K, 12); rws = (K + cols - 1) // cols
im = Image.new('RGB', (cols * 100, rws * 110), (30, 30, 30)); d = ImageDraw.Draw(im)
for k in range(K):
    ex = Image.fromarray(crops[members[k][len(members[k]) // 2]]).resize((96, 96))
    im.paste(ex, ((k % cols) * 100 + 2, (k // cols) * 110 + 2))
    d.text(((k % cols) * 100 + 4, (k // cols) * 110 + 98), '%d n=%d' % (k, len(members[k])), fill=(255, 255, 0))
im.save(prefix + '_icons.png')
json.dump({'video': video, 'start': start, 'dur': dur, 'fps': fps, 'rows': rows, 'sizes': [len(m) for m in members]}, open(prefix + '.json', 'w'))
# run-length sequence
seq = []; 
for t, k in rows:
    if seq and seq[-1][1] == k: seq[-1][2] = t
    else: seq.append([t, k, t])
print('frames', n, 'clusters', K, 'sizes', [len(m) for m in members])
print('sequence: ' + ' '.join('%d@%.0f-%.0f' % (k, a - start, b - start) for a, k, b in seq if b - a >= 1.0))
