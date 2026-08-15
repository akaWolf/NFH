"""Texture2D reading and decoding for Unity 5.3 builds.

Uncompressed formats decode with the standard library alone. ETC1/ETC2 need
numpy — the block decode is vectorised, since the game ships ~40 Mpx of it.

PNG is written directly with zlib rather than pulling in an imaging library.
"""
import os, struct, zlib

# UnityEngine.TextureFormat
ALPHA8, ARGB4444, RGB24, RGBA32, ARGB32 = 1, 2, 3, 4, 5
RGB565, R16, DXT1, DXT5, RGBA4444, BGRA32 = 7, 9, 10, 12, 13, 14
ETC_RGB4, ETC2_RGB, ETC2_RGBA1, ETC2_RGBA8 = 34, 45, 46, 47

FORMAT_NAMES = {
    ALPHA8: 'Alpha8', ARGB4444: 'ARGB4444', RGB24: 'RGB24', RGBA32: 'RGBA32',
    ARGB32: 'ARGB32', RGB565: 'RGB565', R16: 'R16', DXT1: 'DXT1', DXT5: 'DXT5',
    RGBA4444: 'RGBA4444', BGRA32: 'BGRA32', ETC_RGB4: 'ETC_RGB4',
    ETC2_RGB: 'ETC2_RGB', ETC2_RGBA1: 'ETC2_RGBA1', ETC2_RGBA8: 'ETC2_RGBA8',
}

# bytes per pixel for the linear formats; block formats handled separately
LINEAR_BPP = {ALPHA8: 1, R16: 2, RGB565: 2, ARGB4444: 2, RGBA4444: 2,
              RGB24: 3, RGBA32: 4, ARGB32: 4, BGRA32: 4}


class Texture:
    __slots__ = ('name', 'width', 'height', 'fmt', 'mips', 'data', 'streamed')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def format_name(self):
        return FORMAT_NAMES.get(self.fmt, 'fmt%d' % self.fmt)

    def __repr__(self):
        return '<Texture %s %dx%d %s%s>' % (self.name, self.width, self.height,
                                            self.format_name,
                                            ' streamed' if self.streamed else '')


def read_texture2d(sf, obj, resource_dirs=None):
    """Parse a Texture2D object out of a SerializedFile.

    Layout is Unity 5.3's: name, dimensions, format, mip count, readability
    flags, image/dimension counts, sampler settings, then either inline pixel
    data or a StreamingInfo pointing into a sibling .resource file.
    """
    from unityser import Reader
    r = Reader(sf.body(obj), 0)
    name = r.astr()
    width = r.i32(); height = r.i32()
    r.i32()                                  # m_CompleteImageSize
    fmt = r.i32(); mips = r.i32()
    r.u8(); r.u8(); r.align(4)               # m_IsReadable, m_ReadAllowed
    r.i32(); r.i32()                         # m_ImageCount, m_TextureDimension
    r.i32(); r.i32(); r.u('f', 4); r.i32()   # m_TextureSettings
    r.i32(); r.i32()                         # m_LightmapFormat, m_ColorSpace
    size = r.i32()
    streamed = False
    if size > 0:
        data = r.raw(size)
    else:
        off = r.u32(); sz = r.u32(); path = r.astr()
        streamed = True
        data = b''
        if resource_dirs and path:
            from audio import find_resource
            p = find_resource(path, resource_dirs)
            if p:
                with open(p, 'rb') as fh:
                    fh.seek(off); data = fh.read(sz)
    return Texture(name=name, width=width, height=height, fmt=fmt, mips=mips,
                   data=data, streamed=streamed)


# ---------------------------------------------------------------- decoding

def decode(tex):
    """-> (width, height, RGBA bytes) with the origin at the top left.

    Unity stores textures bottom-up, so the rows are flipped here.
    """
    import numpy as np
    w, h, f = tex.width, tex.height, tex.fmt
    if f in LINEAR_BPP:
        rgba = _decode_linear(tex, np)
    elif f in (ETC_RGB4, ETC2_RGB, ETC2_RGBA8):
        rgba = _decode_etc(tex, np)
    else:
        raise NotImplementedError('format %s' % tex.format_name)
    rgba = rgba.reshape(h, w, 4)[::-1]       # bottom-up -> top-down
    return w, h, rgba.tobytes()


