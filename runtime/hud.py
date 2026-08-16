"""The in-game HUD, ported from HUD.cs method by method.

Coordinates follow Helpers.AdjustRectangleRelatizeSize: a serialized rect's
x and y are fractions of the screen, its width and height are design pixels
scaled by screen/800 and screen/600. The mouse hit test is
Helpers.PointInRect (bottom-up y in Unity; SDL's y is already top-down).

Text renders through SDL_ttf with a system font — the game's own fonts are
Unity assets that are not extracted; sizes approximate
LevelDataGUIRenderer.CalculateFontSize by plain screen scaling.
"""
import os, re, ctypes

import sdl2

try:
    from sdl2 import sdlttf
except Exception:                                  # pragma: no cover
    sdlttf = None

FONT_CANDIDATES = (
    '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/TTF/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    # the Windows bundle's fallbacks (the game's own faces, extracted on
    # the first run, always win — hud/gui try them first)
    'C:\\Windows\\Fonts\\arialbd.ttf',
    'C:\\Windows\\Fonts\\arial.ttf',
)

# CalculateRating's message keys (GameInfo.cs:93-101)
RATING_KEYS = {'EXCELLENT': 'EXCELLENTMSG', 'GOOD': 'GOODJOBMSG',
               'PASSED': 'PASSMSG', 'FAILED': 'FAIL2MSG',
               'TIME UP': 'TIMEUPMSG'}

# HUD.Start's LoadTextures base paths (HUD.cs:349-352). The strips share
# base names (all three faces ship an idle_0000), so the cache must see the
# full Resources path — tools/extract_gui.py stores them path-flattened.
WOODY_BASE = 'Textures/GUI/ingame2/woody_mb/'
ROTT_BASE = 'Textures/GUI/ingame2/neighbor/'
MOTHER_BASE = 'Textures/GUI/ingame2/mother/'
WHISTLE_BASE = 'Textures/GUI/main/'
# Actor.GetBaseIconPath (Actor.cs:64-71)
BUBBLE_BASES = ('Textures/Bubbles/', 'Textures/NFH2/Bubbles/')


def load_strings(level_path, language=0):
    """LocalizationManager.LoadLocalizationFile: 'KEY<>VALUE' lines from
    Localization/Final/<language> — the file is picked by SettingKey.Language
    (LocalizationManager.cs:80-117; 0 = Lang, the port keeps that default so
    the bare viewer reads English); ';' comments. tools/extract_strings.py
    puts the extracted files under strings/{s1,s2}/."""
    from menu import LANGUAGES
    from base import asset_root
    root = asset_root()
    season = 's2' if '/s2/' in level_path.replace('\\', '/') else 's1'
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


def _names(text):
    """HUD.LoadTextures splits the TextAsset on ':' (and newlines)"""
    out = []
    for part in (text or '').replace('\r', '\n').replace('\n', ':').split(':'):
        part = part.strip()
        if part:
            out.append(part)
    return out


class HudAnim:
    """HUDAnimation: per-frame times, optional looping, paused until Restart."""

    def __init__(self, d):
        d = d or {}
        self.indices = list(d.get('Indices') or [])
        self.times = list(d.get('Times') or [])
        self.looping = bool(d.get('Looping'))
        self.finished = True
        self.paused = True
        self.idx = 0
        self.t = 0.0

    def restart(self):
        if not self.indices:
            return
        self.idx = 0
        self.t = self.times[0]
        self.finished = False
        self.paused = False

    @property
    def running(self):
        return not self.finished and not self.paused

    @property
    def frame(self):
        if not self.indices:
            return 0
        return self.indices[min(self.idx, len(self.indices) - 1)]

    def update(self, dt):
        """HUDAnimation.Update, dt in place of Time.deltaTime"""
        if self.finished or self.paused:
            return
        self.t -= dt
        if self.t > 0.0:
            return
        self.idx += 1
        if self.idx >= len(self.indices):
            if not self.looping:
                self.finished = True
                self.idx -= 1
            else:
                self.idx = 0
        self.t = self.times[self.idx]


class Hud:
    def __init__(self, level, world, cache, renderer, width, height,
                 language=0):
        self.d = level.hud or {}
        self.level = level
        self.world = world
        self.cache = cache
        self.rnd = renderer
        self.W = width
        self.H = height
        d = self.d
        self.has_mother = 'Mother' in world.pawns
        # HUD.Start: the face and whistle strips come from TextAsset lists
        self.woody_faces = _names((d.get('WoodyFileNames') or {}).get('text'))
        self.rott_faces = _names((d.get('RottweilerFileNames') or {}).get('text'))
        self.mother_faces = _names((d.get('MotherFileNames') or {}).get('text'))
        self.whistle = _names((d.get('WhistleFileNames') or {}).get('text'))
        # HUDAnimations
        self.whistle_anim = HudAnim(d.get('WhistleAnim'))
        self.trick_anim = HudAnim(d.get('TrickAnim'))
        self.statue_anim = HudAnim(d.get('StatueAnim'))
        self.woody_idle = HudAnim(d.get('WoodyIdleAnim'))
        self.woody_laugh = HudAnim(d.get('WoodyLaughAnim'))
        self.rott_idle = HudAnim(d.get('RottweilerIdleAnim'))
        self.rott_sleep = HudAnim(d.get('RottweilerSleepAnim'))
        self.rott_blind = HudAnim(d.get('RottweilerBlindAnim'))
        self.rott_angry = [HudAnim(d.get('RottweilerAngry1Anim')),
                           HudAnim(d.get('RottweilerAngry2Anim')),
                           HudAnim(d.get('RottweilerAngry3Anim'))]
        self.mother_idle = HudAnim(d.get('MotherIdleAnim'))
        self.mother_sleep = HudAnim(d.get('MotherSleepAnim'))
        self.mother_blind = HudAnim(d.get('MotherBlindAnim'))
        # InitializeHUDAnims (HUD.cs:415-436): everything sits paused on
        # frame 0 — the grey statue, the resting whistle — and only the
        # three idle strips start (PlayRottweilerIdle/PlayWoodyIdle/
        # PlayMotherIdle)
        self.woody_active = self.woody_idle
        self.rott_active = self.rott_idle
        self.mother_active = self.mother_idle
        for a in (self.woody_idle, self.rott_idle, self.mother_idle):
            a.restart()
        self.displayed_begin = 0          # DisplayedItemsBegin
        self.max_items = d.get('MaxInventoryItemsDisplayed') or 5
        # InventoryManager.AddInventory / RemoveInventory call back into
        # HUD.OnInventoryAdded / OnInventoryRemoved (InventoryManager.cs:20, 53)
        world.inventory.on_added = self.on_inventory_added
        world.inventory.on_removed = self.on_inventory_removed
        self.tooltip = None               # HUD.Tooltip (SetTooltip's line)
        self.tooltip_state = 'Examine'    # HUD.CurrentTooltipState (enum default)
        self._hover_updated = False       # a SetTooltip pass ran this frame
        self.hover_started = None         # inventory hover bubble timer
        self.hover_index = None
        self.mouse = (0, 0)
        self.mouse_down = False
        # the description bubble (HUD.ShowDescription / DrawDescription)
        self.show_description = False
        self.colored_tooltip = False      # HUD.ColoredTooltip (the latch)
        self._hover_item = None           # Woody.HoverItem (an Item...)
        self._hover_door = None           # ...or a Door, which is an Item too
        self._hover_zone = None
        # DrawAngryMeter's 0.1 s repaint throttle (HUD.cs:1242-1247)
        self._angry_rects = None          # AngryMeterFullRect + UV rect
        self._last_angry_update = 0.0     # LastUpdateAngryMeterTime
        self.desc_string = ''
        self.desc_pos = (0.0, 0.0)
        self.desc_long = False
        self._angry_state = 'idle'
        self._mother_state = 'idle'
        self.cam = None                   # set by the viewer for the bars
        self.cursor_tex = None            # MouseCursor.CurrentTexture
        self._tricks_rects = None
        self._angry_count_rect = None
        self._statue_rect = None
        self.strings = load_strings(level.path, language)
        self.woody_strings = {
            k: self.loc((level.pawns.get('Woody') or {}).get(k + '_string', ''))
            for k in ('use', 'with', 'empty_use', 'look_at',
                      'open', 'examine', 'hide', 'end')}
        self._font = None
        self._font_small = None
        self._fonts = {}
        if sdlttf is not None:
            sdlttf.TTF_Init()
            # the game's own faces, extracted by tools/extract_strings.py;
            # a face name bakes its design point size (acmesa22, bluehigh18)
            from base import asset_root
            season = 's2' if '/s2/' in level.path.replace('\\', '/') else 's1'
            self._font_dir = os.path.join(asset_root(), 'fonts', season)
            self._font = self._style_font('TimeStyle') or \
                self._sys_font(self._style_size('TimeStyle'))
            self._font_small = self._style_font('TooltipStyle') or \
                self._sys_font(self._style_size('TooltipStyle'))

    def _sys_font(self, size):
        """a system face at the HUD.Start size — the fallback when the
        game's own faces are not extracted"""
        for p in FONT_CANDIDATES:
            if os.path.exists(p):
                return sdlttf.TTF_OpenFont(p.encode(), max(8, int(size)))
        return None

    # HUD.Start sizes its styles from the screen, not from the face
    # (HUD.cs:335-342, LevelDataGUIRenderer.CalculateFontSize cs:177-191:
    # (W/1024 + H/768)*10, the description W/1024*13, each truncated to
    # int and adjusted per style; ProgressBar.Start does the same +3 for
    # its DataStyle, ProgressBar.cs:79, 239-245). At 800x600 that is 15:
    # the clock 18, tooltips/score 13, rating 15, description 10.
    FONT_ADJUST = {'TimeStyle': 3, 'TimeShadowStyle': 3, 'DataStyle': 3,
                   'TooltipStyle': -2, 'ColoredTooltipStyle': -2,
                   'ScoreStyle': -2, 'ScoreStyleHover': -2,
                   'RatingStyle': 0}

    def _style_size(self, style_key):
        w_ratio = self.W / 1024.0
        h_ratio = self.H / 768.0
        if style_key == 'DescriptionStyle':
            return int(w_ratio * 13.0)              # CalculateFontSizeDescription
        base_key = style_key.split('@')[0]          # the per-bar DataStyle keys
        return int((w_ratio + h_ratio) * 10.0) + self.FONT_ADJUST.get(base_key, 0)

    def _style_font(self, style_key):
        """open the GUIStyle's serialized face at the size HUD.Start gives
        the style (the size baked into the face name — acmesa22,
        bluehigh18 — is the asset's, which the runtime overrides)"""
        st = self.d.get(style_key) or {}
        name = (st.get('m_Font') or {}).get('font') if \
            isinstance(st.get('m_Font'), dict) else None
        if not name:
            return None
        size = self._style_size(style_key)
        key = (name, size)
        if key in self._fonts:
            return self._fonts[key]
        font = None
        for cand in (name, name.upper(), name.lower()):
            p = os.path.join(self._font_dir, cand + '.ttf')
            if os.path.exists(p):
                font = sdlttf.TTF_OpenFont(p.encode(), max(8, size))
                break
        self._fonts[key] = font
        return font

    def loc(self, key):
        """LocalizationManager.GetString: empty when unknown"""
        if not key:
            return ''
        return self.strings.get(key, key)

    def _style_color(self, style_key, default=(255, 255, 255)):
        """the style's serialized m_Normal text color"""
        st = self.d.get(style_key)
        if isinstance(st, dict) and 'm_Normal.r' in st:
            return (int(round((st.get('m_Normal.r') or 0.0) * 255)),
                    int(round((st.get('m_Normal.g') or 0.0) * 255)),
                    int(round((st.get('m_Normal.b') or 0.0) * 255)))
        return default

    def _align(self, style_key, default=4):
        """the style's serialized TextAnchor (m_Alignment)"""
        st = self.d.get(style_key)
        if isinstance(st, dict) and st.get('m_Alignment') is not None:
            return st['m_Alignment']
        return default

    # -- geometry ----------------------------------------------------------
    def rect(self, name):
        """AdjustRectangleRelatizeSize over a serialized rect"""
        r = self.d.get(name)
        return self._adj(r)

    def _adj(self, r):
        if not r:
            return None
        return (r['x'] * self.W, r['y'] * self.H,
                r['width'] / 800.0 * self.W, r['height'] / 600.0 * self.H)

    def _hit(self, r, mx, my):
        """Helpers.PointInRect with SDL's top-down mouse"""
        return (r is not None and r[0] <= mx <= r[0] + r[2]
                and r[1] <= my <= r[1] + r[3])

    def _inventory_rects(self):
        return [self._adj(r) for r in (self.d.get('InventoryRects') or [])]

    def _tricks(self):
        """InitializeTricks (HUD.cs:437-517): the vertical coin ladder and the
        derived AngryCount / Statue anchors, computed once"""
        if self._tricks_rects is not None:
            return self._tricks_rects
        total = self.world.game.total
        H = self.H
        tr = self.d.get('TrickRect') or {'x': 0, 'y': 0, 'width': 0, 'height': 0}
        hstep = (self.d.get('TotalTrickHeight') or 53.0) * H / 600.0
        num = 0.0
        num2, num3, num4 = 1.0, 0.65, 0.75
        if total < 6:
            base = H / 1.6 - ((total - 2) // 2) * hstep
            if total == 4:
                num2, num4 = 1.1, 0.73
        elif total <= 7:
            base = H / 1.6 - ((total - 4) // 2) * hstep
            if total == 6:
                num2, num3, num4 = 1.1, 0.55, 0.65
            else:
                num2, num3, num4 = 1.1, 0.4, 0.55
        elif total <= 9:
            num4, num3, num2 = 0.4, 0.2, 1.0
            base = H / 1.3 - ((total - 4) // 2) * hstep
            num = base * 0.06
        else:
            num4, num3, num2 = 0.3, 0.055, 1.0
            base = H - (total // 2) * hstep
            num = base * 0.07
        rects = []
        y = base
        for i in range(total):
            rects.append({'x': tr['x'], 'y': y / H * num2,
                          'width': tr['width'], 'height': tr['height']})
            y -= hstep
        acr = self.d.get('AngryCountRect') or {'x': 0, 'y': 0,
                                               'width': 0, 'height': 0}
        sr = self.d.get('StatueRect') or {'x': 0, 'y': 0,
                                          'width': 0, 'height': 0}
        last_y = rects[-1]['y'] if rects else 0.0
        self._angry_count_rect = self._adj(
            {'x': acr['x'] - acr['x'] * 0.02, 'y': last_y * num4,
             'width': acr['width'], 'height': acr['height']})
        self._statue_rect = self._adj(
            {'x': sr['x'], 'y': last_y * num3,
             'width': sr['width'], 'height': sr['height']})
        self._tricks_rects = [self._adj(r) for r in rects]
        return self._tricks_rects

    # -- primitives --------------------------------------------------------
    def _tex(self, ref):
        """SDL plumbing: a serialized Texture reference (the exporter's
        {'texture': name}, collision-numbered) -> the cached texture"""
        if isinstance(ref, dict):
            ref = ref.get('texture')
        if not ref:
            return None
        return self.cache.get(ref)

    def _blit(self, ref, r, src=None):
        """SDL plumbing: GUI.DrawTexture(rect, texture) — one stretched blit"""
        entry = self._tex(ref)
        if entry is None or r is None:
            return
        tex = entry[0]
        dst = sdl2.SDL_Rect(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
        if src is None:
            sdl2.SDL_RenderCopy(self.rnd, tex, None, dst)
        else:
            s = sdl2.SDL_Rect(*[int(v) for v in src])
            sdl2.SDL_RenderCopy(self.rnd, tex, s, dst)

    def _measure(self, font, s):
        """SDL plumbing: the rendered size of a string (GUIStyle.CalcSize)"""
        w = ctypes.c_int(0)
        h = ctypes.c_int(0)
        sdlttf.TTF_SizeUTF8(font, s.encode(), ctypes.byref(w),
                            ctypes.byref(h))
        return w.value

    def _text(self, s, r, small=False, center=True, color=(255, 255, 255),
              align=None, style_key=None):
        """GUI.Label/TextArea honor the style's TextAnchor (m_Alignment):
        0-2 top, 3-5 middle, 6-8 bottom rows; left/center/right columns.
        `align` overrides the legacy `center` flag when given. A style_key
        additionally applies the serialized m_ContentOffset, m_Padding and
        m_WordWrap — DescriptionStyle ships offset y=-10, padding 4/4 and
        wrapping in every level."""
        font = None
        if style_key and sdlttf is not None:
            font = self._style_font(style_key)
        if font is None:
            font = self._font_small if small else self._font
        if font is None or not s or r is None:
            return
        st = self.d.get(style_key) if style_key else None
        clip = False
        if isinstance(st, dict):
            # the exporter flattens the style's sub-structs into dotted keys
            offx = st.get('m_ContentOffset.x', 0.0) or 0.0
            offy = st.get('m_ContentOffset.y', 0.0) or 0.0
            pl = st.get('m_Padding.left', 0) or 0
            pr = st.get('m_Padding.right', 0) or 0
            pt = st.get('m_Padding.top', 0) or 0
            pb = st.get('m_Padding.bottom', 0) or 0
            scale_x = self.W / 800.0
            scale_y = self.H / 600.0
            r = (r[0] + (offx + pl) * scale_x,
                 r[1] + (offy + pt) * scale_y,
                 r[2] - (pl + pr) * scale_x,
                 r[3] - (pt + pb) * scale_y)
            # m_TextClipping=1 crops the glyphs to the rect (the clock, the
            # score fields and both tooltip styles ship it)
            clip = st.get('m_TextClipping') == 1
            if align is None and st.get('m_Alignment') is not None:
                align = st['m_Alignment']
            if st.get('m_WordWrap'):
                wrapped = []
                for line in s.split('\n'):
                    words = line.split(' ')
                    cur = ''
                    for word in words:
                        cand = (cur + ' ' + word).strip()
                        if cur and self._measure(font, cand) > r[2]:
                            wrapped.append(cur)
                            cur = word
                        else:
                            cur = cand
                    wrapped.append(cur)
                s = '\n'.join(wrapped)
        if clip:
            cr = sdl2.SDL_Rect(int(r[0]), int(r[1]),
                               max(1, int(r[2])), max(1, int(r[3])))
            sdl2.SDL_RenderSetClipRect(self.rnd, ctypes.byref(cr))
        col = sdl2.SDL_Color(*color)
        lines = s.split('\n')
        rendered = []
        for line in lines:
            surf = sdlttf.TTF_RenderUTF8_Blended(font, line.encode(), col)
            if not surf:
                continue
            tex = sdl2.SDL_CreateTextureFromSurface(self.rnd, surf)
            rendered.append((tex, surf.contents.w, surf.contents.h))
            sdl2.SDL_FreeSurface(surf)
        total_h = sum(h for _, _, h in rendered)
        if align is None:
            y = r[1]
            col_kind = 1 if center else 0
        else:
            row, col_kind = align // 3, align % 3
            y = r[1] if row == 0 else \
                r[1] + (r[3] - total_h) / 2 if row == 1 else \
                r[1] + r[3] - total_h
        for tex, w, h in rendered:
            x = r[0] if col_kind == 0 else \
                r[0] + (r[2] - w) / 2 if col_kind == 1 else \
                r[0] + r[2] - w
            dst = sdl2.SDL_Rect(int(x), int(y), w, h)
            sdl2.SDL_RenderCopy(self.rnd, tex, None, dst)
            sdl2.SDL_DestroyTexture(tex)
            y += h
        if clip:
            sdl2.SDL_RenderSetClipRect(self.rnd, None)

    # -- state hooks (HUD.Play*) ------------------------------------------
    def _trick_state_string(self, it, fuckedup, compound_tricked, compound,
                            tricked_key):
        """the TrickItem override head (TrickItem.cs:1164-1225): FuckedUp,
        then the compound pair, then the depends-on tricked check"""
        if it.kind not in ('TrickItem', 'Drawing', 'Rake', 'Toilet',
                           'Television'):
            return None
        if it.fucked_up:
            return fuckedup
        if it.compound_tricked:
            return compound_tricked if it.tricked else compound
        if it.check_depends_on_tricked and \
                it.is_tricked(self.level.items):
            return getattr(it, tricked_key)
        return None

    def _get_name_string(self, it):
        """Item.GetNameString (Item.cs:2295-2314) + the TrickItem override
        (TrickItem.cs:1164-1183)"""
        s = self._trick_state_string(it, it.name_fuckedup_string,
                                     it.name_compound_tricked,
                                     it.name_compound, 'name_tricked_string')
        if s is not None:
            return s
        if it.name == 'ValveMain':
            return it.name_string if it.main_valve_open \
                else it.name_tricked_string
        if it.tricked:
            return it.name_tricked_string
        if it.primed:
            return it.name_primed_string
        return it.name_string

    def _get_with_string(self, it):
        """Item.GetWithString (Item.cs:2316-2327) + the TrickItem override
        (TrickItem.cs:1185-1204)"""
        s = self._trick_state_string(it, it.with_fuckedup_string,
                                     it.with_compound_tricked,
                                     it.with_compound, 'with_tricked_string')
        if s is not None:
            return s
        if it.tricked:
            return it.with_tricked_string
        if it.primed:
            return it.with_primed_string
        return it.with_string

    def get_description_string(self, it):
        """Item.GetDescriptionString (Item.cs:2329-2344) + the TrickItem
        override (TrickItem.cs:1206-1225)"""
        s = self._trick_state_string(it, it.description_fuckedup,
                                     it.description_compound_tricked,
                                     it.description_compound,
                                     'description_tricked')
        if s is not None:
            return s
        linked = self.level.items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        if it.tricked and linked is not None and linked.tricked:
            return it.description_linked
        if it.tricked:
            return it.description_tricked
        if it.primed:
            return it.description_primed
        return it.description_string

    def show_item_tooltip(self, key, wx, wy, use_long):
        """HUD.ShowItemTooltip (HUD.cs:702-709): latch the description
        bubble; DrawDescription renders it until a move clears it"""
        if not key:
            return
        self.show_description = True
        self.desc_string = self.loc(key)
        self.desc_pos = (wx, wy)
        self.desc_long = bool(use_long)

    def _draw_description(self):
        """HUD.DrawDescription (HUD.cs:673-700): the bubble at the projected
        DescriptionPosition, x-centred, sitting h*1.25 above"""
        if not self.show_description or self.cam is None:
            return
        if self.desc_long:
            tex = self.d.get('LongTextBubbleTexture')
            r = self.rect('LongTextBubbleRect')
        else:
            tex = self.d.get('TextBubbleTexture')
            r = self.rect('TextBubbleRect')
        if r is None:
            return
        sx, sy = self.cam.world_to_screen(self.desc_pos[0], self.desc_pos[1],
                                          self.W, self.H)
        rect = (sx - r[2] / 2.0, sy - r[3] * 1.25, r[2], r[3])
        self._blit(tex, rect)
        self._text(self.desc_string, rect, small=True, color=(40, 40, 40),
                   style_key='DescriptionStyle')

    def set_tooltip(self, state, text):
        """HUD.SetTooltip (HUD.cs:1024-1060): a latched ColoredTooltip
        blocks every write (cs:1026), the GoTo state renders empty
        (cs:1049-1051); CurrentTooltipState remembers the arm for
        MakePermanentTooltip (cs:1069-1075)"""
        self._hover_updated = True
        if self.colored_tooltip:
            return
        self.tooltip_state = state
        self.tooltip = None if state == 'GoTo' else text

    def update_hover(self, item, zone, door=None):
        """MouseCursor.UpdateHover -> UpdateMouseOver (MouseCursor.cs:93-348):
        the permanent tooltip under the cursor, every arm through
        SetTooltip. Nothing under the cursor writes nothing — DrawHUD's
        per-frame clear (HUD.cs:646-649) then empties the line."""
        w = self.world
        ws = self.woody_strings
        inv = w.inventory
        loc = self.loc
        tip = self.set_tooltip
        # Woody.HoverItem (MouseCursor.cs:165) — a Door is an Item too
        self._hover_item = item
        self._hover_door = door
        self._hover_zone = zone
        # UpdateMouseOver reads CurrentInventory — the icon-stage selection
        # (MouseCursor.cs:189-198); UsedInventory has no hover arm
        held = inv.current
        if held is not None:
            if item is not None:
                tail = loc(self._get_with_string(item))
            elif door is not None:            # Item.GetWithString on a Door
                tail = loc(door.with_string)
            else:
                tail = ws['empty_use']
            tip('UseWith', ws['use'] + loc(held.get('name') or '')
                + ws['with'] + tail)
            return
        if item is None and door is not None:
            # the Door arm of UpdateMouseOver (MouseCursor.cs:302-331):
            # locked speaks LookAt, an exit door speaks End, and both GoTo
            # arms render empty (SetTooltip's GoTo, HUD.cs:1049-1051)
            if door.locked:
                tip('LookAt', ws['look_at'] + loc(door.locked_name))
            elif getattr(door, 'exit_door', False):
                woody_zone = w.woody.zone.pid \
                    if w.woody and w.woody.zone else None
                zpid = door.zone
                if door.zone == woody_zone and door.link_to is not None:
                    other = self.level.door_by_pid(door.link_to)
                    zpid = other.zone if other is not None else zpid
                z = next((zz for zz in self.level.zones
                          if zz.pid == zpid), None)
                tip('End', ws['end'] + loc(z.end_string if z else ''))
            else:
                tip('GoTo', None)
            return
        if item is None:
            # the bare-zone arm (MouseCursor.cs:333-347); no zone at all
            # means no SetTooltip call
            if zone is None:
                return
            woody_zone = w.woody.zone.pid if w.woody and w.woody.zone else None
            if zone.pid != woody_zone and getattr(zone, 'exit', False):
                tip('End', ws['end'] + loc(zone.end_string))
            else:
                tip('GoTo', None)
            return
        if item.kind in ('TrickItem', 'Drawing', 'Rake', 'Toilet',
                         'Television'):
            if item.is_floor:
                tip('GoTo', None)                       # GoTo renders empty
            elif item.required_inventory in (None, '', 'IT_NONE') \
                    and item.tricked \
                    and not item.dont_change_tooltip_when_tricked:
                tip('LookAt', ws['look_at'] + loc(self._get_name_string(item)))
                self._swap_cursor_icon(item, item.mouse_over_after_trick)
            elif item.required_inventory in (None, '', 'IT_NONE') \
                    and not item.tricked \
                    and item.dont_change_tooltip_when_tricked:
                tip('Use', ws['use'] + loc(self._get_name_string(item)))
            elif item.dont_change_tooltip_when_tricked and item.tricked:
                tip('Use', ws['use'] + loc(self._get_name_string(item)))
            elif item.change_tooltip_when_tricked:
                tip('Use', ws['use'] + loc(self._get_name_string(item)))
            else:
                tip('LookAt', ws['look_at'] + loc(self._get_name_string(item)))
                self._swap_cursor_icon(item, item.mouse_over_after_trick)
        elif item.kind == 'HideItem':
            tip('Hide', ws['hide'] + loc(item.hide_string_key))
        elif item.kind == 'SearchItem':
            if item.searching_item:
                if item.locked:
                    tip('LookAt', ws['look_at'] + loc(item.name_string))
                elif item.primed:
                    tip('Open', ws['open'] + loc(item.name_primed_string))
                elif item.require_priming:
                    tip('LookAt', ws['look_at'] + loc(item.name_string))
                else:
                    tip('Examine', ws['examine'] + loc(item.name_string))
            else:
                tip('Examine', ws['examine'] + loc(item.name_string))
        elif item.kind == 'GroundItem':
            tip('LookAt', ws['look_at'] + loc(item.name_string))
        elif item.kind == 'InspectItem':
            changer = self.level.items.get(item.item_that_changes_tooltip) \
                if item.item_that_changes_tooltip else None
            if changer is None or not changer.got_tricked:
                tip('LookAt', ws['look_at'] + loc(item.name_string))
            else:
                tip('LookAt', ws['look_at'] + loc(item.name_primed_string))
        # any other Item kind: UpdateMouseOver returns without a SetTooltip
        # (MouseCursor.cs:304-306)

    def _swap_cursor_icon(self, item, name):
        """UpdateMouseOver's MouseOverIcon reload
        (MouseCursor.cs, MouseOverBasePath)"""
        if item.change_mouse_over_after_trick and name:
            item.mouse_over_icon = 'Textures/GUI/cursor/' + name

    def update_cursor(self, item, door, zone, wx, wy, my):
        """MouseCursor.UpdateCursor (MouseCursor.cs): the held-inventory
        icons, the item/door MouseOverIcon, the walking cursor over other
        zones and the floor band, else the default"""
        w = self.world
        mc = self.level.mouse_cursor
        if mc is None:
            self.cursor_tex = None
            return
        # Woody.MouseOverHUD: the bottom MinMouseY pixels (design 600)
        over_hud = my > self.H - mc['min_mouse_y'] * self.H / 600.0
        woody = w.woody
        # UpdateHover's early out (GameEnding / a menu open)
        if w.game.ending or w.menu_open or woody is None:
            self.cursor_tex = mc['default_hud']
            return
        inv = w.inventory
        # UpdateCursor reads CurrentInventory only (MouseCursor.cs:362-373):
        # once promoted to Used the arms revert to the plain cursors
        if inv.current is not None:
            self.cursor_tex = mc['use_inv'] if (item is not None
                                                or door is not None) \
                else mc['cancel_inv']
            return
        woody_zone = woody.zone.pid if woody.zone else None
        cand = item if item is not None else door
        cand_icon = cand.mouse_over_icon if cand is not None else None
        # Item.CanUse, on doors too (Item.cs:314; MouseCursor.cs:374)
        cand_use = cand.can_use if cand is not None else False
        same_zone_door = door is None or door.zone == woody_zone
        if cand is not None and cand_icon and cand_use and same_zone_door:
            self.cursor_tex = mc['default_hud'] if over_hud else cand_icon
            return
        if door is not None and door.zone != woody_zone:
            self.cursor_tex = door.mouse_over_icon if door.locked \
                else mc['walking']
            return
        if zone is not None and (zone.pid != woody_zone
                                 or -0.6 <= wy - woody.sprite.y <= 0.16):
            self.cursor_tex = mc['walking']
            return
        self.cursor_tex = mc['default_hud'] if over_hud else mc['default']

    def draw_cursor(self, mx, my):
        """MouseCursor.OnGUI (MouseCursor.cs:60-91): the cursor texture at
        the mouse, cursorSize through AdjustRectangle"""
        mc = self.level.mouse_cursor
        if mc is None or self.world.is_dexterity_on:
            return
        tex = self.cursor_tex or mc['default']
        if tex is None:
            return
        r = mc['size']
        self._blit(tex, (mx, my, r.get('width', 0.03) * self.W,
                         r.get('height', 0.04) * self.H))

    def play_trick_done(self):
        """HUD.PlayTrickDone + Woody.PlayTrickDone's laugh"""
        self.trick_anim.restart()
        self.woody_laugh.restart()
        self.woody_active = self.woody_laugh

    def play_rottweiler_angry(self, level):
        """HUD.PlayRottweilerAngry(RottweilerAngerLevel): the angry face
        strip for the level PlayAngryAnimation picked (Rottweiler.cs:600,
        607, 672-688); the idle returns when the strip finishes"""
        self._angry_state = 'angry'
        self.rott_active = self.rott_angry[max(0, min(2, level - 1))]
        self.rott_active.restart()

    def play_whistle(self):
        """HUD.PlayWhistle (HUD.cs:1473-1481): the whistling sound plus a
        WhistleAnim restart"""
        snd = self.d.get('WhistlingSound')
        clip = snd.get('clip') if isinstance(snd, dict) else None
        if clip and self.world.sound_sink is not None:
            self.world.sound_sink(clip)
        self.whistle_anim.restart()

    def _icon_names(self, entry):
        """Inventory.Initialize's icon paths (Inventory.cs:110-124)"""
        t = entry.get('type') or ''
        if t.startswith('IT2_'):
            base = 'inventory2/' + t[4:].lower()
            return base + '_hovered', base + '_std', base + '_down'
        base = 'inventory/I_' + (t[3:] if t.startswith('IT_') else t).lower()
        return base + '_hov', base + '_norm', base + '_pres'

    # -- drawing -----------------------------------------------------------
    def draw(self, dt, mouse, mouse_down=False):
        self.mouse = mouse
        self.mouse_down = mouse_down
        w = self.world
        g = w.game
        self._draw_dexterity()
        # the world-anchored bars draw at GUIDepth.BackHUD — beneath the
        # HUD strip (ProgressBar.TexturesGUIDepth serializes BackHUD=12,
        # the HUD itself sits at 11)
        self._draw_progress_bars()
        # DrawHUD opens with the description bubble (HUD.cs:636-638)
        self._draw_description()
        self._draw_base()
        self._draw_inventory(dt)
        # DrawHUD's per-frame clear (HUD.cs:646-649): an unlatched line
        # survives only the frame it was set in — a frame without a
        # SetTooltip pass (GameEnding / a menu stops UpdateHover,
        # MouseCursor.cs:120-124) draws nothing. The clear runs before the
        # draw here so the recorder still sees the drawn line afterwards.
        if not self.colored_tooltip and not self._hover_updated:
            self.tooltip = None
        self._hover_updated = False
        if self.tooltip:
            # the Mother levels park the permanent tooltip elsewhere
            # (HUD.cs:611-614); a latched tooltip draws the colored style
            # (DrawTooltip, HUD.cs:1084-1093 — yellow 0.86/0.86/0)
            trect = self.rect('TooltipMotherRect') if self.has_mother and \
                self.d.get('TooltipMotherRect') else self.rect('TooltipRect')
            skey = 'ColoredTooltipStyle' if self.colored_tooltip \
                else 'TooltipStyle'
            self._text(self.tooltip, trect, small=True,
                       color=self._style_color(skey),
                       align=self._align(skey, 3), style_key=skey)
        self._draw_buttons()
        self._draw_angry_meter(dt)
        if not g.is_tutorial:
            self._draw_tricks(dt)
            self._draw_time()
        self._draw_characters(dt)
        if g.ended:
            self._draw_score()
        self._draw_angry_count()

    def _draw_base(self):
        """DrawBase: the Mother levels use the alternate art"""
        if not self.has_mother:
            self._blit(self.d.get('MainBackground'),
                       self.rect('MainBackgroundRect'))
            self._blit(self.d.get('RottweilerOnlyBackground'),
                       self.rect('RottweilerOnlyBackgroundRect'))
        else:
            self._blit(self.d.get('AlternateBackground'),
                       self.rect('AlternateBackgroundRect'))
            self._blit(self.d.get('RottweilerAndMotherBackground'),
                       self.rect('RottweilerAndMotherBackgroundRect'))
        self._blit(self.d.get('WoodyMobileBackground'),
                   self.rect('WoodyMobileBackgroundRect'))

    def on_inventory_added(self):
        """HUD.OnInventoryAdded (HUD.cs:898-905): the page jumps so the
        newest item is visible"""
        n = len(self.world.inventory.items)
        rects = len(self.d.get('InventoryRects') or [])
        if n > rects:
            self.displayed_begin = n - rects
        self._check_displayed_begin()

    def on_inventory_removed(self):
        """HUD.OnInventoryRemoved (HUD.cs:907-914): fired before the
        RemoveAt, so the clamp reads the pre-removal count"""
        n = len(self.world.inventory.items)
        rects = len(self.d.get('InventoryRects') or [])
        if self.displayed_begin >= n - rects:
            self.displayed_begin = n - rects
        self._check_displayed_begin()

    def _check_displayed_begin(self):
        """HUD.CheckDisplayedItemsBegin (HUD.cs:916-922)"""
        if self.displayed_begin < 0:
            self.displayed_begin = 0

    def _draw_inventory(self, dt):
        """DrawNavigationArrows + DrawInventory (HUD.cs:804-810, 924-1022):
        icons in norm/hov/pres state, the pressed icon's UseWith line, the
        1 s hover bubble"""
        w = self.world
        g = w.game
        inv = w.inventory
        items = inv.items
        rects = self._inventory_rects()
        mx, my = self.mouse
        ws = self.woody_strings
        loc = self.loc
        # DrawNavigationArrows (HUD.cs:804-810); DisplayedItemsBegin moves
        # only through OnInventoryAdded/Removed and the arrow clicks
        if self.displayed_begin > 0:
            self._blit((self.d.get('InventoryPrevious') or [None, None])[1],
                       self.rect('InventoryPreviousRect'))
        if self.displayed_begin + self.max_items < len(items):
            self._blit((self.d.get('InventoryNext') or [None, None])[1],
                       self.rect('InventoryNextRect'))
        hover_any = False
        for i, r in enumerate(rects):
            k = i + self.displayed_begin
            if k >= len(items):
                break
            entry = items[k]
            hov, norm, pres = self._icon_names(entry)
            over = self._hit(r, mx, my) and not g.ending
            if inv.current is entry:
                # only CurrentInventory draws pressed (UsedInventory has no
                # draw state), and its item's OnIconPressed is polled every
                # frame — the phones raise the alarm and deselect
                # themselves, GameEnding deselects too (HUD.cs:942-960)
                if w.icon_pressed(entry) and not g.ending:
                    # SetTooltip(UseWith, name, HoverItem == null ?
                    # EmptyUseString : HoverItem.GetNameString()) — the
                    # hovered Item or Door, through the latch gate
                    if self._hover_item is not None:
                        tail = loc(self._get_name_string(self._hover_item))
                    elif self._hover_door is not None:
                        tail = loc(self._hover_door.locked_name)   # NameString
                    else:
                        tail = ws['empty_use']
                    self.set_tooltip('UseWith', ws['use']
                                     + loc(entry.get('name') or '')
                                     + ws['with'] + tail)
                    self._blit(pres, r)
                else:
                    inv.current = None            # SetCurrentInventory(null)
                    self._blit(norm, r)
            elif over:
                # an unselected icon under the cursor with nothing selected
                # speaks "Use X with nothing" (HUD.cs:962-967)
                if inv.current is None:
                    self.set_tooltip('UseWith', ws['use']
                                     + loc(entry.get('name') or '')
                                     + ws['with'] + ws['empty_use'])
                self._blit(hov, r)
            else:
                self._blit(norm, r)
            if not over:
                continue                          # HUD.cs:982-985
            hover_any = True
            if self.hover_index != k:
                self.hover_index = k              # HoverInventory / start
                self.hover_started = 0.0
                continue
            self.hover_started = (self.hover_started or 0.0) + dt
            # the bubble needs a non-empty DescriptionString (HUD.cs:991)
            desc = entry.get('desc') or ''
            if self.hover_started > (self.d.get(
                    'InventoryTooltipHoverInterval') or 1.0) and desc:
                # a LongDescription inventory speaks through the big bubble
                # (DrawInventory, HUD.cs:995-1008)
                if entry.get('long'):
                    br = self.rect('LongTextBubbleRect')
                    tex = self.d.get('LongTextBubbleTexture')
                else:
                    br = self.rect('TextBubbleRect')
                    tex = self.d.get('TextBubbleTexture')
                if br is not None:
                    div = 4.0 if i == 0 else 2.5
                    bubble = (r[0] - br[2] / div, r[1] - br[3],
                              br[2], br[3])
                    self._blit(tex, bubble)
                    self._text(loc(desc), bubble, small=True,
                               color=(40, 40, 40),
                               style_key='DescriptionStyle')
        if not hover_any:
            self.hover_index = None               # HoverInventory = IT_NONE
            self.hover_started = None

    def _draw_buttons(self):
        """DrawButtons/DrawActionButton: normal/hover textures; the sneak
        button shows the pressed art while the toggle is on"""
        mx, my = self.mouse
        g = self.world.game

        def button(textures, r, pressed=False):
            if not textures or r is None:
                return
            idx = 1
            if pressed:
                idx = 2
            elif self._hit(r, mx, my) and not g.ending:
                idx = 0
            self._blit(textures[min(idx, len(textures) - 1)], r)
        button(self.d.get('PowerButtons'), self.rect('PowerRect'))
        if g.completed >= g.winning:
            button(self.d.get('CompleteEpisodeButtons'), self.rect('CompleteRect'))
        sn = self.d.get('SneakButtons')
        if sn and len(sn) == 3 and self.world.woody is not None:
            button(sn, self.rect('SneakRect'),
                   pressed=self.world.woody.sneak_toggle)
        inf = self.d.get('InfoButtons')
        if inf and len(inf) == 3:
            # DrawActionButton's info arms (HUD.cs:835-895): a touch held on
            # the button shows every item's interaction icon, releasing (or
            # leaving the rect) clears it. The mouse plays the touch: held
            # button down over the rect = the Stationary/Moved phases.
            r = self.rect('InfoRect')
            held = (self._hit(r, self.mouse[0], self.mouse[1])
                    and getattr(self, 'mouse_down', False) and not g.ending)
            self.world.game.show_interaction_icon = held
            button(inf, r, pressed=held)

    def _draw_angry_meter(self, dt):
        """DrawAngryMeter: the full strip is clipped from the bottom by the
        meter percentage, plus the whistle idle animation"""
        rott = self.world.pawns.get('Rottweiler')
        if rott is None:
            return
        self._blit(self.d.get('AngryMeterEmpty'), self.rect('AngryMeterEmptyRect'))
        full = self.rect('AngryMeterFullRect')
        entry = self._tex(self.d.get('AngryMeterFull'))
        if rott.angry_meter > 0.0 and full is not None and entry is not None:
            # the fill rect and its UV window are recomputed at most every
            # 0.1 s of Time.time (LastUpdateAngryMeterTime, HUD.cs:1240-1248)
            # — the meter moves in 10 Hz steps and draws the cached rects
            # between updates
            tex, tw, th = entry[0], entry[1], entry[2]
            now = self.world.time
            if self._angry_rects is None or \
                    now - self._last_angry_update > 0.1:
                pct = max(0.0, min(100.0, rott.angry_meter)) / 100.0
                self._angry_rects = (
                    (int(full[0]), int(full[1] + full[3] * (1.0 - pct)),
                     int(full[2]), int(full[3] * pct)),
                    (0, int(th * (1.0 - pct)), tw, int(th * pct)))
                self._last_angry_update = now
            dst = sdl2.SDL_Rect(*self._angry_rects[0])
            src = sdl2.SDL_Rect(*self._angry_rects[1])
            sdl2.SDL_RenderCopy(self.rnd, tex, src, dst)
        self.whistle_anim.update(dt)
        if self.whistle:
            i = min(self.whistle_anim.frame, len(self.whistle) - 1)
            name = WHISTLE_BASE + self.whistle[i]
            r = self.rect('WhistleRect')
            entry = self._tex(name)
            if r is not None and entry is not None:
                # WhistleRects[i]: the frame breathes — its size is the
                # average of the adjusted rect and the frame's own pixels
                # (HUD.Start, HUD.cs:353-357)
                r = (r[0], r[1], (r[2] + entry[1]) / 2.0,
                     (r[3] + entry[2]) / 2.0)
            self._blit(name, r)

    def _draw_tricks(self, dt):
        """DrawTricks: the coin ladder, the celebration strip, the statue"""
        g = self.world.game
        rects = self._tricks()
        for i, r in enumerate(rects):
            if i < g.completed:
                if i < g.completed - 1 or not self.trick_anim.running:
                    self._blit(self.d.get('TrickFull'), r)
            else:
                self._blit(self.d.get('TrickEmpty'), r)
        if self.trick_anim.running and g.completed > 0:
            self.trick_anim.update(dt)
            adj = self.d.get('TrickDoneAdjustRect') or {}
            base = rects[g.completed - 1]
            r = (base[0] + (adj.get('x', 0.0)) * self.W,
                 base[1] + (adj.get('y', 0.0)) * self.H,
                 (adj.get('width', 0.0)) / 800.0 * self.W,
                 (adj.get('height', 0.0)) / 600.0 * self.H)
            frames = self.d.get('TrickDoneAnimation') or []
            if frames:
                self._blit(frames[min(self.trick_anim.frame, len(frames) - 1)], r)
        self.statue_anim.update(dt)
        statues = self.d.get('Statue') or []
        if statues and self._statue_rect is not None:
            self._blit(statues[min(self.statue_anim.frame, len(statues) - 1)],
                       self._statue_rect)

    def _draw_time(self):
        """DrawTime: mm:ss when timed, --:-- otherwise (non-NFH2 only)"""
        woody = self.world.woody
        if woody is not None and woody.nfh2:
            return
        g = self.world.game
        if g.timed:
            n = max(0, int(g.time_seconds))
            s = '%02d:%02d' % (n // 60, n % 60)
        else:
            s = '--:--'
        self._text(s, self.rect('TimeShadowRect'), color=(0, 0, 0),
                   align=self._align('TimeShadowStyle', 4),
                   style_key='TimeShadowStyle')
        self._text(s, self.rect('TimeRect'),
                   align=self._align('TimeStyle', 4),
                   style_key='TimeStyle')

    def _draw_characters(self, dt):
        """DrawCharacters: the face strips and the think bubbles with the
        current action's item icon (RoutineAction.BubbleIcon)"""
        rott = self.world.pawns.get('Rottweiler')
        # face-state selection (HUD.PlayRottweiler*); a ProgressBar's
        # SetSleeping picks the blind strip over sleep
        # (ProgressBar.cs:183-192)
        if rott is not None:
            # the sleep/blind strips override; the angry strip arrives by
            # PlayRottweilerAngry and hands back to the idle when it ends
            # (HUD.PlayRottweilerIdle on Restart)
            state = ('blind' if rott.hud_blind else 'sleep') \
                if rott.is_sleeping else self._angry_state
            if state in ('sleep', 'blind') and state != self._angry_state:
                self._angry_state = state
                self.rott_active = self.rott_sleep if state == 'sleep' \
                    else self.rott_blind
                self.rott_active.restart()
            elif state == 'angry' and self.rott_active.finished:
                self._angry_state = 'idle'
                self.rott_active = self.rott_idle
                self.rott_active.restart()
            elif state not in ('sleep', 'blind', 'angry') \
                    and self.rott_active not in (self.rott_idle,):
                self._angry_state = 'idle'
                self.rott_active = self.rott_idle
                self.rott_active.restart()
        if self.woody_active.finished:
            self.woody_active = self.woody_idle
            self.woody_idle.restart()
        self.woody_active.update(dt)
        if self.woody_faces:
            self._blit(WOODY_BASE + self.woody_faces[
                min(self.woody_active.frame, len(self.woody_faces) - 1)],
                self.rect('WoodyFaceRect'))
        self.rott_active.update(dt)
        if self.rott_faces:
            self._blit(ROTT_BASE + self.rott_faces[
                min(self.rott_active.frame, len(self.rott_faces) - 1)],
                self.rect('RottweilerFaceRect'))
        self._face_fill('Rottweiler', 'RottweilerFaceRect')
        # DisableRottweilerThinkBubble skips the whole bubble (HUD.cs:1155)
        if rott is None or not rott.hud_disable_think:
            routine = next((r for r in self.world.routines
                            if r.role == 'Rottweiler'), None)
            self._think_bubble(routine, 'RottweilerThinkBubble',
                               'RottweilerThinkBubbleRect',
                               'RottweilerThinkBubbleIconRect')
        if self.has_mother:
            mother = self.world.pawns.get('Mother')
            # PlayMotherSleep/Blind/Idle (HUD.cs:1440-1460) via SetSleeping
            if mother is not None:
                mstate = ('blind' if mother.hud_blind else 'sleep') \
                    if mother.is_sleeping else 'idle'
                if mstate != self._mother_state:
                    self._mother_state = mstate
                    self.mother_active = {
                        'sleep': self.mother_sleep,
                        'blind': self.mother_blind}.get(mstate, self.mother_idle)
                    self.mother_active.restart()
            self.mother_active.update(dt)
            if self.mother_faces:
                self._blit(MOTHER_BASE + self.mother_faces[
                    min(self.mother_active.frame, len(self.mother_faces) - 1)],
                    self.rect('MotherFaceRect'))
            self._face_fill('Mother', 'MotherFaceRect')
            # DisableMotherThinkBubble (HUD.cs:1176)
            if mother is None or not mother.hud_disable_think:
                mrt = next((r for r in self.world.routines
                            if r.role == 'Mother'), None)
                self._think_bubble(mrt, 'MotherThinkBubble',
                                   'MotherThinkBubbleRect',
                                   'MotherThinkBubbleIconRect')

    def _face_fill(self, actor, rect_key):
        """HUDProgressBar.OnGUI (HUDProgressBar.cs:10-21): the face overlay
        drains top-down — the group's height is (1 - progress) of the face
        rect, cropping the overlay texture's bottom off. The menu hides it
        (OnGameMenuEnter -> Hide, HUDProgressBar.cs:23-43)."""
        if self.world.menu_open:
            return
        for pb in self.world.progress_bars:
            if not (pb.visible and pb.is_pawn_hud
                    and pb.spec['actor'] == actor):
                continue
            r = self.rect(rect_key)
            p = min(1.0, max(0.0, pb.progress))
            hh = (1.0 - p) * r[3]
            if hh <= 0:
                continue
            entry = self._tex(pb.hud_tex)
            if entry is None:
                continue
            th = entry[2]
            import sdl2
            src = sdl2.SDL_Rect(0, 0, entry[1], max(1, int(th * (1.0 - p))))
            self._blit(pb.hud_tex, (r[0], r[1], r[2], hh), src=src)
            return

    def _draw_dexterity(self):
        """DexterityComponent.OnGUI (DexterityComponent.cs:428-454): the
        field (rotated 180 with the alarm fill clipped to the percentage),
        the item ghost and the pick cursor"""
        for ds in getattr(self.world, 'dex_states', {}).values():
            if not ds.enabled:
                continue
            bg = ds.spec['bg_wrong'] if ds.wrong else ds.spec['bg']
            self._blit(bg, tuple(ds.bg))
            # RotateAroundPivot(180) + a group of height p: the group clips
            # the texture's top p, and the rotation lands it — upside down —
            # on the BOTTOM of the field
            p = min(1.0, max(0.0, ds.percent / 100.0))
            fill_h = ds.bg[3] * p
            entry = self._tex(ds.spec['full'])
            if entry is not None and fill_h > 0:
                import sdl2 as _sdl
                th = entry[2]
                srcr = _sdl.SDL_Rect(0, 0, entry[1], max(1, int(th * p)))
                dstr = _sdl.SDL_Rect(int(ds.bg[0]),
                                     int(ds.bg[1] + ds.bg[3] - fill_h),
                                     int(ds.bg[2]), max(1, int(fill_h)))
                _sdl.SDL_RenderCopyEx(self.rnd, entry[0], srcr, dstr,
                                      180.0, None, _sdl.SDL_FLIP_NONE)
            self._blit(ds.spec['bg_item'], tuple(ds.item_rect))
            self._blit(ds.spec['fg'], tuple(ds.fg))

    def _draw_progress_bars(self):
        """ProgressBar.OnGUI (ProgressBar.cs:247-272): the world-anchored
        percent bar — empty backdrop, the full strip clipped to progress and
        the percent label"""
        if self.cam is None:
            return
        for pb in self.world.progress_bars:
            if not pb.visible:
                continue
            sx, sy = self.cam.world_to_screen(pb.spec['x'], pb.spec['y'],
                                              self.W, self.H)
            d = pb.spec['delta']
            r = pb.spec['rect']
            x = sx + d.get('x', 0.0) * self.W
            y = sy + d.get('y', 0.0) * self.H
            w = r.get('width', 0.0) * self.W
            h = r.get('height', 0.0) * self.H
            p = min(1.0, max(0.0, pb.progress))
            self._blit(pb.spec['empty'], (x, y, w, h))
            if p > 0:
                entry = self._tex(pb.spec['full'])
                if entry is not None:
                    import sdl2
                    src = sdl2.SDL_Rect(0, 0, max(1, int(entry[1] * p)),
                                        entry[2])
                    self._blit(pb.spec['full'], (x, y, w * p, h), src=src)
            # Helpers.DrawLabel with the bar's DataStyle (ProgressBar.cs:269;
            # m_Alignment 4, the face from the style, the size
            # CalculateFontSize(0)+3, cs:79) — the style rides the bar spec,
            # so it is registered under a per-bar key for _style_font
            skey = 'DataStyle@%s' % pb.spec.get('pid')
            if skey not in self.d and pb.spec.get('data_style'):
                self.d[skey] = pb.spec['data_style']
            self._text('%d%%' % int(round(p * 100)), (x, y, w, h), small=True,
                       align=4, style_key=skey if skey in self.d else None)

    def _think_bubble(self, routine, tex_key, rect_key, icon_rect_key):
        self._blit(self.d.get(tex_key), self.rect(rect_key))
        if routine is None:
            return
        it = routine.urgent_item or routine.item
        name = None
        if it is not None:
            # Alerter actions show BubbleIconMad (RoutineActionUse.BubbleIcon
            # override); actives win over the plain icon
            if it.kind == 'Alerter':
                name = it.bubble_icon_mad or it.bubble_icon
            # the Mother's special icon (RoutineAction.BubbleMotherIcon,
            # RoutineAction.cs:59-70)
            if name is None and routine.role == 'Mother' \
                    and it.special_bubble_for_mother:
                name = it.bubble_mother_icon
            if name is None:
                name = it.bubble_icon_active or it.bubble_icon
        else:
            # a MoveOnly action shows MoveZone.BubbleIcon (RoutineAction.cs:53)
            a = routine.action
            zone_go = a.get('move_zone') if a else None
            icons = self.level.bubble_icons.get(zone_go) if zone_go else None
            if icons:
                name = icons.get('active') or icons.get('icon')
        if name:
            r = self.rect(icon_rect_key)
            for base in BUBBLE_BASES:
                if self._tex(base + name) is not None:
                    self._blit(base + name, r)
                    return
            self._blit(os.path.basename(name), r)

    def _draw_angry_count(self):
        """DrawAngryCount: 'xN' beside the coins (non-NFH2, unless disabled)"""
        g = self.world.game
        woody = self.world.woody
        rott = self.world.pawns.get('Rottweiler')
        if rott is None or g.dont_show_angry_count or \
                (woody is not None and woody.nfh2):
            return
        self._tricks()
        # Helpers.DrawLabel(AngryCountRect, ..., TimeStyle) — HUD.cs:669
        self._text('x%d' % rott.angry_count_ticks, self._angry_count_rect,
                   align=self._align('TimeStyle', 4), style_key='TimeStyle')

    def _draw_score(self):
        """DrawScore (game over, Classic): the board, the ratings, the
        restart / ok buttons"""
        g = self.world.game
        mx, my = self.mouse
        self._blit(self.d.get('OriginalScoreboard'), self.rect('OriginalScoreRect'))
        # the three TextFields: Rating, "GO_TRICKS\nC / T", "GO_VIEWER_RATING\nN%"
        self._text(self.loc(RATING_KEYS.get(g.rating, g.rating)),
                   self.rect('RatingRatioRect'),
                   color=self._style_color('RatingStyle'),
                   align=self._align('RatingStyle', 4),
                   style_key='RatingStyle')
        self._text(self.loc('GO_TRICKS') + '\n' + g.trick_ratio,
                   self.rect('TrickRatioRect'),
                   color=self._style_color('ScoreStyle'),
                   align=self._align('ScoreStyle', 4),
                   style_key='ScoreStyle')
        self._text(self.loc('GO_VIEWER_RATING') + '\n' + g.viewer_rating,
                   self.rect('ViewerRatingRect'),
                   color=self._style_color('ScoreStyle'),
                   align=self._align('ScoreStyle', 4),
                   style_key='ScoreStyle')
        for rk, mk, key in (('RestartButtonRect', 'RestartMessageRect',
                             'RESTART_MESSAGE'),
                            ('OkButtonRect', 'OkMessageRect', 'OK_MESSAGE')):
            r = self.rect(rk)
            hover = self._hit(r, mx, my)
            self._blit(self.d.get('ScoreButtonHover' if hover else 'ScoreButton'), r)
            # a hover swaps the text style too (DrawScore, HUD.cs:744-763)
            skey = 'ScoreStyleHover' if hover else 'ScoreStyle'
            self._text(self.loc(key), self.rect(mk), small=True,
                       color=self._style_color(skey),
                       align=self._align('DescriptionStyle', 4))

    # -- input -------------------------------------------------------------
    def check_click(self, mx, my):
        """HUD.CheckClick: True consumes the click before the world sees it.
        Returns 'restart' from the score screen's restart button."""
        self.mouse = (mx, my)
        w = self.world
        g = w.game
        inv = w.inventory
        if g.ending:
            if g.ended:
                if self._hit(self.rect('RestartButtonRect'), mx, my):
                    return 'restart'
                if self._hit(self.rect('OkButtonRect'), mx, my):
                    return 'next'      # the level selection menu is not
                                       # modelled; the viewer opens the next
                                       # level of its list instead
            if self._hit(self.rect('PowerRect'), mx, my):
                w.toggle_menu()        # HUD.cs:1302-1306: still live at the end
                return True
            return False
        rects = self._inventory_rects()
        for i, r in enumerate(rects):
            k = i + self.displayed_begin
            if k >= len(inv.items):
                break
            if self._hit(r, mx, my) and inv.current is not inv.items[k]:
                # SetCurrentInventory + the UseWith line (HUD.cs:1311-1316);
                # the item's OnIconPressed is polled by DrawInventory from
                # the next frame on (HUD.cs:944) — the phones deselect there
                inv.current = inv.items[k]
                self.set_tooltip('UseWith', self.woody_strings['use']
                                 + self.loc(inv.items[k].get('name') or '')
                                 + self.woody_strings['with']
                                 + self.woody_strings['empty_use'])
                return True
        # every click past the icons (HUD.cs:1319-1327): SetUsedInventory(
        # CurrentInventory) — unconditional, so a click with nothing selected
        # drops the used one — then UpdateTooltip: clear the latch, re-hover
        # with Current still set, and latch unless the arm is GoTo
        # (MakePermanentTooltip, cs:1069-1075); then SetCurrentInventory(null),
        # a second UpdateHover (blocked by the latch), and the latch is
        # dropped when no Item — a Door is one — sits under the cursor
        inv.used = inv.current                # Woody.SetUsedInventory
        self.colored_tooltip = False          # ClearPermanentTooltip
        self.update_hover(self._hover_item, self._hover_zone, self._hover_door)
        if self.tooltip_state != 'GoTo':
            self.colored_tooltip = True       # MakePermanentTooltip
        inv.current = None                    # SetCurrentInventory(null)
        self.update_hover(self._hover_item, self._hover_zone, self._hover_door)
        if self._hover_item is None and self._hover_door is None:
            self.colored_tooltip = False      # ClearPermanentTooltip
        if self._hit(self.rect('InventoryPreviousRect'), mx, my) \
                and self.displayed_begin > 0:
            self.displayed_begin -= 1
            return True
        if self._hit(self.rect('InventoryNextRect'), mx, my) \
                and self.displayed_begin + self.max_items < len(inv.items):
            self.displayed_begin += 1
            return True
        if self._hit(self.rect('InfoRect'), mx, my):
            return True                    # press-and-hold; nothing on click
        if self._hit(self.rect('SneakRect'), mx, my) and w.woody is not None:
            # Woody.ToggleSneak (Woody.cs:1151): S2 flips the flag only
            w.woody.sneak_toggle = not w.woody.sneak_toggle
            if not w.woody.nfh2:
                w.woody.sneaking = w.woody.sneak_toggle
            return True
        if self._hit(self.rect('PowerRect'), mx, my):
            # Woody.ToggleMenu (HUD.cs:1350-1353); the widgets stay unported,
            # the pause itself runs
            w.toggle_menu()
            return True
        if self._hit(self.rect('CompleteRect'), mx, my) \
                and g.completed >= g.winning:
            # GameInfo.FinishGameOnHUDClick (HUD.cs:1355-1359); Won is
            # already true whenever the button is enabled (TrickDone,
            # GameInfo.cs:477-481)
            w.finish_game_on_hud_click()
            return True
        for key, who in (('WoodyFaceRect', 'Woody'),
                         ('RottweilerFaceRect', 'Rottweiler'),
                         ('MotherFaceRect', 'Mother')):
            if self._hit(self.rect(key), mx, my):
                # HUD.CheckClick's face snaps (HUD.cs:1360-1374) —
                # CameraMover.SnapToPawn interpolates over
                if who != 'Mother' or self.has_mother:
                    w.snap_request = who
                return True
        # any other HUD-bar area: fall through to the world
        return False
