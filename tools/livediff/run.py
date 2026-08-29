"""Record the original game's state the way runtime/record.py records
the port's, so the two can be diffed line by line.

    python3 tools/livediff/run.py <out-dir> [--seconds=60] [--host=localhost:27042]
                                 [--attach] [--load=<SceneName>]
                                 [--tap=<Item>@<seconds> --adb=<ssh host>]

frida-server runs inside the emulator; the host reaches it through a
forwarded port (see README.md). The script spawns the game, injects
state.js and writes <out-dir>/state.jsonl — one line per GameInfo.Update,
which is the original's per-frame tick.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PKG = os.environ.get('NFH_PKG', 'com.nordigames.nfh2')   # Season 1: com.nordigames.nfh


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: (a.split('=', 1)[1] if '=' in a else '1')
            for a in argv if a.startswith('--')}
    if not args:
        print(__doc__)
        return 2
    out_dir = args[0]
    os.makedirs(out_dir, exist_ok=True)
    seconds = float(opts.get('seconds', 60))
    host = opts.get('host', 'localhost:27042')

    import frida
    dev = frida.get_device_manager().add_remote_device(host)
    pkg = opts.get('package', PKG)
    pid = None
    if 'attach' in opts:
        # ride an already-running game: the menus have to be walked
        # before GameInfo exists at all
        # on Android frida names a process by its application label,
        # so the package has to be looked up among the applications
        live = [a for a in dev.enumerate_applications()
                if a.identifier == pkg and a.pid]
        if not live:
            print('%s is not running' % pkg)
            return 2
        session = dev.attach(live[0].pid)
    else:
        pid = dev.spawn([pkg])
        session = dev.attach(pid)
    js = open(os.path.join(HERE, 'state.js')).read()
    # --load=<scene>: Application.LoadLevel from the player's thread before
    # recording (an empty name leaves the running level alone)
    js = js.replace('LOAD_LEVEL_NAME', opts.get('load', ''))
    # --extra=<file.js> [--role=<Pawn class>]: a second tracer (steps.js,
    # clock.js ...) in the same session — a second frida client on the
    # process has taken the game down; its own messages (no 'type') go to
    # extra.jsonl
    if 'extra' in opts:
        extra = open(os.path.join(HERE, opts['extra'])).read()
        js += "\n;(function () { const ROLE = %s;\n%s\n})();\n" % (
            json.dumps(opts.get('role', 'Rottweiler')), extra)
    script = session.create_script(js)

    log = open(os.path.join(out_dir, 'state.jsonl'), 'w')
    extra_log = open(os.path.join(out_dir, 'extra.jsonl'), 'w')
    stats = {'frames': 0, 'errors': [], 'level_frames': 0, 'last_frame_wall': 0.0, 'taps': []}

    def on_message(message, data):
        if message.get('type') == 'error':
            stats['errors'].append(message.get('description'))
            return
        p = message.get('payload')
        if not isinstance(p, dict):
            return
        if 'type' not in p:               # the --extra tracer's rows
            extra_log.write(json.dumps(p) + '\n')
            return
        if p.get('type') == 'frame':
            # frames arrive only while a level runs: a gap of over a second
            # is the load, and the counter after it is level time
            now = time.time()
            # ...but only until StartGame: a stall mid-level (the emulator
            # pausing over a second) must not restart the count the taps are
            # scheduled on (Level206's replay burst its last 25 clicks)
            if now - stats['last_frame_wall'] > 1.0 and stats.get('start') is None:
                stats['level_frames'] = 0
            stats['last_frame_wall'] = now
            stats['level_frames'] += 1
            # the frame StartGame let the neighbour go (the title cards
            # played out, or cut short by a stray touch)
            if p.get('start') and stats.get('start') is None:
                stats['start'] = stats['level_frames']
            # record.py's clock: the port steps a fixed 60 Hz, and the
            # original's dt is pinned to match (see README.md)
            woody = p.get('woody')
            log.write(json.dumps({
                't': round(p['n'] / 60.0, 3),
                'woody': None if not woody else {'x': round(woody[0], 3),
                                                 'y': round(woody[1], 3)},
                'locked': p.get('locked'),
                'frozen': p.get('frozen'),
                'sneak': p.get('sneak'),
                'msleep': p.get('msleep'),      # Mother.IsSleeping (the sleep bars)
                'rsleep': p.get('rsleep'),      # Rottweiler.IsSleeping
                'rott': p.get('rott'),
                'mother': p.get('mother'),
                'rott_action': p.get('rott_action'),
                'olga': p.get('olga'),
                'olga_action': p.get('olga_action'),
                'cam': p.get('cam'),
                'script': p.get('script'),
                'game': p['game'],
            }) + '\n')
            stats['frames'] += 1
        elif p.get('type') == 'tap':
            # the original's own count runs from its attach; the level's
            # count restarts at the load (see the frame branch)
            n = p['n'] - (stats['frames'] - stats['level_frames'])
            stats['taps'].append(n)
            print('[tap] level frame %d' % n)
        else:
            print('[%s] %s' % (p.get('type'), json.dumps(p)[:400]))

    script.on('message', on_message)
    script.load()
    if pid is not None:
        dev.resume(pid)
    # no frames within 20 s means no level is running (a menu, a score
    # screen): there is nothing to record, and the sweep's retry walks the
    # game back into a level sooner
    for _ in range(400):
        if stats['frames']:
            break
        time.sleep(0.05)
    else:
        print('no frames: the game is not in a level')
        log.close(); extra_log.close()
        return 1
    inject = opts.get('inject')            # a plan's clicks injected in-process
    if inject:                             # (inject.js), frame-exact
        import invtypes, re
        types = invtypes.load()
        anims = [l.strip().rstrip(',') for l in open(os.path.join(ROOT, 'src', 'Assembly-CSharp', 'AnimationState.cs'))
                 if re.match(r'^\s*[A-Za-z0-9_]+,?\s*$', l) and l.strip() not in ('{', '}')]
        anim_id = {n: i for i, n in enumerate(anims)}
        rows = []
        for r in json.load(open(inject)):
            if not r.get('world'):
                continue
            rows.append({'f': int(r['frame']), 'w': [float(r['world'][0]), float(r['world'][1])],
                         't': types.get(r['type'], -1) if r.get('type') else -1,
                         'item': r.get('item'), 'typeName': r.get('type')})
        rows.sort(key=lambda r: r['f'])
        js = open(os.path.join(HERE, 'inject.js')).read()
        js = js.replace('ROWS_JSON', json.dumps(rows)).replace('ANIM_RUN_UP', str(anim_id['Run_Up'])) \
               .replace('ANIM_WALK_UP', str(anim_id['Walk_Up'])).replace('ANIM_HIDE_IN', str(anim_id['Hide_In']))
        def on_inject(message, data):
            p = message.get('payload')
            if isinstance(p, dict) and 'injected' in p:
                q = p['injected']
                stats.setdefault('planned', []).append({'want': q['want'], 'at': q['at'], 'item': q.get('item'),
                                                        'type': q.get('typeName'), 'world': q['world'], 'result': q['result']})
                print('[inject] frame %d (%d) %s with %s -> %s' % (q['want'], q['at'], q.get('item') or q['world'], q.get('typeName'), q['result']), flush=True)
            elif isinstance(p, dict) and 'inject' in p:
                print('[inject] %s' % json.dumps(p)[:300], flush=True)
            elif message.get('type') == 'error':
                print('[inject error] %s' % message.get('description'), flush=True)
        inj = session.create_script(js)
        inj.on('message', on_inject)
        inj.load()
        last = rows[-1]['f'] if rows else 0
        deadline = time.time() + seconds
        while stats.get('start') is None and time.time() < deadline:
            time.sleep(0.05)
        want_end = (stats.get('start') or 0) + last + 1800     # 30 s past the last click
        while stats['level_frames'] < want_end and time.time() < deadline:
            time.sleep(0.05)
        seconds = max(0.0, deadline - time.time())
    taps = opts.get('taps')                # a plan's clicks replayed: JSON rows
    if taps:                               # {frame, item, type}, frames from play
        import tap as tapper
        import invtypes
        types = invtypes.load()
        rows = json.load(open(taps))
        host = opts.get('adb')
        em = os.environ.get('NFH_EM', 'bash /tmp/emulator.sh')
        deadline = time.time() + seconds
        # the runner's clock runs from play; the original's level frames
        # from the load — StartGame (the neighbour's CanStart) is the offset
        while stats.get('start') is None and time.time() < deadline:
            time.sleep(0.05)
        start = stats.get('start') or 0
        print('[taps] StartGame at level frame %d, %d clicks' % (start, len(rows)))
        for row in rows:
            want = start + int(row['frame'])
            while stats['level_frames'] < want and time.time() < deadline:
                time.sleep(0.02)
            sel = types.get(row.get('type')) if row.get('type') else -1
            try:
                pt = tapper.resolve(session, row.get('item'), select=sel, world=row.get('world'))
            except Exception as e:          # the game died under the run: keep what landed
                print('[taps] frame %d: %s — the rest of the clicks dropped' % (want, e))
                break
            if pt is None:
                print('[taps] frame %d: could not resolve %s' % (want, row.get('item') or row.get('world')))
                continue
            print('[taps] frame %d (%d) %s with %s at %d %d' % (want, stats['level_frames'], row.get('item') or row.get('world'), row.get('type'), pt[0], pt[1]))
            stats.setdefault('planned', []).append({'want': want, 'at': stats['level_frames'],
                                                    'item': row.get('item'), 'type': row.get('type'),
                                                    'world': row.get('world')})
            cmd = (['ssh', '-o', 'BatchMode=yes', host, '%s tap %d %d' % (em, pt[0], pt[1])] if host
                   else ['bash', '-c', '%s tap %d %d' % (em, pt[0], pt[1])] if 'NFH_EM' in os.environ
                   else ['adb', 'shell', 'input', 'tap', str(pt[0]), str(pt[1])])
            import subprocess
            subprocess.run(cmd, check=False, timeout=60)
        seconds = max(0.0, deadline - time.time())
    tap = opts.get('tap')                  # Item@seconds: click it mid-run,
    if tap:                                # through this same session
        name, at = tap.split('@')
        if at.startswith('f'):
            # Item@f<N>: the tap on the level's frame N — the same game
            # moment on every run, load time notwithstanding
            want = int(at[1:])
            deadline = time.time() + seconds
            while stats['level_frames'] < want and time.time() < deadline:
                time.sleep(0.05)
        else:
            time.sleep(float(at))
        import tap as tapper
        pt = tapper.resolve(session, name)
        if pt is None:
            print('tap: could not resolve %s' % name)
        else:
            # the item's runtime transform position rides along — the
            # scene file's is not always where the original keeps it
            print('tap %s at %d %d (world %s)' % (name, pt[0], pt[1],
                  [round(v, 3) for v in (pt[2] or [])]))
            pt = pt[:2]
            host = opts.get('adb')
            em = os.environ.get('NFH_EM', 'bash /tmp/emulator.sh')
            # the bench may be this very host (NFH_EM set, no --adb): the
            # tap runs through the same entry locally
            cmd = (['ssh', '-o', 'BatchMode=yes', host,
                    '%s tap %d %d' % ((em,) + pt)] if host
                   else ['bash', '-c', '%s tap %d %d' % ((em,) + pt)] if 'NFH_EM' in os.environ
                   else ['adb', 'shell', 'input', 'tap', str(pt[0]), str(pt[1])])
            import subprocess
            subprocess.run(cmd, check=False, timeout=60)
        seconds = max(0.0, seconds - (stats['level_frames'] / 60.0
                                      if at.startswith('f') else float(at)))
    time.sleep(seconds)
    log.close()
    extra_log.close()
    json.dump({'taps': stats['taps'], 'level_frames': stats['level_frames'], 'planned': stats.get('planned', []),
               'start': stats.get('start')},
              open(os.path.join(out_dir, 'tap.json'), 'w'))
    print('%d frames -> %s' % (stats['frames'],
                               os.path.join(out_dir, 'state.jsonl')))
    for e in stats['errors'][:5]:
        print('script error:', e)
    return 0 if stats['frames'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
