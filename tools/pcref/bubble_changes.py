"""The PC neighbour's bubble, frame by frame: the times its icon changes in
Badinfos' runs (pc_s1_all_720 / pc_nfh2_all_720, 30 fps). Season 1's icon
sits in a 70x22 crop at 35/600 of the 720p frame, Season 2's in a 110x50
crop at 40/545, above the neighbour's animated face; a change is a frame
whose mean difference to the one before exceeds a threshold (10 by
default), the next looked for 10 frames on. The card's end and the first
icon show as changes too. Read for Season 1's idle laps (2026-09-30:
docs/PC_FIDELITY.md "The sofa's five sits").

    python3 tools/pcref/bubble_changes.py E02 [seconds from the start] [length] [--s2]
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.expanduser('~/nfh-bench/pcref/pc_s1_all_720.mp4')
EPS = json.load(open(os.path.join(HERE, 'episodes_s1.json')))
V2 = os.path.expanduser('~/nfh-bench/pcref/pc_nfh2_all_720.mp4')
EPS2 = json.load(open(os.path.join(HERE, 'episodes_nfh2.json')))
FPS = 30
W, H, X, Y = 70, 22, 35, 600
W2, H2, X2, Y2 = 110, 50, 40, 545


def changes(t0, dur, threshold=10.0, s2=False):
    global V, W, H, X, Y
    if s2:
        V, W, H, X, Y = V2, W2, H2, X2, Y2
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(t0), '-t', str(dur), '-i', V,
                          '-vf', 'fps=%d,crop=%d:%d:%d:%d' % (FPS, W, H, X, Y),
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    n = len(raw) // (W * H * 3)
    f = np.frombuffer(raw[:n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3).astype(int)
    out = []
    last = -99
    for i in range(1, n):
        d = np.abs(f[i] - f[i - 1]).mean()
        if d > threshold and i - last > 10:
            out.append((round(t0 + i / FPS, 2), round(d, 1)))
            last = i
    return out


def main(argv):
    s2 = '--s2' in argv
    argv = [a for a in argv if a != '--s2']
    ep = next(e for e in (EPS2 if s2 else EPS) if e['name'].startswith(argv[1]))
    off = float(argv[2]) if len(argv) > 2 else -1.0
    dur = float(argv[3]) if len(argv) > 3 else ep['len']
    for t, d in changes(ep['start'] + off, dur, s2=s2):
        print('%8.2f  (+%6.2f)  diff %5.1f' % (t, t - ep['start'], d))


if __name__ == '__main__':
    main(sys.argv)
