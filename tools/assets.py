"""Cross-file PPtr resolution.

A PPtr is (file_id, path_id): file_id 0 means "this file", anything else indexes
the file's externals list. Following one means opening the referenced serialized
file, so results are cached.
"""
import os

import paths
from unityser import SerializedFile, Reader


class AssetIndex:
    def __init__(self):
        self._files = {}

    def open(self, path):
        key = os.path.basename(path)
        if key not in self._files:
            self._files[key] = SerializedFile(path)
        return self._files[key]

    def resolve_file(self, sf, file_id):
        """the SerializedFile a PPtr's file_id refers to, or None"""
        if file_id == 0:
            return sf
        if file_id - 1 >= len(sf.externals):
            return None
        name = os.path.basename(sf.externals[file_id - 1][2])
        for d in (paths.OBB, paths.APK):
            p = os.path.join(d, name)
            if os.path.exists(p):
                try:
                    return self.open(p)
                except Exception:
                    return None
        return None

    def deref(self, sf, file_id, path_id):
        """-> (SerializedFile, object) or (None, None)"""
        if path_id == 0:
            return None, None
        tf = self.resolve_file(sf, file_id)
        if tf is None:
            return None, None
        for o in tf.objects:
            if o['path_id'] == path_id:
                return tf, o
        return None, None


def read_material_maintex(sf, obj):
    """Material -> ('_MainTex' PPtr as (file_id, path_id)), or None"""
    r = Reader(sf.body(obj), 0)
    r.astr()                                  # m_Name
    r.i32(); r.i64()                          # m_Shader
    r.astr()                                  # m_ShaderKeywords
    r.u32(); r.i32()                          # lightmap flags, custom queue
    for _ in range(r.i32()):                  # stringTagMap
        r.astr(); r.astr()
    for _ in range(r.i32()):                  # m_TexEnvs
        key = r.astr()
        fid = r.i32(); pid = r.i64()
        r.u('f', 4); r.u('f', 4)              # m_Scale
        r.u('f', 4); r.u('f', 4)              # m_Offset
        if key == '_MainTex':
            return fid, pid
    return None


def read_renderer_materials(sf, obj):
    """MeshRenderer -> [(file_id, path_id)] for m_Materials.

    Unity 5.3's Renderer header is 56 bytes before the material array: the
    GameObject pointer, three shadow/enable bytes, a 4-byte field this build
    does not name, the two lightmap indices, and the two lightmap tiling
    vectors.
    """
    r = Reader(sf.body(obj), 0)
    r.i32(); r.i64()                          # m_GameObject
    r.u8(); r.u8(); r.u8(); r.align(4)        # enabled, cast, receive
    r.u32()                                   # probe/motion-vector flags
    r.u16(); r.u16()                          # lightmap indices
    for _ in range(8):                        # two Vector4 tiling/offsets
        r.u('f', 4)
    return [(r.i32(), r.i64()) for _ in range(r.i32())]


def background_texture(index, sf, level_go_components):
    """Resolve the backdrop texture name for a level.

    level_go_components is the component list of the GameObject carrying both
    the Level script and the MeshRenderer.
    """
    mr = next((pid for cid, fid, pid in level_go_components if cid == 23), None)
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
            tex = read_material_maintex(mf, mo)
        except Exception:
            continue
        if not tex:
            continue
        tf, to = index.deref(mf, tex[0], tex[1])
        if to is None:
            continue
        try:
            return Reader(tf.body(to), 0).astr()      # Texture2D m_Name
        except Exception:
            return None
    return None
