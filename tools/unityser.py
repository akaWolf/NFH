"""Minimal Unity SerializedFile (version 15 / Unity 5.3) reader.

Enough to enumerate the object table and pull MonoScript class names,
so we can tell how data-driven the scenes are. Read-only, no deps.
"""
import struct, sys, os

CLASS_NAMES = {
    0:'Object',1:'GameObject',2:'Component',3:'LevelGameManager',4:'Transform',
    5:'TimeManager',6:'GlobalGameManager',8:'Behaviour',9:'GameManager',
    11:'AudioManager',12:'ParticleAnimator',13:'InputManager',15:'EllipsoidParticleEmitter',
    17:'Pipeline',18:'EditorExtension',19:'Physics2DSettings',20:'Camera',
    21:'Material',23:'MeshRenderer',25:'Renderer',26:'ParticleRenderer',
    27:'Texture',28:'Texture2D',29:'SceneSettings',30:'GraphicsSettings',
    33:'MeshFilter',41:'OcclusionPortal',43:'Mesh',45:'Skybox',47:'QualitySettings',
    48:'Shader',49:'TextAsset',50:'Rigidbody2D',51:'Physics2DManager',
    53:'Collider2D',54:'Rigidbody',55:'PhysicsManager',56:'Collider',
    57:'Joint',58:'CircleCollider2D',59:'HingeJoint',60:'PolygonCollider2D',
    61:'BoxCollider2D',62:'PhysicsMaterial2D',64:'MeshCollider',65:'BoxCollider',
    66:'SpriteCollider2D',68:'EdgeCollider2D',72:'ComputeShader',74:'AnimationClip',
    75:'ConstantForce',78:'TagManager',81:'AudioListener',82:'AudioSource',
    83:'AudioClip',84:'RenderTexture',87:'AnimatorController',89:'Cubemap',
    90:'Avatar',91:'AnimatorController',93:'RuntimeAnimatorController',
    95:'Animator',96:'TrailRenderer',98:'DelayedCallManager',102:'TextMesh',
    104:'RenderSettings',108:'Light',109:'CGProgram',111:'Animation',
    114:'MonoBehaviour',115:'MonoScript',116:'MonoManager',117:'Texture3D',
    119:'Projector',120:'LineRenderer',121:'Flare',122:'Halo',123:'LensFlare',
    124:'FlareLayer',125:'HaloLayer',126:'NavMeshAreas',127:'HaloManager',
    128:'Font',129:'PlayerSettings',130:'NamedObject',131:'GUITexture',
    132:'GUIText',133:'GUIElement',134:'PhysicMaterial',135:'SphereCollider',
    136:'CapsuleCollider',137:'SkinnedMeshRenderer',138:'FixedJoint',
    141:'BuildSettings',142:'AssetBundle',143:'CharacterController',
    150:'PreloadData',152:'MovieTexture',153:'ConfigurableJoint',
    156:'TerrainData',157:'LightmapSettings',158:'WebCamTexture',
    159:'EditorSettings',162:'EditorUserSettings',164:'AudioReverbFilter',
    166:'AudioHighPassFilter',180:'AudioLowPassFilter',181:'AudioEchoFilter',
    182:'AudioChorusFilter',183:'AudioReverbZone',184:'WindZone',
    191:'AudioBehaviour',196:'NavMeshSettings',197:'LightProbes',
    198:'ParticleSystem',199:'ParticleSystemRenderer',200:'ShaderVariantCollection',
    205:'LODGroup',206:'BlendTree',207:'Motion',208:'NavMeshObstacle',
    212:'SpriteRenderer',213:'Sprite',214:'CachedSpriteAtlas',215:'ReflectionProbe',
    218:'Terrain',220:'LightProbeGroup',221:'AnimatorOverrideController',
    222:'CanvasRenderer',223:'Canvas',224:'RectTransform',225:'CanvasGroup',
    226:'BillboardAsset',227:'BillboardRenderer',228:'SpeedTreeWindAsset',
    229:'AnchoredJoint2D',230:'Joint2D',231:'SpringJoint2D',232:'DistanceJoint2D',
    233:'HingeJoint2D',234:'SliderJoint2D',235:'WheelJoint2D',
    241:'AudioMixer',243:'AudioMixerGroup',244:'AudioMixerSnapshot',
    245:'PhysicsUpdateBehaviour2D',246:'ConstantForce2D',247:'Effector2D',
    248:'AreaEffector2D',249:'PointEffector2D',250:'PlatformEffector2D',
    251:'SurfaceEffector2D',258:'LightProbeProxyVolume',271:'SketchUpImporter',
    290:'AssetBundleManifest',1001:'Prefab',1002:'EditorExtensionImpl',
}


