"""Decode every Texture2D in the game data to PNG.

    NFH_DATA=/path/to/extraction python3 tools/extract_textures.py out/textures

Needs numpy for the ETC block formats; everything else is standard library.
"""
import os, sys, glob, re, collections, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from unityser import SerializedFile
from texture import read_texture2d, decode, write_png

TEXTURE_CLASS_ID = 28


def serialized_files():
    """Everything that can hold a Texture2D: scenes, sharedassets, and the
    GUID-named per-asset files."""
    seen, out = set(), []
    for d in (paths.APK, paths.OBB):
        for p in glob.glob(os.path.join(d, '*')):
            b = os.path.basename(p)
            if b.endswith('.resource') or '.split' in b or b.endswith('.dll'):
                continue
            if not os.path.isfile(p):
                continue
            if (re.fullmatch(r'[0-9a-f]{32}', b) or re.fullmatch(r'level\d+', b)
                    or b.endswith('.assets') or b.startswith('globalgamemanagers')):
                if b not in seen:
                    seen.add(b); out.append(p)
    return sorted(out)


def main(outdir):
    paths.check()
    os.makedirs(outdir, exist_ok=True)
    fmts = collections.Counter()
    failed = []
    used = collections.Counter()
    n = px = 0
    t0 = time.time()
    for p in serialized_files():
        try:
            sf = SerializedFile(p)
        except Exception:
            continue
        rdirs = (os.path.dirname(p), paths.APK, paths.OBB)
        for o in sf.objects:
            if o['class_id'] != TEXTURE_CLASS_ID:
                continue
            try:
                tex = read_texture2d(sf, o, resource_dirs=rdirs)
            except Exception as e:
                failed.append(('<unreadable>', p, '%s: %s' % (type(e).__name__, e)))
                continue
            fmts[tex.format_name] += 1
            name = re.sub(r'[^A-Za-z0-9_.-]', '_', tex.name) or 'unnamed'
            used[name] += 1
            if used[name] > 1:                     # names are not unique
                name = '%s~%d' % (name, used[name])
            try:
                w, h, rgba = decode(tex)
                write_png(os.path.join(outdir, name + '.png'), w, h, rgba)
                n += 1; px += w * h
            except Exception as e:
                failed.append((tex.name, tex.format_name,
                               '%s: %s' % (type(e).__name__, e)))
    dt = time.time() - t0
    print('wrote %d PNGs (%.1f Mpx) in %.1fs -> %s' % (n, px / 1e6, dt, outdir))
    print('formats:', ', '.join('%s=%d' % kv for kv in fmts.most_common()))
    if failed:
        print('\nfailed: %d' % len(failed))
        for a, b, c in failed[:15]:
            print('   %-28s %-12s %s' % (a, b, c))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'textures'))
