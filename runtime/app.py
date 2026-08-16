"""The game application — the flow the original wraps around the levels:

    python3 runtime/app.py            # Splash -> Entry menu -> levels

CoreFrameworkController loads "Entry" (CoreFrameworkController.cs:24-27);
the Entry scene runs GameIntroAnimation (the splash), the Control* menu
windows and the two level selections; a tile's start button calls
LevelLoader.LoadLevel, whose loading screen leads into the level scene;
there IntroAnimation plays the title cards and StartGame begins play;
Woody's power button / Esc toggles InGameMenu, the exit door and the
destructive menu buttons raise ExitConfirmation, and the score screen's
Restart / OK lead back (HUD.cs:1287-1299) — OK through Level.
OpenLevelSelection + MenuLoader into the level-selection window.

One process hosts both seasons (the original shipped two apps that
launched each other, ControlButton.CanLaunchApplication /
BuildSettings.AppToLaunch — ControlButton.cs:153-160; the port's Entry is
Season 1's, whose GameSelection already carries both selections).

Fullscreen is the port's own toggle in the options windows (the PC build
had one; the Android decompile has no SettingKey for it) — stored under
the port's "Fullscreen" pref and applied as SDL fullscreen-desktop with a
800x600 logical size.
"""
import ctypes, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sdl2

from base import asset_root, data_root
from gui import Gfx, Text, adjust_rect, font_size
from menu import (Menu, SceneData, ControlToggle, level_index,
                  load_strings)
from prefs import Prefs
from render import TextureCache
from tutorial import build as build_tutorial
from audio_out import SoundBank, audio_dirs
from viewer import Viewer, WIDTH, HEIGHT

ROOT = asset_root()                       # textures/, audio/, strings/, fonts/
LEVELS = data_root()                      # levels/*.json ship with the port


def scene_path(name, season):
    """a scene name (ControlButton.LevelToStart / LevelLoader) -> the
    exported JSON; the season comes from the name (Level2xx lives in the
    Season-2 build), everything else from the caller's season"""
    if name.startswith('Level2'):
        season = 's2'
    elif name.startswith(('Level1', 'Intro1')):
        season = 's1'
    return os.path.join(LEVELS, 'levels', season, name + '.json'), season


# ---------------------------------------------------------------------------
# the port's fullscreen toggle (a PC-build option; no Android counterpart)

FULLSCREEN_TOGGLE = {
    # a ControlToggle spec shaped like MenuToggleTrickCamera's row
    # (levels/s1/Entry.json): the checkbox pair, one row above it
    'm_Name': '', 'Textures': [
        {'texture': 'checkbox_off~2'}, {'texture': 'checkbox_off_hov~2'},
        {'texture': 'checkbox_off_hov~2'}, {'texture': 'checkbox_on~2'},
        {'texture': 'checkbox_on_hov~2'}, {'texture': 'checkbox_on_hov~2'}],
    'UseMobileTextures': False, 'MobileTextures': [],
    'ScreenRect': {'x': 0.70, 'y': 0.5723794102668762,
                   'width': 0.028063610196113586,
                   'height': 0.04991680011153221},
    'ScreenMobileRect': {'x': 0.0, 'y': 0.0, 'width': 0.0, 'height': 0.0},
    'UseMobileText': True, 'TextString': '', 'TextStringMobile': '',
    'TextRect': {'x': 0.0, 'y': 0.0, 'width': 0.0, 'height': 0.0},
    'TextMobileRect': {'x': 0.738, 'y': 0.574,
                       'width': 0.25, 'height': 0.05217970162630081},
    'DontDrawPercentages': False, 'MultiLangTextRect': [],
    'Tooltip': '', 'ToolTipMobile': '', 'UseMobileToolTip': False,
    'TooltipRect': {'x': 0.0, 'y': 0.0, 'width': 0.0, 'height': 0.0},
    'TooltipMobileRect': {'x': 0.0, 'y': 0.0, 'width': 0.0, 'height': 0.0},
    'Depth': 'Menu', 'SettingControl': True, 'SettingKey': 'Fullscreen',
    'SettingType': 'Int', 'Locked': False, 'ApplySettings': True,
    'DefaultInt': 0, 'IsLaguage': False, 'LanguageType': 'Lang',
    'SetLanguage': False, 'UnsetLanguage': False,
}


def add_fullscreen_toggle(menu, options_go, text_style):
    """append the port's toggle to an options window's widget set; the
    label is a literal (no localization key exists for it)"""
    d = dict(FULLSCREEN_TOGGLE)
    d['TextStyle'] = dict(text_style or {})
    d['HoverTextStyle'] = dict(text_style or {})
    w = ControlToggle(menu.scene, options_go, d, menu)
    w.text = w.text_mobile = 'FULLSCREEN'
    menu.widgets.append(w)
    menu._by_go.setdefault(options_go, []).append(w)
    return w