class Reader:
    def __init__(self, data, pos=0, little=True):
        self.d = data; self.p = pos; self.e = '<' if little else '>'

    def u(self, fmt, n):
        v = struct.unpack_from(self.e + fmt, self.d, self.p); self.p += n; return v[0]

    i8  = lambda s: s.u('b', 1)
    u8  = lambda s: s.u('B', 1)
    i16 = lambda s: s.u('h', 2)
    u16 = lambda s: s.u('H', 2)
    i32 = lambda s: s.u('i', 4)
    u32 = lambda s: s.u('I', 4)
    i64 = lambda s: s.u('q', 8)

    def raw(self, n):
        b = self.d[self.p:self.p + n]; self.p += n; return b

    def align(self, n=4):
        self.p = (self.p + n - 1) // n * n

    def cstr(self):
        e = self.d.index(b'\0', self.p)
        s = self.d[self.p:e].decode('utf-8', 'replace'); self.p = e + 1; return s

    def astr(self):
        """Aligned length-prefixed string, as used inside object payloads."""
        n = self.i32()
        if n < 0 or n > 1 << 20:
            raise ValueError('bad string length %d' % n)
        s = self.raw(n).decode('utf-8', 'replace'); self.align(4); return s


class SerializedFile:
    def __init__(self, path):
        self.path = path
        self.d = open(path, 'rb').read()
        h = Reader(self.d, 0, little=False)
        self.metadata_size = h.u32()
        self.file_size = h.u32()
        self.version = h.u32()
        self.data_offset = h.u32()
        self.endian = h.u8()
        h.raw(3)
        if self.version != 15:
            raise NotImplementedError('version %d not handled' % self.version)
        r = Reader(self.d, h.p, little=(self.endian == 0))
        self.unity_version = r.cstr()
        self.target_platform = r.i32()
        self.enable_type_tree = r.u8()

        self.types = []
        for _ in range(r.i32()):
            cid = r.i32()
            script_id = r.raw(16) if cid < 0 else None
            old_hash = r.raw(16)
            if self.enable_type_tree:
                raise NotImplementedError('type tree present')
            self.types.append({'class_id': cid, 'script_id': script_id, 'hash': old_hash})

        self.objects = []
        for _ in range(r.i32()):
            r.align(4)
            path_id = r.i64()
            byte_start = r.u32()
            byte_size = r.u32()
            type_id = r.i32()
            class_id = r.u16()
            script_type_index = r.i16()
            stripped = r.u8()
            self.objects.append({
                'path_id': path_id,
                'start': self.data_offset + byte_start,
                'size': byte_size,
                'type_id': type_id,
                'class_id': class_id,
                'script_type_index': script_type_index,
            })

        self.script_refs = []
        for _ in range(r.i32()):
            idx = r.i32(); r.align(4); self.script_refs.append((idx, r.i64()))

        self.externals = []
        for _ in range(r.i32()):
            r.cstr()                      # temp empty
            guid = r.raw(16); typ = r.i32(); self.externals.append((guid.hex(), typ, r.cstr()))

    def body(self, o):
        return self.d[o['start']:o['start'] + o['size']]

    def mono_scripts(self):
        """path_id -> class name, by parsing MonoScript (class 115) payloads."""
        out = {}
        for o in self.objects:
            if o['class_id'] != 115:
                continue
            try:
                r = Reader(self.body(o), 0, little=(self.endian == 0))
                r.astr()          # m_Name
                r.i32()           # m_ExecutionOrder
                r.raw(16)         # m_PropertiesHash (Hash128)
                cls = r.astr()    # m_ClassName
                ns = r.astr()     # m_Namespace
                asm = r.astr()    # m_AssemblyName
                out[o['path_id']] = (ns + '.' + cls) if ns else cls
            except Exception:
                out[o['path_id']] = '<unparsed>'
        return out

    def monobehaviour_script_ref(self, o):
        """MonoBehaviour payload starts with m_GameObject, m_Enabled, m_Script PPtr."""
        r = Reader(self.body(o), 0, little=(self.endian == 0))
        r.i32(); r.i64()          # m_GameObject PPtr (file_id int32, path_id int64)
        r.u8(); r.align(4)        # m_Enabled + pad
        file_id = r.i32(); path_id = r.i64()
        return file_id, path_id


if __name__ == '__main__':
    for p in sys.argv[1:]:
        f = SerializedFile(p)
        print('%-12s v%d %s plat=%d objs=%-6d types=%-4d ext=%d'
              % (os.path.basename(p), f.version, f.unity_version,
                 f.target_platform, len(f.objects), len(f.types), len(f.externals)))
