"""Record the original game's state the way runtime/record.py records
the port's, so the two can be diffed line by line.

    python3 tools/livediff/run.py <out-dir> [--seconds=60] [--host=localhost:27042]

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
    pid = dev.spawn([opts.get('package', PKG)])
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
                'rott': p.get('rott'),
                'game': p['game'],
            }) + '\n')
            stats['frames'] += 1
        else:
            print('[%s] %s' % (p.get('type'), json.dumps(p)[:160]))

    script.on('message', on_message)
    script.load()
    dev.resume(pid)
    time.sleep(seconds)
    log.close()
    print('%d frames -> %s' % (stats['frames'],
                               os.path.join(out_dir, 'state.jsonl')))
    for e in stats['errors'][:5]:
        print('script error:', e)
    return 0 if stats['frames'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
