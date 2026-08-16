"""SDL2 renderer reproducing the game's screen-space blitting model.

The game never used Unity's renderer for sprites: each actor blits a frame of
its sheet in screen space, ordered by an explicit depth enum. This mirrors that
— see docs/GAMEPLAY.md §8.
"""
import ctypes, os

import sdl2

from scene import DESIGN_H

# the levels' camera: orthographic, size 3, so 6 world units fill the height
ORTHO_SIZE = 3.0


class Camera:
    """the level camera as the port models it: an orthographic Camera.main
    (the scene's Camera component — orthographic, size 3 in every level,
    exported into Level.camera_size) at a world x/y; the methods below are
    its WorldToScreenPoint / ScreenToWorldPoint"""

    def __init__(self, x=0.0, y=0.0, size=ORTHO_SIZE):
        self.x = x; self.y = y; self.size = size

    def world_to_screen(self, wx, wy, w, h):
        """world point -> GUI pixel coords (y down), matching Unity's
        Camera.WorldToScreenPoint followed by `Screen.height - y`."""
        aspect = w / float(h)
        sx = (wx - self.x) / (self.size * aspect) * (w * 0.5) + w * 0.5
        sy = (wy - self.y) / self.size * (h * 0.5) + h * 0.5
        return sx, h - sy

    def screen_to_world(self, sx, sy, w, h):
        aspect = w / float(h)
        wx = (sx - w * 0.5) / (w * 0.5) * (self.size * aspect) + self.x
        wy = ((h - sy) - h * 0.5) / (h * 0.5) * self.size + self.y
        return wx, wy

    def world_rect_to_screen(self, cx, cy, ww, wh, w, h):
        x0, y0 = self.world_to_screen(cx - ww * 0.5, cy + wh * 0.5, w, h)
        x1, y1 = self.world_to_screen(cx + ww * 0.5, cy - wh * 0.5, w, h)
        return x0, y0, x1 - x0, y1 - y0


class TextureCache:
    """PNG sheets, loaded on demand. Uses PIL for the PNG decode; the extraction
    tools themselves stay dependency-free."""

    def __init__(self, renderer, directories):
        self.r = renderer
        self.dirs = [d for d in directories if d and os.path.isdir(d)]
        self._cache = {}
        self._missing = set()
        self._wrap = {}                  # resolved name -> 'repeat'|'clamp'
        # Resources.Load is case-insensitive; the data says O_workout for a
        # sheet shipped as O_Workout
        self._lower = {}
        # each directory's wrap.json (tools/extract_textures.py): the PNG's
        # Texture2D.m_TextureSettings.m_WrapMode, keyed by the PNG name
        self._wrap_index = {}
        for d in self.dirs:
            for fn in os.listdir(d):
                if fn.endswith('.png'):
                    self._lower.setdefault(fn[:-4].lower(), os.path.join(d, fn))
            wj = os.path.join(d, 'wrap.json')
            if os.path.exists(wj):
                try:
                    import json
                    self._wrap_index[d] = json.load(open(wj))
                except Exception:
                    pass

    def wrap_mode(self, name):
        """the sampler wrap mode of the sheet a name resolves to — 'repeat',
        'clamp', or None when the extraction carries no wrap.json for it
        (Graphics.DrawTexture applies it to a source rect outside [0,1])"""
        if name not in self._cache and self.get(name) is None:
            return None
        return self._wrap.get(name)

    def get(self, name):
        if name in self._cache:
            return self._cache[name]
        if name in self._missing:
            return None
        # Sheet names are Resources.Load paths, so some carry a subdirectory
        # ("Closed/closeddoorback_ms"); extraction flattened those to a file
        # name, sanitising the separator.
        import re
        candidates = [name, name.replace('/', '_'), os.path.basename(name),
                      re.sub(r'[^A-Za-z0-9_.-]', '_', name)]
        path = None
        # each candidate tries exact case then the case-insensitive table
        # before the NEXT candidate — a full path must win over its base
        # name, or the colliding flat faces shadow the path-extracted ones
        for cand in candidates:
            for d in self.dirs:
                p = os.path.join(d, cand + '.png')
                if os.path.exists(p):
                    path = p; break
            if path is None:
                path = self._lower.get(cand.lower())
            if path:
                break
        if path is None:
            self._missing.add(name)
            return None
        idx = self._wrap_index.get(os.path.dirname(path))
        if idx is not None:
            mode = idx.get(os.path.basename(path)[:-4])
            if mode is not None:
                self._wrap[name] = mode
        from PIL import Image
        img = Image.open(path).convert('RGBA')
        w, h = img.size
        raw = img.tobytes()
        buf = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        surf = sdl2.SDL_CreateRGBSurfaceFrom(
            buf, w, h, 32, w * 4,
            0x000000ff, 0x0000ff00, 0x00ff0000, 0xff000000)
        tex = sdl2.SDL_CreateTextureFromSurface(self.r, surf)
        sdl2.SDL_FreeSurface(surf)
        sdl2.SDL_SetTextureBlendMode(tex, sdl2.SDL_BLENDMODE_BLEND)
        self._cache[name] = (tex, w, h, buf)
        return self._cache[name]

    @property
    def missing(self):
        """diagnostic: the sheet names no directory resolved (the viewer's
        end-of-run report; the original logs 'could not load' instead —
        AnimationInstance.cs:137-140)"""
        return sorted(self._missing)


