"""PC NFH2 anger gauge fill per second: the vertical bar at the left of the
720p frame (x 8..30, y 60..540); a row is 'filled' when it is orange/yellow
(R > 180, G in 80..230, B < 120). Prints fill % every 5 s and the drift
between trick jumps."""
import sys, subprocess, numpy as np
video, start, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(start), '-t', str(dur), '-i', video, '-vf', 'fps=1,crop=22:480:8:60', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
n = len(raw) // (480 * 22 * 3); f = np.frombuffer(raw[:n * 480 * 22 * 3], dtype=np.uint8).reshape(n, 480, 22, 3).astype(int)
fill = []
for i in range(n):
    r, g, b = f[i, :, :, 0], f[i, :, :, 1], f[i, :, :, 2]
    orange = (r > 180) & (g > 80) & (g < 230) & (b < 120)
    rows = orange.mean(axis=1) > 0.5
    ys = np.nonzero(rows)[0]
    fill.append(0.0 if len(ys) == 0 else round(100.0 * (480 - ys.min()) / 480, 1))
print('t(s): ' + ' '.join('%d:%.0f' % (i, fill[i]) for i in range(0, n, 5)))
# drift between jumps: segments where the fill changes by < 3 over the segment
segs = []; a = 0
for i in range(1, n):
    if abs(fill[i] - fill[i - 1]) > 4:
        if i - 1 - a >= 8: segs.append((a, i - 1, fill[a], fill[i - 1]))
        a = i
if n - 1 - a >= 8: segs.append((a, n - 1, fill[a], fill[n - 1]))
print('plateaus (start-end s: fill start -> end): ' + '; '.join('%d-%d: %.0f->%.0f' % s for s in segs))
