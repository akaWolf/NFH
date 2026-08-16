"""The immediate-mode GUI the menus and the flow screens draw with — the
port of the Helpers/GUI calls the Control*, IntroAnimation, LevelLoader,
Credits and ExitConfirmation classes share:

- `adjust_rect` is Helpers.AdjustRectangle (Helpers.cs:437-440): the four
  components are screen fractions; `adjust_rect_size` is
  AdjustRectangleRelatizeSize (cs:442-445): x/y fractions, w/h design
  pixels; `matrix_rect` is a rect drawn under
  `GUI.matrix = TRS(scale(W/1024, H/768))` (GameIntroAnimation.cs:103,
  LevelDataGUIRenderer.cs:185): its pixels are 1024x768 design pixels.
- `font_size` is LevelDataGUIRenderer.CalculateFontSize (cs:177-183) —
  (W/1024 + H/768) * 10, truncated by the callers' (int) casts.
- `Text.label` is Helpers.DrawLabel -> GUI.Label with a serialized GUIStyle
  (face, alignment, word wrap, clipping, content offset, padding, the
  normal text color) — the same reading hud.py gives the HUD's styles.
- `draw_tex` is GUI.DrawTexture / Graphics.DrawTexture through the
  TextureCache (the whole texture into the rect).

SDL_ttf renders the game's own faces (fonts/<season>/, tools/extract_strings.py);
a system face stands in when they are not extracted.
"""
import ctypes, os

import sdl2
try:
    from sdl2 import sdlttf
except Exception:                       # pragma: no cover — no SDL_ttf
    sdlttf = None

from hud import FONT_CANDIDATES         # the same system fallbacks

DESIGN_W, DESIGN_H = 1024.0, 768.0      # the GUI.matrix design space


def adjust_rect(r, W, H):
    """Helpers.AdjustRectangle: fractions of the screen on all four"""
    if not r:
        return (0.0, 0.0, 0.0, 0.0)
    return (r.get('x', 0.0) * W, r.get('y', 0.0) * H,
            r.get('width', 0.0) * W, r.get('height', 0.0) * H)


def adjust_rect_size(r, W, H, dw=800.0, dh=600.0):
    """Helpers.AdjustRectangleRelatizeSize: x/y fractions, w/h design px"""
    if not r:
        return (0.0, 0.0, 0.0, 0.0)
    return (r.get('x', 0.0) * W, r.get('y', 0.0) * H,
            r.get('width', 0.0) / dw * W, r.get('height', 0.0) / dh * H)


def matrix_rect(r, W, H):
    """a rect under GUI.matrix = scale(W/1024, H/768): design pixels"""
    if not r:
        return (0.0, 0.0, 0.0, 0.0)
    sx, sy = W / DESIGN_W, H / DESIGN_H
    return (r.get('x', 0.0) * sx, r.get('y', 0.0) * sy,
            r.get('width', 0.0) * sx, r.get('height', 0.0) * sy)


def font_size(W, H):
    """LevelDataGUIRenderer.CalculateFontSize(0) before the int cast"""
    return (W / DESIGN_W + H / DESIGN_H) * 10.0


def point_in_rect(x, y, r):
    """Helpers.PointInRect on a top-down rect"""
    return r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]


def draw_tex(rnd, cache, name, r, src=None):
    """GUI.DrawTexture(rect, texture): the whole texture into the rect"""
    if not name or r is None or r[2] <= 0 or r[3] <= 0:
        return False
    entry = cache.get(name)
    if entry is None:
        return False
    dst = sdl2.SDL_Rect(int(round(r[0])), int(round(r[1])),
                        max(1, int(round(r[2]))), max(1, int(round(r[3]))))
    srect = None
    if src is not None:
        srect = sdl2.SDL_Rect(*src)
    sdl2.SDL_RenderCopy(rnd, entry[0], srect, ctypes.byref(dst))
    return True