def draw_sprite(rnd, cache, cam, sprite, anim, t, w, h):
    """One blit, following AnimationControllerBase.DrawAnimation."""
    # OnGUI (AnimationControllerBase.cs:177-188): nothing while Hidden, and
    # nothing for a controller with no CurrentAnimation (sprite.current None)
    if getattr(sprite, 'hidden', False) or sprite.current is None or anim is None:
        return False
    # sheet None: Resources.Load found no texture for the animation's path
    # (AnimationInstance.LoadTexture, cs:136-140); OnGUI still Refreshes it
    # (AnimationControllerBase.cs:179-186), DrawTexture just has nothing
    entry = cache.get(anim.sheet) if anim.sheet else None
    if entry is None or not anim.ow or not anim.oh:
        return False
    tex, tw, th, _ = entry
    scale = h / DESIGN_H                      # everything is sized off 800x600
    sheet_w = anim.ow * scale
    sheet_h = anim.oh * scale
    fw = sheet_w / anim.cols
    fh = sheet_h / anim.rows

    sx, sy = cam.world_to_screen(sprite.x, sprite.y, w, h)
    dx = sx + (sprite.ctrl_dx + anim.dx) * scale
    dy = sy + (sprite.ctrl_dy + anim.dy) * scale

    # frame is owned by the AnimPlayer (AnimationControllerBase.Refresh);
    # frame_at(t) only serves sprites nothing is ticking
    frame = sprite.cur_frame if sprite.cur_frame is not None else anim.frame_at(t)
    col = frame % anim.cols
    row = frame // anim.cols
    src_y = int(round(row * th / anim.rows))
    src_h = max(1, int(round(th / anim.rows)))
    if row >= anim.rows:
        # DrawAnimation (AnimationControllerBase.cs:153-170) never checks
        # CurrentFrame against the sheet: a single that ended with nothing
        # set after it keeps advancing (Refresh, cs:102-141: AdvanceFrame,
        # ReachedEndFrame, StopSingleAnimation finds no follow-up), so the
        # source rect's y = 1 - (row+1)/rows drops below 0 and
        # Graphics.DrawTexture samples by the TEXTURE's wrap mode
        # (Texture2D.m_TextureSettings.m_WrapMode, tools/extract_textures.py's
        # wrap.json): Repeat wraps V modulo 1 — the row wraps onto the sheet;
        # Clamp pins V to 0 — the texture's bottom edge (the LAST PNG row,
        # the extraction flips Unity's bottom-up rows) stretched over the
        # cell. Without a wrap index nothing is drawn, as before.
        mode = cache.wrap_mode(anim.sheet)
        if mode == 'repeat':
            row %= anim.rows
            src_y = int(round(row * th / anim.rows))
        elif mode == 'clamp':
            src_y, src_h = th - 1, 1
        else:
            return False
    src = sdl2.SDL_Rect(int(round(col * tw / anim.cols)), src_y,
                        max(1, int(round(tw / anim.cols))), src_h)
    dst = sdl2.SDL_Rect(int(round(dx)), int(round(dy)),
                        max(1, int(round(fw))), max(1, int(round(fh))))
    sdl2.SDL_RenderCopy(rnd, tex, ctypes.byref(src), ctypes.byref(dst))
    return True


