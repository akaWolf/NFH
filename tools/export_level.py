"""Export one Unity scene to readable JSON: enums as names, PPtrs as object names."""
import json, sys, os
import paths
from unityser import SerializedFile, Reader
from cli_meta import Assembly
from monodeser import Layouts, read_monobehaviour
from scene import Scene

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


def export(path, out_path=None, asm=None, layouts=None, script_names=None):
    asm = asm or Assembly(paths.DLL)
    L = layouts or Layouts(asm)
    names = script_names if script_names is not None else \
        SerializedFile(paths.GG_ASSETS).mono_scripts()
    sc = Scene(path, asm, L, names)

    enums = {}
    for n, rid in asm.by_name.items():
        if asm.is_enum(rid):
            enums[n] = asm.enum_values(rid)

    out = {'scene': os.path.basename(path),
           'unity_scene': SCENE_NAMES.get(os.path.basename(path)),
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
            e['data'] = {'name': sc.name_of(pid), 'gameObject': d['gameObject'],
                         'position': d['position'], 'scale': d['scale'],
                         'rotation': d['rotation'],
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