def _decode_linear(tex, np):
    w, h, f = tex.width, tex.height, tex.fmt
    need = w * h * LINEAR_BPP[f]
    buf = tex.data[:need]
    if len(buf) < need:
        raise ValueError('%s: short data, %d < %d' % (tex.name, len(buf), need))
    out = np.zeros((w * h, 4), np.uint8)
    if f in (RGBA32, ARGB32, BGRA32):
        a = np.frombuffer(buf, np.uint8).reshape(-1, 4)
        if f == RGBA32:   out[:] = a
        elif f == ARGB32: out[:] = a[:, [1, 2, 3, 0]]
        else:             out[:] = a[:, [2, 1, 0, 3]]
    elif f == RGB24:
        a = np.frombuffer(buf, np.uint8).reshape(-1, 3)
        out[:, :3] = a; out[:, 3] = 255
    elif f == ALPHA8:
        a = np.frombuffer(buf, np.uint8)
        out[:, :3] = 255; out[:, 3] = a
    elif f == R16:
        a = np.frombuffer(buf, '<u2')
        out[:, 0] = (a >> 8); out[:, 3] = 255
    elif f == RGB565:
        v = np.frombuffer(buf, '<u2').astype(np.uint32)
        r = (v >> 11) & 0x1f; g = (v >> 5) & 0x3f; b = v & 0x1f
        out[:, 0] = (r * 255 + 15) // 31
        out[:, 1] = (g * 255 + 31) // 63
        out[:, 2] = (b * 255 + 15) // 31
        out[:, 3] = 255
    elif f in (RGBA4444, ARGB4444):
        v = np.frombuffer(buf, '<u2').astype(np.uint32)
        n = [(v >> 12) & 0xf, (v >> 8) & 0xf, (v >> 4) & 0xf, v & 0xf]
        n = [(x * 17).astype(np.uint8) for x in n]
        if f == RGBA4444:
            out[:, 0], out[:, 1], out[:, 2], out[:, 3] = n
        else:
            out[:, 3], out[:, 0], out[:, 1], out[:, 2] = n
    return out


# ETC1 / ETC2 ------------------------------------------------------------
#
# One 4x4 block is 8 bytes: two subblocks, each with a base colour and one of
# eight modifier tables selected per pixel by a 2-bit index. ETC2_RGBA8 puts an
# 8-byte EAC alpha block in front of each colour block.

ETC_MODIFIERS = [
    [2, 8], [5, 17], [9, 29], [13, 42], [18, 60], [24, 80], [33, 106], [47, 183],
]

EAC_MODIFIERS = [
    [-3, -6, -9, -15, 2, 5, 8, 14], [-3, -7, -10, -13, 2, 6, 9, 12],
    [-2, -5, -8, -13, 1, 4, 7, 12], [-2, -4, -6, -13, 1, 3, 5, 12],
    [-3, -6, -8, -12, 2, 5, 7, 11], [-3, -7, -9, -11, 2, 6, 8, 10],
    [-4, -7, -8, -11, 3, 6, 7, 10], [-3, -5, -8, -11, 2, 4, 7, 10],
    [-2, -6, -8, -10, 1, 5, 7, 9], [-2, -5, -8, -10, 1, 4, 7, 9],
    [-2, -4, -8, -10, 1, 3, 7, 9], [-2, -5, -7, -10, 1, 4, 6, 9],
    [-3, -4, -7, -10, 2, 3, 6, 9], [-1, -2, -3, -10, 0, 1, 2, 9],
    [-4, -6, -8, -9, 3, 5, 7, 8], [-3, -5, -7, -9, 2, 4, 6, 8],
]


def _decode_etc(tex, np):
    w, h, f = tex.width, tex.height, tex.fmt
    bw, bh = (w + 3) // 4, (h + 3) // 4
    has_alpha = (f == ETC2_RGBA8)
    stride = 16 if has_alpha else 8
    need = bw * bh * stride
    buf = tex.data[:need]
    if len(buf) < need:
        raise ValueError('%s: short data, %d < %d' % (tex.name, len(buf), need))
    blocks = np.frombuffer(buf, np.uint8).reshape(bw * bh, stride)

    colour = blocks[:, 8:] if has_alpha else blocks
    px = _etc_colour_blocks(colour, np, etc2=(f != ETC_RGB4))   # (n,4,4,3)

    out = np.zeros((bh * 4, bw * 4, 4), np.uint8)
    out[..., 3] = 255
    grid = px.reshape(bh, bw, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 3)
    out[..., :3] = grid
    if has_alpha:
        al = _eac_blocks(blocks[:, :8], np)                 # (n,4,4)
        ag = al.reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(bh * 4, bw * 4)
        out[..., 3] = ag
    return out[:h, :w].reshape(-1, 4)


ETC2_DISTANCE = [3, 6, 11, 16, 23, 32, 41, 64]


