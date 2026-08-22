"""Record the original game's state the way runtime/record.py records
the port's, so the two can be diffed line by line.

    python3 tools/livediff/run.py <out-dir> [--seconds=60] [--host=localhost:27042]
                                 [--attach] [--tap=<Item>@<seconds> --adb=<ssh host>]

frida-server runs inside the emulator; the host reaches it through a
forwarded port (see README.md). The script spawns the game, injects
state.js and writes <out-dir>/state.jsonl — one line per GameInfo.Update,
which is the original's per-frame tick.
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = 'com.nordigames.nfh2'


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
    script = session.create_script(open(os.path.join(HERE, 'state.js')).read())

    log = open(os.path.join(out_dir, 'state.jsonl'), 'w')
    stats = {'frames': 0, 'errors': []}

    def on_message(message, data):
        if message.get('type') == 'error':
            stats['errors'].append(message.get('description'))
            return
        p = message.get('payload')
        if not isinstance(p, dict):
            return
        if p.get('type') == 'frame':
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
        time.sleep(float(at))
        import tap as tapper
        pt = tapper.resolve(session, name)
        if pt is None:
            print('tap: could not resolve %s' % name)
        else:
            print('tap %s at %d %d' % (name, pt[0], pt[1]))
            host = opts.get('adb')
            cmd = (['ssh', '-o', 'BatchMode=yes', host,
                    'bash /tmp/emulator.sh tap %d %d' % pt] if host
                   else ['adb', 'shell', 'input', 'tap', str(pt[0]), str(pt[1])])
            import subprocess
            subprocess.run(cmd, check=False, timeout=60)
        seconds = max(0.0, seconds - float(at))
    time.sleep(seconds)
    log.close()
    print('%d frames -> %s' % (stats['frames'],
                               os.path.join(out_dir, 'state.jsonl')))
    for e in stats['errors'][:5]:
        print('script error:', e)
    return 0 if stats['frames'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
