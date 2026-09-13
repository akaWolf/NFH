"""The PC Season 1 thermometer's jumps: the second of every trick of an
episode of Badinfos' run (the mercury jumps to full as game.exe's trick
handler fires, fcn.0047bd00 — before the trick's animation), the fill just
before each jump and the gap to the previous one. A fill above the tube's
bottom means the previous trick's rage was still up (the +3 bonus); the
tube shows the top ~70 % of the bar (thermo_rows.py), so a jump within ~4 s
of the tube's emptying can still be a bonus — the HUD's bonus counter in
the frame settles it. Read for E06 (docs/PC_LAPS_DETAIL.md, 2026-09-22).

    python3 tools/pcref/thermo_jumps.py E06 [E10 ...]   (thermo.py's video)
"""
import json, os, subprocess, sys
ROOT = os.path.expanduser('~/projects/own/NFH')
V = os.path.expanduser('~/nfh-bench/pcref/pc_s1_all_720.mp4')
EPS = json.load(open(os.path.join(ROOT, 'tools/pcref/episodes_s1.json')))
def column(e, t0, t1, x=156, y0=592, h=94):
    f = '/tmp/thermo_jumps_%d.raw' % os.getpid()
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-ss', str(e['start'] + t0), '-i', V, '-t', str(t1 - t0), '-vf', 'fps=10,crop=2:%d:%d:%d' % (h, x, y0), '-f', 'rawvideo', '-pix_fmt', 'rgb24', f])
    out = open(f, 'rb').read(); os.unlink(f)
    fr = h * 6; res = []
    for i in range(len(out) // fr):
        px = [out[i * fr + y * 6: i * fr + y * 6 + 3] for y in range(h)]
        top = next((y for y in range(h) if px[y][0] > px[y][2] + 40), None)
        res.append(top)
    return res
def episode(name):
  ep = next(e for e in EPS if e['name'].startswith(name))
  r = column(ep, 0, ep['len'])
  tops = [t for t in r if t is not None]
  full = min(tops); empty = 94
  fill = [0.0 if t is None else (empty - t) / float(empty - full) * 100.0 for t in r]
  print(name, 'len %.1f full_row=%d' % (ep['len'], full))
  prev_jump = None
  i = 1
  while i < len(fill):
      a, b = fill[i - 1], fill[i]
      if b - a > 25 and b > 80:
          t = i / 10.0
          before = max(fill[max(0, i - 4):i])
          gap = (t - prev_jump) if prev_jump is not None else None
          print('jump t=%6.1f before=%5.1f%% gap=%s' % (t, before, '%.1f' % gap if gap is not None else '-'))
          prev_jump = t
          i += 5
      i += 1
  # the zero crossings after each hold
  z = [i / 10.0 for i in range(1, len(fill)) if fill[i - 1] > 3 and fill[i] <= 3]
  print('empties at', ' '.join('%.1f' % t for t in z))

for name in sys.argv[1:]:
  episode(name)
