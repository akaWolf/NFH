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


CLICK_FRAME = 720                     # 12 s of level time


def first_take(level):
    """the first `take <Item>` leg of the level's plan whose GameObject is
    active at load — GameObject.Find, which the tap resolves through, does
    not see an inactive one (Level214's HatchFish)"""
    p = os.path.join(ROOT, 'tests', 'plans', season_of(level), level + '.txt')
    if not os.path.exists(p):
        return None
    objs = json.load(open(os.path.join(ROOT, 'levels', season_of(level), level + '.json')))['objects']
    active = {o['data']['name'] for o in objs.values()
              if o['type'] == 'GameObject' and o['data'].get('active', True)}
    for line in open(p):
        line = line.split('#')[0].strip()
        if line.startswith('take ') and line.split()[1] in active:
            return line.split()[1]
    return None


def record_clicks_port(level):
    it = first_take(level)
    if it is None:
        print('%-10s clicks: no take in the plan' % level, flush=True)
        return False
    out = os.path.join(OUT, level, 'port')
    os.makedirs(out, exist_ok=True)
    # the original's tap lands a second or two after the frame it was asked
    # for (frida, ssh, adb): its own count of the click — the frame
    # Woody.ProcessMoveInput ran — is the port's click frame, with the
    # title cards played on both sides
    frame = CLICK_FRAME
    tp = os.path.join(OUT, level, 'live', 'tap.json')
    if os.path.exists(tp):
        taps = json.load(open(tp)).get('taps') or []
        if taps:
            frame = taps[0]
    script = os.path.join(out, 'script.txt')
    with open(script, 'w') as f:
        f.write('wait %s\nclickitem %s\n' % (frame / 60.0, it))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'record_app.py'), level, out,
                        '--script=' + script, '--cards', '--seconds=%s' % (SECONDS + 10)],
                       capture_output=True, text=True, timeout=900,
                       env=dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy'))
    ok = os.path.exists(os.path.join(out, 'state.jsonl'))
    click = [l for l in r.stdout.splitlines() if 'clickitem' in l]
    print('%-10s clicks port %s %s' % (level, 'ok' if ok else 'FAILED', click[-1] if click else ''), flush=True)
    return ok


ADB_HOST = os.environ.get('NFH_ADB_HOST', '')   # '' — the bench is this host


def _relevel(level, adb=ADB_HOST):
    """walk the season's game back into a level — the app dies after a
    few LoadLevel calls in a row on the 2 GB emulator"""
    em = os.environ.get('NFH_EM', 'bash /tmp/emulator.sh')
    season = '1' if season_of(level) == 's1' else '2'
    cmd = 'NFH_SEASON=%s %s level' % (season, em)
    try:
        subprocess.run(['ssh', '-o', 'BatchMode=yes', adb, cmd] if adb else ['bash', '-c', cmd],
                       capture_output=True, text=True, timeout=200)
    except subprocess.TimeoutExpired:      # the wrapper hung on a dead emulator
        print('%-10s relevel: the wrapper timed out' % level, flush=True)


def record_clicks_live(level, adb=ADB_HOST, retry=True):
    it = first_take(level)
    if it is None:
        return False
    out = os.path.join(OUT, level, 'live')
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, NFH_PKG=PKG[season_of(level)])
    r = subprocess.run([sys.executable, os.path.join(HERE, 'run.py'), out, '--attach',
                        '--load=' + level, '--tap=%s@f%d' % (it, CLICK_FRAME),
                        '--seconds=%s' % (SECONDS + 14)] + (['--adb=' + adb] if adb else []),
                       capture_output=True, text=True, timeout=600, env=env)
    n = 0
    q = os.path.join(out, 'state.jsonl')
    if os.path.exists(q):
        n = sum(1 for _ in open(q))
    tapline = [l for l in r.stdout.splitlines() if l.startswith('tap ') or l.startswith('[tap]')]
    print('%-10s clicks live %d frames %s' % (level, n,
          tapline[-1] if tapline else 'NO TAP ' + r.stdout[-200:].replace(chr(10), ' ')), flush=True)
    # a settling emulator renders under 60 fps right after its boot and the
    # recording comes out short in frames: once, walk back in and retry
    want = int(0.8 * SECONDS * 60)
    # the title cards run ~470 frames; StartGame earlier than that means a
    # stray touch cut them, and the neighbour's routine is ahead of the
    # port's by the difference — not a comparison
    tj = os.path.join(out, 'tap.json')
    start = json.load(open(tj)).get('start') if os.path.exists(tj) else None
    if start is not None and start < 440:
        print('%-10s clicks live: the intro was cut at frame %d' % (level, start), flush=True)
        n = 0
    if n < want and retry:
        _relevel(level, adb)
        return record_clicks_live(level, adb, retry=False)
    return n >= want


