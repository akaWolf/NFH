"""The menu scene (Entry) and the flow widgets — Control.cs and its
subclasses, LevelDataGUIRenderer, GameIntroAnimation, Credits,
LanguageComboBox, ExitConfirmation (+DirectorAnimation), MenuMouseController,
the Entry scene's Level/MusicPlayer glue and the PlayerPrefs-backed level
progress (Level.cs:265-420) — driven by the exported scene JSON
(levels/<season>/Entry.json: the raw objects for the GameObject tree, the
resolved `hud` section for the components' textures, styles and strings).

Input: the original is the mobile build (Input.touchCount gates), so the
mouse plays the touch: hovering = the pointer over the control, pressed =
the left button held, a click = the button released over the control
(Control.LateUpdate, Control.cs:243-250). The hover texture (index 1) is
drawn for a hovered, unpressed button — the PC build's look, which the
mobile CheckTextureIndex (cs:187-225) never reaches; the radio tiles do it
themselves (ControlRadioButton.cs:105-125).
"""
import json, os, re

from gui import (adjust_rect, matrix_rect, font_size, point_in_rect,
                 draw_tex, style_color, DESIGN_W, DESIGN_H)

LANGUAGES = ['Lang', 'NEW_LANG_SP', 'NEW_LANG_FR', 'NEW_LANG_DE',
             'NEW_LANG_IT', 'NEW_LANG_PL', 'NEW_LANG_HU', 'NEW_LANG_CH',
             'NEW_LANG_RU']                    # Language.cs, in enum order

# GUIDepth (GUIDepth.cs): a higher value draws further back
GUI_DEPTH = {'BackItems': 72, 'BackDoors': 64, 'Items': 32, 'ItemsFront': 24,
             'Doors': 22, 'Alerters': 20, 'FrontDoors': 19, 'Rottweiler': 18,
             'Woody': 16, 'LevelFenceBack': 14, 'LevelFence': 13,
             'BackHUD': 12, 'HUD': 11, 'MainMenu': 10, 'Menu': 9,
             'MainMenuControl': 8, 'MainMenuFont': 7, 'ConfirmMessage': 2,
             'MouseIcon': 1}

# GameInfo.GetGameOnlyLevelIndex (GameInfo.cs:494-506): Application.
# loadedLevel - 2 for Season 1 (Intro101 = level2 -> 0, Level101 = level5
# -> 3), loadedLevel + 15 for Season 2 (Level201 = level3 -> 18 ...
# Level214 = level16 -> 31); Level.LevelsCount is 32 (Level.cs:105).
# `build` is the export's `scene` field ('level17'). NOTE the original
# build order swaps Level112/Level113 (level17/level16), so the scenes
# compute 15/14 while their menu tiles serialize LevelIndex 14/15 — the
# in-level title card and the progress slot follow the loadedLevel arithmetic
# and land on the *other* level's data, an original bug the port keeps
# (runtime/README.md).
def level_index(season, build):
    n = int(re.sub(r'\D', '', build or '') or 0)
    return n - 2 if season == 's1' else n + 15


LEVELS_COUNT = 32


# ---------------------------------------------------------------------------
# strings (LocalizationManager)

def load_strings(root, season, language):
    """LocalizationManager.LoadLocalizationFile for Localization/Final/<lang>
    (LocalizationManager.cs:30-56; the file by SettingKey.Language,
    cs:80-117): KEY<>VALUE lines, ';' comments, the first key wins"""
    out = {}
    name = LANGUAGES[language] if 0 <= language < len(LANGUAGES) else 'Lang'
    p = os.path.join(root, 'strings', season, name + '.txt')
    if not os.path.exists(p):
        p = os.path.join(root, 'strings', season, 'Lang.txt')
    if not os.path.exists(p):
        return out
    for line in open(p, encoding='utf-8', errors='replace'):
        line = line.rstrip('\r\n')
        if not line or line.startswith(';') or '<>' not in line:
            continue
        k, v = line.split('<>', 1)
        out.setdefault(k, v)
    return out


# ---------------------------------------------------------------------------
# the level progress (Level.cs:265-420)

class Progress:
    """Level's PlayerPrefs helpers: the per-level Duration / TricksTotal /
    MinRating tables the Entry scene seeds once (InitializeLevelsData,
    Level.cs:265-275), the scores (SaveScore, cs:348-354), ResetData"""

    def __init__(self, prefs):
        self.prefs = prefs

    def initialize(self, durations, tricks_total, min_ratings):
        if self.prefs.get_int('LevelsInitialized', 0) != 1:
            for i in range(len(durations)):
                self.prefs.set_int('Duration%d' % i, int(durations[i]) * 60)
                self.prefs.set_int('TricksTotal%d' % i, int(tricks_total[i]))
                self.prefs.set_int('MinRating%d' % i, int(min_ratings[i]))
            self.prefs.set_int('LevelsInitialized', 1)
            self.prefs.save()

    def min_rating(self, level):
        return self.prefs.get_int('MinRating%d' % level)

    def duration(self, level):
        return self.prefs.get_int('Duration%d' % level)

    def tricks_total(self, level):
        return self.prefs.get_int('TricksTotal%d' % level)

    def tricks_played(self, level):
        return self.prefs.get_int('TricksPlayed%d' % level)

    def rating_achieved(self, level):
        return self.prefs.get_int('RatingAchieved%d' % level)

    def is_passed(self, level):
        """IsLevelPassed -> (passed, perfect)"""
        return (self.prefs.get_int('LevelCompleted%d' % level) == 1,
                self.prefs.get_int('LevelPerfect%d' % level) == 1)

    def save_score(self, level, completed, rating, won, perfect,
                   force=False):
        """Level.SaveScore: tricks/rating only rise, completion sticks"""
        if self.tricks_played(level) < completed or force:
            self.prefs.set_int('TricksPlayed%d' % level, completed)
        if self.rating_achieved(level) < rating or force:
            self.prefs.set_int('RatingAchieved%d' % level, rating)
        passed, was_perfect = self.is_passed(level)
        if not passed or force:
            self.prefs.set_int('LevelCompleted%d' % level, 1 if won else 0)
            if not was_perfect or force:
                self.prefs.set_int('LevelPerfect%d' % level,
                                   1 if perfect else 0)
        elif not was_perfect and passed:
            self.prefs.set_int('LevelPerfect%d' % level, 1 if perfect else 0)
        self.prefs.save()

    def reset(self):
        """Level.ResetData (cs:355-361)"""
        for i in range(LEVELS_COUNT):
            self.save_score(i, 0, 0, False, False, force=True)


class Settings:
    """Level.LoadSettings (Level.cs:295-310): the settings the PlayerPrefs
    hold, with the call sites' defaults"""

    def __init__(self, prefs):
        self.prefs = prefs
        self.load()

    def load(self):
        p = self.prefs
        self.music_enabled = p.get_int('MusicEnabled', 1) == 1
        self.audio_enabled = p.get_int('AudioEnabled', 1) == 1
        self.music_level = p.get_float('MusicLevel', 10.0)   # MaxMusicLevel
        self.audio_level = p.get_float('AudioLevel', 10.0)   # MaxAudioLevel
        self.timed_game = p.get_int('TimedGame', 1) == 1
        self.trick_camera = p.get_int('TrickCamera', 0) == 1
        self.language = p.get_int('Language', 0)
        self.sensibility = p.get_float('Sensibility', 0.5)
        # the port's own key (the PC build's fullscreen option; the mobile
        # decompile has no SettingKey for it)
        self.fullscreen = p.get_int('Fullscreen', 0) == 1

    @property
    def music_volume(self):
        """MusicPlayer: volume = Level.MusicLevel * Level.AudioLevel, which
        the AudioSource clamps into [0, 1]"""
        return max(0.0, min(1.0, self.music_level * self.audio_level))

    @property
    def sound_volume(self):
        return max(0.0, min(1.0, self.audio_level))


# ---------------------------------------------------------------------------
# the scene data: the GameObject tree with its active flags

class SceneData:
    """the exported scene: objects, the GameObject tree (active flags,
    parents, children), the resolved components keyed by (type, go)"""

    def __init__(self, path):
        self.path = path
        d = json.load(open(path, encoding='utf-8'))
        self.scene = d.get('scene')
        self.season = 's2' if '/s2/' in path.replace('\\', '/') else 's1'
        self.objs = d['objects']
        self.resolved = {}                # (type, go) -> resolved data
        for typ, lst in (d.get('hud') or {}).items():
            for e in lst:
                go = (e.get('m_GameObject') or {}).get('path')
                if go is not None:
                    self.resolved[(typ, go)] = e
        self.active = {}                  # go -> GameObject.active
        # the port's Entry-scene switch (runtime/README.md): when set,
        # SetObjectActive(obj, True) re-applies each direct child's
        # AUTHORED activeSelf instead of forcing True — the original
        # forces True (Control.cs:406-424), which the in-game menu needs
        # (its whole widget set ships inactive), but in the Entry options
        # it resurrects the two authored-off desktop buttons (Back, Lang)
        # and paints BACK across RESET SAVED GAME DATA
        self.restore_authored = False
        self.authored_active = {}
        self.parent = {}
        self.children = {}
        self.name = {}
        self.comps = {}                   # go -> [(type, pid)]
        for pid, o in self.objs.items():
            if o['type'] == 'GameObject':
                g = int(pid)
                self.active[g] = bool(o['data'].get('active', True))
                self.authored_active[g] = self.active[g]
                self.name[g] = o['data'].get('name')
        for pid, o in self.objs.items():
            dd = o.get('data') or {}
            if o['type'] == 'Transform':
                # the exporter's raw Transform: gameObject / father are ids
                go = dd.get('gameObject')
                f = dd.get('father')
                fo = self.objs.get(str(f)) if f else None
                fgo = ((fo or {}).get('data') or {}).get('gameObject')
                if go is not None and fgo is not None:
                    self.parent[go] = fgo
                    self.children.setdefault(fgo, []).append(go)
                continue
            go = (dd.get('m_GameObject') or {}).get('path') \
                if isinstance(dd.get('m_GameObject'), dict) else None
            if go is not None:
                self.comps.setdefault(go, []).append((o['type'], int(pid)))

    def find(self, typ):
        return [(go, e) for (t, go), e in self.resolved.items() if t == typ]

    def go_of(self, pid):
        """a serialized PPtr's path -> the owning GameObject id: a
        component reference (StartButton, Group, LevelDataRenderer... are
        component pointers) resolves through its m_GameObject; a GameObject
        reference returns itself"""
        if pid is None:
            return None
        o = self.objs.get(str(pid))
        if o is None:
            return None
        if o.get('type') == 'GameObject':
            return pid
        d = o.get('data') or {}
        go = d.get('m_GameObject')
        if isinstance(go, dict):
            return go.get('path')
        return d.get('gameObject')

    def go_name(self, go):
        return self.name.get(go)

    def active_in_hierarchy(self, go):
        """GameObject.activeInHierarchy: itself and every parent active"""
        g = go
        while g is not None:
            if not self.active.get(g, True):
                return False
            g = self.parent.get(g)
        return True

    def set_active(self, go, active):
        """Control.SetObjectActive (Control.cs:406-424): the object and its
        direct children — forced to `active`, except under the Entry
        scene's restore_authored switch (see __init__), where enabling
        re-applies each child's authored activeSelf"""
        if go is None:
            return
        self.active[go] = bool(active)
        for c in self.children.get(go, ()):
            if active and self.restore_authored:
                self.active[c] = self.authored_active.get(c, True)
            else:
                self.active[c] = bool(active)

    def set_active_self(self, go, active):
        """GameObject.SetActive on the object alone"""
        if go is not None:
            self.active[go] = bool(active)


