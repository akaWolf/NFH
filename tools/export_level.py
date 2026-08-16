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


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _qrot(q, v):
    """rotate a vector by a quaternion (x, y, z, w)"""
    x, y, z, w = q
    vx, vy, vz = v
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (vx + w * tx + y * tz - z * ty,
            vy + w * ty + z * tx - x * tz,
            vz + w * tz + x * ty - y * tx)


def _world_transforms(sc):
    """Compose Unity's transform hierarchy: world = parent + parentRot * (parentScale * local).

    Rotation matters. 216 transforms across these levels carry the 90-degree
    quaternion that lays an object into the view plane, and 28 of their children
    sit at a non-zero local offset — one of them 28.7 units along local z, which
    the rotation turns into world y. Dropping the rotation misplaces those.
    """
    trs = {pid: o['data'] for pid, o in sc.objs.items()
           if o.get('class_id') == 4 and 'data' in o}
    out = {}

    def resolve(pid, depth=0):
        if pid in out:
            return out[pid]
        t = trs.get(pid)
        if t is None or depth > 32:
            return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0)
        f = t.get('father')
        if f:
            pp, ps, pr = resolve(f, depth + 1)
        else:
            pp, ps, pr = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0)
        lp, ls, lr = t['position'], t['scale'], t['rotation']
        scaled = tuple(ps[i] * lp[i] for i in range(3))
        rotated = _qrot(pr, scaled)
        wp = tuple(pp[i] + rotated[i] for i in range(3))
        ws = tuple(ps[i] * ls[i] for i in range(3))
        wr = _qmul(pr, tuple(lr))
        out[pid] = (wp, ws, wr)
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
        mr = next((pid for cid, _, pid in comps if cid == 23), None)
        if mr is None:
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
        # Renderer.m_Enabled is the first byte after the GameObject pointer
        # (the layout read_renderer_materials documents); the tricked-overlay
        # objects ship with it off and SetTrickedObjectHidden flips it
        ro = next((x for x in sc.f.objects if x['path_id'] == mr), None)
        er = Reader(sc.f.body(ro), 0); er.i32(); er.i64()
        renderer_enabled = bool(er.u8())
        p, s, _r = world.get(tr, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0),
                                  (0.0, 0.0, 0.0, 1.0)))
        out.append({'name': name, 'texture': tex, 'active': active,
                    'renderer_enabled': renderer_enabled,
                    'go': o['path_id'],
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
            wp, ws, wr = world.get(pid, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0),
                                         (0.0, 0.0, 0.0, 1.0)))
            e['data'] = {'name': sc.name_of(pid), 'gameObject': d['gameObject'],
                         'position': d['position'], 'scale': d['scale'],
                         'rotation': d['rotation'],
                         'world_position': list(wp), 'world_scale': list(ws),
                         'world_rotation': list(wr),
                         'children': d['children'], 'father': d['father']}
        else:
            e['data'] = d
        out['objects'][str(pid)] = e

    resolve_pattern_files(sc, index, out)
    hud = hud_sections(sc, index, out)
    if hud:
        out['hud'] = hud
    bi = bubble_icons(sc, index, out)
    if bi:
        out['bubble_icons'] = bi

    if out_path:
        with open(out_path, 'w') as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
    return sc, out


def _resolve_asset_ref(sc, index, v):
    """an {'external': N, 'path': P} (or raw {'file': N, 'path': P}) PPtr ->
    {'texture': name} for a Texture2D, {'text': body} for a TextAsset,
    {'font': name} for a Font (GUIStyle.m_Font keeps the raw form)"""
    tf, o = index.deref(sc.f, v.get('external', v.get('file', 0)), v['path'])
    if o is None:
        return None
    if o['class_id'] == 28:                      # Texture2D: m_Name leads
        return {'texture': Reader(tf.body(o), 0).astr()}
    if o['class_id'] == 49:                      # TextAsset: m_Name, m_Script
        r = Reader(tf.body(o), 0)
        r.astr()
        return {'text': r.astr()}
    if o['class_id'] == 128:                     # Font: m_Name leads
        return {'font': Reader(tf.body(o), 0).astr()}
    return None


