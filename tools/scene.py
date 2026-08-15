"""Read a whole Unity 5.3 scene: GameObject tree + components + script data."""
import struct
from unityser import SerializedFile, Reader, CLASS_NAMES
from cli_meta import Assembly
from monodeser import Layouts, read_monobehaviour


def r_gameobject(r):
    n = r.i32()
    comps = []
    for _ in range(n):
        cid = r.i32(); fid = r.i32(); pid = r.i64()
        comps.append({'class_id': cid, 'file': fid, 'path': pid})
    layer = r.i32(); name = r.astr(); tag = r.u16()
    active = r.u8()          # no trailing align: byte_size excludes the object padding
    return {'components': comps, 'layer': layer, 'name': name,
            'tag': tag, 'active': bool(active)}


def _v3(r): return [r.u('f', 4), r.u('f', 4), r.u('f', 4)]


def r_transform(r):
    go = (r.i32(), r.i64())
    rot = [r.u('f', 4) for _ in range(4)]
    pos = _v3(r); scale = _v3(r)
    kids = [(r.i32(), r.i64()) for _ in range(r.i32())]
    father = (r.i32(), r.i64())
    return {'gameObject': go[1], 'rotation': rot, 'position': pos, 'scale': scale,
            'children': [k[1] for k in kids], 'father': father[1]}


def r_boxcollider(r):
    go = (r.i32(), r.i64()); mat = (r.i32(), r.i64())
    trig = r.u8(); en = r.u8(); r.align(4)
    return {'gameObject': go[1], 'isTrigger': bool(trig), 'enabled': bool(en),
            'size': _v3(r), 'center': _v3(r)}


READERS = {1: r_gameobject, 4: r_transform, 65: r_boxcollider}


class Scene:
    def __init__(self, path, asm, layouts, script_names):
        self.f = SerializedFile(path)
        self.asm = asm; self.L = layouts
        self.names = script_names
        self.objs = {}           # path_id -> {'type':..., 'data':...}
        self.errors = []
        local = self.f.mono_scripts()
        for o in self.f.objects:
            cid = o['class_id']
            pid = o['path_id']
            tname = CLASS_NAMES.get(cid, 'cls%d' % cid)
            entry = {'class_id': cid, 'type': tname}
            try:
                if cid in READERS:
                    r = Reader(self.f.body(o), 0)
                    entry['data'] = READERS[cid](r)
                    entry['exact'] = (r.p == o['size'])
                elif cid == 114:
                    fid, spid = self.f.monobehaviour_script_ref(o)
                    cls = self.names.get(spid) if fid == 1 else local.get(spid)
                    entry['script'] = cls
                    rid = asm.by_name.get(cls) if cls else None
                    if rid is not None:
                        lay = layouts.class_layout(rid, stop_at='MonoBehaviour')
                        d, used = read_monobehaviour(self.f.body(o), lay)
                        entry['data'] = d
                        entry['exact'] = (used == o['size'])
                        entry['type'] = cls
            except Exception as e:
                self.errors.append((pid, tname, '%s: %s' % (type(e).__name__, e)))
                entry['exact'] = False
            self.objs[pid] = entry

    def gameobjects(self):
        return {p: o for p, o in self.objs.items() if o['class_id'] == 1}

    def name_of(self, path_id):
        o = self.objs.get(path_id)
        if not o: return None
        if o['class_id'] == 1: return o['data']['name']
        d = o.get('data') or {}
        gp = d.get('gameObject') or (d.get('m_GameObject') or {}).get('path')
        return self.name_of(gp) if gp else None


def load_all(scene_path, dll=None, gg=None):
    import paths
    asm = Assembly(dll or paths.DLL)
    L = Layouts(asm)
    names = SerializedFile(gg or paths.GG_ASSETS).mono_scripts()
    return Scene(scene_path, asm, L, names)