# ---------------------------------------------------------------------------
# the widgets

class Control:
    """Control.cs — the base widget: textures by state, the label, the
    tooltip, the setting it carries, the click"""

    kind = 'Control'

    def __init__(self, scene, go, d, menu):
        self.scene = scene
        self.go = go
        self.d = d
        self.menu = menu
        self.W, self.H = menu.W, menu.H
        tex = d.get('Textures') or []
        self.textures = [(t or {}).get('texture') for t in tex]
        self.use_mobile_textures = bool(d.get('UseMobileTextures'))
        mtex = d.get('MobileTextures') or []
        self.mobile_textures = [(t or {}).get('texture') for t in mtex]
        self.screen_rect = adjust_rect(d.get('ScreenRect'), self.W, self.H)
        self.screen_mobile_rect = adjust_rect(d.get('ScreenMobileRect'),
                                              self.W, self.H)
        self.use_mobile_text = bool(d.get('UseMobileText'))
        self.text_key = d.get('TextString') or ''
        self.text_mobile_key = d.get('TextStringMobile') or ''
        self.text = ''
        self.text_mobile = ''
        self.dont_draw_percentages = bool(d.get('DontDrawPercentages'))
        tr = d.get('TextRect'); tmr = d.get('TextMobileRect')
        if not self.dont_draw_percentages:
            tr = adjust_rect(tr, self.W, self.H)
            tmr = adjust_rect(tmr, self.W, self.H)
        else:
            tr = (0.0, 0.0, 0.0, 0.0) if not tr else (
                tr.get('x', 0.0), tr.get('y', 0.0), tr.get('width', 0.0),
                tr.get('height', 0.0))
            tmr = (0.0, 0.0, 0.0, 0.0) if not tmr else (
                tmr.get('x', 0.0), tmr.get('y', 0.0), tmr.get('width', 0.0),
                tmr.get('height', 0.0))
        self.text_rect = self._text_rect0 = tr
        self.text_mobile_rect = self._text_mobile_rect0 = tmr
        self.multi_lang = [(m.get('CurrLanguage'),
                            adjust_rect(m.get('TextRect'), self.W, self.H),
                            adjust_rect(m.get('TextMobileRect'),
                                        self.W, self.H))
                           for m in (d.get('MultiLangTextRect') or [])]
        self.text_style = d.get('TextStyle') or {}
        self.hover_text_style = d.get('HoverTextStyle') or {}
        self.tooltip_key = d.get('Tooltip') or ''
        self.tooltip_mobile_key = d.get('ToolTipMobile') or ''
        self.use_mobile_tooltip = bool(d.get('UseMobileToolTip'))
        self.tooltip_rect = adjust_rect(d.get('TooltipRect'), self.W, self.H)
        self.tooltip_mobile_rect = adjust_rect(d.get('TooltipMobileRect'),
                                               self.W, self.H)
        self.tooltip_style = d.get('TooltipStyle') or {}
        self.depth = GUI_DEPTH.get(d.get('Depth'), 8)
        self.setting_control = bool(d.get('SettingControl'))
        self.setting_key = d.get('SettingKey') or 'AudioEnabled'
        self.setting_type = d.get('SettingType') or 'Int'
        self.locked = bool(d.get('Locked'))
        self.apply_settings = bool(d.get('ApplySettings'))
        self.default_int = int(d.get('DefaultInt') or 0)
        self.is_language = bool(d.get('IsLaguage'))
        self.language_type = d.get('LanguageType') or 'Lang'
        self.set_language = bool(d.get('SetLanguage'))
        self.unset_language = bool(d.get('UnsetLanguage'))
        self.path_texture = (d.get('PathTexture') or {}).get('texture') \
            if isinstance(d.get('PathTexture'), dict) else None
        self.path_rect = adjust_rect(d.get('PathRect'), self.W, self.H)
        self.texture_index = 0
        self.texture_index_delta = 0
        self.int_value = 0
        self.float_value = 0.0
        self.string_value = ''
        self.hover_seconds = 0.0          # SecondCountAux
        self.is_pressed = False
        # font sizes: Control.Start sets TooltipStyle to CalculateFontSize;
        # the subclasses size TextStyle/HoverTextStyle (ControlButton 0,
        # ControlToggle 0, ControlSlider 0, ControlRadioButton -4)
        self.font = int(font_size(self.W, self.H))
        self.tooltip_font = int(font_size(self.W, self.H))
        self.text_font = int(font_size(self.W, self.H))
        self.hover_font = int(font_size(self.W, self.H))
        self.start()

    # -- Control.Start (cs:74-98) ------------------------------------------
    def start(self):
        self.switch_text_rect()
        self.load_localization_data()
        if self.setting_control:
            self.load_value()

    def load_localization_data(self):
        loc = self.menu.loc
        self.text = loc(self.text_key)
        self.text_mobile = loc(self.text_mobile_key)
        self.tooltip = loc(self.tooltip_key)
        self.tooltip_mobile = loc(self.tooltip_mobile_key)

    def switch_text_rect(self):
        """SwitchTextRect / CheckLanguage (cs:323-346)"""
        lang = LANGUAGES[self.menu.settings.language] \
            if 0 <= self.menu.settings.language < len(LANGUAGES) else 'Lang'
        for cur, tr, tmr in self.multi_lang:
            if cur == lang:
                self.text_rect, self.text_mobile_rect = tr, tmr
                return
        self.text_rect = self._text_rect0
        self.text_mobile_rect = self._text_mobile_rect0

    # -- the setting value (cs:268-304) ------------------------------------
    def save_value(self):
        p = self.menu.prefs
        if self.setting_type == 'Int':
            p.set_int(self.setting_key, self.int_value)
        elif self.setting_type == 'Float':
            p.set_float(self.setting_key, self.float_value)
        else:
            p.set_string(self.setting_key, self.string_value)

    def load_value(self):
        p = self.menu.prefs
        if self.setting_type == 'Int':
            self.int_value = p.get_int(self.setting_key, self.default_int)
        elif self.setting_type == 'Float':
            self.float_value = p.get_float(self.setting_key,
                                           float(self.default_int))
        else:
            self.string_value = p.get_string(self.setting_key)

    # -- geometry ----------------------------------------------------------
    @property
    def rect(self):
        return self.screen_mobile_rect if self.use_mobile_textures \
            else self.screen_rect

    @property
    def active(self):
        return self.scene.active_in_hierarchy(self.go)

    def can_input(self):
        """CanInput (cs:348-355): nothing while a level loads"""
        return not self.menu.is_loading_level

    def is_mouse_over_control(self):
        """IsMouseOverControl (cs:238-242)"""
        mx, my = self.menu.mouse
        return point_in_rect(mx, my, self.rect) and not self.menu.confirm_opened

    def is_mouse_hovering(self):
        """IsMouseHovering (cs:234-236): the touch is the pointer here"""
        return self.is_mouse_over_control()

    # -- the per-frame work (OnGUI / LateUpdate) ---------------------------
    def check_texture_index(self):
        """CheckTextureIndex (cs:187-225): pressed while the pointer is
        down over the control, normal otherwise — plus the PC hover look"""
        if self.is_mouse_hovering():
            if self.menu.mouse_down:
                if not self.is_pressed:
                    self.is_pressed = True
                    self.menu.click_sound()
                self.texture_index = self.texture_index_delta + 2
            else:
                self.is_pressed = False
                self.texture_index = self.texture_index_delta + 1 \
                    if self._has_texture(self.texture_index_delta + 1) \
                    else self.texture_index_delta
        else:
            self.texture_index = self.texture_index_delta
            self.is_pressed = False

    def _has_texture(self, i):
        arr = self.mobile_textures if self.use_mobile_textures \
            else self.textures
        return 0 <= i < len(arr) and arr[i]

    def _texture(self, i):
        arr = self.mobile_textures if self.use_mobile_textures \
            else self.textures
        if 0 <= i < len(arr):
            return arr[i]
        return arr[0] if arr else None

    def draw_texture(self, g):
        tex = self._texture(self.texture_index)
        if tex:
            g.tex(tex, self.rect)

    def draw_text(self, g, dt):
        """DrawText (cs:127-184): the hover style while hovered, the tooltip
        after 2 s of a held pointer"""
        if self.use_mobile_text:
            rect, text = self.text_mobile_rect, self.text_mobile
        else:
            rect, text = self.text_rect, self.text
        if self.is_mouse_hovering():
            g.label(rect, text, self.hover_text_style, self.hover_font)
            if self.menu.mouse_down and self.hover_seconds >= 2.0:
                if self.use_mobile_tooltip:
                    g.label(self.tooltip_mobile_rect, self.tooltip_mobile,
                            self.tooltip_style, self.tooltip_font)
                else:
                    g.label(self.tooltip_rect,
                            self.tooltip_mobile if self.use_mobile_text
                            else self.tooltip,
                            self.tooltip_style, self.tooltip_font)
            else:
                self.hover_seconds += dt
        else:
            g.label(rect, text, self.text_style, self.text_font)
            self.hover_seconds = 0.0

    def draw_path(self, g):
        if self.path_texture:
            g.tex(self.path_texture, self.path_rect)

    def on_gui(self, g, dt):
        """Control.OnGUI (cs:110-119)"""
        if self.can_input():
            self.check_texture_index()
            self.draw_texture(g)
            self.draw_text(g, dt)
            self.draw_path(g)

    def late_update(self):
        """Control.LateUpdate (cs:243-250): the click is the release over
        the control"""
        if self.can_input() and self.menu.mouse_up \
                and self.is_mouse_over_control() and not self.locked \
                and not self.menu.is_exit_confirmation_shown():
            self.do_work()

    def do_work(self):
        """Control.DoWork (cs:251-265)"""
        if self.can_input():
            if self.setting_control:
                self.save_value()
            if self.apply_settings:
                self.menu.load_settings()