# ---------------------------------------------------------------------------
# the loading screens

class LoadingScreen:
    """LevelLoader.OnGUI (LevelLoader.cs:141-171) and the Transition
    scene's LevelTransition.OnGUI (LevelTransition.cs:80-100): the loading
    texture, the progress bar, the localized DataString. The original
    loads async and fills the bar with LoadingOperation.progress; the
    port's load is blocking, so the bar sits at the Transition's fixed
    0.8 — the screen shows for the load plus LevelTransition.LoadTimer."""

    def __init__(self, d, W, H, loc, progress=0.8):
        self.W, self.H = W, H
        self.loading = (d.get('LoadingTexture') or {}).get('texture')
        self.loading_rect = adjust_rect(d.get('LoadingRect'), W, H)
        self.bar_empty = (d.get('ProgressBarEmpty') or {}).get('texture')
        self.bar_full = (d.get('ProgressBarFull') or {}).get('texture')
        self.bar_rect = adjust_rect(d.get('ProgressRect'), W, H)
        self.data_rect = adjust_rect(d.get('DataRect'), W, H)
        self.data_style = d.get('DataStyle') or {}
        self.data_string = loc(d.get('DataString'))
        # Start: DataStyle.fontSize = CalculateFontSize(0) + 3
        self.font = int(font_size(W, H)) + 3
        self.progress = progress
        self.load_timer = float(d.get('LoadTimer') or 0.1)

    def draw(self, g):
        g.tex(self.loading, self.loading_rect)
        g.tex(self.bar_empty, self.bar_rect)
        r = self.bar_rect
        # GUI.BeginGroup(width * progress) clips the full bar
        g.tex_uv(self.bar_full, (r[0], r[1], r[2] * self.progress, r[3]),
                 (0.0, 0.0, self.progress, 1.0))
        g.label(self.data_rect, self.data_string, self.data_style, self.font)


# ---------------------------------------------------------------------------
# the title cards (IntroAnimation.cs)

