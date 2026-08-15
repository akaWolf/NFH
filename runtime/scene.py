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
                 'ow', 'oh', 'dx', 'dy', 'loop', 'hold', 'pattern',
                 'infinite', 'type_looping')

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
        # two independent things: InfiniteLoop is a runtime flag that always
        # wins, while Type==Looping only applies when the animation is started
        # as a looping one — PlaySingleAnimation overrides the type to Single.
        self.infinite = bool(d.get('InfiniteLoop'))
        self.type_looping = d.get('Type') == 'Looping'
        self.loop = self.infinite or self.type_looping
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
    __slots__ = ('name', 'pid', 'x', 'y', 'w', 'h', 'exit',
                 'play_left', 'play_right')

    def __init__(self, name, pid, x, y, w, h, is_exit):
        self.name = name; self.pid = pid
        self.x = x; self.y = y
        self.w = w; self.h = h; self.exit = is_exit
        # Level.SetPlayLeft/SetPlayRight, filled in from the Level component;
        # the collider box is containment, these are the walking limits
        self.play_left = x - w * 0.5
        self.play_right = x + w * 0.5

    @property
    def left(self):
        return self.play_left

    @property
    def right(self):
        return self.play_right


class Item:
    """Anything the neighbour's routine can act on, or Woody can trick."""
    __slots__ = ('name', 'pid', 'kind', 'x', 'y', 'zone', 'dx', 'dy',
                 'use_distance', 'delta_olga_x', 'delta_mother_x',
                 'use_anim', 'use_tricked_anim', 'idle', 'idle_tricked', 'animating',
                 'required_inventory', 'trick_score', 'anger', 'sprite',
                 'tricked', 'got_tricked', 'already_tricked', 'depends_on',
                 'use_at_other_place', 'neutral')

    def __init__(self, name, pid, kind, x, y, zone, dx, dy, d):
        self.name = name; self.pid = pid; self.kind = kind
        self.x = x; self.y = y; self.zone = zone
        self.dx = dx; self.dy = dy
        # each pawn type has its own use sequence; an empty one means this
        # item is simply not that character's to use
        self.use_anim = {
            'Rottweiler': d.get('RottweilerUseAnimation') or [],
            'Olga': d.get('OlgaUseAnimation') or [],
            'Mother': d.get('MotherUseAnimation') or [],
        }
        self.use_tricked_anim = {
            'Rottweiler': d.get('RottweilerUseTrickedAnimation') or [],
            'Olga': d.get('OlgaUseTrickedAnimation') or [],
            'Mother': d.get('MotherUseTrickedAnimation') or [],
        }
        self.idle = d.get('IdleNormal')
        self.idle_tricked = d.get('IdleTricked')
        # PlayItemAnimation is a no-op unless Animating, and skips NONE outright
        self.animating = bool(d.get('Animating'))
        self.use_distance = d.get('UseDistance') or 0.01
        self.delta_olga_x = (d.get('DeltaOlgaLocation') or {}).get('x', 0.0)
        self.delta_mother_x = (d.get('DeltaMotherLocation') or {}).get('x', 0.0)
        self.required_inventory = d.get('RequiredInventory')
        self.trick_score = d.get('TrickScore') or 0
        self.anger = d.get('AngerAmount') or 0
        self.depends_on = (d.get('DependsOn') or {}).get('path')
        self.use_at_other_place = bool(d.get('UseAtOtherPlace'))
        self.neutral = bool(d.get('Neutral'))
        self.sprite = None
        self.tricked = bool(d.get('Tricked'))
        self.got_tricked = False
        self.already_tricked = False

    @property
    def target_x(self):
        """Item.TargetLocation = position + DeltaLocation"""
        return self.x + self.dx

    def move_x(self, role):
        """Item.GetMoveLocation: Olga and Mother stand offset, everyone else
        at TargetLocation itself."""
        if role == 'Olga':
            return self.target_x + self.delta_olga_x
        if role == 'Mother':
            return self.target_x + self.delta_mother_x
        return self.target_x

    def sequence_for(self, role, tricked):
        """Item.PlayAnimation picks one array and plays it. No fallback: an
        empty array means this character has no business using the item."""
        table = self.use_tricked_anim if tricked else self.use_anim
        return table.get(role) or []

    def is_tricked(self):
        """TrickItem.IsTricked for the states reachable outside a live trick"""
        return self.tricked and not self.use_at_other_place and not self.neutral


