"""Record the port through the whole application — tutorial layer, title
cards skipped, the real click path — in runtime/record.py's schema, so a
tutorial level can be compared with the original frame for frame.

    python3 tools/livediff/record_app.py <Level> <out-dir> [--script=<file>] [--seconds=40]

Script lines: `wait <s>` and `clickitem <Item>` (the item's collider
centre, through the viewer's click handling — a locked tutorial item is
ignored here as it is in the game).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

DT = 1.0 / 60.0


def state(app, t):
    v = app.viewer
    w = v.world
    wd = v.woody
    return {
        't': round(t, 3),
        'woody': None if wd is None else {
            'x': round(wd.sprite.x, 3), 'y': round(wd.sprite.y, 3),
            'zone': wd.zone.name if wd.zone else None,
            'state': wd.state, 'anim': wd.anim.anim.name,
            'locked': wd.input_locked},
        'game': {'caught': w.game.got_caught, 'ending': w.game.ending,
                 'tricks': w.game.completed},
        'routines': [{'role': r.role, 'state': r.state,
                      'item': r.item.name if r.item else None,
                      'anim': r.pawn.anim.anim.name,
                      'x': round(r.pawn.sprite.x, 3),
                      'y': round(r.pawn.sprite.y, 3),
                      'zone': r.pawn.zone.name if r.pawn.zone else None,
                      'pstate': r.pawn.state}
                     for r in w.routines],
        'tutorial': None if app.tutorial is None else {
            'active': app.tutorial.active,
            'action': app.tutorial.action_index},
    }


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: (a.split('=', 1)[1] if '=' in a else '1')
            for a in argv if a.startswith('--')}
    if len(args) != 2:
        print(__doc__)
        return 2
    level, out = args
    os.makedirs(out, exist_ok=True)
    steps = []
    if opts.get('script'):
        for line in open(opts['script']):
            line = line.split('#')[0].strip()
            if line:
                steps.append(line.split())
    seconds = float(opts.get('seconds', 40))

    from prefs import MemoryPrefs
    from menu import GameIntroAnimation
    from app import App
    from viewer import WIDTH, HEIGHT
    GameIntroAnimation.finished = False
    app = App(headless=True, prefs=MemoryPrefs())
    app.load_level(level)
    app.tick(DT, events=(False, True, False, False))     # the title cards
    v = app.viewer

    def click_item(name):
        it = next((i for i in v.level.items.values() if i.name == name), None)
        if it is None or it.collider is None:
            return 'no item %s' % name
        # frame Woody first, as the game's camera does once the cards are
        # over — parked on the neighbour, the click lands off the world
        if v.woody is not None:
            v.cam.x, v.cam.y = v.woody.sprite.x, v.woody.sprite.y + 0.6
            v._clamp_camera()
        sx, sy = v.cam.world_to_screen(it.collider[0], it.collider[1], WIDTH, HEIGHT)
        return v.handle_click(sx, sy) or 'none'

    log = open(os.path.join(out, 'state.jsonl'), 'w')
    t, wait_until = 0.0, 0.0
    pending = list(steps)
    while t < seconds + 1e-9:
        while pending and t + 1e-9 >= wait_until:
            parts = pending[0]
            if parts[0] == 'wait':
                wait_until = t + float(parts[1])
                pending.pop(0)
                break
            pending.pop(0)
            if parts[0] == 'clickitem':
                print('t=%6.2f clickitem %s -> %s' % (t, parts[1], click_item(parts[1])))
        app.tick(DT, events=(False, False, False, False))
        log.write(json.dumps(state(app, t)) + '\n')
        t += DT
    log.close()
    print('recorded %.1fs -> %s' % (seconds, out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
