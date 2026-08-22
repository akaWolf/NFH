"""Scripted, deterministic recordings of the real viewer.

Drives the same Viewer the player gets (draw loop, camera, HUD, world tick),
but with a fixed 60 Hz clock and scripted input instead of wall time and the
mouse. Dumps numbered frames and a state line per frame, so a run can be
eyeballed as a strip and asserted on as data.

    python3 runtime/record.py levels/s1/Level101.json out/entrance \
        --script=tests/entrance.txt --seconds=10 --fps=4

The virtual mouse is real input: it hovers (cursor art, tooltips, hover
poses), holds buttons (the info icons) and glides between targets instead of
parking at (0,0).

Script lines (one per line, '#' comments):
    wait <seconds>
    click <screen-x> <screen-y>
    clickitem <ItemName>        # click the item's collider centre
    clickworld <wx> <wy>        # click a world position
    key sneak                   # the Tab toggle
    inv <n>                     # select inventory slot n (0 clears)
    mouse <sx> <sy>             # park the virtual cursor
    mouseitem <ItemName>        # glide the cursor onto an item
    mouseworld <wx> <wy>        # glide the cursor to a world point
    mousedown / mouseup         # hold / release the left button
    mousetour on|off            # auto-glide across items/doors each frame
    follow on|off               # the viewer's follow-camera convenience
    cam <wx> <wy>               # park the camera (viewer-side)
    pause / resume              # the Space toggle (Woody.ToggleMenu's pause)
    dex <dx> <dy>               # feed a dexterity input delta
"""
import ctypes, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sdl2

from viewer import Viewer, WIDTH, HEIGHT