class ControlButton(Control):
    """ControlButton.cs: a window switch, a setting save, a level start, a
    confirmation, the language buttons"""

    kind = 'ControlButton'

    def __init__(self, scene, go, d, menu):
        self.object_to_enable = (d.get('ObjectToEnable') or {}).get('path')
        self.object_to_disable = (d.get('ObjectToDisable') or {}).get('path')
        self.require_confirmation = bool(d.get('RequireConfirmation'))
        self.confirm_key = d.get('ConfirmString') or ''
        self.styled_confirm = bool(d.get('StyledConfirm'))
        self.confirm_style = d.get('ConfirmStyle') or {}
        self.level_to_start = d.get('LevelToStart') or ''
        self.save_settings = bool(d.get('SaveSettings'))
        self.disable_in_game_menu = bool(d.get('DisableInGameMenu'))
        self.return_to_level_selection = bool(d.get('ReturnToLevelSelection'))
        self.quit_application = bool(d.get('QuitApplication'))
        self.reset_data = bool(d.get('ResetData'))
        self.level_buttons_group = (d.get('LevelButtonsGroup') or {}).get('path')
        self.hide_level_data = bool(d.get('HideLevelData'))
        self.show_level_data = bool(d.get('ShowLevelData'))
        self.hide_on_android = bool(d.get('HideOnAndroid'))
        self.is_button_selected = False
        self.show_confirm_action = False
        Control.__init__(self, scene, go, d, menu)
        # ControlButton.Start (cs:50-64): text sizes, the confirm rect
        self.text_font = int(font_size(self.W, self.H))
        self.hover_font = int(font_size(self.W, self.H))
        self.confirm_font = int(font_size(self.W, self.H)) - 3
        self.confirm_rect = adjust_rect(d.get('ConfirmRect'), self.W, self.H)
        self.confirm_string = self.menu.loc(self.confirm_key)

    def load_localization_data(self):
        Control.load_localization_data(self)
        self.confirm_string = self.menu.loc(self.confirm_key)

    def check_texture_index(self):
        """the language buttons show their selected state (cs:220-234)"""
        if self.is_language:
            self.texture_index = 2 if self.is_button_selected else 0
        else:
            Control.check_texture_index(self)

    def set_button_selected(self, selected):
        self.is_button_selected = selected

    def do_work(self):
        """ControlButton.DoWork (cs:75-96)"""
        self.menu.tooltip_control = self
        if self.setting_control:
            self.save_value()
        if self.require_confirmation:
            self.menu.confirm_opened = self.show_confirm_action = True
            if not self.styled_confirm:
                self.menu.exit_message.show(self.confirm_string,
                                            self._confirmation_dismissed)
            else:
                self.menu.exit_message.show_styled(
                    self.confirm_style, self.confirm_rect,
                    self.confirm_string, self._confirmation_dismissed)
        else:
            self.do_actual_work()

    def _confirmation_dismissed(self, accept):
        self.menu.confirm_opened = self.show_confirm_action = False
        if accept:
            self.do_actual_work()
        return True

    def do_actual_work(self):
        """DoActualWork (cs:97-163). CanLaunchApplication / the split-app
        objects (cs:98-106, 189-199) address the two store apps; this port
        holds both seasons in one process, so the plain ObjectToEnable /
        Disable pair runs."""
        m = self.menu
        if self.reset_data:
            m.progress.reset()
            grp = m.widget_by_go(self.level_buttons_group,
                                 ControlRadioButtonGroup)
            if grp is not None:
                grp.load_textures()
        if self.save_settings:
            m.prefs.save()
        if self.is_language:
            m.selected_lang = LANGUAGES.index(self.language_type) \
                if self.language_type in LANGUAGES else 0
        if self.set_language:
            m.set_current_language(m.selected_lang, reload=True,
                                   selected_by_player=True)
        elif self.unset_language:
            m.selected_lang = m.settings.language
        self.activate_objects()
        self.start_level()
        if self.disable_in_game_menu:
            m.disable_in_game_menu()
        if self.quit_application:
            m.quit()
        if self.hide_level_data:
            m.show_level_data(False)
        if self.show_level_data:
            m.show_level_data(True)

    def start_level(self):
        """StartLevel (cs:164-185)"""
        if not self.level_to_start:
            return
        self.menu.prefs.save()
        if self.return_to_level_selection:
            self.menu.open_level_selection = True
        if self.level_to_start == 'samesame':
            self.menu.load_level(self.menu.current_scene_name)
        else:
            self.menu.load_level(self.level_to_start)

    def activate_objects(self):
        self.scene.set_active(self.object_to_enable, True)
        self.scene.set_active(self.object_to_disable, False)


class ControlWindow(Control):
    """ControlWindow.cs: a backdrop and a frame of widgets; Esc closes it
    to MainMenu, the FirstWindow's Esc asks to quit"""

    kind = 'ControlWindow'

    def __init__(self, scene, go, d, menu):
        self.main_menu = (d.get('MainMenu') or {}).get('path')
        self.close_with_any_key = bool(d.get('CloseWithAnyKey'))
        self.first_window = bool(d.get('FirstWindow'))
        self.confirm_key = d.get('ConfirmString') or ''
        self.show_level_data = bool(d.get('ShowLevelData'))
        self.escape_aux = bool(d.get('EscapeAux'))
        Control.__init__(self, scene, go, d, menu)
        self.confirm_string = self.menu.loc(self.confirm_key)

    def late_update(self):
        Control.late_update(self)
        m = self.menu
        if self.main_menu is not None:
            if m.key_escape or (self.close_with_any_key and m.mouse_up):
                self.force_close()
        elif self.first_window:
            if m.key_escape and self.escape_aux:
                m.exit_message.hide_confirm()
                self.escape_aux = False
            elif m.key_escape and not self.escape_aux:
                m.exit_message.show_quit_game(self.confirm_string)
                self.escape_aux = True

    def draw_text(self, g, dt):
        pass

    def check_texture_index(self):
        pass

    def draw_texture(self, g):
        if self.textures or self.mobile_textures:
            arr = self.mobile_textures if self.use_mobile_textures \
                else self.textures
            if arr and arr[0]:
                g.tex(arr[0], self.rect)

    def force_close(self):
        """ForceClose (cs:78-87)"""
        if self.show_level_data:
            self.menu.show_level_data(True)
        self.scene.set_active(self.go, False)
        self.scene.set_active(self.main_menu, True)
        self.menu.tooltip_control = None


class ControlToggle(Control):
    """ControlToggle.cs: an int setting flipped by the click; the on state
    uses textures 3..5"""

    kind = 'ControlToggle'

    def is_mouse_over_control(self):
        mx, my = self.menu.mouse
        tr = self.text_mobile_rect if self.use_mobile_text else self.text_rect
        return point_in_rect(mx, my, self.rect) or point_in_rect(mx, my, tr)

    def do_work(self):
        self.menu.tooltip_control = self
        if self.setting_control and self.setting_type == 'Int':
            self.int_value = 1 - self.int_value
        self.update_texture_index_delta()
        Control.do_work(self)

    def load_value(self):
        Control.load_value(self)
        self.update_texture_index_delta()

    def update_texture_index_delta(self):
        self.texture_index_delta = 3 if (
            self.setting_control and self.setting_type == 'Int'
            and self.int_value == 1) else 0


class ControlSlider(Control):
    """ControlSlider.cs: the value is the pointer's x across the rect while
    the button is held; the fill is the texture's left `value` fraction"""

    kind = 'ControlSlider'

    def __init__(self, scene, go, d, menu):
        self.background = (d.get('Background') or {}).get('texture') \
            if isinstance(d.get('Background'), dict) else None
        self.calculated_rect = None
        self.uv_width = 1.0
        Control.__init__(self, scene, go, d, menu)

    def do_work(self):
        m = self.menu
        m.tooltip_control = self
        m.last_click = self.setting_key
        num = abs(m.mouse[0] - self.screen_rect[0])
        if self.setting_control:
            self.calculated_rect = self.screen_rect
            if self.setting_type == 'Int':
                self.int_value = int(num / self.screen_rect[2]) \
                    if self.screen_rect[2] else 0
                self.calculate_int_rect()
            elif self.setting_type == 'Float':
                self.float_value = num / self.screen_rect[2] \
                    if self.screen_rect[2] else 0.0
                self.calculate_float_rect()
        Control.do_work(self)

    def load_value(self):
        Control.load_value(self)
        if self.setting_type == 'Int':
            self.calculate_int_rect()
        elif self.setting_type == 'Float':
            self.calculate_float_rect()

    def calculate_float_rect(self):
        """CalculateFloatRect (ControlSlider.cs:64-70) with the fill
        clamped to the track: the serialized DefaultInt is 10 on a control
        whose DoWork writes [0,1] (cs:47-52), so an untouched first run
        computes a fill rect ten tracks wide, painted to the screen edge.
        The port clamps the DRAWN fill at 1 — a documented cosmetic
        departure; the stored value and the volume (already clamped by
        the settings) are untouched, and the first drag lands both worlds
        on the same [0,1]."""
        r = self.screen_mobile_rect
        self.uv_width = min(1.0, self.float_value)
        self.calculated_rect = (r[0], r[1], r[2] * self.uv_width, r[3])

    def calculate_int_rect(self):
        r = self.screen_mobile_rect
        self.uv_width = min(1.0, float(self.int_value))
        self.calculated_rect = (r[0], r[1], r[2] * self.uv_width, r[3])

    def draw_texture(self, g):
        if self.background:
            g.tex(self.background, self.screen_mobile_rect)
        tex = self._texture(self.texture_index)
        if tex and self.calculated_rect is not None:
            g.tex_uv(tex, self.calculated_rect, (0.0, 0.0,
                                                 max(0.0, min(1.0, self.uv_width)), 1.0))

    def late_update(self):
        """LateUpdate (cs:95-102): the held button drags"""
        if self.menu.mouse_down and self.is_mouse_over_control() \
                and not self.locked \
                and not self.menu.is_exit_confirmation_shown():
            self.do_work()


