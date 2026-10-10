"""The PC Season 1 neighbour's bubble, frame by frame: the times its icon
changes in Badinfos' run (pc_s1_all_720, 30 fps). The icon sits in a
70x22 crop at 35/600 of the 720p frame, above the neighbour's animated
face; a change is a frame whose mean difference to the one before exceeds
a threshold (10 by default), the next looked for 10 frames on. The card's
end and the first icon show as changes too. Read for E01-E03 (2026-09-30:
docs/PC_FIDELITY.md "The sofa's five sits").

    python3 tools/pcref/bubble_changes.py E02 [seconds from the start] [length]
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.expanduser('~/nfh-bench/pcref/pc_s1_all_720.mp4')
EPS = json.load(open(os.path.join(HERE, 'episodes_s1.json')))
FPS = 30
W, H, X, Y = 70, 22, 35, 600


def changes(t0, dur, threshold=10.0):
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
    ep = next(e for e in EPS if e['name'].startswith(argv[1]))
    off = float(argv[2]) if len(argv) > 2 else -1.0
    dur = float(argv[3]) if len(argv) > 3 else ep['len']
    for t, d in changes(ep['start'] + off, dur):
        print('%8.2f  (+%6.2f)  diff %5.1f' % (t, t - ep['start'], d))


if __name__ == '__main__':
    main(sys.argv)
