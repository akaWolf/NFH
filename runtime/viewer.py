"""Level viewer — draws an exported level with the game's own rendering model.

    NFH_TEXTURES=/path/to/pngs python3 runtime/viewer.py levels/s1/Level101.json

Keys: left/right pan, [ ] switch level, Z zones, D depth order, Space pause,
      S screenshot, Esc quit.
"""
import ctypes, os, sys, glob, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sdl2

from base import asset_root, data_root
from scene import Level, DESIGN_H
from world import World
from audio_out import SoundBank
from render import (Camera, TextureCache, draw_sprite, draw_quad,
                    draw_zone_overlay, draw_fence, draw_item_tip)
from hud import Hud

WIDTH, HEIGHT = 800, 600


def texture_dirs(level_paths=()):
    """viewer decision: the PNG search path — NFH_TEXTURES first, then the
    season directories with the season of the opened levels first (a build's
    Resources.Load only sees its own season; 93 shared names differ by md5
    between the two extractions, 12 of them level sheets — M_appear,
    M_disappear, N_Cry, N_Ladder, N_Search, W_Appear, W_Disappear, W_Fear,
    W_NoNo, W_Whats_Up, beer, ms_0000 — the rest menu buttons), then
    textures/. The order is fixed once per session by ANY s2 path in the
    list — a mixed s1+s2 session gives s2 priority to the s1 levels too."""
    env = os.environ.get('NFH_TEXTURES')
    dirs = env.split(':') if env else []
    root = asset_root()
    # season-specific dirs; the season of the opened levels wins name clashes
    seasons = ['s1', 's2']
    if any('/s2/' in p.replace('\\', '/') for p in level_paths):
        seasons.reverse()
    for s in seasons:
        dirs.append(os.path.join(root, 'textures', s))
    dirs.append(os.path.join(root, 'textures'))
    return dirs