class ControlRadioButtonGroup(Control):
    """ControlRadioButtonGroup.cs"""

    kind = 'ControlRadioButtonGroup'

    def __init__(self, scene, go, d, menu):
        self.radio_refs = [(r or {}).get('path') for r in
                           (d.get('RadioButtons') or [])]
        Control.__init__(self, scene, go, d, menu)

    @property
    def radio_buttons(self):
        return [b for b in (self.menu.widget_by_go(p, ControlRadioButton)
                            for p in self.radio_refs) if b is not None]

    def load_textures(self):
        for b in self.radio_buttons:
            b.load_textures()

    def radio_button_pressed(self, pressed):
        for b in self.radio_buttons:
            if b is not pressed:
                b.unselect()

    def on_gui(self, g, dt):
        pass

    def late_update(self):
        pass


class ControlRadioButton(Control):
    """ControlRadioButton.cs: a level tile — its textures by the level's
    progress, the percentage, the lock, the selection and the double click"""

    kind = 'ControlRadioButton'
    CATCH_TIME = 0.25

    def __init__(self, scene, go, d, menu):
        self.group_ref = (d.get('Group') or {}).get('path')
        self.base_texture_path = d.get('BaseTexturePath') or ''
        self.base_texture_name = d.get('BaseTextureName') or ''
        self.normal_suffix = d.get('NormalSuffix') or ''
        self.passed_suffix = d.get('PassedSuffix') or ''
        self.perfect_suffix = d.get('PerfectSuffix') or ''
        self.hover_suffix = d.get('HoverSuffix') or ''
        self.pressed_suffix = d.get('PressedSuffix') or ''
        self.path_suffix = d.get('PathSuffix') or ''
        self.start_button_ref = (d.get('StartButton') or {}).get('path')
        self.level_to_start = d.get('LevelToStart') or ''
        self.level_index = int(d.get('LevelIndex') if d.get('LevelIndex')
                               is not None else -1)
        self.level_data_renderer_ref = (d.get('LevelDataRenderer') or {}).get('path')
        self.level_locked = False
        self.is_level_passed = False
        self.is_level_perfect = False
        self.on_vacation_season = bool(d.get('OnVacationSeason'))
        self.dont_show_percentages = bool(d.get('DontShowPercentagesNFH2'))
        self.is_level_selection = bool(d.get('IsLevelSelection'))
        self.last_click_time = -1e9
        self.hover_radio_aux = False
        self.locked_texture = None
        Control.__init__(self, scene, go, d, menu)
        self.text_font = int(font_size(self.W, self.H)) - 4  # Start (cs:38)
        self.on_enable()

    def on_enable(self):
        """OnEnable (cs:31-36)"""
        self.adjust_text_rect()
        self.load_textures()
        self.nfh1_show_level_percentages()

    def load_localization_data(self):
        """the label is the rating achieved (cs:54-57)"""
        self.text = '%d%%' % self.menu.progress.rating_achieved(self.level_index)
        self.tooltip = self.tooltip_mobile = self.text_mobile = ''

    def adjust_text_rect(self):
        r = self.screen_rect
        self.text_rect = (r[0] + r[2] * 0.095, r[1] + r[3] * 0.72, r[2], r[3])

    def load_textures(self):
        """LoadTextures (cs:67-88): the state suffix by the progress, the
        Resources paths resolved by the texture cache's name lookup"""
        self.is_level_passed, self.is_level_perfect = \
            self.menu.progress.is_passed(self.level_index)
        self.load_localization_data()
        self.locked_texture = 'Textures/Lock/nfh2_locked_level' \
            if self.on_vacation_season else 'Textures/Lock/nfh_locked_level'
        suf = self.perfect_suffix if self.is_level_perfect else (
            self.passed_suffix if self.is_level_passed else self.normal_suffix)
        base = self.base_texture_path + self.base_texture_name + suf
        self.textures = [base, base + self.hover_suffix,
                         base + self.pressed_suffix]
        self.mobile_textures = list(self.textures)
        self.path_texture = 'Textures/NFH2/MainMenu/Connectors/' + \
            self.path_suffix if self.path_suffix else None

    def draw_texture(self, g):
        Control.draw_texture(self, g)
        if self.locked_texture and self.level_locked and self.is_level_selection:
            g.tex(self.locked_texture, self.screen_rect)

    def check_texture_index(self):
        """CheckTextureIndex (cs:105-125): 1 hovered with the hover sound,
        0 otherwise, 2 stays selected; a press plays the click sound"""
        if self.texture_index != 2:
            if self.is_mouse_hovering():
                self.texture_index = 1
                if not self.hover_radio_aux:
                    self.menu.hover_sound()
                    self.hover_radio_aux = True
            else:
                self.hover_radio_aux = False
                self.texture_index = 0
        if self.menu.mouse_pressed and self.is_mouse_hovering():
            self.menu.click_sound()

    def draw_text(self, g, dt):
        if not self.dont_show_percentages:
            g.label(self.text_rect, self.text, self.text_style,
                    self.text_font)

    def force_do_work(self):
        self.do_work()

    def do_work(self):
        """DoWork (cs:136-165)"""
        Control.do_work(self)
        if self.is_level_selection and self.level_locked:
            return                        # PreComputePurchase: the store
        self.select()
        sb = self.menu.widget_by_go(self.start_button_ref, ControlButton)
        if sb is not None:
            sb.level_to_start = self.level_to_start
            if not self.on_vacation_season:
                self.menu.prefs.set_int('LastLoadedLevel', self.level_index)
            else:
                self.menu.prefs.set_int('LastLoadedLevel2',
                                        self.level_index - 18)
        if self.menu.mouse_up:
            now = self.menu.time
            if now - self.last_click_time < self.CATCH_TIME and sb is not None:
                sb.start_level()
            self.last_click_time = now

    def select(self):
        self.texture_index = 2
        grp = self.menu.widget_by_go(self.group_ref, ControlRadioButtonGroup)
        if grp is not None:
            grp.radio_button_pressed(self)
        ldr = self.menu.level_data_renderer(self.level_data_renderer_ref)
        if ldr is not None:
            ldr.load_level_data(self.level_index)

    def unselect(self):
        self.texture_index = 0

    def is_level_locked(self):
        return self.level_locked

    def set_locked(self, locked):
        self.level_locked = locked

    def nfh1_show_level_percentages(self):
        if not self.on_vacation_season:
            self.dont_show_percentages = bool(
                self.locked_texture and self.level_locked
                and self.is_level_selection)

    def late_update(self):
        Control.late_update(self)
        self.nfh1_show_level_percentages()