DT = 1.0 / 60.0
MOUSE_SPEED = 900.0          # px/s the virtual cursor glides at


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
        self.mouse = [WIDTH / 2.0, HEIGHT / 2.0]
        self.mouse_target = None
        self.tour = False
        self._tour_stops = []
        self._tour_i = 0
        self.v.virtual_mouse = self.mouse
        self.paused = False
        self.frame_hooks = []    # fn(t, DT) after each tick — the test
                                 # layers (tests/invariants.py) ride here

    # -- scripted input ----------------------------------------------------
    def _click(self, sx, sy):
        r = self.v.handle_click(sx, sy)
        return r or 'none'

    def _screen_of_item(self, name):
        it = next((i for i in self.v.level.items.values()
                   if i.name == name), None)
        if it is None or it.collider is None:
            return None
        return self.v.cam.world_to_screen(it.collider[0], it.collider[1],
                                          WIDTH, HEIGHT)

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
            pos = self._screen_of_item(parts[1])
            r = self._click(*pos) if pos else 'no item %s' % parts[1]
        elif op == 'key' and parts[1] == 'sneak':
            v.woody.toggle_sneak()       # Woody.ToggleSneak (Woody.cs:1151)
            r = 'sneak %s' % v.woody.sneaking
        elif op == 'inv':
            v.world.inventory.select(int(parts[1]) - 1 if parts[1] != '0' else -1)
            r = 'inv'
        elif op == 'mouse':
            self.mouse_target = [float(parts[1]), float(parts[2])]
            r = 'mouse->%s,%s' % (parts[1], parts[2])
        elif op == 'mouseitem':
            pos = self._screen_of_item(parts[1])
            if pos:
                self.mouse_target = list(pos)
                r = 'mouse->%s' % parts[1]
            else:
                r = 'no item %s' % parts[1]
        elif op == 'mouseworld':
            sx, sy = v.cam.world_to_screen(float(parts[1]), float(parts[2]),
                                           WIDTH, HEIGHT)
            self.mouse_target = [sx, sy]
            r = 'mouse->world'
        elif op == 'mousedown':
            v.virtual_mouse_down = True
            r = 'down'
        elif op == 'mouseup':
            v.virtual_mouse_down = False
            r = 'up'
        elif op == 'mousetour':
            self.tour = parts[1] == 'on'
            self._tour_stops = []
            r = 'tour %s' % self.tour
        elif op == 'follow':
            v.follow = parts[1] == 'on'
            r = 'follow %s' % v.follow
        elif op == 'pause':
            self.paused = True
            r = 'paused'
        elif op == 'resume':
            self.paused = False
            r = 'resumed'
        elif op == 'cam':
            v.follow = False
            v.cam.x = float(parts[1]); v.cam.y = float(parts[2])
            r = 'cam'
        elif op == 'forcewin':
            # GameInfo.ForceWinGame (GameInfo.cs:315-321): all tricks, a 100
            # rating, Won, and WinImmediate — the finish plays at once
            v.world.game.force_win()
            r = 'forcewin'
        elif op == 'dex':
            for ds in v.world.dex_states.values():
                if ds.enabled:
                    ds.input = (ds.input[0] + float(parts[1]),
                                ds.input[1] + float(parts[2]))
            r = 'dex'
        else:
            r = 'skip'
        print('t=%6.2f %s -> %s' % (t, ' '.join(parts), r))

    def _tour_tick(self):
        """each frame the cursor glides to the next item/door on screen —
        the pass-4 rule: never park the mouse at (0,0)"""
        if not self._tour_stops:
            stops = []
            for it in self.v.level.items.values():
                if it.collider is not None and it.clickable:
                    stops.append((it.collider[0], it.collider[1]))
            for d in self.v.level.doors:
                if d.collider is not None and not d.disabled:
                    stops.append((d.collider[0], d.collider[1]))
            self._tour_stops = stops
            self._tour_i = 0
        if not self._tour_stops:
            return
        wx, wy = self._tour_stops[self._tour_i % len(self._tour_stops)]
        sx, sy = self.v.cam.world_to_screen(wx, wy, WIDTH, HEIGHT)
        if not (0 <= sx < WIDTH and 0 <= sy < HEIGHT):
            self._tour_i += 1
            return
        self.mouse_target = [sx, sy]
        if abs(self.mouse[0] - sx) < 3 and abs(self.mouse[1] - sy) < 3:
            self._tour_i += 1

    def _mouse_tick(self):
        if self.mouse_target is None:
            return
        dx = self.mouse_target[0] - self.mouse[0]
        dy = self.mouse_target[1] - self.mouse[1]
        dist = (dx * dx + dy * dy) ** 0.5
        step = MOUSE_SPEED * DT
        if dist <= step:
            self.mouse[0], self.mouse[1] = self.mouse_target
            self.mouse_target = None
        else:
            self.mouse[0] += dx / dist * step
            self.mouse[1] += dy / dist * step
        self.mouse[0] = max(6, min(WIDTH - 6, self.mouse[0]))
        self.mouse[1] = max(6, min(HEIGHT - 6, self.mouse[1]))

    # -- state -------------------------------------------------------------
    def _state(self, t):
        v = self.v
        w = v.world
        wd = v.woody
        doors = {}
        for d in v.level.doors:
            # anim None: a controller with no CurrentAnimation (an
            # IgnoreIdleAnimation door before its first pass) is not active
            if d.sprite is not None and d.sprite.anim is not None \
                    and d.sprite.anim.name != d.idle:
                doors[d.name] = d.sprite.anim.name
        faces = None
        if v.hud is not None:
            faces = {'woody': v.hud.woody_active.frame,
                     'rott': v.hud.rott_active.frame}
        hud = None
        if v.hud is not None:
            hud = {'tooltip': v.hud.tooltip,
                   'colored': v.hud.colored_tooltip,
                   'bubble': v.hud.desc_string if v.hud.show_description
                   else None,
                   'cursor': v.hud.cursor_tex}
        return {
            't': round(t, 3),
            'woody': None if wd is None else {
                'x': round(wd.sprite.x, 3), 'y': round(wd.sprite.y, 3),
                'zone': wd.zone.name if wd.zone else None,
                'state': wd.state, 'anim': wd.anim.anim.name,
                'locked': wd.input_locked, 'hidden': wd.hidden,
                'sprite_hidden': wd.sprite.hidden,
                'sneak': wd.sneaking},
            'cam': [round(v.cam.x, 3), round(v.cam.y, 3)],
            'mouse': [round(self.mouse[0]), round(self.mouse[1])],
            'doors_active': doors,
            'faces': faces,
            'hud': hud,
            'game': {'caught': w.game.got_caught, 'ending': w.game.ending,
                     'tricks': w.game.completed,
                     'time': round(w.game.time_seconds, 1)},
            'bars': [{'actor': pb.spec.get('actor'),
                      'progress': round(pb.progress, 3)}
                     for pb in getattr(w, 'progress_bars', ())
                     if pb.visible],
            'dex': [{'percent': round(ds.percent, 1)}
                    for ds in getattr(w, 'dex_states', {}).values()
                    if ds.enabled],
            'routines': [{'role': r.role,
                          'state': r.state,
                          'item': r.item.name if r.item else None,
                          'anim': r.pawn.anim.anim.name,
                          'x': round(r.pawn.sprite.x, 3),
                          'y': round(r.pawn.sprite.y, 3),
                          'zone': r.pawn.zone.name if r.pawn.zone else None}
                         for r in w.routines],
        }

    def tick(self, t):
        """one 60 Hz step of the real viewer loop: the mouse glide, the
        world tick with the stored-click replay, the camera, the draw and
        the state line — everything but the scripted-input consumption,
        so a driver (the script loop below, tests/monkey.py) can feed
        input its own way and still run the exact player loop."""
        v = self.v
        if self.tour:
            self._tour_tick()
        self._mouse_tick()
        v._frame_dt = DT
        if not self.paused and not v.world.menu_open:
            v.t += DT
            v.world.tick(DT)
            # the stored click replays once the block lifts
            w = v.woody
            if w is not None and w.stored_input is not None \
                    and not w.input_locked and not w.anim.blocking \
                    and not w.is_warping \
                    and not v.world.game.ending:
                click, w.stored_input = w.stored_input, None
                v.world_click(*click)
        v._update_camera(DT)
        if v.world.is_dexterity_on and v.woody:
            v.cam.x = v.woody.sprite.x
            v.cam.y = v.woody.sprite.y
        elif v.follow and v.woody:
            v.cam.x = v.woody.sprite.x
            v.cam.y = v.woody.sprite.y + 0.6
        v._clamp_camera()
        v.draw()
        for hook in self.frame_hooks:
            hook(t, DT)
        self.log.write(json.dumps(self._state(t)) + '\n')
        if self.frame_every is not None and t + 1e-9 >= self._next_shot:
            v.screenshot(os.path.join(self.outdir,
                                      'f%04d_t%05.2f.png'
                                      % (self._shot_i, t)))
            self._shot_i += 1
            self._next_shot += self.frame_every

    def run(self):
        t = 0.0
        self._next_shot = 0.0
        self._shot_i = 0
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
            self.tick(t)
            t += DT
        self.log.close()
        print('recorded %.1fs, %d frames -> %s' % (self.seconds,
                                                   self._shot_i,
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
    inv = None
    if 'invariants' in opts:
        sys.path.insert(0, os.path.join(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))), 'tests'))
        from invariants import Invariants
        inv = Invariants(rec.v)
        rec.frame_hooks.append(inv.frame)
    rec.run()
    if inv is not None:
        vio = inv.finish()
        json.dump(vio, open(os.path.join(args[1], 'invariants.json'), 'w'),
                  indent=1)
        for x in vio:
            print('INV %-14s %-28s %s' % (x['kind'], x['subject'],
                                          x['detail']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
