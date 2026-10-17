#!/usr/bin/env python3
"""Where a run's drift jumps: the bubble pairs of cmp_pairs.py (the HUD bubble's changes paired by name on
both sides — the one pairing that survives a tricked lap's extra sequences) read as a series of port-minus-PC
offsets; a change of the offset by `--jump` seconds or more between one bubble and the next names the
station in between — the visit (or its tricked reaction, or the walk out of it) that took longer on one
side. The steady part of the drift is reported as the median step.

    python3 tools/pcoracle/jumps_report.py ~/nfh-bench/runs/replay2*_nocatch/pairs.txt [--jump=2]"""
import os, re, sys


def bubbles(path):
    out = []; on = False
    for l in open(os.path.expanduser(path)):
        if l.startswith('== bubble'): on = True; continue
        if on and l.startswith('=='): break
        if on:
            m = re.match(r'\s+([\d.]+) PC (\S*)\s+([\d.]+) port (\S*)\s+([+-][\d.]+)', l)
            if m: out.append((float(m.group(1)), m.group(2), float(m.group(5))))
    return out


def main(argv):
    thr = float(next((a[len('--jump='):] for a in argv if a.startswith('--jump=')), '2'))
    for p in sorted(a for a in argv[1:] if not a.startswith('--')):
        level = re.search(r'replay(\d+)', p); level = level.group(1) if level else p
        b = bubbles(p)
        if len(b) < 2: print('== %s: %d bubble pairs' % (level, len(b))); continue
        steps = [b[i + 1][2] - b[i][2] for i in range(len(b) - 1)]
        med = sorted(steps)[len(steps) // 2]
        print('== %s: %d pairs, the offset %+.2f -> %+.2f s, the median step %+.2f s' % (level, len(b), b[0][2], b[-1][2], med))
        for i, d in enumerate(steps):
            if abs(d) >= thr:
                print('  %7.2f %-16s -> %7.2f %-16s %+6.2f s  (the port %s between: the %s visit, its reaction or the walk on)' % (
                    b[i][0], b[i][1], b[i + 1][0], b[i + 1][1], d, 'longer' if d > 0 else 'shorter', b[i][1]))


if __name__ == '__main__':
    main(sys.argv)
