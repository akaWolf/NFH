"""XWD (ZPixmap, 24/32 bpp) -> PNG"""
import struct, sys
from PIL import Image
raw = open(sys.argv[1], 'rb').read()
h = struct.unpack('>25I', raw[:100])
hsize, ver, fmt, depth, w, hgt, xoff, border, unit, bitorder, pad, bpp, bpl, vclass, rm, gm, bm, bitsrgb, cmapent, ncol = h[:20]
off = hsize + ncol * 12
img = Image.frombuffer('RGB', (w, hgt), raw[off:off + bpl * hgt], 'raw', 'BGRX' if border == 0 else 'RGBX', bpl, 1)
img.convert('RGB').save(sys.argv[2])
print(w, hgt, depth, bpp, 'byte_order', border)
