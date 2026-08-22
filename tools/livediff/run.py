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
    stats = {'frames': 0, 'errors': [], 'level_frames': 0, 'last_frame_wall': 0.0}

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
            if now - stats['last_frame_wall'] > 1.0:
                stats['level_frames'] = 0
            stats['last_frame_wall'] = now
            stats['level_frames'] += 1
            # record.py's clock: the port steps a fixed 60 Hz, and the
            # original's dt is pinned to match (see README.md)
            woody = p.get('woody')
            log.write(json.dumps({
                't': round(p['n'] / 60.0, 3),
                'woody': None if not woody else {'x': round(woody[0], 3),
                                                 'y': round(woody[1], 3)},
                'locked': p.get('locked'),
                'sneak': p.get('sneak'),
                'rott': p.get('rott'),
                'game': p['game'],
            }) + '\n')
            stats['frames'] += 1
        else:
            print('[%s] %s' % (p.get('type'), json.dumps(p)[:400]))

    script.on('message', on_message)
    script.load()
    if pid is not None:
        dev.resume(pid)
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
            cmd = (['ssh', '-o', 'BatchMode=yes', host,
                    '%s tap %d %d' % ((em,) + pt)] if host
                   else ['adb', 'shell', 'input', 'tap', str(pt[0]), str(pt[1])])
            import subprocess
            subprocess.run(cmd, check=False, timeout=60)
        seconds = max(0.0, seconds - (stats['level_frames'] / 60.0
                                      if at.startswith('f') else float(at)))
    time.sleep(seconds)
    log.close()
    extra_log.close()
    print('%d frames -> %s' % (stats['frames'],
                               os.path.join(out_dir, 'state.jsonl')))
    for e in stats['errors'][:5]:
        print('script error:', e)
    return 0 if stats['frames'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
