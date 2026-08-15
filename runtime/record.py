"""Scripted, deterministic recordings of the real viewer.

Drives the same Viewer the player gets (draw loop, camera, HUD, world tick),
but with a fixed 60 Hz clock and scripted input instead of wall time and the
mouse. Dumps numbered frames and a state line per frame, so a run can be
eyeballed as a strip and asserted on as data.

    python3 runtime/record.py levels/s1/Level101.json out/entrance \
        --script=tests/entrance.txt --seconds=10 --fps=4

Script lines (one per line, '#' comments):
    wait <seconds>
    click <screen-x> <screen-y>
    clickitem <ItemName>        # click the item's collider centre
    clickworld <wx> <wy>        # click a world position
    key sneak                   # the Tab toggle
    inv <n>                     # select inventory slot n (0 clears)
"""
import ctypes, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sdl2

from viewer import Viewer, WIDTH, HEIGHT

DT = 1.0 / 60.0


def parse_script(path):
    steps = []
    if not path:
        return steps
    for line in open(path):
        line = line.split('#')[0].strip()
        if not line:
            continue
        parts = line.split()
        steps.append(parts)
    return steps


class Recorder:
    def __init__(self, level_path, outdir, script=None, seconds=10.0, fps=4.0):
        os.environ.setdefault('SDL_VIDEODRIVER', 'offscreen')
        self.v = Viewer([level_path], headless=True)
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.steps = parse_script(script)
        self.seconds = seconds
        self.frame_every = 1.0 / fps if fps > 0 else None
        self.log = open(os.path.join(outdir, 'state.jsonl'), 'w')

    # -- scripted input ----------------------------------------------------
    def _click(self, sx, sy):
        v = self.v
        if v.woody is None or v.woody.input_locked or v.world.game.ending:
            return 'blocked'
        if v.hud is not None:
            consumed = v.hud.check_click(sx, sy)
            if consumed == 'restart':
                v.load(v.i)
                return 'restart'
            if consumed:
                return 'hud'
        wx, wy = v.cam.screen_to_world(sx, sy, WIDTH, HEIGHT)
        it = v._item_at(wx, wy)
        if it is not None:
            v.world.woody_use(it)
            return 'use %s' % it.name
        v.woody.start_move_flags()
        ok = v.woody.goto(wx, wy)
        return 'goto %s' % ok

    def _step(self, parts, t):
        v = self.v
        op = parts[0]
        if op == 'click':
            r = self._click(float(parts[1]), float(parts[2]))
        elif op == 'clickworld':
            sx, sy = v.cam.world_to_screen(float(parts[1]), float(parts[2]),
                                           WIDTH, HEIGHT)
            r = self._click(sx, sy)
        elif op == 'clickitem':
            it = next((i for i in v.level.items.values()
                       if i.name == parts[1]), None)
            if it is None or it.collider is None:
                r = 'no item %s' % parts[1]
            else:
                sx, sy = v.cam.world_to_screen(it.collider[0], it.collider[1],
                                               WIDTH, HEIGHT)
                r = self._click(sx, sy)
        elif op == 'key' and parts[1] == 'sneak':
            v.woody.sneak_toggle = not v.woody.sneak_toggle
            v.woody.sneaking = v.woody.sneak_toggle
            r = 'sneak %s' % v.woody.sneaking
        elif op == 'inv':
            v.world.inventory.select(int(parts[1]) - 1 if parts[1] != '0' else -1)
            r = 'inv'
        else:
            r = 'skip'
        print('t=%6.2f %s -> %s' % (t, ' '.join(parts), r))

    # -- state -------------------------------------------------------------
    def _state(self, t):
        v = self.v
        w = v.world
        wd = v.woody
        doors = {}
        for d in v.level.doors:
            if d.sprite is not None and d.sprite.anim.name != d.idle:
                doors[d.name] = d.sprite.anim.name
        faces = None
        if v.hud is not None:
            faces = {'woody': v.hud.woody_active.frame,
                     'rott': v.hud.rott_active.frame}
        return {
            't': round(t, 3),
            'woody': None if wd is None else {
                'x': round(wd.sprite.x, 3), 'y': round(wd.sprite.y, 3),
                'zone': wd.zone.name if wd.zone else None,
                'state': wd.state, 'anim': wd.anim.anim.name,
                'locked': wd.input_locked, 'hidden': wd.hidden,
                'sneak': wd.sneaking},
            'cam': [round(v.cam.x, 3), round(v.cam.y, 3)],
            'doors_active': doors,
            'faces': faces,
            'game': {'caught': w.game.got_caught, 'ending': w.game.ending,
                     'tricks': w.game.completed,
                     'time': round(w.game.time_seconds, 1)},
            'routines': [{'role': r.role,
                          'state': r.state,
                          'item': r.item.name if r.item else None,
                          'anim': r.pawn.anim.anim.name}
                         for r in w.routines],
        }

    def run(self):
        v = self.v
        t = 0.0
        next_shot = 0.0
        shot_i = 0
        pending = list(self.steps)
        wait_until = 0.0
        while t < self.seconds + 1e-9:
            while pending and t + 1e-9 >= wait_until:
                parts = pending[0]
                if parts[0] == 'wait':
                    wait_until = t + float(parts[1])
                    pending.pop(0)
                    break
                self._step(pending.pop(0), t)
            v._frame_dt = DT
            v.t += DT
            v.world.tick(DT)
            if v.follow and v.woody:
                v.cam.x = v.woody.sprite.x
                v.cam.y = v.woody.sprite.y + 0.6
            v.draw()
            self.log.write(json.dumps(self._state(t)) + '\n')
            if self.frame_every is not None and t + 1e-9 >= next_shot:
                v.screenshot(os.path.join(self.outdir,
                                          'f%04d_t%05.2f.png' % (shot_i, t)))
                shot_i += 1
                next_shot += self.frame_every
            t += DT
        self.log.close()
        print('recorded %.1fs, %d frames -> %s' % (self.seconds, shot_i,
                                                   self.outdir))


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: (a.split('=', 1)[1] if '=' in a else '1')
            for a in argv[1:] if a.startswith('--')}
    if len(args) < 2:
        print(__doc__)
        return 1
    rec = Recorder(args[0], args[1], script=opts.get('script'),
                   seconds=float(opts.get('seconds', 10)),
                   fps=float(opts.get('fps', 4)))
    rec.run()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
