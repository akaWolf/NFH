"""Extract Resources textures by their full container path.

The flat extraction collides on base names — three HUD face strips all ship
an idle_0000. Resources.Load resolves through the ResourceManager container
(class 147 in globalgamemanagers): path -> PPtr. This tool walks the
container and writes every texture under the given path prefixes with its
FULL path flattened into the file name (textures/gui/ingame2/neighbor/
idle_0000 -> textures_gui_ingame2_neighbor_idle_0000.png), which the runtime
texture cache already matches through its name.replace('/', '_') candidate.

    NFH_DATA=... python3 tools/extract_gui.py textures/s1 textures/gui textures/bubbles inventory
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from unityser import SerializedFile, Reader
from assets import AssetIndex
from texture import read_texture2d, decode, write_png

RESOURCE_MANAGER = 147


def container(sf):
    for o in sf.objects:
        if o['class_id'] == RESOURCE_MANAGER:
            r = Reader(sf.body(o), 0)
            for _ in range(r.i32()):
                p = r.astr()
                fid = r.i32()
                pid = r.i64()
                yield p, fid, pid
            return


def main(outdir, prefixes):
    os.makedirs(outdir, exist_ok=True)
    gg = SerializedFile(paths.GG)
    index = AssetIndex()
    resource_dirs = [os.path.dirname(paths.GG), paths.OBB]
    done = fail = 0
    for path, fid, pid in container(gg):
        if not any(path.startswith(p) for p in prefixes):
            continue
        tf, o = index.deref(gg, fid, pid)
        if o is None or o['class_id'] != 28:
            continue
        try:
            tex = read_texture2d(tf, o, resource_dirs)
            w, h, rgba = decode(tex)
        except Exception:
            fail += 1
            continue
        name = path.replace('/', '_') + '.png'
        write_png(os.path.join(outdir, name), w, h, rgba)
        done += 1
    print('%d textures by path -> %s (%d failed)' % (done, outdir, fail))


if __name__ == '__main__':
    paths.check()
    main(sys.argv[1] if len(sys.argv) > 1 else 'textures',
         tuple(sys.argv[2:]) or ('textures/gui/',))
