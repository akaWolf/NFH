"""ECMA-335 metadata reader.

Recovers class -> field layout from Assembly-CSharp.dll, which is exactly the
schema Unity used to serialize MonoBehaviour payloads into the scene files.
"""
import struct

# canonical table ids
MODULE, TYPEREF, TYPEDEF, FIELDPTR, FIELD = 0x00, 0x01, 0x02, 0x03, 0x04
METHODPTR, METHODDEF, PARAMPTR, PARAM = 0x05, 0x06, 0x07, 0x08
INTERFACEIMPL, MEMBERREF, CONSTANT, CUSTOMATTRIBUTE = 0x09, 0x0A, 0x0B, 0x0C
DECLSECURITY, STANDALONESIG, EVENTMAP, EVENT = 0x0E, 0x11, 0x12, 0x14
PROPERTYMAP, PROPERTY, MODULEREF, TYPESPEC = 0x15, 0x17, 0x1A, 0x1B
ASSEMBLY, ASSEMBLYREF, FILE, EXPORTEDTYPE = 0x20, 0x23, 0x26, 0x27
MANIFESTRESOURCE, NESTEDCLASS, GENERICPARAM = 0x28, 0x29, 0x2A
METHODSPEC, GENERICPARAMCONSTRAINT = 0x2B, 0x2C

CODED = {
 'TypeDefOrRef':       (2, [TYPEDEF, TYPEREF, TYPESPEC]),
 'HasConstant':        (2, [FIELD, PARAM, PROPERTY]),
 'HasCustomAttribute': (5, [METHODDEF, FIELD, TYPEREF, TYPEDEF, PARAM, INTERFACEIMPL,
                            MEMBERREF, MODULE, DECLSECURITY, PROPERTY, EVENT,
                            STANDALONESIG, MODULEREF, TYPESPEC, ASSEMBLY, ASSEMBLYREF,
                            FILE, EXPORTEDTYPE, MANIFESTRESOURCE, GENERICPARAM,
                            GENERICPARAMCONSTRAINT, METHODSPEC]),
 'HasFieldMarshal':    (1, [FIELD, PARAM]),
 'HasDeclSecurity':    (2, [TYPEDEF, METHODDEF, ASSEMBLY]),
 'MemberRefParent':    (3, [TYPEDEF, TYPEREF, MODULEREF, METHODDEF, TYPESPEC]),
 'HasSemantics':       (1, [EVENT, PROPERTY]),
 'MethodDefOrRef':     (1, [METHODDEF, MEMBERREF]),
 'MemberForwarded':    (1, [FIELD, METHODDEF]),
 'Implementation':     (2, [FILE, ASSEMBLYREF, EXPORTEDTYPE]),
 'CustomAttributeType':(3, [-1, -1, METHODDEF, MEMBERREF, -1]),
 'ResolutionScope':    (2, [MODULE, MODULEREF, ASSEMBLYREF, TYPEREF]),
 'TypeOrMethodDef':    (1, [TYPEDEF, METHODDEF]),
}

C = lambda n: ('c', n)
T = lambda t: ('t', t)