def draw_quad(rnd, cache, cam, q, w, h):
    """A world-space textured Plane — the backdrop and the static item overlays.
    These go through Unity's normal renderer, so they draw beneath every
    sprite. Renderer.m_Enabled gates the draw: the tricked overlays ship with
    it off and SetTrickedObjectHidden flips it at runtime."""
    if not q.get('active') or not q.get('renderer_enabled', True):
        return False
    entry = cache.get(q['texture'])
    if entry is None:
        return False
    rx, ry, rw, rh = cam.world_rect_to_screen(q['x'], q['y'], q['w'], q['h'], w, h)
    dst = sdl2.SDL_Rect(int(round(rx)), int(round(ry)),
                        max(1, int(round(rw))), max(1, int(round(rh))))
    # the material's _MainTex_ST: the Plane's 0..1 UVs sample
    # uv * scale + offset (V from the bottom) — the source window of the
    # texture; the exporter emits it as 'uv' [sx, sy, ox, oy], identity
    # when the material has no tiling (L101's Binoculars quad shows the
    # (0.625..0.70, 0.34..0.52) window of a 256x256 sheet)
    uv = q.get('uv')
    if not uv or (abs(uv[0] - 1.0) < 1e-6 and abs(uv[1] - 1.0) < 1e-6
                  and abs(uv[2]) < 1e-6 and abs(uv[3]) < 1e-6):
        sdl2.SDL_RenderCopy(rnd, entry[0], None, ctypes.byref(dst))
        return True
    tw, th = entry[1], entry[2]
    sx, sy, ox, oy = uv
    # the window may leave the texture (L102's Beer 1.2x1.5 from 0, the
    # MumSmeared 1x2.5 from v=-0.9 — all six such quads sample Clamp
    # textures): outside [0,1] a Clamp texture repeats its edge row/column,
    # so the quad is up to 3x3 bands — the interior window plus stretched
    # 1-pixel edges. Each axis: the dst span covering u in [0,1] is
    # rx + rw*(0-ox)/sx .. rx + rw*(1-ox)/sx (V flipped: v=1 is the top).
    def bands(r0, rlen, o, sc, tlen, flip):
        # -> list of (dst_start, dst_len, src_start, src_len) along one axis
        out = []
        if sc <= 0:
            return out
        lo, hi = o, o + sc                     # the uv span the quad covers
        edge0 = (0.0 - lo) / sc                # fraction of the quad below u=0
        edge1 = (1.0 - lo) / sc                # fraction below u=1
        a = max(0.0, min(1.0, edge0))
        b = max(0.0, min(1.0, edge1))
        segs = [(0.0, a, 'lo'), (a, b, 'in'), (b, 1.0, 'hi')]
        for f0, f1, kind in segs:
            if f1 - f0 <= 1e-9:
                continue
            d0 = int(round(r0 + rlen * f0)); d1 = int(round(r0 + rlen * f1))
            if d1 <= d0:
                continue
            if kind == 'in':
                u0 = max(0.0, lo + sc * f0); u1 = min(1.0, lo + sc * f1)
                if flip:
                    s0 = int(round((1.0 - u1) * tlen)); s1 = int(round((1.0 - u0) * tlen))
                else:
                    s0 = int(round(u0 * tlen)); s1 = int(round(u1 * tlen))
                out.append((d0, d1 - d0, s0, max(1, s1 - s0)))
            else:
                # below u=0 samples the u=0 edge, above u=1 the u=1 edge
                # (flipped for V: v=0 is the last pixel row)
                at_zero = (kind == 'lo')
                if flip:
                    src0 = tlen - 1 if at_zero else 0
                else:
                    src0 = 0 if at_zero else tlen - 1
                out.append((d0, d1 - d0, src0, 1))
        return out
    for dx0, dw0, sx0, sw0 in bands(rx, rw, ox, sx, tw, False):
        for dy0, dh0, sy0, sh0 in bands(ry, rh, oy, sy, th, True):
            src = sdl2.SDL_Rect(sx0, sy0, sw0, sh0)
            d = sdl2.SDL_Rect(dx0, dy0, max(1, dw0), max(1, dh0))
            sdl2.SDL_RenderCopy(rnd, entry[0], ctypes.byref(src), ctypes.byref(d))
    return True


