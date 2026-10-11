#!/usr/bin/env python3
"""The station deviations across the paired runs: every walk / stay block of the pairing (cmp_pairs.py's
`walks and stays`) whose port minus PC is two ticks or more, per level, with the station's clips — the
to-do list of the per-key profile after the departure ticks.

    python3 tools/pcoracle/stays_report.py ~/nfh-bench/runs/replay2*_park/pairs2.txt [--ticks=2]"""
import os, re, sys

def main(argv):
    thr = int(next((a[len('--ticks='):] for a in argv if a.startswith('--ticks=')), '2'))
    paths = [a for a in argv[1:] if not a.startswith('--')]
    total = []
    for p in sorted(paths):
        level = re.search(r'replay(\d+)', p); level = level.group(1) if level else p
        try:
            lines = open(os.path.expanduser(p)).read().split('\n')
        except OSError:
            continue
        # the station-to-station legs (the action starts) and the blocks, the latter for the clips' names
        i = next((k for k, l in enumerate(lines) if l.startswith('== stations (PC / port: the action')), None)
        if i is None: continue
        rows = []
        for l in lines[i + 1:]:
            if l.startswith('=='): break
            m = re.match(r'\s+([\d.]+)\s+([\d.]+) \|\s+([\d.]+)\s+([\d.]+) \| ([+-][\d.]+) \(sum ([+-][\d.]+)\)', l)
            if m:
                rows.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5)), float(m.group(6))))
        j = next((k for k, l in enumerate(lines) if 'walks and stays' in l), None)
        stays = []
        if j is not None:
            for l in lines[j + 1:]:
                if l.startswith('=='): break
                m = re.match(r'\s+([\d.]+) stay\s+([\d.]+) (.*?)\s*\|\s+([\d.]+)\s+([\d.]+) (.*?)\s*\|', l)
                if m: stays.append((float(m.group(1)), m.group(3).strip(), m.group(6).strip()))
        # the bubble pairs: the drift of the port against the PC per 100 s (the robust measure where the
        # action starts do not pair one to one)
        b = next((k for k, l in enumerate(lines) if l.startswith('== bubble')), None)
        bub = []
        if b is not None:
            for l in lines[b + 1:]:
                if l.startswith('=='): break
                m = re.match(r'\s+([\d.]+) PC (\S*)\s+([\d.]+) port (\S*)\s+([+-][\d.]+)', l)
                if m: bub.append((float(m.group(1)), float(m.group(5))))
        drift = ''
        if len(bub) >= 2 and bub[-1][0] > bub[0][0]:
            drift = ', the bubble %+.2f s over %.0f s (%+.2f s per 100 s, %d pairs)' % (bub[-1][1] - bub[0][1], bub[-1][0] - bub[0][0], (bub[-1][1] - bub[0][1]) * 100.0 / (bub[-1][0] - bub[0][0]), len(bub))
        if not rows:
            print('== %s: no station legs%s' % (level, drift)); continue
        bad = [r for r in rows if abs(r[4]) * 12 >= thr - 0.5]
        print('== %s: %d legs, %d off by %d+ ticks, the sum %+.2f s over %.0f s%s' % (level, len(rows), len(bad), thr, rows[-1][5], rows[-1][0], drift))
        for t, la, tb, lb, d, acc in bad:
            st = next((s for s in stays if abs(s[0] - t) < 0.6), None)
            clips = ('%s / %s' % (st[1][:22], st[2][:30])) if st else ''
            print('  to %7.2f: PC leg %6.2f port %6.2f %+5.2f (%+d ticks)  %s' % (t, la, lb, d, round(d * 12), clips))
            total.append((level, t, d))
    print('== %d deviations of %d+ ticks in %d levels' % (len(total), thr, len(set(l for l, *_ in total))))

if __name__ == '__main__':
    main(sys.argv)