class IntroCards:
    """IntroAnimation: Company -> CompanyOutGameIn -> Game -> GameEpisodeIn
    -> GameEpisode -> GameEpisodeOut -> GameOut, then StartGame; any click
    or Esc skips (StopIntroAnimation). The rects move by *Speed px/s with
    the In caps; Title is localized "IN", Episode "L{n}T"."""

    STATES = ('Company', 'CompanyOutGameIn', 'Game', 'GameEpisodeIn',
              'GameEpisode', 'GameEpisodeOut', 'GameOut')

    def __init__(self, d, W, H, loc, level_idx, gfx):
        self.W, self.H = W, H
        self.d = d
        self.background = (d.get('Background') or {}).get('texture')
        self.background_rect = adjust_rect(d.get('BackgroundRect'), W, H)
        self.company = (d.get('CompanyLogo') or {}).get('texture')
        self.company_rect = list(adjust_rect(d.get('CompanyRect'), W, H))
        self.game = (d.get('GameLogo') or {}).get('texture')
        self.game_rect = list(adjust_rect(d.get('GameRect'), W, H))
        self.title_rect = list(adjust_rect(d.get('TitleRect'), W, H))
        self.episode_rect = list(adjust_rect(d.get('EpisodeRect'), W, H))
        self.title_style = d.get('TitleStyle') or {}
        self.episode_style = d.get('EpisodeStyle') or {}
        # StartAnimation (cs:96-97): the sizes off CalculateFontSize
        self.title_size = int(font_size(W, H)) + 5
        self.episode_size = int(font_size(W, H)) + 6
        self.times = [float(d.get(k) or 0.0) for k in (
            'CompanyStaticTime', 'CompanyOutGameInTime', 'GameTime',
            'GameEpisodeInTime', 'GameEpisodeTime', 'GameEpisodeOutTime',
            'GameOutTime')]
        self.speeds = {k: float(d.get(k) or 0.0) for k in (
            'CompanyOutSpeed', 'GameInSpeed', 'TitleInSpeed',
            'EpisodeInSpeed', 'TitleOutSpeed', 'EpisodeOutSpeed',
            'GameOutSpeed')}
        self.game_in_max = float(d.get('GameInMax') or 0.0) * W  # cs:107
        self.title = loc('IN')
        self.episode = loc('L%dT' % level_idx)
        # TitleInMin / EpisodeInMax off CalcSize (cs:110-113)
        tw = gfx.calc_width(self.title_style, self.title_size, self.title)
        ew = gfx.calc_width(self.episode_style, self.episode_size,
                            self.episode)
        self.title_in_min = (W - tw) / 2.0
        self.episode_in_max = (W - ew) / 2.0
        self.state = 0
        self.timer = self.times[0]
        self.running = True

    def tick(self, dt, clicked, escape):
        """Update (cs:118-124) + the DoIntroLogic coroutine (cs:257-276)"""
        if not self.running:
            return False
        if clicked or escape:
            self.running = False          # StopIntroAnimation -> StartGame
            return True
        self.timer -= dt
        if self.timer <= 0.0:
            self.state += 1
            if self.state >= len(self.times):
                self.running = False      # DoIntroLogic's tail: StartGame
                return True
            self.timer = self.times[self.state]
        return False

    def _inc_cap(self, rect, inc, mx, dt):
        if rect[0] < mx:
            rect[0] = min(mx, rect[0] + inc * dt)

    def _dec_cap(self, rect, dec, mn, dt):
        if rect[0] > mn:
            rect[0] = max(mn, rect[0] - dec * dt)

    def draw(self, g, dt):
        """OnGUI (cs:126-153) + the Render* arms (cs:163-256)"""
        if not self.running:
            return
        g.tex(self.background, self.background_rect)
        st = self.STATES[self.state]
        if st == 'Company':
            g.tex(self.company, tuple(self.company_rect))
        elif st == 'CompanyOutGameIn':
            self.company_rect[1] += self.speeds['CompanyOutSpeed'] * dt
            g.tex(self.company, tuple(self.company_rect))
            self._inc_cap(self.game_rect, self.speeds['GameInSpeed'],
                          self.game_in_max, dt)
            g.tex(self.game, tuple(self.game_rect))
        elif st == 'Game':
            g.tex(self.game, tuple(self.game_rect))
        elif st == 'GameEpisodeIn':
            g.tex(self.game, tuple(self.game_rect))
            self._dec_cap(self.title_rect, self.speeds['TitleInSpeed'],
                          self.title_in_min, dt)
            g.label(tuple(self.title_rect), self.title, self.title_style,
                    self.title_size)
            self._inc_cap(self.episode_rect, self.speeds['EpisodeInSpeed'],
                          self.episode_in_max, dt)
            g.label(tuple(self.episode_rect), self.episode,
                    self.episode_style, self.episode_size)
        elif st == 'GameEpisode':
            g.tex(self.game, tuple(self.game_rect))
            g.label(tuple(self.title_rect), self.title, self.title_style,
                    self.title_size)
            g.label(tuple(self.episode_rect), self.episode,
                    self.episode_style, self.episode_size)
        elif st == 'GameEpisodeOut':
            g.tex(self.game, tuple(self.game_rect))
            self.title_rect[0] += self.speeds['TitleOutSpeed'] * dt
            g.label(tuple(self.title_rect), self.title, self.title_style,
                    self.title_size)
            self.episode_rect[0] += self.speeds['EpisodeOutSpeed'] * dt
            g.label(tuple(self.episode_rect), self.episode,
                    self.episode_style, self.episode_size)
        elif st == 'GameOut':
            self.game_rect[1] += self.speeds['GameOutSpeed'] * dt
            g.tex(self.game, tuple(self.game_rect))


# ---------------------------------------------------------------------------
# the in-game menu scene (the level's widgets over the shared Menu class)

class InGameMenuScene(Menu):
    """the level's InGameMenu (InGameMenu.cs) + its options window, the
    ExitConfirmation, the LevelDataGUIRenderer page — the same Control*
    widgets, with the level context: the audio applies to the level music,
    HasAnyMenuOpen is this menu, ShowLevelData drives the renderer"""

    def __init__(self, path, W, H, prefs, sounds, texture_size, app,
                 scene_name):
        Menu.__init__(self, path, W, H, prefs, sounds=sounds,
                      texture_size=texture_size, app=app)
        self.current_scene_name = scene_name
        self.enabled = False              # InGameMenu (Behaviour) enabled
        igm = self.scene.find('InGameMenu')
        self.menu_object = (igm[0][1].get('MenuObject') or {}).get('path') \
            if igm else None
        # InGameMenu.Start (cs:16-22): the renderer is the in-game one,
        # loaded with the level's index, then Disable()
        self.level_idx = level_index(self.season, self.scene.scene)
        for r in self.renderers.values():
            r.is_in_game_menu = True
            r.load_level_data(self.level_idx)
            r.enabled = False
        self.disable()

    # -- InGameMenu (cs:28-61) ----------------------------------------------
    def toggle(self):
        active = self.menu_object is not None and \
            self.scene.active_in_hierarchy(self.menu_object)
        if (active or not self.enabled) and not self.is_exit_confirmation_shown():
            if self.enabled:
                self.disable()
            else:
                self.enable()

    def enable(self):
        self.time_scale = 0.0
        self.enabled = True
        for r in self.renderers.values():
            r.enabled = True
        self.scene.set_active(self.menu_object, True)

    def disable(self):
        self.time_scale = 1.0
        self.enabled = False
        for r in self.renderers.values():
            r.enabled = False
        self.scene.set_active(self.menu_object, False)

    def disable_in_game_menu(self):
        """ControlButton.DisableInGameMenu -> InGameMenu.Disable"""
        self.disable()

    def has_any_menu_open(self):
        """Woody.HasAnyMenuOpen (Woody.cs:1140-1143)"""
        return self.enabled

    def show_level_data(self, show):
        """InGameMenu.ShowLevelData (cs:24-27)"""
        for r in self.renderers.values():
            r.enabled = show

    def apply_audio(self):
        """Level.LoadSettings' arm in a level (Level.cs:295-310): the level
        track through the World's MusicPlayer port"""
        if self.sounds is None:
            return
        s = self.settings
        self.sounds.set_sound_volume(s.sound_volume, enabled=s.audio_enabled)
        self.sounds.set_music_volume(s.music_volume)
        world = self.app.viewer.world if self.app and self.app.viewer else None
        if not (s.audio_enabled and s.music_enabled):
            # MusicPlayer.StopAllSounds
            self.sounds.stop_music()
            self.sounds.stop_entrance()
            if world is not None:
                world._music_timer = None
        elif world is not None and world.level.music and \
                world.level.music.get('level') and \
                not self.sounds._mixer.Mix_Playing(self.sounds.MUSIC_CHANNEL) \
                and world._music_timer is None and not world.game.ending:
            # PlayLevelMusic with OneTime already true -> StartMusic plays
            # the track only if the source is silent (MusicPlayer.cs:98-105)
            self.sounds.play_music(world.level.music['level'],
                                   loop=world.level.music.get('loop', True))

    def draw_cursor(self):
        pass                              # the level's MouseCursor draws