def _etc2_th_planar(b, np):
    """T, H and Planar block colours — the three modes ETC2 adds over ETC1.

    Returns (t_px, h_px, planar_px), each (n,16,3), in the same column-major
    pixel order as the ETC1 path.
    """
    dist = np.array(ETC2_DISTANCE, np.int32)
    idx = np.arange(16)
    x = idx // 4
    y = idx % 4

    # --- T mode: one flat colour plus a second shifted +/- dist
    r1 = ((b[:, 0] >> 1) & 0x0C) | (b[:, 0] & 0x03)
    g1 = b[:, 1] >> 4
    b1 = b[:, 1] & 0x0F
    r2 = b[:, 2] >> 4
    g2 = b[:, 2] & 0x0F
    b2 = b[:, 3] >> 4
    dt = ((b[:, 3] >> 1) & 0x06) | (b[:, 3] & 0x01)
    c0 = np.stack([r1, g1, b1], -1) * 17
    c1 = np.stack([r2, g2, b2], -1) * 17
    d = dist[dt][:, None]
    t_pal = np.stack([c0, np.clip(c1 + d, 0, 255), c1, np.clip(c1 - d, 0, 255)], 1)

    # --- H mode: two colours, each shifted +/- dist
    hr1 = (b[:, 0] >> 3) & 0x0F
    hg1 = ((b[:, 0] & 0x07) << 1) | ((b[:, 1] >> 4) & 0x01)
    hb1 = (b[:, 1] & 0x08) | ((b[:, 1] << 1) & 0x06) | ((b[:, 2] >> 7) & 0x01)
    hr2 = (b[:, 2] >> 3) & 0x0F
    hg2 = ((b[:, 2] & 0x07) << 1) | ((b[:, 3] >> 7) & 0x01)
    hb2 = (b[:, 3] >> 3) & 0x0F
    hc0 = np.stack([hr1, hg1, hb1], -1) * 17
    hc1 = np.stack([hr2, hg2, hb2], -1) * 17
    dh = (b[:, 3] & 0x04) | ((b[:, 3] >> 1) & 0x02)
    pack = lambda c: (c[:, 0] << 16) | (c[:, 1] << 8) | c[:, 2]
    dh = dh | (pack(hc0) >= pack(hc1)).astype(np.int32)
    d = dist[dh][:, None]
    h_pal = np.stack([np.clip(hc0 + d, 0, 255), np.clip(hc0 - d, 0, 255),
                      np.clip(hc1 + d, 0, 255), np.clip(hc1 - d, 0, 255)], 1)

    # --- Planar mode: a bilinear ramp; pixel selector bits are unused
    e6 = lambda v: (v << 2) | (v >> 4)
    e7 = lambda v: (v << 1) | (v >> 6)
    ro = (b[:, 0] >> 1) & 0x3F
    go = ((b[:, 0] & 1) << 6) | ((b[:, 1] >> 1) & 0x3F)
    bo = (((b[:, 1] & 1) << 5) | (b[:, 2] & 0x18) |
          ((b[:, 2] << 1) & 0x06) | ((b[:, 3] >> 7) & 1))
    rh = ((b[:, 3] >> 1) & 0x3E) | (b[:, 3] & 1)
    gh = (b[:, 4] >> 1) & 0x7F
    bh = ((b[:, 4] & 1) << 5) | ((b[:, 5] >> 3) & 0x1F)
    rv = ((b[:, 5] & 7) << 3) | ((b[:, 6] >> 5) & 7)
    gv = ((b[:, 6] & 0x1F) << 2) | ((b[:, 7] >> 6) & 3)
    bv = b[:, 7] & 0x3F
    o = np.stack([e6(ro), e7(go), e6(bo)], -1)[:, None, :]
    hh = np.stack([e6(rh), e7(gh), e6(bh)], -1)[:, None, :]
    vv = np.stack([e6(rv), e7(gv), e6(bv)], -1)[:, None, :]
    xs = x[None, :, None]; ys = y[None, :, None]
    planar = np.clip((xs * (hh - o) + ys * (vv - o) + 4 * o + 2) >> 2, 0, 255)

    return t_pal, h_pal, planar


