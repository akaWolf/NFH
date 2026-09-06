import sys, json, subprocess, numpy as np
from PIL import Image, ImageDraw
video, start, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
x0, y0, w, h = map(int, sys.argv[4:8]); prefix = sys.argv[8]; T = float(sys.argv[9]) if len(sys.argv) > 9 else 60
raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(start), '-t', str(dur), '-i', video, '-vf', 'fps=1,crop=%d:%d:%d:%d' % (w, h, x0, y0), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
n = len(raw) // (w * h * 3); crops = np.frombuffer(raw[:n * w * h * 3], dtype=np.uint8).reshape(n, h, w, 3)
MODE = sys.argv[10] if len(sys.argv) > 10 else 'white'
white = ((crops.min(axis=3) > 190) if MODE == 'white' else ((crops[:, :, :, 0] > 170) & (crops[:, :, :, 1] < 130))).astype(np.float32)
feat = white.reshape(n, -1)
centers = []; members = []; rows = []
for i in range(n):
    f = feat[i]; best = None; bd = 1e18
    for k, c in enumerate(centers):
        d = float(np.abs(f - c).sum())
        if d < bd: bd, best = d, k
    if best is None or bd > T:
        centers.append(f.copy()); members.append([i]); best = len(centers) - 1
    else:
        members[best].append(i); centers[best] = feat[members[best]].mean(axis=0)
    rows.append([round(start + i, 1), best])
K = len(centers); cols = min(K, 12); im = Image.new('RGB', (cols * 100, ((K + cols - 1) // cols) * 60), (30, 30, 30)); d = ImageDraw.Draw(im)
for k in range(K):
    ex = Image.fromarray((white[members[k][len(members[k]) // 2]] * 255).astype(np.uint8)).resize((96, 48))
    im.paste(ex, ((k % cols) * 100 + 2, (k // cols) * 60 + 2)); d.text(((k % cols) * 100 + 4, (k // cols) * 60 + 50), '%d n=%d' % (k, len(members[k])), fill=(255, 255, 0))
im.save(prefix + '_icons.png'); json.dump(rows, open(prefix + '.json', 'w'))
seq = []
for t, k in rows:
    if seq and seq[-1][1] == k: seq[-1][2] = t
    else: seq.append([t, k, t])
print('frames', n, 'clusters', K, 'sizes', sorted([len(m) for m in members], reverse=True)[:12])
print(' '.join('%d@%.0f-%.0f' % (k, a, b) for a, k, b in seq if b - a >= 3))