PLANS = os.environ.get('NFH_PLANS', '/tmp/nfh-tricks2')   # the plan runner's --out


def plan_clicks(level):
    """the port's clicks from a plan run (tests/run_tricks.py logs them):
    rows {frame, item, type, result}, frames from play"""
    p = os.path.join(PLANS, '%s_%s' % (season_of(level), level), 'clicks.json')
    if not os.path.exists(p):
        print('%-10s replay: no %s' % (level, p), flush=True)
        return None
    rows = json.load(open(p))
    # a run restarted by the runner logs every attempt; the last one counts
    cut = 0
    for i in range(1, len(rows)):
        if rows[i]['frame'] < rows[i - 1]['frame']:
            cut = i
    return rows[cut:]


def replay_live(level, adb=ADB_HOST, retry=True):
    """the plan's clicks replayed on the original: each click on the
    frame the port made it (from StartGame), with the port's inventory
    entry in Woody's hand"""
    rows = plan_clicks(level)
    if not rows:
        return False
    until = os.environ.get('NFH_REPLAY_UNTIL')     # play frames: the clicks past it dropped
    if until:
        rows = [r for r in rows if r['frame'] <= int(until)]
    out = os.path.join(OUT, level, 'live')
    os.makedirs(out, exist_ok=True)
    clicks = os.path.join(out, 'clicks.json')
    json.dump(rows, open(clicks, 'w'))
    seconds = rows[-1]['frame'] / 60.0 + 30
    env = dict(os.environ, NFH_PKG=PKG[season_of(level)])
    mode = os.environ.get('NFH_REPLAY_MODE', 'inject')   # inject (in-process, frame-exact) or tap (adb)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'run.py'), out, '--attach',
                        '--load=' + level, '--%s=%s' % ('inject' if mode == 'inject' else 'taps', clicks),
                        '--seconds=%s' % (seconds + 14)] + (['--adb=' + adb] if adb else []),
                       capture_output=True, text=True, timeout=int(seconds) + 300, env=env)
    open(os.path.join(out, 'run.log'), 'w').write(r.stdout + r.stderr)
    n = 0
    q = os.path.join(out, 'state.jsonl')
    if os.path.exists(q):
        n = sum(1 for _ in open(q))
    tj = os.path.join(out, 'tap.json')
    tap = json.load(open(tj)) if os.path.exists(tj) else {}
    start = tap.get('start')
    planned = tap.get('planned') or []
    print('%-10s replay live %d frames, start %s, %d/%d clicks landed' % (
        level, n, start, len(planned), len(rows)), flush=True)
    if start is not None and start < 440:
        print('%-10s replay live: the intro was cut at frame %d' % (level, start), flush=True)
        n = 0
    want = int(0.8 * seconds * 60)
    if (n < want or len(planned) < len(rows)) and retry:
        _relevel(level, adb)
        return replay_live(level, adb, retry=False)
    return n >= want