def _etc_colour_blocks(blk, np, etc2=True):
    n = blk.shape[0]
    b = blk.astype(np.int32)
    diffbit = (b[:, 3] >> 1) & 1
    flipbit = b[:, 3] & 1

    # individual mode: two 4-bit channels per subblock, scaled by 17
    ind = np.stack([
        np.stack([(b[:, 0] >> 4) & 0xf, (b[:, 1] >> 4) & 0xf, (b[:, 2] >> 4) & 0xf], -1) * 17,
        np.stack([b[:, 0] & 0xf, b[:, 1] & 0xf, b[:, 2] & 0xf], -1) * 17,
    ], 1)                                                   # (n,2,3)

    # differential mode: 5-bit base plus a 3-bit signed delta, scaled to 8 bits
    base5 = np.stack([(b[:, 0] >> 3) & 0x1f, (b[:, 1] >> 3) & 0x1f, (b[:, 2] >> 3) & 0x1f], -1)
    d3 = np.stack([b[:, 0] & 7, b[:, 1] & 7, b[:, 2] & 7], -1)
    d3 = np.where(d3 > 3, d3 - 8, d3)
    raw5 = base5 + d3
    sec5 = np.clip(raw5, 0, 31)
    ext = lambda v: (v << 3) | (v >> 2)
    dif = np.stack([ext(base5), ext(sec5)], 1)              # (n,2,3)

    base = np.where(diffbit[:, None, None].astype(bool), dif, ind)

    # In ETC2 a differential block whose channel sum overflows 5 bits is not a
    # differential block at all: the first overflowing channel selects T, H or
    # Planar instead. 0 = plain ETC1.
    if etc2:
        ov = (raw5 < 0) | (raw5 > 31)
        d_ = diffbit.astype(bool)
        mode = np.where(d_ & ov[:, 0], 1,
               np.where(d_ & ~ov[:, 0] & ov[:, 1], 2,
               np.where(d_ & ~ov[:, 0] & ~ov[:, 1] & ov[:, 2], 3, 0)))
    else:
        mode = np.zeros(n, np.int32)

    tbl = np.stack([(b[:, 3] >> 5) & 7, (b[:, 3] >> 2) & 7], -1)   # (n,2)

    bits = (b[:, 4] << 24) | (b[:, 5] << 16) | (b[:, 6] << 8) | b[:, 7]
    bits = bits.astype(np.uint32)
    # pixel order within a block is column-major: index = x*4 + y
    idx = np.arange(16)
    msb = (bits[:, None] >> (16 + idx[None, :])) & 1
    lsb = (bits[:, None] >> idx[None, :]) & 1
    sel = (msb << 1) | lsb                                  # (n,16) in 0..3

    # a pixel's 2-bit selector indexes this row directly: 0..3 = +a, +b, -a, -b
    mods = np.array(ETC_MODIFIERS, np.int32)                # (8,2)
    full = np.stack([mods[:, 0], mods[:, 1], -mods[:, 0], -mods[:, 1]], 1)

    x = (idx // 4)[None, :]
    y = (idx % 4)[None, :]
    sub = np.where(flipbit[:, None].astype(bool), (y >= 2).astype(np.int32),
                   (x >= 2).astype(np.int32))               # (n,16)

    t = np.take_along_axis(tbl, sub, 1)                     # (n,16)
    delta = full[t, sel]                                    # (n,16)
    px_base = np.take_along_axis(base, sub[:, :, None].repeat(3, 2), 1)   # (n,16,3)
    rgb = np.clip(px_base + delta[:, :, None], 0, 255)      # (n,16,3)

    if etc2 and (mode != 0).any():
        t_pal, h_pal, planar = _etc2_th_planar(b, np)
        # T and H paint from a 4-entry palette chosen by the same selector bits
        pick = lambda pal: np.take_along_axis(pal, sel[:, :, None].repeat(3, 2), 1)
        m = mode[:, None, None]
        rgb = np.where(m == 1, pick(t_pal),
              np.where(m == 2, pick(h_pal),
              np.where(m == 3, planar, rgb)))

    out = np.zeros((n, 4, 4, 3), np.uint8)
    out[:, y[0], x[0]] = rgb.astype(np.uint8)
    return out


def _eac_blocks(blk, np):
    n = blk.shape[0]
    b = blk.astype(np.int32)
    base = b[:, 0]
    mult = (b[:, 1] >> 4) & 0xf
    tsel = b[:, 1] & 0xf
    bits = np.zeros(n, np.uint64)
    for i in range(2, 8):
        bits = (bits << np.uint64(8)) | b[:, i].astype(np.uint64)
    idx = np.arange(16)
    shift = (45 - 3 * idx).astype(np.uint64)
    sel = ((bits[:, None] >> shift[None, :]) & np.uint64(7)).astype(np.int32)
    tbl = np.array(EAC_MODIFIERS, np.int32)
    mod = tbl[tsel][np.arange(n)[:, None], sel]             # (n,16)
    mult = np.where(mult == 0, 1, mult)     # 0 is undefined in the spec; use 1
    val = np.clip(base[:, None] + mod * mult[:, None], 0, 255).astype(np.uint8)
    out = np.zeros((n, 4, 4), np.uint8)
    out[:, idx % 4, idx // 4] = val
    return out


# ---------------------------------------------------------------- PNG out

def write_png(path, width, height, rgba):
    """Minimal RGBA8 PNG writer — no imaging library needed."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)                                       # filter: none
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    hdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', hdr))
        f.write(chunk(b'IDAT', zlib.compress(bytes(raw), 6)))
        f.write(chunk(b'IEND', b''))