class LevelDataRenderer:
    """LevelDataGUIRenderer.cs: the selected level's page — title, hint,
    description, briefing, the duration / min rating / record / tricks,
    the level image — under the 1024x768 GUI.matrix at depth MainMenuFont"""

    def __init__(self, scene, go, d, menu):
        self.scene, self.go, self.d, self.menu = scene, go, d, menu
        self.W, self.H = menu.W, menu.H
        self.enabled = True                   # Behaviour.enabled
        self.menu_nfh2 = bool(d.get('MenuNFH2'))
        self.is_in_game_menu = bool(d.get('IsInGameMenu'))
        self.level_delta = int(d.get('LevelDelta') or 0)
        self.selected_level = -1
        self.sx, self.sy = self.W / DESIGN_W, self.H / DESIGN_H
        self.dont_draw_trick_texture = bool(d.get('DontDrawTrickTexture'))
        # Initialize (cs:84-144): the style sizes
        base = int(font_size(self.W, self.H))
        self.sizes = {}
        def size_of(style_key, default_px=None):
            st = d.get(style_key) or {}
            s = st.get('m_FontSize') or 0
            return s if s else (default_px or base)
        self.sizes = {k: size_of(k) for k in (
            'PageTitleStyle', 'RightPageTitleStyle', 'TitleStyle',
            'MainTitleStyle', 'HintStyle', 'DescriptionStyle',
            'BriefingStyle', 'HintTitleStyle', 'PlayEpisodeStyle',
            'TricksPlayedStyle', 'RatingStyle', 'RecordStyle',
            'MinRatingStyle', 'MinRatingTitleStyle', 'TotalTricksStyle',
            'NFH2TricksStyle', 'NoSneakStyle')}
        self.rects = {k: dict(d.get(k) or {}) for k in (
            'LeftPageTitleRect', 'RightPageTitleRect', 'TitleRect',
            'HintRect', 'DescriptionRect', 'BriefingRect', 'HintTitleRect',
            'LevelImageRect', 'ReturnToMenuRect', 'PlayEpisodeRect',
            'TricksPlayedTitleRect', 'TricksPlayedRect', 'StartTrickRect',
            'RatingTitleRect', 'RatingRect', 'RecordRect', 'MinRatingRect',
            'MinRatingTitleRect', 'DurationRect', 'DurationTitleRect',
            'TotalTricksPlayedRect', 'NFH2MinTricksRect',
            'NFH2TricksTotalRect', 'NoSneakRect')}
        if self.menu_nfh2:
            self.sizes['BriefingStyle'] = 18
            self.rects['BriefingRect']['height'] = 232.53
            self.rects['BriefingRect']['y'] = 336.4
            self.sizes['DescriptionStyle'] = 15
            self.rects['DescriptionRect']['width'] = 315.0
            self.sizes['NoSneakStyle'] = 16
        else:
            self.rects['HintRect'].update({'x': 751.1, 'y': 261.5,
                                           'width': 230.8, 'height': 112.8})
            self.sizes['BriefingStyle'] = 18
            self.sizes['DescriptionStyle'] = 15
            self.sizes['HintTitleStyle'] = 20
            self.sizes['MinRatingStyle'] = 21
        if not self.menu_nfh2:
            self.sizes['TotalTricksStyle'] = base
        else:
            self.sizes['TotalTricksStyle'] = base + 15
        self.episode_rects = [dict(r) for r in (d.get('EpisodeRects') or [])]
        loc = menu.loc
        self.left_page_title = loc(d.get('LeftPageTitle'))
        self.right_page_title = loc(d.get('RightPageTitle'))
        self.hint_title = loc(d.get('HintTitle'))
        self.return_to_menu = loc(d.get('ReturnToMenu'))
        self.play_episode = loc(d.get('PlayEpisode'))
        self.tricks_played_title = loc(d.get('TricksPlayedTitle'))
        self.rating_title = loc(d.get('RatingTitle'))
        self.record = loc(d.get('Record'))
        self.no_sneak_text = loc(d.get('NoSneakText'))
        self.min_rating_title = loc(d.get('MinRatingTitle'))
        self.duration_title = loc(d.get('DurationTitle'))
        self.episode_titles = [loc(t) for t in (d.get('EpisodeTitles') or [])]
        self.level_images = [(t or {}).get('texture') for t in
                             (d.get('LevelImages') or [])]
        self.trick_texture = (d.get('TrickTexture') or {}).get('texture')
        self.empty_trick_texture = (d.get('EmptyTrickTexture') or {}).get('texture')
        self.duration_fmt = d.get('Duration') or ''
        self.min_rating_fmt = d.get('MinRating') or ''
        self.rating_fmt = d.get('Rating') or ''
        self.tricks_played_fmt = d.get('TricksPlayed') or ''
        self.title = self.hint = self.description = self.briefing = ''
        self.duration_actual = self.min_rating_actual = ''
        self.rating_actual = self.tricks_played_actual = ''
        self.total_tricks_played = ''

    def _fmt(self, key, *args):
        """string.Format(LocalizationManager.GetString(key), args) — the
        {0}/{1} placeholders"""
        s = self.menu.loc(key)
        for i, a in enumerate(args):
            s = s.replace('{%d}' % i, str(a))
        return s

    def load_level_data(self, level_index):
        """LoadLevelData (cs:145-160)"""
        self.selected_level = level_index
        if level_index < 0:
            return
        loc, pr = self.menu.loc, self.menu.progress
        self.title = loc('L%dT' % level_index).replace('\\n', '\n')
        self.hint = loc('L%dH' % level_index)
        self.description = loc('L%dD' % level_index)
        self.briefing = loc('L%dB' % level_index).replace('\\n', '\n')
        dur = pr.duration(level_index)
        self.duration_actual = self._fmt(self.duration_fmt, dur // 60,
                                         '%02d' % (dur % 60))
        self.min_rating_actual = self._fmt(self.min_rating_fmt,
                                           pr.min_rating(level_index))
        self.rating_actual = self._fmt(self.rating_fmt,
                                       pr.rating_achieved(level_index))
        self.tricks_played_actual = self._fmt(self.tricks_played_fmt,
                                              pr.tricks_played(level_index),
                                              pr.tricks_total(level_index))
        self.total_tricks_played = str(self.calculate_tricks())

    def calculate_tricks(self):
        """CalculateTricks (cs:270-277): the Season-2 total over the tiles
        (the shipped `i - -18`)"""
        return sum(self.menu.progress.tricks_played(i + 18)
                   for i in range(len(self.level_images)))

    def get_level_image_index(self):
        if self.is_in_game_menu and self.menu_nfh2:
            return self.selected_level - 1
        return self.selected_level + self.level_delta

    def _r(self, key):
        return matrix_rect(self.rects.get(key), self.W, self.H)

    def _label(self, g, rect_key, text, style_key):
        g.label(self._r(rect_key), text, self.d.get(style_key) or {},
                self.sizes.get(style_key, 15) * self.sy, scale=(self.sx, self.sy))

    def draw(self, g):
        """DrawLevelData (cs:187-247)"""
        self._label(g, 'LeftPageTitleRect', self.left_page_title,
                    'PageTitleStyle')
        if self.selected_level < 0:
            return
        pr = self.menu.progress
        if not self.menu_nfh2:
            self._label(g, 'MinRatingRect', self.min_rating_actual, 'MinRatingStyle')
            self._label(g, 'MinRatingTitleRect', self.min_rating_title, 'MinRatingTitleStyle')
            self._label(g, 'DurationRect', self.duration_actual, 'MinRatingStyle')
            self._label(g, 'DurationTitleRect', self.duration_title, 'MinRatingTitleStyle')
            self._label(g, 'PlayEpisodeRect', self.play_episode, 'PlayEpisodeStyle')
            self._label(g, 'TricksPlayedTitleRect', self.tricks_played_title, 'PlayEpisodeStyle')
            self._label(g, 'RightPageTitleRect', self.right_page_title, 'RightPageTitleStyle')
            self._label(g, 'HintTitleRect', self.hint_title, 'HintTitleStyle')
            self._label(g, 'RecordRect', self.record, 'RecordStyle')
            self._label(g, 'RatingTitleRect', self.rating_title, 'PlayEpisodeStyle')
        else:
            self._label(g, 'RatingTitleRect', self.rating_title, 'RatingStyle')
            self._label(g, 'RecordRect', self.record, 'DescriptionStyle')
            self._label(g, 'TotalTricksPlayedRect', self.total_tricks_played, 'TotalTricksStyle')
            self._label(g, 'NFH2MinTricksRect', '%d%%' % pr.min_rating(self.selected_level), 'NFH2TricksStyle')
            self._label(g, 'NFH2TricksTotalRect', str(pr.tricks_total(self.selected_level)), 'NFH2TricksStyle')
            self._label(g, 'NoSneakRect', self.no_sneak_text, 'NoSneakStyle')
        self._label(g, 'RatingRect', self.rating_actual, 'TricksPlayedStyle')
        self._label(g, 'TricksPlayedRect', self.tricks_played_actual, 'TricksPlayedStyle')
        self._label(g, 'TitleRect', self.title, 'MainTitleStyle')
        self._label(g, 'HintRect', self.hint, 'HintStyle')
        self._label(g, 'DescriptionRect', self.description, 'DescriptionStyle')
        self._label(g, 'ReturnToMenuRect', self.return_to_menu, 'TitleStyle')
        self._label(g, 'BriefingRect', self.briefing, 'BriefingStyle')
        start = self.rects.get('StartTrickRect') or {}
        x, y = start.get('x', 0.0), start.get('y', 0.0)
        w, h = start.get('width', 0.0), start.get('height', 0.0)
        for i in range(pr.tricks_total(self.selected_level)):
            g.tex(self.empty_trick_texture,
                  matrix_rect({'x': x + w * 1.5 * i, 'y': y, 'width': w,
                               'height': h}, self.W, self.H))
        if not self.dont_draw_trick_texture:
            for j in range(pr.tricks_played(self.selected_level)):
                g.tex(self.trick_texture,
                      matrix_rect({'x': x + w * 1.5 * j, 'y': y, 'width': w,
                                   'height': h}, self.W, self.H))
        idx = self.get_level_image_index()
        if 0 <= idx < len(self.level_images):
            g.tex(self.level_images[idx], self._r('LevelImageRect'))
        if not self.menu_nfh2:
            for k, er in enumerate(self.episode_rects):
                if k < len(self.episode_titles):
                    g.label(matrix_rect(er, self.W, self.H),
                            self.episode_titles[k],
                            self.d.get('TitleStyle') or {},
                            self.sizes.get('TitleStyle', 15) * self.sy,
                            scale=(self.sx, self.sy))


class DirectorAnimation:
    """DirectorAnimation.cs: the director's face strip on the confirmation
    dialog (DrawFacesExit: a ping-pong at DirectorFaceInterval)"""

    def __init__(self, d, W, H):
        self.faces = [(t or {}).get('texture') for t in (d.get('DirectorFaces') or [])]
        self.rect = adjust_rect(d.get('DirectorRect'), W, H)
        self.interval = float(d.get('DirectorFaceInterval') or 0.25)
        self.index = 0
        self.increment = 1
        self.start_time = 0.0
        self.clock = 0.0                  # Time.realtimeSinceStartup

    def restart(self):
        self.index = 1
        self.increment = 1
        self.start_time = self.clock

    def tick(self, dt):
        self.clock += dt

    def draw_faces_exit(self, g):
        if self.clock - self.start_time > self.interval:
            self.start_time = self.clock
            self.index += self.increment
            if self.index == len(self.faces) - 1 or self.index == 0:
                self.increment = -self.increment
        if self.faces:
            i = max(0, min(len(self.faces) - 1, self.index))
            g.tex(self.faces[i], self.rect)