class Door:
    """A zone link. Passing one plays an animation on the *door's* controller —
    the sheets contain the walking character, so the pawn hides during transit.
    """
    __slots__ = ('name', 'pid', 'x', 'y', 'zone', 'link_to', 'locked',
                 'door_type', 'enter', 'leave', 'rott_enter', 'rott_leave',
                 'exit_anim', 'idle', 'sprite', 'passing')

    def __init__(self, name, pid, x, y, zone, link_to, locked, door_type, d):
        self.name = name; self.pid = pid; self.x = x; self.y = y
        self.zone = zone; self.link_to = link_to; self.locked = locked
        self.door_type = door_type
        # enter/leave are ItemAnimationState and play on the door; ExitAnimation
        # is an AnimationState and loops on the pawn once it is through
        self.enter = d.get('WoodyEnterAnimation')
        self.leave = d.get('WoodyLeaveAnimation')
        self.rott_enter = d.get('RottweilerEnterAnimation')
        self.rott_leave = d.get('RottweilerLeaveAnimation')
        self.exit_anim = d.get('ExitAnimation')
        self.idle = d.get('IdleAnimation')
        self.sprite = None
        self.passing = None                 # Door.PassingPawn


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
        self.items = {}             # component pid -> Item
        self.routines = []          # ActionManager models
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
            elif t in ('TrickItem', 'SearchItem', 'HideItem', 'GroundItem',
                       'InspectItem', 'Alerter') and 'data' in o:
                self._add_item(int(pid), o)
            elif t in ('ItemAnimationController', 'PawnAnimationController') and 'data' in o:
                self._add_sprite(o)
        self.sprites.sort(key=lambda s: -s.depth)      # far (high) first
        self._find_background()
        self._build_graph()
        self._find_pawns()
        self._link_item_sprites()
        self._find_routines()
        self._apply_zone_bounds()

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
                               bool(d.get('Locked')), d.get('DoorType'), d))

    def _add_item(self, pid, o):
        d = o['data']
        go = self._go_of(o)
        tr = self._transform(go)
        if not tr:
            return
        p = self._pos(tr)
        dl = d.get('DeltaLocation') or {}
        zc = (d.get('Zone') or {}).get('path')
        zgo = self._go_of(self._o(zc)) if zc and self._o(zc) else None
        self.items[pid] = Item(self._o(go)['data']['name'], pid, o['type'],
                               p[0], p[1], zgo,
                               dl.get('x', 0.0), dl.get('y', 0.0), d)

    def _link_item_sprites(self):
        """Item.Start: AnimController = GetComponentInChildren — the controller
        is on the item's own GameObject or a child, never found by position."""
        by_go = {}
        for s in self.sprites:
            if s.kind == 'ItemAnimationController':
                by_go.setdefault(s.go, s)

        def find(go):
            if go in by_go:
                return by_go[go]
            tp = self._transform_of.get(go)
            for k in ((self._o(tp)['data'].get('children') or []) if tp else ()):
                kgo = self._o(k)['data'].get('gameObject')
                if kgo in by_go:
                    return by_go[kgo]
            return None

        for it in self.items.values():
            it.sprite = find(self._go_of(self._o(it.pid)))
        for d in self.doors:
            d.sprite = find(self._go_of(self._o(d.pid)))

    def _apply_zone_bounds(self):
        """Level.Start(): PlayLeft/PlayRight come from lists on the Level
        component, indexed by the number in the zone's name, and are deltas
        either side of the zone's own x."""
        lvl = None
        for o in self.objs.values():
            if o['type'] == 'Level' and 'data' in o:
                lvl = o['data']
                break
        if not lvl:
            return
        left = lvl.get('ZonesPlayLeft') or []
        right = lvl.get('ZonesPlayRight') or []
        for z in self.zones:
            try:
                i = int(z.name[4:])
            except (ValueError, IndexError):
                continue
            if i < len(left):
                z.play_left = z.x - left[i]
            if i < len(right):
                z.play_right = z.x + right[i]

    def _find_routines(self):
        for pid, o in self.objs.items():
            if o['type'] != 'ActionManager' or 'data' not in o:
                continue
            d = o['data']
            acts = []
            for a in (d.get('Actions') or []):
                ml = a.get('MoveLocation') or {}
                mz = (a.get('MoveZone') or {}).get('path')
                acts.append({'item': (a.get('Item') or {}).get('path'),
                             'duration': a.get('Duration') or 0.0,
                             'max_distance': a.get('MaximumPawnDistanceToAction') or 0.03,
                             'hide_object': bool(a.get('HideObjectDuringUse')),
                             'move_only': bool(a.get('MoveOnly')),
                             'move_x': ml.get('x', 0.0),
                             'move_zone': self._go_of(self._o(mz)) if mz and self._o(mz) else None,
                             'mutex': bool(a.get('MutexAction')),
                             'mutex_anim': a.get('MutexLoopingAnimation')})
            # Owner names the GameObject, which Season 2 calls "Rottweiler2";
            # the component type is the stable key
            ow = d.get('Owner') or {}
            self.routines.append({'owner': ow.get('type') or ow.get('name'),
                                  'owner_name': ow.get('name'),
                                  'actions': acts,
                                  'start_index': d.get('ActionStartIndex') or 0,
                                  'loop_from_start': bool(d.get('LoopFromStartIndex')),
                                  'selected_index': d.get('ActionSelectedIndex') or 0,
                                  'frozen': bool(d.get('Frozen'))})

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
                # ReturnToIdleAnimation plays the tricked idle when IsTricked
                if field == 'IdleNormal' and item['data'].get('Tricked'):
                    want = item['data'].get('IdleTricked') or want
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
            pd = o['data']
            self.pawns[o['type']] = {
                'sprite': sprite,
                'zone': zgo,
                # ProcessMovement: position += Velocity * dt * Speed, and
                # WalkOnPath sets Velocity = direction * ForceMagnitude, so a
                # horizontal walk covers Speed * ForceMagnitude per second
                'speed': pd.get('Speed') or 0.0,
                'speed_sneaking': pd.get('SpeedSneaking') or 0.0,
                'force': pd.get('ForceMagnitude') or 0.0,
                'door_force': pd.get('DoorForceMagnitude') or 0.0,
                'run_force': pd.get('RunningForceMagnitude') or 0.0,
                'run_door_force': pd.get('RunningDoorForceMagnitude') or 0.0,
                'door_delta': ((pd.get('DoorDistanceDelta') or {}).get('x', 0.0),
                               (pd.get('DoorDistanceDelta') or {}).get('y', 0.0)),
                'default': pd.get('DefaultAnimation'),
            }

    def _go_of_sprite(self, sprite):
        return getattr(sprite, 'go', None)

    def _find_background(self):
        """The backdrop is the quad carrying the Level component."""
        for q in self.quads:
            if q.get('is_level'):
                self.background = (q['texture'], q['x'], q['y'], q['w'], q['h'])
                return
