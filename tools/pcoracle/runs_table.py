#!/usr/bin/env python3
"""One line per level for a tag's runs on the original against the port's replays: the legs the plan ran on
the PC (the oracle's `plan:` line), the PC's catches or would-be catches the port has within two seconds,
the bubble drift per 100 s and the drift's jumps (jumps_report.py) — the state of a season at a glance.

    python3 tools/pcoracle/runs_table.py nocatch 101 102 ... [--jump=2]"""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref')); sys.path.insert(0, HERE)
import canon, jumps_report


def main(argv):
    tag = argv[1]; thr = next((a[len('--jump='):] for a in argv if a.startswith('--jump=')), '2')
    levels = [int(a) for a in argv[2:] if not a.startswith('--')]
    bench = os.path.expanduser('~/nfh-bench')
    for n in levels:
        folder = canon.pc_level(n)['folder']; logs = 'logs1' if n < 200 else 'logs'; season = 's1' if n < 200 else 's2'
        olog = os.path.join(bench, 'wine', logs, 'oracle%d_%s.log' % (n, tag))
        plan = ''
        try:
            for l in open(olog):
                if l.startswith('plan:'):
                    m = re.match(r'plan: (\d+)/(\d+) legs', l); plan = '%s/%s legs' % (m.group(1), m.group(2)) if m else l[:20]
        except OSError:
            print('%d: no %s run' % (n, tag)); continue
        run = os.path.join(bench, 'runs', 'replay%d_%s' % (n, tag)); pairs = os.path.join(run, 'pairs.txt')
        trace = os.path.join(bench, 'wine', logs, 'oracle_%s_%s.jsonl' % (folder, tag))
        catches = ''
        if os.path.isdir(os.path.join(run, '%s_Level%d' % (season, n))):
            out = subprocess.run([sys.executable, os.path.join(HERE, 'catch_report.py'), str(n), trace, os.path.join(run, '%s_Level%d' % (season, n))],
                                 capture_output=True, text=True).stdout
            pc = out.count('== PC catch'); hit = out.count('the port would catch within 2 s: [')
            extra = re.search(r'the PC would not \(within 2 s\): (\[.*?\]|none)', out)
            catches = 'catches %d, the port within 2 s %d%s' % (pc, hit, (', the port alone ' + extra.group(1)) if extra and extra.group(1) != 'none' else '')
        drift = ''; jumps = ''
        if os.path.exists(pairs):
            b = jumps_report.bubbles(pairs)
            if len(b) >= 2 and b[-1][0] > b[0][0]:
                drift = 'bubble %+.2f s/100 s (%d pairs)' % ((b[-1][2] - b[0][2]) * 100.0 / (b[-1][0] - b[0][0]), len(b))
                steps = [b[i + 1][2] - b[i][2] for i in range(len(b) - 1)]
                jumps = ', '.join('%s %+.1f' % (b[i][1], d) for i, d in enumerate(steps) if abs(d) >= float(thr))
                jumps = ('jumps: ' + jumps) if jumps else 'no jump'
        print('%d %-14s %-12s %-40s %-32s %s' % (n, folder, plan, catches, drift, jumps))


if __name__ == '__main__':
    main(sys.argv)
