"""The PC Season 1 thermometer (the neighbour's anger meter, bottom-left of
the 720p frame): the mercury column sampled at 10 Hz from Badinfos' run,
its full-to-empty durations per episode and the decay they imply.

python3 tools/pcref/thermo.py [video] -> one line per episode

The tube spans y 592-685 (93 px) at x 156-157; a full meter reads 89 on
that scale (the column tops out below the tube's rim), so the readings
are normalised by 89. The meter jumps to full on every trick (as the
mobile's Rottweiler.cs:611 does), holds there while the angry plays, then
falls linearly to empty: the durations are the level's constant, two to
three times faster than the mobile data's AngryMeterDecay (4.23 %/s,
23.6 s). The tick counter does not follow the mercury (ticks land with
the tube empty for up to ten seconds; docs/PC_FIDELITY.md §7), so the
rate is a drawing constant only — levels/pc/*.overlay.json carry it as
PCThermometerDrain for the HUD, the tick meter keeps the data's value.
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/nfh-bench/pcref/pc_s1_all_720.mp4')
EPS = json.load(open(os.path.join(ROOT, 'tools/pcref/episodes_s1.json')))
FULL = 89.0

def column(e, t0, t1, x=156, y0=592, h=94):
    """the mercury height per 0.1 s, normalised so a full tube is 100"""
    f = '/tmp/thermo_col_%d.raw' % os.getpid()
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(e['start'] + t0), '-i', V,
                    '-t', str(t1 - t0), '-vf', 'fps=10,crop=2:%d:%d:%d' % (h, x, y0),
                    '-f', 'rawvideo', '-pix_fmt', 'rgb24', f])
    out = open(f, 'rb').read(); os.unlink(f)
    fr = h * 6; res = []
    for i in range(len(out) // fr):
        px = [out[i * fr + y * 6: i * fr + y * 6 + 3] for y in range(h)]
        top = next((y for y in range(h) if px[y][0] > 150 and px[y][0] - px[y][2] > 60), None)
        res.append((93 - top) / 93 * 100 / FULL * 100 if top is not None else 0.0)
    return res

def full_to_empty(r):
    """seconds from the end of each full hold to the empty tube, for the
    holds whose decay runs out before the next trick"""
    N = len(r); i = 0; runs = []; holds = []
    while i < N:
        if r[i] >= 95:
            j = i
            while j < N and r[j] >= 95:
                j += 1
            if j - i >= 10:
                holds.append((j - i) / 10.0)
            m = j; ok = True
            while m < N and r[m] > 1.5:
                if r[m] > r[m - 1] + 8:
                    ok = False; break
                m += 1
            if ok and m < N and m > j:
                runs.append((m - j) / 10.0)
            i = max(m, j) + 1
            continue
        i += 1
    return runs, holds

if __name__ == '__main__':
    for e in EPS:
        runs, holds = full_to_empty(column(e, 0, e['len']))
        rate = 100 / (sum(runs) / len(runs)) if runs else None
        print('%-24s full->empty %s  decay %s %%/s  holds %s' % (
            e['name'], [round(x, 1) for x in runs][:6], '%.1f' % rate if rate else 'n/a (no clean stretch)',
            [round(h, 1) for h in holds][:8]))
