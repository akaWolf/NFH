"""Turn an exported level JSON into something drawable.

Everything here follows docs/GAMEPLAY.md §8: sprites are screen-space blits from
sheet atlases, ordered by the GUIDepth enum, sized against a fixed 800x600
design resolution.
"""
import json, os

DESIGN_W, DESIGN_H = 800.0, 600.0

# lower value draws in front (Unity's GUI.depth convention)
GUI_DEPTH = {
    'BackItems': 72, 'BackDoors': 64, 'Items': 32, 'ItemsFront': 24,
    'Doors': 22, 'Alerters': 20, 'FrontDoors': 19, 'Rottweiler': 18,
    'Woody': 16, 'LevelFenceBack': 14, 'LevelFence': 13, 'BackHUD': 12,
    'HUD': 11, 'MainMenu': 10, 'Menu': 9, 'MainMenuControl': 8,
    'MainMenuFont': 7, 'ConfirmMessage': 2, 'MouseIcon': 1,
}

# the built-in Plane the levels use for their backdrop is 10x10 units
UNITY_PLANE_SIZE = 10.0


class Anim:
    __slots__ = ('name', 'sheet', 'cols', 'rows', 'start', 'end', 'fps',
                 'ow', 'oh', 'dx', 'dy', 'loop', 'hold', 'pattern')

    def __init__(self, d, base_path=''):
        self.name = d.get('Name')
        # AnimationInstance.LoadTexture does Resources.Load(BaseAnimationPath +
        # TextureFileName), so an empty TextureFileName means the base path is
        # itself the asset. Textures are extracted under their own name, which
        # is the last path component either way.
        self.sheet = os.path.basename((base_path or '') + (d.get('TextureFileName') or ''))
        self.cols = max(1, d.get('SheetColumns') or 1)
        self.rows = max(1, d.get('SheetRows') or 1)
        self.start = d.get('StartFrame') or 0
        self.end = d.get('EndFrame') or 0
        self.fps = d.get('FrameRate') or 10.0
        self.ow = d.get('OriginalWidth') or 0.0
        self.oh = d.get('OriginalHeight') or 0.0
        dl = d.get('DeltaLocation') or {}
        self.dx = dl.get('x', 0.0); self.dy = dl.get('y', 0.0)
        self.loop = bool(d.get('InfiniteLoop')) or d.get('Type') == 'Looping'
        self.hold = bool(d.get('HoldOnLastFrame'))
        self.pattern = d.get('Pattern') or None

    def frame_at(self, t):
        """frame index for elapsed time t, honouring Pattern when present"""
        if self.pattern:
            i = int(t * self.fps)
            if not self.loop and i >= len(self.pattern):
                i = len(self.pattern) - 1 if self.hold else i % len(self.pattern)
            return self.pattern[i % len(self.pattern)]
        n = self.end - self.start + 1
        if n <= 0:
            return self.start
        i = int(t * self.fps)
        if not self.loop and i >= n:
            i = n - 1 if self.hold else i % n
        return self.start + (i % n)


class Sprite:
    """one drawable: a world position, a depth, and an animation to play"""
    __slots__ = ('name', 'x', 'y', 'depth', 'anims', 'current', 'ctrl_dx',
                 'ctrl_dy', 'kind', 'go', 'hidden')

    def __init__(self, name, x, y, depth, anims, current, ctrl_dx, ctrl_dy,
                 kind, go=None):
        self.name = name; self.x = x; self.y = y; self.depth = depth
        self.anims = anims; self.current = current
        self.ctrl_dx = ctrl_dx; self.ctrl_dy = ctrl_dy; self.kind = kind
        self.go = go; self.hidden = False


class Zone:
    __slots__ = ('name', 'pid', 'x', 'y', 'w', 'h', 'exit')

    def __init__(self, name, pid, x, y, w, h, is_exit):
        self.name = name; self.pid = pid
        self.x = x; self.y = y
        self.w = w; self.h = h; self.exit = is_exit

    @property
    def left(self):
        return self.x - self.w * 0.5

    @property
    def right(self):
        return self.x + self.w * 0.5


class Door:
    """A zone link. Passing one plays an animation on the *door's* controller —
    the sheets contain the walking character, so the pawn hides during transit.
    """
    __slots__ = ('name', 'pid', 'x', 'y', 'zone', 'link_to', 'locked',
                 'door_type', 'enter', 'leave', 'sprite')

    def __init__(self, name, pid, x, y, zone, link_to, locked, door_type,
                 enter, leave):
        self.name = name; self.pid = pid; self.x = x; self.y = y
        self.zone = zone; self.link_to = link_to; self.locked = locked
        self.door_type = door_type; self.enter = enter; self.leave = leave
        self.sprite = None