def draw_tex_uv(rnd, cache, name, r, uv):
    """Graphics.DrawTexture(rect, texture, sourceRect): the normalized
    source window `uv` = (u, v, w, h) stretched over the rect. A width past
    1 (ControlSlider's CalculateFloatRect on the default 10) samples
    outside the texture: the sheet's wrap mode decides — clamp stretches
    the last column over the rest, repeat tiles it (the same reading as
    render.draw_quad's bands)."""
    if not name or r is None or r[2] <= 0 or r[3] <= 0:
        return False
    entry = cache.get(name)
    if entry is None:
        return False
    tex, tw, th = entry[0], entry[1], entry[2]
    u, v, uw, vh = uv
    if uw <= 0 or vh <= 0:
        return False
    x0, y0, w, h = r
    if uw <= 1.0 and u >= 0.0 and u + uw <= 1.0 + 1e-6:
        src = sdl2.SDL_Rect(int(round(u * tw)), int(round(v * th)),
                            max(1, int(round(uw * tw))),
                            max(1, int(round(vh * th))))
        dst = sdl2.SDL_Rect(int(round(x0)), int(round(y0)),
                            max(1, int(round(w))), max(1, int(round(h))))
        sdl2.SDL_RenderCopy(rnd, tex, src, ctypes.byref(dst))
        return True
    # past the texture: one band per texture width
    px_per_u = w / uw
    mode = cache.wrap_mode(name) or 'clamp'
    x = x0
    remaining = uw
    first = True
    while remaining > 1e-6:
        seg = min(1.0, remaining)
        if first or mode == 'repeat':
            src = sdl2.SDL_Rect(0, int(round(v * th)),
                                max(1, int(round(seg * tw))),
                                max(1, int(round(vh * th))))
            dst = sdl2.SDL_Rect(int(round(x)), int(round(y0)),
                                max(1, int(round(seg * px_per_u))),
                                max(1, int(round(h))))
            sdl2.SDL_RenderCopy(rnd, tex, src, ctypes.byref(dst))
            x += seg * px_per_u
            remaining -= seg
            first = False
        else:
            # clamp: the last column stretched over everything left
            src = sdl2.SDL_Rect(tw - 1, int(round(v * th)), 1,
                                max(1, int(round(vh * th))))
            dst = sdl2.SDL_Rect(int(round(x)), int(round(y0)),
                                max(1, int(round(remaining * px_per_u))),
                                max(1, int(round(h))))
            sdl2.SDL_RenderCopy(rnd, tex, src, ctypes.byref(dst))
            break
    return True


class Gfx:
    """the drawing context the menu widgets get (OnGUI's GUI/Graphics
    calls): textures through the cache, labels through `Text`"""

    def __init__(self, rnd, cache, text):
        self.rnd = rnd
        self.cache = cache
        self.text = text

    def tex(self, name, r):
        return draw_tex(self.rnd, self.cache, name, r)

    def tex_uv(self, name, r, uv):
        return draw_tex_uv(self.rnd, self.cache, name, r, uv)

    def label(self, r, s, st, size, scale=(1.0, 1.0), align=None,
              color=None):
        if self.text is not None:
            self.text.label(r, s, st, size, scale=scale, align=align,
                            color=color)

    def calc_width(self, st, size, s):
        return self.text.calc_width(st, size, s) if self.text else 0

    def texture_size(self, name):
        e = self.cache.get(name) if name else None
        return (e[1], e[2]) if e else (0, 0)


def style_color(st, default=(255, 255, 255)):
    """the style's m_Normal text color"""
    if isinstance(st, dict) and 'm_Normal.r' in st:
        return (int(round((st.get('m_Normal.r') or 0.0) * 255)),
                int(round((st.get('m_Normal.g') or 0.0) * 255)),
                int(round((st.get('m_Normal.b') or 0.0) * 255)))
    return default


