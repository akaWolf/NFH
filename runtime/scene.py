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
                 'infinite', 'type_looping', 'sounds', 'blocking')

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
        self.blocking = bool(d.get('Blocking'))     # AnimationInstance.Blocking
        self.pattern = d.get('Pattern') or None
        self.sounds = [(sd.get('Frame'), sd.get('FileName'))
                       for sd in (d.get('Sounds') or []) if sd.get('FileName')]

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
                 'ctrl_dy', 'kind', 'go', 'hidden', 'cur_frame')

    def __init__(self, name, x, y, depth, anims, current, ctrl_dx, ctrl_dy,
                 kind, go=None):
        self.name = name; self.x = x; self.y = y; self.depth = depth
        self.anims = anims; self.current = current
        self.ctrl_dx = ctrl_dx; self.ctrl_dy = ctrl_dy; self.kind = kind
        self.go = go; self.hidden = False; self.cur_frame = None


def _anim_name(v):
    """the enum's NONE means no animation"""
    return None if v in (None, 'NONE') else v


class Zone:
    __slots__ = ('name', 'pid', 'x', 'y', 'w', 'h', 'exit',
                 'play_left', 'play_right', 'ty', 'height_delta')

    def __init__(self, name, pid, x, y, w, h, is_exit, ty=0.0, height_delta=0.0):
        self.name = name; self.pid = pid
        self.x = x; self.y = y
        self.w = w; self.h = h; self.exit = is_exit
        self.ty = ty                        # transform y, floor reference
        self.height_delta = height_delta    # Zone.HeightDelta
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
                 'should_walk_up', 'should_walk_down', 'item_use_height',
                 'delta_use_height', 'enter_zone', 'leave_zone',
                 'animation', 'take_animation', 'empty_animation',
                 'use_woody_sequence', 'animation_sequence',
                 'use_take_sequence', 'take_sequence',
                 'angry_easy_up', 'angry_easy_down', 'angry_hard',
                 'fix_animation', 'fix_sequence', 'use_fix_sequence',
                 'fix_without_animations', 'can_fix', 'dont_get_angry',
                 'dont_laugh', 'grab_directly', 'keep_after_use',
                 'can_undo_trick', 'get_tricked_at_once', 'require_priming',
                 'primed', 'second_required', 'locked', 'used', 'use_once',
                 'wrong_trick', 'fucked_up', 'was_priming',
                 'compound', 'compound_required', 'compound_tricked',
                 'compound_tricked_anim', 'compound_double_anim',
                 'inventory_items', 'dont_remove_inventory',
                 'activate_item_trick', 'set_tricked_on_item',
                 'linked_item_trick', 'fix_item_trick', 'depends_on_2',
                 'use_depends_on_when_tricked', 'force_fix_original',
                 'hide_anim', 'hide_idle', 'leave_animation', 'hide_woody',
                 'sleep_sequence', 'alert_start', 'alert_left', 'alert_right',
                 'wake_sequence', 'poor_sequence', 'alerter_delay',
                 'alert_on_start_timer', 'rott_surprise',
                 'surprise_far_left', 'surprise_far_right', 'notice_enter',
                 'collider',
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
        self.idle = _anim_name(d.get('IdleNormal'))
        self.idle_tricked = _anim_name(d.get('IdleTricked'))
        # PlayItemAnimation is a no-op unless Animating, and skips NONE outright
        self.animating = bool(d.get('Animating'))
        self.use_distance = d.get('UseDistance') or 0.01
        self.should_walk_up = bool(d.get('ShouldWalkUp'))
        self.should_walk_down = bool(d.get('ShouldWalkDown'))
        self.item_use_height = d.get('ItemUseHeight') or 0.03
        self.delta_use_height = d.get('DeltaUseHeight') or 0.0
        self.enter_zone = _anim_name(d.get('EnterZone'))
        self.leave_zone = _anim_name(d.get('LeaveZone'))
        # Woody's use animation (Woody.TryUseItem plays Animation, or the
        # sequence when UseWoodyAnimationSequence)
        self.animation = _anim_name(d.get('Animation'))
        self.take_animation = _anim_name(d.get('TakeAnimation'))
        self.empty_animation = _anim_name(d.get('EmptyAnimation'))
        self.use_woody_sequence = bool(d.get('UseWoodyAnimationSequence'))
        self.animation_sequence = d.get('AnimationSequence') or []
        self.use_take_sequence = bool(d.get('UseTakeAnimationSequence'))
        self.take_sequence = d.get('TakeAnimationSequence') or []
        # the neighbour's reaction set (Rottweiler.PlayAngryAnimation)
        self.angry_easy_up = _anim_name(d.get('AnimationAngryEasyUp'))
        self.angry_easy_down = _anim_name(d.get('AnimationAngryEasyDown'))
        self.angry_hard = _anim_name(d.get('AnimationAngryHard'))
        self.fix_animation = _anim_name(d.get('FixAnimation'))
        self.fix_sequence = d.get('FixSequence') or []
        self.use_fix_sequence = bool(d.get('UseFixSequence'))
        self.fix_without_animations = bool(d.get('FixWithoutAnimations'))
        self.can_fix = bool(d.get('CanFix'))
        self.dont_get_angry = bool(d.get('DontGetAngry'))
        self.dont_laugh = bool(d.get('DontLaughWhenTrickItem'))
        # trick bookkeeping (Item / TrickItem fields)
        self.grab_directly = bool(d.get('GrabDirectly'))
        self.keep_after_use = bool(d.get('KeepAfterUse'))
        self.can_undo_trick = bool(d.get('CanUndoTrick'))
        self.get_tricked_at_once = bool(d.get('GetTrickedAtOnce'))
        self.require_priming = bool(d.get('RequirePriming'))
        self.primed = bool(d.get('Primed'))
        self.second_required = d.get('SecondRequiredInventory')
        self.locked = bool(d.get('Locked'))
        self.used = False
        self.use_once = bool(d.get('UseOnce'))
        self.wrong_trick = False
        self.fucked_up = False
        self.was_priming = False
        self.compound = bool(d.get('Compound'))
        self.compound_required = d.get('CompoundRequiredInventory')
        self.compound_tricked = bool(d.get('CompoundTricked'))
        self.compound_tricked_anim = _anim_name(d.get('CompoundTrickedAnim'))
        self.compound_double_anim = _anim_name(d.get('CompoundDoubleTrickedAnim'))
        # SearchItem.InventoryItems
        self.inventory_items = [
            {'type': v.get('Type'), 'use_count': v.get('UseCount') or 0,
             'name': v.get('NameString') or ''}
            for v in (d.get('InventoryItems') or [])]
        self.dont_remove_inventory = bool(d.get('DontRemoveInventoryItem'))
        self.activate_item_trick = (d.get('ActivateItemTrick') or {}).get('path')
        self.set_tricked_on_item = (d.get('SetTrickedOnItem') or {}).get('path')
        self.linked_item_trick = (d.get('LinkedItemTrick') or {}).get('path')
        self.fix_item_trick = (d.get('FixItemTrick') or {}).get('path')
        self.use_depends_on_when_tricked = bool(d.get('UseDependsOnWhenTricked'))
        self.force_fix_original = bool(d.get('ForceFixOriginal'))
        # HideItem: the wardrobe's own animations and whether Woody vanishes
        self.hide_anim = _anim_name(d.get('HideAnim'))
        self.hide_idle = _anim_name(d.get('IdleAnim'))
        self.leave_animation = _anim_name(d.get('LeaveAnimation'))
        self.hide_woody = bool(d.get('HideWoody'))
        # Alerter: the sleeping pet's animation sets and timings
        self.sleep_sequence = d.get('SleepSequence') or []
        self.alert_start = _anim_name(d.get('AlertSequenceStart'))
        self.alert_left = _anim_name(d.get('AlertLeft'))
        self.alert_right = _anim_name(d.get('AlertRight'))
        self.wake_sequence = d.get('WakeSequence') or []
        self.poor_sequence = d.get('PoorSequence') or []
        self.alerter_delay = d.get('AlerterDelay') if d.get('AlerterDelay') is not None else 1.0
        self.alert_on_start_timer = d.get('AlertOnStartTimer') or 0.0
        # what the neighbour plays on arriving at a (non-tricked) surprise item
        self.rott_surprise = d.get('RottweilerSurpriseAnimation') or []
        self.surprise_far_left = _anim_name(d.get('SurpriseFarLeft'))
        self.surprise_far_right = _anim_name(d.get('SurpriseFarRight'))
        self.notice_enter = bool(d.get('NoticeWhenEnterZone'))
        self.collider = None                # (cx, cy, w, h), for click hit-tests
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

    def is_tricked(self, items=None):
        """TrickItem.IsTricked (TrickItem.cs:258), including the DependsOn
        chain when the item table is provided."""
        direct = self.tricked and not self.use_at_other_place and not self.neutral
        via = False
        if items is not None and self.depends_on is not None:
            dep = items.get(self.depends_on)
            if dep is not None and dep.tricked and dep.got_tricked and \
                    (not self.use_depends_on_when_tricked or self.tricked):
                via = True
        return (direct or via) and not self.was_priming and not self.fucked_up


