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
    def __init__(self, x=0.0, y=0.0, size=ORTHO_SIZE):
        self.x = x; self.y = y; self.size = size

    def world_to_screen(self, wx, wy, w, h):
        """world point -> GUI pixel coords (y down), matching Unity's
        Camera.WorldToScreenPoint followed by `Screen.height - y`."""
        aspect = w / float(h)
        sx = (wx - self.x) / (self.size * aspect) * (w * 0.5) + w * 0.5
        sy = (wy - self.y) / self.size * (h * 0.5) + h * 0.5
        return sx, h - sy

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
        for cand in candidates:
            for d in self.dirs:
                p = os.path.join(d, cand + '.png')
                if os.path.exists(p):
                    path = p; break
            if path:
                break
        if path is None:
            self._missing.add(name)
            return None
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
        return sorted(self._missing)


def draw_sprite(rnd, cache, cam, sprite, anim, t, w, h):
    """One blit, following AnimationControllerBase.DrawAnimation."""
    entry = cache.get(anim.sheet)
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

    frame = anim.frame_at(t)
    col = frame % anim.cols
    row = frame // anim.cols
    if row >= anim.rows:
        return False
    src = sdl2.SDL_Rect(int(round(col * tw / anim.cols)),
                        int(round(row * th / anim.rows)),
                        max(1, int(round(tw / anim.cols))),
                        max(1, int(round(th / anim.rows))))
    dst = sdl2.SDL_Rect(int(round(dx)), int(round(dy)),
                        max(1, int(round(fw))), max(1, int(round(fh))))
    sdl2.SDL_RenderCopy(rnd, tex, ctypes.byref(src), ctypes.byref(dst))
    return True


def draw_quad(rnd, cache, cam, q, w, h):
    """A world-space textured Plane — the backdrop and the static item overlays.
    These go through Unity's normal renderer, so they draw beneath every sprite."""
    if not q.get('active'):
        return False
    entry = cache.get(q['texture'])
    if entry is None:
        return False
    rx, ry, rw, rh = cam.world_rect_to_screen(q['x'], q['y'], q['w'], q['h'], w, h)
    dst = sdl2.SDL_Rect(int(round(rx)), int(round(ry)),
                        max(1, int(round(rw))), max(1, int(round(rh))))
    sdl2.SDL_RenderCopy(rnd, entry[0], None, ctypes.byref(dst))
    return True


def draw_zone_overlay(rnd, cam, zones, w, h):
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