# ---------------------------------------------------------------------------

class App:
    """the scene machine: 'menu' (Entry with the splash) / 'level'; the
    loading screens run inline between them"""

    def __init__(self, headless=False, prefs=None):
        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
        flags = sdl2.SDL_WINDOW_HIDDEN if headless else sdl2.SDL_WINDOW_SHOWN
        self.win = sdl2.SDL_CreateWindow(
            b'Neighbours from Hell', sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED, WIDTH, HEIGHT, flags)
        self.rnd = sdl2.SDL_CreateRenderer(
            self.win, -1,
            sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC)
        sdl2.SDL_RenderSetLogicalSize(self.rnd, WIDTH, HEIGHT)
        self.headless = headless
        # per-season caches: each build's Resources only saw its own season,
        # and 93 shared names differ between the extractions
        self.caches = {
            's1': TextureCache(self.rnd, [os.path.join(ROOT, 'textures', d)
                                          for d in ('s1', 's2', '')]),
            's2': TextureCache(self.rnd, [os.path.join(ROOT, 'textures', d)
                                          for d in ('s2', 's1', '')])}
        self.texts = {s: Text(self.rnd, os.path.join(ROOT, 'fonts', s))
                      for s in ('s1', 's2')}
        bank = None if headless else SoundBank.try_open(())
        self.banks = {'s1': None, 's2': None}
        if bank is not None:
            self.banks['s1'] = SoundBank(bank._mixer, audio_dirs(['/s1/']))
            self.banks['s2'] = SoundBank(bank._mixer, audio_dirs(['/s2/']))
        self.prefs = prefs or Prefs()
        self.season = 's1'
        self.gfx = Gfx(self.rnd, self.caches['s1'], self.texts['s1'])
        # Level.MenuLoader / OpenLevelSelection are static across scenes
        # (Level.cs:88-92): the HUD stamps MenuLoader by the level's path
        # (HUD.cs:358-368), the score screen's OK raises OpenLevelSelection
        self.menu_loader = 0
        self.open_level_selection = False
        self.state = 'menu'
        self.menu = None
        self.viewer = None
        self.igm = None
        self.cards = None
        self.level_scene_name = None
        self.level_season = 's1'
        self._score_saved = False
        self._pending = None              # a scene load requested this frame
        self.quit = False
        self.time_scale = 1.0
        self.fullscreen = False
        self._mouse = (WIDTH / 2.0, HEIGHT / 2.0)
        self._mouse_down = False
        self._events = []                 # per-frame edges
        sdl2.SDL_ShowCursor(sdl2.SDL_DISABLE)
        self.apply_fullscreen(self.prefs.get_int('Fullscreen', 0) == 1)
        self.open_entry()

    # -- fullscreen (the port's option) --------------------------------
    def apply_fullscreen(self, on):
        if on == self.fullscreen:
            return
        self.fullscreen = on
        if not self.headless:
            sdl2.SDL_SetWindowFullscreen(
                self.win, sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP if on else 0)

    def _sync_fullscreen(self, settings):
        self.apply_fullscreen(settings.fullscreen)

    # -- the services shared with the scenes ---------------------------
    def texture_size(self, name):
        e = self.gfx.cache.get(name) if name else None
        return (e[1], e[2]) if e else (0, 0)

    def _bind_season(self, season):
        self.season = season
        self.gfx = Gfx(self.rnd, self.caches[season], self.texts[season])

    # -- the Entry scene ------------------------------------------------
    def open_entry(self, name='Entry'):
        """LevelLoader.LoadLevel('Entry'): the Entry scene's Menu — always
        Season 1's Entry (it hosts both level selections; the original's
        pair of apps launched each other here)"""
        if self.state == 'level':
            # leaving a level goes through the Transition scene
            # (LevelLoader.cs:77-88)
            self._draw_loading(name)
        self._bind_season('s1')
        path, _ = scene_path(name, 's1')
        self.viewer = None
        self.igm = None
        self.cards = None
        self.tutorial = None
        self.tutorial_camera = None
        self.state = 'menu'
        self.menu = Menu(path, WIDTH, HEIGHT, self.prefs,
                         sounds=self.banks['s1'],
                         texture_size=self.texture_size, app=self)
        # the fullscreen toggle rides the options window (port decision);
        # the label style borrows the trick-camera row's
        opt = next((go for go, e in self.menu.scene.find('ControlWindow')
                    if self.menu.scene.go_name(go) == 'MenuOptions'), None)
        style = next((t.get('TextStyle') for _, t in
                      self.menu.scene.find('ControlToggle')
                      if (t.get('SettingKey') == 'TrickCamera')), None)
        if opt is not None:
            add_fullscreen_toggle(self.menu, opt, style)
        # Level.Update's OpenLevelSelection arm consumes the statics
        self.menu.open_level_selection = self.open_level_selection
        self.menu.menu_loader = self.menu_loader
        self.open_level_selection = False
        self.menu_loader = 0
        self.menu.apply_audio()

    # -- a level scene ----------------------------------------------------
    def load_level(self, name):
        """LevelLoader.LoadLevel out of the menu / LevelTransition out of a
        level: draw the loading screen, blocking-load the scene, then the
        title cards"""
        path, season = scene_path(name, self.level_season)
        if not os.path.exists(path):
            print('no such scene: %s' % name)
            return
        self._draw_loading(name)
        self._bind_season(season)
        self.level_season = season
        self.level_scene_name = name
        self.state = 'level'
        self._score_saved = False
        v = Viewer([path], start=0, headless=self.headless, window=self.win,
                   renderer=self.rnd, cache=self.caches[season],
                   sounds=self.banks[season], autoload=False)
        v.defer_music = True
        v.language = self.prefs.get_int('Language', 0)
        v.on_score = self._on_score
        self.viewer = v
        v.load(0)
        self.igm = InGameMenuScene(path, WIDTH, HEIGHT, self.prefs,
                                   self.banks[season], self.texture_size,
                                   self, name)
        opt = next((go for go, e in self.igm.scene.find('ControlWindow')
                    if self.igm.scene.go_name(go) == 'InGameMenuOptions'),
                   None)
        style = next((t.get('TextStyle') for _, t in
                      self.igm.scene.find('ControlToggle')
                      if t.get('SettingKey') == 'TrickCamera'), None)
        if opt is not None:
            add_fullscreen_toggle(self.igm, opt, style)
        self.igm.apply_audio()
        w = v.world
        w.menu_toggle_hook = self.igm.toggle
        w.show_exit_confirmation = self._show_exit_confirmation
        w.on_score_computed = self._save_score
        # the tutorial layer (LevelScript + the scene's camera script);
        # GameInfo.ShowTutorialTextAfterIntro activates it at StartGame
        # (IntroAnimation.cs:305-307)
        self.tutorial, self.tutorial_camera = build_tutorial(
            self.igm.scene, WIDTH, HEIGHT, self.igm.loc, v)
        if self.tutorial is not None:
            w.level_script = self.tutorial
        gi = next((o['data'] for o in self.igm.scene.objs.values()
                   if o.get('type') == 'GameInfo'), {}) or {}
        self._show_tutorial_after_intro = bool(
            gi.get('ShowTutorialTextAfterIntro'))
        # HUD.Start stamps MenuLoader by Woody's path (HUD.cs:358-368)
        self.menu_loader = 2 if (v.woody is not None and v.woody.nfh2) else 1
        # the title cards (Level.Start -> IntroAnimation.StartAnimation);
        # scenes without the component (the Entry/Transition ones) skip
        ia = self.igm.scene.find('IntroAnimation')
        self.cards = None
        if ia and v.woody is not None:
            idx = level_index(season, self.igm.scene.scene)
            self.cards = IntroCards(ia[0][1], WIDTH, HEIGHT, self.igm.loc,
                                    idx, self.gfx)
            self._cards_elapsed = 0.0
            # DoIntroLogic parks the camera on the neighbour for the cards
            # (SnapToRottweilerImmediate, IntroAnimation.cs:259-262)
            rott = w.pawns.get('Rottweiler')
            if rott is not None:
                v.cam.x, v.cam.y = rott.sprite.x, rott.sprite.y
                v._clamp_camera()
            # MusicPlayer.Start: the clap fires at the scene load
            # (cs:43-47 -> PlayEffectsMusic, gated on MusicEnabled)
            st = self.igm.settings
            m = w.level.music or {}
            if w.music_bank is not None and m.get('clap') \
                    and st.audio_enabled and st.music_enabled:
                w.music_bank.play_music(m['clap'], loop=False)
        else:
            st = self.igm.settings
            w.start_music(0.0, clap=True,
                          music_on=st.audio_enabled and st.music_enabled,
                          audio_on=st.audio_enabled)
            if self.tutorial is not None and self._show_tutorial_after_intro:
                self.tutorial.activate()

    def _draw_loading(self, name):
        """the blocking load's screen: LevelTransition's when a level is
        loaded from a level (LevelLoader.cs:77-88), LevelLoader's when it
        comes from Entry; drawn once, held for LoadTimer"""
        season = 's2' if name.startswith('Level2') else self.level_season \
            if self.state == 'level' else 's1'
        src = None
        if self.state == 'level':
            tp, _ = scene_path('Transition', self.level_season)
            sd = SceneData(tp)
            lt = sd.find('LevelTransition')
            src = lt[0][1] if lt else None
            strings = load_strings(ROOT, sd.season,
                                   self.prefs.get_int('Language', 0))
        elif self.menu is not None:
            ll = self.menu.scene.find('LevelLoader')
            src = ll[0][1] if ll else None
            strings = self.menu.strings
        if src is None:
            return
        loc = lambda k: strings.get(k, '') if k else ''
        screen = LoadingScreen(src, WIDTH, HEIGHT, loc)
        sdl2.SDL_SetRenderDrawColor(self.rnd, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.rnd)
        screen.draw(self.gfx)
        sdl2.SDL_RenderPresent(self.rnd)
        if not self.headless:
            sdl2.SDL_Delay(int(screen.load_timer * 1000))

    # -- the level hooks ----------------------------------------------------
    def _on_score(self, kind):
        """HUD.CheckClick's score buttons (HUD.cs:1287-1299)"""
        if kind == 'restart':
            self._pending = self.level_scene_name
        else:
            self.open_level_selection = True     # Level.OpenLevelSelection
            self._pending = 'Entry'

    def _show_exit_confirmation(self, pawn):
        """Woody.ShowExitConfirmation (Woody.cs:552-556) over the pawn's
        park; the dialog's verdict runs ConfirmationDismissed (cs:558-568)"""
        igm = self.igm

        def dismissed(accept):
            if accept:
                pawn.continue_exit()
            else:
                pawn.abort_exit()
            return True

        igm.exit_message.show(igm.loc(pawn.exit_confirm_message), dismissed)

    def _save_score(self):
        """GameInfo.CalculateScore's tail (GameInfo.cs:409/429-435):
        Level.SaveScore(GetGameOnlyLevelIndex(), ...); Perfect is
        CalculateRating's >= 100 arm (cs:438-465). Runs off
        World.on_score_computed — after the numbers exist, not at the
        GameEnding flag (the all-tricks win separates them by 2.5 s)."""
        if self._score_saved:
            return
        self._score_saved = True
        w = self.viewer.world
        g = w.game
        idx = level_index(self.level_season, self.igm.scene.scene)
        perfect = g.won and g.final_viewer_rating >= 100
        self.igm.progress.save_score(idx, g.completed,
                                     g.final_viewer_rating, g.won, perfect)

    # -- input -----------------------------------------------------------
    def _pump(self):
        """one frame of SDL events -> the edges the scenes consume"""
        ev = sdl2.SDL_Event()
        up = pressed = up_right = escape = False
        while sdl2.SDL_PollEvent(ctypes.byref(ev)):
            if ev.type == sdl2.SDL_QUIT:
                self.quit = True
            elif ev.type == sdl2.SDL_MOUSEMOTION:
                self._mouse = (ev.motion.x, ev.motion.y)
                if self.viewer is not None and self.viewer.world.is_dexterity_on:
                    for ds in self.viewer.world.dex_states.values():
                        if ds.enabled:
                            ds.input = (ds.input[0] + ev.motion.xrel * 25.0,
                                        ds.input[1] - ev.motion.yrel * 25.0)
            elif ev.type == sdl2.SDL_MOUSEBUTTONDOWN:
                self._mouse = (ev.button.x, ev.button.y)
                if ev.button.button == sdl2.SDL_BUTTON_LEFT:
                    self._mouse_down = True
                    pressed = True
            elif ev.type == sdl2.SDL_MOUSEBUTTONUP:
                self._mouse = (ev.button.x, ev.button.y)
                if ev.button.button == sdl2.SDL_BUTTON_LEFT:
                    self._mouse_down = False
                    up = True
                elif ev.button.button == sdl2.SDL_BUTTON_RIGHT:
                    up_right = True
            elif ev.type == sdl2.SDL_KEYUP and \
                    ev.key.keysym.sym == sdl2.SDLK_ESCAPE:
                escape = True
            elif ev.type == sdl2.SDL_KEYDOWN and self.state == 'level':
                k = ev.key.keysym.sym
                if k == sdl2.SDLK_TAB and self.viewer.woody:
                    self.viewer.woody.toggle_sneak()
                elif sdl2.SDLK_0 <= k <= sdl2.SDLK_9:
                    idx = (k - sdl2.SDLK_1) if k != sdl2.SDLK_0 else -1
                    self.viewer.world.inventory.select(idx)
        return pressed, up, up_right, escape

    def feed(self, pressed, up, up_right, escape):
        """a scripted frame (the tests drive this instead of _pump)"""
        self._events = (pressed, up, up_right, escape)

    # -- the frame ---------------------------------------------------------
    def tick(self, dt, events=None):
        pressed, up, up_right, escape = events if events is not None \
            else self._pump()
        if self.state == 'menu':
            self._tick_menu(dt, pressed, up, up_right, escape)
        else:
            self._tick_level(dt, pressed, up, up_right, escape)
        if self._pending is not None:
            name, self._pending = self._pending, None
            if name == 'Entry':
                self.open_entry()
            else:
                self.load_level(name)

    def _tick_menu(self, dt, pressed, up, up_right, escape):
        m = self.menu
        m.feed_input(self._mouse, self._mouse_down, pressed, up, up_right,
                     escape)
        m.tick(dt)
        self._sync_fullscreen(m.settings)
        if m.quit_requested:
            self.quit = True
        elif m.reload_requested:
            # SetCurrentLanguage's blocking reload of Entry
            # (LocalizationManager.cs:196-204)
            self.open_entry()
        elif m.pending_load:
            name = m.pending_load
            m.pending_load = None
            m.is_loading_level = False
            self.load_level(name)

    def _tick_level(self, dt, pressed, up, up_right, escape):
        v, igm = self.viewer, self.igm
        w = v.world
        igm.feed_input(self._mouse, self._mouse_down, pressed, up, up_right,
                       escape)
        if self.cards is not None and self.cards.running:
            # the title cards: the scene breathes, nothing acts
            self._cards_elapsed += dt
            w.tick_ambient(dt)
            if self.cards.tick(dt, up or up_right, escape):
                # StartGame (IntroAnimation.cs:283-320): the port's world
                # clock starts here; the music picks up the load-time
                # clocks, the camera glides back to Woody (SnapToWoody,
                # cs:305 -> CameraMover.SnapToPawn)
                st = igm.settings
                w.start_music(self._cards_elapsed, clap=False,
                              music_on=st.audio_enabled and st.music_enabled,
                              audio_on=st.audio_enabled)
                w.snap_request = 'Woody'
                # StartGame's tutorial arm (IntroAnimation.cs:305-307)
                if self.tutorial is not None \
                        and self._show_tutorial_after_intro:
                    self.tutorial.activate()
            v._frame_dt = dt
            v.virtual_mouse = self._mouse
            v.virtual_mouse_down = self._mouse_down
            v.draw(overlay=lambda: self.cards.draw(self.gfx, dt))
            return
        # the menu scene of the level: dialogs first (Update), then widgets
        igm.tick(dt)
        self._sync_fullscreen(igm.settings)
        if igm.quit_requested:
            self.quit = True
        if igm.pending_load:
            name = igm.pending_load
            igm.pending_load = None
            igm.is_loading_level = False
            if igm.open_level_selection:
                self.open_level_selection = True
                igm.open_level_selection = False
            self._pending = name
            return
        # Woody.FindInput's Esc -> ToggleMenu (Woody.cs:583-586), once the
        # intro is done and the dexterity is off; the dialog ate its Esc
        # inside igm.tick (ExitConfirmation.Update)
        if igm.key_escape and not w.is_dexterity_on:
            w.toggle_menu()
            igm.clear_input()
        # the world click on the press edge (the viewer's convention):
        # dropped while timeScale is 0 (Woody.cs:637) or the dialog shows
        # (HUD.CheckClick's gate, HUD.cs:1282-1285); the HUD itself stays
        # clickable while paused (the power button, HUD.cs:1302-1306), so
        # the click goes through handle_click, whose own gates sort it
        if pressed and not igm.is_exit_confirmation_shown():
            v.handle_click(*self._mouse)
        w.menu_open = igm.enabled
        if igm.time_scale > 0.0 and not w.menu_open:
            w.tick(min(dt, 0.1))
            if self.tutorial is not None and self.tutorial.active:
                self.tutorial.tick(dt)
            if self.tutorial_camera is not None \
                    and self.tutorial_camera.active:
                self.tutorial_camera.tick(dt)
            woody = v.woody
            if woody is not None and woody.stored_input is not None \
                    and not woody.input_locked and not woody.anim.blocking \
                    and not woody.is_warping and not w.game.ending:
                click, woody.stored_input = woody.stored_input, None
                v.world_click(*click)
            if w.is_dexterity_on and woody:
                v.cam.x, v.cam.y = woody.sprite.x, woody.sprite.y
        v._update_camera(dt if igm.time_scale > 0.0 else 0.0)
        v._clamp_camera()
        v._frame_dt = dt
        v.virtual_mouse = self._mouse
        v.virtual_mouse_down = self._mouse_down
        v.draw(overlay=lambda: self._draw_level_overlay(dt))

    def _draw_level_overlay(self, dt):
        igm = self.igm
        if self.tutorial is not None and self.tutorial.active:
            # LevelScript.OnGUI skips while a menu is open (cs:100)
            self.tutorial.draw(self.gfx, dt,
                               menu_open=igm.enabled
                               or igm.is_exit_confirmation_shown())
        if self.tutorial_camera is not None and self.tutorial_camera.active:
            self.tutorial_camera.draw(self.gfx)
        if igm.enabled:
            igm.draw(self.gfx, dt)
        else:
            # the dialog can show without the menu (the exit door)
            igm.exit_message.draw(self.gfx)

    def draw_menu(self, dt):
        sdl2.SDL_SetRenderDrawColor(self.rnd, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.rnd)
        self.menu.draw(self.gfx, dt)
        sdl2.SDL_RenderPresent(self.rnd)

    def run(self):
        last = time.time()
        while not self.quit:
            now = time.time()
            dt, last = now - last, now
            self.tick(min(dt, 0.1))
            if self.state == 'menu':
                self.draw_menu(dt)
        self.prefs.save()                 # Unity saves the prefs on exit


