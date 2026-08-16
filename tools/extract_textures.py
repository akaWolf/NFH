"""Decode every Texture2D in the game data to PNG.

    NFH_DATA=/path/to/extraction python3 tools/extract_textures.py out/textures
    NFH_DATA=... python3 tools/extract_textures.py out/textures --wrap-only

Needs numpy for the ETC block formats; everything else is standard library.
Next to the PNGs goes `wrap.json` — each texture's m_WrapMode ('repeat' /
'clamp'), which the runtime needs to draw a frame that ran past its sheet the
way Graphics.DrawTexture does; `--wrap-only` rewrites just that sidecar.
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


WRAP_INDEX = 'wrap.json'


def write_wrap_index(outdir, wraps):
    """the sidecar the runtime reads next to the PNGs: {png name: 'repeat' |
    'clamp'} — Texture2D.m_TextureSettings.m_WrapMode, the sampler state
    Graphics.DrawTexture applies when AnimationControllerBase.DrawAnimation
    (cs:153-170) hands it a source rect outside [0,1] (a CurrentFrame that
    ran past the sheet: Repeat wraps back onto the sheet, Clamp smears the
    edge row)"""
    import json
    with open(os.path.join(outdir, WRAP_INDEX), 'w') as f:
        json.dump(wraps, f, indent=0, sort_keys=True)
    modes = collections.Counter(wraps.values())
    print('wrap modes -> %s: %s' % (os.path.join(outdir, WRAP_INDEX),
                                    ', '.join('%s=%d' % kv for kv in
                                              modes.most_common())))


def wrap_only(outdir):
    """rebuild just the wrap sidecar for an existing extraction: the same
    files, the same numbering, no pixel work"""
    paths.check()
    os.makedirs(outdir, exist_ok=True)
    used = collections.Counter()
    wraps = {}
    for p in serialized_files():
        try:
            sf = SerializedFile(p)
        except Exception:
            continue
        for o in sf.objects:
            if o['class_id'] != TEXTURE_CLASS_ID:
                continue
            try:
                tex = read_texture2d(sf, o)     # header only, no .resource read
            except Exception:
                continue
            name = re.sub(r'[^A-Za-z0-9_.-]', '_', tex.name) or 'unnamed'
            used[name] += 1
            if used[name] > 1:
                name = '%s~%d' % (name, used[name])
            wraps[name] = tex.wrap_name
    write_wrap_index(outdir, wraps)
    return 0


def main(outdir):
    paths.check()
    os.makedirs(outdir, exist_ok=True)
    fmts = collections.Counter()
    failed = []
    used = collections.Counter()
    wraps = {}
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
            wraps[name] = tex.wrap_name
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
    write_wrap_index(outdir, wraps)
    if failed:
        print('\nfailed: %d' % len(failed))
        for a, b, c in failed[:15]:
            print('   %-28s %-12s %s' % (a, b, c))
    return 0 if not failed else 1


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[0] if args else 'textures'
    if '--wrap-only' in sys.argv:              # refresh wrap.json alone
        sys.exit(wrap_only(out))
    sys.exit(main(out))
