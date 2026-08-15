"""Export one Unity scene to readable JSON: enums as names, PPtrs as object names."""
import json, sys, os
import paths
from unityser import SerializedFile, Reader
from cli_meta import Assembly
from monodeser import Layouts, read_monobehaviour
from scene import Scene
from assets import AssetIndex, background_texture

SCENE_NAMES = {}


def humanize(data, node, sc, enums):
    """walk value + layout together, resolving enums and pointers"""
    if node is None:
        return data
    k = node.kind
    if k == 'prim':
        if node.enum:
            table = enums.get(node.enum)
            if table is not None:
                return table.get(data, '%s(%d)' % (node.enum, data))
        return data
    if k == 'pptr':
        return ref(data, sc)
    if k == 'array':
        return [humanize(v, node.elem, sc, enums) for v in data]
    if k == 'struct':
        return {c.name: humanize(data.get(c.name), c, sc, enums) for c in node.children}
    return data


def ref(p, sc):
    if not isinstance(p, dict):
        return p
    if p.get('path', 0) == 0:
        return None
    if p.get('file', 0) != 0:
        return {'external': p['file'], 'path': p['path']}
    nm = sc.name_of(p['path'])
    o = sc.objs.get(p['path'])
    return {'path': p['path'], 'name': nm, 'type': o['type'] if o else None}


# Unity built-in mesh ids; every visual quad in these levels is the Plane
BUILTIN_PLANE, BUILTIN_CUBE = 10209, 10202
PLANE_SIZE = 10.0


def _world_transforms(sc):
    """position and scale composed down the hierarchy.

    Unity's transforms nest, so a door parented to a zone stores a local
    position. These levels carry no meaningful rotation on the item chain, so
    composing position and scale is enough: world = parent + parentScale * local.
    """
    from unityser import Reader
    tr = {}
    for o in sc.objs.values():
        pass
    trs = {pid: o['data'] for pid, o in sc.objs.items()
           if o.get('class_id') == 4 and 'data' in o}
    out = {}

    def resolve(pid, depth=0):
        if pid in out:
            return out[pid]
        t = trs.get(pid)
        if t is None or depth > 32:
            return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
        f = t.get('father')
        if f:
            pp, ps = resolve(f, depth + 1)
        else:
            pp, ps = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
        lp, ls = t['position'], t['scale']
        wp = tuple(pp[i] + ps[i] * lp[i] for i in range(3))
        ws = tuple(ps[i] * ls[i] for i in range(3))
        out[pid] = (wp, ws)
        return out[pid]

    for pid in trs:
        resolve(pid)
    return out


def _quads(sc, index, world):
    """Every MeshRenderer quad: the level backdrop and the handful of static
    item overlays. All of them are the built-in 10x10 Plane laid into XY, so the
    world size is 10 * (scale.x, scale.z)."""
    from unityser import Reader
    out = []
    for o in sc.f.objects:
        if o['class_id'] != 1:
            continue
        r = Reader(sc.f.body(o), 0)
        n = r.i32()
        comps = [(r.i32(), r.i32(), r.i64()) for _ in range(n)]
        layer = r.i32(); name = r.astr(); r.u16(); active = bool(r.u8())
        if not any(cid == 23 for cid, _, _ in comps):
            continue
        mf = next((pid for cid, _, pid in comps if cid == 33), None)
        tr = next((pid for cid, _, pid in comps if cid == 4), None)
        if mf is None or tr is None:
            continue
        mo = next((x for x in sc.f.objects if x['path_id'] == mf), None)
        rr = Reader(sc.f.body(mo), 0); rr.i32(); rr.i64()
        mesh_pid = (rr.i32(), rr.i64())[1]
        if mesh_pid != BUILTIN_PLANE:
            continue
        tex = background_texture(index, sc.f, comps)
        if not tex:
            continue
        p, s = world.get(tr, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
        out.append({'name': name, 'texture': tex, 'active': active,
                    'x': p[0], 'y': p[1], 'z': p[2],
                    'w': PLANE_SIZE * s[0], 'h': PLANE_SIZE * s[2],
                    'is_level': any(sc.objs.get(pid, {}).get('type') == 'Level'
                                    for _, _, pid in comps)})
    out.sort(key=lambda q: -q['z'])
    return out


def export(path, out_path=None, asm=None, layouts=None, script_names=None,
           index=None):
    asm = asm or Assembly(paths.DLL)
    L = layouts or Layouts(asm)
    names = script_names if script_names is not None else \
        SerializedFile(paths.GG_ASSETS).mono_scripts()
    sc = Scene(path, asm, L, names)
    index = index or AssetIndex()
    world = _world_transforms(sc)

    enums = {}
    for n, rid in asm.by_name.items():
        if asm.is_enum(rid):
            enums[n] = asm.enum_values(rid)

    out = {'scene': os.path.basename(path),
           'unity_scene': SCENE_NAMES.get(os.path.basename(path)),
           'quads': _quads(sc, index, world),
           'objects': {}}
    for pid, o in sc.objs.items():
        e = {'type': o['type'], 'class_id': o['class_id']}
        d = o.get('data')
        if d is None:
            out['objects'][str(pid)] = e
            continue
        if o['class_id'] == 114:
            rid = asm.by_name.get(o.get('script'))
            lay = L.class_layout(rid, stop_at='MonoBehaviour') if rid is not None else []
            hv = {'m_GameObject': ref(d['m_GameObject'], sc), 'm_Name': d['m_Name']}
            for node in lay:
                hv[node.name] = humanize(d.get(node.name), node, sc, enums)
            e['data'] = hv
        elif o['class_id'] == 1:
            e['data'] = dict(d)
            e['data']['components'] = [
                {'path': c['path'],
                 'type': (sc.objs.get(c['path']) or {}).get('type')} for c in d['components']]
        elif o['class_id'] == 4:
            wp, ws = world.get(pid, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
            e['data'] = {'name': sc.name_of(pid), 'gameObject': d['gameObject'],
                         'position': d['position'], 'scale': d['scale'],
                         'rotation': d['rotation'],
                         'world_position': list(wp), 'world_scale': list(ws),
                         'children': d['children'], 'father': d['father']}
        else:
            e['data'] = d
        out['objects'][str(pid)] = e

    if out_path:
        with open(out_path, 'w') as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
    return sc, out


def load_scene_names():
    gg = SerializedFile(paths.GG)
    for o in gg.objects:
        if o['class_id'] == 141:
            r = Reader(gg.body(o), 0)
            for i in range(r.i32()):
                SCENE_NAMES['level%d' % i] = r.astr()
            return SCENE_NAMES
    return SCENE_NAMES


if __name__ == '__main__':
    paths.check()
    load_scene_names()
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    sc, out = export(src, dst)
    print('%s -> %s objects%s' % (src, len(out['objects']),
                                  (', written to ' + dst) if dst else ''))