SCHEMA = {
 0x00: [('Generation','u16'),('Name','str'),('Mvid','guid'),('EncId','guid'),('EncBaseId','guid')],
 0x01: [('ResolutionScope',C('ResolutionScope')),('Name','str'),('Namespace','str')],
 0x02: [('Flags','u32'),('Name','str'),('Namespace','str'),('Extends',C('TypeDefOrRef')),
        ('FieldList',T(FIELD)),('MethodList',T(METHODDEF))],
 0x03: [('Field',T(FIELD))],
 0x04: [('Flags','u16'),('Name','str'),('Signature','blob')],
 0x05: [('Method',T(METHODDEF))],
 0x06: [('RVA','u32'),('ImplFlags','u16'),('Flags','u16'),('Name','str'),
        ('Signature','blob'),('ParamList',T(PARAM))],
 0x07: [('Param',T(PARAM))],
 0x08: [('Flags','u16'),('Sequence','u16'),('Name','str')],
 0x09: [('Class',T(TYPEDEF)),('Interface',C('TypeDefOrRef'))],
 0x0A: [('Class',C('MemberRefParent')),('Name','str'),('Signature','blob')],
 0x0B: [('Type','u8'),('Padding','u8'),('Parent',C('HasConstant')),('Value','blob')],
 0x0C: [('Parent',C('HasCustomAttribute')),('Type',C('CustomAttributeType')),('Value','blob')],
 0x0D: [('Parent',C('HasFieldMarshal')),('NativeType','blob')],
 0x0E: [('Action','u16'),('Parent',C('HasDeclSecurity')),('PermissionSet','blob')],
 0x0F: [('PackingSize','u16'),('ClassSize','u32'),('Parent',T(TYPEDEF))],
 0x10: [('Offset','u32'),('Field',T(FIELD))],
 0x11: [('Signature','blob')],
 0x12: [('Parent',T(TYPEDEF)),('EventList',T(EVENT))],
 0x13: [('Event',T(EVENT))],
 0x14: [('EventFlags','u16'),('Name','str'),('EventType',C('TypeDefOrRef'))],
 0x15: [('Parent',T(TYPEDEF)),('PropertyList',T(PROPERTY))],
 0x16: [('Property',T(PROPERTY))],
 0x17: [('Flags','u16'),('Name','str'),('Type','blob')],
 0x18: [('Semantics','u16'),('Method',T(METHODDEF)),('Association',C('HasSemantics'))],
 0x19: [('Class',T(TYPEDEF)),('MethodBody',C('MethodDefOrRef')),('MethodDeclaration',C('MethodDefOrRef'))],
 0x1A: [('Name','str')],
 0x1B: [('Signature','blob')],
 0x1C: [('MappingFlags','u16'),('MemberForwarded',C('MemberForwarded')),
        ('ImportName','str'),('ImportScope',T(MODULEREF))],
 0x1D: [('RVA','u32'),('Field',T(FIELD))],
 0x1E: [('Token','u32'),('FuncCode','u32')],
 0x1F: [('Token','u32')],
 0x20: [('HashAlgId','u32'),('Major','u16'),('Minor','u16'),('Build','u16'),('Rev','u16'),
        ('Flags','u32'),('PublicKey','blob'),('Name','str'),('Culture','str')],
 0x21: [('Processor','u32')],
 0x22: [('OSPlatformID','u32'),('OSMajor','u32'),('OSMinor','u32')],
 0x23: [('Major','u16'),('Minor','u16'),('Build','u16'),('Rev','u16'),('Flags','u32'),
        ('PublicKey','blob'),('Name','str'),('Culture','str'),('HashValue','blob')],
 0x24: [('Processor','u32'),('AssemblyRef',T(ASSEMBLYREF))],
 0x25: [('OSPlatformID','u32'),('OSMajor','u32'),('OSMinor','u32'),('AssemblyRef',T(ASSEMBLYREF))],
 0x26: [('Flags','u32'),('Name','str'),('HashValue','blob')],
 0x27: [('Flags','u32'),('TypeDefId','u32'),('Name','str'),('Namespace','str'),
        ('Implementation',C('Implementation'))],
 0x28: [('Offset','u32'),('Flags','u32'),('Name','str'),('Implementation',C('Implementation'))],
 0x29: [('NestedClass',T(TYPEDEF)),('EnclosingClass',T(TYPEDEF))],
 0x2A: [('Number','u16'),('Flags','u16'),('Owner',C('TypeOrMethodDef')),('Name','str')],
 0x2B: [('Method',C('MethodDefOrRef')),('Instantiation','blob')],
 0x2C: [('Owner',T(GENERICPARAM)),('Constraint',C('TypeDefOrRef'))],
}

ET_PRIM = {0x02:'bool',0x03:'char',0x04:'sbyte',0x05:'byte',0x06:'short',0x07:'ushort',
           0x08:'int',0x09:'uint',0x0a:'long',0x0b:'ulong',0x0c:'float',0x0d:'double',
           0x18:'IntPtr',0x19:'UIntPtr'}

# FieldAttributes
F_STATIC, F_INITONLY, F_LITERAL, F_NOTSERIALIZED = 0x10, 0x20, 0x40, 0x80
F_PUBLIC = 0x06


