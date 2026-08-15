"""Deserialize Unity 5.3 MonoBehaviour payloads using the field layout
recovered from Assembly-CSharp.dll.

Self-check: bytes consumed must equal the object's declared size.
"""
import struct
from cli_meta import Assembly, Type, F_STATIC, F_INITONLY, F_LITERAL, F_NOTSERIALIZED, F_PUBLIC

# UnityEngine value types serialized inline, with their field layout
UNITY_STRUCTS = {
    'UnityEngine.Vector2':    [('x','float'),('y','float')],
    'UnityEngine.Vector3':    [('x','float'),('y','float'),('z','float')],
    'UnityEngine.Vector4':    [('x','float'),('y','float'),('z','float'),('w','float')],
    'UnityEngine.Quaternion': [('x','float'),('y','float'),('z','float'),('w','float')],
    'UnityEngine.Color':      [('r','float'),('g','float'),('b','float'),('a','float')],
    'UnityEngine.Color32':    [('rgba','uint')],
    'UnityEngine.Rect':       [('x','float'),('y','float'),('width','float'),('height','float')],
    'UnityEngine.Bounds':     [('cx','float'),('cy','float'),('cz','float'),
                               ('ex','float'),('ey','float'),('ez','float')],
    'UnityEngine.Matrix4x4':  [('m%d' % i,'float') for i in range(16)],
    'UnityEngine.LayerMask':  [('m_Bits','int')],
    'UnityEngine.RectOffset':  [('m_Left','int'),('m_Right','int'),('m_Top','int'),('m_Bottom','int')],
}

# GUIStyle is a plain serializable class, not a UnityEngine.Object, and it uses
# the native alignment convention: pad after a *run* of small fields, not after
# each one. Total is 348 bytes for an empty m_Name.
GUISTYLE_STATE = [('m_Background','pptr'),('r','float'),('g','float'),('b','float'),('a','float')]
GUISTYLE = (
    [('m_Name','string')]
    + [('%s.%s' % (s, n), t)
       for s in ('m_Normal','m_Hover','m_Active','m_Focused',
                 'm_OnNormal','m_OnHover','m_OnActive','m_OnFocused')
       for n, t in GUISTYLE_STATE]
    + [('%s.%s' % (o, n), 'int')
       for o in ('m_Border','m_Margin','m_Padding','m_Overflow')
       for n in ('left','right','top','bottom')]
    + [('m_Font','pptr'), ('m_FontSize','int'), ('m_FontStyle','int'), ('m_Alignment','int'),
       ('m_WordWrap','byte'), ('m_RichText','byte'), ('@align', None),
       ('m_TextClipping','int'), ('m_ImagePosition','int'),
       ('m_ContentOffset.x','float'), ('m_ContentOffset.y','float'),
       ('m_FixedWidth','float'), ('m_FixedHeight','float'),
       ('m_StretchWidth','byte'), ('m_StretchHeight','byte'), ('@align', None)]
)

# UnityEngine enums we may meet as field types (serialized as int)
UNITY_ENUMS = {
    'UnityEngine.WrapMode', 'UnityEngine.Space', 'UnityEngine.RuntimePlatform',
    'UnityEngine.KeyCode', 'UnityEngine.TextAnchor', 'UnityEngine.FilterMode',
    'UnityEngine.RenderMode', 'UnityEngine.CameraClearFlags', 'UnityEngine.HideFlags',
    'UnityEngine.AudioRolloffMode', 'UnityEngine.ForceMode', 'UnityEngine.LightType',
    'UnityEngine.ScreenOrientation', 'UnityEngine.SystemLanguage',
}

# things Unity cannot serialize at all -> field is skipped
NONSERIALIZABLE_PREFIX = ('System.Func', 'System.Action', 'System.Predicate',
                          'System.Delegate', 'System.MulticastDelegate',
                          'System.Collections.Generic.Dictionary',
                          'System.Collections.Generic.HashSet',
                          'System.Collections.Generic.Queue',
                          'System.Collections.Generic.Stack',
                          'System.Collections.Hashtable',
                          'System.Collections.IEnumerator',
                          'System.Type', 'System.IntPtr', 'System.Exception',
                          'System.EventHandler', 'System.Threading',
                          'System.IO', 'System.Reflection')

PRIM_SIZE = {'bool':1,'sbyte':1,'byte':1,'char':2,'short':2,'ushort':2,
             'int':4,'uint':4,'float':4,'long':8,'ulong':8,'double':8}