def replay_port(level):
    """the port run again on the original's frames: each click on the
    frame the original acted on it (its first ProcessMoveInput at or
    after the tap), the title cards played"""
    tj = os.path.join(OUT, level, 'live', 'tap.json')
    if not os.path.exists(tj):
        print('%-10s replay port: no live tap.json' % level, flush=True)
        return False
    tap = json.load(open(tj))
    taps = sorted(tap.get('taps') or [])
    # the two clocks meet at StartGame: the original's cards run a few
    # frames more or less from run to run (Level208: 464 once, 474 the
    # next), so the port clicks at `at +N` from its own StartGame
    start = tap.get('start') or 0
    out = os.path.join(OUT, level, 'port')
    os.makedirs(out, exist_ok=True)
    lines = []
    last = 0
    planned = tap.get('planned') or []
    for k, c in enumerate(planned):
        # the original's ProcessMoveInput for this tap: the first one
        # between it and the next tap; none — the click did not land
        # there, and the port clicks on the tap's own frame
        end = planned[k + 1]['at'] if k + 1 < len(planned) else 10 ** 9
        n = next((t for t in taps if c['at'] <= t < end), None)
        if n is None and 'result' in c:
            # an injected click (inject.js) acts on its own frame; the
            # ProcessMoveInput hook does not see a call made through
            # mono_runtime_invoke, so the frame is the click's
            n = c['at'] if 'world' in c['result'] or 'stored' in c['result'] or 'unhide' in c['result'] else None
        if n is None:
            print('%-10s replay port: the original did not act on %s@%d' % (level, c.get('item') or c.get('world'), c['at']), flush=True)
            n = c['at']
        lines.append('at +%d' % (n - start))
        lines.append('select %s' % c['type'] if c.get('type') else 'deselect')
        if c.get('item') and c.get('world'):
            # the world point disambiguates a name several items share
            lines.append('clickitem %s %r %r' % (c['item'], c['world'][0], c['world'][1]))
        elif c.get('item'):
            lines.append('clickitem %s' % c['item'])
        else:
            lines.append('clickat %r %r' % (c['world'][0], c['world'][1]))
        last = n
    script = os.path.join(out, 'script.txt')
    open(script, 'w').write('\n'.join(lines) + '\n')
    seconds = tap.get('level_frames', last + 1800) / 60.0
    # a live side run with dexterity.js won its rounds by machine: the port
    # plays its rounds the same way (record_app's NFH_DEX_AUTOPLAY)
    xj = os.path.join(OUT, level, 'live', 'extra.jsonl')
    dex = os.path.exists(xj) and any('"dexterity"' in l for l in open(xj))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'record_app.py'), level, out,
                        '--script=' + script, '--cards', '--seconds=%s' % seconds],
                       capture_output=True, text=True, timeout=int(seconds) + 600,
                       env=dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
                                NFH_DEX_AUTOPLAY='1' if dex else '0'))
    open(os.path.join(out, 'run.log'), 'w').write(r.stdout + r.stderr)
    ok = os.path.exists(os.path.join(out, 'state.jsonl'))
    print('%-10s replay port %s, %d clicks' % (level, 'ok' if ok else 'FAILED', len(lines) // 3), flush=True)
    return ok


def _events(rows, tricks, caught, frame, ending=None):
    """(frame, event) of every tricks-count step, the catch, the ending"""
    ev = []
    last = 0
    got = False
    ended = False
    for r in rows:
        t = tricks(r)
        if t is not None and t != last:
            ev.append((frame(r), 'tricks %d' % t))
            last = t
        if caught(r) and not got:
            ev.append((frame(r), 'caught'))
            got = True
        if ending is not None and ending(r) and not ended:
            ev.append((frame(r), 'ending'))
            ended = True
    return ev


def replay_report(level):
    """the two sides' trick counts and catches, frame by frame"""
    live = os.path.join(OUT, level, 'live', 'state.jsonl')
    port = os.path.join(OUT, level, 'port', 'state.jsonl')
    if not (os.path.exists(live) and os.path.exists(port)):
        print('%-10s replay: missing a side' % level)
        return None
    L = [json.loads(l) for l in open(live)]
    P = [json.loads(l) for l in open(port)]
    tap = json.load(open(os.path.join(OUT, level, 'live', 'tap.json')))
    # frames from StartGame on both sides (the cards' length differs)
    ls = tap.get('start') or 0
    ps = next((i + 1 for i, r in enumerate(P) if r.get('started')), 0)
    lframe = lambda r: int(round(r['t'] * 60)) - ls         # run.py: t = n / 60
    pframe = lambda r: int(round(r['t'] * 60)) + 1 - ps
    le = _events(L, lambda r: (r.get('game') or {}).get('tricks'),
                 lambda r: (r.get('game') or {}).get('caught'), lframe,
                 lambda r: (r.get('game') or {}).get('ending'))
    pe = _events(P, lambda r: (r.get('game') or {}).get('tricks'),
                 lambda r: (r.get('game') or {}).get('caught'), pframe,
                 lambda r: (r.get('game') or {}).get('ending'))
    print('%s: StartGame at %s (port %s), frames from it; clicks %s' % (level, ls, ps,
          ' '.join('%s@%d' % (c.get('item') or 'pt', c['at'] - ls) for c in tap.get('planned') or [])))
    # Woody.Frozen (a tutorial's Freeze): the frames the clicks are dropped
    def frozen_runs(rows, get, frame):
        runs, cur = [], None
        for r in rows:
            v = get(r)
            if v and cur is None:
                cur = [frame(r), frame(r)]
            elif v and cur is not None:
                cur[1] = frame(r)
            elif not v and cur is not None:
                runs.append(tuple(cur)); cur = None
        if cur is not None:
            runs.append(tuple(cur))
        return runs
    lf = frozen_runs(L, lambda r: r.get('frozen'), lframe)
    pf = frozen_runs(P, lambda r: (r.get('woody') or {}).get('frozen'), pframe)
    if lf or pf:
        print('  frozen:   original %s, port %s' % (lf, pf))
    # the tutorial's steps: LevelScript.ActionIndex on the original, the
    # port's tutorial layer's action
    lsc = _events(L, lambda r: r.get('script'), lambda r: False, lframe)
    psc = _events(P, lambda r: (r.get('tutorial') or {}).get('action') if r.get('tutorial') else None,
                  lambda r: False, pframe)
    if lsc or psc:
        print('  script:   original %s, port %s' % (' '.join('%s@%d' % (e.split()[1], f) for f, e in lsc),
                                                     ' '.join('%s@%d' % (e.split()[1], f) for f, e in psc)))
    # the neighbour's routine: ActionManager.ActiveActionIndex steps
    def rott_index(rows, get, frame):
        out, last = [], None
        for r in rows:
            v = get(r)
            if v is not None and v != last:
                out.append('%s@%d' % (v, frame(r))); last = v
        return out
    li = rott_index(L, lambda r: (r.get('rott_action') or {}).get('index'), lframe)
    pi = rott_index(P, lambda r: next((x.get('index') for x in r.get('routines') or [] if x.get('role') == 'Rottweiler'), None), pframe)
    if li or pi:
        print('  routine:  original %s, port %s' % (' '.join(li[:40]), ' '.join(pi[:40])))
    print('  original: ' + ', '.join('%s@%d' % (e, f) for f, e in le))
    print('  port:     ' + ', '.join('%s@%d' % (e, f) for f, e in pe))
    return {'level': level, 'live': le, 'port': pe}


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
        # a click sweep aligns on the click itself: the original's tap frame
        # (tap.json, in level frames; the recording's rows run from the
        # attach) against the port's script frame — the title cards run a
        # few frames apart on the two sides, which would otherwise read as
        # a lag in every reply to the click
        # (Woody only: the neighbour's routine is the level's own clock, and
        # the port's cards end three frames before the original's — his
        # rows keep the first-move alignment of the opening sweep)
        tj = os.path.join(OUT, level, 'live', 'tap.json')
        if pawn == 'woody' and os.path.exists(tj):
            t = json.load(open(tj))
            if t.get('taps'):
                rows = sum(1 for _ in open(live))
                a = rows - t['level_frames'] + t['taps'][0]
                b = t['taps'][0]
        M = dt.passing(port, pawn)[b:]          # the port's door passes
        L, P = L[a:], P[b:]
        n = min(len(L), len(P))
        d = []
        for i in range(n):
            p, q = L[i], P[i]
            if p is None or q is None or (i < len(M) and M[i]):
                d.append(None)
                continue
            d.append(((p[0]-q[0])**2 + (p[1]-q[1])**2) ** 0.5)
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
    if cmd == 'clicks-port':
        return 0 if all([record_clicks_port(l) for l in levels]) else 1
    if cmd == 'clicks-live':
        return 0 if all([record_clicks_live(l) for l in levels]) else 1
    if cmd == 'port':
        return 0 if all(record_port(l) for l in levels) else 1
    if cmd == 'replay-live':
        return 0 if all([replay_live(l) for l in levels]) else 1
    if cmd == 'replay-port':
        return 0 if all([replay_port(l) for l in levels]) else 1
    if cmd == 'replay-report':
        return 0 if all([replay_report(l) is not None for l in levels]) else 1
    if cmd == 'replay':
        return 0 if all([replay_live(l) and replay_port(l) and replay_report(l) is not None
                         for l in levels]) else 1
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
