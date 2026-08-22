"""The sweep: every level's opening, original against port, no input.

    python3 tools/livediff/sweep.py port  [levels...]   # record the port (record_app.py)
    python3 tools/livediff/sweep.py live  [levels...]   # record the original (run.py --load)
    python3 tools/livediff/sweep.py diff  [levels...]   # diff_traces per pawn, a table

Levels default to every Level1xx/2xx in levels/. Output under
$NFH_SWEEP (default /tmp/nfh-sweep): <Level>/port/state.jsonl,
<Level>/live/state.jsonl, and report.md / report.json from `diff`.
The original side needs the game of that season running on the bench
(tools/livediff/emulator.sh up) and the frida tunnel on 27042.
"""
import glob, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.environ.get('NFH_SWEEP', '/tmp/nfh-sweep')
SECONDS = float(os.environ.get('NFH_SWEEP_SECONDS', '60'))
PKG = {'s1': 'com.nordigames.nfh', 's2': 'com.nordigames.nfh2'}


def season_of(level):
    return 's2' if level.startswith('Level2') else 's1'


def all_levels():
    out = []
    for season in ('s1', 's2'):
        for p in sorted(glob.glob(os.path.join(ROOT, 'levels', season, 'Level*.json'))):
            out.append(os.path.splitext(os.path.basename(p))[0])
    return out


def record_port(level):
    out = os.path.join(OUT, level, 'port')
    os.makedirs(out, exist_ok=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'record_app.py'), level, out,
                        '--seconds=%s' % SECONDS],
                       capture_output=True, text=True, timeout=900,
                       env=dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy'))
    ok = os.path.exists(os.path.join(out, 'state.jsonl'))
    print('%-10s port %s' % (level, 'ok' if ok else 'FAILED\n' + r.stdout[-400:] + r.stderr[-400:]), flush=True)
    return ok


def record_live(level):
    out = os.path.join(OUT, level, 'live')
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, NFH_PKG=PKG[season_of(level)])
    # the title cards take ~8 s of the budget; frames only count in-level
    r = subprocess.run([sys.executable, os.path.join(HERE, 'run.py'), out, '--attach',
                        '--load=' + level, '--seconds=%s' % (SECONDS + 14)],
                       capture_output=True, text=True, timeout=600, env=env)
    n = 0
    p = os.path.join(out, 'state.jsonl')
    if os.path.exists(p):
        n = sum(1 for _ in open(p))
    print('%-10s live %d frames %s' % (level, n, '' if n > 600 else 'SHORT\n' + r.stdout[-300:] + r.stderr[-300:]), flush=True)
    return n > 600


def diff(level):
    sys.path.insert(0, HERE)
    import diff_traces as dt
    live = os.path.join(OUT, level, 'live', 'state.jsonl')
    port = os.path.join(OUT, level, 'port', 'state.jsonl')
    if not (os.path.exists(live) and os.path.exists(port)):
        return {'level': level, 'missing': True}
    row = {'level': level}
    for pawn in ('rott', 'woody'):
        L, P = dt.load(live, pawn), dt.load(port, pawn)
        if not any(L) or not any(P):
            row[pawn] = None
            continue
        a, b = dt.first_move(L), dt.first_move(P)
        L, P = L[a:], P[b:]
        n = min(len(L), len(P))
        d = []
        for i in range(n):
            p, q = L[i], P[i]
            d.append(None if p is None or q is None else ((p[0]-q[0])**2 + (p[1]-q[1])**2) ** 0.5)
        v = [x for x in d if x is not None]
        if not v:
            row[pawn] = None
            continue
        first_bad = next((i for i, x in enumerate(d) if x is not None and x > 0.002), None)
        big = [i for i, x in enumerate(d) if x is not None and x > 0.05]
        row[pawn] = {'frames': len(v), 'mean': round(sum(v) / len(v), 4), 'max': round(max(v), 3),
                     'identical': first_bad if first_bad is not None else len(v),
                     'over05': len(big), 'first_over05_s': round(big[0] / 60.0, 2) if big else None}
    return row


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, levels = argv[0], argv[1:] or all_levels()
    if cmd == 'port':
        return 0 if all(record_port(l) for l in levels) else 1
    if cmd == 'live':
        return 0 if all([record_live(l) for l in levels]) else 1
    if cmd == 'diff':
        rows = [diff(l) for l in levels]
        os.makedirs(OUT, exist_ok=True)
        json.dump(rows, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
        lines = ['| level | pawn | frames | mean | max | identical | >0.05 | first >0.05 |',
                 '|---|---|---|---|---|---|---|---|']
        for r in rows:
            if r.get('missing'):
                lines.append('| %s | — | missing | | | | | |' % r['level'])
                continue
            for pawn in ('rott', 'woody'):
                x = r.get(pawn)
                if x is None:
                    lines.append('| %s | %s | — | | | | | |' % (r['level'], pawn))
                    continue
                lines.append('| %s | %s | %d | %.4f | %.3f | %d | %d | %s |' % (
                    r['level'], pawn, x['frames'], x['mean'], x['max'], x['identical'], x['over05'],
                    '' if x['first_over05_s'] is None else '%.2fs' % x['first_over05_s']))
        open(os.path.join(OUT, 'report.md'), 'w').write('\n'.join(lines) + '\n')
        print('\n'.join(lines))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