PRIM_FMT = {'bool':'?','sbyte':'b','byte':'B','char':'H','short':'h','ushort':'H',
            'int':'i','uint':'I','float':'f','long':'q','ulong':'Q','double':'d'}


class Node:
    """one entry in a serialization layout"""
    __slots__ = ('name', 'kind', 'prim', 'children', 'elem', 'enum')

    def __init__(self, name, kind, prim=None, children=None, elem=None, enum=None):
        self.name = name          # prim|string|pptr|struct|array|guistyle
        self.kind = kind
        self.prim = prim
        self.children = children or []
        self.elem = elem
        self.enum = enum          # enum type name, when the value is an enum

    def __repr__(self):
        return '<%s %s %s>' % (self.kind, self.prim or '', self.name)


class Layouts:
    def __init__(self, asm):
        self.a = asm
        self._cache = {}
        self._unity_obj_cache = {}

    # ---- classification --------------------------------------------------
    def _is_unity_object(self, tname, tab=None, rid=None):
        """True if the type derives from UnityEngine.Object -> serialized as PPtr"""
        if tname in self._unity_obj_cache:
            return self._unity_obj_cache[tname]
        res = False
        if tname.startswith('UnityEngine.'):
            res = tname not in UNITY_STRUCTS and tname not in UNITY_ENUMS
        elif tname in self.a.by_name:
            r = self.a.by_name[tname]
            seen = 0
            while r is not None and seen < 40:
                seen += 1
                bn = self.a.base_name(r)
                if bn is None: break
                if bn.startswith('UnityEngine.'):
                    res = bn not in UNITY_STRUCTS and bn not in UNITY_ENUMS
                    break
                r = self.a.by_name.get(bn)
        self._unity_obj_cache[tname] = res
        return res

    def _enum_underlying(self, rid):
        for nm, ty, fl, frid in self.a.fields_of(rid):
            if nm == 'value__':
                return ty.name if ty.kind == 'prim' else 'int'
        return 'int'

    @staticmethod
    def _subst(ty, subs):
        """replace generic parameters (!0, !1 ...) with the instantiated types"""
        if not subs:
            return ty
        if ty.kind == 'var':
            return subs.get(ty.rid, ty)
        if ty.kind in ('array', 'ptr') and ty.elem is not None:
            return Type(ty.kind, ty.name, elem=Layouts._subst(ty.elem, subs))
        if ty.kind == 'generic':
            return Type('generic', ty.name, args=[Layouts._subst(a, subs) for a in ty.args],
                        tab=ty.tab, rid=ty.rid)
        return ty

    def node_for(self, name, ty, subs=None, depth=0):
        """Type -> Node, or None if Unity would not serialize it."""
        if depth > 8:
            return None
        ty = self._subst(ty, subs)
        k = ty.kind
        if k == 'prim':
            if ty.name in PRIM_SIZE:
                return Node(name, 'prim', prim=ty.name)
            return None
        if k == 'string':
            return Node(name, 'string')
        if k in ('object', 'ptr', 'var', 'mdarray'):
            return None
        if k == 'array':
            inner = self.node_for('data', ty.elem, subs, depth + 1)
            return Node(name, 'array', elem=inner) if inner else None
        if k == 'generic':
            if ty.name == 'System.Collections.Generic.List`1' and len(ty.args) == 1:
                inner = self.node_for('data', ty.args[0], subs, depth + 1)
                return Node(name, 'array', elem=inner) if inner else None
            if any(ty.name.startswith(p) for p in NONSERIALIZABLE_PREFIX):
                return None
            if ty.tab == 2 and ty.rid in self.a.typedefs:
                argmap = {i: a for i, a in enumerate(ty.args)}
                return self._class_node(name, ty.rid, argmap, depth)
            return None
        # k == 'ref'
        tn = ty.name
        if tn == 'System.String':
            return Node(name, 'string')
        if tn == 'System.Object':
            return None
        if any(tn.startswith(p) for p in NONSERIALIZABLE_PREFIX):
            return None
        if tn in UNITY_STRUCTS:
            return Node(name, 'struct',
                        children=[Node(n, 'prim', prim=p) for n, p in UNITY_STRUCTS[tn]])
        if tn in UNITY_ENUMS:
            return Node(name, 'prim', prim='int')
        if tn == 'UnityEngine.GUIStyle':
            return Node(name, 'guistyle')
        if tn == 'UnityEngine.AnimationCurve':
            return None
        if self._is_unity_object(tn):
            return Node(name, 'pptr')
        rid = self.a.by_name.get(tn)
        if rid is None:
            return None
        if self.a.is_enum(rid):
            return Node(name, 'prim', prim=self._enum_underlying(rid), enum=tn)
        return self._class_node(name, rid, {}, depth)

    def _class_node(self, name, rid, argmap, depth):
        """inline-serialized class/struct: requires [Serializable]"""
        if not self.a.is_serializable(rid):
            return None
        return Node(name, 'struct', children=self.class_layout(rid, argmap, depth + 1))

    # ---- layout ----------------------------------------------------------
    def _chain(self, rid, subs, stop_at):
        """[(rid, subs)] ordered most-base first"""
        chain = []
        r, s = rid, dict(subs or {})
        while r is not None and len(chain) < 40:
            if stop_at and self.a.typedefs[r][0] == stop_at:
                break
            chain.append((r, s))
            btab, brid, bargs = self.a.base_of_full(r)
            if btab != 2 or brid is None or brid not in self.a.typedefs:
                break
            bname = self.a.typedefs[brid][0]
            if bname.startswith('UnityEngine.') or bname.startswith('System.'):
                if stop_at and bname == stop_at:
                    break
                if bname in ('System.Object', 'System.ValueType', 'System.Enum'):
                    break
            s = {i: self._subst(a, s) for i, a in enumerate(bargs)}
            r = brid
        chain.reverse()
        return chain

    def class_layout(self, rid, subs=None, depth=0, stop_at=None):
        """Serialized fields of a TypeDef, base classes first."""
        key = (rid, stop_at, tuple(sorted((i, repr(t)) for i, t in (subs or {}).items())))
        if key in self._cache:
            return self._cache[key]
        self._cache[key] = []              # guard against recursive types
        out = []
        for r, s in self._chain(rid, subs, stop_at):
            for nm, ty, fl, frid in self.a.fields_of(r):
                if fl & (F_STATIC | F_LITERAL | F_INITONLY | F_NOTSERIALIZED):
                    continue
                if (fl & F_PUBLIC) != F_PUBLIC:
                    fattrs = self.a.field_attrs(frid)
                    if not any('SerializeField' in x for x in fattrs):
                        continue
                n = self.node_for(nm, ty, s, depth)
                if n is not None:
                    out.append(n)
        self._cache[key] = out
        return out


