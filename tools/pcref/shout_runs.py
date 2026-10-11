#!/usr/bin/env python3
"""Season 1: the neighbour's shout icon (bubble_wut) in Badinfos' run against
a port run's — each run of the icon from its appearance to the next icon, the
tricked reaction's tail (the shout, what the case plays after it, the repair,
a walk back, up to the next case's ICON).

    python3 tools/pcref/shout_runs.py <run under ~/nfh-bench/runs> <level>

The video's icon by template (E08's `wut` at 175.0 s of the episode, the
64x30 icon crop at 20/600 of the 720p frame, a mean difference under 25),
its runs of more than six frames at 30 fps, in level time (the episode's
offset of tools/pcref/thermo_jumps.py's comparisons); the port's from the
run's state.jsonl (hud.think), with the icon before each. Read on
2026-10-11 over the fourteen plans: within 0.2 s wherever the video shows
the same trick (runtime/README.md, "The PC profile's walk-by with a clip of
its own")."""
import json
import os
import subprocess
import sys

import numpy as np

V = os.path.expanduser('~/nfh-bench/pcref/pc_s1_all_720.mp4')
HERE = os.path.dirname(os.path.abspath(__file__))
EPS = json.load(open(os.path.join(HERE, 'episodes_s1.json')))
OFF = {101: -0.90, 102: -0.93, 103: -1.73, 104: -1.80, 105: -1.70, 106: -2.33, 107: -1.67,
       108: -1.73, 109: -1.95, 110: -1.27, 111: -2.10, 112: -2.10, 113: -1.30, 114: -2.70}
CROP, W, H = '64:30:20:600', 64, 30


def grab(t, d, fps):
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-ss', str(t), '-t', str(d), '-i', V,
                          '-vf', 'fps=%g,crop=%s' % (fps, CROP), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    k = len(raw) // (W * H * 3)
    return np.frombuffer(raw[:k * W * H * 3], dtype=np.uint8).reshape(k, H, W, 3).astype(float)


def video_runs(n, thr=25.0):
    ref = grab(EPS[7]['start'] + 175.0, 0.04, 25)[0]
    ep = EPS[n - 101]
    frames = grab(ep['start'], ep['len'], 30)
    isw = np.abs(frames - ref).mean(axis=(1, 2, 3)) < thr
    out = []
    i = 0
    while i < len(isw):
        if isw[i]:
            j = i
            while j < len(isw) and isw[j]:
                j += 1
            if j - i > 6:
                out.append((i / 30.0 + OFF[n], (j - i) / 30.0))
            i = j
        else:
            i += 1
    return out


def port_runs(run, n):
    out = []
    last = cur = None
    for line in open(os.path.expanduser('~/nfh-bench/runs/%s/s1_Level%d/state.jsonl' % (run, n))):
        s = json.loads(line)
        th = s['hud'].get('think')
        if th == 'bubble_wut' and last != 'bubble_wut':
            cur = [s['t'], None, last]
        if th != 'bubble_wut' and last == 'bubble_wut' and cur:
            cur[1] = s['t']
            out.append((cur[0], cur[1] - cur[0], cur[2]))
            cur = None
        last = th
    return out


def main(argv):
    run, n = argv[1], int(argv[2])
    print('video:', ' '.join('%.2f/%.2f' % r for r in video_runs(n)))
    print('port: ', ' '.join('%.2f/%.2f(%s)' % (a, b, (p or '')[7:15]) for a, b, p in port_runs(run, n)))


if __name__ == '__main__':
    main(sys.argv)
