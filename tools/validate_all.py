"""Self-test: every object in every scene must consume exactly its declared size."""
import collections
import paths
from unityser import SerializedFile
from cli_meta import Assembly
from monodeser import Layouts
from scene import Scene

paths.check()
asm = Assembly(paths.DLL)
L = Layouts(asm)
names = SerializedFile(paths.GG_ASSETS).mono_scripts()

ok = collections.Counter(); bad = collections.Counter()
for p in paths.scene_files():
    s = Scene(p, asm, L, names)
    for pid, o in s.objs.items():
        if 'exact' not in o: continue
        (ok if o['exact'] else bad)[o['type']] += 1

total = sum(ok.values()) + sum(bad.values())
print('exact %d / %d objects across %d scenes' % (sum(ok.values()), total,
                                                  len(paths.scene_files())))
if bad:
    print('FAILING:', bad.most_common(15))
    raise SystemExit(1)
print('types covered:', len(ok))