class Door:
    """A zone link. Passing one plays an animation on the *door's* controller —
    the sheets contain the walking character, so the pawn hides during transit.
    """
    __slots__ = ('name', 'pid', 'x', 'y', 'zone', 'link_to', 'locked',
                 'door_type', 'enter', 'leave', 'rott_enter', 'rott_leave',
                 'exit_anim', 'idle', 'sprite', 'passing', 'should_walk_up',
                 'use_distance', 'item_use_height', 'delta_use_height',
                 'dx', 'dy')

    def __init__(self, name, pid, x, y, zone, link_to, locked, door_type, d):
        self.name = name; self.pid = pid; self.x = x; self.y = y
        self.zone = zone; self.link_to = link_to; self.locked = locked
        self.door_type = door_type
        # enter/leave are ItemAnimationState and play on the door; ExitAnimation
        # is an AnimationState and loops on the pawn once it is through
        self.enter = _anim_name(d.get('WoodyEnterAnimation'))
        self.leave = _anim_name(d.get('WoodyLeaveAnimation'))
        self.rott_enter = _anim_name(d.get('RottweilerEnterAnimation'))
        self.rott_leave = _anim_name(d.get('RottweilerLeaveAnimation'))
        self.exit_anim = _anim_name(d.get('ExitAnimation'))
        self.idle = _anim_name(d.get('IdleAnimation'))
        self.sprite = None
        self.passing = None                 # Door.PassingPawn
        self.should_walk_up = bool(d.get('ShouldWalkUp'))
        self.use_distance = d.get('UseDistance') or 0.01
        self.item_use_height = d.get('ItemUseHeight') or 0.03
        self.delta_use_height = d.get('DeltaUseHeight') or 0.0
        dl = d.get('DeltaLocation') or {}
        self.dx = dl.get('x', 0.0); self.dy = dl.get('y', 0.0)