def draw_fence(rnd, cache, cam, f, w, h):
    """Level.OnGUI (Level.cs:322-341): a fence texture at the projected world
    position, sized by its serialized rect. LoadFenceSize (cs:244-252) forces
    the width to (H/W)*1.75/0.75 screen fractions unless IgnoreFenceSize;
    Helpers.AdjustRectangle turns the fractions into pixels."""
    entry = cache.get(f['texture'])
    if entry is None:
        return False
    sx, sy = cam.world_to_screen(f['x'], f['y'], w, h)
    fw = f['w'] if f['ignore_size'] else (h / float(w)) * 1.75 / 0.75
    dst = sdl2.SDL_Rect(int(round(sx)), int(round(sy)),
                        max(1, int(round(fw * w))),
                        max(1, int(round(f['h'] * h))))
    sdl2.SDL_RenderCopy(rnd, entry[0], None, ctypes.byref(dst))
    return True


def draw_item_tip(rnd, cache, cam, it, w, h):
    """Item.OnGUI (Item.cs:2740-2760): the interaction icon over the item
    while the HUD info button is held. Width scales by W/800, height by
    H/600 (the original's per-axis WidthRatio/HeightRatio), centred on x and
    sitting on top of the projected position."""
    entry = cache.get(it.tip_icon)
    if entry is None:
        return False
    tex, tw, th = entry[0], entry[1], entry[2]
    wr = w / 800.0
    hr = h / 600.0
    iw = tw * it.tip_dimensions * wr
    ih = th * it.tip_dimensions * hr
    sx, sy = cam.world_to_screen(it.x, it.y, w, h)
    dst = sdl2.SDL_Rect(int(round(sx + it.tip_delta[0] * wr - iw / 2.0)),
                        int(round(sy - it.tip_delta[1] * hr - ih)),
                        max(1, int(round(iw))), max(1, int(round(ih))))
    sdl2.SDL_RenderCopy(rnd, tex, None, ctypes.byref(dst))
    return True


def draw_zone_overlay(rnd, cam, zones, w, h):
    """viewer debug overlay (the Z key): the zone boxes tinted, exits amber
    — instrumentation, no game rule behind it"""
    sdl2.SDL_SetRenderDrawBlendMode(rnd, sdl2.SDL_BLENDMODE_BLEND)
    for z in zones:
        rx, ry, rw, rh = cam.world_rect_to_screen(z.x, z.y, z.w, z.h, w, h)
        r = sdl2.SDL_Rect(int(rx), int(ry), int(rw), int(rh))
        if z.exit:
            sdl2.SDL_SetRenderDrawColor(rnd, 255, 200, 40, 60)
        else:
            sdl2.SDL_SetRenderDrawColor(rnd, 40, 220, 255, 40)
        sdl2.SDL_RenderFillRect(rnd, ctypes.byref(r))
        sdl2.SDL_SetRenderDrawColor(rnd, 255, 255, 255, 160)
        sdl2.SDL_RenderDrawRect(rnd, ctypes.byref(r))
