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


def load_strings(level_path):
    """LocalizationManager.LoadLocalizationFile: 'KEY<>VALUE' lines from
    Localization/Final/<language>; ';' comments. tools/extract_strings.py
    puts the extracted files under strings/{s1,s2}/."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    season = 's2' if '/s2/' in level_path.replace('\\', '/') else 's1'
    out = {}
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
    def __init__(self, level, world, cache, renderer, width, height):
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
        # PlayRottweilerIdle / PlayWoodyIdle at Start; idles loop
        self.woody_active = self.woody_idle
        self.rott_active = self.rott_idle
        self.mother_active = self.mother_idle
        for a in (self.woody_idle, self.rott_idle, self.mother_idle,
                  self.rott_sleep, self.mother_sleep, self.rott_blind,
                  self.mother_blind, self.whistle_anim, self.statue_anim):
            a.restart()
        self.displayed_begin = 0          # DisplayedItemsBegin
        self.max_items = d.get('MaxInventoryItemsDisplayed') or 5
        self.tooltip = None               # SetTooltip's UseWith line
        self.hover_started = None         # inventory hover bubble timer
        self.hover_index = None
        self.mouse = (0, 0)
        self._angry_state = 'idle'
        self._mother_state = 'idle'
        self.cam = None                   # set by the viewer for the bars
        self.cursor_tex = None            # MouseCursor.CurrentTexture
        self._tricks_rects = None
        self._angry_count_rect = None
        self._statue_rect = None
        self.strings = load_strings(level.path)
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
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            season = 's2' if '/s2/' in level.path.replace('\\', '/') else 's1'
            self._font_dir = os.path.join(root, 'fonts', season)
            self._font = self._style_font('TimeStyle') or \
                self._sys_font(17)
            self._font_small = self._style_font('TooltipStyle') or \
                self._sys_font(13)

    def _sys_font(self, design_size):
        for p in FONT_CANDIDATES:
            if os.path.exists(p):
                return sdlttf.TTF_OpenFont(
                    p.encode(), max(8, int(design_size * self.H / 600.0)))
        return None

    def _style_font(self, style_key):
        """open the GUIStyle's serialized face at its baked size"""
        st = self.d.get(style_key) or {}
        name = (st.get('m_Font') or {}).get('font') if \
            isinstance(st.get('m_Font'), dict) else None
        if not name:
            return None
        if name in self._fonts:
            return self._fonts[name]
        m = re.search(r'(\d+)$', name)
        size = int(m.group(1)) if m else 16
        font = None
        for cand in (name, name.upper(), name.lower()):
            p = os.path.join(self._font_dir, cand + '.ttf')
            if os.path.exists(p):
                font = sdlttf.TTF_OpenFont(
                    p.encode(), max(8, int(size * self.H / 600.0)))
                break
        self._fonts[name] = font
        return font

    def loc(self, key):
        """LocalizationManager.GetString: empty when unknown"""
        if not key:
            return ''
        return self.strings.get(key, key)

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
        if isinstance(ref, dict):
            ref = ref.get('texture')
        if not ref:
            return None
        return self.cache.get(ref)

    def _blit(self, ref, r, src=None):
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

    def _text(self, s, r, small=False, center=True, color=(255, 255, 255),
              align=None):
        """GUI.Label/TextArea honor the style's TextAnchor (m_Alignment):
        0-2 top, 3-5 middle, 6-8 bottom rows; left/center/right columns.
        `align` overrides the legacy `center` flag when given."""
        font = self._font_small if small else self._font
        if font is None or not s or r is None:
            return
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

    # -- state hooks (HUD.Play*) ------------------------------------------
    def _get_name_string(self, it):
        """Item.GetNameString (Item.cs:2295-2314)"""
        if it.name == 'ValveMain':
            return it.name_string if it.main_valve_open \
                else it.name_tricked_string
        if it.tricked:
            return it.name_tricked_string
        if it.primed:
            return it.name_primed_string
        return it.name_string

    def _get_with_string(self, it):
        """Item.GetWithString (Item.cs:2316-2327)"""
        if it.tricked:
            return it.with_tricked_string
        if it.primed:
            return it.with_primed_string
        return it.with_string

    def update_hover(self, item, zone):
        """MouseCursor.UpdateMouseOver (MouseCursor.cs): the permanent
        tooltip under the cursor. SetTooltip's GoTo state renders empty
        (HUD.cs:1049-1051), so the go-to arms clear it."""
        w = self.world
        ws = self.woody_strings
        inv = w.inventory
        loc = self.loc
        if inv.used is not None:
            tail = loc(self._get_with_string(item)) if item is not None \
                else ws['empty_use']
            self.tooltip = ws['use'] + (inv.used.get('name') or '') \
                + ws['with'] + tail
            return
        if item is None:
            self.tooltip = None
            return
        woody_zone = w.woody.zone.pid if w.woody and w.woody.zone else None
        if item.kind in ('TrickItem', 'Drawing', 'Rake', 'Toilet',
                         'Television'):
            if item.is_floor:
                self.tooltip = None                     # GoTo renders empty
            elif item.required_inventory in (None, '', 'IT_NONE') \
                    and item.tricked \
                    and not item.dont_change_tooltip_when_tricked:
                self.tooltip = ws['look_at'] + loc(self._get_name_string(item))
                self._swap_cursor_icon(item, item.mouse_over_after_trick)
            elif item.required_inventory in (None, '', 'IT_NONE') \
                    and not item.tricked \
                    and item.dont_change_tooltip_when_tricked:
                self.tooltip = ws['use'] + loc(self._get_name_string(item))
            elif item.dont_change_tooltip_when_tricked and item.tricked:
                self.tooltip = ws['use'] + loc(self._get_name_string(item))
            elif item.change_tooltip_when_tricked:
                self.tooltip = ws['use'] + loc(self._get_name_string(item))
            else:
                self.tooltip = ws['look_at'] + loc(self._get_name_string(item))
                self._swap_cursor_icon(item, item.mouse_over_after_trick)
        elif item.kind == 'HideItem':
            self.tooltip = ws['hide'] + loc(item.hide_string_key)
        elif item.kind == 'SearchItem':
            if item.searching_item:
                if item.locked:
                    self.tooltip = ws['look_at'] + loc(item.name_string)
                elif item.primed:
                    self.tooltip = ws['open'] + loc(item.name_primed_string)
                elif item.require_priming:
                    self.tooltip = ws['look_at'] + loc(item.name_string)
                else:
                    self.tooltip = ws['examine'] + loc(item.name_string)
            else:
                self.tooltip = ws['examine'] + loc(item.name_string)
        elif item.kind == 'GroundItem':
            self.tooltip = ws['look_at'] + loc(item.name_string)
        elif item.kind == 'InspectItem':
            changer = self.level.items.get(item.item_that_changes_tooltip) \
                if item.item_that_changes_tooltip else None
            if changer is None or not changer.got_tricked:
                self.tooltip = ws['look_at'] + loc(item.name_string)
            else:
                self.tooltip = ws['look_at'] + loc(item.name_primed_string)
        else:
            self.tooltip = None

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
        if inv.used is not None:
            self.cursor_tex = mc['use_inv'] if (item is not None
                                                or door is not None) \
                else mc['cancel_inv']
            return
        woody_zone = woody.zone.pid if woody.zone else None
        cand = item if item is not None else door
        cand_icon = cand.mouse_over_icon if cand is not None else None
        cand_use = getattr(cand, 'can_use', True) if cand is not None else False
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

    def _icon_names(self, entry):
        """Inventory.Initialize's icon paths (Inventory.cs:110-124)"""
        t = entry.get('type') or ''
        if t.startswith('IT2_'):
            base = 'inventory2/' + t[4:].lower()
            return base + '_hovered', base + '_std', base + '_down'
        base = 'inventory/I_' + (t[3:] if t.startswith('IT_') else t).lower()
        return base + '_hov', base + '_norm', base + '_pres'

    # -- drawing -----------------------------------------------------------
    def draw(self, dt, mouse):
        self.mouse = mouse
        w = self.world
        g = w.game
        self._draw_dexterity()
        self._draw_base()
        self._draw_inventory(dt)
        if self.tooltip:
            self._text(self.tooltip, self.rect('TooltipRect'), small=True,
                       align=self._align('TooltipStyle', 3))
        self._draw_buttons()
        self._draw_angry_meter(dt)
        if not g.is_tutorial:
            self._draw_tricks(dt)
            self._draw_time()
        self._draw_characters(dt)
        self._draw_progress_bars()
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

    def _draw_inventory(self, dt):
        """DrawNavigationArrows + DrawInventory: icons in norm/hov/pres state,
        the UseWith tooltip on the selection, hover bubbles after 1 s"""
        inv = self.world.inventory
        items = inv.items
        rects = self._inventory_rects()
        mx, my = self.mouse
        if self.displayed_begin > max(0, len(items) - len(rects)):
            self.displayed_begin = max(0, len(items) - len(rects))
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
            if inv.used is entry:
                self._blit(pres, r)
                # SetTooltip(UseWith): UseString + name + WithString + target
                self.tooltip = (self.woody_strings['use']
                                + self.loc(entry.get('name') or '')
                                + self.woody_strings['with']
                                + self.woody_strings['empty_use'])
            elif self._hit(r, mx, my) and not self.world.game.ending:
                self._blit(hov, r)
            else:
                self._blit(norm, r)
            if self._hit(r, mx, my) and not self.world.game.ending:
                hover_any = True
                if self.hover_index != k:
                    self.hover_index = k
                    self.hover_started = 0.0
                else:
                    self.hover_started = (self.hover_started or 0.0) + dt
                    if self.hover_started > (self.d.get(
                            'InventoryTooltipHoverInterval') or 1.0):
                        br = self.rect('TextBubbleRect')
                        if br is not None:
                            div = 4.0 if i == 0 else 2.5
                            bubble = (r[0] - br[2] / div, r[1] - br[3],
                                      br[2], br[3])
                            self._blit(self.d.get('TextBubbleTexture'), bubble)
                            self._text(self.loc(entry.get('desc') or
                                                entry.get('name') or ''),
                                       bubble, small=True,
                                       color=(40, 40, 40),
                                       align=self._align('DescriptionStyle', 4))
        if not hover_any:
            self.hover_index = None
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
            button(inf, self.rect('InfoRect'))

    def _draw_angry_meter(self, dt):
        """DrawAngryMeter: the full strip is clipped from the bottom by the
        meter percentage, plus the whistle idle animation"""
        rott = self.world.pawns.get('Rottweiler')
        if rott is None:
            return
        self._blit(self.d.get('AngryMeterEmpty'), self.rect('AngryMeterEmptyRect'))
        pct = max(0.0, min(100.0, rott.angry_meter)) / 100.0
        full = self.rect('AngryMeterFullRect')
        entry = self._tex(self.d.get('AngryMeterFull'))
        if pct > 0.0 and full is not None and entry is not None:
            tex, tw, th = entry[0], entry[1], entry[2]
            dst = sdl2.SDL_Rect(int(full[0]),
                                int(full[1] + full[3] * (1.0 - pct)),
                                int(full[2]), int(full[3] * pct))
            src = sdl2.SDL_Rect(0, int(th * (1.0 - pct)), tw, int(th * pct))
            sdl2.SDL_RenderCopy(self.rnd, tex, src, dst)
        self.whistle_anim.update(dt)
        if self.whistle:
            i = min(self.whistle_anim.frame, len(self.whistle) - 1)
            self._blit(WHISTLE_BASE + self.whistle[i], self.rect('WhistleRect'))

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
                   align=self._align('TimeShadowStyle', 4))
        self._text(s, self.rect('TimeRect'),
                   align=self._align('TimeStyle', 4))

    def _draw_characters(self, dt):
        """DrawCharacters: the face strips and the think bubbles with the
        current action's item icon (RoutineAction.BubbleIcon)"""
        rott = self.world.pawns.get('Rottweiler')
        # face-state selection (HUD.PlayRottweiler*); a ProgressBar's
        # SetSleeping picks the blind strip over sleep
        # (ProgressBar.cs:183-192)
        if rott is not None:
            state = ('blind' if rott.hud_blind else 'sleep') \
                if rott.is_sleeping else \
                ('angry' if not rott.can_decrease_angry else 'idle')
            if state != self._angry_state:
                self._angry_state = state
                if state == 'sleep':
                    self.rott_active = self.rott_sleep
                elif state == 'blind':
                    self.rott_active = self.rott_blind
                elif state == 'angry':
                    self.rott_active = self.rott_angry[
                        min(2, rott.angry_count_ticks)]
                else:
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
            # Helpers.DrawLabel with the bar's DataStyle (m_Alignment 4)
            self._text('%d%%' % int(round(p * 100)), (x, y, w, h), small=True,
                       align=4)

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
                   align=self._align('TimeStyle', 4))

    def _draw_score(self):
        """DrawScore (game over, Classic): the board, the ratings, the
        restart / ok buttons"""
        g = self.world.game
        mx, my = self.mouse
        self._blit(self.d.get('OriginalScoreboard'), self.rect('OriginalScoreRect'))
        # the three TextFields: Rating, "GO_TRICKS\nC / T", "GO_VIEWER_RATING\nN%"
        self._text(self.loc(RATING_KEYS.get(g.rating, g.rating)),
                   self.rect('RatingRatioRect'),
                   align=self._align('RatingStyle', 4))
        self._text(self.loc('GO_TRICKS') + '\n' + g.trick_ratio,
                   self.rect('TrickRatioRect'),
                   align=self._align('ScoreStyle', 4))
        self._text(self.loc('GO_VIEWER_RATING') + '\n' + g.viewer_rating,
                   self.rect('ViewerRatingRect'),
                   align=self._align('ScoreStyle', 4))
        for rk, mk, key in (('RestartButtonRect', 'RestartMessageRect',
                             'RESTART_MESSAGE'),
                            ('OkButtonRect', 'OkMessageRect', 'OK_MESSAGE')):
            r = self.rect(rk)
            hover = self._hit(r, mx, my)
            self._blit(self.d.get('ScoreButtonHover' if hover else 'ScoreButton'), r)
            self._text(self.loc(key), self.rect(mk), small=True,
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
                    return True        # level selection is not modelled
            return True if self._hit(self.rect('PowerRect'), mx, my) else False
        rects = self._inventory_rects()
        for i, r in enumerate(rects):
            k = i + self.displayed_begin
            if k >= len(inv.items):
                break
            if self._hit(r, mx, my) and inv.used is not inv.items[k]:
                # the held item's OnIconPressed gates the selection — the
                # phone icons raise the alarm instead (HUD.cs:944)
                if w.icon_pressed(inv.items[k]):
                    inv.used = inv.items[k]      # SetCurrentInventory
                return True
        if self._hit(self.rect('InventoryPreviousRect'), mx, my) \
                and self.displayed_begin > 0:
            self.displayed_begin -= 1
            return True
        if self._hit(self.rect('InventoryNextRect'), mx, my) \
                and self.displayed_begin + self.max_items < len(inv.items):
            self.displayed_begin += 1
            return True
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
            # GameInfo.FinishGameOnHUDClick with Won kept true
            g.won = True
            g.ending = True
            g.ended = True
            w._score()
            for r in w.routines:
                r.frozen = True
            return True
        for key in ('WoodyFaceRect', 'RottweilerFaceRect', 'MotherFaceRect'):
            if self._hit(self.rect(key), mx, my):
                return True            # camera snaps are the viewer's follow
        # any other HUD-bar area: fall through to the world
        return False