class ExitConfirmation:
    """ExitConfirmation.cs: the yes/no dialog with the director's faces —
    a ControlButton's confirmation, a window's quit question, the exit
    door's message in a level"""

    def __init__(self, d, director, menu, font_adjust):
        self.menu = menu
        self.W, self.H = menu.W, menu.H
        self.d = d
        self.director = director
        self.exit_confirm_rect = adjust_rect(d.get('ExitConfirmRect'), self.W, self.H)
        self.exit_confirm = (d.get('ExitConfirm') or {}).get('texture')
        self.exit_confirm_ok_only = (d.get('ExitConfirmOkOnly') or {}).get('texture')
        self.message_rect = adjust_rect(d.get('ExitConfirmMessageRect'), self.W, self.H)
        self.exit_style = d.get('ExitStyle') or {}
        self.no_rect = adjust_rect(d.get('ExitNoButtonRect'), self.W, self.H)
        self.no_hover = (d.get('ExitNoButtonHover') or {}).get('texture')
        self.no_tex = (d.get('ExitNoButton') or {}).get('texture')
        self.yes_rect = adjust_rect(d.get('ExitYesButtonRect'), self.W, self.H)
        self.yes_hover = (d.get('ExitYesHover') or {}).get('texture')
        self.yes_tex = (d.get('ExitYes') or {}).get('texture')
        # Start (cs:33-42): the style size from the window's/renderer's
        # CalculateFontSize - 3
        self.font = int(font_size(self.W, self.H)) - 3
        self.should_show = False
        self.message = ''
        self.dismissed = None
        self.ok_button_only = False
        self.draw_quit = False
        self.alternate_style = None
        self.alternate_rect = None
        self.close_time = 0.0
        self.enabled = False

    def update(self):
        """Update (cs:43-95): the release over No / Yes, the Esc"""
        if not self.enabled:
            return
        m = self.menu
        mx, my = m.mouse
        if m.mouse_up:
            m.clear_input()
            if point_in_rect(mx, my, self.no_rect):
                if self.dismissed is not None:
                    self.dismissed(False)
                m.escape_aux_clear()
                self.hide()
            elif point_in_rect(mx, my, self.yes_rect) and not self.ok_button_only:
                if self.dismissed is not None:
                    self.dismissed(True)
                if not self.draw_quit:
                    m.escape_aux_clear()
                    self.hide()
        if m.key_escape:
            if self.dismissed is not None:
                self.dismissed(False)
            m.escape_aux_set()
            self.hide()

    def draw(self, g):
        """DrawExitConfirmation (cs:107-158)"""
        if not self.should_show:
            return
        g.tex(self.exit_confirm_ok_only if self.ok_button_only
              else self.exit_confirm, self.exit_confirm_rect)
        if self.director is not None:
            self.director.draw_faces_exit(g)
        if self.alternate_style is None:
            g.label(self.message_rect, self.message, self.exit_style, self.font)
        else:
            g.label(self.alternate_rect, self.message, self.alternate_style,
                    self.font)
        mx, my = self.menu.mouse
        if not self.ok_button_only:
            g.tex(self.no_hover if point_in_rect(mx, my, self.no_rect)
                  else self.no_tex, self.no_rect)
            g.tex(self.yes_hover if point_in_rect(mx, my, self.yes_rect)
                  else self.yes_tex, self.yes_rect)
        else:
            g.tex(self.yes_hover if point_in_rect(mx, my, self.no_rect)
                  else self.yes_tex, self.no_rect)

    def show_quit_game(self, message):
        """ShowQuitGameConfirmation (cs:159-169)"""
        self.draw_quit = True
        self.ok_button_only = False
        self.enabled = True
        self.message = message
        self.should_show = True
        self.dismissed = self._quit_game
        self.menu.time_scale = 0.0
        if self.director is not None:
            self.director.restart()
        self.alternate_style = None

    def _quit_game(self, should_quit):
        if should_quit:
            self.menu.quit()
        return False

    def show(self, message, dismissed, ok_button_only=False):
        """ShowExitConfirmation (cs:170-180)"""
        self.ok_button_only = ok_button_only
        self.enabled = True
        self.message = message
        self.should_show = True
        self.dismissed = dismissed
        self.menu.time_scale = 0.0
        if self.director is not None:
            self.director.restart()
        self.alternate_style = None

    def show_styled(self, style, rect, message, dismissed,
                    ok_button_only=False):
        self.show(message, dismissed, ok_button_only)
        self.alternate_style = style
        self.alternate_rect = rect

    def hide(self):
        """HideExitConfirmation (cs:187-205)"""
        self.draw_quit = False
        self.enabled = False
        self.should_show = False
        self.menu.time_scale = 0.0 if self.menu.has_any_menu_open() else 1.0
        self.close_time = self.menu.time
        self.menu.on_confirmation_hidden()

    def hide_confirm(self):
        if self.dismissed is not None:
            self.dismissed(False)
        self.hide()


class GameIntroAnimation:
    """GameIntroAnimation.cs: the app splash — the publisher logos, the
    game logo, "click to start"; any click or Esc enters the menu; it runs
    once per process (the static Finished)"""

    finished = False                      # static Finished

    def __init__(self, d, menu):
        self.menu = menu
        self.W, self.H = menu.W, menu.H
        self.d = d
        self.state = 'None'
        self.timer = 0.0
        self.background = (d.get('Background') or {}).get('texture')
        self.background_rect = adjust_rect(d.get('BackgroundRect'), self.W, self.H)
        self.company_logo = (d.get('CompanyLogo') or {}).get('texture')
        self.company_rect = matrix_rect(d.get('CompanyRect'), self.W, self.H)
        self.company_logo2 = (d.get('CompanyLogo2') or {}).get('texture')
        self.company_rect2 = matrix_rect(d.get('CompanyRect2'), self.W, self.H)
        self.company_message_rect = matrix_rect(d.get('CompanyMessageRect'), self.W, self.H)
        self.game_logo = (d.get('GameLogo') or {}).get('texture')
        self.game_rect = adjust_rect(d.get('GameRect'), self.W, self.H)
        self.game_message_rect = matrix_rect(d.get('GameMessageRect'), self.W, self.H)
        self.start_rect = matrix_rect(d.get('StartRect'), self.W, self.H)
        self.message_style = d.get('MessageStyle') or {}
        self.start_style = d.get('StartStyle') or {}
        loc = menu.loc
        self.start_message = loc(d.get('StartMessage'))
        self.mobile_start_message = loc(d.get('MobileStartMessage'))
        self.company_message = loc(d.get('CompanyMessage'))
        self.game_message = loc(d.get('GameMessage'))
        self.company_time = float(d.get('CompanyTime') or 1.0)
        self.company2_time = float(d.get('Company2Time') or 2.0)
        self.game_time = float(d.get('GameTime') or 1.0)
        self.enabled = True
        self.sx, self.sy = self.W / DESIGN_W, self.H / DESIGN_H
        # the sizes the styles serialize (their fontSize is not recomputed)
        self.message_size = (self.message_style.get('m_FontSize') or 16) * self.sy
        self.start_size = (self.start_style.get('m_FontSize') or 16) * self.sy
        if GameIntroAnimation.finished:
            self.enter_game()
        else:
            self.state = 'Company'            # DoIntroLogic's first step
            self.timer = self.company_time

    def tick(self, dt):
        """DoIntroLogic (cs:129-137) + Update (cs:89-96)"""
        if not self.enabled:
            return
        m = self.menu
        if (m.key_escape or m.mouse_up or m.mouse_up_right) \
                and not GameIntroAnimation.finished:
            GameIntroAnimation.finished = True
            self.enter_game()
            return
        if self.state in ('Company', 'Company2', 'Game'):
            self.timer -= dt
            if self.timer <= 0.0:
                if self.state == 'Company':
                    self.state, self.timer = 'Company2', self.company2_time
                elif self.state == 'Company2':
                    self.state, self.timer = 'Game', self.game_time
                else:
                    self.state = 'Start'

    def enter_game(self):
        """EnterGame (cs:97-103)"""
        self.menu.clear_input()
        self.state = 'None'
        self.enabled = False

    def draw(self, g):
        """OnGUI (cs:52-79)"""
        if not self.enabled or self.state == 'None':
            return
        g.tex(self.background, self.background_rect)
        sc = (self.sx, self.sy)
        if self.state == 'Company':
            g.tex(self.company_logo, self.company_rect)
            g.label(self.company_message_rect, self.company_message,
                    self.message_style, self.message_size, scale=sc)
        elif self.state == 'Company2':
            g.tex(self.company_logo2, self.company_rect2)
            g.label(self.company_message_rect, self.company_message,
                    self.message_style, self.message_size, scale=sc)
        elif self.state in ('Game', 'Start'):
            g.tex(self.game_logo, self.game_rect)
            g.label(self.game_message_rect, self.game_message,
                    self.message_style, self.message_size, scale=sc)
            if self.state == 'Start':
                g.label(self.start_rect, self.mobile_start_message,
                        self.start_style, self.start_size, scale=sc)


class Credits:
    """Credits.cs: the scrolling credits — names from the NamesFile XML,
    the entries (images and strings with a style name) from EntriesFile,
    SpeedFactor px/s upward after a 1.5 s pause, the window closes 1.5 s
    after the last entry leaves the top"""

    def __init__(self, d, menu, window_go):
        import xml.etree.ElementTree as ET
        self.menu = menu
        self.W, self.H = menu.W, menu.H
        self.window_go = window_go
        self.speed = float(d.get('SpeedFactor') or -100.0)
        self.middle = (d.get('MiddlePart') or {}).get('texture')
        self.middle_rect = adjust_rect(d.get('MiddleRect'), self.W, self.H)
        self.top = (d.get('TopPart') or {}).get('texture')
        self.top_rect = adjust_rect(d.get('TopRect'), self.W, self.H)
        self.bottom = (d.get('BottomPart') or {}).get('texture')
        self.bottom_rect = adjust_rect(d.get('BottomRect'), self.W, self.H)
        self.styles = {(s or {}).get('m_Name'): s for s in (d.get('Styles') or [])}
        self.entries = []                 # [type, text/texture, style, rect]
        self.original_y = []
        self.data_loaded = False
        self.start_moving = False
        self.start_exiting = False
        self.exit_timer = 0.0
        self.pause_timer = 1.5
        names_xml = (d.get('NamesFile') or {}).get('text') or ''
        entries_xml = (d.get('EntriesFile') or {}).get('text') or ''
        self._ET = ET
        self.names_xml, self.entries_xml = names_xml, entries_xml
        self.font = int(font_size(self.W, self.H))
        self.on_enable()

    def on_enable(self):
        """OnEnable (cs:111-124)"""
        self.pause_timer = 1.5
        self.start_moving = False
        self.start_exiting = False
        self.exit_timer = 0.0
        if not self.data_loaded:
            self.load_data()
        else:
            for i, e in enumerate(self.entries):
                e[3][1] = self.original_y[i]

    def load_data(self):
        """LoadData / LoadNames / LoadEntries (cs:137-208)"""
        ET = self._ET
        names = {}
        try:
            for el in ET.fromstring(self.names_xml).iter('string'):
                names[el.get('name')] = el.get('text') or ''
        except Exception:
            pass
        base_x = self.W * 0.3
        last_y = 0.0
        self.entries = []
        self.original_y = []
        try:
            root = ET.fromstring(self.entries_xml)
            items = list(root.iter())
        except Exception:
            items = []
        lines_cont = len(items)
        padding = self.H
        for el in items:
            lines_cont -= 1
            if el.tag not in ('image', 'string'):
                continue
            st = dict(self.styles.get(el.get('format')) or {})
            mt = st.get('m_Margin.top', 0) or 0
            last_y += mt * (self.H / 600.0)
            if el.tag == 'image':
                st['m_Padding.top'] = 0
            else:
                st['m_Padding.top'] = padding
                st['m_Margin.bottom'] = 50
            if (st.get('m_Padding.top') or 0) > 0:
                st['m_Padding.top'] = int((st.get('m_Padding.top') or 0) * 0.8)
            ml = st.get('m_Margin.left', 0) or 0
            if el.tag == 'image':
                tex = 'textures/' + (el.get('file') or '')
                tw, th = self.menu.texture_size(tex)
                rect = [base_x + ml * self.W / 800.0, self.H * 0.25,
                        tw * (self.W / 800.0), th * self.H / 600.0]
                self.entries.append(['image', tex, st, rect])
            else:
                if lines_cont == 1:
                    st['m_Margin.bottom'] = 420
                text = names.get(el.get('text') or '', '')
                rect = [base_x + ml * self.W / 800.0, last_y,
                        200.0 * (self.W / 800.0), 50.0 * (self.H / 600.0)]
                self.entries.append(['string', text, st, rect])
            self.original_y.append(self.entries[-1][3][1])
            last_y += (st.get('m_Margin.bottom', 0) or 0) * (self.H / 600.0)
        self.data_loaded = True

    def tick(self, dt):
        """Update (cs:96-110) + OnGUI's per-frame scroll (cs:118-127:
        the original mutates the rects inside the draw; the port moves
        them here so a headless frame advances the same way)"""
        if not self.start_moving:
            self.pause_timer -= dt
            if self.pause_timer <= 0.0:
                self.start_moving = True
        elif self.data_loaded:
            for e in self.entries:
                e[3][1] += self.speed * dt
            if self.entries and self.entries[-1][3][1] < 0.0 \
                    and not self.start_exiting:
                self.start_exiting = True
                self.exit_timer = 1.5
        if self.start_exiting:
            self.exit_timer -= dt
            if self.exit_timer <= 0.0:
                self.start_exiting = False
                self.exit_timer = 0.0
                w = self.menu.widget_by_go(self.window_go, ControlWindow)
                if w is not None:
                    w.force_close()

    def draw(self, g, dt):
        """OnGUI (cs:60-95)"""
        if self.data_loaded:
            g.tex(self.middle, self.middle_rect)
            for typ, payload, st, rect in self.entries:
                if typ == 'image':
                    g.tex(payload, tuple(rect))
                else:
                    g.label(tuple(rect), payload, st, self.font)
        g.tex(self.top, self.top_rect)
        g.tex(self.bottom, self.bottom_rect)


