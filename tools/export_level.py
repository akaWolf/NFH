"""Export one Unity scene to readable JSON: enums as names, PPtrs as object names."""
import json, sys, os, re
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


def _quad_texture(index, sf, comps):
    """background_texture, but through the extraction's collision-numbered
    names — four L201 chests all serialize a texture literally named
    'ms_0000', and the bare m_Name would land them on L211's deck rail"""
    from assets import read_renderer_materials, read_material_maintex_st
    mr = next((pid for cid, _, pid in comps if cid == 23), None)
    if mr is None:
        return None
    obj = next((o for o in sf.objects if o['path_id'] == mr), None)
    if obj is None:
        return None
    try:
        mats = read_renderer_materials(sf, obj)
    except Exception:
        return None
    for fid, pid in mats:
        mf, mo = index.deref(sf, fid, pid)
        if mo is None:
            continue
        try:
            st = read_material_maintex_st(mf, mo)
        except Exception:
            continue
        if not st:
            continue
        tex, scale, offset = st
        tf, to = index.deref(mf, tex[0], tex[1])
        if to is None:
            continue
        # the material's _MainTex_ST: the Plane's 0..1 UVs go through
        # uv * scale + offset — L101's Binoculars quad shows the
        # (0.625..0.70, 0.34..0.52) window of its 256x256 sheet, not the
        # whole texture
        uv = [scale[0], scale[1], offset[0], offset[1]]
        name = _extract_texture_names().get(
            (os.path.basename(tf.path), to['path_id']))
        if name:
            return name, uv
        try:
            return Reader(tf.body(to), 0).astr(), uv
        except Exception:
            return None
    return None


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
        tex_uv = _quad_texture(index, sc.f, comps)
        if not tex_uv:
            continue
        tex, uv = tex_uv
        # Renderer.m_Enabled is the first byte after the GameObject pointer
        # (the layout read_renderer_materials documents); the tricked-overlay
        # objects ship with it off and SetTrickedObjectHidden flips it
        ro = next((x for x in sc.f.objects if x['path_id'] == mr), None)
        er = Reader(sc.f.body(ro), 0); er.i32(); er.i64()
        renderer_enabled = bool(er.u8())
        p, s, _r = world.get(tr, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0),
                                  (0.0, 0.0, 0.0, 1.0)))
        out.append({'name': name, 'texture': tex, 'uv': uv, 'active': active,
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
    resolve_sheet_textures(sc, index, out)
    resolve_texture_fields(sc, index, out)
    resolve_audio_fields(sc, index, out)
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
    if o['class_id'] == 28:                      # Texture2D: the extraction's
        name = _extract_texture_names().get(     # collision-numbered PNG name;
            (os.path.basename(tf.path), o['path_id']))   # m_Name alone is not
        if name is None:                         # unique (Mutter_dis_001 x2,
            name = Reader(tf.body(o), 0).astr()  # progress_back x2, camera x2)
        return {'texture': name}
    if o['class_id'] == 49:                      # TextAsset: m_Name, m_Script
        r = Reader(tf.body(o), 0)
        r.astr()
        return {'text': r.astr()}
    if o['class_id'] == 128:                     # Font: m_Name leads
        return {'font': Reader(tf.body(o), 0).astr()}
    if o['class_id'] == 83:                      # AudioClip: the extraction's
        name = _extract_audio_names().get(       # collision-numbered WAV name
            (os.path.basename(tf.path), o['path_id']))
        if name is None:
            name = Reader(tf.body(o), 0).astr()
        return {'clip': name}
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


_EXTRACT_NAMES = None
_EXTRACT_AUDIO_NAMES = None


def _extract_audio_names():
    """(file basename, path_id) -> the WAV name extract_audio.py wrote,
    replicating its collision numbering"""
    global _EXTRACT_AUDIO_NAMES
    if _EXTRACT_AUDIO_NAMES is not None:
        return _EXTRACT_AUDIO_NAMES
    import collections
    from extract_textures import serialized_files
    from audio import read_audioclip
    used = collections.Counter()
    table = {}
    for p in serialized_files():
        try:
            sf = SerializedFile(p)
        except Exception:
            continue
        for o in sf.objects:
            if o['class_id'] != 83:
                continue
            try:
                clip = read_audioclip(sf, o)
            except Exception:
                continue
            name = re.sub(r'[^A-Za-z0-9_.-]', '_', clip.name) or 'unnamed'
            used[name] += 1
            table[(os.path.basename(p), o['path_id'])] = \
                name if used[name] == 1 else '%s~%d' % (name, used[name])
    _EXTRACT_AUDIO_NAMES = table
    return table


AUDIO_FIELDS = {
    # MusicPlayer's whole soundtrack (MusicPlayer.cs:5-35)
    'MusicPlayer': ('LevelSounds', 'AlternateLevelSounds', 'LevelStart',
                    'EntranceSound', 'SuccessNormal', 'SuccessPerfect',
                    'Caught', 'Failed', 'Joke', 'EntranceClap'),
    # the audience laughs (Rottweiler.PlayAudienceLaugh, cs:805-818)
    'Rottweiler': ('MediumLaughs', 'BigLaughs'),
}


def resolve_audio_fields(sc, index, out):
    """resolve the AudioClip PPtrs the runtime's sound port consumes"""
    for e in out['objects'].values():
        d = e.get('data')
        if e.get('class_id') == 82 and isinstance(d, dict):
            # an AudioSource's own clip (MusicPlayer.HoverSound / ClickSound
            # are AudioSource references, MusicPlayer.cs:31-33)
            v = d.get('clip')
            if isinstance(v, dict) and ('external' in v or 'file' in v):
                d['clip'] = _resolve_asset_ref(sc, index, v) or v
            continue
        fields = AUDIO_FIELDS.get(e.get('type'))
        if not fields or not isinstance(d, dict):
            continue
        for k in fields:
            v = d.get(k)
            if isinstance(v, dict) and ('external' in v or 'file' in v):
                d[k] = _resolve_asset_ref(sc, index, v) or v
            elif isinstance(v, list):
                d[k] = [(_resolve_asset_ref(sc, index, x) or x)
                        if isinstance(x, dict) and
                        ('external' in x or 'file' in x) else x
                        for x in v]


def _extract_texture_names():
    """(file basename, path_id) -> the PNG name extract_textures.py wrote,
    replicating its collision numbering (m_Name, '~N' on repeats) so a PPtr
    to one of the twelve 'ms_0000' textures still lands on the right file"""
    global _EXTRACT_NAMES
    if _EXTRACT_NAMES is not None:
        return _EXTRACT_NAMES
    import collections
    from extract_textures import serialized_files
    from texture import read_texture2d
    used = collections.Counter()
    table = {}
    for p in serialized_files():
        try:
            sf = SerializedFile(p)
        except Exception:
            continue
        rdirs = (os.path.dirname(p), paths.APK, paths.OBB)
        for o in sf.objects:
            if o['class_id'] != 28:
                continue
            try:
                tex = read_texture2d(sf, o, resource_dirs=rdirs)
            except Exception:
                continue
            name = re.sub(r'[^A-Za-z0-9_.-]', '_', tex.name) or 'unnamed'
            used[name] += 1
            table[(os.path.basename(p), o['path_id'])] = \
                name if used[name] == 1 else '%s~%d' % (name, used[name])
    _EXTRACT_NAMES = table
    return table


_RESOURCE_CONTAINER = None


def reset_season_caches():
    """every module cache binds to one season's files (paths.set_data) —
    drop them all before exporting another season in the same process
    (the bundle's first run chains s1 then s2)"""
    global _EXTRACT_NAMES, _EXTRACT_AUDIO_NAMES, _RESOURCE_CONTAINER
    SCENE_NAMES.clear()
    _EXTRACT_NAMES = None
    _EXTRACT_AUDIO_NAMES = None
    _RESOURCE_CONTAINER = None


def _resource_container():
    """Resources.Load's index: the ResourceManager container in
    globalgamemanagers (class 147, path -> PPtr; tools/extract_gui.py walks
    the same table). Keys are the lower-cased Resources paths — that is why
    Resources.Load is case-insensitive. -> {path: (file basename, path_id)}
    keeping the FIRST entry of a duplicated path: the container is a
    multimap and Load returns its first match (7 paths repeat in S1, 9 in
    S2 — the HUD bars, Mutter_dis_001, progress_back/front,
    abrechnungsscreen, plus two sheet/pattern-file pairs; the Texture2D
    entry comes first in every one of them)."""
    global _RESOURCE_CONTAINER
    if _RESOURCE_CONTAINER is not None:
        return _RESOURCE_CONTAINER
    from extract_gui import container
    gg = SerializedFile(paths.GG)
    index = AssetIndex()
    table = {}
    for p, fid, pid in container(gg):
        if p in table:
            continue
        tf = index.resolve_file(gg, fid)
        if tf is not None:
            table[p] = (os.path.basename(tf.path), pid)
    _RESOURCE_CONTAINER = table
    return table


def _resolve_resource_texture(path):
    """Resources.Load(path) for a texture sheet -> the extraction's
    collision-numbered PNG name, or None when the container has no such
    path (Load returns null; AnimationInstance.LoadTexture, cs:136-140,
    logs 'could not load' and the sheet stays empty). A path whose first
    container entry is not a Texture2D also yields None (the cast in
    LoadTexture would fail) — no such path exists in either season."""
    if not path:
        return None
    ent = _resource_container().get(path.lower())
    if ent is None:
        return None
    return _extract_texture_names().get(ent)


def resolve_sheet_textures(sc, index, out):
    """AnimationInstance.LoadTexture (AnimationInstance.cs:130-143):
    SheetTexture = Resources.Load(BaseAnimationPath + TextureFileName) —
    a Resources path, not a PPtr, so the collision numbering cannot come
    from a pointer: walk the ResourceManager container the way Load does
    and store the resolved PNG name as each animation's SheetTexture (the
    runtime field LoadTexture fills; null where Load finds nothing: 162
    references, 160 of them S1's mother-door strips under a path that
    does not exist plus L213's two BoatPicnic strips). Without it the
    runtime fell back to the bare basename, which lands 23 Season-2 sheet
    references (18 distinct level/sheet pairs) on a same-named twin —
    L212's live bull drew the 109x72 'bull' bubble icon instead of bull~2,
    L202's rocks took L211's deck rail (ms_0000 for ms_0000~8)."""
    for e in out['objects'].values():
        d = e.get('data')
        if not isinstance(d, dict) or 'BaseAnimationPath' not in d \
                or not isinstance(d.get('Animations'), list):
            continue
        base = d.get('BaseAnimationPath') or ''
        for a in d['Animations']:
            if isinstance(a, dict) and 'TextureFileName' in a:
                a['SheetTexture'] = _resolve_resource_texture(
                    base + (a.get('TextureFileName') or ''))


def resolve_texture_fields(sc, index, out):
    """resolve the Texture PPtr fields the runtime's OnGUI ports consume in
    place: the items' interaction-icon tips (Item.OnGUI, Item.cs:2740-2760)
    and the Level fences (Level.OnGUI, Level.cs:322-341). Fence textures get
    the extraction's collision-numbered name — their m_Name is not unique."""
    for e in out['objects'].values():
        d = e.get('data')
        if not isinstance(d, dict):
            continue
        v = d.get('ItemTipIcon')
        if isinstance(v, dict) and ('external' in v or 'file' in v):
            d['ItemTipIcon'] = _resolve_asset_ref(sc, index, v) or v
        v = d.get('FenceTextures')
        if isinstance(v, list) and any(isinstance(x, dict) and
                                       ('external' in x or 'file' in x)
                                       for x in v):
            d['FenceTextures'] = [_resolve_fence_texture(sc, index, x)
                                  for x in v]
        # Item.PrimedMaterial (Item.cs:1236-1239): the quad's material swap
        # on prime — resolve it down to its _MainTex name
        v = d.get('PrimedMaterial')
        if isinstance(v, dict) and ('external' in v or 'file' in v):
            d['PrimedMaterial'] = _resolve_material_texture(sc, index, v) or v


def _resolve_material_texture(sc, index, v):
    """a Material PPtr -> {'texture': its _MainTex extraction name}"""
    from assets import read_material_maintex
    mf, mo = index.deref(sc.f, v.get('external', v.get('file', 0)), v['path'])
    if mo is None or mo['class_id'] != 21:
        return None
    try:
        tex = read_material_maintex(mf, mo)
    except Exception:
        return None
    if not tex:
        return None
    tf, to = index.deref(mf, tex[0], tex[1])
    if to is None:
        return None
    name = _extract_texture_names().get(
        (os.path.basename(tf.path), to['path_id']))
    if name is None:
        name = Reader(tf.body(to), 0).astr()
    return {'texture': name}


def _resolve_fence_texture(sc, index, v):
    if not (isinstance(v, dict) and ('external' in v or 'file' in v)):
        return v
    tf, o = index.deref(sc.f, v.get('external', v.get('file', 0)), v['path'])
    if o is None or o['class_id'] != 28:
        return _resolve_asset_ref(sc, index, v) or v
    name = _extract_texture_names().get(
        (os.path.basename(tf.path), o['path_id']))
    if name is None:
        return _resolve_asset_ref(sc, index, v) or v
    return {'texture': name}


def hud_sections(sc, index, out):
    """resolve the HUD / HUDProgressBar components' asset pointers into a
    top-level section, leaving the raw objects untouched"""
    res = {}
    for pid, e in out['objects'].items():
        if e.get('type') not in ('HUD', 'HUDProgressBar', 'ProgressBar',
                                 'DexterityComponent', 'MouseCursor',
                                 # the menu / flow classes (Control.cs and
                                 # kin, GameIntroAnimation, LevelLoader,
                                 # LevelTransition, Credits, InGameMenu,
                                 # ExitConfirmation, IntroAnimation, the
                                 # level tiles' data renderer): the same
                                 # pointer resolution, read by runtime/menu.py
                                 'Control', 'ControlButton', 'ControlWindow',
                                 'ControlSlider', 'ControlToggle',
                                 'ControlRadioButton', 'ControlRadioButtonGroup',
                                 'ControlRadioButtonInitializer',
                                 'ControlLabel', 'ControlButtonRestore',
                                 'LanguageComboBox', 'MenuLangInitializer',
                                 'LevelDataGUIRenderer', 'LevelUnlocker',
                                 'LevelPackUnlocker', 'GameIntroAnimation',
                                 'SplashScreen', 'LevelLoader',
                                 'LevelTransition', 'Credits',
                                 'MenuMouseController', 'InGameMenu',
                                 'ExitConfirmation', 'IntroAnimation',
                                 'DirectorAnimation', 'LevelScript',
                                 'TutorialScriptCamera',
                                 'TutorialScriptCameraIntro3',
                                 'TutorialScriptCameraNFH2',
                                 'TutorialScriptCameraNFH2206',
                                 'MusicPlayer', 'Level') \
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