class Viewer:
    def __init__(self, level_paths, start=0, headless=False, window=None,
                 renderer=None, cache=None, sounds=None, autoload=True):
        self.paths = level_paths
        self.i = start
        self.headless = headless
        if window is None:
            sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
            flags = sdl2.SDL_WINDOW_HIDDEN if headless else sdl2.SDL_WINDOW_SHOWN
            self.win = sdl2.SDL_CreateWindow(b'NFH viewer',
                                             sdl2.SDL_WINDOWPOS_CENTERED,
                                             sdl2.SDL_WINDOWPOS_CENTERED,
                                             WIDTH, HEIGHT, flags)
            self.rnd = sdl2.SDL_CreateRenderer(
                self.win, -1, sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC)
            self.cache = TextureCache(self.rnd, texture_dirs(level_paths))
            self.sounds = None if headless else SoundBank.try_open(level_paths)
        else:
            # the application owns the window, the renderer, the sheets and
            # the mixer; the viewer draws the level into them
            self.win, self.rnd, self.cache, self.sounds = \
                window, renderer, cache, sounds
        # the application runs IntroAnimation's title cards itself and
        # calls World.start_music at StartGame (see World.__init__)
        self.defer_music = False
        # the score screen's buttons (HUD.cs:1287-1299): the application
        # hooks the level reload / the return to the level selection here;
        # the bare viewer reloads / steps to the next level itself
        self.on_score = None
        # SettingKey.Language for the level strings (the bare viewer keeps
        # the extraction default 0 = English)
        self.language = 0
        self.cam = Camera()
        self.show_zones = False
        self.paused = False
        self._frame_dt = 0.0
        self.follow = False
        self._cam_interp = None           # CameraMover.InterpolateToPosition
        self.virtual_mouse = None         # the recorder's scripted cursor
        self.virtual_mouse_down = False
        self.woody = None
        self.t = 0.0
        if autoload:
            self.load(self.i)

    def load(self, i):
        self.i = i % len(self.paths)
        self.level = Level(self.paths[self.i])
        if self.level.camera_size:
            self.cam.size = self.level.camera_size
        self.world = World(self.level,
                           sound_sink=self.sounds.play if self.sounds else None,
                           music=self.sounds, defer_music=self.defer_music)
        for role in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
            self.world.spawn_pawn(role)
        self.woody = self.world.pawns.get('Woody')
        self.world.woody = self.woody
        self.world.start_routines()
        bg = self.level.background
        self.cam.x = bg[1] if bg else 0.0
        self.cam.y = bg[2] if bg else 0.0
        # the original camera is free (edge scroll + arrows + face snaps);
        # F toggles the viewer's follow convenience on top
        self.follow = False
        self._cam_interp = None
        if self.woody is not None:
            # start looking at Woody's entrance
            self.cam.x = self.woody.sprite.x
            self.cam.y = self.woody.sprite.y
        self.t = 0.0
        self.hud = Hud(self.level, self.world, self.cache, self.rnd,
                       WIDTH, HEIGHT, language=self.language) \
            if self.level.hud else None
        if self.hud is not None:
            # Woody.PlayTrickDone -> the HUD celebration
            self.world.game.on_trick_done = self.hud.play_trick_done
            self.hud.cam = self.cam       # the world-anchored progress bars
            self.world.hud = self.hud     # the description bubble / whistle
        # the dexterity minigame anchors its GUI at the component's screen
        # position (DexterityComponent.StartDexterity, cs:150-169)
        self.world.screen_size = (WIDTH, HEIGHT)
        self.world.screen_point = lambda x, y: self.cam.world_to_screen(
            x, y, WIDTH, HEIGHT)
        def _snap():
            # SnapToWoodyImmediate parks the camera exactly on Woody
            # (CameraMover.cs:468-471) — no viewer offset here
            if self.woody is not None:
                self.cam.x = self.woody.sprite.x
                self.cam.y = self.woody.sprite.y
                self._clamp_camera()
        self.world.snap_camera = _snap
        if not self.headless and self.level.mouse_cursor is not None:
            sdl2.SDL_ShowCursor(sdl2.SDL_DISABLE)
        print('%s — %d sprites, %d zones, %d items, %d routines (%d actions)'
              % (self.level.name, len(self.level.sprites), len(self.level.zones),
                 len(self.level.items), len(self.world.routines),
                 sum(len(r.actions) for r in self.world.routines)))

    def _update_camera(self, dt):
        """CameraMover's desktop contract (UpdateWindowsInput,
        CameraMover.cs:110-165 — dead on the Android build, but the desktop
        original is the reference): mouse at a 5 px edge or the arrow keys
        scroll at Speed*(Sensibility*3) — SpeedX pre-scaled by the aspect
        (Start, cs:83-90) — and the HUD face snaps interpolate over
        (InterpolateToPosition + Lerp at MoveVelocity=0.5/s). The follow
        toggle (F) is the viewer's own convenience on top."""
        w = self.world
        if w.camera_frozen or self.headless:
            return
        if w.is_dexterity_on or (self.follow and self.woody):
            return                        # handled in the run loop
        if w.snap_request is not None:
            who, w.snap_request = w.snap_request, None
            pawn = w.pawns.get(who)
            if pawn is not None:
                self._cam_interp = [pawn.sprite.x, pawn.sprite.y, 0.0]
        if self._cam_interp is not None:
            tx, ty, done = self._cam_interp
            done += 0.5 * dt              # MovementDone += MoveVelocity*dt
            if done >= 1.0:
                self.cam.x, self.cam.y = tx, ty
                self._cam_interp = None
            else:
                self.cam.x += (tx - self.cam.x) * done
                self.cam.y += (ty - self.cam.y) * done
                self._cam_interp[2] = done
            return
        mx, my = ctypes.c_int(0), ctypes.c_int(0)
        sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
        if self.virtual_mouse is not None:
            mx.value, my.value = int(self.virtual_mouse[0]), \
                int(self.virtual_mouse[1])
        keys = sdl2.SDL_GetKeyboardState(None)
        aspect = WIDTH / float(HEIGHT)
        speed_x = 7.0 * aspect * (0.5 * 3.0)   # SpeedX*aspect, Sensibility .5
        speed_y = 7.0 * (0.5 * 3.0)
        if mx.value > WIDTH - 5 or keys[sdl2.SDL_SCANCODE_RIGHT]:
            self.cam.x += dt * speed_x
        elif mx.value < 5 or keys[sdl2.SDL_SCANCODE_LEFT]:
            self.cam.x -= dt * speed_x
        if my.value < 5 or keys[sdl2.SDL_SCANCODE_UP]:
            self.cam.y += dt * speed_y
        elif my.value > HEIGHT - 5 or keys[sdl2.SDL_SCANCODE_DOWN]:
            self.cam.y -= dt * speed_y

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

    def _hit_at(self, wx, wy):
        """the click raycast (Pawn.MoveToLocation, Pawn.cs:403): ONE ray
        from the camera plane along +z (Woody.cs:708), the first collider
        hit wins — items and doors compete on the NEAR face of their world
        box (Level._world_box's z - dz), which is Physics.Raycast's hit
        distance; ties keep the first in scene order (the raycast's choice
        between coincident faces is not specified). Returns (item, door):
        one of them, whichever won. Not modelled: the zone boxes ride in
        the same ray (near face -1.525 on every zone), which only matters
        for the 13 shallow colliders a zone box overlaps in XY (the 12 S2
        fences Fence1-3 of L208/209/212/213 at -0.447, L214's MotherWait at
        -0.5) — all shipped disabled and never enabled by any code path;
        of the 667 XY-overlapping item/door collider pairs 113 order
        differently by centre than by near face — L103's Candle (near
        -2.01) over the Microwave (-4.0), a ToiletPaper (-4.5) over its
        DoorRight01 (-4.02) — see docs/audit/verified/assets_refs.md."""
        best = None
        best_z = None

        def near(c):
            # the ray's hit distance: the box's near face along z
            z = c[4] if len(c) > 4 else 0.0
            return z - (c[5] if len(c) > 5 else 0.0)
        for it in self.level.items.values():
            c = it.collider
            if c is None or not it.clickable or not it.can_use:
                continue
            if abs(wx - c[0]) <= c[2] * 0.5 and abs(wy - c[1]) <= c[3] * 0.5:
                z = near(c)
                if best_z is None or z < best_z:
                    best, best_z = ('item', it), z
        for d in self.level.doors:
            c = d.collider
            if c is None or d.disabled:
                continue
            if abs(wx - c[0]) <= c[2] * 0.5 and abs(wy - c[1]) <= c[3] * 0.5:
                z = near(c)
                if best_z is None or z < best_z:
                    best, best_z = ('door', d), z
        if best is None:
            return None, None
        return (best[1], None) if best[0] == 'item' else (None, best[1])

    def _door_at(self, wx, wy):
        """hover hit-test against the doors' BoxColliders (the raycast in
        MouseCursor.UpdateHover reaches Door colliders too)"""
        return self._hit_at(wx, wy)[1]

    def _item_at(self, wx, wy):
        """click hit-test; kept for the recorder's clickitem"""
        return self._hit_at(wx, wy)[0]

    def handle_click(self, sx, sy):
        """one mouse press — the Woody.CheckMouseClick chain
        (Woody.cs:631-672): HUD first, then the HUD strip, the hiding
        leave-and-replay, the blocked-input buffer, the climb gate, and
        finally the world click."""
        if self.world.is_dexterity_on:
            return None                   # GameInfo.IsDexterityOn (Pawn.cs:351)
        if self.hud is not None:
            consumed = self.hud.check_click(sx, sy)
            if consumed in ('restart', 'next') and self.on_score is not None:
                # the application: Restart reloads the level, OK returns
                # to the level selection (HUD.cs:1287-1299)
                self.on_score(consumed)
                return 'score'
            if consumed == 'restart':
                self.load(self.i)
                return 'restart'
            if consumed == 'next':
                # viewer decision: the score screen's OK leads to the level
                # selection menu in the original (LevelLoader; the
                # application models it); here it opens the next level of
                # the list
                self.load(self.i + 1)
                return 'restart'
            if consumed:
                self._print_state()
                return 'hud'
        # a click over the HUD strip is swallowed even between the buttons
        # (MouseOverHUD, Woody.cs:637)
        mc = self.level.mouse_cursor
        if mc is not None and sy > HEIGHT - mc['min_mouse_y'] * HEIGHT / 600.0:
            return 'hud-strip'
        # Woody.Frozen (Woody.cs:637) — set by FinishGame's Woody.Freeze
        # (GameInfo.cs:364) and the dexterity snap; the 2.5 s win wait
        # (GameEnding without FinishGame, GameInfo.cs:292-302) keeps his
        # clicks live
        if self.woody is not None and self.woody.frozen:
            return 'ending'
        # `!(Time.timeScale > 0f)` (Woody.cs:637): a paused game — the power
        # button's menu half, or the viewer's Space — drops world clicks
        # after the HUD had its look
        if self.world.menu_open or self.paused:
            return 'paused'
        w = self.woody
        click = (sx, sy)
        # LastInputTime stamps here, past the gates but before the buffers
        # (Woody.cs:641): a stored or hiding click resets the boredom timer
        self.world._last_input_time = self.world.time
        # hiding: leave the spot and replay the click after the blocking
        # leave animation; a click during the literal Hide_In dive is
        # dropped, not stored (Woody.cs:642-651)
        if w.hiding and w.hiding_item is not None:
            if w.anim.anim.name != 'Hide_In':
                w.unhide()
                w.input_locked = False
                w.stored_input = click
                return 'unhide'
            return 'hide-in'
        # a locked input or a blocking animation buffers the click for the
        # replay (StoreBlockedInput, Woody.cs:652-656)
        if w.input_locked or w.anim.blocking:
            w.stored_input = click
            return 'stored'
        # the vertical climb swallows clicks (Woody.cs:657-667), and so does
        # a latched DonePassingToOtherZone (cs:659-662) — the mid-stairs
        # re-route shapes only ever run off a replayed stored click. The
        # Season-1 re-dispatch (cs:668-671: `!NFH2Path && itemAux is Door`,
        # itemAux being the current step's Target, Woody.cs:214-217) runs
        # past both gates, so a click during a door climb is processed
        # there; elsewhere it repeats the same dispatch with the same click
        # and lands on the same result, so one call suffices
        s1_door_step = not w.nfh2 and w.state == w.DOOR_CLIMB
        if w.anim.anim.name in ('Run_Up', 'Walk_Up') and not s1_door_step:
            return 'climb'
        if w.done_passing:                # NFH2 only (Pawn.cs:319)
            return 'passing'
        self.world_click(sx, sy)
        return 'world'

    def world_click(self, sx, sy):
        """one accepted world click: hit-test and dispatch
        (Pawn.MoveToLocation -> GetMoveDestination)"""
        wx, wy = self.cam.screen_to_world(sx, sy, WIDTH, HEIGHT)
        it, door = self._hit_at(wx, wy)
        if it is not None:
            used = self.world.inventory.used
            print('use %s%s' % (it.name,
                  ' with ' + used['type'] if used else ''))
        if not self.world.woody_click(wx, wy, it, door):
            print('no route to (%.2f, %.2f)' % (wx, wy))
        self._print_state()

    def _print_state(self):
        """viewer instrumentation: one console line of inventory / tricks /
        outcome after each click (no game rule)"""
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

    def draw(self, present=True, overlay=None, cursor=True):
        """one frame; `overlay` draws between the HUD and the cursor (the
        application's in-game menu / dialogs at the Menu GUI depths),
        `present` False leaves the frame for the caller to present"""
        sdl2.SDL_SetRenderDrawColor(self.rnd, 20, 22, 28, 255)
        sdl2.SDL_RenderClear(self.rnd)
        for q in self.level.quads:                   # sorted back-to-front by z
            draw_quad(self.rnd, self.cache, self.cam, q, WIDTH, HEIGHT)
        drawn = 0
        # one GUI-depth-ordered pass over everything screen-space and
        # world-anchored: the sprites, the Level fences (Level.OnGUI,
        # GUIDepth.LevelFence sits between the pawns and the HUD) and the
        # interaction-icon tips (Item.OnGUI at ItemTipIconDepth while the
        # info button is held). Behaviors reassign AnimationGUIDepth at
        # runtime (Level201, 211, 213, SandCastle, ParrotLedge...), so the
        # far-to-near order is re-derived every frame instead of once at load.
        draw_list = [(s.depth, 'sprite', s) for s in self.level.sprites]
        draw_list += [(f['depth'], 'fence', f) for f in self.level.fences]
        if self.world.game.show_interaction_icon:
            # Item.OnGUI's gates (Item.cs:2749): a live collider, and hidden
            # items only with AlwaysShowTipIcon
            draw_list += [
                (it.tip_icon_depth, 'tip', it)
                for it in self.level.items.values()
                if it.tip_icon and it.clickable
                and (not (it.sprite is not None and it.sprite.hidden)
                     or it.always_show_tip)]
        for depth, kind, obj in sorted(draw_list, key=lambda t: -t[0]):
            if kind == 'sprite':
                # current None: a controller with no CurrentAnimation yet
                # (AnimationControllerBase.cs:179-185) — draw_sprite skips it
                a = obj.anims[obj.current] if obj.current is not None else None
                if draw_sprite(self.rnd, self.cache, self.cam, obj, a, self.t,
                               WIDTH, HEIGHT):
                    drawn += 1
            elif kind == 'fence':
                draw_fence(self.rnd, self.cache, self.cam, obj, WIDTH, HEIGHT)
            else:
                draw_item_tip(self.rnd, self.cache, self.cam, obj,
                              WIDTH, HEIGHT)
        if self.show_zones:
            draw_zone_overlay(self.rnd, self.cam, self.level.zones, WIDTH, HEIGHT)
        if self.hud is not None:
            mx, my = ctypes.c_int(0), ctypes.c_int(0)
            buttons = sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            if self.virtual_mouse is not None:
                # the recorder drives a scripted cursor instead of the OS one
                mx.value, my.value = int(self.virtual_mouse[0]), \
                    int(self.virtual_mouse[1])
                buttons = sdl2.SDL_BUTTON_LMASK if self.virtual_mouse_down \
                    else 0
            # MouseCursor.UpdateHover: the item under the cursor drives the
            # permanent tooltip and the TrickItem hover pose
            wx, wy = self.cam.screen_to_world(mx.value, my.value,
                                               WIDTH, HEIGHT)
            hit = None
            hover_door = None
            zone = None
            if not self.world.game.ending and not self.world.menu_open:
                hit, hover_door = self._hit_at(wx, wy)
                zone = self.level.zone_at(wx, wy)
                if hit is not None:
                    self.world.on_mouse_hover(hit)
                self.hud.update_hover(hit, zone, hover_door)
            self.hud.update_cursor(hit, hover_door, zone,
                                   wx, wy, my.value)
            self.hud.draw(self._frame_dt, (mx.value, my.value),
                          bool(buttons & sdl2.SDL_BUTTON_LMASK))
            if overlay is not None:
                overlay()
            if cursor:
                self.hud.draw_cursor(mx.value, my.value)
        elif overlay is not None:
            overlay()
        if present:
            sdl2.SDL_RenderPresent(self.rnd)
        return drawn

    def screenshot(self, path):
        """viewer instrumentation: dump the current frame as PNG (S key,
        --shot=)"""
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
        sys.path.insert(0, os.path.join(data_root(), 'tools'))
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
                        # Woody.ToggleSneak (Woody.cs:1151-1168)
                        self.woody.toggle_sneak()
                        print('sneak:', self.woody.sneaking)
                    elif sdl2.SDLK_0 <= k <= sdl2.SDLK_9:
                        idx = (k - sdl2.SDLK_1) if k != sdl2.SDLK_0 else -1
                        self.world.inventory.select(idx)
                        self._print_state()
                if ev.type == sdl2.SDL_MOUSEMOTION and \
                        self.world.is_dexterity_on:
                    # the touch delta drives the pick (DexterityComponent
                    # FixedUpdate, cs:227); the mouse plays the touch role
                    for ds in self.world.dex_states.values():
                        if ds.enabled:
                            ds.input = (ds.input[0] + ev.motion.xrel * 25.0,
                                        ds.input[1] - ev.motion.yrel * 25.0)
                if ev.type == sdl2.SDL_MOUSEBUTTONDOWN and self.woody:
                    if self.handle_click(ev.button.x, ev.button.y) == 'restart':
                        continue
            now = time.time()
            dt = now - last; last = now
            self._frame_dt = dt
            if not self.paused:
                self.t += dt
            self._update_camera(dt)
            if not self.paused and not self.world.menu_open:
                # viewer decision: the frame dt is clamped to 0.1 s so a
                # stall (window drag, a swap) does not become one giant
                # step; the original runs on Time.deltaTime, which Unity
                # itself only caps at Time.maximumDeltaTime (1/3 s by
                # default) — a tighter cap than the engine's, no game rule
                self.world.tick(min(dt, 0.1))
                # the stored click replays once the block lifts
                # (OnBlockingAnimationEnded / OnDoorEnterAnimationFinished —
                # Woody.cs:336-341, 484-488)
                w = self.woody
                if w is not None and w.stored_input is not None \
                        and not w.input_locked and not w.anim.blocking \
                        and not w.is_warping \
                        and not self.world.game.ending:
                    click, w.stored_input = w.stored_input, None
                    self.world_click(*click)
                if self.world.is_dexterity_on and self.woody:
                    # GameCamera.Freeze + SnapToWoodyImmediate (cs:149, 171)
                    self.cam.x = self.woody.sprite.x
                    self.cam.y = self.woody.sprite.y
                elif self.follow and self.woody:
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
    root = data_root()
    paths = args or sorted(glob.glob(os.path.join(root, 'levels', 's1', 'Level*.json')))
    if not paths:
        print('no levels given'); return 1
    start = 0
    if len(paths) == 1 and not shot:
        # viewer decision: one level on the command line (run.sh's default)
        # still gets `[` `]` and the score screen's OK — the siblings of its
        # season directory, starting at the level given
        one = os.path.abspath(paths[0])
        sibs = sorted(glob.glob(os.path.join(os.path.dirname(one), 'Level*.json')))
        if one in sibs:
            paths, start = sibs, sibs.index(one)
    v = Viewer(paths, start=start, headless=bool(shot))
    v.run(shot=shot)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
