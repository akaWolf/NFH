"""Level viewer — draws an exported level with the game's own rendering model.

    NFH_TEXTURES=/path/to/pngs python3 runtime/viewer.py levels/s1/Level101.json

Keys: left/right pan, [ ] switch level, Z zones, D depth order, Space pause,
      S screenshot, Esc quit.
"""
import ctypes, os, sys, glob, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sdl2

from scene import Level, DESIGN_H
from world import World
from audio_out import SoundBank
from render import Camera, TextureCache, draw_sprite, draw_quad, draw_zone_overlay
from hud import Hud

WIDTH, HEIGHT = 800, 600


def texture_dirs(level_paths=()):
    env = os.environ.get('NFH_TEXTURES')
    dirs = env.split(':') if env else []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # season-specific dirs; the season of the opened levels wins name clashes
    seasons = ['s1', 's2']
    if any('/s2/' in p.replace('\\', '/') for p in level_paths):
        seasons.reverse()
    for s in seasons:
        dirs.append(os.path.join(root, 'textures', s))
    dirs.append(os.path.join(root, 'textures'))
    return dirs


class Viewer:
    def __init__(self, level_paths, start=0, headless=False):
        self.paths = level_paths
        self.i = start
        self.headless = headless
        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
        flags = sdl2.SDL_WINDOW_HIDDEN if headless else sdl2.SDL_WINDOW_SHOWN
        self.win = sdl2.SDL_CreateWindow(b'NFH viewer',
                                         sdl2.SDL_WINDOWPOS_CENTERED,
                                         sdl2.SDL_WINDOWPOS_CENTERED,
                                         WIDTH, HEIGHT, flags)
        self.rnd = sdl2.SDL_CreateRenderer(
            self.win, -1, sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC)
        self.cache = TextureCache(self.rnd, texture_dirs(level_paths))
        self.sounds = None if headless else SoundBank.try_open()
        self.cam = Camera()
        self.show_zones = False
        self.paused = False
        self._frame_dt = 0.0
        self.follow = False
        self.woody = None
        self.t = 0.0
        self.load(self.i)

    def load(self, i):
        self.i = i % len(self.paths)
        self.level = Level(self.paths[self.i])
        self.world = World(self.level, sound_sink=self.sounds.play if self.sounds else None)
        for role in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
            self.world.spawn_pawn(role)
        self.woody = self.world.pawns.get('Woody')
        self.world.woody = self.woody
        self.world.start_routines()
        bg = self.level.background
        self.cam.x = bg[1] if bg else 0.0
        self.cam.y = bg[2] if bg else 0.0
        self.follow = bool(self.woody)
        self.t = 0.0
        self.hud = Hud(self.level, self.world, self.cache, self.rnd,
                       WIDTH, HEIGHT) if self.level.hud else None
        if self.hud is not None:
            # Woody.PlayTrickDone -> the HUD celebration
            self.world.game.on_trick_done = self.hud.play_trick_done
            self.hud.cam = self.cam       # the world-anchored progress bars
        print('%s — %d sprites, %d zones, %d items, %d routines (%d actions)'
              % (self.level.name, len(self.level.sprites), len(self.level.zones),
                 len(self.level.items), len(self.world.routines),
                 sum(len(r.actions) for r in self.world.routines)))

    def _clamp_camera(self):
        """CameraMover clamps the viewport corners to the level bounds
        (CameraMover.cs:378-394) — the camera never shows past the house."""
        b = self.level.camera_bounds
        if not b:
            return
        min_x, max_x, min_y, max_y = b
        half_h = self.cam.size
        half_w = self.cam.size * WIDTH / float(HEIGHT)
        if max_x - min_x >= 2 * half_w:
            self.cam.x = max(min_x + half_w, min(max_x - half_w, self.cam.x))
        else:
            self.cam.x = (min_x + max_x) * 0.5
        if max_y - min_y >= 2 * half_h:
            self.cam.y = max(min_y + half_h, min(max_y - half_h, self.cam.y))
        else:
            self.cam.y = (min_y + max_y) * 0.5

    def _item_at(self, wx, wy):
        """click hit-test against the items' BoxColliders; a disabled
        collider (the Pipe hack) takes no clicks, and CanUse gates the
        destination the way Pawn.GetMoveDestination does (Pawn.cs:598)"""
        for it in self.level.items.values():
            c = it.collider
            if c is None or not it.clickable or not it.can_use:
                continue
            if abs(wx - c[0]) <= c[2] * 0.5 and abs(wy - c[1]) <= c[3] * 0.5:
                return it
        return None

    def _print_state(self):
        inv = self.world.inventory
        g = self.world.game
        tail = ''
        if g.got_caught:
            tail = '  CAUGHT'
        elif g.all_done():
            tail = '  LEVEL COMPLETE'
        elif g.won:
            tail = '  WON (exit enabled)'
        print('inventory: %s  used=%s | tricks %d/%d%s' % (
            [i['type'] for i in inv.items],
            inv.used['type'] if inv.used else None,
            g.completed, g.total, tail))

    def draw(self):
        sdl2.SDL_SetRenderDrawColor(self.rnd, 20, 22, 28, 255)
        sdl2.SDL_RenderClear(self.rnd)
        for q in self.level.quads:                   # sorted back-to-front by z
            draw_quad(self.rnd, self.cache, self.cam, q, WIDTH, HEIGHT)
        drawn = 0
        # behaviors reassign AnimationGUIDepth at runtime (Level201, 211, 213,
        # SandCastle, ParrotLedge...), so the far-to-near order is re-derived
        # every frame instead of once at load
        for s in sorted(self.level.sprites, key=lambda s: -s.depth):
            a = s.anims[s.current]
            if draw_sprite(self.rnd, self.cache, self.cam, s, a, self.t,
                           WIDTH, HEIGHT):
                drawn += 1
        if self.show_zones:
            draw_zone_overlay(self.rnd, self.cam, self.level.zones, WIDTH, HEIGHT)
        if self.hud is not None:
            mx, my = ctypes.c_int(0), ctypes.c_int(0)
            sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            self.hud.draw(self._frame_dt, (mx.value, my.value))
        sdl2.SDL_RenderPresent(self.rnd)
        return drawn

    def screenshot(self, path):
        surf = sdl2.SDL_CreateRGBSurface(0, WIDTH, HEIGHT, 32,
                                         0x00ff0000, 0x0000ff00, 0x000000ff,
                                         0xff000000)
        sdl2.SDL_RenderReadPixels(self.rnd, None, sdl2.SDL_PIXELFORMAT_ARGB8888,
                                  surf.contents.pixels, surf.contents.pitch)
        n = WIDTH * HEIGHT * 4
        buf = ctypes.string_at(surf.contents.pixels, n)
        sdl2.SDL_FreeSurface(surf)
        rgba = bytearray(n)
        rgba[0::4] = buf[2::4]; rgba[1::4] = buf[1::4]
        rgba[2::4] = buf[0::4]; rgba[3::4] = buf[3::4]
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
        from texture import write_png
        write_png(path, WIDTH, HEIGHT, bytes(rgba))
        print('screenshot -> %s' % path)

    def run(self, seconds=None, shot=None):
        ev = sdl2.SDL_Event()
        last = time.time()
        start = last
        while True:
            while sdl2.SDL_PollEvent(ctypes.byref(ev)):
                if ev.type == sdl2.SDL_QUIT:
                    return
                if ev.type == sdl2.SDL_KEYDOWN:
                    k = ev.key.keysym.sym
                    if k == sdl2.SDLK_ESCAPE:
                        return
                    elif k == sdl2.SDLK_LEFT:
                        self.cam.x -= 0.5
                    elif k == sdl2.SDLK_RIGHT:
                        self.cam.x += 0.5
                    elif k == sdl2.SDLK_UP:
                        self.cam.y += 0.5
                    elif k == sdl2.SDLK_DOWN:
                        self.cam.y -= 0.5
                    elif k == sdl2.SDLK_LEFTBRACKET:
                        self.load(self.i - 1)
                    elif k == sdl2.SDLK_RIGHTBRACKET:
                        self.load(self.i + 1)
                    elif k == sdl2.SDLK_z:
                        self.show_zones = not self.show_zones
                    elif k == sdl2.SDLK_SPACE:
                        self.paused = not self.paused
                    elif k == sdl2.SDLK_s:
                        self.screenshot('/tmp/nfh-%s.png' % self.level.name)
                    elif k == sdl2.SDLK_f:
                        self.follow = not self.follow
                    elif k == sdl2.SDLK_TAB and self.woody:
                        # Woody.ToggleSneak
                        self.woody.sneak_toggle = not self.woody.sneak_toggle
                        self.woody.sneaking = self.woody.sneak_toggle
                        print('sneak:', self.woody.sneaking)
                    elif sdl2.SDLK_0 <= k <= sdl2.SDLK_9:
                        idx = (k - sdl2.SDLK_1) if k != sdl2.SDLK_0 else -1
                        self.world.inventory.select(idx)
                        self._print_state()
                if ev.type == sdl2.SDL_MOUSEBUTTONDOWN and self.woody:
                    if self.woody.input_locked:
                        continue          # Woody.InputLocked (the entrance)
                    # Woody.Update: HUD.CheckClick() eats the click first
                    if self.hud is not None:
                        consumed = self.hud.check_click(ev.button.x, ev.button.y)
                        if consumed == 'restart':
                            self.load(self.i)
                            continue
                        if consumed:
                            self._print_state()
                            continue
                    wx, wy = self.cam.screen_to_world(ev.button.x, ev.button.y,
                                                      WIDTH, HEIGHT)
                    if self.world.game.ending:
                        pass              # FinishGame: input is locked
                    else:
                        it = self._item_at(wx, wy)
                        if it is not None:
                            used = self.world.inventory.used
                            print('use %s%s' % (it.name,
                                  ' with ' + used['type'] if used else ''))
                            self.world.woody_use(it)
                        else:
                            self.woody.start_move_flags()
                            if not self.woody.goto(wx, wy):
                                print('no route to (%.2f, %.2f)' % (wx, wy))
                        self._print_state()
            now = time.time()
            dt = now - last; last = now
            self._frame_dt = dt
            if not self.paused:
                self.t += dt
            if not self.paused:
                self.world.tick(min(dt, 0.1))
                if self.follow and self.woody:
                    self.cam.x = self.woody.sprite.x
                    self.cam.y = self.woody.sprite.y + 0.6
            self._clamp_camera()
            drawn = self.draw()
            if shot and now - start > 0.4:
                self.screenshot(shot)
                print('drew %d/%d sprites; missing sheets: %d'
                      % (drawn, len(self.level.sprites), len(self.cache.missing)))
                if self.cache.missing[:8]:
                    print('  e.g.', ', '.join(self.cache.missing[:8]))
                return
            if seconds and now - start > seconds:
                return


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    opts = [a for a in argv[1:] if a.startswith('--')]
    shot = next((a.split('=', 1)[1] for a in opts if a.startswith('--shot=')), None)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = args or sorted(glob.glob(os.path.join(root, 'levels', 's1', 'Level*.json')))
    if not paths:
        print('no levels given'); return 1
    v = Viewer(paths, headless=bool(shot))
    v.run(shot=shot)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
    sys.exit(main(sys.argv))