def parse_pattern_file(text):
    """AnimationInstance.SetupPattern (AnimationInstance.cs:85-128): a header
    line, the frame count, another header, the frame indices; then blank
    lines, a consumed header, the sound count, and 'frame, filename' lines.
    Season 2 keeps nearly every animation's frames and sounds in these
    TextAssets instead of the serialized Pattern/Sounds fields."""
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    i = 0

    def read_line():
        nonlocal i
        if i >= len(lines):
            return None
        s = lines[i]
        i += 1
        return s
    try:
        read_line()                                   # header
        count = int(read_line())
        read_line()                                   # second header
        pattern = []
        while i < len(lines) and len(pattern) < count:
            t = (read_line() or '').strip()
            if not t:
                break
            pattern.append(int(t))
        # skip blank lines; the loop also consumes the first non-empty line
        while True:
            t = read_line()
            if t is None:
                return pattern, []
            if t.strip() != '':
                break
        sounds = []
        n = int(read_line())
        while i < len(lines) and len(sounds) < n:
            t = read_line()
            if t is None or not t.strip():
                continue
            frame, name = t.split(',', 1)
            sounds.append({'Frame': int(frame.strip()),
                           'FileName': name.strip()})
        return pattern, sounds
    except (ValueError, TypeError):
        return None, None                             # the C# catch logs and
                                                      # keeps the partial state


def resolve_pattern_files(sc, index, out):
    """fill each animation's Pattern and Sounds from its PatternFile
    TextAsset, the way AnimationInstance.SetupPattern does at load"""
    def walk(v):
        if isinstance(v, dict):
            pf = v.get('PatternFile')
            if isinstance(pf, dict) and pf.get('path'):
                if 'external' not in pf and 'file' not in pf:
                    pf = {'external': 0, 'path': pf['path']}   # scene-local
                r = _resolve_asset_ref(sc, index, pf)
                if r and 'text' in r:
                    pattern, sounds = parse_pattern_file(r['text'])
                    if pattern is not None:
                        v['Pattern'] = pattern
                        v['Sounds'] = sounds
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for e in out['objects'].values():
        if 'data' in e and isinstance(e['data'], dict):
            walk(e['data'])


def hud_sections(sc, index, out):
    """resolve the HUD / HUDProgressBar components' asset pointers into a
    top-level section, leaving the raw objects untouched"""
    res = {}
    for pid, e in out['objects'].items():
        if e.get('type') not in ('HUD', 'HUDProgressBar', 'ProgressBar',
                                 'DexterityComponent', 'MouseCursor') \
                or 'data' not in e:
            continue

        def walk(v):
            if isinstance(v, dict):
                if 'path' in v and ('external' in v or
                                    ('file' in v and len(v) == 2)):
                    return _resolve_asset_ref(sc, index, v) or v
                return {k: walk(x) for k, x in v.items()}
            if isinstance(v, list):
                return [walk(x) for x in v]
            return v
        res.setdefault(e['type'], []).append(walk(e['data']))
    return res


def bubble_icons(sc, index, out):
    """Zone.BubbleIcon textures — a MoveOnly action's think bubble reads
    MoveZone.BubbleIcon (RoutineAction.cs:43-55). Items carry string paths
    instead (Actor.BubbleIconPath), so only Zones resolve here."""
    res = {}
    for pid, e in out['objects'].items():
        d = e.get('data')
        if not isinstance(d, dict):
            continue
        icons = {}
        for f, key in (('BubbleIcon', 'icon'), ('BubbleIconActive', 'active'),
                       ('BubbleIconMad', 'mad')):
            v = d.get(f)
            if isinstance(v, dict) and 'path' in v and \
                    ('external' in v or 'file' in v):
                r = _resolve_asset_ref(sc, index, v)
                if r and 'texture' in r:
                    icons[key] = r['texture']
        if icons:
            res[pid] = icons
    return res


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
