"""The Season 1 thermometer read as the first non-blue row of the tube (the
mercury's white-hot top counts, which thermo.py's red-only reader misses):
per trick, the seconds the fill stays at 97 %+ and the fall in %/s over the
linear part. On Badinfos' video the hold is 5.4-5.8 s (game.exe's 60-tick
hold at 12 Hz plus the top 3 %) and the fall covers 0.7 x the level's
angrytime ticks — the tube shows the top ~70 % of the bar, the bulb the
rest (docs/PC_ROUTINES.md, "The tick is 12 Hz").
    python3 tools/pcref/thermo_rows.py E03 E04 [E06 …]   (thermo.py's video)"""
import json, os, subprocess, sys
ARGS = sys.argv[1:]; sys.argv = sys.argv[:1]
sys.path.insert(0, os.path.expanduser('~/projects/own/NFH/tools/pcref'))
import thermo
V = thermo.V
def column(e, t0, t1, x=156, y0=592, h=94):
    f = '/tmp/thermo_rows_%d.raw' % os.getpid()
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(e['start'] + t0), '-i', V, '-t', str(t1 - t0), '-vf', 'fps=10,crop=2:%d:%d:%d' % (h, x, y0), '-f', 'rawvideo', '-pix_fmt', 'rgb24', f])
    out = open(f, 'rb').read(); os.unlink(f)
    fr = h * 6; res = []
    for i in range(len(out) // fr):
        px = [out[i * fr + y * 6: i * fr + y * 6 + 3] for y in range(h)]
        top = next((y for y in range(h) if px[y][0] > px[y][2] + 40), None)
        res.append(top)
    return res
for name in ARGS:
    ep = next(e for e in thermo.EPS if e['name'].startswith(name))
    r = column(ep, 0, ep['len'])
    N = len(r)
    # the tube: the empty reading is None (all blue); full = the minimum top over the episode
    tops = [t for t in r if t is not None]
    full = min(tops); empty = 94   # px rows: smaller = higher; None = all blue = empty
    fill = [0.0 if t is None else (empty - t) / float(empty - full) * 100.0 for t in r]
    print(name, 'rows full=%d empty=%d (%d px)' % (full, empty, empty - full))
    i = 1
    while i < N:
        a, b = fill[i - 1], fill[i]
        if b - a > 25 and b > 80:
            t = i / 10.0; j = i
            while j < N and fill[j] >= 97: j += 1
            pin = (j - i) / 10.0
            # the fall: fit %/s between 90 % and 30 % (or until the next jump)
            k = j; pts = []
            while k < N and not (fill[k] - fill[k - 1] > 25):
                if 30 <= fill[k] <= 90: pts.append((k / 10.0, fill[k]))
                k += 1
            rate = None
            if len(pts) > 5:
                n = len(pts); sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts)
                sxx = sum(p[0] ** 2 for p in pts); sxy = sum(p[0] * p[1] for p in pts)
                rate = (n * sxy - sx * sy) / (n * sxx - sx * sx)
            end = k / 10.0
            print('   t=%6.1f  >=97%% for %4.1f s   fall %s %%/s   (until %.1f: %s%%)' % (t, pin, ('%.1f' % -rate) if rate else '-', end, int(fill[k - 1])))
            i = max(j, i + 1); continue
        i += 1