class LanguageComboBox:
    """LanguageComboBox.cs: the flag at the top right; clicking it drops
    the flag list (sliding in over 20 frames), a flag sets the language"""

    def __init__(self, d, menu):
        self.menu = menu
        self.W, self.H = menu.W, menu.H
        self.selected = [(t or {}).get('texture') for t in (d.get('SelectedFlag') or [])]
        self.unselected = [(t or {}).get('texture') for t in (d.get('UnselectedFlag') or [])]
        self.types = d.get('LanguageFlagType') or []
        self.scale = float(d.get('Flag_Scale') or 0.5)
        self.dropped = False
        self.counter = 0.0
        cur = LANGUAGES[menu.settings.language] \
            if 0 <= menu.settings.language < len(LANGUAGES) else 'Lang'
        self.current = self.types.index(cur) if cur in self.types else 0

    def on_disable(self):
        self.dropped = False
        self.counter = 0.0

    def _layout(self):
        """OnGUI's GUI.matrix: a 648-high design space scaled by H/648
        when the screen is at least 800 wide (cs:66-78)"""
        if self.W >= 800:
            s = self.H / 648.0
            num = self.W / self.H * 648.0
            return s, s, num
        return self.W / 760.0, self.H / 700.0, 760.0

    def _flag_size(self, name):
        tw, th = self.menu.texture_size(name)
        return tw * self.scale, th * self.scale

    def update_and_draw(self, g):
        """OnGUI (cs:62-100): GUI.Button returns true on the release
        inside the rect"""
        if not self.selected:
            return
        sx, sy, num = self._layout()
        cw, ch = self._flag_size(self.selected[self.current])
        head = (num * 0.9 * sx, 0.0, cw * sx, ch * sy)
        mx, my = self.menu.mouse
        click = self.menu.mouse_up and not self.menu.confirm_opened
        if self.dropped:
            g.tex(self.selected[self.current], head)
            if click and point_in_rect(mx, my, head):
                self.dropped = False
                self.counter = 0.0
                self.menu.clear_input()
                return
            for i, tex in enumerate(self.unselected):
                fw, fh = self._flag_size(tex)
                y = (fh * (i + 1) + i + 0.5) * (self.counter / 10.0)
                r = (num * 0.9 * sx, y * sy, fw * sx, fh * sy)
                g.tex(tex, r)
                if click and point_in_rect(mx, my, r) and self.counter == 10.0:
                    self.dropped = False
                    self.counter = 0.0
                    self.on_flag_selected(i)
                    self.menu.clear_input()
                    return
            if self.counter < 10.0:
                self.counter += 0.5
        else:
            g.tex(self.selected[self.current], head)
            if click and point_in_rect(mx, my, head):
                self.dropped = True
                self.menu.clear_input()

    def on_flag_selected(self, i):
        self.current = i
        lang = self.types[i] if i < len(self.types) else 'Lang'
        idx = LANGUAGES.index(lang) if lang in LANGUAGES else 0
        self.menu.set_current_language(idx, reload=True, selected_by_player=True)


# ---------------------------------------------------------------------------
# the menu scene