class Type:
    """decoded signature type"""
    __slots__ = ('kind', 'name', 'elem', 'args', 'tab', 'rid')

    def __init__(self, kind, name=None, elem=None, args=None, tab=None, rid=None):
        self.kind = kind          # prim|string|object|ref|array|generic|ptr|var
        self.name = name
        self.elem = elem
        self.args = args or []
        self.tab = tab
        self.rid = rid

    def __repr__(self):
        if self.kind == 'array': return repr(self.elem) + '[]'
        if self.kind == 'generic': return '%s<%s>' % (self.name, ','.join(map(repr, self.args)))
        return self.name or self.kind


class Assembly:
    def __init__(self, path):
        d = open(path, 'rb').read(); self.d = d
        pe = struct.unpack_from('<I', d, 0x3c)[0]
        nsec, = struct.unpack_from('<H', d, pe + 6)
        optsz, = struct.unpack_from('<H', d, pe + 20)
        magic, = struct.unpack_from('<H', d, pe + 24)
        self.secs = []
        for i in range(nsec):
            o = pe + 24 + optsz + i * 40
            vsz, va, rsz, ra = struct.unpack_from('<IIII', d, o + 8)
            self.secs.append((va, vsz, ra))
        ddir = pe + 24 + (96 if magic == 0x10b else 112)
        cli = self.rva(struct.unpack_from('<I', d, ddir + 14 * 8)[0])
        md = self.rva(struct.unpack_from('<I', d, cli + 8)[0])
        vlen, = struct.unpack_from('<I', d, md + 12)
        p = md + 16 + ((vlen + 3) // 4 * 4)
        nstreams, = struct.unpack_from('<H', d, p + 2); p += 4
        self.streams = {}
        for _ in range(nstreams):
            off, size = struct.unpack_from('<II', d, p); p += 8
            e = d.index(b'\0', p); name = d[p:e].decode(); p = (e + 1 + 3) // 4 * 4
            self.streams[name] = (md + off, size)
        self.strings = self.streams['#Strings'][0]
        self.blobs = self.streams.get('#Blob', (0, 0))[0]
        tp = self.streams['#~'][0]
        hs = d[tp + 6]
        self.str_w = 4 if hs & 1 else 2
        self.guid_w = 4 if hs & 2 else 2
        self.blob_w = 4 if hs & 4 else 2
        valid, _sorted = struct.unpack_from('<QQ', d, tp + 8)
        self.rows = {}
        q = tp + 24
        for i in range(64):
            if valid >> i & 1:
                self.rows[i], = struct.unpack_from('<I', d, q); q += 4
        self.tables = {}
        for i in sorted(self.rows):
            cols = SCHEMA[i]
            widths = [self.width(k) for _, k in cols]
            self.tables[i] = (q, sum(widths), cols, widths)
            q += sum(widths) * self.rows[i]
        self._build_index()

    # ---- low level -------------------------------------------------------
    def rva(self, r):
        for va, vsz, ra in self.secs:
            if va <= r < va + vsz: return ra + (r - va)
        raise ValueError(hex(r))

    def width(self, kind):
        if kind == 'u8': return 1
        if kind == 'u16': return 2
        if kind == 'u32': return 4
        if kind == 'str': return self.str_w
        if kind == 'blob': return self.blob_w
        if kind == 'guid': return self.guid_w
        if kind[0] == 't':
            return 4 if self.rows.get(kind[1], 0) >= (1 << 16) else 2
        bits, tabs = CODED[kind[1]]
        mx = max((self.rows.get(t, 0) for t in tabs if t >= 0), default=0)
        return 4 if mx >= (1 << (16 - bits)) else 2

    def row(self, tid, idx):
        base, rw, cols, widths = self.tables[tid]
        o = base + (idx - 1) * rw
        out = {}
        for (nm, kind), w in zip(cols, widths):
            out[nm] = int.from_bytes(self.d[o:o + w], 'little'); o += w
        return out

    def decode_coded(self, name, val):
        bits, tabs = CODED[name]
        tag = val & ((1 << bits) - 1)
        return (tabs[tag] if tag < len(tabs) else -1), val >> bits

    def s(self, off):
        e = self.d.index(b'\0', self.strings + off)
        return self.d[self.strings + off:e].decode('utf-8', 'replace')

    def blob(self, off):
        p = self.blobs + off
        n = self.d[p]
        if n & 0x80 == 0: p += 1
        elif n & 0x40 == 0: n = ((n & 0x3f) << 8) | self.d[p+1]; p += 2
        else: n = ((n & 0x1f) << 24) | (self.d[p+1] << 16) | (self.d[p+2] << 8) | self.d[p+3]; p += 4
        return self.d[p:p + n]

    # ---- signatures ------------------------------------------------------
    @staticmethod
    def _cint(b, i):
        n = b[i]
        if n & 0x80 == 0: return n, i + 1
        if n & 0x40 == 0: return ((n & 0x3f) << 8) | b[i+1], i + 2
        return ((n & 0x1f) << 24) | (b[i+1] << 16) | (b[i+2] << 8) | b[i+3], i + 4

    def sigtype(self, b, i=0):
        t = b[i]; i += 1
        if t in ET_PRIM: return Type('prim', ET_PRIM[t]), i
        if t == 0x0e: return Type('string', 'string'), i
        if t == 0x1c: return Type('object', 'object'), i
        if t == 0x01: return Type('prim', 'void'), i
        if t in (0x11, 0x12):
            tok, i = self._cint(b, i)
            tab = [TYPEDEF, TYPEREF, TYPESPEC][tok & 3]; rid = tok >> 2
            return Type('ref', self.typename(tab, rid), tab=tab, rid=rid), i
        if t == 0x1d:
            inner, i = self.sigtype(b, i); return Type('array', elem=inner), i
        if t == 0x14:
            inner, i = self.sigtype(b, i)
            rank, i = self._cint(b, i)
            nsizes, i = self._cint(b, i)
            for _ in range(nsizes): _, i = self._cint(b, i)
            nlo, i = self._cint(b, i)
            for _ in range(nlo): _, i = self._cint(b, i)
            return Type('mdarray', elem=inner), i
        if t == 0x15:
            base, i = self.sigtype(b, i)
            cnt, i = self._cint(b, i)
            args = []
            for _ in range(cnt):
                a, i = self.sigtype(b, i); args.append(a)
            return Type('generic', base.name, args=args, tab=base.tab, rid=base.rid), i
        if t in (0x1f, 0x20):
            _, i = self._cint(b, i); return self.sigtype(b, i)
        if t == 0x45:                      # PINNED
            return self.sigtype(b, i)
        if t in (0x0f, 0x10):              # PTR / BYREF
            inner, i = self.sigtype(b, i); return Type('ptr', elem=inner), i
        if t in (0x13, 0x1e):              # VAR / MVAR
            n, i = self._cint(b, i); return Type('var', 'T%d' % n, rid=n), i
        return Type('prim', 'et0x%02x' % t), i

    def typename(self, tab, rid):
        if tab == TYPEDEF:
            r = self.row(TYPEDEF, rid)
        elif tab == TYPEREF:
            r = self.row(TYPEREF, rid)
        else:
            return 'TypeSpec#%d' % rid
        ns, n = self.s(r['Namespace']), self.s(r['Name'])
        return (ns + '.' + n) if ns else n

    # ---- index -----------------------------------------------------------
    def _build_index(self):
        self._mowner = None
        self.by_name = {}
        self.typedefs = {}
        for rid in range(1, self.rows[TYPEDEF] + 1):
            r = self.row(TYPEDEF, rid)
            ns, n = self.s(r['Namespace']), self.s(r['Name'])
            full = (ns + '.' + n) if ns else n
            self.typedefs[rid] = (full, r)
            self.by_name[full] = rid
        # custom attributes: (table, rid) -> [attr type name]
        self.attrs = {}
        for i in range(1, self.rows.get(CUSTOMATTRIBUTE, 0) + 1):
            r = self.row(CUSTOMATTRIBUTE, i)
            ptab, prid = self.decode_coded('HasCustomAttribute', r['Parent'])
            ctab, crid = self.decode_coded('CustomAttributeType', r['Type'])
            name = self._ctor_type(ctab, crid)
            self.attrs.setdefault((ptab, prid), []).append(name)

    def _method_owner(self, mrid):
        if self._mowner is None:
            m = {}
            n = self.rows[TYPEDEF]
            for rid in range(1, n + 1):
                start = self.typedefs[rid][1]['MethodList']
                end = (self.row(TYPEDEF, rid + 1)['MethodList'] if rid < n
                       else self.rows[METHODDEF] + 1)
                for k in range(start, end): m[k] = rid
            self._mowner = m
        return self._mowner.get(mrid)

    def _ctor_type(self, ctab, crid):
        if ctab == METHODDEF:
            owner = self._method_owner(crid)
            return self.typedefs[owner][0] if owner else '?'
        if ctab == MEMBERREF:
            r = self.row(MEMBERREF, crid)
            tab, rid = self.decode_coded('MemberRefParent', r['Class'])
            return self.typename(tab, rid)
        return '?'

    # ---- public ----------------------------------------------------------
    def fields_of(self, rid):
        """[(name, Type, flags)] in declaration order"""
        n = self.rows[TYPEDEF]
        start = self.typedefs[rid][1]['FieldList']
        end = (self.row(TYPEDEF, rid + 1)['FieldList'] if rid < n else self.rows[FIELD] + 1)
        out = []
        for f in range(start, end):
            fr = self.row(FIELD, f)
            try:
                ty, _ = self.sigtype(self.blob(fr['Signature']), 1)
            except Exception:
                ty = Type('prim', '?')
            out.append((self.s(fr['Name']), ty, fr['Flags'], f))
        return out

    def methods_of(self, rid):
        n = self.rows[TYPEDEF]
        start = self.typedefs[rid][1]['MethodList']
        end = (self.row(TYPEDEF, rid + 1)['MethodList'] if rid < n else self.rows[METHODDEF] + 1)
        return end - start

    def base_of(self, rid):
        """(table, rid) of the base type, or (None, None)"""
        tab, brid, _ = self.base_of_full(rid)
        return tab, brid

    def base_of_full(self, rid):
        """(table, rid, generic_args) — resolves a TypeSpec base to its TypeDef."""
        ext = self.typedefs[rid][1]['Extends']
        if ext == 0: return None, None, []
        tab, brid = self.decode_coded('TypeDefOrRef', ext)
        if tab != TYPESPEC:
            return tab, brid, []
        ty, _ = self.sigtype(self.blob(self.row(TYPESPEC, brid)['Signature']), 0)
        if ty.kind == 'generic':
            return ty.tab, ty.rid, ty.args
        if ty.kind == 'ref':
            return ty.tab, ty.rid, []
        return None, None, []

    def base_name(self, rid):
        tab, brid = self.base_of(rid)
        if tab is None or brid is None: return None
        return self.typename(tab, brid)

    def is_serializable(self, rid):
        """[System.Serializable] is emitted as TypeAttributes.Serializable, not an attribute."""
        return bool(self.typedefs[rid][1]['Flags'] & 0x2000)

    def type_attrs(self, rid):
        return self.attrs.get((TYPEDEF, rid), [])

    def field_attrs(self, frid):
        return self.attrs.get((FIELD, frid), [])

    def is_enum(self, rid):
        return self.base_name(rid) == 'System.Enum'

    def _constants(self):
        """field row -> literal value, from the Constant table"""
        if getattr(self, '_consts', None) is None:
            m = {}
            for i in range(1, self.rows.get(CONSTANT, 0) + 1):
                r = self.row(CONSTANT, i)
                ptab, prid = self.decode_coded('HasConstant', r['Parent'])
                if ptab != FIELD: continue
                raw = self.blob(r['Value'])
                t = r['Type']
                fmt = {0x04:'b',0x05:'B',0x06:'h',0x07:'H',0x08:'i',0x09:'I',
                       0x0a:'q',0x0b:'Q'}.get(t)
                if fmt and len(raw) >= struct.calcsize(fmt):
                    m[prid] = struct.unpack_from('<' + fmt, raw)[0]
            self._consts = m
        return self._consts

    def enum_values(self, rid):
        """enum TypeDef -> {value: name}"""
        consts = self._constants()
        out = {}
        for nm, ty, fl, frid in self.fields_of(rid):
            if not (fl & F_LITERAL): continue
            v = consts.get(frid)
            if v is not None and v not in out:
                out[v] = nm
        return out