class Text:
    """fonts by (face, size) and GUI.Label with a serialized GUIStyle"""

    def __init__(self, rnd, font_dir):
        self.rnd = rnd
        self.font_dir = font_dir
        self._fonts = {}
        if sdlttf is not None:
            sdlttf.TTF_Init()

    def font(self, face, size):
        size = max(8, int(size))
        key = (face, size)
        if key in self._fonts:
            return self._fonts[key]
        font = None
        if sdlttf is not None:
            for cand in ((face, face.upper(), face.lower())
                         if face else ()):
                p = os.path.join(self.font_dir, cand + '.ttf')
                if os.path.exists(p):
                    font = sdlttf.TTF_OpenFont(p.encode(), size)
                    break
            if font is None:
                for p in FONT_CANDIDATES:
                    if os.path.exists(p):
                        font = sdlttf.TTF_OpenFont(p.encode(), size)
                        break
        self._fonts[key] = font
        return font

    def style_font(self, st, size):
        face = ((st or {}).get('m_Font') or {}).get('font') \
            if isinstance((st or {}).get('m_Font'), dict) else None
        return self.font(face or '', size)

    def measure(self, font, s):
        if font is None or sdlttf is None:
            return 0
        w = ctypes.c_int(0); h = ctypes.c_int(0)
        sdlttf.TTF_SizeUTF8(font, s.encode(), ctypes.byref(w),
                            ctypes.byref(h))
        return w.value

    def calc_width(self, st, size, s):
        """GUIStyle.CalcSize(content).x"""
        return self.measure(self.style_font(st, size), s)

    def label(self, r, s, st, size, scale=(1.0, 1.0), align=None,
              color=None):
        """Helpers.DrawLabel -> GUI.Label(rect, text, style): the style's
        TextAnchor (0-2 top, 3-5 middle, 6-8 bottom rows; left/center/right
        columns), m_WordWrap, m_TextClipping, m_ContentOffset and m_Padding,
        the normal color. `scale` is the GUI.matrix scale the padding and
        offset pixels go through (the rect is already scaled)."""
        if not s or r is None or sdlttf is None:
            return
        font = self.style_font(st, size)
        if font is None:
            return
        st = st or {}
        offx = (st.get('m_ContentOffset.x', 0.0) or 0.0) * scale[0]
        offy = (st.get('m_ContentOffset.y', 0.0) or 0.0) * scale[1]
        pl = (st.get('m_Padding.left', 0) or 0) * scale[0]
        pr = (st.get('m_Padding.right', 0) or 0) * scale[0]
        pt = (st.get('m_Padding.top', 0) or 0) * scale[1]
        pb = (st.get('m_Padding.bottom', 0) or 0) * scale[1]
        r = (r[0] + offx + pl, r[1] + offy + pt, r[2] - pl - pr,
             r[3] - pt - pb)
        clip = st.get('m_TextClipping') == 1
        if clip and (r[2] <= 0 or r[3] <= 0):
            return                        # TextClipping.Clip on an empty
                                          # rect draws nothing (the tip
                                          # strings ride zero TextRects)
        if align is None:
            align = st.get('m_Alignment') or 0
        if st.get('m_WordWrap') and r[2] > 0:
            wrapped = []
            for line in s.split('\n'):
                cur = ''
                for word in line.split(' '):
                    cand = (cur + ' ' + word).strip()
                    if cur and self.measure(font, cand) > r[2]:
                        wrapped.append(cur)
                        cur = word
                    else:
                        cur = cand
                wrapped.append(cur)
            s = '\n'.join(wrapped)
        if clip and r[2] > 0 and r[3] > 0:
            cr = sdl2.SDL_Rect(int(r[0]), int(r[1]),
                               max(1, int(r[2])), max(1, int(r[3])))
            sdl2.SDL_RenderSetClipRect(self.rnd, ctypes.byref(cr))
        col = sdl2.SDL_Color(*(color or style_color(st)))
        rendered = []
        for line in s.split('\n'):
            surf = sdlttf.TTF_RenderUTF8_Blended(font, line.encode(), col)
            if not surf:
                continue
            tex = sdl2.SDL_CreateTextureFromSurface(self.rnd, surf)
            rendered.append((tex, surf.contents.w, surf.contents.h))
            sdl2.SDL_FreeSurface(surf)
        total_h = sum(h for _, _, h in rendered)
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