def have_assets():
    """the extracted Season-1 assets are the minimum the Entry needs"""
    return os.path.isdir(os.path.join(asset_root(), 'textures', 's1'))


def _message_box(title, text):
    """a last-resort dialog for the double-click user (works before any
    window exists); the console gets the text either way"""
    print(text)
    try:
        sdl2.SDL_ShowSimpleMessageBox(sdl2.SDL_MESSAGEBOX_INFORMATION,
                                      title.encode(), text.encode(), None)
    except Exception:
        pass


def bootstrap_assets():
    """first run: find the game's apk/obb (or xapk) next to the bundle,
    unpack it to a temp directory and extract the textures, audio,
    strings and fonts into the asset root — tools/unpack.py +
    tools/extract_assets.py, in-process (the bundle has no shell)"""
    import shutil, tempfile
    sys.path.insert(0, os.path.join(data_root(), 'tools'))
    from unpack import find_sources, unpack
    from extract_assets import extract_season
    root = asset_root()
    sources = {}
    for d in dict.fromkeys([root, os.getcwd()]):
        sources = find_sources(d)
        if sources:
            break
    if not sources:
        _message_box('Neighbours from Hell', (
            'No game data found.\n\n'
            'Put the game\'s .apk and .obb (or the .xapk) next to the\n'
            'executable and start it again: the assets are extracted\n'
            'from your own copy of the game on first run.\n\n'
            'Season 1 is required; Season 2 is optional.\n'
            'Looked in: %s' % root))
        return False
    if 's1' not in sources:
        _message_box('Neighbours from Hell', (
            'Only Season 2 data found — Season 1 is required (it carries '
            'the menu). Put its apk/obb here too: %s' % root))
        return False
    for season in ('s1', 's2'):
        entry = sources.get(season)
        if entry is None:
            continue
        print('== extracting %s (one-time, a few minutes) ==' % season)
        tmp = tempfile.mkdtemp(prefix='nfh-data-')
        try:
            unpack(entry, tmp)
            extract_season(tmp, root, season)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return have_assets()


def main(argv):
    if '--smoke' in argv:
        # the CI's bundle check: boot the menu headless and exit
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
        from prefs import MemoryPrefs
        app = App(headless=True, prefs=MemoryPrefs())
        for _ in range(5):
            app.tick(1.0 / 60.0, events=(False, False, False, False))
        app.tick(1.0 / 60.0, events=(False, True, False, False))
        app.draw_menu(1.0 / 60.0)
        print('smoke OK: state=%s windows=%d' % (
            app.state, sum(1 for go, e in app.menu.scene.find('ControlWindow')
                           if app.menu.scene.active_in_hierarchy(go))))
        return 0
    if not have_assets() and not bootstrap_assets():
        return 1
    start = argv[1] if len(argv) > 1 else 'Entry'
    app = App()
    if start != 'Entry':
        app.load_level(start)
    app.run()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
