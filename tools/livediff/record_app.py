"""Record the port through the whole application — tutorial layer, title
cards skipped, the real click path — in runtime/record.py's schema, so a
tutorial level can be compared with the original frame for frame.

    python3 tools/livediff/record_app.py <Level> <out-dir> [--script=<file>] [--seconds=40]

Script lines: `wait <s>` and `clickitem <Item> [x y]` (the item's collider
centre — the nearest item of that name to the world point when several
share it — through the viewer's click handling — a locked tutorial item is
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
            'locked': wd.input_locked, 'frozen': wd.frozen},
        'game': {'caught': w.game.got_caught, 'ending': w.game.ending,
                 'tricks': w.game.completed},
        # StartGame's side of the clock: the title cards are over
        'started': app.cards is None or not app.cards.running,
        'routines': [{'role': r.role, 'state': r.state,
                      'item': r.item.name if r.item else None,
                      'index': r.index, 'frozen': r.frozen,
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
    if opts.get('cards'):
        # the title cards, played out: the recording's clock then runs from
        # the load, as the original's frame count does (IntroAnimation's
        # times come from the same data on both sides)
        app.tick(DT, events=(False, False, False, False))
    else:
        app.tick(DT, events=(False, True, False, False))     # the title cards skipped
    v = app.viewer

    def click_item(name, near=None):
        # several items may share a name (L113's GroundMarbles, one per
        # room): the click's recorded world point picks the nearest one
        cands = [i for i in v.level.items.values()
                 if i.name == name and i.collider is not None]
        if near is not None and cands:
            cands.sort(key=lambda i: (i.collider[0] - near[0]) ** 2
                       + (i.collider[1] - near[1]) ** 2)
        it = cands[0] if cands else None
        if it is None:
            return 'no item %s' % name
        # frame the item first, as the original's tap does (tap.py puts
        # the camera on it with CameraMover.SetFinalPosition before the
        # screen point is read): framed on Woody instead, an item across
        # the level lands off the world or under the HUD strip
        v.cam.x, v.cam.y = it.collider[0], it.collider[1]
        v._clamp_camera()
        sx, sy = v.cam.world_to_screen(it.collider[0], it.collider[1], WIDTH, HEIGHT)
        return v.handle_click(sx, sy) or 'none'

    def click_at(x, y):
        """a bare world point, the camera framed on it as click_item does"""
        v.cam.x, v.cam.y = x, y
        v._clamp_camera()
        sx, sy = v.cam.world_to_screen(x, y, WIDTH, HEIGHT)
        return v.handle_click(sx, sy) or 'none'

    log = open(os.path.join(out, 'state.jsonl'), 'w')
    # NFH_DEX_AUTOPLAY=1: every dexterity round is played to the win the
    # way dexterity.js plays it on the original — the pick steered onto the
    # field's centre each frame (run_tricks' _dex_tick), so a replay whose
    # live side ran with that tracer keeps its rounds comparable
    autoplay = os.environ.get('NFH_DEX_AUTOPLAY') == '1'
    def dex_autoplay():
        for ds in v.world.dex_states.values():
            if ds.enabled:
                ddx = (ds.bg[0] + ds.bg[2] / 2.0) - (ds.fg[0] + ds.fg[2] / 2.0)
                ddy = (ds.bg[1] + ds.bg[3] / 2.0) - (ds.fg[1] + ds.fg[3] / 2.0)
                ds.input = (ddx * 30.0, -ddy * 30.0)
    t, wait_until = 0.0, 0.0
    pending = list(steps)
    frame = 0
    start_frame = None                            # the first frame past the cards
    while t < seconds + 1e-9:
        if start_frame is None and (app.cards is None or not app.cards.running):
            start_frame = frame
        while pending and t + 1e-9 >= wait_until:
            parts = pending[0]
            if parts[0] == 'wait':
                wait_until = t + float(parts[1])
                pending.pop(0)
                break
            if parts[0] == 'at':                  # a level frame: absolute, or
                if parts[1].startswith('+'):      # `at +N` from StartGame
                    if start_frame is None or frame < start_frame + int(parts[1][1:]):
                        break
                elif frame < int(parts[1]):
                    break
                pending.pop(0)
                continue
            pending.pop(0)
            if parts[0] == 'clickitem':
                near = (float(parts[2]), float(parts[3])) if len(parts) >= 4 else None
                print('t=%6.2f f=%d clickitem %s -> %s' % (t, frame, parts[1], click_item(parts[1], near)))
            elif parts[0] == 'clickat':
                print('t=%6.2f f=%d clickat %s %s -> %s' % (t, frame, parts[1], parts[2], click_at(float(parts[1]), float(parts[2]))))
            elif parts[0] in ('select', 'deselect'):
                inv = v.world.inventory
                idx = next((i for i, e in enumerate(inv.items)
                            if parts[0] == 'select' and e['type'] == parts[1]), -1)
                inv.select(idx)
                print('t=%6.2f f=%d %s %s -> %s' % (t, frame, parts[0], parts[1] if len(parts) > 1 else '', idx))
        if autoplay:
            dex_autoplay()
        app.tick(DT, events=(False, False, False, False))
        frame += 1
        log.write(json.dumps(state(app, t)) + '\n')
        t += DT
    log.close()
    print('recorded %.1fs -> %s' % (seconds, out))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