class Level:
    def __init__(self, path):
        raw = json.load(open(path))
        self.path = path
        self._raw_scene = raw.get('scene')
        self._season2 = '/s2/' in path.replace('\\', '/')
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
        self.game_info = {}         # GameInfo serialized fields
        self._build()

    def _level_location_index(self):
        """Actor.Start repositions every actor to LevelLocations[i] where
        i = GetGameWithoutTutorialLevelIndex(). For NFH1 that is
        buildIndex - 5; for NFH2, buildIndex + 12 (GetLevelIndex adds 17)."""
        import re
        m = re.match(r'level(\d+)$', self._raw_scene or '')
        if not m:
            return -1
        build = int(m.group(1))
        name = os.path.basename(self.scene)
        if re.match(r'Level2\d\d', name) or self._season2:
            return build + 12
        return build - 5

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
        self._apply_level_locations()
        self._find_game_info()

    def _add_zone(self, o):
        go = self._go_of(o)
        tr = self._transform(go)
        box = self._component(go, 'BoxCollider')
        if not tr or not box:
            return
        p = self._pos(tr); s = box['data']['size']; c = box['data']['center']
        self.zones.append(Zone(self._o(go)['data']['name'], go,
                               p[0] + c[0], p[1] + c[1], s[0], s[1],
                               bool(o['data'].get('ExitZone')),
                               ty=p[1],
                               height_delta=o['data'].get('HeightDelta') or 0.0))

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

        def find(go, depth=0):
            """GetComponentInChildren is recursive"""
            if go in by_go:
                return by_go[go]
            if depth > 6:
                return None
            tp = self._transform_of.get(go)
            for k in ((self._o(tp)['data'].get('children') or []) if tp else ()):
                kgo = self._o(k)['data'].get('gameObject')
                hit = find(kgo, depth + 1)
                if hit is not None:
                    return hit
            return None

        for it in self.items.values():
            go = self._go_of(self._o(it.pid))
            it.sprite = find(go)
            box = self._component(go, 'BoxCollider')
            if box and 'data' in box:
                b = box['data']
                it.collider = (it.x + b['center'][0], it.y + b['center'][1],
                               b['size'][0], b['size'][1])
        for d in self.doors:
            d.sprite = find(self._go_of(self._o(d.pid)))

    def _apply_zone_bounds(self):
        """Level.Start() rebuilds every zone from lists on the Level component,
        indexed by the number in the zone's name. The serialized zone transforms
        are placeholders:

            zone.position = (x, ZonesY[i], z) + zoneController.position
            zone.HeightDelta = ZonesHeightDeltas[i]
            zone.collider.size = ZonesSizes[i]
            zone.SetPlayLeft/Right(ZonesPlayLeft/Right[i])   # around the NEW x
        """
        lvl = None
        for o in self.objs.values():
            if o['type'] == 'Level' and 'data' in o:
                lvl = o['data']
                break
        if not lvl:
            return
        ctrl = (0.0, 0.0)
        for pid, o in self.objs.items():
            if o['type'] == 'ZoneController' and 'data' in o:
                go = self._go_of(o)
                tr = self._transform(go)
                if tr:
                    p = self._pos(tr)
                    ctrl = (p[0], p[1])
                break
        ys = lvl.get('ZonesY') or []
        sizes = lvl.get('ZonesSizes') or []
        left = lvl.get('ZonesPlayLeft') or []
        right = lvl.get('ZonesPlayRight') or []
        hd = lvl.get('ZonesHeightDeltas') or []
        for z in self.zones:
            try:
                i = int(z.name[4:])
            except (ValueError, IndexError):
                continue
            if i < len(ys):
                new_ty = ys[i] + ctrl[1]
                z.y = z.y - z.ty + new_ty       # keep the collider centre offset
                z.ty = new_ty
            z.x = z.x + ctrl[0]
            if i < len(sizes):
                sz = sizes[i]
                z.w = sz.get('x', z.w)
                z.h = sz.get('y', z.h)
            if i < len(hd):
                z.height_delta = hd[i]
            if i < len(left):
                z.play_left = z.x - left[i]
            if i < len(right):
                z.play_right = z.x + right[i]

    def _find_game_info(self):
        for o in self.objs.values():
            if o['type'] == 'GameInfo' and 'data' in o:
                d = o['data']
                self.game_info = {
                    'total': d.get('TotalTricksCount') or 0,
                    'winning': d.get('WinningTricksCount') or 0,
                }
                return

    def _apply_level_locations(self):
        """Actor.Start: transform.position = LevelLocations[idx]. Shift each
        actor and its sprite by the same delta."""
        idx = self._level_location_index()
        if idx < 0:
            return

        def shift(comp_data, obj):
            ll = comp_data.get('LevelLocations') or []
            if idx >= len(ll):
                return None
            t = ll[idx]
            return t.get('x', 0.0), t.get('y', 0.0)

        for it in self.items.values():
            o = self._o(it.pid)
            pos = shift(o['data'], it)
            if pos is None:
                continue
            dx, dy = pos[0] - it.x, pos[1] - it.y
            it.x, it.y = pos
            if it.sprite is not None:
                it.sprite.x += dx
                it.sprite.y += dy
        for d in self.doors:
            o = self._o(d.pid)
            pos = shift(o['data'], d)
            if pos is None:
                continue
            ddx, ddy = pos[0] - d.x, pos[1] - d.y
            d.x, d.y = pos
            if d.sprite is not None:
                d.sprite.x += ddx
                d.sprite.y += ddy
        for role, spec in self.pawns.items():
            for pid, o in self.objs.items():
                if o['type'] == role and 'data' in o:
                    pos = shift(o['data'], None)
                    if pos is not None:
                        s = spec['sprite']
                        # the sprite is a child; move it with its actor root
                        go = self._go_of(o)
                        tr = self._transform(go)
                        base = self._pos(tr) if tr else (s.x, s.y)
                        s.x += pos[0] - base[0]
                        s.y += pos[1] - base[1]
                    break

    def _find_routines(self):
        for pid, o in self.objs.items():
            if o['type'] != 'ActionManager' or 'data' not in o:
                continue
            d = o['data']
            acts = []
            for a in (d.get('Actions') or []):
                ml = a.get('MoveLocation') or {}
                mz = (a.get('MoveZone') or {}).get('path')
                pa = bool(a.get('PostponeAlarm'))
                def ref(field):
                    return (a.get(field) or {}).get('path')
                acts.append({'item': ref('Item'),
                             'duration': a.get('Duration') or 0.0,
                             'max_distance': a.get('MaximumPawnDistanceToAction') or 0.03,
                             'hide_object': bool(a.get('HideObjectDuringUse')),
                             'hide_owner': bool(a.get('HideOwnerDuringUse')),
                             'move_only': bool(a.get('MoveOnly')),
                             'move_x': ml.get('x', 0.0),
                             'move_zone': self._go_of(self._o(mz)) if mz and self._o(mz) else None,
                             'mutex': bool(a.get('MutexAction')),
                             'postpone_alarm': pa,
                             'mutex_anim': a.get('MutexLoopingAnimation'),
                             # RoutineActionUse.OnActionStarted/Stopped release
                             # infinite loops on these referenced targets
                             'stop_inf_item': ref('ItemToStopInfiniteAnimation'),
                             'stop_inf_pawn': ref('PawnToStopInfiniteAnimation'),
                             'stop_inf_pawn_tricked': ref('PawnToStopInfiniteAnimationWhenTricked'),
                             'once_pawn': ref('PawnToIgnoreInfiniteAnimationOnce'),
                             'once_pawn_not_tricked': ref('PawnToIgnoreInfiniteAnimationOnceWhenNotTricked'),
                             'once_pawn_on_end': ref('PawnToIgnoreInfiniteAnimationOnceOnEnd'),
                             'abort_mutex_pawn': ref('PawnToAbortMutexOnFinish')})
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
                                  ('HideItem', 'IdleAnim'),
                                  ('GroundItem', 'IdleNormal'),
                                  ('Alerter', 'IdleNormal'),
                                  ('InspectItem', 'IdleNormal')):
            item = self._component(go, owner_type)
            if item and 'data' in item:
                want = item['data'].get(field)
                # ReturnToIdleAnimation plays the tricked idle when IsTricked
                if field == 'IdleNormal' and item['data'].get('Tricked'):
                    want = item['data'].get('IdleTricked') or want
                # Alerter.Start plays the SleepSequence instead of an idle
                if owner_type == 'Alerter':
                    seq = item['data'].get('SleepSequence') or []
                    if seq:
                        want = seq[0]
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
            # actions reference pawns by component pid
            # (e.g. PawnToStopInfiniteAnimation, PawnToAbortMutexOnFinish);
            # objs keys are JSON strings, the refs are ints
            pawn_pid = int(pid)
            ctrl = None
            for c in self._comps.get(self._go_of_sprite(sprite) if False else sprite.go, []):
                if c['type'] == 'PawnAnimationController':
                    ctrl = self._o(c['path'])
            cd = (ctrl or {}).get('data') or {}
            self.pawns[o['type']] = {
                'pid': pawn_pid,
                'stand': {'Left': _anim_name(cd.get('StandLeftAnimation')) or 'Stand_Left',
                          'Right': _anim_name(cd.get('StandRightAnimation')) or 'Stand_Right',
                          'Up': _anim_name(cd.get('StandUpAnimation')) or 'Stand_Up',
                          'Down': _anim_name(cd.get('StandDownAnimation')) or 'Stand_Down'},
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
                'player_height_delta': pd.get('PlayerHeightDelta') or 0.0,
                'zone_level_threshold': pd.get('ZoneLevelThreshold') or 0.0,
                'item_use_height_threshold': pd.get('ItemUseHeightThreshold') or 0.0,
                'portal_up': _anim_name(pd.get('PortalUpAnimation')),
                'portal_down': _anim_name(pd.get('PortalDownAnimation')),
                'angry_decay': pd.get('AngryMeterDecay') or 0.0,
                'angry_max': pd.get('AngryMeterMaximum') or 100.0,
                'fear_left': _anim_name(pd.get('FearAnimationLeft')) or 'FearLeft',
                'fear_right': _anim_name(pd.get('FearAnimationRight')) or 'FearRight',
                'win_animation': _anim_name(pd.get('WinAnimation')),
                'is_sleeping': bool(pd.get('IsSleeping')),
                'ignore_woody': bool(pd.get('IgnoreWoody')),
                # RoutineActionHitWoody is serialized inline on the Rottweiler
                'hit_action': {
                    'sequences': [q for q in (
                        (pd.get('HitWoodyAction') or {}).get('Sequence1') or [],
                        (pd.get('HitWoodyAction') or {}).get('Sequence2') or [],
                        (pd.get('HitWoodyAction') or {}).get('Sequence3') or [],
                        (pd.get('HitWoodyAction') or {}).get('Sequence4') or []) if q],
                    'max_distance': (pd.get('HitWoodyAction') or {}).get(
                        'MaximumPawnDistanceToAction') or 0.03,
                },
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