class Buf:
    def __init__(self, data, pos=0):
        self.d = data; self.p = pos

    def prim(self, t):
        n = PRIM_SIZE[t]
        v = struct.unpack_from('<' + PRIM_FMT[t], self.d, self.p)[0]
        self.p += n
        if n < 4: self.align()
        return v

    def align(self, n=4):
        self.p = (self.p + n - 1) // n * n

    def string(self):
        n = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4
        if n < 0 or self.p + n > len(self.d): raise ValueError('bad string len %d' % n)
        s = self.d[self.p:self.p + n].decode('utf-8', 'replace'); self.p += n
        self.align()
        return s

    def pptr(self):
        fid, pid = struct.unpack_from('<iq', self.d, self.p); self.p += 12
        return {'file': fid, 'path': pid}


def read_guistyle(b):
    out = {}
    for name, t in GUISTYLE:
        if t is None:                      # explicit pad after a run of small fields
            b.align()
        elif t == 'string':
            out[name] = b.string()
        elif t == 'pptr':
            out[name] = b.pptr()
        elif t == 'byte':
            out[name] = struct.unpack_from('<B', b.d, b.p)[0]; b.p += 1
        else:
            out[name] = struct.unpack_from('<' + PRIM_FMT[t], b.d, b.p)[0]
            b.p += PRIM_SIZE[t]
    return out


def read_node(b, node):
    k = node.kind
    if k == 'prim':     return b.prim(node.prim)
    if k == 'string':   return b.string()
    if k == 'pptr':     return b.pptr()
    if k == 'guistyle': return read_guistyle(b)
    if k == 'struct': return {c.name: read_node(b, c) for c in node.children}
    if k == 'array':
        n = struct.unpack_from('<i', b.d, b.p)[0]; b.p += 4
        if n < 0 or n > 1 << 22: raise ValueError('bad array count %d' % n)
        out = [read_node(b, node.elem) for _ in range(n)]
        b.align()
        return out
    raise ValueError(k)


def read_monobehaviour(data, layout):
    """returns (dict, bytes_consumed)"""
    b = Buf(data)
    out = {}
    out['m_GameObject'] = b.pptr()
    out['m_Enabled'] = b.prim('byte')
    out['m_Script'] = b.pptr()
    out['m_Name'] = b.string()
    for node in layout:
        out[node.name] = read_node(b, node)
    return out, b.p