class Level:
    def __init__(self, path):
        raw = json.load(open(path))
        self.path = path
        self._bg_texture = raw.get('background')
        self.scene = raw.get('unity_scene') or raw['scene']
        self.name = os.path.basename(self.scene).replace('.unity', '')
        self.objs = raw['objects']
        self._transform_of = {}
        self._comps = {}
        for pid, o in self.objs.items():
            if o['type'] == 'GameObject' and 'data' in o:
                comps = o['data']['components']
                self._comps[int(pid)] = comps
                for c in comps:
                    if c['type'] == 'Transform':
                        self._transform_of[int(pid)] = c['path']
        self.quads = raw.get('quads') or []          # world-space textured planes
        self.background = None      # (texture name, x, y, w, h) in world units
        self.sprites = []
        self.zones = []
        self.doors = []
        self.graph = {}             # zone pid -> [(neighbour pid, Door)]
        self.pawns = {}             # 'Woody' -> {'sprite','zone','speed'}
        self._build()

    # -- helpers ---------------------------------------------------------
    def _o(self, pid):
        return self.objs.get(str(pid))

    def _go_of(self, comp):
        d = comp.get('data') or {}
        g = d.get('gameObject')
        if g is None:
            g = (d.get('m_GameObject') or {}).get('path')
        return g

    def _transform(self, go):
        tp = self._transform_of.get(go)
        return self._o(tp)['data'] if tp else None

    @staticmethod
    def _pos(tr):
        """world position; the exporter composes the hierarchy for us"""
        return tr.get('world_position') or tr['position']

    def _component(self, go, type_name):
        for c in self._comps.get(go, []):
            if c['type'] == type_name:
                return self._o(c['path'])
        return None

    def _active(self, go):
        o = self._o(go)
        return bool(o and 'data' in o and o['data'].get('active'))

    # -- build -----------------------------------------------------------
    def _build(self):
        for pid, o in self.objs.items():
            t = o['type']
            if t == 'Zone' and 'data' in o:
                self._add_zone(o)
            elif t in ('Door', 'Transition') and 'data' in o:
                self._add_door(int(pid), o)
            elif t in ('ItemAnimationController', 'PawnAnimationController') and 'data' in o:
                self._add_sprite(o)
        self.sprites.sort(key=lambda s: -s.depth)      # far (high) first
        self._find_background()
        self._build_graph()
        self._find_pawns()

    def _add_zone(self, o):
        go = self._go_of(o)
        tr = self._transform(go)
        box = self._component(go, 'BoxCollider')
        if not tr or not box:
            return
        p = self._pos(tr); s = box['data']['size']; c = box['data']['center']
        self.zones.append(Zone(self._o(go)['data']['name'], go,
                               p[0] + c[0], p[1] + c[1], s[0], s[1],
                               bool(o['data'].get('ExitZone'))))

    def _zone_of(self, go):
        """the Zone component on this object's parent, as ZoneController does"""
        tp = self._transform_of.get(go)
        if tp is None:
            return None
        f = self._o(tp)['data'].get('father')
        if not f:
            return None
        pgo = self._o(f)['data'].get('gameObject')
        if pgo is None:
            return None
        for c in self._comps.get(pgo, []):
            if c['type'] == 'Zone':
                return pgo
        return None

    def _add_door(self, pid, o):
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        if not tr:
            return
        p = self._pos(tr)
        link = (d.get('LinkTo') or {}).get('path')
        self.doors.append(Door(self._o(go)['data']['name'], pid, p[0], p[1],
                               self._zone_of(go), link,
                               bool(d.get('Locked')), d.get('DoorType'),
                               d.get('WoodyEnterAnimation'),
                               d.get('WoodyLeaveAnimation')))

    def _build_graph(self):
        """Exactly ZoneController.Start(): a door links its own zone to the zone
        of whatever it points at."""
        by_pid = {d.pid: d for d in self.doors}
        self.graph = {z.pid: [] for z in self.zones}
        for d in self.doors:
            if d.zone is None or d.link_to is None or d.locked:
                continue
            other = by_pid.get(d.link_to)
            if other is None or other.zone is None:
                continue
            self.graph.setdefault(d.zone, []).append((other.zone, d))

    def find_path(self, start_pid, end_pid):
        """Zone pids from start to end, each with the door to walk through.
        Uniform edge cost, so BFS — Helpers.GetShortestPath adds 1.0 per hop."""
        import collections
        if start_pid == end_pid:
            return []
        prev = {start_pid: None}
        q = collections.deque([start_pid])
        while q:
            cur = q.popleft()
            for nb, door in self.graph.get(cur, ()):
                if nb in prev:
                    continue
                prev[nb] = (cur, door)
                if nb == end_pid:
                    out = []
                    n = nb
                    while prev[n]:
                        c, dr = prev[n]
                        out.append((n, dr))
                        n = c
                    out.reverse()
                    return out
                q.append(nb)
        return None

    def zone_at(self, x, y):
        for z in self.zones:
            if abs(x - z.x) <= z.w * 0.5 and abs(y - z.y) <= z.h * 0.5:
                return z
        return None

    def zone_by_pid(self, pid):
        for z in self.zones:
            if z.pid == pid:
                return z
        return None

    def door_by_pid(self, pid):
        for d in self.doors:
            if d.pid == pid:
                return d
        return None

    def _add_sprite(self, o):
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        if not tr or not self._active(go):
            return
        base = d.get('BaseAnimationPath') or ''
        anims = [Anim(a, base) for a in (d.get('Animations') or [])]
        anims = [a for a in anims if a.sheet]
        if not anims:
            return
        depth = GUI_DEPTH.get(d.get('AnimationGUIDepth'), 32)
        dl = d.get('DeltaLocation') or {}
        # pick the resting pose: an item's IdleNormal, a pawn's DefaultAnimation
        want = None
        # Door keeps its resting pose in IdleAnimation; every other Item uses
        # IdleNormal. 'NONE' means the object is a static quad, not a sprite.
        for owner_type, field in (('Door', 'IdleAnimation'),
                                  ('Transition', 'IdleAnimation'),
                                  ('TrickItem', 'IdleNormal'),
                                  ('SearchItem', 'IdleNormal'),
                                  ('HideItem', 'IdleNormal'),
                                  ('GroundItem', 'IdleNormal'),
                                  ('Alerter', 'IdleNormal'),
                                  ('InspectItem', 'IdleNormal')):
            item = self._component(go, owner_type)
            if item and 'data' in item:
                want = item['data'].get(field)
                break
        if want is None:
            for pawn_type in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
                pawn = self._component(go, pawn_type)
                if pawn and 'data' in pawn:
                    want = pawn['data'].get('DefaultAnimation')
                    break
        cur = None
        for i, a in enumerate(anims):
            if a.name == want:
                cur = i; break
        if cur is None:
            # no resting animation: either a pawn (first entry is its idle) or a
            # static object drawn as a quad instead
            if want in (None, 'NONE') and o['type'] == 'ItemAnimationController':
                return
            cur = 0
        p = self._pos(tr)
        self.sprites.append(Sprite(self._o(go)['data']['name'], p[0], p[1],
                                   depth, anims, cur,
                                   dl.get('x', 0.0), dl.get('y', 0.0),
                                   o['type'], go))

    def _find_pawns(self):
        """A pawn's sprite lives on a child object named AnimController, so map
        each pawn component to the sprite underneath it."""
        for pid, o in self.objs.items():
            if o['type'] not in ('Woody', 'Rottweiler', 'Olga', 'Mother', 'Kid'):
                continue
            if 'data' not in o:
                continue
            go = self._go_of(o)
            tp = self._transform_of.get(go)
            if tp is None:
                continue
            kids = self._o(tp)['data'].get('children') or []
            sprite = None
            for k in kids:
                kgo = self._o(k)['data'].get('gameObject')
                for s in self.sprites:
                    if s.kind == 'PawnAnimationController' and \
                            self._go_of_sprite(s) == kgo:
                        sprite = s
                        break
                if sprite:
                    break
            if sprite is None:
                continue
            # Zone is a pointer to the *component*; zones are keyed by their
            # GameObject, so hop across
            zc = (o['data'].get('Zone') or {}).get('path')
            zgo = self._go_of(self._o(zc)) if zc and self._o(zc) else None
            self.pawns[o['type']] = {
                'sprite': sprite,
                'zone': zgo,
                'speed': o['data'].get('Speed') or 1.25,
                'default': o['data'].get('DefaultAnimation'),
            }

    def _go_of_sprite(self, sprite):
        return getattr(sprite, 'go', None)

    def _find_background(self):
        """The backdrop is the quad carrying the Level component."""
        for q in self.quads:
            if q.get('is_level'):
                self.background = (q['texture'], q['x'], q['y'], q['w'], q['h'])
                return
