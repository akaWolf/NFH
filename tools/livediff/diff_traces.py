"""Diff two state traces — the original's (tools/livediff/run.py) against
the port's (runtime/record.py) — pawn by pawn, frame by frame.

    python3 tools/livediff/diff_traces.py <live/state.jsonl> <port/state.jsonl>
        [--pawn=woody|rott] [--align=first-move|none] [--show=N]

Both traces run at 60 Hz. `--align=first-move` (the default) lines the
two up on the first frame the pawn moves, which removes the difference
in where each side's clock starts (the port's t=0 is the level load,
the original's is the first GameInfo.Update after the play button);
`--align=none` compares raw frame numbers.
"""
import json, sys


def load(path, pawn):
    out = []
    for line in open(path):
        r = json.loads(line)
        if pawn == 'woody':
            w = r.get('woody')
            p = (w['x'], w['y']) if w else None
        else:
            rt = r.get('rott')
            if isinstance(rt, list):           # the original: [x, y, z]
                p = (rt[0], rt[1]) if rt else None
            else:                              # the port: the Rottweiler's routine
                rs = [q for q in (r.get('routines') or [])
                      if q.get('role') == 'Rottweiler' and 'x' in q]
                p = (rs[0]['x'], rs[0]['y']) if rs else None
        out.append(p)
    return out


def first_move(pts):
    for i in range(1, len(pts)):
        if pts[i] is not None and pts[i - 1] is not None and pts[i] != pts[i - 1]:
            return i - 1
    return 0


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: (a.split('=', 1)[1] if '=' in a else '1')
            for a in argv if a.startswith('--')}
    if len(args) != 2:
        print(__doc__)
        return 2
    pawn = opts.get('pawn', 'rott')
    live, port = load(args[0], pawn), load(args[1], pawn)
    if opts.get('align', 'first-move') == 'first-move':
        a, b = first_move(live), first_move(port)
        print('first move: live frame %d (%.2fs), port frame %d (%.2fs)'
              % (a, a / 60.0, b, b / 60.0))
        live, port = live[a:], port[b:]
    n = min(len(live), len(port))
    dist = []
    for i in range(n):
        p, q = live[i], port[i]
        if p is None or q is None:
            dist.append(None)
            continue
        dist.append(((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5)
    valid = [d for d in dist if d is not None]
    if not valid:
        print('nothing to compare')
        return 1
    first_bad = next((i for i, d in enumerate(dist) if d is not None and d > 0.002), None)
    print('%d frames compared: mean %.4f, max %.4f, identical (<=0.002) for the first %s'
          % (len(valid), sum(valid) / len(valid), max(valid),
             'all' if first_bad is None else '%d (%.2fs)' % (first_bad, first_bad / 60.0)))
    show = int(opts.get('show', 12))
    if first_bad is not None:
        lo = max(0, first_bad - 3)
        for i in range(lo, min(n, lo + show)):
            p, q = live[i], port[i]
            print('  %5d %6.2fs live %s  port %s  d=%s' % (
                i, i / 60.0,
                '(%.3f, %.3f)' % p if p else '-', '(%.3f, %.3f)' % q if q else '-',
                '%.4f' % dist[i] if dist[i] is not None else '-'))
    return 0 if first_bad is None else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