class Menu:
    """The Entry scene: the widget set over the GameObject tree, the splash,
    the language flag, the credits, the confirmation dialog, the menu music,
    and the flow out — load_level(name) hands over to the application."""

    WIDGET_CLASSES = {'ControlButton': ControlButton,
                      'ControlWindow': ControlWindow,
                      'ControlToggle': ControlToggle,
                      'ControlSlider': ControlSlider,
                      'ControlRadioButton': ControlRadioButton,
                      'ControlRadioButtonGroup': ControlRadioButtonGroup,
                      'ControlButtonRestore': ControlButton,
                      'ControlLabel': Control}

    def __init__(self, path, W, H, prefs, sounds=None, texture_size=None,
                 app=None):
        self.W, self.H = W, H
        self.prefs = prefs
        self.app = app
        self.sounds = sounds
        self._texture_size = texture_size or (lambda n: (0, 0))
        self.scene = SceneData(path)
        self.season = self.scene.season
        from base import asset_root
        root = asset_root()
        self.root = root
        self.settings = Settings(prefs)
        self.progress = Progress(prefs)
        self.strings = load_strings(root, self.season, self.settings.language)
        self.selected_lang = self.settings.language    # Control.SelectedLang
        self.current_scene_name = 'Entry'
        # input, per frame
        self.mouse = (W / 2.0, H / 2.0)
        self.mouse_down = False
        self.mouse_pressed = False        # the down edge
        self.mouse_up = False             # the up edge
        self.mouse_up_right = False
        self.key_escape = False
        self.time = 0.0
        self.time_scale = 1.0
        self.is_loading_level = False
        self.confirm_opened = False       # Control.ConfirmOpened
        self.tooltip_control = None
        self.last_click = None            # Control.LastClick
        self.open_level_selection = False # Level.OpenLevelSelection
        self.menu_loader = 0              # Level.MenuLoader
        self.pending_load = None
        self.quit_requested = False
        self.reload_requested = False
        # the Level component of the Entry scene: the menu objects and the
        # level data tables (Level.cs: MainMenu, LevelSelectionMenu(2),
        # Durations/TricksTotal/MinRatings)
        lv = self.scene.find('Level')
        self.level_d = lv[0][1] if lv else {}
        self.main_menu_go = (self.level_d.get('MainMenu') or {}).get('path')
        self.level_selection_go = (self.level_d.get('LevelSelectionMenu') or {}).get('path')
        self.level_selection2_go = (self.level_d.get('LevelSelectionMenu2') or {}).get('path')
        self.progress.initialize(self.level_d.get('Durations') or [],
                                 self.level_d.get('TricksTotal') or [],
                                 self.level_d.get('MinRatings') or [])
        # the widgets
        self.widgets = []
        self._by_go = {}
        for typ, cls in self.WIDGET_CLASSES.items():
            for go, d in self.scene.find(typ):
                w = cls(self.scene, go, d, self)
                self.widgets.append(w)
                self._by_go.setdefault(go, []).append(w)
        # the level tiles' unlock state: LevelUnlocker locks the packs the
        # store has not sold (LevelUnlocker.cs:82-93); there is no store
        # here, so every pack is unlocked (Purchaser.TestMode's arm)
        for w in self.widgets:
            if isinstance(w, ControlRadioButton):
                w.set_locked(False)
        # the data renderers, keyed by GO
        self.renderers = {}
        for go, d in self.scene.find('LevelDataGUIRenderer'):
            self.renderers[go] = LevelDataRenderer(self.scene, go, d, self)
        # the splash, the flag, the credits, the dialog
        gi = self.scene.find('GameIntroAnimation')
        self.intro = GameIntroAnimation(gi[0][1], self) if gi else None
        lc = self.scene.find('LanguageComboBox')
        self.combo = LanguageComboBox(lc[0][1], self) if lc else None
        self.combo_go = lc[0][0] if lc else None
        cr = self.scene.find('Credits')
        self.credits = None
        self.credits_go = None
        if cr:
            go = cr[0][0]
            win = next((w for w in self._by_go.get(go, [])
                        if isinstance(w, ControlWindow)), None)
            self.credits_go = go
            self.credits = Credits(cr[0][1], self, go if win else None)
            self._credits_was_active = False
        ec = self.scene.find('ExitConfirmation')
        ec_go = ec[0][0] if ec else None
        # the tutorial scenes carry a second DirectorAnimation on the
        # LevelScript object (its own message faces); the dialog's is the
        # one sharing the ExitConfirmation's GameObject (Start's
        # GetComponentInChildren from that object, ExitConfirmation.cs:63)
        drs = self.scene.find('DirectorAnimation')
        dr = next((d for go, d in drs if go == ec_go),
                  drs[0][1] if drs else None)
        director = DirectorAnimation(dr, W, H) if dr else None
        self.exit_message = ExitConfirmation(ec[0][1] if ec else {},
                                             director, self, 0)
        # the menu cursor (MenuMouseController: the PC build's cursor
        # texture at the pointer)
        mm = self.scene.find('MenuMouseController')
        self.cursor_tex = (mm[0][1].get('DefaultCursor') or {}).get('texture') if mm else None
        self.cursor_rect = adjust_rect(mm[0][1].get('cursorSize'), W, H) if mm else (0, 0, 16, 16)
        self.cursor_delta = (mm[0][1].get('TextureDeltaLoc') or {}) if mm else {}
        # MusicPlayer: the menu track and the hover/click sounds
        mp = self.scene.find('MusicPlayer')
        self.music = mp[0][1] if mp else {}
        self._music_started = False
        # the radio initializers (OnEnable: the last loaded level's tile)
        self._radio_init = [(go, d) for go, d in
                            self.scene.find('ControlRadioButtonInitializer')]
        self._radio_init_done = set()
        self._lang_init = [go for go, d in self.scene.find('MenuLangInitializer')]

    # -- services the widgets use ------------------------------------------
    def loc(self, key):
        """LocalizationManager.GetString: empty when unknown"""
        if not key:
            return ''
        return self.strings.get(key, '')

    def widget_by_go(self, ref, cls=None):
        """a serialized reference (a component or GameObject path) -> the
        widget of that class on the owning GameObject"""
        go = self.scene.go_of(ref)
        for w in self._by_go.get(go, ()):
            if cls is None or isinstance(w, cls):
                return w
        return None

    def level_data_renderer(self, ref):
        return self.renderers.get(self.scene.go_of(ref))

    def texture_size(self, name):
        return self._texture_size(name)

    def is_exit_confirmation_shown(self):
        return self.exit_message.should_show

    def has_any_menu_open(self):
        return False

    def escape_aux_clear(self):
        for w in self.widgets:
            if isinstance(w, ControlWindow):
                w.escape_aux = False

    def escape_aux_set(self):
        for w in self.widgets:
            if isinstance(w, ControlWindow) and w.first_window:
                w.escape_aux = True

    def on_confirmation_hidden(self):
        self.confirm_opened = False

    def clear_input(self):
        """InputManager.ClearInput: the frame's edges are consumed"""
        self.mouse_up = False
        self.mouse_pressed = False
        self.mouse_up_right = False
        self.key_escape = False

    def _source_clip(self, field):
        """a MusicPlayer AudioSource field (ClickSound / HoverSound,
        MusicPlayer.cs:31-35) -> the clip name on that AudioSource"""
        ref = self.music.get(field)
        pid = ref.get('path') if isinstance(ref, dict) else None
        o = self.scene.objs.get(str(pid)) if pid else None
        clip = ((o or {}).get('data') or {}).get('clip')
        return clip.get('clip') if isinstance(clip, dict) else None

    def click_sound(self):
        """Control.CheckTextureIndex's press (Control.cs:196-207): the
        MusicPlayer.ClickSound source, gated on Level.AudioEnabled"""
        if self.settings.audio_enabled and self.sounds is not None \
                and (self.intro is None or not self.intro.enabled):
            clip = self._source_clip('ClickSound')
            if clip:
                self.sounds.play(clip)

    def hover_sound(self):
        """ControlRadioButton.CheckTextureIndex's hover (cs:110-116)"""
        if self.settings.audio_enabled and self.sounds is not None:
            clip = self._source_clip('HoverSound')
            if clip:
                self.sounds.play(clip)

    def load_settings(self):
        """Level.LoadSettings (cs:295-310): re-read and apply"""
        self.settings.load()
        self.selected_lang = self.settings.language
        self.apply_audio()

    def apply_audio(self):
        """PlayLevelMusic / StopAllSounds by the settings (cs:300-309)"""
        if self.sounds is None:
            return
        s = self.settings
        tracks = self.music.get('LevelSounds') or []
        clip = (tracks[1] or {}).get('clip') if len(tracks) > 1 and isinstance(tracks[1], dict) else None
        src = self.music.get('LevelMusicSource')
        pid = src.get('path') if isinstance(src, dict) else None
        so = self.scene.objs.get(str(pid)) if pid else None
        loop = bool(((so or {}).get('data') or {}).get('loop', True))
        if s.audio_enabled and s.music_enabled and clip:
            if not self._music_started:
                self.sounds.play_music(clip, loop=loop)
                self._music_started = True
            self.sounds.set_music_volume(s.music_volume)
        else:
            self.sounds.stop_music()
            self._music_started = False
        self.sounds.set_sound_volume(s.sound_volume)

    def set_current_language(self, lang, reload=True, selected_by_player=False):
        """LocalizationManager.SetCurrentLanguage (cs:189-206): the pref,
        Level.GameLanguage, and a blocking reload of the Entry scene"""
        if selected_by_player:
            self.prefs.set_int('HasCustomLanguage', 1)
            self.prefs.save()
        if self.settings.language != lang:
            self.prefs.set_int('Language', lang)
            self.prefs.save()
            self.settings.language = lang
            if reload:
                self.reload_requested = True

    def show_level_data(self, show):
        """InGameMenu.ShowLevelData — the in-game menu's renderer; the Entry
        scene has no InGameMenu, so nothing here"""
        for r in self.renderers.values():
            if r.is_in_game_menu:
                r.enabled = show

    def disable_in_game_menu(self):
        pass

    def quit(self):
        self.quit_requested = True

    def load_level(self, name):
        """LevelLoader.LoadLevel (LevelLoader.cs:64-104) — hands the scene
        name to the application; the loading screen is its"""
        self.is_loading_level = True
        self.pending_load = name

    # -- the frame ---------------------------------------------------------
    def feed_input(self, mouse, mouse_down, pressed, up, up_right, escape):
        self.mouse = mouse
        self.mouse_down = mouse_down
        self.mouse_pressed = pressed
        self.mouse_up = up
        self.mouse_up_right = up_right
        self.key_escape = escape

    def _radio_initializers(self):
        """ControlRadioButtonInitializer.OnEnable (cs:9-42): the moment its
        level window turns active, the last loaded level's tile is selected
        (a locked or out-of-range one falls back to the first)"""
        for go, d in self._radio_init:
            active = self.scene.active_in_hierarchy(go)
            if not active:
                self._radio_init_done.discard(go)
                continue
            if go in self._radio_init_done:
                continue
            self._radio_init_done.add(go)
            grp = None
            for child in [go] + self._descendants(go):
                grp = self.widget_by_go(child, ControlRadioButtonGroup)
                if grp is not None:
                    break
            if grp is None:
                continue
            if not d.get('OnVacationSeason'):
                num = self.prefs.get_int('LastLoadedLevel', 0)
                if num < 0 or num > 16:
                    num = 0
            else:
                num = self.prefs.get_int('LastLoadedLevel2', 0)
                if num < 0 or num > 13:
                    num = 0
            buttons = grp.radio_buttons
            if len(buttons) > num:
                if buttons[num].is_level_locked():
                    num = 0
                buttons[num].force_do_work()
            for i, b in enumerate(buttons):
                if i != num:
                    b.unselect()

    def _descendants(self, go):
        out = []
        stack = list(self.scene.children.get(go, ()))
        while stack:
            c = stack.pop()
            out.append(c)
            stack.extend(self.scene.children.get(c, ()))
        return out

    def _lang_initializers(self):
        """MenuLangInitializer.OnEnable (cs:9-20): the language buttons
        under it show the current language selected"""
        for go in self._lang_init:
            if not self.scene.active_in_hierarchy(go):
                continue
            for child in [go] + self._descendants(go):
                for w in self._by_go.get(child, ()):
                    if isinstance(w, ControlButton) and w.is_language:
                        idx = LANGUAGES.index(w.language_type) \
                            if w.language_type in LANGUAGES else 0
                        w.set_button_selected(idx == self.settings.language)

    def _open_level_selection(self):
        """Level.Update's OpenLevelSelection arm (Level.cs:350-363)"""
        if self.open_level_selection and self.main_menu_go is not None \
                and self.level_selection_go is not None \
                and self.level_selection2_go is not None:
            self.open_level_selection = False
            self.scene.set_active(self.main_menu_go, False)
            if self.menu_loader == 1:
                self.scene.set_active(self.level_selection_go, True)
            elif self.menu_loader == 2:
                self.scene.set_active(self.level_selection2_go, True)
            self.menu_loader = 0

    def tick(self, dt):
        """one frame: the intro, the initializers, the widgets' LateUpdate,
        the dialog"""
        self.time += dt
        if not self._music_started:
            self.apply_audio()
        if self.intro is not None and self.intro.enabled:
            self.intro.tick(dt)
        self._open_level_selection()
        self._radio_initializers()
        self._lang_initializers()
        if self.exit_message.director is not None:
            self.exit_message.director.tick(dt)
        # ExitConfirmation.Update runs before the controls' LateUpdate
        self.exit_message.update()
        if self.credits is not None and self.credits_go is not None:
            active = self.scene.active_in_hierarchy(self.credits_go)
            if active and not self._credits_was_active:
                self.credits.on_enable()
            self._credits_was_active = active
            if active:
                self.credits.tick(dt)
        if self.combo is not None and self.combo_go is not None \
                and not self.scene.active_in_hierarchy(self.combo_go):
            self.combo.on_disable()
        # the live set is captured before the pass: a widget whose window a
        # click just activated does not see the same click (Unity schedules
        # a freshly activated behaviour's LateUpdate for the next frame —
        # OnHouseButtonStart shares MenuButtonStart's exact rect and would
        # otherwise fire through), and one deactivated mid-pass stops
        # (a disabled behaviour receives no further callbacks)
        if not (self.intro is not None and self.intro.enabled):
            live = [w for w in self.widgets if w.active]
            for w in live:
                if w.active:
                    w.late_update()

    def draw(self, g, dt):
        """the OnGUI pass in GUIDepth order: far depths first"""
        items = []
        for w in self.widgets:
            if w.active:
                items.append((w.depth, 0, w))
        for go, r in self.renderers.items():
            if r.enabled and self.scene.active_in_hierarchy(go):
                items.append((GUI_DEPTH['MainMenuFont'], 1, r))
        items.sort(key=lambda t: (-t[0], t[1]))
        for depth, kind, obj in items:
            if kind == 0:
                obj.on_gui(g, dt)
            else:
                obj.draw(g)
        if self.credits is not None and self.credits_go is not None \
                and self.scene.active_in_hierarchy(self.credits_go):
            self.credits.draw(g, dt)
        if self.combo is not None and (self.combo_go is None
                                       or self.scene.active_in_hierarchy(self.combo_go)):
            self.combo.update_and_draw(g)
        self.exit_message.draw(g)
        if self.intro is not None:
            self.intro.draw(g)
        if self.cursor_tex:
            mx, my = self.mouse
            g.tex(self.cursor_tex, (mx + self.cursor_delta.get('x', 0.0),
                                    my + self.cursor_delta.get('y', 0.0),
                                    self.cursor_rect[2], self.cursor_rect[3]))
