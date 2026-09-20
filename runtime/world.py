"""Gameplay simulation, following the decompiled source method by method.

The references in comments are to src/Assembly-CSharp: AnimationControllerBase
(frame stepping), AnimationInstance (frame model), Pawn (movement, doors),
Item (use range), ActionManager / RoutineAction* (the routine), Door, Zone.
"""

# `this is TrickItem` in C# is true for the subclasses too
TRICK_KINDS = ('TrickItem', 'Drawing', 'Rake', 'Toilet', 'Television')

# the fresh rat both L208 priming rounds hand back to the Mouse — the
# `new Inventory(IT2_Rat, "MOUSE_NAME", "RAT2_DESC", "SNAKE_INV_NAME",
# "SNAKE_INV_DESC", "", false, true)` of Item.cs:1559 / 1582 (Inventory.cs:
# 71-81), in the port's entry shape
_RAT_ENTRY_208 = {'type': 'IT2_Rat', 'use_count': 0, 'name': 'MOUSE_NAME',
                  'desc': 'RAT2_DESC', 'wrong_zone': '', 'long': False}


import struct as _struct
import os, sys
import random
import pcprofile
_f32_pack, _f32_unpack = _struct.Struct('<f').pack, _struct.Struct('<f').unpack


WAIT_EPS = 1e-6      # a WaitForSeconds / timer ends on the first frame at or past its seconds


def _f32(x):
    """round to the nearest C# float — the runtime's single-precision
    arithmetic, where it decides a tick"""
    return _f32_unpack(_f32_pack(x))[0]


def pc_room_x(zone, x):
    """a mobile x of `zone` on its PC room's floor line (Zone.pc_room: the
    zone's walking limits against the room's path1-path2)"""
    pr = zone.pc_room
    w = (zone.right - zone.left) or 1.0
    return pr['x1'] + (x - zone.left) * (pr['x2'] - pr['x1']) / w


def pc_route(level, role, zone, pos, dest, target):
    """the PC's GoTo route (GameLogic.dll fcn.1000a711 -> fcn.1000a421 /
    fcn.1000a12d; tools/pcref/lap_model_s2.Geometry.route): a Dijkstra over
    the rooms whose hop costs the Manhattan distance from the node's point to
    the near door's `<actor>` hotspot (fcn.10049e01) plus the record's
    `costs`, a hop into the target room the far door's distance to the
    target as well (fcn.1000a5b7); a room is entered at the far door's
    hotspot, the open list is kept sorted with a new node before the equal
    ones (fcn.1000a097), a known room re-parented only for a lower cost, the
    goal tested as a node is popped; the records are level.xml's in order
    (Zone.pc_room `nb`). `pos` and `target` are PC points (target None: no
    last leg). Returns the mobile hops [(zone pid, door)] — a locked or
    disabled door is no record — or None"""
    if getattr(zone, 'pc_room', None) is None or getattr(dest, 'pc_room', None) is None:
        return None
    by_name = {z.name: z for z in level.zones}
    start = {'zone': zone, 'pos': pos, 'cost': 0, 'parent': None}
    nodes = {zone.name: start}
    opn = [start]

    def insert(nd):
        k = 0
        while k < len(opn) and nd['cost'] > opn[k]['cost']:
            k += 1
        opn.insert(k, nd)
    while opn:
        nd = opn.pop(0)
        if nd['zone'] is dest:
            zs = []
            while nd is not None:
                zs.append(nd['zone'])
                nd = nd['parent']
            zs.reverse()
            hops = []
            for z1, z2 in zip(zs, zs[1:]):
                d = next((d for nb, d in level.graph.get(z1.pid, ()) if nb == z2.pid), None)
                if d is None:
                    return None
                hops.append((z2.pid, d))
            return hops
        for rec in nd['zone'].pc_room.get('nb', ()):
            fz = by_name.get(rec['zone'])
            a = rec['near'].get(role)
            b = rec['far'].get(role)
            if fz is None or a is None or b is None or getattr(fz, 'pc_room', None) is None:
                continue
            d = next((d for nb, d in level.graph.get(nd['zone'].pid, ()) if nb == fz.pid), None)
            if d is None or d.disabled or d.locked:
                continue
            c = abs(nd['pos'][1] - a[1]) + abs(nd['pos'][0] - a[0]) + rec['costs']
            if fz is dest and target is not None:
                c += abs(b[1] - target[1]) + abs(b[0] - target[0])
            ex = nodes.get(fz.name)
            if ex is not None:
                if ex['cost'] > nd['cost'] + c:
                    ex.update(cost=nd['cost'] + c, parent=nd, pos=(b[0], b[1]))
                    if ex in opn:
                        opn.remove(ex)
                    insert(ex)
                continue
            new = {'zone': fz, 'pos': (b[0], b[1]), 'cost': nd['cost'] + c, 'parent': nd}
            nodes[fz.name] = new
            insert(new)
    return None


def pc_ap_x(ap, it):
    """a station's PC hotspot x (Item.pc_approach `x`): one value, or one
    per visit where the GoTo takes another hotspot of the object each visit
    (201's puddle: its `neighbor` hotspot for the slip, `neighborleft` for
    the left slip — GameLogic 0x1002847f, 0x10028ea6) — the visit about to
    play, the item's PCUseSeconds slot"""
    x = ap.get('x')
    if isinstance(x, list):
        return x[it.pc_use_visit % len(x)] if x else None
    return x


def pc_target(role, zone, step):
    """the PC point a path's last step walks to: a station's hotspot
    (Item.pc_approach), else the item's or the point's x on the room's floor
    line; None where the step names neither"""
    pr = getattr(zone, 'pc_room', None)
    if pr is None or not isinstance(step, dict):
        return None
    it = step.get('item') if step.get('kind') == 'item' else None
    ap = it.pc_approach.get(role) if it is not None else None
    if ap:
        return (pc_ap_x(ap, it), pr['floor'] + ap['px'])
    if it is not None:
        return (pc_room_x(zone, it.x), pr['floor'])
    if step.get('x') is not None:
        return (pc_room_x(zone, step['x']), pr['floor'])
    return None


class AnimPlayer:
    """AnimationControllerBase.Refresh, one animation controller.

    Time is an accumulator: each tick subtracts dt, and crossing zero advances
    exactly one frame, then adds 1/FrameRate back (times SlowAnimationsFactor
    when the owner is slowed). An animation only loops when its InfiniteLoop
    flag is set or it was started as Looping; PlaySingleAnimation forces the
    type to Single, so inside a sequence only InfiniteLoop still loops.
    HoldOnLastFrame parks on the end frame and never finishes.
    """

    def __init__(self, sprite, sound_sink=None):
        # sprite.current None = CurrentAnimation null (AnimationControllerBase
        # .cs:13): a controller before its first SetAnimation — nothing to
        # draw or refresh (OnGUI, cs:177-188), anim is None until _set
        self.sprite = sprite
        self.by_name = {a.name: i for i, a in enumerate(sprite.anims)}
        self.mode = 'looping'            # how the current animation was started
        self.seq = []                    # AnimationSequence (state names)
        self.seq_index = 0               # SequenceIndex
        self.seq_override = None         # SetSequenceOverride, consumed at the
                                         # next PlayNextSequenceAnimation
        self.as_sequence = False         # a real PlayAnimationSequence runs —
                                         # PlaySingleAnimation-with-callback
                                         # wrappers pass as_sequence=False
        self.on_end = None
        self.acc = 0.0
        self.pat_idx = 0
        self.frame = 0
        self.slow_factor = None          # Owner.ShouldSlowAnimations hook
        self.time_scale = 1.0            # the PC profile's station pace (RoutineAction._pc_use_seconds)
        self.clip_pace = None            # the profile's per-clip seconds of a use (PCClipSeconds)
        self.skip_clip = False           # the profile's clip of 0 seconds: ended on the next tick
        self.hold_clip = None            # the profile's held clip (PCWaitFor): it loops until released
        self.ignore_infinite = False     # SetIgnoreInfiniteLoop
        self.ignore_infinite_once = False
        self.sound_sink = sound_sink
        # a PlayAnimationSequence whose owner has no ActionManager ends its
        # last element twice (see _stop_single): Woody's controller
        self.double_end = False
        self._second_end = False
        self.stand_hook = None           # PawnAnimationController falls back to
                                         # a stand pose; item controllers don't
        self.busy_hook = None            # the owner is moving (a delegate that
                                         # started a move returns true)
        self._play_serial = 0            # counts _set calls: "a delegate
                                         # started an animation"
        # behavior dispatch (Actor.BehaviorPlayAnimation / OnAdvanceFrame from
        # InitializeCurrentAnimation and Refresh; the sequence-end hook is
        # Rottweiler.OnAnimationSequenceEnded's BehaviorOnAnimationSequenceEnded)
        self.on_play = []
        self.on_advance = []
        self.seq_end_hook = None
        self.last_element_hook = None    # OnLastSequenceElementPlaying
        self.show_child_hook = None      # ShowChildRenderersOnEnd (Rottweiler)
        self.seq_step_hook = None        # PlayNextSequenceAnimation's name-hacks
        self.single_end_hook = None      # the OnAnimationEnded delegate
        self._set_start()

    # -- state -------------------------------------------------------------
    @property
    def anim(self):
        """CurrentAnimation — None before the first SetAnimation
        (AnimationControllerBase.cs:13, 350-371)"""
        if self.sprite.current is None:
            return None
        return self.sprite.anims[self.sprite.current]

    def has(self, name):
        return name in self.by_name

    def _set_start(self):
        """AnimationInstance.SetStartFrame (AnimationInstance.cs:217-226).
        UsePattern with an empty Pattern (Anim.empty_pattern): the index
        resets and UpdateCurrentFrame writes nothing (cs:228-234), so
        CurrentFrame stays the instance default 0 — sheet frame 0"""
        a = self.anim
        if a is None:                    # no CurrentAnimation yet
            self.sprite.cur_frame = None
            return
        self.pat_idx = 0
        if a.empty_pattern:
            self.frame = 0
        else:
            self.frame = a.pattern[0] if a.pattern else a.start
        self.acc = 0.0
        self.sprite.cur_frame = self.frame

    def current_index(self):
        """AnimationInstance.CurrentIndex (cs:66-76) — the sound key and the
        OnAdvanceFrame argument: the pattern index under UsePattern (the
        empty pattern included), else CurrentFrame - StartFrame"""
        a = self.anim
        if a is None:
            return 0
        return self.pat_idx if (a.pattern or a.empty_pattern) \
            else self.frame - a.start

    # -- starting animations ----------------------------------------------
    def _set(self, name, mode, index=None):
        i = self.by_name.get(name) if index is None else index
        if i is None:
            raise RuntimeError('No animation found !!! State: %s, Owner: %s'
                               % (name, self.sprite.name))
        self.sprite.current = i
        self.mode = mode
        self._play_serial += 1
        self._second_end = False         # a new play ends the extra period
        if self.clip_pace is not None:
            # the PC profile's use timed per clip (PCClipSeconds): each clip at
            # the pace that lasts its PC seconds, the others at their own; a
            # clip of 0 the PC does not play — it ends on the next tick
            secs = self.clip_pace.get(name)
            mobile = self.sequence_seconds([name]) if secs else 0.0
            self.time_scale = mobile / secs if (secs and mobile > 0.0) else 1.0
            self.skip_clip = secs is not None and secs <= 0.0
        self._set_start()
        # InitializeCurrentAnimation -> Owner.BehaviorPlayAnimation(name)
        for h in self.on_play:
            h(name)
        return True

    def play_single(self, name):
        """PlaySingleAnimation: type forced to Single. The pending sequence is
        left alone, exactly as SetAnimation never touches AnimationSequence —
        an interjected single resumes the sequence when it ends."""
        return self._set(name, 'single')

    def play_directly(self, name):
        """PlayAnimationDirectly -> SetAnimation(state): the animation keeps
        its own serialized type instead of being forced Single. GetAnimation
        (state) returns the FIRST entry of that name (ItemAnimationController
        .cs:41-51): L205's SandSculpture ships N2TrickItemPrimedNormal twice
        (a Looping 1 fps `castle`, then a Single 0.75 fps copy) — the first
        one is what its UseAnimationType plays."""
        i = next((k for k, a in enumerate(self.sprite.anims) if a.name == name),
                 None)
        if i is None:
            raise RuntimeError('No direct animation found !!! State: %s, '
                               'Owner: %s' % (name, self.sprite.name))
        a = self.sprite.anims[i]
        return self._set(name, 'looping' if a.type_looping else 'single', i)

    def play_looping(self, name, abort_if_playing=True):
        # PlayLoopingAnimation(state, abortIfPlaying) reads CurrentAnimation
        # only when it exists (AnimationControllerBase.cs:336-342)
        a = self.anim
        if abort_if_playing and a is not None and a.name == name \
                and self.mode == 'looping':
            return True
        self.seq = []                     # PlayLoopingAnimation: sequence = null
        self.as_sequence = False
        self.on_end = None
        return self._set(name, 'looping')

    def sequence_seconds(self, names):
        """the seconds a sequence of this sprite's animations lasts at their own rates"""
        t = 0.0
        for nm in names:
            i = self.by_name.get(nm)
            if i is None:
                continue
            a = self.sprite.anims[i]
            n = len(a.pattern) if a.pattern else (a.end - a.start + 1)
            t += max(1, n) / float(a.fps or 10.0)
        return t

    def play_sequence(self, names, on_end=None, as_sequence=True):
        """PlayAnimationSequence: each element via PlaySingleAnimation; the
        sequence draining is what ends the owning action. as_sequence=False
        marks the PlaySingleAnimation-plus-delegate wrappers, which must not
        fire the sequence-end behavior hook."""
        names = list(names)
        if not names:
            if on_end:
                on_end()
            return False
        self.seq = names
        self.seq_index = 0
        self.on_end = on_end
        self.as_sequence = as_sequence
        self._next_seq_anim()
        return True

    def _next_seq_anim(self):
        """PlayNextSequenceAnimation (AnimationControllerBase.cs:254-299):
        consume a SequenceOverride, pull the element, advance the index, and
        null the sequence past the end — the last element's completion is what
        fires the sequence-end path."""
        if self.seq_override is not None:
            self.seq_index = max(0, min(self.seq_override, len(self.seq) - 1))
            self.seq_override = None
        if self.seq_step_hook is not None:
            self.seq_step_hook(self, self.seq_index)
        name = self.seq[self.seq_index]
        self.seq_index += 1
        if self.seq_index >= len(self.seq):
            self.seq = []                 # AnimationSequence = null
            if self.last_element_hook is not None:
                self.last_element_hook()  # OnLastSequenceElementPlaying
        self.play_single(name)

    def set_sequence_override(self, index):
        """AnimationControllerBase.SetSequenceOverride: redirects the next
        PlayNextSequenceAnimation pull; persists until consumed."""
        self.seq_override = index

    @property
    def blocking(self):
        """AnimationControllerBase.IsPlayingBlockingAnimation (cs:398-401);
        an item controller with no CurrentAnimation blocks nothing"""
        a = self.anim
        return a is not None and a.blocking

    def waiting(self):
        """diagnostic only: parked on something that cannot finish"""
        a = self.anim
        return a is not None and (a.infinite or self.mode == 'looping') \
            and not self.seq

    # -- stepping ----------------------------------------------------------
    def _reached_end(self):
        """AnimationInstance.ReachedEndFrame (cs:197-204): under UsePattern
        the index against the pattern length — an empty pattern is at its
        end at once (0 >= 0), so a single ends on its first step and a
        looping one holds sheet frame 0"""
        a = self.anim
        if a.pattern or a.empty_pattern:
            return self.pat_idx >= len(a.pattern or ())
        return self.frame > a.end

    def _advance(self):
        """AnimationInstance.AdvanceFrame (cs:206-215): a pattern animation
        takes Pattern[index] as is — UpdateCurrentFrame (cs:228-234) never
        clamps to EndFrame (4557 of the 6260 pattern animations serialize an
        EndFrame below their pattern entries: L209 FireFakir's 127-entry
        idle ships EndFrame 0), and past the last entry it leaves the last
        entry standing. A range animation steps CurrentFrame past EndFrame
        by one; Refresh (AnimationControllerBase.cs:102-142) advances and
        settles the end — loop, next element, hold, stand — in the same call,
        so that frame is drawn only when nothing switches, exactly as the
        original draws it (DrawAnimation, cs:153-170)."""
        a = self.anim
        if a.pattern or a.empty_pattern:
            self.pat_idx += 1
            if a.pattern and self.pat_idx < len(a.pattern):
                self.frame = a.pattern[self.pat_idx]
        else:
            self.frame += 1
        self.sprite.cur_frame = self.frame

    def _loop_to_start(self):
        """AnimationInstance.LoopToStartFrame (cs:186-195)"""
        a = self.anim
        self.pat_idx = 0
        if a.empty_pattern:
            self.frame = 0
        else:
            self.frame = a.pattern[0] if a.pattern else a.start
        self.sprite.cur_frame = self.frame

    def _stop_single(self):
        """StopSingleAnimation: pull the next sequence element, fire the
        sequence-end behavior hook and the callback, else
        SwitchToStandAnimation (a no-op on item controllers, the
        facing-matched stand on pawns)."""
        if self.seq:
            self._next_seq_anim()
            return
        # the end-flags run only once the queue is drained
        # (AnimationControllerBase.cs:226-233): Hide_In/BedIn/LorryEnter...
        # hide their owner, CarnivorPlantSprayTricked re-shows the acting
        # item's child renderers
        if self.anim.hide_owner_on_end:
            self.sprite.hidden = True
        if self.anim.show_child_on_end and self.show_child_hook is not None:
            self.show_child_hook()
        was_seq, self.as_sequence = self.as_sequence, False
        if was_seq and self.seq_end_hook is not None:
            # Rottweiler.OnAnimationSequenceEnded opens with
            # BehaviorOnAnimationSequenceEnded (Rottweiler.cs:448), before
            # the ActionManager.StopCurrentAction the callback stands for
            self.seq_end_hook()
        if was_seq and self.double_end and not self._second_end:
            # the last element of a PlayAnimationSequence on a controller
            # whose owner has no ActionManager — Woody's — ends twice: the
            # first end is the sequence path (StopSingleAnimation cs:239-
            # 246: ShouldStopAction, OnAnimationSequenceEnded — Pawn's
            # returns false, Woody overrides nothing — then ActionManager.
            # StopCurrentAction on a null field, the exception Unity logs)
            # which starts no animation, so the element runs one more
            # period past its end, the last pattern entry standing, and the
            # second end is the single path (cs:234-238): OnAnimationEnded
            # (Woody.OnSingleAnimationEnded: the take's InternalUse) and the
            # stand. Bench, Level214's Carpet take: TakeLow's pattern index
            # 0..5 six ticks each, then index 6 for six more, InternalUse
            # and Stand_Down at the seventh — 90 frames from TryUseItem
            # where the single-ended port took 84.
            self._second_end = True
            return
        self._second_end = False
        cb, self.on_end = self.on_end, None
        serial = self._play_serial
        if self.single_end_hook is not None:
            # OnAnimationEnded delegates: Item.OnItemAnimationCompleted and
            # Woody.OnSingleAnimationEnded's show-after restore ride here
            self.single_end_hook(self.anim.name)
        if cb:
            cb()
        # StopSingleAnimation's two tails (AnimationControllerBase.cs:234-246):
        # a real PlayAnimationSequence (ShouldStopAction, set when the last
        # element was pulled, cs:292) ends in OnAnimationSequenceEnded /
        # StopCurrentAction and never stands; a single ends in
        # SwitchToStandAnimation unless one of its delegates returned true —
        # the arms that return true all start something (an animation, the
        # stored-click replay's move, the finish, the FearShort→FearRepeat
        # loop, Woody.cs:330-353), so "handled" is: a play happened during
        # the delegates or the owner is on the move
        if not was_seq and self.stand_hook is not None \
                and self._play_serial == serial \
                and not (self.busy_hook is not None and self.busy_hook()):
            name = self.stand_hook()
            if name and self.has(name):
                self.play_looping(name)

    def tick(self, dt):
        """AnimationControllerBase.OnGUI (cs:172-189): Refresh — the whole
        time/frame step — runs only for a controller that is not Hidden
        (`!Hidden && Event.current.type == Repaint`, cs:177). A hidden pawn
        or item stands still on its frame: Olga under HideOwnerDuringUse
        never finishes her own use sequence, and Level205/210's mat use
        ends only through the item's sequence delegate
        (Olga.OnItemAnimationSequenceEnded); a pawn hidden by a door pass or
        PawnToHideDuringUse resumes where it stopped. A controller with no
        CurrentAnimation refreshes nothing either (cs:179-185: both Refresh
        arms need `CurrentAnimation != null`)."""
        if self.sprite.hidden or self.sprite.current is None:
            return
        if self.skip_clip:
            # a clip the PC does not play (clip_pace 0): the sequence goes on
            self.skip_clip = False
            self._stop_single()
            return
        # animationTime is a C# float (AnimationControllerBase.cs:17), and
        # so is Time.deltaTime: 0.5f - 30 * 0.016666668f lands below zero on
        # the 30th tick, where the same sums in doubles leave +1e-17 and
        # cost a 31st — one frame per sheet frame, 61 ticks for a 60-tick
        # BedSleep, 49 for a 48-tick use element (tools/livediff/README.md)
        if self.time_scale != 1.0:
            dt = dt * self.time_scale     # the profile only; the mobile path keeps its floats
        self.acc = _f32(self.acc - _f32(dt))
        if self.acc > 0.0:
            return
        a = self.anim
        if self.sound_sink:
            idx = self.current_index()
            for frame, name in a.sounds:
                if frame == idx:
                    self.sound_sink(name)
        self._advance()
        # Refresh: Owner.BehaviorOnAdvanceFrame(CurrentAnimation.CurrentIndex),
        # right after AdvanceFrame and before the end check
        if self.on_advance:
            idx = self.current_index()
            for h in self.on_advance:
                h(idx)
        if self._reached_end():
            looping = ((a.infinite and not self.ignore_infinite)
                       or self.mode == 'looping'
                       or (self.hold_clip is not None and a.name == self.hold_clip))
            if looping:
                self._loop_to_start()
            else:
                if a.infinite and self.ignore_infinite_once:
                    self.ignore_infinite_once = self.ignore_infinite = False
                if a.hold:
                    if not (a.pattern or a.empty_pattern):   # !UsePattern
                        self.frame = a.end
                        self.sprite.cur_frame = a.end
                    # held: never advances the sequence (Refresh does the same)
                else:
                    self._stop_single()
        fps = self.anim.fps or 10.0
        if pcprofile.is_pc():
            # the pawns' door clips at the rate that lasts the PC door action's
            # ticks (pcprofile.clip_fps: Season 1), a frame a tick otherwise
            frames = len(a.pattern) if a.pattern else (a.end - a.start + 1)
            fps = pcprofile.clip_fps(a.name, fps, frames)
        # ResetAnimationTime (cs:144-150): `1f / FrameRate` in single
        # precision, the slow factor likewise
        self.acc = _f32(self.acc + _f32(1.0 / _f32(fps)))
        if self.slow_factor:
            self.acc = _f32(self.acc * _f32(self.slow_factor))


class Pawn:
    """Pawn movement: 2D dominant-axis walking along the floor line, portal
    climbs for walk-up doors and items."""

    IDLE, WALK = 'idle', 'walk'
    DOOR_CLIMB, DOOR_ANIM, DESCEND, ITEM_CLIMB = \
        'door_climb', 'door_anim', 'descend', 'item_climb'
    MOVING = (WALK, DOOR_CLIMB, DESCEND, ITEM_CLIMB)   # the states that integrate

    def __init__(self, level, sprite, zone, spec=None, player=None, role='Woody'):
        self.level = level
        self.sprite = sprite
        self.anim = player or AnimPlayer(sprite)
        self.zone = zone
        self.role = role
        spec = spec or {}
        self.speed = spec.get('speed') or 0.0
        self.speed_sneaking = spec.get('speed_sneaking') or 0.0
        self.force = spec.get('force') or 0.0
        self.door_force = spec.get('door_force') or 0.0
        self.door_delta = spec.get('door_delta') or (0.0, 0.0)
        self.height_delta = spec.get('player_height_delta') or 0.0
        self.zone_threshold = spec.get('zone_level_threshold') or 0.0
        self.item_threshold = spec.get('item_use_height_threshold') or 0.0
        self.extra_delta_height = spec.get('extra_delta_height') or 0.0
        self.portal_up = spec.get('portal_up')
        self.portal_down = spec.get('portal_down')
        self.portal_run_up = spec.get('portal_run_up')
        self.portal_run_down = spec.get('portal_run_down')
        # Rottweiler's anger meter (fields on the pawn, Rottweiler.cs:50-56)
        self.angry_meter = 0.0
        self.angry_decay = spec.get('angry_decay') or 0.0
        self.angry_max = spec.get('angry_max') or 100.0
        self.can_decrease_angry = True
        self.angry_count_ticks = 0
        # the PC profile's Season 1 rage (game.exe's level state, +0x70
        # current / +0x78 hold / +0x84 the level's angrytime, in 1/12 s
        # ticks — pcprofile.s1_rage_*); rage_max 0 means the mobile meter
        self.rage_max = spec.get('rage_max') or 0
        self.rage_decay_tick = spec.get('rage_decay_tick') or 0   # the PC Season 2 decay per tick
        # the PC Season 2 level status's byte +0x28: set by the credit that
        # overflows the gauge (fcn.1000140b, 0x10001500), never cleared —
        # every SHOUT after it plays the freakout (pcprofile.s2_reaction_seconds)
        self.pc_rage_full = False
        self.pc_hit_secs = None          # the PC's seconds for this pawn's hit on him (the trick item's PCHitSeconds)
        self.rage_current = 0
        self.rage_hold = 0
        self.rage_bonus = False          # the flag of the last trick (+0x7c)
        self.rage_acc = 0.0              # seconds toward the next 1/12 s tick
        self.tricked_aux = False         # Rottweiler.TrickedAux: set at cs:652,
                                         # cleared by every Item.Fix (Item.cs:2065)
        self.sneaking = False
        self.sneak_toggle = False        # Woody.MbSneakToggle
        self.in_urgent = False           # Pawn.InUrgentMove
        self.pc_run = False              # the PC case's run gait (Routine._pc_runs)
        self.pc_run_hit = False          # the next hit-pawn run is the PC script's run
        self.movement_paused = False     # Pawn.MovementPaused
        self.exit_confirmation_shown = False   # Pawn.ExitConfirmationShown
        self.waiting_for_exit_confirmation = False  # WaitingforExitConfirmation
        self.hiding = False              # Woody.Hiding (SetHidden override)
        self.min_door_distance = spec.get('min_door_distance') or 0.0
        self.hiding_item = None
        self.is_warping = False          # Pawn.IsWarping, set by door transit
        self._warped = False             # the far door's placement done (PC: at its clip's start)
        self._warp_old = None
        self._warp_hooked = False
        # the PC profile's Season 2 door pass (Door.pc_pass): (near door,
        # pace u/s) of the transition being walked, and the pace of a back
        # door's climb or descent
        self._pc_pass = None
        self._pc_climb_pace = None
        # (stretch, pace u/s or None for a snap) of the floor stretch being
        # walked (_pc_floor_marks), and the PC-timed pace of the frame's movement
        self._pc_floor = None
        self.pc_pace = None
        # the door pair the pawn's PC door-pass step holds (_pc_claim_pair)
        self._pc_claimed = None
        # the PC profile's Season 2 stations (Item.pc_approach): the station
        # the pawn stands at (its PC hotspot x, height, and where the pawn
        # stood), the PC x a path leaves from when it goes to the same PC
        # point, and the seconds spent on a timed step (`pc_secs`)
        self._pc_depart = None
        self._pc_from_x = None
        self._pc_step_t = 0.0
        self._pc_hold_t = 0.0
        # the PC profile's Season 2 catch (World._pc_s2_sees): the catcher's
        # flag 4 (Item.pc_hideout) with the use it belongs to, whether it
        # outlives that use, the clip last read; Woody's hideout leave clip
        self.pc_flag4 = False
        self._pc_use = None
        self._pc_keep = False
        self._pc_clip = None
        self._pc_leave_anim = None
        self.velocity = (0.0, 0.0)       # Pawn.Velocity — a field that
                                         # outlives the frame (cs:855-880)
        self._item_snap = None           # MoveToItem's head, deferred one
                                         # frame past TryUseItem (cs:1735)
        self.pos_snap = False            # marks the frame of a legal position
                                         # snap (tests/invariants.py reads it)
        # the NFH2 walk-through pathing state (Pawn.cs:150-183)
        self.nfh2 = spec.get('nfh2') or False
        self.adjacent_zones = spec.get('adjacent_zones') or False
        self.passing_complex = False     # Pawn.PassingComplexMove
        self.done_passing = False        # Pawn.DonePassingToOtherZone
        self.go_zone = None              # Pawn.GoZone
        self.door_clicked = None         # Pawn.DoorClicked
        self.item_aux = None             # Pawn.ItemAux
        self.flag_aux = False            # Pawn.FlagAux
        self.y_neg = 0.0                 # NewWoodyPositionYNegative
        self.y_pos = 0.0                 # NewWoodyPositionYPositive
        self.transition_enter = None     # Pawn.TransitionEnter
        self.check_for_neighbour = False  # Pawn.CheckForNeighbour
        self._last_zone2 = zone          # Pawn.lastZone2
        self._move_index = -1            # Pawn.MoveIndex (per-route step count)
        # BuildPathToTarget's door-at-once pre-arm (Pawn.cs:744-780): PortalMove
        # armed before any walk, and UseDoorAtOnce (Pawn.cs:139, 752, 771,
        # consumed 1391-1396 / 1412-1416); the pass states stand in for the
        # rest of PortalMove's life
        self.portal_move = False         # Pawn.PortalMove (the pre-arm only)
        self.use_door_at_once = False    # Pawn.UseDoorAtOnce
        self.wrong_zone_tooltip = False  # Pawn.WrongZoneDescritionTooltip
        # MovePath.Steps[MoveIndex].Target of an item step: what TryUseItem
        # and the dexterity retry use (Woody.cs:214-222, 515)
        self.use_target = None
        # the neighbour's walking props (Rottweiler.cs:75-107): each swaps the
        # walking animation set in UpdateWalkingAnimation
        self.feel_sick = False           # Pawn.FeelSick
        self.holding_cake = False        # Rottweiler.HoldingCake
        self.has_fifi = False            # Rottweiler.HasFifi
        self.has_bowling = False         # Rottweiler.HasBowlingBall
        self.has_skates = False          # Rottweiler.HasSkates
        self.alarm_postponed = False     # Rottweiler.AlarmPostponed
        self.is_using_toilet = False     # Rottweiler.IsUsingToilet
        self.normal_pos_aux = False      # Rottweiler.NormalPosAux
        self.item_to_ignore_next_time = None  # Rottweiler.ItemToIgnoreNextTime
        self.show_coins = False          # Rottweiler.ShowCoins
        # Olga's shared animation-instance stores (Olga.cs:12-18) and the
        # L211 toilet delay (Olga.cs:10)
        self.olga_aux_anim = None        # animationAuxOlga
        self.olga_workout_anim = None    # animationWorkoutOlga
        self.olga_wait_picnic_anim = None  # animationWaitPicnicOlga
        self.olga_workout2_anim = None   # animationWorkoutOlga2
        self.delay_toilet_211 = 0.0      # DelayToiletBehavior211
        self.toilet_action = spec.get('toilet_action') or {}
        # the alerter/notice run and the phone answer templates
        # (Rottweiler.SurpriseActionFar cs:26, AlarmAction cs:62)
        self.surprise_far_action = spec.get('surprise_far_action') or {}
        self.alarm_action = spec.get('alarm_action') or {}
        self.wait_in_fear_anim = spec.get('wait_in_fear_anim') or 'WaitInFear'
        self.hit_pawn_action = spec.get('hit_pawn_action') or {}
        self.behaviors = []              # Actor.Behavior + SecondaryBehaviors
        self.routine_behavior = None     # Pawn.RoutineBehavior
        self.walk_hook = None            # Rottweiler.UpdateWalking's notice run
        self.notice_near_distance = spec.get('notice_near_distance') or 0.03
        # the Kid pawn's flags (Kid.cs:19-23)
        self.kid_start_crying = False
        self.kid_using_remote = False
        self.kid_remote = False
        self.is_sleeping = spec.get('is_sleeping') or False
        self.hud_blind = False           # ProgressBar.PlayPawnBlindAnimation
        self.hud_disable_think = False   # HUD.Disable*ThinkBubble
        # the dexterity minigame's Woody flags (Woody.cs:158-178)
        self.in_dexterity = False        # Woody.InDexterity
        self.dexterity_done = False      # Woody.DexterityDone
        self.dexterity_aux = False       # Woody.DexterityAux (the retry one-shot)
        self.mouse_click_after_dexterity = False
        self.frozen = False              # Woody.Frozen
        self.ignore_woody = spec.get('ignore_woody') or False
        self.fear_left = spec.get('fear_left') or 'FearLeft'
        self.fear_right = spec.get('fear_right') or 'FearRight'
        self.win_animation = spec.get('win_animation')
        self.lose_animation = spec.get('lose_animation')
        self.hello_animation = spec.get('hello_animation')
        self.hello_animation_nfh2 = spec.get('hello_animation_nfh2')
        self.exit_confirm_message = spec.get('exit_confirm_message') or ''
        self.idle_animations = spec.get('idle_animations') or []
        self.idle_threshold = spec.get('idle_threshold') or 30.0
        self.animations_in_progress = False  # Pawn.AnimationsInProgress
        self.postponed_alerter = None        # Woody.PostponeAlert + Alerter
        self.stored_input = None             # Woody.StoreBlockedInput
        # Pawn.FinishedEntrance is serialized (Pawn.cs:119): the S1 levels
        # ship Woody's FALSE and the entrance's blocking end flips it
        # (Woody.cs:304-312); every S2 level ships TRUE — no walk-in, no
        # Hello (Woody.cs:191, 223-231; Pawn.cs:1064-1067). Everyone else
        # starts finished (the field never gates them).
        self.finished_entrance = bool(spec.get('finished_entrance', False)) \
            if role == 'Woody' else True
        self.was_hiding = False              # Woody.WasHiding (Unhide sets)
        self.last_hiding_item = None         # Woody.LastHidingItem
        self.at_door_location = False        # Pawn.AtDoorLocation
        self.last_exit_door = None           # Pawn.LastExitDoor
        self.rott_last_door = None           # Pawn.RottLastDoor (cs:153): the
                                             # Rottweiler's copy of the last
                                             # entered door, never cleared
                                             # (AdvanceToNextMove clears only
                                             # LastExitDoor, cs:1059-1062)
        self.medium_laughs = spec.get('medium_laughs') or []
        self.big_laughs = spec.get('big_laughs') or []
        self.run_force = spec.get('run_force') or 0.0
        self.run_door_force = spec.get('run_door_force') or 0.0
        self.hit_action = spec.get('hit_action') or {}
        self.animal_tutorial = bool(spec.get('animal_tutorial'))
        self.nfh2 = bool(spec.get('nfh2'))       # Woody.NFH2Path
        self.grab_action = spec.get('grab_action') or {}
        self.use_fixing_action = spec.get('use_fixing_action') or {}
        self.fixing_item = None          # Rottweiler.FixingItem (the carried tool)
        self.stand = spec.get('stand') or {}
        self.default_anim = spec.get('default')
        self.state = self.IDLE
        self.facing = 'Left'
        self.hidden = False
        self.input_locked = False        # Woody.InputLocked (the entrance)
        self.steps = []
        self.on_arrive = None
        self._step = None
        self._step_sign = None
        self._step_sign_y = None
        self._exit_door = None
        self.world = None                # set by World, for zone reactions
        self.anim.stand_hook = self._switch_to_stand
        self.anim.busy_hook = lambda: self.state != self.IDLE
        start = self.default_anim if self.default_anim and \
            self.anim.has(self.default_anim) else self._stand_name()
        if start:
            self.anim.play_looping(start)

    def _stand_name(self):
        """PawnAnimationController.SwitchToStandAnimation's pose pick
        (PawnAnimationController.cs:99-134): a Looping current animation
        resolves through AnimState — the Walk/Stand/Run/RunWC families by
        their facing, WaitWatch and WaitInFear stay themselves; a Single
        current animation (a bare single that just ended, an idle pose, a
        sequence element) resolves through PrevAnimState — whose only write
        (cs:165-172) sits behind a `Type == Looping` test that the strict
        Single lookup of PlaySingleAnimation (cs:137-151) can never satisfy,
        so it stays the enum default Walk_Down and every such switch plays
        StandDownAnimation. (A Looping animation outside those families
        throws "Stand with nothing before" in the original; the port keeps
        the last facing's stand there.)"""
        if self.anim.mode == 'single':
            name = self.stand.get('Down', 'Stand_Down')
            return name if self.anim.has(name) else None
        cur = self.anim.anim.name
        if cur in ('WaitWatch', 'WaitInFear'):
            return cur
        # the switch reads the direction off the current looping name —
        # Walk_/Stand_/Run_/RunWC + Down/Left/Right/Up (cs:102-125)
        facing = self.facing
        for fam in ('Walk_', 'Stand_', 'Run_', 'RunWC'):
            if cur.startswith(fam) and cur[len(fam):] in ('Down', 'Left',
                                                          'Right', 'Up'):
                facing = cur[len(fam):]
                break
        name = self.stand.get(facing, 'Stand_' + facing)
        if self.anim.has(name):
            return name
        if self.default_anim and self.anim.has(self.default_anim):
            return self.default_anim
        return None

    def _switch_to_stand(self):
        """PawnAnimationController.SwitchToStandAnimation's Woody head
        (PawnAnimationController.cs:86-95): every stand switch while
        DonePassingToOtherZone && NFH2Path drops GoZone, DoorClicked and the
        flag itself — what disarms the y-tracker after a path, a held
        transition wait or an interposed use. Returns the stand pose name
        (the base's facing switch, cs:98-134)."""
        if self.role == 'Woody' and self.done_passing and self.nfh2:
            self.go_zone = None
            self.door_clicked = None
            self.done_passing = False
        return self._stand_name()

    def _stand(self):
        """SwitchToStandAnimation as a call: the clears plus the pose"""
        st = self._switch_to_stand()
        if st:
            self.anim.play_looping(st)

    def set_hidden(self, hidden):
        """Pawn.SetHidden sets AnimController.Hidden (Pawn.cs:1464-1467);
        Woody's override flips Hiding instead (Woody.cs:1086-1089)."""
        self.hidden = hidden
        if self.role == 'Woody':
            self.hiding = hidden
        else:
            self.sprite.hidden = hidden

    def _walk_anim(self, direction):
        """the walking animation per prop state: Rottweiler.
        UpdateWalkingAnimation picks WC / Run / Pie / Bowling / Fifi / Ski
        sets (Rottweiler.cs:939-1030); Woody runs unless sneaking
        (Woody.cs:886-937); Mother and Olga run in an urgent move
        (Mother.cs:183-234, Olga.cs:41-92); the base pawn walks
        (Pawn.cs:1161-1190)."""
        if self.role == 'Rottweiler':
            if self.feel_sick:
                return 'RunWC' + direction
            if self._pc_gait() == 'run' or \
                    (self.in_urgent and not self._pc_walking_urgent()):
                return 'Run_' + direction
            if self.holding_cake:
                return 'WalkPie_' + direction
            if self.has_bowling:
                return 'WalkBowling'
            if self.has_fifi:
                return 'FifiWalk' + direction
            if self.has_skates:
                return 'SkiWalk1' if direction == 'Right' else 'SkiWalk2'
            return 'Walk_' + direction
        if self.role == 'Woody':
            return ('Walk_' if self.sneaking else 'Run_') + direction
        if self.role in ('Mother', 'Olga') and (
                self._pc_gait() == 'run'
                or (self.in_urgent and not self._pc_walking_urgent())):
            return 'Run_' + direction
        return 'Walk_' + direction

    def _pc_gait(self):
        """the Season 1 neighbour's gait under the profile (pcprofile.
        GAIT_PX_PER_TICK): the run on an urgent the PC case runs
        (Routine._pc_runs), the bowling ball's carry (105's case 11 sets
        gait 4 before the GoTo to the window, game.exe 0x46e4d3; the
        mobile's HasBowling), else the walk"""
        if self.role not in ('Rottweiler', 'Mother', 'Olga') or not pcprofile.is_pc():
            return 'walk'
        if self.in_urgent and self.pc_run:
            return 'run'
        if self.has_bowling and not pcprofile.SEASON2:
            return 'bowling'
        return 'walk'

    def _pc_walking_urgent(self):
        """an urgent the PC walks (its gait left at mg: 111's vacuum and
        carpet; Season 2's hits of Olga and the Mother) shows the walk set
        under the profile, as it moves at the walk records (Routine._pc_runs)"""
        return pcprofile.is_pc() and not self.pc_run

    def _portal_up_anim(self):
        """Rottweiler.GetPortalUpAnimation (Rottweiler.cs:398-413); Woody
        climbs with PortalSneakUpAnimation while sneaking (Woody.cs:961-968)
        — the private field's initializer Walk_Up (Woody.cs:64)"""
        if self.role == 'Rottweiler':
            if self.feel_sick:
                return 'RunWCUp'
            if self._pc_gait() == 'run' or \
                    (self.in_urgent and not self._pc_walking_urgent()):
                return self.portal_run_up or 'Run_Up'
            if self.has_fifi:
                return 'FifiWalkUp'
        if self.role == 'Woody' and self.sneaking:
            return 'Walk_Up'
        return self.portal_up

    def _portal_down_anim(self):
        """Rottweiler.GetPortalDownAnimation (Rottweiler.cs:415-434); Woody
        descends with PortalSneakDownAnimation while sneaking (Woody.cs:952-
        959) — the private field's default, AnimationState 0 = Walk_Down
        (Woody.cs:66, AnimationState.cs:3)"""
        if self.role == 'Rottweiler':
            if self.feel_sick:
                return 'RunWCDown'
            if self._pc_gait() == 'run' or \
                    (self.in_urgent and not self._pc_walking_urgent()):
                return self.portal_run_down or 'Run_Down'
            if self.has_fifi:
                return 'FifiWalkDown'
            if self.has_skates:
                return 'SkiWalk2'
        if self.role == 'Woody' and self.sneaking:
            return 'Walk_Down'
        return self.portal_down

    # -- geometry ----------------------------------------------------------
    def floor_y(self, zone=None):
        """Helpers.GetDefaultZoneY: zone y + HeightDelta + PlayerHeightDelta"""
        z = zone or self.zone
        return z.ty + z.height_delta + self.height_delta

    def at_zone_y(self):
        """Pawn.IsPawnAtZoneY"""
        return abs(self.sprite.y - self.floor_y()) < 0.1

    def freeze(self):
        """Woody.Freeze (Woody.cs:993-997): Frozen — CheckMouseClick drops
        the clicks (cs:637) — and PauseMovement, so a walk in progress
        stops where it is (L201's second tutorial freeze caught Woody at
        the foot of the stairs, 5.12, on the original; the port walked on
        to the click's 4.02)"""
        self.frozen = True
        self.movement_paused = True

    def unfreeze(self):
        """Woody.UnFreeze (Woody.cs:999-1003): Frozen off, UnPauseMovement"""
        self.frozen = False
        self.movement_paused = False

    def door_target(self, door):
        """Item.GetTargetLocation (Item.cs:2010-2050): transform +
        DeltaLocation + the per-pawn door delta"""
        pd = door.pawn_deltas.get(self.role, (0.0, 0.0))
        return door.x + door.dx + pd[0], door.y + door.dy + pd[1]

    def pc_room(self):
        """the PC's room pointer the Season 2 catch compares (fcn.1003f573 ->
        fcn.10040a7d): none from a pass's `<actor>_in` to its `<actor>_out` —
        the straight movement or the enter and leave clips set it to none
        (fcn.100037f8, fcn.10003647) and the far room is set at `_out`
        (fcn.10003454) — i.e. on a hop's steps up to the transfer
        (_pc_hop_steps) less the `out` run stood before one, and inside a back
        door's clips (is_warping); else the zone"""
        if self.is_warping:
            return None
        s = self._step
        if s is not None and s.get('pc_hop') is not None and self.state == self.WALK \
                and not (s.get('pc_prehold', 0.0) > 0.0 and self._pc_hold_t < s['pc_prehold'] - 1e-9):
            return None
        return self.zone

    def moving_to_adjacent_zone(self):
        """Pawn.IsMovingToAdjacentZone = TransitionMove: the current path
        step heads through a Transition door (Pawn.cs:1281-1283, 1712)."""
        s = self._step
        return (s is not None and s.get('kind') == 'door'
                and s['door'].is_transition
                and not s['door'].complex_move)

    def at_use_range(self, it):
        """Item.IsAtUseRange (Item.cs:2270-2293) — the walk-phase check, with
        the x term; the walk-up y-arm is skipped for the DontUseOn pawn and
        widens by Woody.ExtraDeltaHeight when the item asks (cs:2286-2288)"""
        if self.zone is None or self.zone.pid != it.zone:
            return False
        mx = it.move_x(self.role)
        my = it.y + it.dy
        dont_on_me = (it.dont_use_on is not None       # Item.DontUseOn
                      and self.world is not None
                      and self.world.pawn_by_pid(it.dont_use_on) is self)
        if it.should_walk_up and not dont_on_me:
            thr = self.item_threshold + it.delta_use_height
            if it.use_woody_extra and self.role == 'Woody':
                thr += self.extra_delta_height
            return (abs(self.sprite.y - my) < thr
                    and abs(self.sprite.x - mx) < it.use_distance)
        return abs(self.sprite.x - mx) < it.use_distance

    def at_use_location(self, obj):
        """Pawn.IsAtUseLocation (Pawn.cs:1690-1705) — the climb-phase check:
        y only, against the object's own transform. Woody's window widens by
        the item's WoodyDeltaUseHeight, or by his own ExtraDeltaHeight when
        UseWoodyExtraDeltaHeight (the Woody.cs:744-755 override). Both Item
        and Door carry the three fields (Door : Item; the door step reads
        them at Pawn.cs:1330, 1412)."""
        thr = self.item_threshold + obj.delta_use_height
        if self.role == 'Woody':
            if obj.use_woody_extra:
                thr = self.item_threshold + obj.delta_use_height \
                    + self.extra_delta_height
            else:
                thr += obj.woody_delta_use_height
        return abs(self.sprite.y - obj.y) < thr

    # -- commands ----------------------------------------------------------
    def start_move_flags(self):
        """Woody.StartMoveToLocation (Woody.cs:714-735): sneak comes from
        the toggle — never on the NFH2 path (cs:717-720; the S2 sheets have
        no Walk_* strips) — a plain click is an urgent (running) move, and
        moving leaves a hiding spot."""
        self.sneaking = self.sneak_toggle
        if self.nfh2:
            self.sneaking = False
        self.in_urgent = not self.sneaking
        if self.hiding:
            self.unhide()

    def toggle_sneak(self):
        """Woody.ToggleSneak (Woody.cs:1151-1168): the button flips
        MbSneakToggle; Sneaking follows it only off the NFH2 path. The
        walking-animation refresh (cs:1164-1167) is the per-tick
        UpdateWalkingAnimation of the walk loop."""
        self.sneak_toggle = not self.sneak_toggle
        self.sneaking = self.sneak_toggle and not self.nfh2

    def hide(self, item):
        """Woody.Hide (Woody.cs:1080-1084) + HideItem.InternalUse's own
        part (HideItem.cs:35-43): Hiding/HidingItem, HideWoody and the hide
        pose. The base InternalUse it opens with (cs:34 — HideDuringWoodyAnim's
        layer swap and object hide, Item.cs:1929-1938) is the caller's
        World._item_internal_use, run just before."""
        self.hiding = True
        self.hiding_item = item
        self.last_hiding_item = item     # LastHidingItem = HidingItem
        self._pc_leave_anim = None
        if item.hide_woody:
            self.sprite.hidden = True
        p = self.world.players.get(id(item.sprite)) \
            if self.world and item.sprite else None
        if p is not None and item.hide_anim and p.has(item.hide_anim):
            # PlayAnimationDirectly (HideItem.cs:42): the strip keeps its
            # own serialized Type — not forced Single
            p.play_directly(item.hide_anim)

    def unhide(self):
        """Woody.Unhide (Woody.cs:1091-1102) + HideItem.Leave
        (HideItem.cs:64-81)"""
        self.hiding = False
        self.sprite.hidden = False
        self.was_hiding = True           # Woody.cs:1101
        item, self.hiding_item = self.hiding_item, None
        self.last_hiding_item = item     # LastHidingItem = HidingItem
        if item is None or self.world is None:
            return
        if item.hide_during_woody_anim:
            # Leave repeats InternalUse's HideDuringWoodyAnim pair — the
            # show-after and the object hide (HideItem.cs:66-70; no layer
            # swap here: Item.cs:1931-1935 is InternalUse-only)
            self.world.hide_during_woody_anim(item, layer=False)
        p = self.world.players.get(id(item.sprite)) if item.sprite else None
        if p is not None and item.hide_idle and p.has(item.hide_idle):
            # PlayAnimationDirectly (HideItem.cs:75-78): the idle keeps its
            # serialized Type — Looping for L207's beach_chair (1x1, 1 fps),
            # which a forced Single would run past its sheet after a second
            p.play_directly(item.hide_idle)
        if item.leave_animation and self.anim.has(item.leave_animation):
            self.anim.play_single(item.leave_animation)
            # the PC's leave step clears flag 4 once its `leave` has played
            # (GameLogic.dll 0x10006ab7): hidden to the Season 2 catch for
            # the clip (World._pc_s2_sees)
            self._pc_leave_anim = item.leave_animation

    def _capture_click(self, dest):
        """GetMoveDestination's GoZone / y-threshold bookkeeping, common to
        the item, door and zone branches (Pawn.cs:604-612, 645-653, 700-708)"""
        if dest is not None and (self.go_zone is None
                                 or self.go_zone.pid != dest.pid) \
                and not self.done_passing:
            self.go_zone = dest
        self.y_neg = self.sprite.y - 0.15          # Interval (Pawn.cs:220)
        if not self.done_passing:
            self.y_pos = self.sprite.y + 0.15

    def goto(self, x, y, on_arrive=None):
        """Pawn.MoveToLocation (Pawn.cs:394-421): the click ray (zone_at
        stands in for Physics.Raycast, cs:403-404) -> MoveToGoal
        (cs:428-441) -> InternalMoveToGoal (cs:475-486); the x clamp is
        FindPath's AdjustEndMoveInZoneArea (Helpers.cs:125-136)"""
        dest = self.level.zone_at(x, y)
        if dest is None:
            return False
        self.item_aux = None                        # ItemAux = targetItem
        self._capture_click(dest)
        return self._route(dest, {'kind': 'point',
                                  'x': min(max(x, dest.left), dest.right)},
                           on_arrive)

    def goto_zone(self, dest, x, on_arrive=None):
        """Pawn.MoveToGoal(Pawn/Item, Zone, Vector3) with a bare zone target
        (Pawn.cs:428-454) -> InternalMoveToGoal (cs:475-486) ->
        ConstructLocationPath (cs:545-552) -> BuildPathToTarget (cs:729)"""
        if dest is None:
            return False
        self._capture_click(dest)
        return self._route(dest, {'kind': 'point', 'x': x}, on_arrive)

    def goto_item(self, it, on_arrive=None):
        """BuildPathToItem (Pawn.cs:811-825): route to the zone, then a
        plain floor step at the item's TargetLocation.x before the item
        step — but only for an elevated item the pawn is not already
        standing under (IsAtItemLocation, cs:827-830: within 0.1 of the
        item's own x). The floor step takes TargetLocation.x itself, where
        the item step takes GetMoveLocation, which offsets Olga and the
        Mother (Item.cs:2245-2262)."""
        dest = self.level.zone_by_pid(it.zone)
        if dest is None:
            return False
        self.item_aux = it                          # Pawn.cs:595
        self._capture_click(dest)
        final = {'kind': 'item', 'item': it, 'x': it.move_x(self.role)}
        if it.should_walk_up and abs(self.sprite.x - it.x) >= 0.1:
            final = [{'kind': 'point', 'x': it.target_x}, final]
        return self._route(dest, final, on_arrive)

    def _helpers(self):
        """the Helpers statics the NFH2 pathing consumes
        (Helpers.cs:9-19)"""
        w = self.world
        if w is None:
            return {'done_helper': False, 'step_index': 0,
                    'first_step_index': 0, 'original_start_zone': None}
        if not hasattr(w, 'helpers'):
            w.helpers = {'done_helper': False, 'step_index': 0,
                         'first_step_index': 0, 'original_start_zone': None}
        return w.helpers

    def _door_between(self, z1_pid, z2_pid):
        """Helpers.GetDoorBetweenZones: a door in z1 linking into z2 returns
        its LinkTo — the z2-side door (Helpers.cs:194-205)"""
        for d in self.level.doors:
            if d.locked or d.zone != z1_pid or d.link_to is None:
                continue
            other = self.level.door_by_pid(d.link_to)
            if other is not None and other.zone == z2_pid:
                return other
        return None

    def _route(self, dest, final_step, on_arrive):
        # a new path aborts the one walked: its door-pass step lets its pair
        # go (the step's cleanup, GameLogic 0x10004169 -> 0x100033d4)
        self._pc_release()
        H = self._helpers()
        woody = self.world.woody if self.world else None
        # FindPath's head (Helpers.cs:81-85): the helper flag latches only
        # when a door links Woody's zone to the destination
        if woody is not None and woody.zone is not None \
                and self._door_between(woody.zone.pid, dest.pid) is not None:
            H['done_helper'] = self.done_passing
        H['original_start_zone'] = self.zone.pid if self.zone else None
        # Woody.MoveToGoal drops the description bubble (Woody.cs:770-775)
        if self.role == 'Woody' and self.world is not None \
                and self.world.hud is not None:
            self.world.hud.show_description = False
        self.on_arrive = on_arrive
        # InitializePath (Pawn.cs:491-498) drops PortalMove; UseDoorAtOnce
        # is only ever consumed in the original (cs:1393, 1414) — a pre-arm
        # abandoned mid-wait would ride into the next path there (and
        # double-play a flat door, cs:1384-1385 + 1391-1396); not reproduced
        self.portal_move = False
        self.use_door_at_once = False
        self.use_target = None
        steps = []
        hops = None
        # FindPath: mid-stairs Woody logically paths from GoZone
        # (Helpers.cs:86-106)
        if dest.pid == self.zone.pid and self.done_passing \
                and self.go_zone is not None \
                and self.go_zone.pid != dest.pid:
            hops = self.level.find_path(self.go_zone.pid, dest.pid)
        if hops is None and dest.pid != self.zone.pid and pcprofile.is_pc():
            hops = self._pc_station_route(dest, final_step)
        if hops is None and dest.pid != self.zone.pid and pcprofile.is_pc() \
                and pcprofile.s2_routes(self.nfh2):
            hops = self._pc_room_route(dest, final_step)
        if hops is None and dest.pid != self.zone.pid:
            hops = self.level.find_path(self.zone.pid, dest.pid)
            if hops is None:
                self.on_arrive = None
                return False
        for zone_pid, door in (hops or ()):
            steps.extend(self._link_steps(door, H))
        # BuildPathToTarget (Pawn.cs:744-780): a path whose first step is a
        # portal door pre-arms PortalMove when Woody stands on that door —
        # ShouldExitDoorNow, Woody.cs:777-780: AtDoorLocation and it is his
        # LastExitDoor — (UseDoorAtOnce, MovingUp = ShouldWalkUp; cs:768-779)
        # or when the pawn is off the floor at the door's x — ShouldWalk
        # DirectlyUpToDoor, cs:785-788, IsAtDoorLocation cs:802-809: MovingUp
        # = ShouldWalkUp, UseDoorAtOnce = !MovingUp (cs:748-753). Otherwise
        # an off-floor start inserts the floor step: every non-Woody pawn,
        # Woody only with FlagAux (cs:755-765)
        d0 = steps[0]['door'] if steps and steps[0].get('kind') == 'door' \
            else None
        exit_now = d0 is not None and self.role == 'Woody' \
            and self.at_door_location and self.last_exit_door is d0
        direct_up = d0 is not None and not exit_now and not self.at_zone_y() \
            and abs(self.sprite.x - d0.x) < 0.1
        if exit_now or direct_up:
            self.portal_move = True
            self.use_door_at_once = exit_now or not d0.should_walk_up
        elif not self.at_zone_y() and (self.role != 'Woody' or self.flag_aux):
            steps.insert(0, {'kind': 'point', 'x': self.sprite.x,
                             'y': self.floor_y()})
        if isinstance(final_step, list):
            steps.extend(final_step)
        else:
            steps.append(final_step)
        if not steps:                    # a cut-tail door path with no hops
            self.on_arrive = None
            return False
        # AdjustEndMoveInZoneArea (Helpers.cs:125-136)
        last = steps[-1]
        if last.get('kind') == 'point' and 'x' in last:
            last['x'] = min(max(last['x'], dest.left), dest.right)
        if pcprofile.is_pc():
            self._pc_floor_marks(steps, self._pc_departure_step(steps))
            self._pc_claim_marks(steps)
        H['step_index'] = len(steps)                # FindPath's StepIndex stamp
        self._move_index = -1
        self.steps = steps
        self._next_step()
        return True

    def _link_steps(self, door, H):
        """Helpers.LinkNodes for one hop (_link_steps_mobile); under the PC
        profile a Season 2 transition's hop takes the PC pass's timing
        (_pc_hop_steps)"""
        steps = self._link_steps_mobile(door, H)
        if pcprofile.is_pc() and door.pc_pass.get(self.role) \
                and any(st.get('kind') == 'cpoint' for st in steps):
            steps = self._pc_hop_steps(door, steps)
        return steps

    def _link_steps_mobile(self, door, H):
        """Helpers.LinkNodes for one hop (Helpers.cs:225-357). `door` is the
        near-side door; the complex Transitions expand into walk steps —
        the walk-through stairs — instead of a warp."""
        if not (door.is_transition and door.complex_move):
            return [{'kind': 'door', 'door': door}]
        other = self.level.door_by_pid(door.link_to)
        if other is None:
            return [{'kind': 'door', 'door': door}]
        far_pid = other.zone
        # zone1 is the hop's destination, zone2 its origin (BuildPath walks
        # the chain backwards)
        zone1_pid = far_pid
        gtl_near = self.door_target(door)
        gtl_far = self.door_target(other)
        tl_near = (door.x + door.dx, door.y + door.dy)
        tl_far = (other.x + other.dx, other.y + other.dy)

        def plain(loc):
            return {'kind': 'point', 'x': loc[0]}
        def complex_step(loc, d):
            return {'kind': 'cpoint', 'x': loc[0], 'y': loc[1], 'door': d}
        def transfer(loc, complex_move):
            s = {'kind': 'cpoint' if complex_move else 'point',
                 'x': loc[0], 'transfer': far_pid, 'door': other}
            if complex_move:
                s['y'] = loc[1]
            return s

        if H['done_helper']:
            if door.nfh2_stairs:
                # the mid-stairs reroute shapes (Helpers.cs:253-304)
                aux = H['step_index'] - H['first_step_index']
                if aux in (2, 3, 4):
                    if H['original_start_zone'] != zone1_pid:
                        return [complex_step(gtl_far, other),
                                transfer(gtl_far, True)]
                    return [plain(gtl_near)]
                if aux == 1:
                    if H['original_start_zone'] != zone1_pid:
                        return [plain(gtl_near),
                                complex_step(gtl_far, other),
                                transfer(gtl_far, True)]
                    return [plain(gtl_near)]
                return []
            # the flat walk-through reroutes (Helpers.cs:307-335)
            si = H['step_index'] - H['first_step_index']
            H['step_index'] = si                    # StepIndex -= FirstStepIndex
            if si == 2:
                H['first_step_index'] = 2
                return [complex_step(tl_near, door),
                        complex_step(tl_far, other),
                        transfer(tl_far, False)]
            if si == 3:
                H['first_step_index'] = 3
                return [complex_step(tl_far, other),
                        transfer(tl_far, False)]
            if si == 4:
                if H['original_start_zone'] == door.zone:
                    H['first_step_index'] = 4
                    return [complex_step(tl_near, door),
                            complex_step(tl_far, other),
                            transfer(tl_far, False)]
                H['first_step_index'] = 1
                return [transfer(tl_far, False)]
            return []
        if door.nfh2_stairs:
            # the fresh stair shape (Helpers.cs:338-343)
            return [plain(gtl_near),
                    complex_step(gtl_far, other),
                    transfer(gtl_far, True)]
        # the fresh flat walk-through (Helpers.cs:344-350)
        return [plain(tl_near),
                complex_step(tl_near, door),
                complex_step(tl_far, other),
                transfer(tl_far, False)]

    # -- step machinery ----------------------------------------------------
    def _next_step(self):
        self.velocity = (0.0, 0.0)       # TakeNextStep (cs:1052), TryUseItem
                                         # (cs:1795) for an item's arrival
        prev, self._step = self._step, None
        if not self.steps:
            self.state = self.IDLE
            # OnPathFinished: the stand switch (Woody.cs:366; the base
            # TakeNextStep's, Pawn.cs:1070) with its Woody clears
            self._stand()
            cb, self.on_arrive = self.on_arrive, None
            if cb is None and self.role == 'Woody' and self.world is not None:
                # Woody.OnPathFinished (Woody.cs:361-362): a finished walk
                # drops the used inventory and the latched tooltip. An item
                # path keeps them for its use chain — the original's path
                # only finishes after UseCompleted (Woody.cs:443,
                # Pawn.cs:1752-1788), so that half belongs to the use tail
                self.world.inventory.used = None
                if self.world.hud is not None:
                    self.world.hud.colored_tooltip = False
            if cb:
                cb()
            return
        # AdvanceToNextMove's bookkeeping (Pawn.cs:1093-1106): MoveIndex,
        # the FlagAux clear at step 1, the DonePassing reset at the last
        # step, and the global FirstStepIndex stamp
        self._move_index += 1
        if self._move_index >= 1:
            # AdvanceToNextMove's reset (Pawn.cs:1059-1062)
            self.at_door_location = False
            self.last_exit_door = None
        if self._move_index == 1 and self.flag_aux:
            self.flag_aux = False
        if len(self.steps) == 1 and self.role == 'Woody':
            # entering the last step (MoveIndex == Steps.Count - 1,
            # Pawn.cs:1100-1104): the y-thresholds restamp and the flag drops
            self.y_neg = self.sprite.y - 0.15
            self.y_pos = self.sprite.y + 0.15
            self.done_passing = False
        self._helpers()['first_step_index'] = self._move_index
        # the step just walked: a hop's transfer hands its `out` run on
        after = prev.get('pc_after_run') if prev is not None else None
        self._step = self.steps.pop(0)
        if self._step.get('pc_hop') is None:
            self._pc_pass = None          # the PC pass pace ends with the hop
        self._pc_hold_t = 0.0
        if after is not None:
            # the `out` run of the hop just passed: a stand before this step
            self._step['pc_prehold'] = self._step.get('pc_prehold', 0.0) + self._pc_run_secs(after)
        if 'pc_secs' in self._step:
            tx, ty = self._step_target()
            self._step['pc_len'] = ((tx - self.sprite.x) ** 2 + (ty - self.sprite.y) ** 2) ** 0.5
            self._pc_step_t = 0.0
        if os.environ.get('NFH_WALK_LOG') == self.role:
            # the walk's diagnostics (tests/run_tricks.py: NFH_WALK_LOG=<role>)
            st = self._step
            print('walk %s t=%.2f zone=%s at=(%.2f,%.2f) step=%s target=%s %s' % (
                self.role, getattr(self.world, 'time', 0.0), getattr(self.zone, 'name', None),
                self.sprite.x, self.sprite.y, st.get('kind'), self._step_target(),
                {k: (v if not hasattr(v, 'name') else v.name) for k, v in st.items()
                 if k.startswith('pc_') or k in ('transfer',)}), file=sys.stderr)
        self._step_sign = None
        self._step_sign_y = None
        self.state = self.WALK

    def _step_target(self, s=None):
        """MoveLocation for the current step (or `s`). CheckMoveLocationY
        forces y to the floor for door and item steps — climbs are separate
        states."""
        if s is None:
            s = self._step
        if s['kind'] == 'point':
            return s['x'], s.get('y', self.floor_y())
        if s['kind'] == 'cpoint':
            # ComplexMove keeps the step's own y (CheckMoveLocationY skips it,
            # Pawn.cs:1135-1148), plus the transition's per-pawn walk delta
            # (Woody.cs:939-950 and the Mother/Olga overrides; 61 transitions
            # carry a Woody delta)
            x, y = s['x'], s.get('y', self.floor_y())
            d = s.get('door')
            if d is not None and getattr(d, 'walk_deltas', None):
                dx, dy = d.walk_deltas.get(self.role, (0.0, 0.0))
                x += dx
                y += dy
            return x, y
        if s['kind'] == 'door':
            d = s['door']
            zone = self.level.zone_by_pid(d.zone)
            return d.x + d.dx, self.floor_y(zone) if zone else self.sprite.y
        it = s['item']
        zone = self.level.zone_by_pid(it.zone)
        return s['x'], self.floor_y(zone) if zone else self.sprite.y

    def _min_dist(self):
        """MinDistToNextMove per step kind"""
        s = self._step
        if s['kind'] == 'door':
            d = s['door']
            return d.item_use_height if d.should_walk_up else d.use_distance
        if s['kind'] == 'item':
            it = s['item']
            return it.item_use_height if it.should_walk_up else it.use_distance
        return 0.03

    def _face_towards(self, dx):
        """the facing the walk sets: Walk_Right for a positive movement x,
        Walk_Left otherwise (Pawn.UpdateWalkingAnimation, Pawn.cs:1175-1179;
        WasMovingLeft = target.x < position.x, cs:1109)"""
        self.facing = 'Right' if dx > 0 else 'Left'

    def walk_speed_scale(self):
        """Pawn.ProcessMovement (Pawn.cs:871-879): position += Velocity * dt
        * Speed, or * SpeedSneaking while SneakFlag. Under the PC profile the
        pace is the PC's speed record along the current direction
        (pcprofile.walk_speed: 8 px a tick along the floor for the neighbour,
        17 for Woody, 5 sneaking, 3/6/2 up and down the room, 12 ticks a
        second at 96 px a unit; the neighbour's other gaits of the PC case,
        _pc_gait)."""
        if pcprofile.is_pc():
            vx, vy = self.velocity
            pace = self._pc_pass_pace()
            self.pc_pace = pace          # the PC-timed pace of this frame (tests/invariants.py)
            if pace is not None:
                n = (vx * vx + vy * vy) ** 0.5
                if n > 0.0:
                    return pace / n
            s = pcprofile.walk_speed(self.role, self.sneaking, vx, vy,
                                     climbing=self.state in (self.DOOR_CLIMB, self.DESCEND),
                                     stairs=bool(self.nfh2), gait=self._pc_gait())
            if s is not None:
                return s
        return self.speed_sneaking if self.sneaking else self.speed

    def _pc_pass_pace(self):
        """the pace (u/s) of a Season 2 door pass or station run under the
        profile, None off one: the mobile scene's path over the PC's ticks,
        whatever its length (a door's complex steps dip to the corridor and
        back — 208's Zone02 door 3.8 u for the PC's 230 px straight, 29
        ticks). GameLogic.dll walks a door pair as one step (vtable 0x100ab1b8,
        0x10003a19): up to the near door's `<actor>_in` in the near room
        (fcn.10003130), then out of every room (fcn.100037f8: fcn.10049467
        and fcn.10041ad0 with no room) straight on to the far door's
        `<actor>_out` — or the doors' enter and leave clips (fcn.10003647,
        fcn.10003236) — and into the far room there (fcn.10003454:
        fcn.10041ad0), whose floor the step's last movement comes down to.
        A transition's hop under the profile (_pc_hop_steps): its complex
        steps through the transfer last the straight movement's ticks, a
        stand before them the `in` run and one after the transfer the `out`
        run (pcprofile.s2_pass_ticks over Door.pc_pass); a back door's climb
        and descent last its `in` and `out` runs and its strips the clips, a
        station's climb its run up or down to the hotspot (_pc_climb_pace,
        set as they start), a timed step its `pc_secs`."""
        if self.state in (self.DOOR_CLIMB, self.DESCEND, self.ITEM_CLIMB):
            return self._pc_climb_pace
        st = self._step
        if st is None or self.state != self.WALK:
            return None
        if 'pc_secs' in st:
            ln = st.get('pc_len', 0.0)
            return ln / st['pc_secs'] if ln > 1e-6 and st['pc_secs'] > 0.0 else None
        near = st.get('pc_hop')
        if near is None:
            fl = st.get('pc_floor')
            return self._pc_floor_pace(st, fl) if fl is not None else None
        cur = self._pc_pass
        if cur is None or cur[0] is not near:
            # the hop's straight part starts: the complex path left of it,
            # through its transfer, against the PC movement's ticks
            p = near.pc_pass.get(self.role) or {}
            x, y = self.sprite.x, self.sprite.y
            length = 0.0
            for stp in [st] + list(self.steps):
                if stp.get('pc_hop') is not near:
                    break
                tx, ty = self._step_target(stp)
                length += ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5
                x, y = tx, ty
                if 'transfer' in stp:
                    break
            straight = {k: p[k] for k in ('dx', 'dy') if k in p}
            ticks = pcprofile.s2_pass_ticks(self.role, self._pc_gait(), straight, self.sneaking)
            pace = length * pcprofile.TICKS_PER_SECOND / ticks if ticks else None
            self._pc_pass = cur = (near, pace)
        return cur[1]

    def _pc_claim_marks(self, steps):
        """the PC profile's Season 2 door claim: GameLogic.dll's door-pass
        step (vtable 0x100ab1b8) waits in its first state while its door
        carries flag 8 (0x10003c54: fcn.100450dc), sets it on both doors of
        the pair as it starts (0x1000339d) — before the walk to the near
        door's `<actor>_in` — and clears it when the far room is set at
        `<actor>_out` (fcn.10003454 -> 0x100033d4). The first step of the
        stretch that leads to a door with a PC pass carries its door
        (`pc_claim`, _walk_on_path)"""
        start = 0
        for k, st in enumerate(steps):
            hold = st.get('pc_hold_run')
            door = None
            if hold is not None and hold[0] == 'in':
                door = hold[1]
            elif st.get('kind') == 'door' and st['door'].pc_pass.get(self.role):
                door = st['door']
            if door is not None and start is not None and start < len(steps):
                steps[start]['pc_claim'] = door
                start = None
            if 'transfer' in st or st.get('kind') == 'door':
                start = k + 1

    def _pc_claim_pair(self, door):
        """the door-pass step's first state: the pair taken, or False while
        another pawn holds it (the pawn stands where it is)"""
        other = self.level.door_by_pid(door.link_to)
        pair = [d for d in (door, other) if d is not None]
        for d in pair:
            holder = d.pc_claim
            if holder is not None and holder is not self:
                if holder._pc_holds(d):
                    return False
                holder._pc_release()      # a path it has dropped (a stale hold)
        self._pc_release()
        for d in pair:
            d.pc_claim = self
        self._pc_claimed = pair
        return True

    def _pc_holds(self, door):
        """the pawn still walks to or through the pair it holds: a step of its
        path names a door of it, or it is inside the pair's transit — the
        paths the port drops without a new route (a surprise, a catch) let
        the pair go this way"""
        pair = self._pc_claimed
        if not pair or door not in pair:
            return False
        for st in ([self._step] if self._step is not None else []) + list(self.steps):
            hold = st.get('pc_hold_run')
            if st.get('pc_hop') in pair or (hold is not None and hold[1] in pair) \
                    or st.get('door') in pair or st.get('pc_claim') in pair:
                return True
        return self.is_warping and getattr(self, '_exit_door', None) in pair

    def _pc_release(self):
        """the pair let go: the far room reached, or the path aborted"""
        pair, self._pc_claimed = self._pc_claimed, None
        for d in pair or ():
            if d.pc_claim is self:
                d.pc_claim = None

    def _pc_floor_pace(self, st, fl):
        """the pace (u/s) of a floor stretch (_pc_floor_marks): its mobile
        length over the PC ticks of its px at the gait, taken as it starts"""
        cur = self._pc_floor
        if cur is None or cur[0] is not fl:
            x, y = self.sprite.x, self.sprite.y
            length = 0.0
            for stp in [st] + list(self.steps):
                if stp.get('pc_floor') is not fl:
                    break
                tx, ty = self._step_target(stp)
                length += ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5
                x, y = tx, ty
            ticks = pcprofile.s2_pass_ticks(self.role, self._pc_gait(), {'dx': fl['px']}, self.sneaking)
            pace = length * pcprofile.TICKS_PER_SECOND / ticks if ticks else None
            self._pc_floor = cur = (fl, pace)
        if cur[1] is None:
            # no dx on the PC (two spots of the mobile scene at one PC x): the
            # movement has no horizontal tick — each step puts the pawn at its
            # target in a frame (the port's 60 Hz), a snap
            self.pos_snap = True
            tx, ty = self._step_target(st)
            return max(((tx - self.sprite.x) ** 2 + (ty - self.sprite.y) ** 2) ** 0.5, 1e-6) * 60.0
        return cur[1]

    def _pc_hop_steps(self, door, steps):
        """a transition's hop under the profile's Season 2 pass (Door.pc_pass):
        its complex steps and transfer marked for the straight movement's
        pace (_pc_pass_pace); the plain step that brings the pawn to the
        near door holds at its end for the `in` run, and the step after the
        transfer holds at its start for the `out` run — the pawn in the near
        zone, then the far one, as the PC's room pointer (fcn.10003454 sets
        the far room at `<actor>_out`, before the run down). No step is added:
        the step counts the mid-stairs reroutes read stay the mobile's."""
        first = True
        for k, st in enumerate(steps):
            hop = st.get('kind') == 'cpoint' or 'transfer' in st
            if hop and first and k > 0 and steps[k - 1].get('kind') == 'point' \
                    and 'transfer' not in steps[k - 1]:
                steps[k - 1]['pc_hold_run'] = ('in', door)
            if hop:
                first = False
                st['pc_hop'] = door
            if 'transfer' in st:
                st['pc_after_run'] = ('out', door)
        return steps

    def _pc_run_secs(self, run):
        """seconds of a hop's `in` or `out` run at the pawn's gait"""
        p = run[1].pc_pass.get(self.role) or {}
        ticks = pcprofile.s2_pass_ticks(self.role, self._pc_gait(),
                                        {run[0]: p.get(run[0], 0)}, self.sneaking)
        return (ticks or 0) / pcprofile.TICKS_PER_SECOND

    def _pc_station_ticks(self, it):
        """the ticks of the PC run between a station's hotspot and its room's
        floor at the pawn's gait (Item.pc_approach, the walk step fcn.10009215
        at the vertical record), None without one or when the pawn comes from
        a station at the same PC x (fcn.10009177 goes straight there)"""
        ap = it.pc_approach.get(self.role) if (it is not None and pcprofile.is_pc()) else None
        if not ap or pc_ap_x(ap, it) == self._pc_from_x:
            return None
        return pcprofile.s2_pass_ticks(self.role, self._pc_gait(), {'in': ap['px']}, self.sneaking) or None

    def _pc_arrived(self, it):
        """a station reached: the next walk leaves from its PC hotspot, or
        where the station's actions move the actor to along the floor
        (PCApproach `tx`, per visit: 205's skiing leaves him 400 px left of
        the skis — the visit about to play is the item's PCUseSeconds slot;
        `txt` for a tricked visit)"""
        ap = it.pc_approach.get(self.role) if (it is not None and pcprofile.is_pc()) else None
        if ap:
            tx = ap.get('tx', 0)
            if isinstance(tx, list):
                tx = tx[it.pc_use_visit % len(tx)] if tx else 0
            if 'txt' in ap and self.level is not None and it.is_tricked(self.level.items):
                # the tricked visit's own move (PCApproach `txt`, per visit on a
                # two-way station: the step's tricked variants — 207's sand
                # castle with the crayfish has him splash the kid 154 px on,
                # 214's manipulated pistol 95, 209's hot coal places him back
                # at it, 201's soaped puddle's crash_short 200 on the slip's
                # side)
                tx = ap['txt']
                if isinstance(tx, list):
                    tx = tx[it.pc_use_visit % len(tx)] if tx else 0
            self._pc_depart = (pc_ap_x(ap, it) + tx, ap['px'], self.sprite.x, self.sprite.y, it)
        else:
            self._pc_depart = None
        self._pc_from_x = None

    def _pc_station_route(self, dest, final_step):
        """the PC profile's Season 2 route from the station the pawn stands
        at to another station (Item.pc_approach `routes`: the rooms of the
        GoTo's path finder, fcn.1000a711 -> fcn.1000a421, a Dijkstra on the
        Manhattan distances between the stations' and the doors' hotspots
        and 500 a door) as the mobile zone hops; None elsewhere, where the
        mobile's Helpers.GetShortestPath stays"""
        dep = self._pc_depart
        if dep is None or self.zone is None:
            return None
        pcx, px, x0, y0, src = dep
        if abs(self.sprite.x - x0) > 0.1 or abs(self.sprite.y - y0) > 0.1:
            return None
        last = final_step[-1] if isinstance(final_step, list) and final_step else final_step
        it = last.get('item') if isinstance(last, dict) and last.get('kind') == 'item' else None
        ap = src.pc_approach.get(self.role) if (src is not None and it is not None) else None
        zones = ((ap or {}).get('routes') or {}).get(it.name) if it is not None else None
        if not zones or zones[0] != self.zone.name or zones[-1] != dest.name:
            return None
        by_name = {z.name: z.pid for z in self.level.zones}
        hops = []
        for z1, z2 in zip(zones, zones[1:]):
            p1, p2 = by_name.get(z1), by_name.get(z2)
            d = next((d for nb, d in self.level.graph.get(p1, ()) if nb == p2), None)
            if d is None or d.disabled or d.locked:
                return None
            hops.append((p2, d))
        return hops

    def _pc_room_route(self, dest, final_step):
        """the PC profile's Season 2 route of a walk from anywhere (pc_route:
        the GoTo's Dijkstra, fcn.1000a711 -> fcn.1000a421) — from the station
        the pawn stands at (its hotspot, _pc_depart) or its x on the room's
        floor line, to the last step's PC point (pc_target)"""
        z = self.zone
        if z is None or getattr(z, 'pc_room', None) is None:
            return None
        dep = self._pc_depart
        if dep is not None and abs(self.sprite.x - dep[2]) <= 0.1 \
                and abs(self.sprite.y - dep[3]) <= 0.1:
            pos = (dep[0], z.pc_room['floor'] + dep[1])
        else:
            pos = (pc_room_x(z, self.sprite.x), z.pc_room['floor'])
        last = final_step[-1] if isinstance(final_step, list) and final_step else final_step
        return pc_route(self.level, self.role, z, pos, dest, pc_target(self.role, dest, last))

    def _pc_departure_step(self, steps):
        """the PC profile's Season 2 departure: a path that leaves a station
        comes down from the PC object's hotspot to the room's floor first
        (fcn.10009177's first waypoint) — the floor step BuildPathToTarget
        inserts for an off-floor start lasts that run, and a pawn the mobile
        scene keeps on the floor stands it out before its first step; a path
        to a station at the same PC x has no run (straight on), and a level
        script's actor bound for a station of the same PC object walks none
        at all: its GoTo finds the actor at the object's hotspot and returns
        at once (fcn.1000e3e0) — the mobile scene's two use spots (210's
        Mother between her chair and her call, 206's weights, 213's Olga at
        the picnic) are one on the PC, the pawn is put on the next. Woody's
        walks are the player's clicks, not a script's GoTo"""
        dep, self._pc_depart = self._pc_depart, None
        self._pc_from_x = None
        if dep is None or not steps or self.portal_move:
            return None
        # (the mobile clip may have moved the pawn off its use spot — the
        # remaster's offsets, 212's bench, 205's ski ride — while the PC actor
        # stands at the hotspot, or where the actions' translations left it:
        # nothing but the use has run since the station was reached)
        pcx, px, _x0, _y0, src = dep
        if src is None or self.zone is None or src.zone != self.zone.pid:
            return None                   # put in another room since (a use's warp)
        last = steps[-1]
        it = last.get('item') if last.get('kind') == 'item' else None
        ap = it.pc_approach.get(self.role) if it is not None else None
        if ap is not None and pc_ap_x(ap, it) == pcx:
            self._pc_from_x = pcx
            sap = src.pc_approach.get(self.role) \
                if (src is not None and self.role != 'Woody') else None
            if sap is not None and sap.get('obj') == ap.get('obj') \
                    and all(st.get('kind') in ('point', 'item') for st in steps):
                tx, ty = self._step_target(last)
                if it.should_walk_up or it.should_walk_down:
                    ty = it.y             # at its use location, climbed
                self.sprite.x, self.sprite.y = tx, ty
                self._arm_item_snap(it, tx)
                self._pc_arrived(it)
                del steps[:]              # arrived: the path finishes at once
            return pcx
        ticks = pcprofile.s2_pass_ticks(self.role, self._pc_gait(), {'in': px}, self.sneaking)
        if not ticks:
            return pcx
        secs = ticks / pcprofile.TICKS_PER_SECOND
        first = steps[0]
        if first.get('kind') == 'point' and first.get('y') is not None \
                and abs(first['x'] - self.sprite.x) < 1e-9:
            first['pc_secs'] = secs       # the floor step down from the station
        else:
            first['pc_prehold'] = first.get('pc_prehold', 0.0) + secs
        return pcx

    def _pc_floor_marks(self, steps, x_pc):
        """the PC profile's Season 2 floor: a movement runs along the room's
        floor line from x to x (fcn.10009177's middle waypoint) one axis a
        tick at the gait's record (fcn.10009215), so a walk's stretch of floor
        between two points the PC data places — the station it leaves or
        goes to (Item.pc_approach `x`: its `<actor>` hotspot), a door's
        `<actor>_in` it walks to or the far door's `<actor>_out` it comes
        from (Door.pc_pass `xi` / `xo`) — lasts |dx| of the PC scene at the
        record, whatever the mobile scene's length between the same two
        points: its plain steps carry the stretch (`pc_floor`, the PC px;
        _pc_pass_pace). `x_pc`: the PC x the path leaves from (the station,
        _pc_departure_step), None off one — a stretch with an end the data
        does not place keeps the floor record over the mobile length (the
        data is Season 2's alone)"""
        run = []
        for st in steps:
            hop = st.get('pc_hop')
            if hop is not None:
                # the hop's straight movement has its own pace; the far room's
                # floor starts at the far door's `<actor>_out`
                run = []
                x_pc = (hop.pc_pass.get(self.role) or {}).get('xo') \
                    if 'transfer' in st else None
                continue
            kind = st.get('kind')
            if kind not in ('point', 'item', 'door'):
                run = []
                x_pc = None
                continue
            if 'pc_secs' in st:
                continue                  # the run down from a station: no dx
            run.append(st)
            end = None
            hold = st.get('pc_hold_run')
            if kind == 'door':
                # a back door's walk: to the near door's `<actor>_in`, the far
                # room's floor from its `<actor>_out`
                p = st['door'].pc_pass.get(self.role) or {}
                end, after = p.get('xi'), p.get('xo')
            elif hold is not None:
                end = (hold[1].pc_pass.get(self.role) or {}).get('xi')
                after = None              # the hop's steps set it
            elif kind == 'item':
                ap = st['item'].pc_approach.get(self.role)
                end = after = pc_ap_x(ap, st['item']) if ap else None
            else:
                continue                  # a waypoint: the stretch goes on
            if x_pc is not None and end is not None:
                mark = {'px': abs(end - x_pc)}
                for s2 in run:
                    s2['pc_floor'] = mark
            run = []
            x_pc = after

    def _pc_back_door_pace(self, door, key, dist):
        """a back door's climb (`in`) or descent (`out`) pace under the
        profile: `dist` u over the PC run's ticks at the gait's vertical
        record (Door.pc_pass); None without the pass"""
        p = door.pc_pass.get(self.role) if (door is not None and pcprofile.is_pc()) else None
        if not p:
            return None
        ticks = pcprofile.s2_pass_ticks(self.role, self._pc_gait(), {key: p.get(key, 0)}, self.sneaking)
        if not ticks or dist <= 0.0:
            return None
        return dist * pcprofile.TICKS_PER_SECOND / ticks

    # -- door transit -------------------------------------------------------
    def _door_anims(self, door):
        """the (Leave, Enter) door strips per pawn class: each override of
        PlayDoorLeave/EnterAnimation plays its own Door pair — Woody
        (Woody.cs:452-463), the Rottweiler (Rottweiler.cs:363-373), the
        Mother (Mother.cs:63-73), Olga (Olga.cs:94-104; her fields ship
        NONE on every door) — through Door.Play<Role>Enter/LeaveAnimation
        (Door.cs:85-139). The base Pawn plays no door strip at all
        (Pawn.cs:1615-1635); no other pawn class ever paths through a door
        (the Kid has no routine), so it falls to the same null branch."""
        if self.role == 'Woody':
            return door.leave, door.enter
        if self.role == 'Rottweiler':
            return door.rott_leave, door.rott_enter
        if self.role == 'Mother':
            return door.mother_leave, door.mother_enter
        if self.role == 'Olga':
            return door.olga_leave, door.olga_enter
        return None, None

    def _wait_for_passing(self, door, other):
        """MoveToDoor's head (Pawn.cs:1359-1364, MoveToAdjacentZone's
        1271-1276): a pair held by another pawn parks this one standing —
        every frame, so the retry rides the state that called"""
        if (door.passing is not None and door.passing is not self) or \
                (other.passing is not None and other.passing is not self):
            self.velocity = (0.0, 0.0)   # Velocity = zero, then the stand
            self._stand()
            return True
        return False

    def _begin_transit(self, door):
        """MoveToDoor's portal branch. A flat door fires both sides at once; a
        walk-up door climbs first and then runs Leave -> Enter sequentially
        (OnDoorLeaveAnimationFinished chains the far side). A pre-armed
        PortalMove (BuildPathToTarget, see _route) lands here without the
        walk and stays armed through a wait."""
        other = self.level.door_by_pid(door.link_to)
        if other is None:
            self.state = self.IDLE
            return
        if not (pcprofile.is_pc() and door.pc_pass.get(self.role)) \
                and self._wait_for_passing(door, other):
            return                        # IsOtherPawnPassing: wait standing
                                          # (the PC's claim otherwise, _pc_claim_marks)
        self.portal_move = False          # the pre-arm is consumed
        if door.should_walk_up:
            # MoveToDoor's first call raises PortalMove and MovingUp and
            # returns (cs:1367-1371): the climb strip and its velocity start
            # next frame, and the walk's Velocity integrates once more now
            self.state = self.DOOR_CLIMB
            # the PC profile: the climb lasts the Season 2 pass's `in` run
            # (the walk up to the near door's `<actor>_in`)
            thr = self.item_threshold + door.delta_use_height
            self._pc_climb_pace = self._pc_back_door_pace(
                door, 'in', abs(door.y - self.sprite.y) - thr)
            return
        # a finished-entrance pass through an ExitDoor asks first
        # (Pawn.cs:1378-1383; ExitConfirmationShown latches for the retry):
        # Woody.ShowExitConfirmation raises the dialog (Woody.cs:552-556)
        # over the base's park (cs:1445-1450); the application hangs the
        # dialog on World.show_exit_confirmation — the bare viewer has none
        # and passes straight through
        if door.exit_door and not self.exit_confirmation_shown \
                and self.finished_entrance and self.role == 'Woody' \
                and self.world is not None \
                and self.world.show_exit_confirmation is not None:
            self.exit_confirmation_shown = True
            self.waiting_for_exit_confirmation = True
            self.movement_paused = True   # PauseMovement, Velocity = 0
            self.velocity = (0.0, 0.0)
            self.world.show_exit_confirmation(self)
            return
        self.use_door_at_once = False     # Pawn.cs:1393
        # the PC runs the near door's `enter` and the far door's `leave` one
        # after the other through a flat door too (pcprofile.doors_sequential)
        self._transit_animations(
            door, other,
            sequential=pcprofile.is_pc() and pcprofile.doors_sequential(self.nfh2))

    def continue_exit(self):
        """Pawn.ContinueExit (Pawn.cs:1510-1515): ContinueMovement, the
        portal flag and the wait dropped — the next arrival re-enters
        MoveToDoor past the latched ExitConfirmationShown"""
        self.movement_paused = False
        self.portal_move = False
        self.waiting_for_exit_confirmation = False

    def abort_exit(self):
        """Pawn.AbortExit (Pawn.cs:1500-1508): EndPortalMove(abort) drops
        the portal flags without TakeNextStep, StopMovement + ContinueMovement
        leave the move inert (MoveLocationChanged false: the path no longer
        drives, as the alerter's RestartMovement models it), the latch
        clears, SwitchToStandAnimation"""
        self.portal_move = False
        self.steps = []
        self._step = None
        self._pc_release()
        self.state = self.IDLE
        self.movement_paused = False
        self.exit_confirmation_shown = False
        self.waiting_for_exit_confirmation = False
        self._stand()

    def _transit_animations(self, door, other, sequential):
        self.state = self.DOOR_ANIM
        # PlayDoorLeaveAnimation: SetHidden(true) hides the controller for
        # every pawn, and the `is Woody` branch hides Woody's own too
        # (Pawn.cs:1615-1635) — the door sheets contain the walking figure
        self.hidden = True
        self.sprite.hidden = True
        self.is_warping = True            # PlayDoorLeaveAnimation: IsWarping
        if self.role == 'Woody':
            # Woody's override locks the input for the span of the pass
            # (Woody.cs:459-463); without this a click landing mid-transit
            # builds a second route through the same door and the pass
            # animation plays twice
            self.input_locked = True
        self._exit_door = other
        door.passing = other.passing = self
        if self.world:
            self.world.zone_reaction(door.zone, 'leave')
            if not sequential:
                self.world.zone_reaction(other.zone, 'enter')
        leave_anim, _ = self._door_anims(door)
        _, enter_anim = self._door_anims(other)
        # the PC profile: a Season 2 back door's strips last the near door's
        # `enter` and the far door's `leave` (Door.pc_pass)
        pcp = door.pc_pass.get(self.role) if pcprofile.is_pc() else None
        if pcp and 'enter' in pcp:
            self._pc_clip_pace(door.sprite, leave_anim, pcp['enter'])
            self._pc_clip_pace(other.sprite, enter_anim, pcp['leave'])
        if sequential:
            # walk-up: Leave first; its end starts the far Enter
            def leave_done():
                door.passing = None
                if door.sprite is not None:
                    door.sprite.time_scale = 1.0
                self._door_idle(door)
                if self.world:
                    self.world.zone_reaction(other.zone, 'enter')
                if pcprofile.is_pc() and pcprofile.door_warp_early(self.nfh2):
                    # the PC places the pawn at the far door for its `leave`
                    # action and the room pointer follows the placement: the
                    # zone flips at the far clip's start (pcprofile.door_warp_early)
                    # — the catch predicates read it from here; the zone-change
                    # hooks (the routine's notices, the alerters, the item
                    # reactions) still run at the clip's end, in _enter_played
                    self._warp_through(other)
                self._play_enter(other, enter_anim)
            if door.sprite is not None and leave_anim:
                # Door.PlayAnimation is a PlaySingleAnimation behind
                # EnableAnimationController (Door.cs:141-153)
                if door.ignore_idle:
                    door.sprite.sprite.hidden = False
                door.sprite.play_sequence([leave_anim], on_end=leave_done,
                                          as_sequence=False)
            else:
                leave_done()              # Door.PlayAnimation's null branch
        else:
            if door.sprite is not None and leave_anim:
                if door.ignore_idle:
                    door.sprite.sprite.hidden = False
                door.sprite.play_sequence(
                    [leave_anim], on_end=lambda: self._leave_played(door),
                    as_sequence=False)
            else:
                door.passing = None
            self._play_enter(other, enter_anim)

    def _pc_clip_pace(self, player, name, ticks):
        """a door strip at the rate that lasts `ticks` of the 12 Hz tick (the
        PC profile's Season 2 back doors); the door's player keeps the scale
        until the strip ends"""
        if player is None or not name or not ticks or name not in player.by_name:
            return
        a = player.sprite.anims[player.by_name[name]]
        frames = len(a.pattern) if a.pattern else (a.end - a.start + 1)
        fps = pcprofile.clip_fps(a.name, a.fps or 10.0, frames)
        player.time_scale = (frames / fps) * pcprofile.TICKS_PER_SECOND / ticks

    def _door_idle(self, door):
        """Door.OnAnimationEnded ends every pass animation with
        ReturnToIdleAnimation (Door.cs:155-197, 209-224): the unlocked door
        rests on its alternate idle, and an IgnoreIdleAnimation door leaves
        its controller disabled — the sprite disappears between passes."""
        if door.sprite is None:
            return
        if door.ignore_idle:
            door.sprite.sprite.hidden = True
            return
        name = door.alternate_idle if door.use_alternate_idle else door.idle
        if name and door.sprite.has(name):
            door.sprite.play_looping(name)

    def _play_enter(self, other, enter_anim):
        if other.sprite is not None and enter_anim:
            if other.ignore_idle:         # EnableAnimationController
                other.sprite.sprite.hidden = False
            other.sprite.play_sequence([enter_anim], on_end=self._enter_played,
                                       as_sequence=False)
        else:
            self._enter_played()

    def _leave_played(self, door):
        """Door.OnAnimationEnded's *Leave cases (Door.cs:180-195):
        PassingPawn.OnDoorLeaveAnimationFinished (Pawn.cs:1682-1688 — only
        a ShouldWalkUp door does anything there, handled by leave_done
        above), ReturnToIdleAnimation, PassingPawn = null"""
        door.passing = None
        if door.sprite is not None:
            door.sprite.time_scale = 1.0  # the PC pass's strip pace (_pc_clip_pace)
        self._door_idle(door)

    def _warp_through(self, d):
        """WarpThroughDoor (Pawn.cs:1522-1528, 1560-1566): the placement at the
        far door and the zone change — at the far clip's end on the mobile,
        at its start under the PC profile (pcprofile.door_warp_early).
        Returns the zone left."""
        old_zone = self.zone.pid if self.zone else None
        self.sprite.x = d.x + self.door_delta[0]
        self.sprite.y = d.y + self.door_delta[1]
        # Woody and the Mother override the base warp with the door's own
        # exit offset (Woody.cs:476, Mother.cs:60)
        if self.role == 'Woody':
            self.sprite.x = d.x + d.delta_exit[0]
            self.sprite.y = d.y + d.delta_exit[1]
        elif self.role == 'Mother':
            self.sprite.x = d.x + d.delta_mother_exit[0]
            self.sprite.y = d.y + d.delta_mother_exit[1]
        self.zone = self.level.zone_by_pid(d.zone) or self.zone
        if self.role in ('Woody', 'Rottweiler'):
            # WarpThroughDoor -> PassDoor -> ChangeZone -> CrabAnimations
            # drops DonePassingToOtherZone on this zone change too
            # (Pawn.cs:1522-1528, 1560-1566, 1598-1602)
            self.done_passing = False
        # Rottweiler.OnDoorEnterAnimationFinished: a flat-door exit snaps the
        # neighbour back onto the floor line (Rottweiler.cs:168-172)
        if self.role == 'Rottweiler' and not d.should_walk_up:
            self.sprite.y = self.floor_y()
        self._warped = True
        self._warp_old = old_zone
        if self._pc_claimed and d in self._pc_claimed:
            self._pc_release()            # the PC placement at the far door
        return old_zone

    def _enter_played(self):
        """OnDoorEnterAnimationFinished: warp, unhide, loop ExitAnimation;
        a walk-up far door means climbing back down to the floor."""
        d = self._exit_door
        if d is None:
            return
        d.passing = None
        if d.sprite is not None:
            d.sprite.time_scale = 1.0     # the PC pass's strip pace (_pc_clip_pace)
        self._door_idle(d)
        if self._warped:
            old_zone = self._warp_old      # placed at the far clip's start (PC)
        else:
            old_zone = self._warp_through(d)
        hooked = self._warp_hooked
        self._warped = False
        self._warp_hooked = False
        if self.role == 'Woody':
            # the transit lock lifts on arrival (Woody.cs:471-474, 481-483):
            # a finished entrance unlocks outright, an unfinished one only
            # through a non-exit door
            if self.finished_entrance or not d.exit_door:
                self.input_locked = False
        self.hidden = False
        self.sprite.hidden = False        # SetHidden(false), Pawn.cs:1661
        self.is_warping = False           # OnDoorEnterAnimationFinished
        # the door-at-once bookkeeping (base OnDoorEnterAnimationFinished):
        # AtDoorLocation = ShouldWalkUp, LastExitDoor = the far door
        self.at_door_location = d.should_walk_up
        self.last_exit_door = d
        if self.role == 'Rottweiler':
            self.rott_last_door = d       # Pawn.cs:1645-1648
        if not hooked and self.world is not None \
                and old_zone != (self.zone.pid if self.zone else None):
            if self.world.on_pawn_zone_changed(self, old_zone):
                # OnChangeZone returned true: taken over — the catch check
                # still closes OnDoorEnterAnimationFinished (Pawn.cs:1666)
                if self.world is not None:
                    self.world.door_exit_catch()
                return
        if d.exit_anim and self.anim.has(d.exit_anim):
            self.anim.play_looping(d.exit_anim)
        if d.should_walk_up and self.steps:
            self.state = self.DESCEND
            # the PC profile: the descent lasts the Season 2 pass's `out` run
            # (from the far door's `<actor>_out` down to the room's floor)
            self._pc_climb_pace = self._pc_back_door_pace(
                self.level.door_by_pid(d.link_to), 'out',
                (self.sprite.y - self.floor_y()) - self.zone_threshold)
            down = self._portal_down_anim()
            if down and self.anim.has(down):
                self.anim.play_looping(down)
        else:
            self._next_step()
        if self.role == 'Woody' and self.world is not None:
            # the tutorial's door signal (Woody.OnDoorEnterAnimationFinished,
            # Woody.cs:477-480: the far door is compared)
            if self.world.level_script is not None:
                self.world.level_script.on_woody_door_entered(d)
            # a finished-entrance pass through an ExitDoor ends the level —
            # after the ExitAnimation loop and EndPortalMove, so the win /
            # lose pose is what stays on screen (Pawn.cs:1652-1665)
            if d.exit_door and self.finished_entrance:
                self.world.finish_game_on_hud_click()
            # a finish that arrived mid-pass plays at the arrival
            # (Woody.OnDoorEnterAnimationFinished, Woody.cs:490-493) and
            # returns before the catch check
            if self.world.should_play_finish:
                self.world._play_finish_animation()
                return
        # the arrival catch check closes the handler, after EndPortalMove
        # has taken the next step and the routine may have started its
        # use (Pawn.cs:1666-1670 for the other pawns, Woody.cs:495-496):
        # HitWoody's StopCurrentAction then cuts that use short, and the
        # hit sequence is what stays on the sheet
        if self.world is not None:
            self.world.door_exit_catch()

    # -- tick ---------------------------------------------------------------
    def _zone_watch(self):
        """Pawn.Update's lastZone2 watch (Pawn.cs:291-313): crossing into a
        new zone drops the complex-move state, releases the transition claim
        and — for Woody — runs one catch check"""
        if self._last_zone2 is not self.zone:
            if self.role == 'Woody' and self.passing_complex:
                self.check_for_neighbour = True
            self.passing_complex = False
            te = self.transition_enter
            if te is not None:
                link = self.level.door_by_pid(te.link_to)
                if link is not None and link.passing_nfh2 is self:
                    link.passing_nfh2 = None
                if te.passing_nfh2 is self:
                    te.passing_nfh2 = None
            self.transition_enter = None
        if self.check_for_neighbour:
            self.check_for_neighbour = False
            w = self.world
            if w is not None:
                # the crossing check is the door-exit predicate — no
                # sneaking escape (Pawn.cs:310-311, 366-388)
                w.door_exit_catch()
        # ItemAux arms FlagAux for walk-up items in the same zone
        # (Pawn.cs:314-317)
        ia = self.item_aux
        if ia is not None and ia.should_walk_up and self.role == 'Woody' \
                and self.zone is not None and ia.zone == self.zone.pid:
            self.flag_aux = True
        self._last_zone2 = self.zone
        # the DonePassingToOtherZone tracker (Pawn.cs:319-342)
        if (self.go_zone is not None or self.door_clicked is not None) \
                and self.nfh2 and self.role == 'Woody' \
                and not self.done_passing and not self.flag_aux:
            y = self.sprite.y
            if y > 0.0:
                if y < self.y_neg and self.y_neg > 0.0:
                    self.done_passing = True
            elif y < 0.0:
                if y < self.y_neg and self.y_neg < 0.0:
                    self.done_passing = True
                elif y > self.y_pos and not self.done_passing:
                    self.done_passing = True

    def _complex_arrival(self):
        """MoveToAdjacentZone's complex-step head (Pawn.cs:1220-1270): claim
        the transition pair, stand while another pawn holds it, and set
        PassingComplexMove — with Woody's entry catch check (cs:1228-1233).
        Returns True when the pawn must stand and wait."""
        s = self._step
        nxt = self.steps[0] if self.steps else None
        active = ((nxt is not None and nxt.get('kind') == 'cpoint')
                  or (s is not None and s.get('kind') == 'cpoint'))
        if not active:
            te = self.transition_enter
            if te is not None:
                link = self.level.door_by_pid(te.link_to)
                if link is not None and link.passing_nfh2 is self:
                    link.passing_nfh2 = None
                if te.passing_nfh2 is self:
                    te.passing_nfh2 = None
            self.transition_enter = None
            self.passing_complex = False
            return False
        # MoveTransitionNFH2 (Pawn.cs:996-1030)
        cd = None
        if nxt is not None and nxt.get('kind') == 'cpoint' \
                and nxt.get('door') is not None:
            cd = nxt['door']
        elif s is not None and s.get('kind') == 'cpoint' \
                and s.get('door') is not None:
            cd = s['door']
        if cd is not None:
            # TransitionEnter is assigned before the claim test (Pawn.cs:1004,
            # 1014), so a pair already held by another pawn parks this one
            # standing on the first approach (cs:1022-1027)
            self.transition_enter = cd
            link = self.level.door_by_pid(cd.link_to)
            if link is not None and (cd.passing_nfh2 is None
                                     or link.passing_nfh2 is None):
                cd.passing_nfh2 = self
                link.passing_nfh2 = self
            elif cd.passing_nfh2 is not None and cd.passing_nfh2 is not self \
                    and not (pcprofile.is_pc() and cd.pc_pass.get(self.role)):
                # (under the PC profile a pair with a PC pass is the PC's
                # door-pass step's to hold, from the walk to the door on:
                # _pc_claim_marks)
                self.velocity = (0.0, 0.0)
                self._stand()
                return True
        w = self.world
        if self.role == 'Woody' and w is not None:
            if w.can_rottweiler_see_woody() and not w.game.got_caught \
                    and not w._pc_catch_barred():
                w._catch()
                return True
        self.passing_complex = True
        return False

    def _transfer_zone(self, zone_pid):
        """TakeNextStep's TransferToZone -> ChangeZone (Pawn.cs:1054-1057,
        1526-1534): the zone swap, the crab/search zone reactions and the
        DonePassing reset"""
        old = self.zone
        new = self.level.zone_by_pid(zone_pid)
        if new is None:
            return
        self.zone = new
        if self.role in ('Woody', 'Rottweiler'):
            self.done_passing = False        # CrabAnimations, Pawn.cs:1566
        if self.world is not None:
            if old is not None:
                self.world.zone_reaction(old.pid, 'leave')
            self.world.zone_reaction(new.pid, 'enter')
            old_pid = old.pid if old is not None else None
            self.world.on_pawn_zone_changed(self, old_pid)

    def tick(self, dt):
        self.anim.tick(dt)
        if pcprofile.is_pc() and self.rage_max > 0:
            # the PC level state's tick (game.exe fcn.00438a80, 12 Hz): the
            # hold counts down first, then the current; the mobile meter
            # mirrors the mercury, current * 100 / the level's angrytime
            self.rage_acc += dt
            period = 1.0 / pcprofile.S1_TICK_HZ
            while self.rage_acc >= period - 1e-9:
                self.rage_acc -= period
                self.rage_current, self.rage_hold = \
                    pcprofile.s1_rage_tick(self.rage_current, self.rage_hold)
                if self.rage_current == 0:
                    self.rage_bonus = False
            self.angry_meter = float(
                pcprofile.s1_rage_percent(self.rage_current, self.rage_max))
        elif pcprofile.is_pc() and self.rage_decay_tick > 0:
            # the PC Season 2 gauge (GameLogic.dll's level update 0x100442b3,
            # 0x100447c4, 12 Hz): the
            # rage falls by the level's `time` every tick, no latch
            self.rage_acc += dt
            period = 1.0 / pcprofile.S2_TICK_HZ
            while self.rage_acc >= period - 1e-9:
                self.rage_acc -= period
                if self.angry_meter > 0.0:
                    self.angry_meter = pcprofile.s2_rage_tick(
                        self.angry_meter, self.rage_decay_tick)
        elif self.can_decrease_angry and self.angry_meter > 0.0:
            # Rottweiler.Update: the meter decays while allowed
            self.angry_meter = max(0.0, self.angry_meter - self.angry_decay * dt)
        self._zone_watch()
        if self.movement_paused:          # ProcessMovement's outer gate
            return
        # ProcessMovement (Pawn.cs:855-880): WalkOnPath settles this frame's
        # Velocity — snapping and switching moves on the way — and only then
        # does the position integrate it. Velocity outlives the frame:
        # TakeNextStep (cs:1052) and TryUseItem (cs:1795) zero it, the
        # entries of MoveToItem and MoveToDoor do not, so the walk's last
        # velocity lands once more on the frame a climb begins — the
        # SoapChest trace in tools/livediff/README.md is the reference
        if self._step is not None and self.state == self.WALK:
            # the PC profile's timed steps and holds (_pc_departure_step,
            # _pc_hop_steps, the station approach)
            if 'pc_secs' in self._step:
                self._pc_step_t += dt
            if 'pc_prehold' in self._step or self._step.get('pc_holding'):
                self._pc_hold_t += dt
        self._walk_on_path()
        vx, vy = self.velocity
        if self.state in self.MOVING and (vx or vy):
            # MinimumVelocitySquared is 0 on all 84 shipped pawns
            scale = self.walk_speed_scale() * dt
            self.sprite.x += vx * scale
            self.sprite.y += vy * scale

    def _walk_on_path(self):
        """WalkOnPath with MoveToItem and MoveToDoor as the port's states:
        every branch leaves the frame's Velocity behind instead of moving"""
        snap = self._item_snap
        if snap is not None:
            # MoveToItem's head on the frame after TryUseItem (cs:1735-1738):
            # MovingUp is clear, so a target the walk crossed (HasPassedTarget
            # against the current x, cs:1037-1040) and can pass snaps the x.
            # The original repeats this every frame of the use; nothing
            # moves the x meanwhile here, so once is the same
            tx, was_left, passable = snap
            self._item_snap = None
            if passable and ((tx < self.sprite.x) != was_left):
                self.sprite.x = tx
                self.pos_snap = True
        if self.state == self.WALK:
            if self.portal_move and self._step.get('kind') == 'door':
                # a pre-armed PortalMove skips the walk (WalkOnPath's guard,
                # Pawn.cs:957) — MoveToDoor runs from where the pawn stands
                # (cs:983, 1389-1417)
                self._begin_transit(self._step['door'])
                return
            st0 = self._step
            if st0.get('pc_prehold', 0.0) > 0.0 and self._pc_hold_t < st0['pc_prehold'] - 1e-9:
                # the PC profile: a run the mobile scene has no depth for,
                # stood out before the step moves (_pc_hop_steps' `out` run,
                # _pc_departure_step)
                self.velocity = (0.0, 0.0)
                self._stand()
                return
            if 'pc_prehold' in st0:
                del st0['pc_prehold']
                self._pc_hold_t = 0.0
            door = st0.get('pc_claim')
            if door is not None and not st0.get('pc_claimed'):
                # the PC's door-pass step starts: its pair, or a stand where
                # the pawn is while another holds it (_pc_claim_marks)
                if not self._pc_claim_pair(door):
                    self.velocity = (0.0, 0.0)
                    self._stand()
                    return
                st0['pc_claimed'] = True
            tx, ty = self._step_target()
            dx, dy = tx - self.sprite.x, ty - self.sprite.y
            mag = (dx * dx + dy * dy) ** 0.5
            # HasPassedTarget: WalkOnPath also stops when the pawn has crossed
            # the target x — a step can be bigger than UseDistance, and without
            # this the pawn oscillates around the goal forever. The original
            # tracked x only; a fixed 1/60 step makes the same loop possible
            # on the y axis (arrival window 2*MinDist < one velocity step), so
            # the same crossing check guards y too.
            sign = (dx > 0) - (dx < 0)
            passed = (self._step_sign is not None and sign != 0
                      and sign != self._step_sign)
            if self._step_sign is None and sign != 0:
                self._step_sign = sign
            sign_y = (dy > 0) - (dy < 0)
            passed_y = (self._step_sign_y is not None and sign_y != 0
                        and sign_y != self._step_sign_y)
            if self._step_sign_y is None and sign_y != 0:
                self._step_sign_y = sign_y
            # CanPassTarget (Pawn.cs:1032-1035, 1725-1728): the crossing snap
            # runs only on steps with a Passable target — an impassable door
            # (L201's TransitionDownwards, L213's DoorBack) leaves the pawn
            # where the crossing found it, as does a bare point step
            s0 = self._step
            target = s0.get('door') if s0['kind'] == 'door' else \
                s0.get('item') if s0['kind'] == 'item' else None
            can_pass = target is not None and getattr(target, 'passable', True)
            if passed and can_pass:
                self.sprite.x = tx        # MoveToItem snaps onto the target
                self.pos_snap = True
            if passed_y:
                if can_pass:
                    self.sprite.y = ty
                    self.pos_snap = True
                passed = True
            if mag <= self._min_dist() or passed:
                s = self._step
                if 'pc_secs' in s and self._pc_step_t < s['pc_secs'] - 1e-9:
                    # a timed step of the PC profile holds until its time is out
                    self.velocity = (0.0, 0.0)
                    self._stand()
                    return
                run = s.get('pc_hold_run')
                if run is not None:
                    # the `in` run of the hop this step brings the pawn to,
                    # stood out at the near door (_pc_hop_steps)
                    if not s.get('pc_holding'):
                        s['pc_holding'] = True
                        s['pc_hold'] = self._pc_run_secs(run)
                        self._pc_hold_t = 0.0
                    if self._pc_hold_t < s['pc_hold'] - 1e-9:
                        self.velocity = (0.0, 0.0)
                        self._stand()
                        return
                # MoveToAdjacentZone runs at arrival for the NFH2 pawns
                # (Pawn.cs:983); a held transition parks the pawn standing
                if self.adjacent_zones and self._complex_arrival():
                    return
                if s.get('transfer') is not None:
                    self._transfer_zone(s['transfer'])
                    if s.get('pc_hop') is not None:
                        self._pc_release()   # the far room set at `<actor>_out`
                if s['kind'] == 'door':
                    self._begin_transit(s['door'])
                elif s['kind'] == 'item' and s['item'].should_walk_up:
                    # MoveToItem's first call (cs:1740-1752) raises ItemMove
                    # and MovingUp and returns: the climb strip, the velocity
                    # and the use-location test start next frame, and the
                    # walk's Velocity integrates once more below
                    self.state = self.ITEM_CLIMB
                    # the PC profile: the climb lasts the PC run up or down to
                    # the station's hotspot (Item.pc_approach)
                    it = s['item']
                    ticks = self._pc_station_ticks(it)
                    dist = abs(it.y - self.sprite.y) - (self.item_threshold + it.delta_use_height)
                    self._pc_climb_pace = (dist * pcprofile.TICKS_PER_SECOND / ticks
                                           if ticks and dist > 0.0 else None)
                else:
                    if s['kind'] == 'item':
                        if not s.get('pc_approached'):
                            # the PC profile: the run up or down to the
                            # station's hotspot, stood out where the mobile
                            # scene has no climb (Item.pc_approach)
                            s['pc_approached'] = True
                            ticks = self._pc_station_ticks(s['item'])
                            if ticks:
                                s['pc_secs'] = ticks / pcprofile.TICKS_PER_SECOND
                                s['pc_len'] = 0.0
                                self._pc_step_t = 0.0
                                self.velocity = (0.0, 0.0)
                                self._stand()
                                return
                        self._arm_item_snap(s['item'], tx)
                        self._pc_arrived(s['item'])
                    self._next_step()     # TryUseItem / TakeNextStep: zero
                return
            nx, ny = dx / mag, dy / mag
            # WalkOnPath: dominant axis picks the force and the animation, and
            # IsInUrgentMove switches to the Running magnitudes; _walk_anim
            # holds each pawn's UpdateWalkingAnimation override
            if self.walk_hook is not None:
                # WalkOnPath -> UpdateWalking (Pawn.cs:981, Rottweiler.cs:833)
                self.walk_hook()
                if self.state != self.WALK:
                    return                # a near-surprise took the pawn over
            if nx != 0.0 and abs(nx) > abs(ny):   # cs:961-969
                f = self.run_force if self.in_urgent else self.force
                self._face_towards(nx)
                self.anim.play_looping(self._walk_anim(self.facing))
            else:                                  # cs:970-979
                f = self.run_door_force if self.in_urgent else self.door_force
                self.anim.play_looping(
                    self._walk_anim('Up' if ny > 0 else 'Down'))
            self.velocity = (nx * f, ny * f)
        elif self.state == self.DOOR_CLIMB:
            # checks run before the move, as MoveToDoor runs before
            # ProcessMovement applies the velocity
            d = self._step['door']
            other = self.level.door_by_pid(d.link_to)
            if other is None:
                self.state = self.IDLE
                return
            if self._wait_for_passing(d, other):
                return                    # MoveToDoor's head, Pawn.cs:1359
            # the climb arm (Pawn.cs:1398-1416): the climb strip is
            # re-asserted every frame (a wait's stand ends), and
            # UseDoorAtOnce leaves at once, from any height
            up = self._portal_up_anim()
            if up and self.anim.has(up):
                self.anim.play_looping(up)
            # the velocity precedes the arrival test (cs:1404-1416), and the
            # leave animation leaves it standing (cs:1615-1626): the hidden,
            # warping pawn keeps rising in the original until the far door
            # places it (OnDoorEnterAnimationFinished) — DOOR_ANIM is not a
            # MOVING state here, the placement makes the drift moot
            self.velocity = (0.0, self.run_door_force if self.in_urgent
                             else self.door_force)
            if self.at_use_location(d) or self.use_door_at_once:
                self.use_door_at_once = False           # Pawn.cs:1414
                self._transit_animations(d, other, sequential=True)
                return
        elif self.state == self.DESCEND:
            # WalkOnPath's else-branch runs MoveToItem before MoveToDoor on
            # every frame of the descent as well (Pawn.cs:983), and its head
            # (cs:1735-1738) snaps x to the step's TargetLocation.x — the
            # NEAR door's — when the walk has crossed it (HasPassedTarget
            # against WasMovingLeft as the walk set it) and the door is
            # Passable: the far door's placement (WarpThroughDoor, Woody's
            # DeltaExitLocation) keeps its y, but the pawn comes down the
            # stairs at the near door's x. Level101/111 click traces
            # (tools/livediff/README.md).
            d = self._step.get('door')
            if d is not None and self._step_sign is not None \
                    and getattr(d, 'passable', True):
                tx = self._step_target()[0]
                sign = (tx > self.sprite.x) - (tx < self.sprite.x)
                if sign != 0 and sign != self._step_sign \
                        and abs(self.sprite.x - tx) > 1e-9:
                    self.sprite.x = tx
                    self.pos_snap = True
            # IsAtPortalTargetLocation: signed, no snapping afterwards
            if self.sprite.y - self.floor_y() < self.zone_threshold:
                self._next_step()         # EndPortalMove -> TakeNextStep
                return
            self.velocity = (0.0, -(self.run_door_force if self.in_urgent
                                    else self.door_force))    # cs:1430-1437
        elif self.state == self.ITEM_CLIMB:
            # MoveToItem's climb (cs:1756-1787): the strip re-asserted, the
            # velocity set, then the use-location test — where TryUseItem
            # zeroes the velocity in the same frame (cs:1795)
            it = self._step['item']
            up = self._portal_down_anim() if it.should_walk_down \
                else self._portal_up_anim()
            if up and self.anim.has(up):
                self.anim.play_looping(up)
            direction = -1.0 if it.should_walk_down else 1.0
            self.velocity = (0.0, direction * (self.run_door_force
                                               if self.in_urgent
                                               else self.door_force))
            if self.at_use_location(it):
                self.velocity = (0.0, 0.0)
                self._arm_item_snap(it, self._step_target()[0])
                self._pc_arrived(it)
                self._next_step()         # on_arrive fires the use

    def _arm_item_snap(self, item, tx):
        """the state MoveToItem's head will test next frame (cs:1735-1738):
        WasMovingLeft as TakeNextStep set it (cs:1109) and Passable"""
        self._item_snap = (tx, self._step_sign == -1,
                           getattr(item, 'passable', True))


class AlerterFSM:
    """Alerter.cs, the sleeping pet. Two booleans (Awake, Alert) plus the two
    AlerterDelay coroutines; every sequence that Alerter.cs starts with the
    OnAnimationSequenceCompleted callback carries it here too."""

    def __init__(self, world, item):
        self.world = world
        self.item = item
        self.player = world.players.get(id(item.sprite)) if item.sprite else None
        self.awake = False
        self.alert = False
        self.triggered_by_woody = False
        self.animation_type = 0
        self.can_start = True            # IntroAnimation.cs:293 sets it post-intro
        self.start_timer = item.alert_on_start_timer
        self._see_delay = None           # CoRoutineWoodySeeAlerter
        self._see_hold = 0
        self._hear_hold = 0
        self._hear_delay = None          # CoRoutineRottweilerHearAlerter
        if self.player is not None:
            self._play(item.sleep_sequence, chain=True)

    # -- helpers -----------------------------------------------------------
    def _play(self, names, chain=False):
        if self.player is None:
            return
        names = [n for n in names if n and self.player.has(n)]
        if names:
            self.player.play_sequence(
                names, on_end=self._sequence_done if chain else None)
        elif chain:
            self._sequence_done()

    def _woody(self):
        return self.world.woody

    def _woody_moving(self):
        w = self._woody()
        return w is not None and w.state in (w.WALK, w.DOOR_CLIMB,
                                             w.DESCEND, w.ITEM_CLIMB)

    def can_see_woody(self):
        """Alerter.CanSeeWoody: Woody.IsSneaking counts standing still as
        sneaking (Woody.cs:1075), and only fools a sleeping pet."""
        w = self._woody()
        if w is None or w.zone is None or w.zone.pid != self.item.zone:
            return False
        sneaking = w.sneaking or not self._woody_moving()
        return not w.is_warping and not w.hiding and (not sneaking or self.awake)

    def _alert_pair(self):
        w = self._woody()
        left = w is not None and w.sprite.x < self.item.x
        a = self.item.alert_left if left else self.item.alert_right
        return [a, a]

    # -- the Alerter.Update body -------------------------------------------
    def tick(self, dt):
        w = self._woody()
        if w is None:
            return
        if self.can_see_woody() and self._woody_moving() and not self.alert:
            self.animation_type = 1
            self.triggered_by_woody = True
            self.on_notice_woody()
        elif (w.zone is not None and w.zone.pid == self.item.zone
                and not w.is_warping and not self.alert and self.awake
                and not self._woody_moving() and not w.hiding):
            self.animation_type = 0
            self.triggered_by_woody = True
            self.on_notice_woody()
        if not self.can_see_woody() and not self.alert:
            self.triggered_by_woody = False
        if self.can_start and self.start_timer > 0.0:
            self.start_timer -= dt
            if self.start_timer <= 0.0:
                self.triggered_by_woody = False
                self.on_notice_woody()
        # the two AlerterDelay coroutines (Alerter.cs:92-99, 106-113): a
        # WaitForSeconds started from an animation's end — the door's
        # OnAnimationEnded that brought Woody into the zone — and counted in
        # single precision; the original's flinch comes 32 frames after the
        # placement for a 0.5 s delay (Level111, tools/livediff/README.md):
        # the 30 frames of the wait, and two for the coroutine's start and
        # resume around the frame's phases — three holds here, the first
        # of which the same tick's FSM pass consumes
        if self._see_delay is not None:
            if self._see_hold:
                self._see_hold -= 1
            else:
                self._see_delay -= dt
                if self._see_delay <= WAIT_EPS:
                    self._see_delay = None
                    if self.can_see_woody():
                        self.world.woody_see_alerter(self.item)
        if self._hear_delay is not None:
            if self._hear_hold:
                self._hear_hold -= 1
            else:
                self._hear_delay -= dt
                if self._hear_delay <= WAIT_EPS:
                    self._hear_delay = None
                    self.world.rott_hear_alerter(self, self.triggered_by_woody)

    def on_notice_woody(self):
        self.wake_up()
        self._see_delay = self.item.alerter_delay
        self._see_hold = 3

    def wake_up(self):
        self._hear_delay = self.item.alerter_delay
        self._hear_hold = 3
        self.awake = True
        self.alert = True
        if self.animation_type == 1:
            seq = [self.item.alert_start] + self._alert_pair()
        else:
            seq = self._alert_pair()
        self._play(seq, chain=True)

    def on_rottweiler_enter(self):
        self.awake = True
        self._play(self.item.poor_sequence)      # no completion chain

    def on_rottweiler_leave(self):
        if self.awake:
            self._play(self.item.wake_sequence, chain=True)
            self.alert = False

    def _sequence_done(self):
        """Alerter.OnAnimationSequenceCompleted"""
        w = self._woody()
        rott = self.world.pawns.get('Rottweiler')
        if self.alert:
            if (w is not None and w.zone is not None
                    and w.zone.pid == self.item.zone
                    and not w.hiding and not w.is_warping):
                self._play(self._alert_pair(), chain=True)
            else:
                self.alert = False
                self._play(self.item.wake_sequence, chain=True)
        elif self.awake:
            if (rott is None or rott.zone is None
                    or rott.zone.pid != self.item.zone) \
                    and not self.can_see_woody():
                self.awake = False
                self.alert = False
                self._play(self.item.sleep_sequence, chain=True)


class InventoryState:
    """InventoryManager: a flat list, a two-stage selection — clicking an
    icon sets CurrentInventory, the next world-bound click promotes it to
    UsedInventory (HUD.CheckClick, HUD.cs:1309-1322)."""

    def __init__(self):
        self.items = []                  # dicts: {'type','use_count','name'}
        self.used = None                 # UsedInventory
        self.current = None              # CurrentInventory
        # HUD.OnInventoryAdded / OnInventoryRemoved (InventoryManager.cs:20,
        # 53) — the HUD hooks its paging in here
        self.on_added = None
        self.on_removed = None

    def add(self, new_items):
        """InventoryManager.AddInventory (InventoryManager.cs:15-23): the
        list grows first, then OnInventoryAdded fires once per new item"""
        new_items = [dict(i) for i in new_items]
        self.items.extend(new_items)
        for _ in new_items:
            if self.on_added is not None:
                self.on_added()

    def has(self, required):
        """InventoryManager.HasInventory"""
        return any(i['type'] == required for i in self.items)

    def is_using(self, required):
        """InventoryManager.IsUsingInventory"""
        return self.used is not None and self.used['type'] == required

    def remove(self, required):
        """InventoryManager.RemoveInventory (InventoryManager.cs:47-58):
        first match only; OnInventoryRemoved fires before the RemoveAt, so
        the HUD's clamp still sees the old count"""
        for i, it in enumerate(self.items):
            if it['type'] == required:
                if self.on_removed is not None:
                    self.on_removed()
                del self.items[i]
                break
        if self.used is not None and self.used['type'] == required and \
                not self.has(required):
            self.used = None
        if self.current is not None and self.current['type'] == required \
                and not self.has(required):
            self.current = None

    def promote(self):
        """the non-icon click's SetUsedInventory(CurrentInventory) +
        SetCurrentInventory(null) pair (HUD.cs:1320-1322): both writes are
        unconditional (Woody.SetUsedInventory, Woody.cs:1062-1073), so a
        click with nothing selected also drops the used one"""
        self.used = self.current
        self.current = None

    def select(self, idx):
        """the viewer's digit keys / the recorder's `inv N`: the icon click's
        SetCurrentInventory (HUD.cs:1314) — the next non-icon click promotes
        it exactly as an icon click would; 0 (idx -1) deselects"""
        self.current = self.items[idx] if 0 <= idx < len(self.items) else None


class GameState:
    """GameInfo: trick counters and the win flags."""

    def __init__(self, info):
        self.total = info.get('total', 0)
        self.winning = info.get('winning', 0)
        self.completed = 0
        self.won = False
        self.caught_by = None            # the port's record: 'Rottweiler' / 'Mother'
        self.linked_trick = False
        self.compound_tricks = 0
        self.log = []
        self.got_caught = False          # GameInfo.gotCaught
        self.ending = False              # GameInfo.GameEnding (FinishGame)
        self.ended = False               # GameInfo.GameEnded (FinishAnimationEnded)
        self.win_timer = None            # WinGameOnCompleteAllTricks' 2.5s wait
        self.win_immediate = False       # GameInfo.WinImmediate (ForceWinGame)
        self.lives = 0                   # PC profile only: On Vacation's three attempts
        self.final_trick_score = 0       # GameInfo.FinalTrickScore
        # the clock: TimedGame counts down from TimeMinutes, else up
        # (GameInfo.Start 171-177, Update 239-254; PlayerPrefs default is on)
        self.timed = True
        self.time_seconds = (info.get('time_minutes') or 0.0) * 60.0
        self.time_up = False
        self.is_tutorial = bool(info.get('is_tutorial'))
        self.compound_trick_score = info.get('compound_trick_score') or 0
        self.ignore_score = bool(info.get('ignore_score'))
        self.dont_show_angry_count = bool(info.get('dont_show_angry_count'))
        # the score screen strings (GameInfo.CalculateScore)
        self.rating = ''
        self.trick_ratio = ''
        self.viewer_rating = ''
        self.final_viewer_rating = 0
        self.pc_points = None            # PC profile: the COLLAPSE! board's sum
        self.pc_min_rating = None        # PC profile: the level's minquota (Season 1)
        self.pc_lines = []               # its rows, (points, label)
        self.on_trick_done = None        # Woody.PlayTrickDone -> the HUD
        # GameInfo.ShowInteractionIcon: true while the HUD info button is
        # held; every item then draws its ItemTipIcon (HUD.cs:860-895)
        self.show_interaction_icon = False

    def calculate_score(self, angry_count_ticks, nfh2=False, elapsed=0.0):
        """GameInfo.CalculateScore + CalculateRating (GameInfo.cs:392-465).
        The label lines ride localization files that are not extracted, so
        only the value halves render. `elapsed` (the seconds played) is the
        PC profile's clock input; the mobile score never reads the clock."""
        if not nfh2 and pcprofile.is_pc():
            # the PC's viewer rating, read live off Badinfos' HUD (E01: 16 ->
            # 49 -> 72 -> 100 for Microwave 16, Binoculars 30, TV 20, Sofa 25
            # with the tick counter 0/1/2/3; E02: 18, 31, 44, 54, 72, 100 for
            # Beer 18, three 10s, TV 15, Sofa 25 with 0/1/2/2/3/4): each
            # trick pays its TrickScore — the mobile data's values ARE the
            # PC's — plus 3 for every angry tick; the mobile's
            # CompletedTricksCount x min(CompoundTrickScore, ticks) reaches
            # the same 100 at the end of both runs but not the same value on
            # the way (E02 after two tricks: 48 against the PC's 49)
            final = self.final_trick_score + 3 * angry_count_ticks
            if self.pc_min_rating is not None:
                # the PC's SUCCESS: the minimum viewer rating reached
                # (leveldata minquota; the manual's "Minimum viewer
                # ratings") — the mobile's Won is its WinningTricksCount
                # (GameInfo.cs) and the rating is graded after
                self.won = min(100, final) >= self.pc_min_rating
        elif not nfh2:
            compound = self.compound_trick_score
            if not self.is_tutorial and angry_count_ticks < compound:
                compound = angry_count_ticks
            final = self.final_trick_score + self.completed * compound
        else:
            final = int(self.completed * 90.0 / max(1, self.total))
            # the tick bonus honors IgnoreScore (GameInfo.cs:414-419);
            # no shipped level sets it (tests/run_csdiff.py caught the gap)
            # the PC profile scores the collapse itself: the PC gauge may
            # fill more than once (docs/PC_VS_MOBILE.md, the gauge measured)
            one = angry_count_ticks == 1 or (pcprofile.is_pc()
                                             and angry_count_ticks >= 1)
            if one and not self.ignore_score:
                final += 10
            if pcprofile.is_pc():
                # the PC's COLLAPSE! board as GameLogic.dll sums it
                # (fcn.10040226 / fcn.10040205, docs/PC_ROUTINES.md): 1000 a
                # coin AND 1000 a life left (the status struct's +0 and
                # +0x14 together), 5000 when the gauge overflowed (the
                # accounting's flag at 100 000 rage, once), and 6 000 000
                # over the level's ticks at 12 a second for the clock —
                # 500 000 / the seconds played. Badinfos' thirteen end
                # screens (docs/PC_VS_MOBILE.md) read the same sums: his
                # three untouched lives were the "3000 for a collapse" and
                # the overflow the "5000 trophy" of the earlier reading
                coins = self.completed * 1000
                lives = self.lives * 1000
                collapse = 5000 if angry_count_ticks >= 1 else 0
                ticks = max(1, int(round(float(elapsed or 0.0) * pcprofile.S2_TICK_HZ)))
                clock = 6000000 // ticks
                self.pc_points = coins + lives + collapse + clock
                self.pc_lines = [(coins, 'coins'), (lives, 'lives'),
                                 (collapse, 'collapse'), (clock, 'time')]
        self.final_viewer_rating = min(final, 100)
        self.trick_ratio = '%d / %d' % (self.completed, self.total)
        self.viewer_rating = '%d%%' % self.final_viewer_rating
        if not self.won:
            self.rating = 'TIME UP' if self.time_up else 'FAILED'
        elif self.final_viewer_rating >= 100:
            self.rating = 'EXCELLENT'
        elif self.final_viewer_rating >= 60:
            self.rating = 'GOOD'
        else:
            self.rating = 'PASSED'
        if nfh2 and pcprofile.is_pc():
            # the PC board's caption (pcprofile.s2_result, GUIEngine
            # 0x10001536): FAILURE, COLLAPSE! on an overflow, GOOD JOB! with
            # every coin, else SUCCESS! — the mobile's bands are its own
            self.rating = pcprofile.s2_result(self.won, angry_count_ticks >= 1,
                                              self.completed, self.total)
        if not nfh2 and pcprofile.is_pc():
            # the PC's own captions (pcprofile.s1_result): BRILLIANT! from a
            # viewer rating of 90, SUCCESS! below it, TIME'S UP! and FAILED!
            # — the mobile's EXCELLENT/GOOD/PASSED bands are its own
            self.rating = pcprofile.s1_result(self.won, self.time_up,
                                              self.final_viewer_rating)

    def trick_done(self, score):
        """GameInfo.TrickDone (GameInfo.cs:467): Woody.PlayTrickDone leads"""
        if self.on_trick_done is not None:
            self.on_trick_done()
        if self.linked_trick:
            self.linked_trick = False
            self.completed += 1
        self.completed += 1
        self.log.append(score)
        self.final_trick_score += score  # FinalTrickScore += trickScore
        if self.completed >= self.winning:
            self.won = True

    def force_win(self):
        """GameInfo.ForceWinGame (GameInfo.cs:315-321): all tricks counted,
        FinalTrickScore = 100 (a 100 rating), Won, and WinImmediate skips
        the 2.5 s coroutine (Update, cs:228-235). Its only caller is the
        tutorial LevelScript (LevelScript.cs:191); the recorder's `forcewin`
        drives it."""
        self.completed = self.total
        self.final_trick_score = 100
        self.won = True
        self.win_immediate = True

    def all_done(self):
        """the immediate-win check in GameInfo.Update"""
        return self.total > 0 and self.completed >= self.total


class Routine:
    """ActionManager: a cyclic action list. Zero-duration actions end when the
    use sequence drains; advancement happens on the next Update tick."""

    IDLE, MOVING, USING = 'idle', 'moving', 'using'

    def __init__(self, level, pawn, spec, role='Rottweiler'):
        self.level = level
        self.pawn = pawn
        self.role = role
        self.actions = spec['actions']
        self.actions_to_add = spec.get('actions_to_add') or []
        self.index = spec['start_index']
        self.start_index = spec['start_index']
        self.selected_index = spec['selected_index']
        self.loop_from_start = spec['loop_from_start']
        self.loop_from_selected = spec.get('loop_from_selected', False)
        self.frozen = spec['frozen']
        self.freeze_neighbour = False    # ActionManager.FreezeNeighbour
        self.stop_dog_action = False     # ActionManager.StopDogAction
        self.state = self.IDLE
        self.timer = 0.0
        self.pc_hold = 0.0               # the PC profile's stand at a walk-by station (_pc_use_seconds)
        self.pc_mutex_left = None        # the PC profile's timed mutex (a PC stay on a MutexAction)
        self.pc_hold_cb = None           # what a pc_hold ends in, when not the use's own end
        self.pc_return = None            # the tricked station whose shout waits for the return (PCTrickReturn)
        self._pc_wait = None             # the PC profile's held clip of this use (_pc_clip_use)
        self._pc_credit = None           # the PC profile's early credit of this tricked use (PCCreditAfter)
        self.pc_run_next = False         # the next urgent runs: a lost PC game's `run` (_dex_surprise)
        self.pc_fire_at = 0.0            # the PC fire due so many seconds into a tricked use (PCFireAt)
        self.pc_credit_timer = 0.0       # Season 2: the record's credit due so many seconds into it (PCCreditAt)
        self.pc_credit_item = None
        self.pc_credit2_timer = 0.0      # the linked trick's own record, due later in the linked step (PCLinkedPaysAt)
        self.pc_credit2_item = None
        self.pc_credit3_timer = 0.0      # the linked shot's third record (206's ExtraCoin206, PCExtraPaysAtLinked)
        self.pc_credit3_item = None
        self.pc_fire_item = None
        self.delay_start = 1.5           # Rottweiler/Mother/Olga DelayStart
        self.started = False             # ActionManager.CurrentAction != null
        self.on_use = None
        self.log = []
        self._pending = None
        self.urgent_item = None          # ActionManager.UrgentAction's item
        # the running urgent template — kind + the flags Rottweiler.
        # IsAlarmPostponed reads off it (None while a routine action runs)
        self._urgent_action = None
        self.was_alerted = None          # Rottweiler.WasAlerted + RottAlerter
        # the two parked runs are separate slots: the alerter/notice run
        # (Rottweiler.ShouldStartSurpriseActionFar + SurpriseActionFar.Item,
        # cs:88, 271, 305) and the phone alarm (PendingAlarm/PendingAlarmItem,
        # cs:96-98, 1043-1044), released by CheckSurpriseActionFar (cs:1139)
        # and CheckPendingAlarm (cs:231) respectively
        self.pending_surprise = None
        self.pending_alarm = None
        # AlarmAction.Urgent: serialized false, and the CabinPhone hack sets
        # it for good (Rottweiler.MoveToAlarm, cs:872-875)
        self._alarm_urgent = bool(self.pawn.alarm_action.get('urgent'))
        self._urgent_handler = None      # a chain step's own arrival handler
        self._fix_tool = None            # the FixingItem being fetched
        self._fix_target = None          # the tricked item it fixes
        self._urgent_stack = []          # interrupted urgents to replay, LIFO
        self.marbles_next = False        # ActionManager.MarblesNextAction
        self.remove_watering_can = False  # the L108 watering-can dance
        self.remove_now = False
        self.routine_behavior = None     # Pawn.RoutineBehavior instance
        self.alarm_next_action = False   # ActionManager.AlarmNextAction
        self.action_changed = False      # ActionManager.ActionChanged
        self.cont_aux = -1               # ActionManager.ContAux (KidActions)
        self._same_zone = False          # ActionManager.SameZone (Dog/Chili)
        self._sz_watch = False           # an urgent MoveAction toward a Dog/Chili
        self._sz_flag = False            # RoutineActionMove.Flag
        self._sz_pos = None              # RoutineActionMove.RottPos
        self._sz_door = None             # RoutineActionMove.RottweilerLastDoor
        self._manager_dead = False       # ActionManager.Update dying at cs:444
        self._same_zone_yelled = False   # ActionManager.AngryAnimationStarted
        self._alarm_use = False          # the AlarmAction urgent runs a full Use
        self._angry_target = None        # the item the current angry set is for
        self._wait_in_fear_done = None   # the parked resume of the affect flow
        self._hit_target = None          # RoutineActionHitPawn.Target
        # StartUrgentAction's OriginalAction (ActionManager.cs:715-718): the
        # routine action an urgent interrupted, restarted by StopUrgentAction
        # (cs:647) even when the list or the index moved underneath
        self._original_action = None
        self._override = None            # that restart, while it runs
        # ActionManager.ActiveAction: the action StartAction started, until
        # AdvanceActionIndex — the list entry at the index can move under it
        # (Item.FishPlantBehavior, HatchFixBehavior, StopOlgaInfiniteLoop)
        self._active = None
        self._toilet_run = False         # the ToiletAction urgent is running
        # ActionManager's per-manager animation-instance stores
        # (ActionManager.cs:63-81)
        self.anim_aux = None             # animationAux
        self.anim_wc = None              # animationWC
        self.anim_standing_left = None
        self.anim_standing_up = None
        self.anim_wc_flag = False
        self.anim_standing_left_flag = False
        self.anim_standing_up_flag = False
        self.one_time_olga = False       # ActionManager.OneTime
        self.second_one_time_olga = False  # ActionManager.SecondOneTime
        # Rottweiler.Start wires the controller delegates (Rottweiler.cs:152)
        if role == 'Rottweiler':
            self.pawn.anim.last_element_hook = self._on_last_seq_element
            self.pawn.walk_hook = self._update_walking
            self.pawn.anim.show_child_hook = self._show_child_renderers
        self.pawn.anim.seq_step_hook = self._seq_step_hack

    @property
    def action(self):
        return self._active if self._active is not None else self._entry()
    def _entry(self):
        """Actions[ActiveActionIndex] — or the OriginalAction a
        StopUrgentAction restarts in its place (ActionManager.cs:647)"""
        if self._override is not None:
            return self._override
        if not self.actions:
            return None
        return self.actions[self.index % len(self.actions)]

    @property
    def item(self):
        a = self.action
        return self.level.items.get(a['item']) if a else None

    def start(self):
        if self.actions and not self.frozen:
            self._pending = 'first'      # StartFirstAction -> StartNextAction

    def _show_child_renderers(self):
        """StopSingleAnimation's ShowChildRenderersOnEnd arm: the current
        action's item re-shows its child renderers
        (AnimationControllerBase.cs:230-233)"""
        it = self.urgent_item if self.urgent_item is not None else self.item
        if it is not None and self.pawn.world is not None:
            self.pawn.world.set_child_renderers_hidden(it, False)

    def _on_last_seq_element(self):
        """Rottweiler.OnLastSequenceElementPlaying (Rottweiler.cs:256-263):
        an AlertNext use makes the next action's item ring while the last
        sequence element still plays — Level105's phones."""
        a = self.action
        it = self.item
        if (self.state == self.USING and self.urgent_item is None
                and a is not None and a.get('alert_next') and it is not None
                and not it.is_tricked(self.level.items)):
            i = self._next_index(self.index)   # GetNextAction (cs:112-117)
            nxt = self.level.items.get(self.actions[i]['item']) \
                if self.actions[i]['item'] else None
            if nxt is not None and self.pawn.world is not None:
                self.pawn.world.play_alert_animation(nxt)

    def _seq_step_hack(self, player, idx):
        """PlayNextSequenceAnimation's per-element bookkeeping: the two
        name-hacks (AnimationControllerBase.cs:261-275), the
        Item.CurrentSequenceIndex stamp for the Rottweiler and Mother owners
        (cs:277-284), and the OnSequenceIndexChange run of
        Item.OnSequenceIndexChanged (Item.cs:2693-2726)."""
        it = self.item if self.urgent_item is None else self.urgent_item
        if it is not None and self.role in ('Rottweiler', 'Mother'):
            it.current_seq_index = idx + 1        # assigned post-increment
            if it.enable_anim_index_control:
                self._anim_index_control(it, idx)
        if idx == 1 and it is not None and it.name == 'ChairAssembly':
            book = next((b for b in self.level.items.values()
                         if b.name == 'ChairAssemblyBook'), None)
            if book is not None and book.got_tricked and it.sprite is not None:
                it.sprite.hidden = True   # SetObjectHidden(true)
        if self.role == 'Olga' and idx < len(player.seq) \
                and player.seq[idx] == 'TowelSleep' \
                and player.has('TowelSleep'):
            player.sprite.anims[player.by_name['TowelSleep']].infinite = True

    def _anim_index_control(self, it, idx):
        """Item.OnSequenceIndexChanged (Item.cs:2693-2726): the controls
        matching the running sequence hide/show the item — or another item —
        at their start and end element indices (compared against
        CurrentSequenceIndex - 1, which is this element's index)."""
        w = self.pawn.world
        if w is None:
            return
        for c in it.anims_to_control:
            if not isinstance(c, dict):
                continue
            if c.get('AnimationSequence') != it.current_sequence:
                continue
            if c.get('AnimationStartIndex') == idx:
                if c.get('HideObjectOnStartIndex', True):
                    w.set_object_hidden(it, True)
            elif c.get('AnimationLastIndex') == idx \
                    and c.get('ShowObjectOnLastIndex'):
                w.set_object_hidden(it, False)
            if c.get('AnimationStartIndexItem') == idx:
                tgt = self.level.items.get(
                    (c.get('HideItemOnStartIndex') or {}).get('path'))
                if tgt is not None:
                    w.set_object_hidden(tgt, True)
            elif c.get('AnimationLastIndexItem') == idx:
                # the original shows the HIDE target here (Item.cs:2722-2725),
                # a shipped quirk kept as-is
                tgt = self.level.items.get(
                    (c.get('HideItemOnStartIndex') or {}).get('path'))
                if tgt is not None and c.get('ShowItemOnLastIndex') is not None:
                    w.set_object_hidden(tgt, False)
            return

    def _next_index(self, index):
        """ActionManager.AdvanceActionIndex (ActionManager.cs:566-584): the
        wrap goes to the start index, else to the selected index only when
        LoopFromSelectedIndex is set, else to 0 — Level206's Mother
        (LoopFromSelectedIndex=false, ActionSelectedIndex=3) wraps to 0."""
        index += 1
        if index >= len(self.actions):
            if self.loop_from_start:
                index = self.start_index
            elif self.loop_from_selected:
                index = self.selected_index
            else:
                index = 0
        return index

    def _advance(self):
        self._override = None
        self._active = None
        self.index = self._next_index(self.index)

    def _trick_kid_actions(self, it):
        """TrickItem.KidActions (TrickItem.cs:632-653), run from
        TrickItem.RottweilerUse. Two different kids: the SandSculpture arm
        animates Item.Kid — a TrickItem (Item.cs:522; L205's OlgaKid) with
        its ITEM-side UseNormalSequence / UseTrickedSequence (cs:634-641);
        the SandCastle arm animates the Kid PAWN (Rottweiler.kid,
        Rottweiler.cs:122) with the pawn-side sequences (cs:642-653)."""
        w = self.pawn.world
        if w is None or it.kind not in TRICK_KINDS:
            return
        if it.name == 'SandSculpture':
            kid_it = self.level.items.get(it.kid_item) if it.kid_item else None
            p = w.players.get(id(kid_it.sprite)) \
                if kid_it is not None and kid_it.sprite is not None else None
            if p is None:
                return
            seq = kid_it.use_tricked_sequence if it.tricked \
                else kid_it.use_normal_sequence
            seq = [a for a in (seq or []) if p.has(a)]
            if seq:
                p.play_sequence(seq)
            return
        kid = w.pawns.get('Kid')
        if kid is None or it.name != 'SandCastle':
            return
        spec = self.level.pawns.get('Kid') or {}
        linked = self.level.items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        if not it.tricked:
            seq = spec.get('kid_use_normal_seq')
        elif linked is not None and linked.tricked:
            seq = spec.get('kid_use_linked_seq')
        else:
            seq = spec.get('kid_use_tricked_seq')
        seq = [a for a in (seq or []) if kid.anim.has(a)]
        if seq:
            kid.anim.play_sequence(seq)

    def _kid_actions(self):
        """ActionManager.KidActions (ActionManager.cs:394-419), fired from
        StartNextAction: the Rake starts the kid crying, Olga's mat hands him
        the remote and hides the next action's item, the bridge rail brings
        the submarine back, and the beach mat resets the kid's idle."""
        w = self.pawn.world
        it = self.item
        kid = w.pawns.get('Kid') if w is not None else None
        if it is not None and it.name == 'Rake' and kid is not None \
                and self.role == 'Rottweiler':
            kid.kid_start_crying = True
        self.cont_aux += 1
        if self.role == 'Olga' and it is not None and it.name == 'OlgaMat' \
                and self.cont_aux > 0 and kid is not None:
            kid.kid_using_remote = True
            if self.actions:
                nxt = self.level.items.get(
                    self.actions[(self.index + 1) % len(self.actions)]['item'])
                if nxt is not None:
                    if nxt.sprite is not None:
                        nxt.sprite.hidden = True   # SetObjectHidden(true)
                    nxt.clickable = False          # collider disabled
        if self.role == 'Rottweiler' and it is not None \
                and it.name == 'BridgeRail' and w is not None:
            sub = next((s for s in self.level.items.values()
                        if s.name == 'Submarine'), None)
            if sub is not None:
                if sub.sprite is not None:
                    sub.sprite.hidden = False
                sub.clickable = True
                p = w.players.get(id(sub.sprite)) if sub.sprite else None
                if p is not None and sub.primed_fucked_up \
                        and p.has(sub.primed_fucked_up):
                    p.play_single(sub.primed_fucked_up)
            if kid is not None:
                kid.kid_remote = True
        if self.role == 'Rottweiler' and self.actions and it is not None \
                and it.name == 'OlgaMatBeach' and w is not None:
            last = self.level.items.get(self.actions[-1]['item']) \
                if self.actions[-1]['item'] else None
            kid_it = self.level.items.get(last.kid_item) \
                if last is not None and last.kid_item else None
            if kid_it is not None and kid_it.sprite is not None:
                p = w.players.get(id(kid_it.sprite))
                if p is not None and kid_it.idle and p.has(kid_it.idle):
                    p.play_looping(kid_it.idle)

    def _olga_infinite_behavior(self, olga):
        """ActionManager.OlgaInfiniteBehavior (ActionManager.cs:384-392)"""
        if self.anim_aux is not None:
            self.anim_aux.infinite = True
        self.anim_aux = olga.anim.anim
        olga.anim.anim.infinite = False

    def _olga_extra_animations(self):
        """ActionManager.OlgaExtraAnimations (ActionManager.cs:268-382):
        the InfiniteLoop juggling that swaps Olga between her waiting poses
        as the routines advance — Sweets, LifeBoat, FishingRod, Tortilla,
        Pinata/BoatPicnic, MechanicalBullWait, CaptainDoor and Glass, each by
        item name, mutating the shared animation instances."""
        w = self.pawn.world
        olga = w.pawns.get('Olga') if w is not None else None
        if olga is None or not self.actions:
            return
        items = self.level.items
        cur = items.get(self.action['item']) if self.action and \
            self.action.get('item') else None
        prev = items.get(self.actions[(self.index - 1) % len(self.actions)]
                         ['item']) \
            if self.actions[(self.index - 1) % len(self.actions)]['item'] \
            else None
        name = cur.name if cur is not None else None
        if self.role == 'Rottweiler' and prev is not None and \
                (prev.rott_use_olga_seq or prev.rott_use_tricked_olga_seq):
            # cs:270-273: Olga returns to her default pose after the drag
            if olga.default_anim and olga.anim.has(olga.default_anim):
                olga.anim.play_looping(olga.default_anim)
        if self.role == 'Rottweiler' and name == 'Sweets':   # cs:274-297
            if self.anim_standing_left_flag:
                self.anim_standing_left = olga.anim.anim
            if self.anim_standing_left is not None:
                self.anim_standing_left_flag = False
                self.anim_standing_left.infinite = False
            else:
                self.anim_standing_left_flag = True
            if self.anim_standing_up is not None:
                self.anim_standing_up.infinite = True
            if self.anim_wc is not None:
                self.anim_wc.infinite = True
        elif self.role == 'Rottweiler' and name == 'LifeBoat':   # cs:298-314
            if not self.anim_standing_up_flag:
                self.anim_standing_up_flag = True
                self.anim_standing_up = olga.anim.anim
            self.anim_standing_up.infinite = False
            if self.anim_standing_left is not None:
                self.anim_standing_left.infinite = True
            if self.anim_wc is not None:
                self.anim_wc.infinite = True
        elif self.role == 'Rottweiler' and name == 'FishingRod':  # cs:315-331
            if not self.anim_wc_flag:
                self.anim_wc_flag = True
                self.anim_wc = olga.anim.anim
            self.anim_wc.infinite = False
            if self.anim_standing_left is not None:
                self.anim_standing_left.infinite = True
            if self.anim_standing_up is not None:
                self.anim_standing_up.infinite = True
        if self.role == 'Rottweiler' and name == 'Tortilla':  # cs:332-336
            self._olga_infinite_behavior(olga)
            olga.olga_aux_anim = self.anim_aux
        ort = next((r for r in w.routines if r.role == 'Olga'), None)
        olga_cur = None
        if ort is not None and ort.actions:
            olga_cur = items.get(ort.actions[ort.index % len(ort.actions)]
                                 ['item']) \
                if ort.actions[ort.index % len(ort.actions)]['item'] else None
        if self.role == 'Rottweiler' and name == 'Pinata' \
                and olga_cur is not None and olga_cur.name == 'BoatPicnic' \
                and not self.second_one_time_olga:    # cs:337-345
            olga.anim.anim.infinite = False
            olga.olga_wait_picnic_anim = olga.anim.anim
        if self.role == 'Olga' and olga_cur is not None \
                and olga_cur.name in ('BoatPicnic', 'MechanicalBullWait') \
                and not self.one_time_olga:           # cs:346-350
            self.one_time_olga = True
            olga.olga_workout2_anim = olga.anim.anim
        if self.role == 'Olga' and olga_cur is not None \
                and olga_cur.name == 'MechanicalBullWait':   # cs:351-365
            if olga.olga_wait_picnic_anim is not None:
                olga.olga_wait_picnic_anim.infinite = True
                self.second_one_time_olga = False
            if olga.olga_workout2_anim is not None:
                olga.olga_workout2_anim.infinite = True
        if self.role == 'Rottweiler' and name == 'CaptainDoor':  # cs:366-377
            if prev is not None and prev.name == 'Shower' and prev.got_tricked:
                self._olga_infinite_behavior(olga)
            if prev is not None and prev.name == 'Bouquet' \
                    and not prev.got_tricked:
                self._olga_infinite_behavior(olga)
            olga.olga_aux_anim = self.anim_aux
        elif self.role == 'Olga' and name == 'Glass' \
                and olga.olga_aux_anim is not None:   # cs:378-381
            olga.olga_aux_anim.infinite = True

    def _start_action(self, start_next=False):
        self.started = True              # StartAction: CurrentAction = ...
        self._active = None              # the entry at the index from here on
        it = self.item
        a = self.action
        if start_next:
            # the StartNextAction extras (ActionManager.cs:178-237): the
            # previous action's final position, the kid hooks, the hide
            # releases, the gramophone skip and the spent-action removal
            w = self.pawn.world
            prev = None
            if self.actions:
                prev_i = (self.index - 1) % len(self.actions)
                prev = self.level.items.get(self.actions[prev_i]['item']) \
                    if self.actions[prev_i]['item'] else None
            if w is not None and self.role == 'Rottweiler' and prev is not None:
                # CheckFinalPosition of the finished action's item
                # (ActionManager.cs:180-191): UseFinalPositionsInBeginning,
                # the WaterPuddle unconditionally, then the one-shot reset
                if prev.use_final_positions_in_beginning \
                        and not self.pawn.normal_pos_aux:
                    w.check_final_position(self.pawn, prev)
                if prev.name == 'WaterPuddle':
                    w.check_final_position(self.pawn, prev)
                if self.pawn.normal_pos_aux:
                    self.pawn.normal_pos_aux = False
            self._kid_actions()
            self._olga_extra_animations()
            if w is not None and self.actions and len(self.actions) > 1:
                # NextActionAfterGramaphoneTricked skips one action
                # (ActionManager.cs:200-204)
                p2 = self.level.items.get(
                    self.actions[(self.index - 2) % len(self.actions)]['item']) \
                    if self.actions[(self.index - 2) % len(self.actions)]['item'] \
                    else None
                if p2 is not None and p2.next_action_after_gramaphone:
                    p2.next_action_after_gramaphone = False
                    self.index = (self.index + 1) % len(self.actions)
                    # the skipped entry is the nailed record player's second
                    # use ([8] of Level114, two after its fix at [6]): the
                    # original's StartAction(Actions[ActiveActionIndex])
                    # then starts the SHOTGUN — the port used to keep the
                    # entry it had already fetched (`a`), played the broken
                    # player and lost the shotgun instead (Badinfos' E14:
                    # pipe 301-313 > shotgun 319, no second listen)
                    it = self.item
                    a = self.action
            if w is not None and prev is not None:
                # the hide releases (ActionManager.cs:205-212)
                if prev.hide_during_rott_animation:
                    w.set_object_hidden(prev, False)
                hoda = self.level.items.get(prev.hide_object_during_animation) \
                    if prev.hide_object_during_animation else None
                if hoda is not None:
                    w.set_object_hidden(hoda, False)
            if self.actions:
                # RemoveActionAfterUse drops the spent action
                # (ActionManager.cs:218-227)
                last_i = (self.index - 1) % len(self.actions)
                if self.actions[last_i].get('remove_action_after_use'):
                    del self.actions[last_i]
                    if last_i >= len(self.actions):
                        last_i = 0
                    self.index = last_i
                # IgnoreWoodyWhenUse releases at the next start
                # (ActionManager.cs:228-231)
                last = self.level.items.get(
                    self.actions[(self.index - 1) % len(self.actions)]['item']) \
                    if self.actions[(self.index - 1) % len(self.actions)]['item'] \
                    else None
                if last is not None and last.ignore_woody_when_use \
                        and self.role == 'Rottweiler':
                    self.pawn.ignore_woody = False
            self.action_changed = True    # ActionManager.cs:234
        # the watering-can round two (ActionManager.cs:196-199): reaching
        # index 2 with the parked can removes it for real
        if self.remove_watering_can and self.actions and \
                self.index % len(self.actions) == 2 and len(self.actions) > 1:
            self.remove_now = True
            self.remove_actions_by_item(self.actions[1]['item'])
            it = self.item
            a = self.action
        # the Iron routine jumps (ActionManager.cs:213-217, Rottweiler.cs:461):
        # a fixed primed iron rewinds the loop to the start index late in the
        # list, and jumps onward from the last action
        if it is not None and it.name == 'Iron' and self.actions:
            cur = self.index % len(self.actions)
            if it.change_iron_routine and cur > 8:
                it.change_iron_routine = False
                self.index = self.start_index
                it = self.item
                a = self.action
            elif it.change_iron_routine_last_path and \
                    cur == len(self.actions) - 1:
                it.change_iron_routine_last_path = False
                self._advance()
                it = self.item
                a = self.action
        if it is not None and not it.active and not it.started:
            if os.environ.get('NFH_ROUTINE_LOG'):
                print('routine %s t=%.1f inactive item skipped: %s index=%s' % (
                    self.role, getattr(self.pawn.world, 'time', 0.0), it.name, self.index), file=sys.stderr)
            # StartAction on an item whose object has never been active:
            # MoveToAction's Item.LoadRottweilerAnimations (ActionManager.
            # cs:119-127, Item.cs:785-811) dereferences the item's
            # Rottweiler, unset because Item.Start never ran (Item.cs:677-
            # 690 sets the pawn fields on the first active frame) — a
            # NullReferenceException that leaves the action unstarted
            # (ActiveAction stays the finished one) and the next Update's
            # AdvanceToNextAction moves the index on. Bench, Level214's
            # wheel race (the mug used late, the wheel still 11 s from its
            # DelayActivateItem): his index 1 at level frame 25717, 2 at
            # 25718, and off to the pistol. Under a hook on that chain the
            # exception cannot unwind and the game dies. An item that
            # started and was deactivated since is walked to and used as
            # any other — its fields are set, its animations loaded once
            # (RottweilerAnimationsLoaded): Level101's binoculars, glued to
            # his face by the trick (Level101Behavior.cs:29-33 SetActive
            # (false) on PeepTrick, the use rewritten to RottLookNoBin),
            # still take him to the window every round; skipped, he sat
            # on the sofa for good (the sofa is the routine's other action).
            self._pending = 'advance'
            self.state = self.IDLE
            return
        self._active = a                 # ActiveAction = action (cs:169)
        if a is not None and a.get('move_only'):
            if self.routine_behavior is not None:
                # ActionManager.MoveToAction (ActionManager.cs:119-124)
                self.routine_behavior.on_move_to_routine_action(None, a)
            # a MoveOnly step is a plain MoveToGoal (RoutineActionMove.cs:
            # 76-79), and MoveToGoal drops InUrgentMove (Pawn.cs:428-432):
            # the walk after an Urgent action is a walk
            self.pawn.in_urgent = False
            zone = self.level.zone_by_pid(a.get('move_zone'))
            if zone is not None and self.pawn.goto_zone(zone, a['move_x'],
                                                        on_arrive=self._finish):
                self.state = self.MOVING
                return
            self._pending = 'advance'
            self.state = self.IDLE
            return
        if it is None:
            self._pending = 'advance'
            self.state = self.IDLE
            return
        if self.pawn.at_use_range(it):
            self._use()
        else:
            if self.routine_behavior is not None:
                # ActionManager.MoveToAction (ActionManager.cs:119-124)
                self.routine_behavior.on_move_to_routine_action(it, a)
            self.state = self.MOVING
            # an Urgent action is approached at a run (MoveToGoalUrgent,
            # RoutineActionMove.cs:68-75); on PC the Season 2 ones are runs of
            # the level script too (206's pillows: the gait set to 2 before
            # each walk, GameLogic 0x1002ea9b-0x1002f0c4; the Mother's `call`
            # on 210, 0x10019270, and on 208, 0x1001d889) — Season 1 has no
            # Urgent routine action
            self.pawn.in_urgent = bool(a.get('urgent'))
            self.pawn.pc_run = bool(a.get('urgent')) and pcprofile.is_pc() \
                and pcprofile.SEASON2
            if self.pc_return is not None and it is self.pc_return:
                # back to the tricked station at a run (PCTrickReturn: 205's
                # nailed skis, the gait write 0x10024fde before the GoTo)
                self.pawn.in_urgent = True
                self.pawn.pc_run = True
            if not self.pawn.goto_item(it, on_arrive=self._use):
                self._pending = 'advance'
                self.state = self.IDLE

    def _use(self):
        it = self.item
        a = self.action
        if os.environ.get('NFH_ROUTINE_LOG'):
            print('routine %s t=%.1f use start item=%s tricked=%s state=%s override=%s anim=%s' % (
                self.role, getattr(self.pawn.world, 'time', 0.0), getattr(it, 'name', None),
                it.is_tricked(self.level.items) if it is not None else None, self.state,
                (self.level.items.get(self._override['item']).name if self._override and self._override.get('item') is not None and self.level.items.get(self._override['item']) else None),
                self.pawn.anim.anim.name), file=sys.stderr)
        if it is None:
            self._pending = 'advance'; self.state = self.IDLE; return
        if self.routine_behavior is not None:
            # ActionManager.StartAction fires the hook right before the
            # action itself starts (ActionManager.cs:165-168)
            self.routine_behavior.on_start_routine_action(it, a)
        # RoutineActionUse.OnActionStarted fires on arrival (ActionManager.
        # StartAction interposes a MoveAction when the pawn is away); the
        # ignore-loop release opens it (RoutineActionUse.cs:152-171)
        self._infinite_flags_on_start(a, it)
        if pcprofile.is_pc():
            # a clip held elsewhere until this role's use of this item begins
            # (PCWaitFor `at` start: the behavior= message an action fires as
            # it starts, a poll on the actor's arrival)
            it.pc_began.add(self.role)
        if a.get('mutex'):
            # MutexAction parks on its looping animation until another action's
            # PawnToAbortMutexOnFinish releases it (RoutineActionUse.cs:172-179)
            self.state = self.USING
            self.timer = 0.0
            secs = self._pc_use_seconds(it) if pcprofile.is_pc() else 0.0
            if secs > 0.0:
                # the PC's step has no mutex: it lasts its own actions and
                # goes on (205's mat: the `talk` and the 72-tick wait,
                # 0x100258fd), whoever else is done (PCUseSeconds)
                self.pc_mutex_left = secs
            if a.get('hide_owner'):
                # HideOwnerDuringUse -> Owner.SetHidden(true), cs:174-177
                self.pawn.set_hidden(True)
            if a.get('mutex_anim'):
                self.pawn.anim.play_looping(a['mutex_anim'])
            return
        # the walking-prop toggles (RoutineActionUse.cs:181-200): cake, Fifi
        # and skates ride the action flags and swap the walking sets
        if a.get('cake'):
            self.pawn.holding_cake = not self.pawn.holding_cake
        if a.get('give_fifi'):
            self.pawn.has_fifi = True
        if a.get('give_skates'):
            self.pawn.has_skates = True
        if a.get('remove_fifi'):
            self.pawn.has_fifi = False
        if a.get('remove_skates'):
            self.pawn.has_skates = False
        w = self.pawn.world
        if self.pc_return is not None and it is self.pc_return and w is not None:
            self._pc_return_use(it)
            return
        # Item.Use turns the item's sleep bar on: the Rottweiler-actor bar at
        # its head (Item.cs:831-834), the Mother-actor bar at its tail
        # (cs:861-864) and in MotherUse (cs:1110-1113); RottweilerPrime does
        # its own (cs:1322-1325), covered by activating before the prime leg
        if w is not None:
            if self.role == 'Mother':
                w.activate_progress_bar(it, 'Mother')
            else:
                w.activate_progress_bar(it, 'Rottweiler')
                w.activate_progress_bar(it, 'Mother')
        # Item.Use's Rottweiler branch (Item.cs:1056-1095): a toggles-prime
        # item alternates prime / use; RequireUnprime makes it three-phase
        # (prime, use, unprime). The PigKeys and Pipe name-hacks are skipped.
        if self.role == 'Rottweiler' and it.rott_toggles_prime and w is not None:
            # the PigKeys dispatch precedes the toggle (Item.cs:1057-1063):
            # taken keys reappear on the unprimed pass, primed keys are taken
            if it.name == 'PigKeys' and not it.tricked:
                if it.item_removed and not it.primed:
                    it.item_removed = False
                elif not it.item_removed and it.primed:
                    it.item_removed = True
            leg = None
            unprime = False
            if it.require_unprime:
                if not it.primed:
                    w.set_primed(it, True)
                    leg = it.rott_prime_anim
                elif not it.is_using:
                    it.is_using = True    # falls through to the plain use
                else:
                    w.set_primed(it, False)
                    it.is_using = False
                    leg = it.rott_unprime_anim
                    unprime = True
            else:
                was = it.primed
                w.set_primed(it, not it.primed)
                if not was:
                    leg = it.rott_prime_anim
                    # a closed main valve early in the loop plays the unprime
                    # set instead (Item.cs:1335-1338)
                    if it.name == 'ValveMain' and not it.main_valve_open \
                            and self.start_index <= 3:
                        leg = it.rott_unprime_anim
                    # RottweilerPrime's tail closes an open valve
                    # (Item.cs:1352-1355)
                    if it.name == 'ValveMain' and it.main_valve_open:
                        it.main_valve_open = False
                    # the first Fifi prime swaps the put animation in
                    # (Item.cs RottweilerPrime's DogFifi arm)
                    if it.name == 'DogFifi' and not it.prime_item_aux:
                        it.prime_item_aux = True
                        it.rott_prime_anim = ['FifiPutLeft']
                elif it.name == 'Pipe':
                    # an unprimed Pipe stops taking clicks (Item.cs:1085)
                    it.clickable = False
            if leg is not None and it.name == 'Pipe' and it.primed:
                it.clickable = True       # RottweilerPrime re-enables it
                                          # (Item.cs:1331-1334)
            if leg is it.rott_prime_anim and it.enable_collider_after_prime:
                it.clickable = True       # RottweilerPrime (Item.cs:1326-1329)
            if leg is not None:
                # RottweilerPrime / RottweilerUnprime raise WasPriming
                # (Item.cs:1330, 1361): IsTricked() reads false for the leg
                # (TrickItem.cs:260) — no angry, no exit delta swap, and
                # OnUseEnded keeps the primed pose (cs:691) — until the next
                # RottweilerUse clears it (Item.cs:835)
                it.was_priming = True
                if unprime and it.kind in TRICK_KINDS:
                    # TrickItem.RottweilerUnprime returns the item to idle at
                    # the leg's start (TrickItem.cs:1052-1057)
                    w._return_to_idle(it)
                seq = [x for x in leg if self.pawn.anim.has(x)]
                self.state = self.USING
                self.timer = a['duration']
                # the prime and unprime legs are visits of the PC station too
                # (111's board: the give at his first ironing; the rack's
                # putclothes; 113's fuse take): they take this visit's
                # PCUseSeconds and play at its pace, keeping the per-visit
                # values in the PC's order (tools/pcref/pc_durations.py)
                if self.role == 'Rottweiler' and seq and pcprofile.is_pc() \
                        and pcprofile.rule('durations'):
                    pc = self._pc_visit_seconds(it)
                    if pc:
                        mobile = self.pawn.anim.sequence_seconds(seq)
                        if mobile > 0.0:
                            self.pawn.anim.time_scale = mobile / pc
                if a.get('hide_owner'):
                    self.pawn.set_hidden(True)   # cs:213-216
                self._after_use_side_effects(a, it)
                # RottweilerPrime / RottweilerUnprime return true (Item.cs:
                # 1356, 1359-1370), so RoutineActionUse.OnActionStarted's
                # teleport (cs:205-208) applies to the prime legs too —
                # L201's puddle stands the neighbour at 3.46 on every visit
                if it.teleport_rott_on_use:
                    self.pawn.sprite.x = it.x + it.rott_teleport_offset[0]
                    self.pawn.sprite.y = it.y + it.rott_teleport_offset[1]
                    self.pawn.pos_snap = True
                    self.pawn._item_snap = None
                if seq:
                    self.pawn.anim.play_sequence(seq, on_end=self._finish)
                else:
                    # no prime animation: StopCurrentAction(canPostponeStop:
                    # false) — no angry postpone (Item.cs RottweilerPrime tail)
                    self._action_stopped()
                    self._pending = 'advance'
                    self.state = self.IDLE
                    self._check_parked_runs()
                return
        # Item.RottweilerUse opens by clearing WasPriming (Item.cs:835) — the
        # plain use and the RequireUnprime use leg both come through here
        if self.role == 'Rottweiler':
            it.was_priming = False
        # Item.RottweilerUse's FixingItem dispatch (Item.cs:836-858): a raw-
        # Tricked item that names a fixing tool sends him fetching (neutral or
        # ForceUseFixingItem), and with the right tool in hand the item is
        # fixed and the tool used instead
        if self.role == 'Rottweiler' and w is not None and it.tricked \
                and not it.pc_masked and it.fixing_item is not None:
            if self._fixing_dispatch(it):
                return
            tool = self.level.items.get(it.fixing_item)
            if tool is not None and self.pawn.fixing_item is tool:
                w._fix(it)                     # Item.cs:854-857: Fix(); tool use
                tool.was_priming = False       # the tool's RottweilerUse head (cs:835)
                seq = tool.sequence_for(self.role,
                                        tool.is_tricked(self.level.items),
                                        self.level.items)
                self.state = self.USING
                self.timer = a['duration']
                if seq:
                    self.pawn.anim.play_sequence(list(seq), on_end=self._finish)
                else:
                    self._action_stopped()
                    self._pending = 'advance'
                    self.state = self.IDLE
                    self._check_parked_runs()
                return
        # TrickItem.MotherUse: a tricked ChangeActionsWhenTricked208 item
        # injects both managers' ActionsToAddInGame (TrickItem.cs:1253-1262)
        if self.role == 'Mother' and it.change_actions_208 and it.tricked \
                and self.pawn.world is not None:
            for r in self.pawn.world.routines:
                if r.role in ('Mother', 'Rottweiler'):
                    r.add_in_game_actions()
        tricked = it.is_tricked(self.level.items)
        # Item.RottweilerUse opens with the raw-Tricked GotTricked mark
        # (Item.cs:836-838) — before any animation concern; the sink/valve
        # chains hang off it — and IgnoreWoodyWhenUse (cs:827-830)
        if self.role == 'Rottweiler':
            if it.ignore_woody_when_use:
                self.pawn.ignore_woody = True
            # TrickItem.RottweilerUse re-opens a closed main valve
            # (TrickItem.cs:570-573)
            if it.name == 'ValveMain' and not it.main_valve_open:
                it.main_valve_open = True
            # TrickItem.KidActions (TrickItem.cs:632-653): the sand
            # sculpture/castle uses play the kid's reaction sets
            self._trick_kid_actions(it)
            if it.tricked and not it.pc_masked:
                it.got_tricked = True
                # UpdatePawnToAffectAnimation (Item.cs:868-882): the affected
                # Olga plays her tricked use alongside; the Mother arms hers
                if it.pawn_to_affect is not None and w is not None:
                    affected = w.pawn_by_pid(it.pawn_to_affect)
                    if affected is not None and affected.role == 'Olga':
                        it.use_olga_tricked_flag = True
                        if it.name != 'SandCastle':
                            oseq = [x for x in it.use_tricked_anim.get('Olga')
                                    or [] if affected.anim.has(x)]
                            if oseq:
                                affected.anim.play_sequence(oseq)
                            w.play_tricked_item_anim(it)
                    elif affected is not None and affected.role == 'Mother':
                        it.use_mother_tricked_flag = True
        # ChangeHitPawnAnimation207 (TrickItem.cs:1264-1280): the sand castle
        # and shell swap the hit-pawn opener and the wait-in-fear pose
        if self.role == 'Rottweiler' and w is not None:
            self._change_hit_pawn_animation_207(it)
        # the Mother's affected variant (TrickItem.PlayAnimation cs:795-798):
        # her angry-at-the-neighbour set plays first, and the ordinary
        # dispatch below immediately replaces it — kept transient like the
        # original's consecutive PlayAnimationSequence calls
        if self.role == 'Mother' and it.pawn_to_affect is not None \
                and it.use_mother_tricked_flag and it.mother_rott_angry:
            mseq = [x for x in it.mother_rott_angry if self.pawn.anim.has(x)]
            if mseq:
                self.pawn.anim.play_sequence(mseq)
        # the Rake subclass skips its animations outside the compound trick
        # (Rake.cs:3-11): the use goes straight to the stop flow
        if it.kind == 'Rake' and self.role == 'Rottweiler' \
                and not (it.tricked and it.compound_tricked):
            self.state = self.USING
            self.timer = a['duration']
            self._after_use_side_effects(a, it)
            self.log.append((it.name, tricked))
            if self.on_use:
                self.on_use(it, tricked)
            self._finish()
            return
        # the Drawing subclass cycles its smears (Drawing.cs:44-68)
        if it.kind == 'Drawing' and self.role == 'Rottweiler' and w is not None:
            w.set_active(it, True)
            if it.drawing_done_cleaning:
                it.drawing_done_cleaning = False
                ru = it.use_anim.get('Rottweiler') or []
                if len(ru) > 1:                    # ResetUseAnimation
                    it.use_anim['Rottweiler'] = [ru[1]]
            if it.sprite is not None:
                it.sprite.hidden = False
            w.play_item_anim(it, 'Drawing%d' % it.drawing_current)
            it.drawing_current += 1
            if it.drawing_current >= 4:            # >= Drawing4
                it.drawing_current = 1
                ru = it.use_anim.get('Rottweiler') or []
                it.use_anim['Rottweiler'] = \
                    ['GoldCupClean'] + (ru[:1] if ru else [])
                it.drawing_done_cleaning = True
        seq, item_play = self._pick_use_sequence(it, tricked, w)
        # TrickItem.RottweilerUse's own side arms (TrickItem.cs:566-630)
        if self.role == 'Rottweiler' and w is not None:
            hoda = self.level.items.get(it.hide_object_during_animation) \
                if it.hide_object_during_animation else None
            if hoda is not None:              # cs:574-578
                w.set_object_hidden(hoda, True)
                w.set_tricked_object_hidden(hoda, True)
            dep = self.level.items.get(it.depends_on) \
                if it.depends_on is not None else None
            raw = it.tricked and not it.pc_masked   # (a visit the PC plays untricked)
            if it.hide_during_rott_animation:  # cs:579-593
                if raw or (dep is not None and dep.tricked):
                    if it.tricked_object_go is not None:
                        w.set_tricked_object_hidden(it, True)
                    else:
                        w.set_object_hidden(it, True)
                elif not raw and it.name != 'ChairAssembly':
                    w.set_object_hidden(it, True)
            if it.disable_collider_after_use:  # cs:594-598
                it.clickable = False
                it.can_use = False
            if it.use_at_other_place:          # cs:599-607
                if it.should_return:
                    it.at_home = not it.at_home
                    w.set_active_object_hidden(it, not it.at_home)
                    it.clickable = it.at_home
            elif raw:                          # cs:608-611
                w.check_destroy_when_tricked(it)
            if it.is_tricked(self.level.items):
                if it.force_fuckedup_when_tricked:   # cs:612-619
                    it.idle = it.idle_fucked_up
                    it.use_normal = it.use_fucked_up
                    it.primed_normal = it.primed_fucked_up
                if it.give_bowling_when_tricked:     # cs:620-624
                    self.pawn.has_bowling = True
            if it.remove_bowling:              # cs:625-628
                self.pawn.has_bowling = False
        self.state = self.USING
        self.timer = a['duration']
        if a.get('hide_owner'):
            self.pawn.set_hidden(True)    # HideOwnerDuringUse, cs:213-216
        self._after_use_side_effects(a, it)
        # RoutineActionUse.OnActionStarted's teleport (cs:205-208) and
        # Olga.TryUseItem's x-snap (Olga.cs:146-152)
        if it.teleport_rott_on_use and self.role == 'Rottweiler':
            self.pawn.sprite.x = it.x + it.rott_teleport_offset[0]
            self.pawn.sprite.y = it.y + it.rott_teleport_offset[1]
            self.pawn.pos_snap = True
            # the walk's deferred MoveToItem snap (_walk_on_path's head) would
            # read the teleported x as "passed the target" and put him back
            # on the walk target two frames later; the original holds the
            # teleported stand for the whole use (L201's WaterPuddle: 3.46
            # through both uses, not 3.12 / 4.32)
            self.pawn._item_snap = None
        if it.set_olga_x_on_use and self.role == 'Olga':
            self.pawn.sprite.x = it.x
            self.pawn.pos_snap = True
        self.log.append((it.name, tricked))
        if self.on_use:
            self.on_use(it, tricked)
        # the item plays its own use pose alongside the pawn's sequence
        # (TrickItem.PlayUseAnimation / PlayTrickedAnimation, cs:947-994)
        if w is not None and item_play is not None:
            item_play()
        # the neighbour's use drags Olga through her set (TrickItem.cs:911-914)
        if self.role == 'Rottweiler' and w is not None \
                and (it.rott_use_olga_seq or it.rott_use_tricked_olga_seq):
            olga = w.pawns.get('Olga')
            if olga is not None:
                oseq = it.rott_use_tricked_olga_seq if it.tricked \
                    else it.rott_use_olga_seq
                oseq = [x for x in oseq if olga.anim.has(x)]
                if oseq:
                    olga.anim.play_sequence(oseq)
        pc = self._pc_use_seconds(it)
        ft = self._pc_trick_item(it)
        if pcprofile.is_pc() and self.role == 'Rottweiler' and it is not None \
                and getattr(ft, 'pc_fire_at', None) is not None \
                and it.is_tricked(self.level.items) and not ft.pc_fired:
            # the PC step fires this far into the tricked stand when its own
            # clip or more actions follow the fire (PCFireAt: the tub's hair
            # after the shower clip, the dirty microwave on arrival at 0 and
            # the cooking after it — docs/PC_ROUTINES.md "The fire's tail");
            # the playing trick fires, the one the angry pays (_pc_trick_item)
            if float(ft.pc_fire_at) > 0.0:
                self.pc_fire_at = float(ft.pc_fire_at)
                self.pc_fire_item = ft
            elif w is not None:
                w.s1_fire(self.pawn, ft)
        if pcprofile.is_pc() and pcprofile.SEASON2 and self.role == 'Rottweiler' \
                and it is not None and it.is_tricked(self.level.items):
            # Season 2: the trick's record pays on the tick its `time`
            # equals the action's elapsed count (fcn.1000140b, the cmp at
            # 0x10001455), this far into the tricked stand (PCCreditAt; the
            # linked trick's own, PCCreditAtLinked) — the paced use makes the
            # PC seconds wall seconds
            target = self._tricked_item(it)
            linked = self.level.items.get(it.linked_item_trick) if it.linked_item_trick else None
            both = linked is not None and linked.tricked and it.tricked \
                and bool(it.use_tricked_linked)
            # (a station tricked through its DependsOn pays its dependency's
            # record: 206's pad shooting the rubber bear, the harpoon's)
            at = it.pc_credit_at_linked if (it.pc_credit_at_linked is not None and both) \
                else getattr(self._pc_trick_item(it), 'pc_credit_at', None)
            if at is not None and target is not None and not target.pc_credited:
                self.pc_credit_timer = float(at)
                self.pc_credit_item = target
            if both and it.pc_linked_pays_at is not None and target is not None:
                # the linked trick's own record, its own tick of the linked
                # step (fcn.1000140b credits each named record at its `time`:
                # 202's bridge_electrify 22 ticks after bridge_crash)
                target.pc_linked_due = True
                self.pc_credit2_timer = float(it.pc_linked_pays_at)
                self.pc_credit2_item = target
            if both and it.pc_extra_pays_at_linked is not None and it.extra_coin_206 \
                    and target is not None:
                # the linked shot's third record at its own tick (206's
                # rubberrabbit, the ExtraCoin206)
                self.pc_credit3_timer = float(it.pc_extra_pays_at_linked)
                self.pc_credit3_item = target
        if os.environ.get('NFH_ROUTINE_LOG'):
            print('routine %s t=%.1f use sequence item=%s seq=%s pc=%s mobile=%.2f' % (
                self.role, getattr(self.pawn.world, 'time', 0.0), it.name, list(seq or []), pc,
                self.pawn.anim.sequence_seconds(seq) if seq else 0.0), file=sys.stderr)
        if seq:
            if pc:
                # the PC station lasts its DoActions' ticks (levels/pc overlays,
                # PCUseSeconds): the mobile clips play at the pace that lasts them
                mobile = self.pawn.anim.sequence_seconds(seq)
                if mobile > 0.0:
                    self.pawn.anim.time_scale = mobile / pc
            elif pcprofile.is_pc():
                self._pc_clip_use(it)
            if pcprofile.is_pc() and it.pc_credit_after \
                    and it.pc_credit_after in seq and it.is_tricked(self.level.items):
                # the trick's record pays as its PC action ends (PCCreditAfter)
                self._pc_credit = {'clip': it.pc_credit_after, 'seen': False}
            self.pawn.anim.play_sequence(list(seq), on_end=self._finish)
        elif pc:
            # a station the remaster only walks by is an action on the PC (the
            # shout at the window, the yoga): the stand holds for its ticks,
            # then the empty sequence's own end (_finish, with StopAction's
            # side effects) runs from the tick — an urgent or a surprise
            # meanwhile drops the hold
            self.pc_hold = pc
        else:
            # an empty sequence completes at once, and the angry postpone
            # still rides StopAction (OnUseAnimationsCompleted ->
            # StopAction(canPostponeStop: true)) — the invisible valves
            # of Level113 depend on this
            self._finish()

    def _pick_use_sequence(self, it, tricked, w):
        """the use-animation dispatch, branch for branch: the Rottweiler
        runs TrickItem.PlayAnimation (TrickItem.cs:791-916) over the base
        Item.PlayAnimation (Item.cs:894-905); the Mother runs
        PlayMotherAnimation with the DeckChair alternation (Item.cs:1117-1137);
        Olga runs PlayOlgaAnimation with its name-hacks (Item.cs:1144-1167)
        and the TrickItem override's item-side plays (cs:964-975). Returns
        the pawn's sequence and a callable that plays the item's own pose."""
        items = self.level.items
        linked = items.get(it.linked_item_trick) if it.linked_item_trick else None
        dep = items.get(it.depends_on) if it.depends_on is not None else None
        item_play = None
        if self.role == 'Mother':
            # PlayMotherAnimation (Item.cs:1117-1137); the Get* methods stamp
            # CurrentAnimationSequence (Item.cs:907-940)
            if not it.tricked:
                if it.is_mother_second_use and it.execute_once_mother \
                        and it.name == 'DeckChair':
                    it.current_sequence = 'MotherSecondUse'
                    return list(it.mother_second_use), None
                it.execute_once_mother = True
                it.current_sequence = 'MotherUse'
                return list(it.use_anim.get('Mother') or []), None
            it.execute_once_mother = False
            it.current_sequence = 'MotherUseTricked'
            return list(it.use_tricked_anim.get('Mother') or []), None
        if self.role == 'Olga':
            # PlayOlgaAnimation (Item.cs:1144-1167): the tricked name-hacks
            # and flags all resolve to the tricked set; the TrickItem
            # override adds the item-side pose (TrickItem.cs:964-975)
            olga_tricked = it.is_tricked(items) and (
                it.name in ('OlgaStandStill', 'MechanicalBull', 'PullKart')
                or it.use_olga_tricked_flag or it.use_olga_tricked_anim_flag)
            if it.kind in TRICK_KINDS:
                if it.tricked:
                    item_play = lambda: w.play_tricked_item_anim(it, self.pawn)
                else:
                    # the non-tricked use wires Olga.OnItemAnimationSequence-
                    # Ended into the item's UseNormalSequence (TrickItem.cs:
                    # 972): its end stops her current action — the release
                    # of a use whose owner is hidden (Level205/210's mat)
                    item_play = lambda: w.play_use_item_anim(
                        it, on_end=self._olga_item_seq_ended)
            if olga_tricked:
                return list(it.use_tricked_anim.get('Olga') or []), item_play
            return list(it.use_anim.get('Olga') or []), item_play
        # ---- the Rottweiler dispatch ----------------------------------
        if it.kind not in TRICK_KINDS:
            # base Item.PlayAnimation (Item.cs:894-905)
            table = it.use_tricked_anim if it.tricked else it.use_anim
            return list(table.get('Rottweiler') or []), None
        # the Drawing subclass cycles its RottweilerUse set itself
        # (Drawing.cs:44-68) — handled by _drawing_use before this call
        it.current_sequence = 'RottweilerUse'      # the default stamp
        if it.pc_masked:
            # a visit the PC plays untricked (206: the pad's load and Fifi's
            # take while its rabbit waits, the harpoon's take with the pad
            # armed — Level206RoutineBehavior): the plain use
            return list(it.use_anim.get('Rottweiler') or []), \
                (lambda: w.play_use_item_anim(it))
        if linked is not None and linked.tricked and it.tricked \
                and it.use_tricked_linked:            # cs:804-817
            it.current_sequence = 'RottweilerUseLinkedTricked'
            if it.name == 'SandCastle':               # cs:806-811
                it.rott_use_exit_delta[0] = 0.0
                it.rott_prime_exit_delta = (0.0, it.rott_prime_exit_delta[1])
                it.rott_use_item_exit_delta[0] = 0.0
            self._extra_coin_210(it)                  # cs:812
            self._extra_coin_206(it)                  # cs:813
            self._change_animation_210(it)            # cs:814
            self._depends_nfh2(it, linked)            # cs:816
            return list(it.use_tricked_linked), \
                (lambda: w.play_tricked_item_anim(it, self.pawn))
        if it.play_custom_tricked and it.tricked:     # cs:818-823
            return list(it.rott_custom_tricked), \
                (lambda: w.play_tricked_item_anim(it, self.pawn))
        if it.compound and it.compound_tricked and it.tricked:   # cs:824-830
            self._extra_coin_compound(it)
            return list(it.rott_compound_use_tricked), \
                (lambda: w.play_tricked_item_anim(it, self.pawn))
        if it.fucked_up and it.should_play_rott_fuckedup:        # cs:831-836
            return list(it.rott_use_fuckedup), \
                (lambda: w.play_item_anim(it, it.use_fucked_up))
        if it.depends_pig_keys and w is not None:     # cs:837-842
            keys = items.get(it.pig_keys)
            milk = items.get(it.pig_milk)
            if keys is not None and keys.primed and keys.tricked and \
                    (milk is None or not milk.tricked):
                return list(it.rott_surprise), \
                    (lambda: w.play_tricked_item_anim(it, self.pawn))
        if it.tricked and not it.use_at_other_place and not it.neutral:
            if it.name == 'SandCastle':               # cs:843-856
                it.rott_use_exit_delta[0] = -0.9
                it.rott_use_item_exit_delta[0] = 0.4
            self._toilet_211(it)                      # cs:850
            self._fish_plant(it)                      # cs:851
            self._depends_nfh2(it, linked)            # cs:855
            it.current_sequence = 'RottweilerUseTricked'
            return list(it.use_tricked_anim.get('Rottweiler') or []), \
                (lambda: w.play_tricked_item_anim(it, self.pawn))
        shade = shez = None
        if it.depends_on_shade_tricked:               # cs:799-803
            shade = next((i for i in items.values()
                          if i.name == 'SunShade'), None)
            shez = next((i for i in items.values()
                         if i.name == 'Shezlong'), None)
        if dep is not None and dep.tricked and dep.got_tricked \
                and (not it.use_depends_on_when_tricked or it.tricked) \
                and not it.depends_on_shade_tricked:  # cs:857-862
            return list(dep.use_tricked_anim.get('Rottweiler') or []), \
                (lambda: w.play_tricked_item_anim(it, self.pawn))
        if it.use_depends_on_when_tricked and it.tricked \
                and not it.depends_on_shade_tricked and dep is not None:
            return list(dep.use_anim.get('Rottweiler') or []), \
                (lambda: w.play_tricked_item_anim(it, self.pawn))   # cs:863-868
        if it.depends_on_shade_tricked and shade is not None \
                and shade.tricked and dep is not None:
            if not dep.tricked and (shez is None or not shez.tricked):
                return list(dep.use_anim.get('Rottweiler') or []), \
                    (lambda: w.play_tricked_item_anim(it, self.pawn))  # cs:869-874
            if dep.tricked and (shez is None or not shez.tricked):
                dep.got_tricked = True                # cs:875-881
                return list(dep.use_tricked_anim.get('Rottweiler') or []), \
                    (lambda: w.play_tricked_item_anim(it, self.pawn))
        if it.fucked_up:                              # cs:882-887
            return list(it.use_anim.get('Rottweiler') or []), \
                (lambda: w.play_item_anim(it, it.use_fucked_up))
        if it.name == 'SandCastle':                   # cs:888-895
            it.rott_prime_exit_delta = (0.0, it.rott_prime_exit_delta[1])
            it.rott_use_exit_delta[0] = 0.0
            it.rott_use_item_exit_delta[0] = 0.0
        if it.name == 'LaunchPad' and not it.tricked \
                and linked is not None and linked.tricked \
                and not pcprofile.is_pc():                   # cs:896-902
            # (the PC's pad steps never shoot the rubber alone: the shoot
            # step 0x1002d948 plays shootbear with no question; the rubber
            # fires at the harpoon's take, 0x1002dd0a -> 0x1002da29)
            it.harpoon_aux = True
            return list(linked.use_tricked_anim.get('Rottweiler') or []), \
                (lambda: w.play_tricked_item_anim(linked, self.pawn))
        self._depends_nfh2(it, linked)                # cs:905
        return list(it.use_anim.get('Rottweiler') or []), \
            (lambda: w.play_use_item_anim(it))

    def _extra_coin_compound(self, it):
        """Item.ExtraCoinCompound (Item.cs:2398-2409): the Tortilla and the
        carnivorous plant pay a second trick"""
        w = self.pawn.world
        if w is None:
            return
        if it.name == 'Tortilla' and it.tricked and it.compound_extra_coin:
            w.game.trick_done(it.trick_score)
        elif it.name == 'PlantCarnivore' and it.tricked \
                and it.plant_carnivore_extra:
            w.game.trick_done(it.trick_score)

    def _extra_coin_206(self, it):
        """Item.ExtraCoin206Calculation (Item.cs:2411-2418)"""
        w = self.pawn.world
        if pcprofile.is_pc() and it.pc_extra_pays_at_linked is not None:
            return            # booked with its record (World.pc_s2_extra_credit)
        linked = self.level.items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        if w is not None and it.name == 'LaunchPad' and it.tricked \
                and linked is not None and linked.tricked:
            w.game.trick_done(it.trick_score)

    def _extra_coin_210(self, it):
        """Item.ExtraCoin210Calculation (Item.cs:2420-2427)"""
        w = self.pawn.world
        linked = self.level.items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        basket = self.level.items.get(it.dog_basket_210) \
            if it.dog_basket_210 else None
        if w is not None and it.name == 'DogBasket' and it.tricked \
                and linked is not None and linked.tricked \
                and basket is not None and basket.primed:
            w.game.trick_done(it.trick_score)

    def _change_animation_210(self, it):
        """Item.ChangeAnimation210 (TrickItem.cs:918-929)"""
        basket = self.level.items.get(it.dog_basket_210) \
            if it.dog_basket_210 else None
        if basket is not None and basket.primed and it.use_tricked_linked:
            it.use_tricked_linked = ['RottTickle', 'PoolFallEmpty',
                                     'PoolLeaveEmpty']

    def _depends_nfh2(self, it, linked):
        """TrickItem.DependsOnNFH2Behavior (TrickItem.cs:931-945): the
        NFH2 dependency acts its own use sequence alongside"""
        w = self.pawn.world
        dep = self.level.items.get(it.depends_nfh2) if it.depends_nfh2 else None
        if w is None or dep is None or linked is None:
            return
        p = w.players.get(id(dep.sprite)) if dep.sprite else None
        if p is None:
            return
        if dep.tricked and not linked.tricked:
            seq = [x for x in dep.use_tricked_sequence if p.has(x)]
        elif not dep.tricked and not linked.tricked:
            seq = [x for x in dep.use_normal_sequence if p.has(x)]
        elif dep.tricked and linked.tricked:
            seq = [x for x in dep.use_tricked_sequence if p.has(x)]
        else:
            seq = []
        if seq:
            p.play_sequence(seq)

    def _toilet_211(self, it):
        """Item.Toilet211Behavior (Item.cs:2373-2386): the tricked sweets
        with the tricked linked toilet retarget the toilet run, arm the
        after-toilet angry and pay the extra coin"""
        w = self.pawn.world
        rush = self.level.items.get(it.linked_trick_rush_toilet) \
            if it.linked_trick_rush_toilet else None
        if w is None or not it.tricked or rush is None or not rush.tricked \
                or it.name != 'Sweets':
            return
        if it.linked_trick_rush_toilet_target:
            self.pawn.toilet_action['item'] = it.linked_trick_rush_toilet_target
        olga = w.pawns.get('Olga')
        if olga is not None:
            spec = self.level.pawns.get('Olga') or {}
            it.pawn_to_affect = spec.get('pid')
        it.play_angry_after_toilet = True
        it.extra_coin_toilet_211 = True    # feeds the NFH2 anger ladder
        if pcprofile.is_pc() and it.pc_toilet_pays_at is not None:
            return            # booked with its record in the wc (World.pc_s2_extra_credit)
        w.game.trick_done(it.trick_score)

    def _fish_plant(self, it):
        """Item.FishPlantBehavior (Item.cs:2388-2396): the tricked bouquet
        strips Olga's next two actions"""
        if it.name != 'Bouquet' or not it.tricked \
                or self.role != 'Rottweiler':
            return
        ort = next((r for r in self.pawn.world.routines
                    if r.role == 'Olga'), None) if self.pawn.world else None
        if ort is not None and len(ort.actions) > 2:
            del ort.actions[1]
            del ort.actions[1]
            ort.index = max(0, ort.index - 1)

    def _change_hit_pawn_animation_207(self, it):
        """TrickItem.ChangeHitPawnAnimation207 (TrickItem.cs:1264-1280)"""
        w = self.pawn.world
        olga = w.pawns.get('Olga')
        rott = w.pawns.get('Rottweiler')
        linked = self.level.items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        if it.name == 'SandCastle':
            if olga is not None and olga.hit_pawn_action.get('sequence'):
                olga.hit_pawn_action['sequence'][0] = 'SandCastleLiftOlga'
            if rott is not None:
                rott.wait_in_fear_anim = 'SandCastleFallOneFrame'
        elif olga is not None and it.name == 'Shell':
            if olga.hit_pawn_action.get('sequence'):
                olga.hit_pawn_action['sequence'][0] = 'HitPawn'
            if rott is not None:
                rott.wait_in_fear_anim = 'WaitInFear'
        elif it.name == 'PoolBoard' and linked is not None and linked.tricked:
            if rott is not None:
                rott.wait_in_fear_anim = 'WaitInFear'

    def _after_use_side_effects(self, a, it):
        """RoutineActionUse.OnActionStarted's side-effect run
        (RoutineActionUse.cs:201-307), in source order: the toilet flag, the
        tricked hide-after, the during-use hides and activations, the layer
        swap, then the prime/trick-after-use tail and the Bed mark."""
        w = self.pawn.world
        if w is None:
            return
        items = self.level.items
        if a.get('is_toilet') and self.role == 'Rottweiler':
            self.pawn.is_using_toilet = True           # cs:201-204
        if it.is_tricked(items) and a.get('go_hide_after_use_tricked'):
            tgt = items.get(a['go_hide_after_use_tricked'])
            if tgt is not None:                        # cs:209-212
                w.set_active_object_hidden(tgt, True)
        if a.get('hide_object'):                       # cs:217-220
            w.set_active_object_hidden(it, True)
        if a.get('hide_object_tricked') and it.tricked:  # cs:221-224
            w.set_active_object_hidden(it, True)
        if a.get('hide_object_tricked_delayed'):       # cs:225-228
            tgt = items.get(a['hide_object_tricked_delayed'])
            if tgt is not None:
                w.call_later(a.get('hide_object_tricked_delay') or 0.0,
                             lambda t=tgt: w.set_active_object_hidden(t, True))
        if a.get('hide_child'):                        # cs:229-232
            w.set_child_renderers_hidden(it, True)
        if a.get('object_to_hide'):                    # cs:233-236
            tgt = items.get(a['object_to_hide'])
            if tgt is not None:
                w.set_active_object_hidden(tgt, True)
        if a.get('object_to_hide_tricked') and it.is_tricked(items):
            tgt = items.get(a['object_to_hide_tricked'])
            if tgt is not None:                        # cs:237-240
                w.set_active_object_hidden(tgt, True)
        if a.get('object_to_activate'):                # cs:241-244
            tgt = items.get(a['object_to_activate'])
            if tgt is not None:
                w.set_active(tgt, True)
        if a.get('pawn_to_hide'):                      # cs:245-248
            p = w.pawn_by_pid(a['pawn_to_hide'])
            if p is not None:
                p.set_hidden(True)
        linked = items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        if a.get('change_layer_linked') and it.tricked \
                and linked is not None and linked.tricked:
            from scene import GUI_DEPTH                # cs:249-261
            depth = GUI_DEPTH.get(a.get('layer_to_change'))
            tgt = items.get(a.get('item_to_change_layer')) \
                if a.get('item_to_change_layer') else None
            if tgt is not None and tgt.sprite is not None and depth:
                a['_layer_aux'] = tgt.sprite.depth
                tgt.sprite.depth = depth
            p = w.pawn_by_pid(a.get('pawn_to_change_layer')) \
                if a.get('pawn_to_change_layer') else None
            if p is not None and depth:
                a['_layer_aux'] = p.sprite.depth
                p.sprite.depth = depth
        tgt = self.level.items.get(a.get('prime_after_use_tricked')) \
            if a.get('prime_after_use_tricked') else None
        if tgt is not None and it.tricked:
            d = a.get('prime_tricked_delay') or 0.0
            if d == 0.0:
                w.set_primed(tgt, not tgt.primed)
            else:
                w.call_later(d, lambda t=tgt: w.set_primed(t, not t.primed))
        tgt = self.level.items.get(a.get('prime_after_use')) \
            if a.get('prime_after_use') else None
        if tgt is not None:
            d = a.get('prime_delay') or 0.0
            if d == 0.0:
                w.set_primed(tgt, not tgt.primed)
            else:
                w.call_later(d, lambda t=tgt: w.set_primed(t, not t.primed))
        tgt = self.level.items.get(a.get('trick_after_use')) \
            if a.get('trick_after_use') else None
        if tgt is not None:
            tgt.tricked = not tgt.tricked  # RoutineActionUse.cs:298-301
        if it.kind in TRICK_KINDS and it.is_bed:
            it.is_rottweiler_sleeping = True   # cs:302-306

    def _tricked_item(self, it):
        """RoutineActionUse.GetTrickedItem"""
        if it.tricked and not it.use_depends_on_when_tricked:
            return it
        if it.depends_on is not None:
            dep = self.level.items.get(it.depends_on)
            if dep is not None and dep.tricked:
                if dep.force_fix_original:
                    return it
                return dep
        return None

    def abandon_urgent(self):
        """a running urgent template dropped by a script's restart of the
        routine (ActionManager.StartAction stops the Active urgent for the
        routine action it starts, cs:157-160; the SurpriseNear the skates
        ride began never reaches its own StopUrgentAction): the urgent
        fields clear so the next surprise stashes its own OriginalAction
        — without this the marbles' surprise after the skates inherited
        the mixer and sent him back to it, past the expander (Level112)"""
        self._urgent_action = None
        self.urgent_item = None
        self._urgent_handler = None
        self._original_action = None
        self._urgent_stack = []
        self.pawn.in_urgent = False

    def unfreeze(self, start_next=True, advance=False, idx_after=0):
        """ActionManager.Unfreeze (ActionManager.cs:797-812): drop the
        freeze, re-anchor at 0 when the caller says ...AfterForceAdvance
        is 1, optionally advance, then StartNextAction"""
        self.frozen = False
        if idx_after == 1:
            self.index = 0
        if advance:
            self._advance()
        if start_next:
            self._pending = 'first'      # StartNextAction on this index

    def remove_action_by_index(self, index):
        """ActionManager.RemoveActionByIndex (ActionManager.cs:844-850)"""
        if 0 <= index < len(self.actions):
            del self.actions[index]

    def add_in_game_actions(self, index=None):
        """ActionManager.AddInGameActions (ActionManager.cs:814-842): insert
        the serialized extras after the active action (or at the index)."""
        if not self.actions_to_add:
            return
        at = (self.index % len(self.actions)) + 1 if index is None else index
        for k, a in enumerate(self.actions_to_add):
            self.actions.insert(at + k, a)

    def remove_actions_by_item(self, item_pid):
        """ActionManager.RemoveActionByItem (ActionManager.cs:748-790):
        rebuild the list and re-anchor the index the way the original does
        inside its loop, with the Plant and WateringCan arms."""
        if not self.actions:
            return
        removed = self.level.items.get(item_pid)
        if removed is not None and removed.name == 'Plant':
            removed.tricked = True        # ActionManager.cs:752-755
        cans = []
        if not self.remove_watering_can or self.remove_now:
            cur = self.index % len(self.actions)
            kept = []
            anchor = None
            for i, a in enumerate(self.actions):
                a_it = self.level.items.get(a['item']) if a['item'] else None
                if a_it is not None and a_it.name == 'WateringCan':
                    cans.append(a)
                if a['item'] != item_pid:
                    kept.append(a)
                if i == cur:
                    anchor = len(kept) - 1
            if kept:
                self.actions = kept
                if anchor is not None:
                    self.index = anchor   # the pending advance lands next
            if self.remove_now:           # ActionManager.cs:775-779
                self.index = 1
                self.remove_now = False
        if removed is not None and removed.name == 'WateringCan' \
                and not self.remove_watering_can and cans and \
                len(self.actions) >= 2:
            # the can's first removal parks it as action 1 for one more round
            # (ActionManager.cs:781-789)
            self.actions = [self.actions[0], cans[0], self.actions[1]]
            self.remove_watering_can = True

    def _stop_side_effects(self, a, it):
        """RoutineActionUse.StopAction's side-effect run (cs:386-535): the
        unlocks, the exit deltas with their one-shot aux flags, the unhides,
        the Bed clear, the after-use hide/show and the layer restore. The
        original runs this on BOTH stop calls of a tricked use."""
        w = self.pawn.world
        if w is None or a is None:
            return
        items = self.level.items
        # the unlocks and the tutorial's alternate switch run for EVERY
        # action, a MoveOnly one included — only the tricked unlocks sit
        # behind `Item != null` (RoutineActionUse.cs:390-407); Intro103's
        # dog walk is a MoveOnly step whose ItemsToUnlock opens the Drawer
        for pid in a.get('doors_to_unlock') or ():     # cs:390-393
            d = self.level.door_by_pid(pid)
            if d is not None:
                w.unlock_door(d)
        for pid in a.get('items_to_unlock') or ():     # cs:394-397
            tgt = items.get(pid)
            if tgt is not None:
                tgt.locked = False
        if it is not None and it.tricked:              # cs:398-404
            for pid in a.get('items_to_unlock_tricked') or ():
                tgt = items.get(pid)
                if tgt is not None:
                    tgt.locked = False
        if w.level_script is not None:
            # the tutorial's alternate-description switch
            # (RoutineActionUse.cs:405-407)
            w.level_script.on_rottweiler_action()
        if a.get('move_only') or it is None:
            # everything below reads the action's Item (cs:415-535)
            return
        dont_on_owner = it.dont_use_on is not None and \
            w.pawn_by_pid(it.dont_use_on) is self.pawn
        dx, dy = it.rott_use_item_exit_delta
        if (dx > 0 or dy > 0) and not it.exit_delta_aux and it.tricked:
            if not dont_on_owner:                      # cs:428-440
                self.pawn.sprite.x += dx
                self.pawn.sprite.y += dy
                self.pawn.pos_snap = True
                it.exit_delta_aux = True
        else:
            it.exit_delta_aux = False                  # cs:441-444
        dx, dy = it.rott_use_not_tricked_exit_delta
        if (dx > 0 or dy > 0) and not it.exit_delta_not_tricked_aux \
                and not it.tricked and \
                (not it.already_tricked or it.still_use_not_tricked_delta):
            if not dont_on_owner:                      # cs:445-453
                self.pawn.sprite.x += dx
                self.pawn.sprite.y += dy
                self.pawn.pos_snap = True
                it.exit_delta_not_tricked_aux = True
        else:
            it.exit_delta_not_tricked_aux = False      # cs:454-457
        # the plain exit delta, prime-vs-use by WasPriming (cs:458-480);
        # DontUseOn skips the owner it names
        delta = it.rott_prime_exit_delta if it.was_priming \
            else it.rott_use_exit_delta
        if not dont_on_owner:
            self.pawn.sprite.x += delta[0]
            self.pawn.sprite.y += delta[1]
            self.pawn.pos_snap = True
        if a.get('hide_object'):                       # cs:485-488
            w.set_active_object_hidden(it, False)
        if a.get('hide_object_tricked') and it.tricked:  # cs:489-492
            w.set_active_object_hidden(it, False)
        if a.get('hide_child'):                        # cs:493-496
            w.set_child_renderers_hidden(it, False)
        if a.get('object_to_hide'):                    # cs:497-500
            tgt = items.get(a['object_to_hide'])
            if tgt is not None:
                w.set_active_object_hidden(tgt, False)
        if a.get('object_to_hide_tricked'):            # cs:501-504
            tgt = items.get(a['object_to_hide_tricked'])
            if tgt is not None:
                w.set_active_object_hidden(tgt, False)
        if a.get('object_to_activate'):                # cs:505-508
            tgt = items.get(a['object_to_activate'])
            if tgt is not None:
                w.set_active(tgt, False)
        if a.get('pawn_to_hide'):                      # cs:509-512
            p = w.pawn_by_pid(a['pawn_to_hide'])
            if p is not None:
                p.set_hidden(False)
        if it.kind in TRICK_KINDS and it.is_bed:       # cs:513-516
            it.is_rottweiler_sleeping = False
        if a.get('go_hide_after_use'):                 # cs:517-520
            tgt = items.get(a['go_hide_after_use'])
            if tgt is not None:
                w.set_active_object_hidden(tgt, True)
        linked = items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        if a.get('change_layer_linked') and it.tricked \
                and linked is not None and linked.tricked \
                and a.get('_layer_aux') is not None:   # cs:521-531
            tgt = items.get(a.get('item_to_change_layer')) \
                if a.get('item_to_change_layer') else None
            if tgt is not None and tgt.sprite is not None:
                tgt.sprite.depth = a['_layer_aux']
            p = w.pawn_by_pid(a.get('pawn_to_change_layer')) \
                if a.get('pawn_to_change_layer') else None
            if p is not None:
                p.sprite.depth = a['_layer_aux']
        if a.get('go_show_after_use'):                 # cs:532-535
            tgt = items.get(a['go_show_after_use'])
            if tgt is not None:
                w.set_active_object_hidden(tgt, False)

    def _pc_trick_item(self, it):
        """the item whose PC trick a tricked station plays: the one its angry
        pays, RoutineActionUse.GetTrickedItem (_tricked_item). A station
        tricked through its DependsOn plays the dependency's trick — 113's
        chair kit the pain book's (lir/stoolkit_pain), 109's chili the chips'
        (kit/cookiebox_hot), 102's sofa the laxative beer's — with that
        trick's stand, fire and pay, as game.exe's level class runs that
        trick's own case (tools/pcref/pc_reactions.py maps every PC trick
        onto the item that pays it); the host's values are its own trick's"""
        if it is None or not it.is_tricked(self.level.items):
            return it
        return self._tricked_item(it) or it

    def _pc_clip_end(self):
        """the per-clip timing, the hold and the credit watch end with the use"""
        self.pawn.anim.clip_pace = None
        self.pawn.anim.skip_clip = False
        self._pc_credit = None
        if self._pc_wait is not None:
            self._pc_wait = None
            self.pawn.anim.hold_clip = None

    def _pc_clip_use(self, it):
        """a use the profile times per clip: its clips at their PC seconds
        (PCClipSeconds for the neighbour's station, PCClipSecondsRole for
        another role's), and a clip held until another role has used an item
        (PCWaitFor — 202's swim step waits at the shore until the `sub`
        Olga's Submarine use switches into the sea, GameLogic 0x100224a8-
        0x10022563, then the kid's dive and run ashore, 0x10022046)"""
        if it is None or not pcprofile.rule('durations'):
            return
        table = it.pc_clip_secs if self.role == 'Rottweiler' \
            else it.pc_clip_secs_role.get(self.role)
        self.pawn.anim.clip_pace = dict(table) if table else None
        wf = it.pc_wait_for if self.role == 'Rottweiler' \
            else it.pc_wait_for_role.get(self.role)
        if wf:
            self._pc_wait = dict(wf, released=None)
            self.pawn.anim.hold_clip = wf['clip']

    def _pc_wait_tick(self, dt):
        """the held clip's release (PCWaitFor): once the awaited role has used
        the awaited item (its pc_put mark, consumed here — the one sub in the
        sea), or begun to (`at` start: its pc_began mark — 210's call and his
        arrival at her chair), the clip plays on for the `then` seconds, then
        the sequence goes on"""
        wt = self._pc_wait
        if wt['released'] is None:
            src = next((i for i in self.level.items.values()
                        if i.name == wt['item']), None)
            marks = None if src is None else \
                (src.pc_began if wt.get('at') == 'start' else src.pc_put)
            if marks is not None and wt['role'] in marks:
                marks.discard(wt['role'])
                wt['released'] = 0.0
            return
        wt['released'] += dt
        if wt['released'] < float(wt['then']) - 1e-9:
            return
        self._pc_wait = None
        anim = self.pawn.anim
        anim.hold_clip = None
        if anim.anim is not None and anim.anim.name == wt['clip']:
            anim._stop_single()

    def _pc_use_seconds(self, it):
        """the PC station's seconds for this visit of the neighbour's routine under the
        profile (the item's PCUseSeconds, one value or one per visit, cycling); 0 = none"""
        if it is None or not pcprofile.is_pc() or not pcprofile.rule('durations'):
            return 0.0
        if self.role != 'Rottweiler':
            # another actor's stand at the PC data's `time` (PCUseSecondsRole)
            vals = (getattr(it, 'pc_use_secs_role', None) or {}).get(self.role)
            if not vals:
                return 0.0
            k = it.pc_use_visit_role.get(self.role, 0)
            it.pc_use_visit_role[self.role] = k + 1
            return float(vals[k % len(vals)])
        t = self._pc_trick_item(it)
        linked = self.level.items.get(it.linked_item_trick) if it.linked_item_trick else None
        if getattr(it, 'pc_use_secs_linked', None) is not None and it.tricked \
                and linked is not None and linked.tricked and it.use_tricked_linked:
            # the linked-tricked stand (PCUseSecondsLinked: the use the
            # mobile plays as RottweilerUseLinkedTricked is the script's
            # other step — 201's crash_long by the open rail); its visit slot
            # passes as any
            self._pc_visit_seconds(it)
            return float(it.pc_use_secs_linked)
        if getattr(t, 'pc_use_secs_tricked', None) is not None \
                and it.is_tricked(self.level.items):
            # the tricked stand's own seconds (PCUseSecondsTricked: game.exe
            # runs kit/foambottle's make_foampudding, 38 frames, not
            # kit/milkbottle's make_pudding — docs/PC_ROUTINES.md "The
            # stands"); 0 = the PC plays nothing before the fire (104's dirty
            # microwave fires on arrival and cooks after the clean): the
            # mobile's tricked clip runs at its own pace, not the normal stay's.
            # The stand is the playing trick's (_pc_trick_item). It is this
            # visit of the PC station order all the same — the case's other
            # branch, then the chain's next case — so its slot passes
            self._pc_visit_seconds(it)
            return float(t.pc_use_secs_tricked)
        return self._pc_visit_seconds(it)

    def _pc_visit_seconds(self, it):
        """the item's PCUseSeconds for this visit: one value, or one per
        visit in the PC station order, cycling; 0 = none"""
        if not getattr(it, 'pc_use_secs', None):
            return 0.0
        v = it.pc_use_secs[it.pc_use_visit % len(it.pc_use_secs)]
        it.pc_use_visit += 1
        return float(v)

    def _finish(self):
        """RoutineActionUse.StopAction(canPostponeStop: true): the side
        effects run, then a tricked TrickItem does not finish the action —
        the owner plays the angry sequence first (RoutineActionUse.cs:
        541-553). The stop also removes spent actions (cs:415-427)."""
        self.pawn.anim.time_scale = 1.0
        self._pc_clip_end()
        if pcprofile.is_pc() and self.item is not None \
                and self.state == self.USING:
            # a held clip elsewhere waits for this role's use of this item
            # (PCWaitFor: Olga's sub in the sea)
            self.item.pc_put.add(self.role)
        self.pc_hold = 0.0
        self.pc_fire_at = 0.0; self.pc_fire_item = None
        self.pc_credit_timer = 0.0; self.pc_credit_item = None
        self.pc_credit2_timer = 0.0; self.pc_credit2_item = None
        self.pc_credit3_timer = 0.0; self.pc_credit3_item = None
        it = self.item
        a = self.action
        self.timer = 0.0                  # Finished: no timeout can follow
        # the side effects run for EVERY stop — a MoveOnly step's unlocks
        # and the tutorial switch included (RoutineActionUse.cs:386-412)
        self._stop_side_effects(a, it)
        if it is not None:
            if it.should_destroy() and it.is_tricked(self.level.items):
                self.remove_actions_by_item(it.pid)
            dep = self.level.items.get(it.depends_on) \
                if it.depends_on is not None else None
            if dep is not None and dep.should_destroy() and dep.tricked:
                self.remove_actions_by_item(dep.pid)
            if it.remove_after_first_use:
                self.remove_actions_by_item(it.pid)
        w = self.pawn.world
        if self.role == 'Rottweiler' and it is not None and w is not None:
            # the Harpoon hand-off (cs:541-545): the pad's stop plays the
            # tricked harpoon's angry instead
            linked = self.level.items.get(it.linked_item_trick) \
                if it.linked_item_trick else None
            if linked is not None and linked.tricked \
                    and linked.name == 'Harpoon' and it.harpoon_aux:
                it.harpoon_aux = False
                self._angry_target = linked
                w.play_angry(self.pawn, linked, on_done=self._angry_done)
                return
            # `Item as TrickItem` (cs:419) passes the subclasses too — the
            # Drawing (L107) and the Rake (L202) go angry like any TrickItem
            if it.kind in TRICK_KINDS and it.is_tricked(self.level.items):
                target = self._tricked_item(it)
                if target is not None and self._pc_defer_angry(it, target):
                    return
                hook = getattr(w.level_script, 'pc_trick_hook', None)
                if target is not None and hook is not None and hook(self, it, target):
                    return                # the PC tutorial's script goes on (201)
                if target is not None:
                    self._angry_target = target
                    w.play_angry(self.pawn, target, on_done=self._angry_done)
                    return
        if it is not None and it.pc_masked:
            it.pc_masked = False           # the untricked visit is over
        self._action_stopped()
        self._pending = 'advance'
        self._check_parked_runs()

    def _pc_defer_angry(self, it, target):
        """the PC's shout and repair of a tricked station played back at it
        after a run (PCTrickReturn: 205's nailed skis — the ride's record
        pays as the ride ends, then the script runs him to the ski, 0x10024fde,
        pants, shouts and repairs it, 0x1002512d): the coin now, the station's
        next visit — reached at a run — plays the rest"""
        if not pcprofile.is_pc() or not getattr(target, 'pc_trick_return', None) \
                or target is not it or not self.actions:
            return False
        nxt = self.actions[self._next_index(self.index)]
        if nxt.get('item') != it.pid:
            return False
        w = self.pawn.world
        if not target.pc_credited:
            w.pc_s2_credit(self.pawn, target)
        self.pc_return = target
        self._action_stopped()
        self._pending = 'advance'
        self._check_parked_runs()
        return True

    def _pc_return_use(self, it):
        """the return visit of a deferred station (PCTrickReturn): he stands
        panting for its seconds (`pant`, 205), then the shout and the repair
        — the angry set — and the visit ends as the angry's does"""
        self.pc_return = None
        self.pawn.pc_run = False
        self.state = self.USING
        self.timer = 0.0
        w = self.pawn.world
        self.pawn._stand()

        def shout():
            self._angry_target = it
            w.play_angry(self.pawn, it, on_done=self._angry_done)
        pant = float((it.pc_trick_return or {}).get('pant') or 0.0)
        if pant > 0.0:
            self.pc_hold = pant
            self.pc_hold_cb = shout
        else:
            shout()

    def _angry_done(self):
        """the second StopAction arrives with canPostponeStop=false: the
        side effects run again — the aux flags gate the delta doubling — and
        the action finishes, or restarts for a ReuseAfterFix item
        (Rottweiler.cs:707-714, ActionManager.RestartCurrentAction)"""
        it = self.item
        if it is not None:
            self._stop_side_effects(self.action, it)
        target = getattr(self, '_angry_target', None)
        self._angry_target = None
        if getattr(self, '_stopped_for_urgent', False):
            # OnActionStopped already ran at the WaitInFear urgent's start
            # (_start_wait_in_fear): the action is no longer Active, and the
            # next StartAction stops nothing (ActionManager.cs:157-160)
            self._stopped_for_urgent = False
        else:
            self._action_stopped()
        if target is not None and target.reuse_after_fix:
            self._pending = 'start'
        else:
            self._pending = 'advance'
            if pcprofile.is_pc() and target is not None and target is it \
                    and target.pc_station_ends_on_trick:
                self._end_pc_station(target)
        self._check_parked_runs()

    def _end_pc_station(self, it):
        """the PC's three-phase machine (111's washer and drier, the
        overlay's PCStationEndsOnTrick: the mobile's RequireUnprime prime, use
        and unprime are one station of Level_Laundry::run, give, wash or dry,
        get_clothes or take): a tricked machine takes the case's other branch
        — the fire and the repair after the wash or the dry — which jumps to
        the case's yield (game.exe 0x455639), so the unprime visit that would
        follow is passed over and the machine is left unprimed for the next
        lap's give"""
        w = self.pawn.world
        if w is not None:
            w.set_primed(it, False)
        it.is_using = False
        if not self.actions:
            return
        nxt = self._next_index(self.index)
        if self.actions[nxt].get('item') == it.pid:
            # the queued advance then lands past the unprime, and its visit's
            # PCUseSeconds (get_clothes, take: played by the tricked branch
            # or not at all) passes with it
            self._pc_visit_seconds(it)
            self._advance()

    def _check_parked_runs(self):
        """the Rottweiler tail of RoutineActionUse.OnActionStopped
        (RoutineActionUse.cs:358-362): CheckSurpriseActionFar(NextAction)
        then CheckPendingAlarm(NextAction) fire the moment a non-mutex use
        stops — the parked run interrupts the action that was about to
        start (StartUrgentAction's nextAction wiring, ActionManager.cs:
        668-678), which is why the callers set `_pending` first: start_urgent
        materializes the advance and the resume lands on that action."""
        a = self.action
        if self.role != 'Rottweiler' or a is None or a.get('move_only') \
                or a.get('mutex'):
            return
        self._check_surprise_far()
        self._check_pending_alarm()

    def _anim_by_pid(self, pid):
        """resolve a serialized Item- or Pawn-component reference to the
        AnimPlayer it animates"""
        if pid is None or self.pawn.world is None:
            return None
        it = self.level.items.get(pid)
        if it is not None:
            return self.pawn.world.players.get(id(it.sprite)) \
                if it.sprite is not None else None
        for role, spec in self.level.pawns.items():
            if spec.get('pid') == pid:
                p = self.pawn.world.pawns.get(role)
                return p.anim if p is not None else None
        return None

    def _infinite_flags_on_start(self, a, it):
        """RoutineActionUse.OnActionStarted (RoutineActionUse.cs:152-171):
        SetIgnoreInfiniteLoop(true) on the item and pawn targets — the
        tricked variant reads the raw Item.Tricked flag — and
        SetIgnoreInfiniteLoopOnce (both flags, AnimationControllerBase.cs:
        213-217) on the once-targets."""
        t = self._anim_by_pid(a.get('stop_inf_item'))
        if t is not None:
            t.ignore_infinite = True
            if pcprofile.is_pc():
                # the PC's action posts its behavior= message as its job ends
                # and the other script answers on the tick after (205's
                # `talk`: behavior="pingpong" on Olga, whose step 0x10025b2a
                # gets her off the mat — `wakeup`, `leave`), PCBehaviourAt
                # into the stay: the loop ends then; not on the mat yet, she
                # goes straight to the table — her next use of it passes at
                # once (World.play_use_item_anim)
                stop_it = self.level.items.get(a.get('stop_inf_item'))

                def cut(t=t, stop_it=stop_it):
                    if t.anim is not None and t.anim.infinite:
                        t._stop_single()
                    elif stop_it is not None:
                        stop_it.pc_cut_pending = True
                at = getattr(it, 'pc_behaviour_at', None)
                w = self.pawn.world
                if at and w is not None:
                    w.call_later(float(at), cut)
                else:
                    cut()
        if it.tricked:
            t = self._anim_by_pid(a.get('stop_inf_pawn_tricked'))
            if t is not None:
                t.ignore_infinite = True
        t = self._anim_by_pid(a.get('stop_inf_pawn'))
        if t is not None:
            t.ignore_infinite = True
        t = self._anim_by_pid(a.get('once_pawn'))
        if t is not None:
            t.ignore_infinite = t.ignore_infinite_once = True
        if not it.tricked:
            t = self._anim_by_pid(a.get('once_pawn_not_tricked'))
            if t is not None:
                t.ignore_infinite = t.ignore_infinite_once = True
                self._pc_behaviour_cut(t, getattr(it, 'pc_behaviour_at', None))

    def _pc_behaviour_cut(self, t, at):
        """the PC's answer to the stay's behaviour: the other actor's script
        takes it on the offer's tick, PCBehaviourAt into the stay or
        PCBehaviourAtEnd after it (213's controls: his step posts `bull` to
        Olga as he arrives, 0x10037f5e, before the controls' `use`; her ride
        posts `leave` to him as its job ends) — her waiting loop the mobile
        ends at its round ends then"""
        if at is None or not pcprofile.is_pc():
            return
        w = self.pawn.world

        def cut():
            if t.anim is not None and t.anim.infinite:
                t._stop_single()
        if at and w is not None:
            w.call_later(float(at), cut)
        else:
            cut()

    def _action_stopped(self):
        """RoutineActionUse.OnActionStopped (RoutineActionUse.cs:319-353):
        MoveOnly returns first; then the ignore flags reset, the once-on-end
        target fires, HideOwnerDuringUse unhides (cs:481-484), and a
        non-mutex action releases PawnToAbortMutexOnFinish's parked mutex."""
        a = self.action
        self.pawn.anim.time_scale = 1.0
        self._pc_clip_end()
        self.pc_hold = 0.0
        self.pc_hold_cb = None
        self.pc_mutex_left = None
        self.pc_fire_at = 0.0; self.pc_fire_item = None
        self.pc_credit_timer = 0.0; self.pc_credit_item = None
        self.pc_credit2_timer = 0.0; self.pc_credit2_item = None
        self.pc_credit3_timer = 0.0; self.pc_credit3_item = None
        if a is None or a.get('move_only'):
            return
        it = self.item
        t = self._anim_by_pid(a.get('stop_inf_item'))
        if t is not None:
            t.ignore_infinite = False
        if it is not None and it.tricked:
            t = self._anim_by_pid(a.get('stop_inf_pawn_tricked'))
            if t is not None:
                t.ignore_infinite = False
        t = self._anim_by_pid(a.get('stop_inf_pawn'))
        if t is not None:
            t.ignore_infinite = False
        t = self._anim_by_pid(a.get('once_pawn_on_end'))
        if t is not None:
            t.ignore_infinite = t.ignore_infinite_once = True
            if it is not None:
                self._pc_behaviour_cut(t, getattr(it, 'pc_behaviour_at_end', None))
        if a.get('hide_owner'):
            self.pawn.set_hidden(False)   # cs:481-484
        if a.get('mutex'):
            return                        # cs:342: the mutex block ends here
        w = self.pawn.world
        if it is not None and w is not None:
            # Item.OnUseEnded resets the affect flags (Item.cs:2216-2223) and
            # the TrickItem override returns the pose to idle (cs:688-695)
            if self.role == 'Rottweiler' and it.pawn_to_affect is not None:
                it.use_olga_tricked_flag = False
                it.use_mother_tricked_flag = False
            if it.kind in TRICK_KINDS and not it.was_priming \
                    and not it.animate_after_use:
                w._return_to_idle(it)
            if a.get('is_toilet') and self.role == 'Rottweiler':
                self.pawn.is_using_toilet = False      # cs:354-357
        # Rottweiler.OnUseEnded lets the meter decay again (cs:879-892)
        self.pawn.can_decrease_angry = True
        self._abort_parked_mutex(a.get('abort_mutex_pawn'))

    def _abort_parked_mutex(self, pid):
        """OnActionStopped's PawnToAbortMutexOnFinish branch
        (RoutineActionUse.cs:344-351): SetHidden(false) on the named pawn,
        then AbortActiveMutex (cs:127-134) marks its mutex action Finished
        and calls AdvanceToNextAction — whose StartNextAction -> StartAction
        stops the still-Active mutex action first (ActionManager.cs:157-160
        -> RoutineAction.StopAction, cs:116-120), so its OnActionStopped
        DOES run: the ignore-loop resets of cs:326-341 (Level205's mat gets
        its InfiniteLoop back the moment the neighbour is sprung), while the
        cs:342 non-mutex block (OnUseEnded, the abort branch) is skipped."""
        if pid is None or self.pawn.world is None:
            return
        role = next((r for r, s in self.level.pawns.items()
                     if s.get('pid') == pid), None)
        if role is None:
            return
        for rt in self.pawn.world.routines:
            if rt.role == role:
                if rt.pc_mutex_left is not None:
                    return                # the PC's step times itself
                rt.pawn.set_hidden(False)
                act = rt.action
                if act is not None and act.get('mutex') \
                        and rt.state == rt.USING:
                    rt._action_stopped()
                    rt._pending = 'advance'
                return

    def _olga_item_seq_ended(self):
        """Olga.OnItemAnimationSequenceEnded (Olga.cs:154-158), the item
        controller's AlternateOnSequenceEnded delegate: the item's
        UseNormalSequence draining calls ActionManager.CurrentAction.
        StopAction(canPostponeStop: true) on whatever runs then — her mat
        use (a RoutineActionUse: the full stop, the postpone), a
        RoutineActionMove (the base Finished — the move restarts at the next
        Update, ActionManager.cs:449-457, a no-op here) or a HitPawn urgent
        (the base Finished -> StopUrgentAction resumes the use)."""
        if self.role != 'Olga' or self.state != self.USING:
            return
        ua = self._urgent_action
        if ua is None:
            self._finish()
        elif ua.get('kind') == 'hit_pawn':
            self._hit_pawn_done()

    # -- urgent interruptions (ActionManager.StartUrgentAction and the
    #    Rottweiler alarm plumbing) -----------------------------------------
    def is_alarm_postponed(self):
        """Rottweiler.IsAlarmPostponed (Rottweiler.cs:1047-1070) over the
        current action: a SurpriseNear always (cs:1049-1052); a SurpriseFar
        or a Grab by its PostponeAlarm (cs:1053-1056, 1061-1064); the
        interposed Move by NextAction.IsAlarmPostponed() (cs:1057-1060) —
        the action's own virtual, which is the bare PostponeAlarm for a Use
        (RoutineActionUse.cs:573-576) and a Grab (RoutineActionGrab.cs:26-29)
        and false for the rest (RoutineAction.cs:163-166); a Use — routine or
        the AlarmAction/ToiletAction/UseFixingItemAction templates — by
        PostponeAlarm || PostponeAlarmDuringUseOnly || Item.IsTricked()
        (cs:1065-1068). The port's MOVING state is the interposed Move."""
        ua = self._urgent_action
        moving = self.state == self.MOVING
        if ua is None:                    # the routine's RoutineActionUse
            a = self.action
            if a is None:
                return False
            if moving:
                return bool(a.get('postpone_alarm'))
            it = self.item
            return bool(a.get('postpone_alarm')
                        or a.get('postpone_alarm_during_use_only')
                        or (it is not None
                            and it.is_tricked(self.level.items)))
        if moving:
            return ua.get('kind') in ('grab', 'use') \
                and bool(ua.get('postpone_alarm'))
        return self._template_postponed(ua, self.urgent_item)

    def _template_postponed(self, ua, item):
        """the arms of Rottweiler.IsAlarmPostponed for an urgent template
        that is current (not its interposed move): cs:1049-1056, 1061-1068"""
        kind = ua.get('kind')
        if kind == 'surprise_near':
            return True
        if kind in ('surprise_far', 'grab'):
            return bool(ua.get('postpone_alarm'))
        if kind == 'use':
            return bool(ua.get('postpone_alarm')
                        or ua.get('postpone_alarm_during_use_only')
                        or (item is not None
                            and item.is_tricked(self.level.items)))
        return False

    def moving_to_alarm(self):
        """Rottweiler.MovingToAlarm"""
        return self.urgent_item is not None and self.urgent_item.kind == 'Alerter'

    def _passing_or_portal(self):
        """Rottweiler.HearAlerter's `!IsPassingDoor() && !PortalMove` (cs:272):
        the door transit itself and the walk-up climb / descend around it
        (Pawn.PortalMove spans Pawn.cs:1369-1371 to EndPortalMove, cs:1488-
        1493 / 1659)."""
        p = self.pawn
        return p.is_warping or p.state in (p.DOOR_CLIMB, p.DOOR_ANIM,
                                           p.DESCEND)

    def start_urgent(self, item, arrived=None, alarm_use=False, kind=None,
                     urgent=None, postpone_alarm=None,
                     postpone_alarm_during_use_only=False, name=None):
        """ActionManager.StartUrgentAction (ActionManager.cs:651-721) for
        the Rottweiler's urgent templates: drop the move in progress and go
        to the item; the interrupted action stays current for the resume. A
        chain step (the fixing-tool run) brings its own arrival handler;
        alarm_use marks a RoutineActionUse template (AlarmAction /
        ToiletAction), whose arrival runs a full Item.Use. `kind` and the
        flags describe the template for IsAlarmPostponed, `name` tells the
        templates of one kind apart; the default is Rottweiler.
        StartSurpriseActionFar's SurpriseActionFar (cs:1150-1154).
        The interposed move runs when the template's Urgent flag is set
        (RoutineActionMove.OnActionStarted, cs:68-75 -> Pawn.MoveToGoalUrgent,
        Pawn.cs:444-448) — SurpriseActionFar and ToiletAction serialize it,
        the AlarmAction and the Return leg do not, Grab/UseFixingItem do on
        L110/L113 only."""
        self.pawn.anim.time_scale = 1.0     # an urgent interrupts a paced station
        self.pc_hold = 0.0
        self.pc_fire_at = 0.0; self.pc_fire_item = None
        self.pc_credit_timer = 0.0; self.pc_credit_item = None
        self.pc_credit2_timer = 0.0; self.pc_credit2_item = None
        self.pc_credit3_timer = 0.0; self.pc_credit3_item = None
        self.started = True              # StartUrgentAction: CurrentAction = the urgent one
        w = self.pawn.world
        if self.role == 'Mother' and w is not None:
            # ActionManager.StartUrgentAction fires the Mother event
            # (ActionManager.cs:653-656)
            w.fire_event('mother_urgent')
        if self.frozen:
            return                        # ActionManager.cs:657-660
        # a queued advance means the next action already started in the
        # original's synchronous flow — materialize it so the resume lands
        # on the right action (StartUrgentAction interrupts the new one)
        if self._pending in ('advance', 'skip'):
            self._advance()
            self._pending = None
        elif self._pending in ('first', 'start'):
            self._pending = None
        if kind is None:
            tpl = self.pawn.surprise_far_action
            kind = 'surprise_far'
            if urgent is None:
                urgent = tpl.get('urgent', True)
            if postpone_alarm is None:
                postpone_alarm = tpl.get('postpone_alarm', False)
        if name is None:
            name = kind
        if arrived is None and self._urgent_action is not None:
            self._stash_interrupted_urgent(name)
        if self._urgent_action is None:
            self._original_action = self.action   # cs:715-718
        if os.environ.get('NFH_ROUTINE_LOG'):
            oa = self._original_action or {}
            oi = self.level.items.get(oa.get('item')) if oa.get('item') is not None else None
            print('routine %s t=%.1f urgent start kind=%s item=%s index=%s original=%s' % (
                self.role, getattr(self.pawn.world, 'time', 0.0), kind, getattr(item, 'name', None),
                self.index, getattr(oi, 'name', None)), file=sys.stderr)
        self.urgent_item = item
        self._urgent_action = {
            'kind': kind, 'name': name, 'postpone_alarm': bool(postpone_alarm),
            'postpone_alarm_during_use_only':
                bool(postpone_alarm_during_use_only)}
        self._urgent_handler = arrived
        self._alarm_use = alarm_use
        self.pawn.steps = []
        self.pawn.in_urgent = bool(urgent)
        self.pawn.pc_run = self._pc_runs(item, kind, name)
        self.state = self.MOVING
        # a new MoveAction target: RoutineActionMove.SameZone() is asked on
        # every ActionManager.Update while the urgent move toward a Dog/Chili
        # is active (ActionManager.cs:442-448, RoutineActionMove.cs:105-128;
        # IsUrgent() is the template's Urgent) — armed here, evaluated in
        # tick, and a manager killed by its null RottLastDoor lives again
        self._sz_watch = item.name in ('Dog', 'Chili') and bool(urgent)
        self._sz_flag = False
        self._manager_dead = False
        if self.routine_behavior is not None:
            # StartAction interposes MoveToAction for the away case
            # (ActionManager.cs:152-154, 119-124)
            if not self.pawn.at_use_range(item):
                self.routine_behavior.on_move_to_routine_action(item, None)
        if self.pawn.at_use_range(item):
            self._urgent_arrived()
        elif not self.pawn.goto_item(item, on_arrive=self._urgent_arrived):
            self._urgent_finished()

    def _pc_runs(self, item, kind, name):
        """whether game.exe's level class runs this urgent's walk (Season 1,
        the neighbour: the case sets the gait to mr or mrwc before its GoTo,
        pcprofile.GAIT_PX_PER_TICK) — the pets' alarm (the `noise` case),
        the toilet and first-aid rushes (the mobile's ToiletAction) and the
        runs the overlay marks on their object (PCRunTo): the antenna's
        shout (101/102's Television, the notice run), the fetch of a fixing
        tool and the way back to the target (110's extinguisher, 113's
        valves); the other urgents the PC walks (111's vacuum and carpet
        cases leave the gait at 0)"""
        run_next, self.pc_run_next = self.pc_run_next, False
        if self.role != 'Rottweiler' or not pcprofile.is_pc() or item is None:
            return False
        if run_next:
            return True
        w = self.pawn.world
        if kind == 'surprise_far' and w is not None and item.pid in w.alerters:
            return True
        if name == 'toilet':
            # Season 2: 211's sweets send him to the loo at a run (the gait
            # set to 2 before the walk to the WC, GameLogic 0x10030e07)
            return True
        if kind in ('surprise_far', 'grab') or name == 'alarm':
            # 211's ringing cabin phone (0x1002fd04) with the Season 1 marks
            return bool(getattr(item, 'pc_run_to', False))
        if name == 'use_fixing':
            return bool(getattr(self._fix_tool, 'pc_run_to', False))
        return False

    def _stash_interrupted_urgent(self, new_name):
        """StartUrgentAction's OriginalAction wiring when an urgent lands on
        a running one (ActionManager.cs:679-718): the running template
        becomes the newcomer's OriginalAction and StopUrgentAction restarts
        it when the newcomer ends (cs:647) — except a running SurpriseNear
        (cs:681-691), a fixing-chain step handing over to the next step
        (cs:692-710; those bring an arrival handler and never reach here), a
        ForceUseOriginalAction carrier (cs:711-714; L110's UseFixingItem-
        Action, whose chain is then abandoned with the tool in hand — the
        next visit fixes with it, Item.cs:854-857), and the same template
        restarted on itself (cs:679: `action != ActiveAction` — a second
        alerter run, or the carpet run of Rottweiler.cs:504). The port
        stacks the interrupted template and replays it from
        _urgent_finished. A stashed toilet run has already had its
        OnUseEnded at the interruption (Rottweiler.cs:879-892: FeelSick and
        InUrgentMove drop; RoutineActionUse.cs:354-357: IsUsingToilet)."""
        ua = self._urgent_action or {}
        kind = ua.get('kind')
        if kind in ('surprise_near', 'hit_pawn') or ua.get('name') == new_name:
            return
        if self._fix_tool is not None and self._urgent_handler is not None:
            tpl0 = self.pawn.grab_action if kind == 'grab' \
                else self.pawn.use_fixing_action
            if kind in ('grab', 'use') and tpl0.get('force_use_original'):
                self._fix_tool = self._fix_target = None
                return
        toilet = bool(getattr(self, '_toilet_run', False))
        if toilet:
            self._toilet_run = False
            if self.state == self.USING:
                # only an Active use is stopped by StartAction(newcomer)
                # (cs:157-160) — its OnActionStopped runs Rottweiler.
                # OnUseEnded (FeelSick, InUrgentMove; cs:879-892) and drops
                # IsUsingToilet (RoutineActionUse.cs:354-357); a run caught
                # on its way keeps the sick walk
                self.pawn.feel_sick = False
                self.pawn.is_using_toilet = False
        self._urgent_stack.append({
            'item': self.urgent_item, 'arrived': self._urgent_handler,
            'ua': ua, 'urgent': self.pawn.in_urgent, 'toilet': toilet})

    def _urgent_arrived(self):
        """RoutineActionSurpriseFar.OnActionStarted"""
        if self._manager_dead:
            return                        # MoveAction.Finished is never asked
        handler, self._urgent_handler = self._urgent_handler, None
        if handler is not None:
            handler()
            return
        it = self.urgent_item
        if it is None:
            return
        self._sz_watch = False            # the MoveAction is over
        if self.routine_behavior is not None:
            # StartAction's hook, on the urgent action too
            # (ActionManager.cs:165-168)
            self.routine_behavior.on_start_routine_action(it, None)
        # the SameZone shortcut's completion chains into the walk instead of
        # finishing the urgent (ActionManager.cs:459-481)
        done = self._same_zone_walk if self._same_zone else self._urgent_finished
        if self._alarm_use:
            # Rottweiler.MoveToAlarm's AlarmAction is a RoutineActionUse: the
            # arrival runs a full Item.Use (RoutineActionUse.cs:205)
            self._alarm_use = False
            if it.tricked and self.role == 'Rottweiler':
                it.got_tricked = True                    # Item.cs:836-838
            seq = [x for x in it.sequence_for(self.role,
                                              it.is_tricked(self.level.items),
                                              self.level.items)
                   if self.pawn.anim.has(x)]
            self.state = self.USING
            # the PC stand of a rush's use (108's toothbrush on the coffee
            # rush): the same pace and fire as a routine use (PCUseSeconds
            # Tricked, PCFireAt — docs/PC_ROUTINES.md "The stands")
            pc = self._pc_use_seconds(it) if pcprofile.is_pc() else 0.0
            w = self.pawn.world
            if pcprofile.is_pc() and pcprofile.SEASON2 and self.role == 'Rottweiler' \
                    and getattr(self, '_toilet_run', False):
                # the rush's own record this far into the wc's puke (211's
                # wcright, 27 of its 40 ticks: PCToiletPaysAt, fcn.1000140b)
                src = next((x for x in self.level.items.values()
                            if x.play_angry_after_toilet and x.extra_coin_toilet_211
                            and x.pc_toilet_pays_at is not None), None)
                if src is not None:
                    self.pc_credit3_timer = float(src.pc_toilet_pays_at)
                    self.pc_credit3_item = src
            ft = self._pc_trick_item(it)
            if pcprofile.is_pc() and self.role == 'Rottweiler' \
                    and getattr(ft, 'pc_fire_at', None) is not None \
                    and it.is_tricked(self.level.items) and not ft.pc_fired:
                if float(ft.pc_fire_at) > 0.0:
                    self.pc_fire_at = float(ft.pc_fire_at)
                    self.pc_fire_item = ft
                elif w is not None:
                    w.s1_fire(self.pawn, ft)
            if os.environ.get('NFH_ROUTINE_LOG'):
                print('routine %s t=%.1f use sequence (rush) item=%s seq=%s pc=%s mobile=%.2f' % (
                    self.role, getattr(self.pawn.world, 'time', 0.0), it.name, list(seq or []), pc,
                    self.pawn.anim.sequence_seconds(seq) if seq else 0.0), file=sys.stderr)
            if seq:
                if pc:
                    mobile = self.pawn.anim.sequence_seconds(seq)
                    if mobile > 0.0:
                        self.pawn.anim.time_scale = mobile / pc
                self.pawn.anim.play_sequence(seq, on_end=self._alarm_use_done)
            else:
                self._alarm_use_done()
            return
        # RoutineActionSurpriseFar.OnActionStarted
        # (RoutineActionSurpriseFar.cs:40-63): a tricked item goes straight
        # to the angry flow, a Neutral TrickItem gets a full Use, anything
        # else plays its surprise animation
        if it.is_tricked(self.level.items):
            self.pawn.world.play_angry(self.pawn, it,
                                       on_done=self._urgent_finished)
        elif it.kind in TRICK_KINDS and it.neutral and self.role == 'Rottweiler':
            if self._fixing_dispatch(it):
                return                     # the fetch replaces the use
            # Item.Use -> RottweilerUse: the raw-Tricked mark and the
            # tricked-or-normal use sequence (Item.cs:836-838, 894-908)
            if it.tricked:
                it.got_tricked = True
            seq = [a for a in it.sequence_for(self.role, it.tricked,
                                              self.level.items)
                   if self.pawn.anim.has(a)]
            self.state = self.USING
            if seq:
                self.pawn.anim.play_sequence(seq, on_end=done)
            else:
                done()
        elif it.kind == 'Alerter' or it.rott_surprise:
            seq = [a for a in it.rott_surprise if self.pawn.anim.has(a)]
            self.state = self.USING
            if seq:
                self.pawn.anim.play_sequence(seq, on_end=done)
            else:
                done()
        else:
            done()

    def _alarm_use_done(self):
        """the AlarmAction use drains into StopAction(canPostponeStop: true):
        a tricked item still plays the angry set first
        (RoutineActionUse.cs:546-553)"""
        it = self.urgent_item
        target = None
        if it is not None and it.kind in TRICK_KINDS \
                and it.is_tricked(self.level.items) \
                and self.pawn.world is not None:
            # PlayAngryAnimation(GetTrickedItem(trickItem)) (cs:548, 556-571):
            # a use tricked only through its dependency angers at the
            # dependency — Level102's toilet, fixed by the walk-past
            # surprise, pays the ToiletPaper on the same visit
            target = self._tricked_item(it)
        if target is not None:
            self.pawn.world.play_angry(self.pawn, target,
                                       on_done=self._urgent_finished)
        else:
            self._urgent_finished()

    def _same_zone_check(self):
        """RoutineActionMove.SameZone (RoutineActionMove.cs:105-128), asked
        on every ActionManager.Update while the urgent MoveAction toward a
        Dog/Chili is active (ActionManager.cs:442-448): once the pawn is in
        the item's zone and not passing a door, the position of that first
        frame (RottPos) and the door he last came through (RottLastDoor,
        Pawn.cs:1644-1647 — the port's rott_last_door) latch, and the run
        switches to the SameZone choreography as soon as he stands at or past
        RottLastDoor.RottweilerExitLocation + RottPos — (0,0) on every door of
        the Dog/Chili levels, so on that very frame, wherever he landed:
        StartAction(SurpriseActionFar) skips the MoveToAction (cs:152, the
        MoveAction stops with Velocity 0 + PauseMovement, RoutineActionMove.
        cs:97-102), the surprise plays on the spot, and Finished + SameZone
        walks him to the pet for the yell (cs:459-481). A neighbour who has
        not passed a door yet has no RottLastDoor: cs:121 throws inside
        Update every frame — the manager is dead (he walks to the pet and
        stands there) until the next StartUrgentAction retargets the
        MoveAction (a Level113 start: he begins in the dog's zone)."""
        it = self.urgent_item
        p = self.pawn
        if it is None or p.zone is None or it.zone != p.zone.pid \
                or p.is_warping:
            return
        if not self._sz_flag:
            self._sz_flag = True
            self._sz_pos = (p.sprite.x, p.sprite.y)
            self._sz_door = p.rott_last_door  # RottLastDoor, RoutineActionMove.cs:119
        if self._sz_door is None:
            self._manager_dead = True
            return
        ex = self._sz_door.rott_exit
        if p.sprite.x >= ex[0] + self._sz_pos[0] \
                and p.sprite.y >= ex[1] + self._sz_pos[1]:
            self._sz_flag = False
            self._sz_watch = False
            self._same_zone = True
            self._same_zone_yelled = False
            p.steps = []
            p.state = p.IDLE
            p.movement_paused = True      # MoveAction.OnActionStopped
            self._urgent_arrived()

    def _same_zone_walk(self):
        """ActiveAction.Finished with SameZone set: walk to the target
        (ActionManager.cs:461-469); the proximity check in tick plays the
        yell when he closes within 0.05"""
        it = self.urgent_item
        if it is None:
            self._urgent_finished()
            return
        self.state = self.MOVING
        self.pawn.movement_paused = False       # Owner.ContinueMovement
        # Owner.MoveToGoal(Item, Zone, TargetLocation, stopAtExitDoor: false)
        # (cs:466) is the plain walk: InUrgentMove drops (Pawn.cs:428-433)
        self.pawn.in_urgent = False
        if not self.pawn.goto_item(it, on_arrive=self._same_zone_yell):
            self._same_zone_yell()

    def _same_zone_yell(self):
        """RottweilerPositionToDog < 0.05: StopAction and the surprise-left
        yell (ActionManager.cs:470-480)"""
        if self._same_zone_yelled:
            return
        self._same_zone_yelled = True
        it = self.urgent_item
        self.pawn.steps = []
        self.pawn.state = self.pawn.IDLE
        seq = [a for a in (it.surprise_left if it is not None else [])
               if self.pawn.anim.has(a)]
        self.state = self.USING
        if seq:
            self.pawn.anim.play_sequence(seq, on_end=self._yell_done)
        else:
            self._yell_done()

    def _yell_done(self):
        """Rottweiler.OnAnimationSequenceEnded's Angry tail
        (Rottweiler.cs:485-510): a SurpriseSequenceLeft opening on 'Angry'
        resets the SameZone flags, and a tricked DirtyCarpet in the zone gets
        its urgent run — the one OnChangeZone always skips"""
        it = self.urgent_item
        self._same_zone = False
        self._same_zone_yelled = False
        if it is not None and it.surprise_left \
                and it.surprise_left[0] == 'Angry' \
                and self.pawn.zone is not None and self.pawn.world is not None:
            for carpet in self.pawn.world.notice_items.get(
                    self.pawn.zone.pid, ()):
                if carpet.tricked and carpet.name == 'DirtyCarpet' \
                        and carpet.zone == self.pawn.zone.pid:
                    self.pawn.movement_paused = False
                    self.start_urgent(carpet)
                    return
        self._urgent_finished()

    def _urgent_finished(self):
        """ActionManager.StopUrgentAction (ActionManager.cs:586-649): a routine
        item that has already fired is skipped, otherwise the interrupted
        action restarts. MarblesNextAction suppresses the skip and clears
        when the marbles urgent itself ends (cs:614, 642-646)."""
        finished = self.urgent_item
        ua, self._urgent_action = self._urgent_action, None
        kind = ua.get('kind') if ua else None
        w = self.pawn.world
        nfh2 = w is not None and w.woody is not None and w.woody.nfh2
        self.urgent_item = None
        self.pawn.in_urgent = False
        # StopUrgentAction's meter release is !NFH2Path-gated (ActionManager.
        # cs:588-591); a use template's stop sets it through OnUseEnded
        # regardless (Rottweiler.cs:879-892)
        if kind == 'use' or not nfh2:
            self.pawn.can_decrease_angry = True
        toilet_continue = False
        if getattr(self, '_toilet_run', False):
            # Rottweiler.OnUseEnded ends the sickness (cs:879-892) and
            # OnActionStopped drops IsUsingToilet (cs:354-357)
            self._toilet_run = False
            self.pawn.feel_sick = False
            self.pawn.is_using_toilet = False
            toilet_continue = bool(self.pawn.toilet_action.get(
                'continue_to_next'))
            it2 = self.item
            if pcprofile.is_pc() and pcprofile.SEASON2:
                # the PC's rush goes on from the wc to its SHOUT (211:
                # 0x10030dc2's puke, then 0x10030d0f on Olga's fight): the
                # rush's own item, whichever action the routine had reached —
                # the mobile reads the interrupted action's (ActionManager.cs:
                # 597), the fishing rod by then, and loses it
                it2 = next((x for x in self.level.items.values()
                            if x.play_angry_after_toilet), it2)
            if it2 is not None and it2.play_angry_after_toilet \
                    and self.pawn.world is not None and not toilet_continue:
                # StopUrgentAction's after-toilet angry (ActionManager.cs:
                # 597-603): the sweets' postponed rage fires now
                it2.play_angry_after_toilet = False
                it2.fix_item_trick = it2.linked_trick_rush_toilet
                it2.angry_without_animations = False
                self.pawn.world.play_angry(self.pawn, it2)
        self._same_zone = False
        self._same_zone_yelled = False
        self._sz_watch = False
        self._alarm_use = False
        self.stop_dog_action = True      # ActionManager.cs:596
        if self.role == 'Mother' and self.pawn.world is not None:
            # StopUrgentAction fires the Mother event (ActionManager.cs:592-595)
            self.pawn.world.fire_event('mother_urgent_stop')
        if toilet_continue:
            # ToiletAction.ContinueToNextAfterFinished (Level102): the urgent
            # clears and AdvanceToNextAction advances the routine normally —
            # StopUrgentAction never runs (ActionManager.cs:530-538, 544-548)
            # — nor does its OriginalAction replay
            self._urgent_stack = []
            self._original_action = None
            self._pending = 'advance'
            self.state = self.IDLE
            self._release_at_urgent_stop(ua, finished)
            return
        if self.frozen:
            # a frozen manager swallows the resume (ActionManager.cs:604-606);
            # the Unfreeze that lifts it starts the routine again
            self._urgent_stack = []
            self._original_action = None
            self.state = self.IDLE
            return
        if self._urgent_stack:
            # StopUrgentAction's StartAction(OriginalAction) (cs:647) replays
            # the urgent this one interrupted (see _stash_interrupted_urgent)
            r = self._urgent_stack.pop()
            ua0 = r['ua']
            self.state = self.IDLE
            if r['toilet']:
                self._toilet_run = True   # the ToiletAction restarts (cs:647)
                if self.pawn.toilet_action.get('is_toilet'):
                    self.pawn.is_using_toilet = True   # RoutineActionUse.cs:201-204
            self.start_urgent(r['item'], arrived=r['arrived'],
                              alarm_use=(ua0.get('kind') == 'use'
                                         and r['arrived'] is None),
                              kind=ua0.get('kind'), name=ua0.get('name'),
                              urgent=r['urgent'],
                              postpone_alarm=ua0.get('postpone_alarm'),
                              postpone_alarm_during_use_only=ua0.get(
                                  'postpone_alarm_during_use_only'))
            self._release_at_urgent_stop(ua, finished)
            return
        if finished is not None and finished.name == 'GroundMarbles':
            self.marbles_next = False
        # the branches read ActiveAction.OriginalAction.Item (cs:607-647):
        # the interrupted action's, wherever the routine's index went
        orig, self._original_action = self._original_action, None
        if os.environ.get('NFH_ROUTINE_LOG'):
            oi = self.level.items.get(orig.get('item')) if orig and orig.get('item') is not None else None
            print('routine %s t=%.1f urgent end kind=%s finished=%s index=%s original=%s got_tricked=%s go_next=%s marbles_next=%s' % (
                self.role, getattr(self.pawn.world, 'time', 0.0), kind, getattr(finished, 'name', None), self.index,
                getattr(oi, 'name', None), getattr(oi, 'got_tricked', None), getattr(oi, 'go_next_action', None), self.marbles_next), file=sys.stderr)
        it = self.level.items.get(orig['item']) \
            if orig is not None and orig.get('item') else self.item
        linked = self.level.items.get(it.linked_item_trick) \
            if it is not None and it.linked_item_trick else None
        replay = False
        if it is not None and it.skip_action:
            # StopUrgentAction's SkipAction arm (ActionManager.cs:608-613):
            # a wiped drawing skips its own redo
            self._pending = 'skip'
        elif it is not None and it.got_tricked and not self.marbles_next and \
                it.name not in ('WateringCan', 'ValveHot', 'ValveMain'):
            # the skip goes straight to StartAction, without the
            # StartNextAction extras (ActionManager.cs:614-619). GotTricked
            # is the sticky "its trick has fired on him" mark (Item.cs:836-
            # 838), not the armed state: the expander and weights Badinfos
            # chains after the marbles and the trap on E12, the shotgun on
            # E14, are unfired at the walk-by (got_tricked False in the
            # port's routine log), so the PC neighbour going back to them
            # is this same rule, not an exception to it; the pudding of
            # Level106, fired at [2], is skipped at [6] after the candy's
            # toilet rush on both profiles (docs/PC_FIDELITY.md §7)
            self._pending = 'skip'
        elif it is not None and it.go_next_action and not self.marbles_next:
            # Item.GoNextAction (ActionManager.cs:620-626)
            it.go_next_action = False
            self._pending = 'skip'
        elif it is not None and linked is not None and linked.tricked \
                and it.name == 'MechanicalBullWait':
            # the bull-wait double skip (ActionManager.cs:627-639)
            if self.actions:
                cur = self.index % len(self.actions)
                if cur >= len(self.actions) - 1 or cur + 2 > len(self.actions) - 1:
                    self.index = 0
                else:
                    self.index = cur + 2
            self._pending = 'start'
        else:
            self._pending = 'start'
            replay = True
        if replay and orig is not None and orig is not self._entry():
            # StartAction(ActiveAction.OriginalAction) (cs:647) restarts the
            # interrupted action itself, not the routine's current entry:
            # Level214's tricked bouquet strips Olga's Glass and BirdPerch
            # and steps her index to the Shower while her HitPawn urgent
            # runs (Item.FishPlantBehavior, Item.cs:2388-2396), and she
            # still walks back to the glass for one more cycle of her pose
            # before AdvanceActionIndex sends her to the shower (bench,
            # Level214 at 323.2-326.2 s of level time)
            self._override = orig
        self.state = self.IDLE
        self._release_at_urgent_stop(ua, finished)

    def _release_at_urgent_stop(self, ua, finished):
        """the parked-run checks each urgent template's OnActionStopped runs
        when the resumed action starts: RoutineActionSurpriseFar's
        CheckPendingAlarm (RoutineActionSurpriseFar.cs:66-71); the use
        templates' CheckSurpriseActionFar + CheckPendingAlarm
        (RoutineActionUse.cs:358-362 — the AlarmAction, the ToiletAction and
        the UseFixingItemAction, whose own check is deferred behind the
        Return leg it queues right after it, RoutineActionUseFixingItem.cs:
        63-73 -> the Return's OriginalAction). Called after `_pending` is
        set so the released run resumes at the chosen action. The stopping
        template is still the CurrentAction the checks read (ActionManager.
        cs:157-170 stop it before replacing it), so IsAlarmPostponed is
        evaluated over it — unless CheckSurpriseActionFar just started the
        alerter run, whose move is what CheckPendingAlarm then sees."""
        if self.role != 'Rottweiler' or ua is None:
            return
        kind = ua.get('kind')
        if kind == 'surprise_far':
            self._check_pending_alarm(self._template_postponed(ua, finished))
        elif kind in ('use', 'return'):
            started = self._check_surprise_far()
            self._check_pending_alarm(
                None if started else self._template_postponed(ua, finished))

    def _check_surprise_far(self):
        """Rottweiler.CheckSurpriseActionFar (Rottweiler.cs:1139-1148): a
        parked alerter/notice run starts now — no gate of its own"""
        if self.pending_surprise is None:
            return False
        it, self.pending_surprise = self.pending_surprise, None
        self.start_urgent(it)             # StartSurpriseActionFar (cs:1150)
        return True

    def _check_pending_alarm(self, postponed=None):
        """Rottweiler.CheckPendingAlarm (Rottweiler.cs:231-240): the parked
        phone alarm starts when nothing postpones it and no door is being
        passed — as MoveToAlarm, i.e. the AlarmAction's full use"""
        if postponed is None:
            postponed = self.is_alarm_postponed()
        if self.pending_alarm is None or postponed or self.pawn.is_warping:
            return False
        it, self.pending_alarm = self.pending_alarm, None
        self.move_to_alarm(it)
        return True

    def move_to_alarm(self, item):
        """Rottweiler.MoveToAlarm (Rottweiler.cs:869-877): the AlarmAction
        urgent — a RoutineActionUse whose arrival answers the phone; the
        CabinPhone hack sets its Urgent flag for good (cs:872-875)"""
        if item.name == 'CabinPhone':
            self._alarm_urgent = True
        tpl = self.pawn.alarm_action
        self.start_urgent(item, alarm_use=True, kind='use', name='alarm',
                          urgent=self._alarm_urgent,
                          postpone_alarm=tpl.get('postpone_alarm'),
                          postpone_alarm_during_use_only=tpl.get(
                              'postpone_alarm_during_use_only'))

    # -- the fixing-tool run (Rottweiler.RunToFixingItem and the Grab /
    #    UseFixingItem / Return action chain) ------------------------------
    def _fixing_dispatch(self, it):
        """Item.RottweilerUse's FixingItem head (Item.cs:847-852): a raw-
        Tricked neutral (or ForceUseFixingItem) item with empty hands starts
        the fetch; True means the use itself must not continue. The urgent
        path reaches it too — the urgent action is a RoutineActionUse, so its
        OnActionStarted also calls Item.Use."""
        w = self.pawn.world
        if w is None or not it.tricked or it.fixing_item is None:
            return False
        if self.pawn.fixing_item is not None:
            return False
        neutral = it.kind in TRICK_KINDS and it.neutral       # Item.IsNeutral
        if not (neutral or it.force_use_fixing_item):
            return False
        tool = self.level.items.get(it.fixing_item)
        if tool is None:
            return False
        it.got_tricked = True                                 # Item.cs:838
        self.run_to_fixing_item(tool, w._tricked_item_to_fix(it))
        return True

    def _pc_tool_pace(self, seq, secs):
        """under the profile a fixing tool's step lasts its PC action's
        seconds — the tool's PCGrabSeconds, PCUseSecondsTricked,
        PCFixUseSeconds or PCReturnSeconds (tools/pcref/pc_reactions.py's
        `tool`: the take, the stand at the target, the use after the repair,
        the give) — the mobile clips at that pace (AnimPlayer.time_scale,
        reset by the step's end)"""
        self.pawn.anim.time_scale = 1.0
        if secs and seq and pcprofile.is_pc() and pcprofile.rule('durations'):
            mobile = self.pawn.anim.sequence_seconds(seq)
            if mobile > 0.0:
                self.pawn.anim.time_scale = mobile / float(secs)

    def run_to_fixing_item(self, tool, tricked):
        """Rottweiler.RunToFixingItem (Rottweiler.cs:1077-1082): shift the
        tricked item's stand spot by DeltaFixLocation, wire the chain, and
        run to the tool as an urgent action."""
        tricked.dx += tricked.delta_fix_x
        tricked.dy += tricked.delta_fix_y
        self._fix_tool = tool
        self._fix_target = tricked
        self._fix_redo = False
        g = self.pawn.grab_action            # the RoutineActionGrab template
        self.start_urgent(tool, arrived=self._grab_arrived, kind='grab',
                          urgent=g.get('urgent'),
                          postpone_alarm=g.get('postpone_alarm'))

    def _grab_arrived(self):
        """RoutineActionGrab.OnActionStarted -> OnSequenceEnded: play the
        GrabSequence, hide the tool, carry it, hop to the tricked item."""
        seq = [x for x in self.pawn.grab_action.get('sequence', [])
               if self.pawn.anim.has(x)]
        self.state = self.USING
        self._pc_tool_pace(seq, getattr(self._fix_tool, 'pc_grab_secs', None))

        def grabbed():
            self.pawn.anim.time_scale = 1.0
            tool = self._fix_tool
            if tool is not None and tool.sprite is not None:
                tool.sprite.hidden = True    # SetActiveObjectHidden(true)
            self.pawn.fixing_item = tool     # Rottweiler.FixingItem = Item
            u = self.pawn.use_fixing_action  # RoutineActionUseFixingItem, a
            self.start_urgent(self._fix_target,  # RoutineActionUse subclass
                              arrived=self._use_fixing_arrived, kind='use',
                              name='use_fixing', urgent=u.get('urgent'),
                              postpone_alarm=u.get('postpone_alarm'))
        if seq:
            self.pawn.anim.play_sequence(seq, on_end=grabbed)
        else:
            grabbed()

    def _use_fixing_arrived(self):
        """RoutineActionUseFixingItem.TryUseFixingItem: a tricked (non-neutral)
        tool fires its own trick first and the action redoes (RedoAction);
        else the target gets CanFix=true, FuckedUp=false, TryFix, and the
        UseFixingItemSequence plays."""
        w = self.pawn.world
        tool = self.pawn.fixing_item
        tgt = self._fix_target
        if w is None or tgt is None:
            self._urgent_finished()
            return
        if tool is not None and tool.tricked and \
                not (tool.kind in TRICK_KINDS and tool.neutral):
            tool.got_tricked = True
            # FixingItem.Use -> RottweilerUse plays the tool's tricked use
            # first (Item.cs:894-908); the angry flow rides its end through
            # StopAction's postpone, and RedoAction then re-enters here
            seq = [x for x in tool.sequence_for('Rottweiler', True,
                                                self.level.items)
                   if self.pawn.anim.has(x)]

            def angry():
                self.pawn.anim.time_scale = 1.0
                self._fix_redo = True      # RedoAction re-enters after the angry
                w.play_angry(self.pawn, tool, on_done=self._use_fixing_arrived)
            self.state = self.USING
            # the PC case's stand at the target (111's vacuum_hole and its
            # explode clip) and the fire before that clip (FIRE5, PCFireAt) —
            # a tool pc_reactions.py maps as one (PCGrabSeconds); another
            # tool's PCUseSecondsTricked is its own station's stand
            pc_tool = tool.pc_grab_secs is not None
            self._pc_tool_pace(seq, tool.pc_use_secs_tricked if pc_tool else None)
            if pcprofile.is_pc() and pc_tool and tool.pc_fire_at is not None \
                    and not tool.pc_fired:
                if float(tool.pc_fire_at) > 0.0:
                    self.pc_fire_at = float(tool.pc_fire_at)
                    self.pc_fire_item = tool
                else:
                    w.s1_fire(self.pawn, tool)
            if seq:
                self.pawn.anim.play_sequence(seq, on_end=angry)
            else:
                angry()
            return
        tgt.can_fix = True
        tgt.fucked_up = False
        w._try_fix(tgt)
        seq = [x for x in self.pawn.use_fixing_action.get('sequence', [])
               if self.pawn.anim.has(x)]
        self.state = self.USING
        # the PC case's use at the target: after the tricked branch's repair
        # the actions that follow it (111's vacuum2; 110's case has none —
        # PCFixUseSeconds 0 drops the clip), of a sound tool the normal
        # branch's action (the vacuum, the extinguish; 113's valves have
        # none past the switch — PCToolUseSeconds 0)
        redo = getattr(self, '_fix_redo', False)
        self._fix_redo = False
        secs = None
        if tool is not None and tool.pc_grab_secs is not None and pcprofile.is_pc():
            secs = tool.pc_fix_use_secs if redo else tool.pc_tool_use_secs
            if secs is not None and float(secs) == 0.0:
                seq = []
        self._pc_tool_pace(seq, secs)

        def used():
            self.pawn.anim.time_scale = 1.0
            self._fixing_done()
        if seq:
            self.pawn.anim.play_sequence(seq, on_end=used)
        else:
            used()

    def _fixing_done(self):
        """RoutineActionUseFixingItem.StopAction clears Rottweiler.FixingItem;
        OnActionStopped starts the Return urgent when ShouldReturnFixingItem
        (its Item is pre-serialized to the tool)."""
        self.pawn.fixing_item = None
        tool = self._fix_tool
        if pcprofile.is_pc() and tool is not None and tool.pc_grab_secs is not None \
                and tool.pc_return_secs is not None and float(tool.pc_return_secs) == 0.0:
            # the PC case keeps the tool (110's case 9 takes the extinguisher
            # and gives nothing back): no walk back, the tool stays taken
            self._fix_tool = self._fix_target = None
            self._urgent_finished()
            return
        if self.pawn.use_fixing_action.get('should_return') \
                and self._fix_tool is not None:
            # RoutineActionReturn: its Urgent is never serialized — a walk
            self.start_urgent(self._fix_tool, arrived=self._return_arrived,
                              kind='return', urgent=self.pawn.use_fixing_action
                              .get('return_urgent'))
        else:
            self._fix_tool = self._fix_target = None
            self._urgent_finished()

    def _return_arrived(self):
        """RoutineActionReturn: the ReturnSequence, then the tool reappears
        (SetObjectHidden(false)) and the routine resumes."""
        seq = [x for x in self.pawn.use_fixing_action.get('return_sequence', [])
               if self.pawn.anim.has(x)]
        self.state = self.USING
        self._pc_tool_pace(seq, getattr(self._fix_tool, 'pc_return_secs', None))

        def returned():
            self.pawn.anim.time_scale = 1.0
            tool = self._fix_tool
            if tool is not None and tool.sprite is not None:
                tool.sprite.hidden = False
            self._fix_tool = self._fix_target = None
            self._urgent_finished()
        if seq:
            self.pawn.anim.play_sequence(seq, on_end=returned)
        else:
            returned()

    def hear_alerter(self, alerter_item, triggered_by_woody):
        """Rottweiler.HearAlerter (Rottweiler.cs:265-301)"""
        if self.moving_to_alarm():
            return
        postponed = self.is_alarm_postponed()
        if postponed and self.state == self.MOVING:
            # cs:272's exception for a tricked current item dereferences
            # ActionManager.CurrentAction.Item — the interposed MoveAction's,
            # which nothing ever sets (ActionManager.cs:23): the original
            # throws out of Alerter.CoRoutineRottweilerHearAlerter
            # (Alerter.cs:116-120) and this bark is lost — neither started
            # nor parked
            return
        # the CurrentAction's item: the urgent template's or the routine's
        cur = self.urgent_item if self._urgent_action is not None else self.item
        if not self._passing_or_portal() and \
                (not postponed or (cur is not None and cur.tricked)):
            if self.pawn.alarm_postponed:
                # Rottweiler.cs:274-278: a PostponeAlarm (SurpriseNear,
                # WaitInFear, a behavior) parks it — PostponeAlerterAction
                self.pending_surprise = alerter_item
                return
            if self.state == self.MOVING:
                self.start_urgent(alerter_item)
                return
            if cur is not None and cur.name != 'Bed':   # cs:285-289
                self.was_alerted = alerter_item     # consumed when he moves
            if self.pawn.animal_tutorial:
                # Intro103's frozen tutorial neighbour: Unfreeze and run
                # (Rottweiler.cs:290-295; CheckHiddenItem is a no-op here,
                # HideObjectDuringUse being unported)
                self.frozen = False
                self.start_urgent(alerter_item)
        else:
            self.pending_surprise = alerter_item    # PostponeAlerterAction

    def _update_walking(self):
        """Rottweiler.UpdateWalking (Rottweiler.cs:833-849): a tricked
        NoticeWhenWalkNearby item within NoticeWhenNearTrickedDistance slips
        (CauseSlip -> FallAction) or startles (SurpriseActionNear) — both are
        RoutineActionSurpriseNear instances. WalkOnPath calls it on every
        walk (Pawn.cs:981) — an urgent run included: the near surprise then
        interrupts the run and StartUrgentAction chains the run as its
        OriginalAction (ActionManager.cs:715-718), replayed at its end —
        Level102's toilet rush passes the tricked toilet on the way. No
        break: every item in range fires, the last one standing."""
        w = self.pawn.world
        if w is None or self.pawn.zone is None:
            return
        for it in list(w.near_items.get(self.pawn.zone.pid, ())):
            if it.tricked and \
                    abs(self.pawn.sprite.x - it.target_x) \
                    < self.pawn.notice_near_distance:
                self._on_surprise_near(it)

    def _on_surprise_near(self, it):
        """Rottweiler.OnSurpriseNear / OnFall -> StartUrgentAction ->
        RoutineActionSurpriseNear.OnActionStarted (cs:12-37): pause, postpone
        the alarm, and the facing-matched surprise sequence shifted by
        SurpriseDeltaLocation."""
        if self._urgent_action is not None:
            # the run it lands on becomes its OriginalAction (cs:679-718) —
            # unless that is a SurpriseNear itself (cs:681-691)
            self._stash_interrupted_urgent('surprise_near')
        if self._urgent_action is None:
            self._original_action = self.action   # cs:715-718
        if os.environ.get('NFH_ROUTINE_LOG'):
            nm = lambda e: self.level.items.get(e['item']).name if e and e.get('item') is not None and self.level.items.get(e['item']) else None
            print('routine %s t=%.1f surprise_near item=%s index=%s action=%s active=%s override=%s original=%s running=%s' % (
                self.role, getattr(self.pawn.world, 'time', 0.0), it.name, self.index, nm(self.action), nm(self._active),
                nm(self._override), nm(self._original_action), (self._urgent_action or {}).get('kind')), file=sys.stderr)
        self.urgent_item = it
        self._urgent_handler = None
        self.pc_hold = 0.0                    # a held station yields to the surprise
        self.pc_fire_at = 0.0; self.pc_fire_item = None
        self.pc_credit_timer = 0.0; self.pc_credit_item = None
        self.pc_credit2_timer = 0.0; self.pc_credit2_item = None
        self.pc_credit3_timer = 0.0; self.pc_credit3_item = None
        self.pawn.anim.time_scale = 1.0
        w = self.pawn.world
        if pcprofile.is_pc() and w is not None and it.tricked \
                and getattr(it, 'pc_fire_before', False) and not it.pc_fired:
            # the soap and marbles slips: game.exe's five-argument step
            # scores first and plays the fall inside it (PCFireBefore)
            w.s1_fire(self.pawn, it)
        # a RoutineActionSurpriseNear is current: IsAlarmPostponed's first
        # arm (Rottweiler.cs:1049-1052)
        self._urgent_action = {'kind': 'surprise_near'}
        self.pawn.steps = []
        self.pawn.state = self.pawn.IDLE
        self.pawn.movement_paused = True      # Owner.PauseMovement
        self.postpone_alarm()                 # Owner.PostponeAlarm
        seq = it.surprise_right if self.pawn.facing == 'Right' \
            else it.surprise_left             # Owner.IsMovingRight
        self.pawn.sprite.x += it.surprise_delta[0]
        self.pawn.sprite.y += it.surprise_delta[1]
        self.pawn.pos_snap = True
        self.state = self.USING
        seq = [a for a in seq if self.pawn.anim.has(a)]
        if seq:
            pc = (getattr(it, 'pc_slip_secs', None) or getattr(it, 'pc_surprise_secs', None)) \
                if pcprofile.is_pc() else None
            if pc:
                # the PC fall (slip1/slip3, 31 frames) or doubletake3 (15):
                # the mobile clip at the pace that lasts it
                mobile = self.pawn.anim.sequence_seconds(seq)
                if mobile > 0.0:
                    self.pawn.anim.time_scale = mobile / pc
            self.pawn.anim.play_sequence(seq, on_end=self._surprise_near_done)
        else:
            self._surprise_near_done()

    def _surprise_near_done(self):
        """the drain reaches StopAction(canPostponeStop: true): a tricked
        item goes angry first (RoutineActionSurpriseNear.cs:47-57)"""
        self.pawn.anim.time_scale = 1.0       # the paced fall or doubletake is over
        it = self.urgent_item
        if it is not None and it.tricked and self.pawn.world is not None:
            self.pawn.world.play_angry(self.pawn, it,
                                       on_done=self._surprise_near_stopped)
        else:
            self._surprise_near_stopped()

    def _surprise_near_stopped(self):
        """OnActionStopped (cs:39-45): ContinueMovement, ContinueAlarm and
        the pending-alarm check. StopUrgentAction picks the resume first —
        OnActionStopped fires from inside StartAction(next) (ActionManager.
        cs:157-160) — so a released run interrupts that action; here the
        resume is chosen (`_pending`) before the checks for the same reason.
        The pending-alarm gate reads the stopping SurpriseNear (postponed,
        cs:1049) — the alarm stays parked unless ContinueAlarm's released
        alerter run is what it sees (cs:1053-1060: not postponed)."""
        self.pawn.movement_paused = False
        ua = self._urgent_action
        self._urgent_finished()
        started = self.continue_alarm()
        self._check_pending_alarm(None if started else
                                  self._template_postponed(ua or {}, None))

    def run_to_hit_pawn(self, target_pawn):
        """Pawn.RunToHitPawn (Pawn.cs:1837-1841) -> StartUrgentAction(
        HitPawnAction): walk into the target's zone within
        MaximumPawnDistanceToAction, then the hit choreography
        (RoutineActionHitPawn.cs:13-45)."""
        if self.frozen:
            return
        # a use still running (no advance queued by its end) is the active
        # action StartAction stops below; a queued advance means it ended
        in_use = self.state == self.USING and self._pending is None \
            and self.action is not None
        if self._pending in ('advance', 'skip'):
            self._advance()
        self._pending = None
        self._hit_target = target_pawn
        if self._urgent_action is None:
            self._original_action = self.action   # cs:715-718
        # StartUrgentAction -> StartAction stops the active action first
        # (ActionManager.cs:157-160, through MoveToAction's StartAction
        # (MoveAction) in the far case too): a use in progress runs its
        # OnActionStopped, whose HideOwnerDuringUse unhides the owner
        # (RoutineActionUse.cs:481-484 — outside the !MutexAction block,
        # which closes at cs:363). A Hidden controller never refreshes
        # (AnimationControllerBase.OnGUI), so Olga parked hidden on her
        # Level205 table-tennis mutex must be shown for her HitPawnSequence
        # to run out: without the stop the port's hit never ended and the
        # neighbour waited in fear for the rest of the level (the sofa-
        # first-style reverse plan of Level205; the standard plan tricks
        # the table last and never saw it).
        if in_use:
            self._action_stopped()
        self.urgent_item = None
        self._urgent_action = {'kind': 'hit_pawn'}
        self.pawn.steps = []
        # HitPawnAction.Urgent picks the run (RoutineActionMove.cs:72-75):
        # Olga's is serialized true, the Mother's only on Level210
        self.pawn.in_urgent = bool(self.pawn.hit_pawn_action.get('urgent'))
        # the PC runs it where the co-actor's script sets her gait to 2
        # before the walk to him (the trick item's PCRunTo, World.play_angry);
        # her other walks to him the PC walks
        self.pawn.pc_run = bool(self.pawn.pc_run_hit) and pcprofile.is_pc()
        self.state = self.MOVING
        maxd = self.pawn.hit_pawn_action.get('max_distance') or 0.03
        if self.pawn.zone is target_pawn.zone and \
                abs(self.pawn.sprite.x - target_pawn.sprite.x) < maxd:
            self._hit_pawn_arrived()
        elif target_pawn.zone is None or not self.pawn.goto_zone(
                target_pawn.zone, target_pawn.sprite.x,
                on_arrive=self._hit_pawn_arrived):
            self._hit_pawn_arrived()
        elif self.pawn.world is not None:
            # the move ends by distance inside the target's zone
            # (RoutineActionHitPawn.IsAtActionLocation, cs:13-18, read by
            # RoutineActionMove.Finished every frame)
            self.pawn.world._hit_watches.append(
                (self.pawn, target_pawn, maxd, True, self._hit_pawn_arrived))

    def _hit_pawn_arrived(self):
        """RoutineActionHitPawn.OnActionStarted (cs:20-38): the target —
        the neighbour being hit — hides (the hit sheets contain him), the
        owner's current item can reveal itself, and the HitPawnSequence
        plays. The Olga toilet-delay arm rides the unported Bouquet hack."""
        target = getattr(self, '_hit_target', None)
        w = self.pawn.world
        if w is not None:
            w._hit_watches = [x for x in w._hit_watches
                              if x[4] != self._hit_pawn_arrived]
        if target is None or w is None:
            self._urgent_finished()
            return
        # (the PC fights on arrival: fcn.1000eb19 queues the `fight` once
        # fcn.1000e601 has her at him, and the job starts on her queue's
        # next run with no look at his — the job queue fcn.100492a8 locks
        # no other actor; _hit_begin)
        self._hit_begin()

    def _hit_begin(self):
        """the hit's start: RoutineActionHitPawn.OnActionStarted's body"""
        target = getattr(self, '_hit_target', None)
        w = self.pawn.world
        if target is None or w is None:
            self._urgent_finished()
            return
        # Target.AnimController.Hidden — the PC's `fight` alike: its job
        # sets the neighbour `inv` in its state 0 and `ms2` in its state 2
        # (generic objects.xml: objanim / objnextanim on him, 0x10002301-
        # 0x100024e9), and posts olga_fight / mother_fight as it ends
        # (fcn.1004000a, 0x10002708), on which his step's SHOUT goes on
        target.sprite.hidden = True
        oit = self.item
        if oit is not None and oit.show_item_when_affected:
            w.set_object_hidden(oit, False)    # cs:32-36
        seq = [x for x in self.pawn.hit_pawn_action.get('sequence', ())
               if self.pawn.anim.has(x)]
        self.state = self.USING
        if seq:
            pc = getattr(self.pawn, 'pc_hit_secs', None)
            if pc:
                # the PC's hit lasts its action's ticks (the co-actor's
                # generic `fight`, fcn.1000eb19; 207's lift, 0x1001513f)
                mobile = self.pawn.anim.sequence_seconds(seq)
                if mobile > 0.0:
                    self.pawn.anim.time_scale = mobile / pc
            self.pawn.anim.play_sequence(seq, on_end=self._hit_pawn_done)
        else:
            self._hit_pawn_done()

    def _hit_pawn_done(self):
        """RoutineActionHitPawn.OnActionStopped (cs:40-45): the target
        reappears and its parked angry resumes"""
        target, self._hit_target = getattr(self, '_hit_target', None), None
        w = self.pawn.world
        if getattr(self.pawn, 'pc_hit_secs', None):
            self.pawn.anim.time_scale = 1.0
            self.pawn.pc_hit_secs = None
        if target is not None:
            target.sprite.hidden = False
            if w is not None:
                w.continue_angry_animation(target)   # Target.ContinueAngryAnimation
        self._urgent_finished()

    def move_to_toilet(self, feel_sick):
        """Rottweiler.MoveToToilet (Rottweiler.cs:863-867) +
        ActionManager.StartToiletAction: the sick run to the serialized
        ToiletAction item; the use end clears the flags
        (Rottweiler.OnUseEnded cs:879-892, OnActionStopped cs:354-357)."""
        pid = self.pawn.toilet_action.get('item')
        it = self.level.items.get(pid) if pid else None
        if it is None:
            return
        self.pawn.feel_sick = feel_sick   # Pawn.MoveToToilet
        if self.pawn.toilet_action.get('is_toilet'):
            self.pawn.is_using_toilet = True
        self._toilet_run = True
        t = self.pawn.toilet_action       # the RoutineActionUse template:
        self.start_urgent(it, alarm_use=True, kind='use',   # Urgent=true
                          name='toilet',                    # everywhere
                          urgent=t.get('urgent'),
                          postpone_alarm=t.get('postpone_alarm'),
                          postpone_alarm_during_use_only=t.get(
                              'postpone_alarm_during_use_only'))

    def postpone_alarm(self):
        """Rottweiler.PostponeAlarm (Rottweiler.cs:1126-1130)"""
        self.pawn.alarm_postponed = True

    def continue_alarm(self):
        """Rottweiler.ContinueAlarm (Rottweiler.cs:1132-1137): drop the
        postpone and fire the parked alerter run (CheckSurpriseActionFar); a
        frozen manager keeps it parked until the Unfreeze"""
        self.pawn.alarm_postponed = False
        if self.frozen:
            return False
        return self._check_surprise_far()

    def on_zone_changed(self):
        """Rottweiler.OnChangeZone: tricked noticing items, pending alarms,
        and calming the alerter he was called by. Returns True when it took
        over the pawn — OnChangeZone's own return value."""
        w = self.pawn.world
        for it in w.notice_items.get(self.pawn.zone.pid, ()):
            # the DirtyCarpet is excluded from the generic run
            # (Rottweiler.cs:188) — its urgent rides the Dog/Chili yell
            # choreography instead (_yell_done). The PC data has the carpet
            # as a room trigger (level_laundry/trigger.xml: object
            # lir/dirtycarpet, position "room", type "always"): the
            # neighbour goes for the vacuum on entering the room, which is
            # how Badinfos' E11 pays the vacuum 30 s after the marbles and
            # the ironing board 22 s later — the profile keeps the trigger
            if it.name == 'DirtyCarpet' and not pcprofile.is_pc():
                continue
            if it.tricked:
                # RunToTrickedItem: PauseMovement + a startled look, then the
                # urgent run (consumed in OnSingleAnimationEnded)
                self.pawn.steps = []
                self.pawn.state = self.pawn.IDLE
                if it.name == 'DirtyCarpet' and pcprofile.is_pc():
                    # the PC's room trigger runs Level_Laundry's cases 20-22
                    # at once: the variant test, the vacuum icon and the walk
                    # to the vacuum (game.exe 0x45647f-0x456561) — no look
                    self.start_urgent(it)
                    return True
                startle = it.surprise_far_left if self.pawn.facing == 'Right' \
                    else it.surprise_far_right
                if startle and self.pawn.anim.has(startle):
                    # RunToTrickedItem is a PlaySingleAnimation, not a
                    # sequence (Rottweiler.cs:329-342)
                    self.pawn.anim.play_sequence(
                        [startle], on_end=lambda i=it: self.start_urgent(i),
                        as_sequence=False)
                else:
                    self.start_urgent(it)
                return True
        # cs:194-201: the parked alerter run behind CanCheckSurpriseActionFar,
        # then the parked phone alarm behind its own gate
        if self._can_check_surprise_far() and self._check_surprise_far():
            return True
        if self._check_pending_alarm():
            return True
        if self.moving_to_alarm() and self.urgent_item.zone == self.pawn.zone.pid:
            fsm = w.alerters.get(self.urgent_item.pid)
            if fsm is not None:
                fsm.on_rottweiler_enter()
        return False

    def _can_check_surprise_far(self):
        """Rottweiler.CanCheckSurpriseActionFar (Rottweiler.cs:209-229): the
        fixing-tool chain with PostponeAlarm blocks it, then the primary
        behavior gets its veto."""
        # IsFixingBlockingItem (cs:218-229): a Grab or UseFixingItem step —
        # or the walk toward one — whose PostponeAlarm is set (the Return
        # leg does not block)
        ua = self._urgent_action or {}
        if self._fix_tool is not None and ua.get('kind') in ('grab', 'use') \
                and ua.get('postpone_alarm'):
            return False
        if self.pawn.behaviors:
            return self.pawn.behaviors[0].can_check_surprise_action_far()
        return True

    def tick(self, dt):
        # the 1.5 s DelayStart before the first action (Rottweiler.cs:153,
        # 916-932; Mother.cs:18, Olga.cs:8) — the intro gate (CanStart) is
        # immediate here since the title cards are not modelled. It counts
        # on the pawn, not the manager: a routine that ships Frozen (L201's
        # LevelScript holds the neighbour until its action 2) has spent it
        # long before the unfreeze, and StartFirstAction under Frozen is a
        # no-op (ActionManager.cs:106) — the Unfreeze's StartNextAction is
        # what starts him, at once
        if self.delay_start > 0.0:
            self.delay_start -= dt
            if self.delay_start > 0.0:
                return
        if self.frozen:
            return
        # ActionManager.OlgaActions (ActionManager.cs:501-509): the one-shot
        # OlgaWCUse infinite release
        w = self.pawn.world
        olga = w.pawns.get('Olga') if w is not None else None
        if w is not None and olga is not None and not w.flag_aux \
                and self.index > 0 and self.actions \
                and olga.anim.anim.name == 'OlgaWCUse':
            w.flag_aux = True
            olga.anim.anim.infinite = False
            self.anim_aux = olga.anim.anim
        # Rottweiler.Update: a deferred alert fires once he moves again
        if self.was_alerted is not None and self.state == self.MOVING:
            it, self.was_alerted = self.was_alerted, None
            self.start_urgent(it)
            return
        # Rottweiler.Update (Rottweiler.cs:897-901): an AlarmNextAction gate
        # re-checks the pending alarm when the routine advances
        if self.action_changed and self.alarm_next_action:
            self.action_changed = False
            if self._check_pending_alarm():
                return
        # ActionManager.Update itself (cs:421-499) — dead while the null
        # RottLastDoor exception fires at cs:444 (see _same_zone_check)
        if self._manager_dead:
            return
        # the urgent MoveAction toward a Dog/Chili asks SameZone() first
        # (ActionManager.cs:442-448)
        if self._sz_watch and self.state == self.MOVING \
                and self.urgent_item is not None and not self._same_zone:
            self._same_zone_check()
            if self._manager_dead:
                return
        # the SameZone run's proximity yell (ActionManager.cs:459-481):
        # closing within 0.05 of the target stops the walk and plays the
        # surprise-left set once
        if self._same_zone and self.state == self.MOVING \
                and self.urgent_item is not None and not self._same_zone_yelled:
            if abs(self.pawn.sprite.x
                   - self.urgent_item.move_x(self.role)) < 0.05:
                self._same_zone_yell()
                return
        if self._pending:
            what, self._pending = self._pending, None
            if what == 'advance':
                # FreezeAfterCompletion parks the manager instead of
                # advancing (ActionManager.cs:539-543)
                cur = self.action
                if cur is not None and cur.get('freeze_after_completion'):
                    self.frozen = True
                    self.freeze_neighbour = True   # ActionManager.cs:541
                    self.state = self.IDLE
                    return
            if what in ('advance', 'skip'):
                self._advance()
            # 'first' and 'advance' are StartNextAction; 'skip' and 'start'
            # go straight to StartAction (ActionManager.cs:608-648)
            self._start_action(start_next=what in ('first', 'advance'))
            return
        if self.state == self.USING and self.pc_mutex_left is not None:
            self.pc_mutex_left -= dt
            if self.pc_mutex_left <= 1e-9:
                # the timed mutex ends as an abort would (_abort_parked_mutex)
                self._action_stopped()
                self._pending = 'advance'
            return
        if self.state == self.USING and self._pc_wait is not None:
            self._pc_wait_tick(dt)
        if self.state == self.USING and self._pc_credit is not None:
            # the credit clip has played and the next one started: the PC's
            # trick action has ended — its record pays now (fcn.1000140b at
            # the action step's end), the reaction still waits for the use
            cur = self.pawn.anim.anim.name if self.pawn.anim.anim is not None else None
            if cur == self._pc_credit['clip']:
                self._pc_credit['seen'] = True
            elif self._pc_credit['seen']:
                self._pc_credit = None
                w = self.pawn.world
                if w is not None and self.item is not None:
                    w.pc_s2_credit(self.pawn, self.item)
        if self.state == self.USING and self.pc_credit_timer > 0.0:
            self.pc_credit_timer -= dt
            if self.pc_credit_timer <= 0.0:
                self.pc_credit_timer = 0.0
                it, self.pc_credit_item = self.pc_credit_item, None
                w = self.pawn.world
                if it is not None and w is not None and not it.pc_credited:
                    w.pc_s2_credit(self.pawn, it)
        if self.state == self.USING and self.pc_credit2_timer > 0.0:
            self.pc_credit2_timer -= dt
            if self.pc_credit2_timer <= 0.0:
                self.pc_credit2_timer = 0.0
                it, self.pc_credit2_item = self.pc_credit2_item, None
                w = self.pawn.world
                if it is not None and w is not None:
                    w.pc_s2_linked_credit(self.pawn, it)
        if self.state == self.USING and self.pc_credit3_timer > 0.0:
            self.pc_credit3_timer -= dt
            if self.pc_credit3_timer <= 0.0:
                self.pc_credit3_timer = 0.0
                it, self.pc_credit3_item = self.pc_credit3_item, None
                w = self.pawn.world
                if it is not None and w is not None:
                    w.pc_s2_extra_credit(self.pawn, it)
        if self.state == self.USING and self.pc_fire_at > 0.0:
            # the PC's five-argument step fires so many seconds into the
            # tricked use, before the trick's own clip (PCFireAt,
            # docs/PC_ROUTINES.md "The fire's tail"); the paced use makes
            # the PC seconds wall seconds
            self.pc_fire_at -= dt
            if self.pc_fire_at <= 0.0:
                self.pc_fire_at = 0.0
                it, self.pc_fire_item = self.pc_fire_item, None
                w = self.pawn.world
                if it is not None and w is not None and not it.pc_fired:
                    w.s1_fire(self.pawn, it)
        if self.state == self.USING and self.pc_hold > 0.0:
            self.pc_hold -= dt
            if self.pc_hold <= 0.0:
                self.pc_hold = 0.0
                self.pc_fire_at = 0.0; self.pc_fire_item = None
                self.pc_credit_timer = 0.0; self.pc_credit_item = None
                self.pc_credit2_timer = 0.0; self.pc_credit2_item = None
                self.pc_credit3_timer = 0.0; self.pc_credit3_item = None
                cb, self.pc_hold_cb = self.pc_hold_cb, None
                if cb is not None:
                    cb()
                else:
                    self._finish()        # the held empty sequence completes
            return
        if self.state == self.USING and self.timer > 0.0:
            self.timer -= dt
            if self.timer <= 0.0:
                # a Duration that runs out only marks the action Finished
                # (RoutineAction.cs:91-98); AdvanceToNextAction follows and
                # the next start runs OnActionStopped alone (ActionManager.
                # cs:157-160) — no StopAction(bool) body, no angry postpone.
                # Data: L110 action 1 (Duration 1.0), whose TakeGround drains
                # in 4/7 s first, so this branch stays latent
                self._action_stopped()
                self._pending = 'advance'
                self._check_parked_runs()


def _dex_surprise(world, rt, item):
    """SurpriseActionFar.Item = alerter; CheckHiddenItem;
    StartSurpriseActionFar (DexterityComponent.cs:416-421). CheckHiddenItem
    un-hides the routine item a HideObjectDuringUse action tucked away
    (Rottweiler.cs)."""
    a = rt.action
    if a is not None and a.get('hide_object') and rt.item is not None:
        world.set_active_object_hidden(rt.item, False)
    if pcprofile.is_pc() and getattr(item, 'pc_minigame_ticks', None):
        # the PC's game lost: its object's `failed` action sends the
        # neighbour's `run` behaviour (GameLogic's registry fcn.1003ef32:
        # `run`, the UTF-16 string at 0x100b21c4, -> 0x1003e278; its step
        # 0x1003dec1, vtable 0x100b0f7c) — the alarm sound, a running GoTo
        # to the object (fcn.100080e1) and `search` there
        rt.pc_run_next = True
    rt.start_urgent(item)
    rt.pc_run_next = False               # a frozen manager never took it


class DexterityState:
    """One DexterityComponent (DexterityComponent.cs): the lockpick minigame.
    A wandering cursor must be held inside the field; the fill drains outside
    it and losing wakes the Rottweiler onto the item."""

    def __init__(self, world, spec):
        self.world = world
        self.spec = spec
        self.item = world.level.items.get(spec['item'])
        self.enabled = False             # Behaviour.enabled — armed by CanWoodyUse
        self.percent = 0.0               # PercentageDone
        self.first_time = False          # FirstTimeOnly
        self.fill_speed = 1.0
        self.rott_in_animation = False   # RottInAnimation
        self.start_again = False         # StartDexterityAgain
        self.update_aux = True
        self.wrong = False               # BackgroundTexture == Wrong
        self.fg = [0.0, 0.0, 0.0, 0.0]   # ForegroundRect (x, y, w, h) px
        self.bg = [0.0, 0.0, 0.0, 0.0]
        self.item_rect = [0.0, 0.0, 0.0, 0.0]
        self.rand_vec = [0.0, 0.0]       # UpdateMovementRandomVector
        self.last_rand_time = 0.0
        self.input = (0.0, 0.0)          # the frame's touch/mouse delta
        # the PC's game (tools/pcref/pc_minigames.py): the action's `time`,
        # its elapsed count, the level tick's accumulator, the game's own
        # tick count (+0x20), its rate (+0x18), the 10 % latch (+0x50), its
        # progress (+0x1c), the wobble's three phases (+0x28..+0x38), the
        # frame's mouse motion in screen px (the PC's thumb is the mouse
        # itself), the mouse, the field's middle (the level's point and its
        # screen px), the port's screen px to the PC's px and the pair the
        # last state message carried (the drawn thumb)
        self.pc_total = 0
        self.pc_elapsed = 0
        self.pc_acc = 0.0
        self.pc_ticks = 0
        self.pc_rate = 0
        self.pc_latch = False
        self.pc_progress = 0
        self.pc_phase = [0.0, 0.0, 0.0]
        self.pc_move = (0.0, 0.0)
        self.pc_mouse = [0.0, 0.0]
        self.pc_mid = None
        self.pc_mid_px = (0.0, 0.0)
        self.pc_k = 1.0
        self.pc_thumb = (0, 0)
        # a lost game's behaviour on its way: [seconds to the level tick
        # that offers it, its actor] (pc_offer_tick)
        self.pc_offer = None

    def start(self):
        """StartDexterity (DexterityComponent.cs:137-177)"""
        import random
        w = self.world
        self.enabled = True
        w.is_dexterity_on = True
        self.percent = 20.0
        ticks = getattr(self.item, 'pc_minigame_ticks', None) if pcprofile.is_pc() else None
        self.pc_total = int(ticks) if ticks else 0
        self.pc_elapsed = 0
        self.pc_acc = 0.0
        self.pc_ticks = 0
        self.pc_rate = 0
        self.pc_latch = False
        self.pc_progress = 0
        self.pc_move = (0.0, 0.0)
        if self.pc_total:
            self.percent = 0.0
        self.first_time = False
        self.wrong = False
        self._rng = random.Random(random.random())   # seeded from the run's random state (tests/run_tricks.py)
        if self.pc_total:
            # the constructor (fcn.100507f4) starts each wobble phase at
            # rand(8) quarter turns of its GetTickCount generator
            self.pc_phase = [self._rng.randrange(8) * pcprofile.S2_GAME_QUARTER
                             for _ in range(3)]
            # the field's middle: Woody's `minigame` hotspot, in the level's
            # px (y down) from his point (fcn.10049e01;
            # pcprofile.S2_GAME_HOTSPOT) — the object's `woody` hotspot the
            # use put him on, PCMinigameLift px above the room's floor line,
            # where the port keeps his point on its walking line and the
            # remaster's clip draws him from it (204's dispenser: 24 px up,
            # GetToyMachineDexterity's frame raised by its offset)
            hx, hy = pcprofile.S2_GAME_HOTSPOT
            lift = getattr(self.item, 'pc_minigame_lift', None) or 0
            self.pc_mid = (w.woody.sprite.x + hx / pcprofile.PX_PER_UNIT,
                           w.woody.floor_y() + (lift - hy) / pcprofile.PX_PER_UNIT) \
                if w.woody is not None else None
        else:
            self.pc_mid = None
        if w.snap_camera is not None:
            # SnapToWoodyImmediate (cs:149); the PC's scroll holds the field's
            # middle there (GFXEngine 0x1000ab08-0x1000ab7e, dexterity_focus)
            if self.pc_mid is not None:
                w.snap_camera(self.pc_mid)
            else:
                w.snap_camera()
        W, H = w.screen_size
        sx, sy = w.screen_point(self.spec['x'], self.spec['y'])
        fa = self.spec['fg_aux']; ba = self.spec['bg_aux']
        ia = self.spec['item_aux']
        # the original divides in int (Screen.height * 190 / 800 etc,
        # DexterityComponent.cs:158-169) — 600*190/800 is 142, not 142.5
        fh = H * 80 // 800; fw = W * 80 // 1280
        self.fg = [sx - fw / 1.2 + fa.get('x', 0.0),
                   sy - fh * 2.5 + fa.get('y', 0.0), fw, fh]
        bh = H * 190 // 800; bw = W * 190 // 1280
        self.bg = [sx - bw / 1.5 + ba.get('x', 0.0),
                   sy - (bh + bh / 3.0) + ba.get('y', 0.0), bw, bh]
        if self.pc_mid is not None:
            # the PC's field is drawn round its middle at its textures' own
            # sizes (hud._draw_pc_game); its px are the level's, 1/96 unit
            # (pcprofile.PX_PER_UNIT), so a PC px is the camera's screen px
            # a unit over it; the mouse starts on the middle (0x1000ab81-
            # 0x1000abb8: the middle's screen point to the scene's +8,
            # slot 0x48)
            mx, my = self.pc_mid
            cx, cy = w.screen_point(mx, my)
            self.pc_k = (cy - w.screen_point(mx, my + 1.0)[1]) / pcprofile.PX_PER_UNIT
            self.pc_mid_px = (cx, cy)
            self.pc_mouse = [cx, cy]
            self.pc_thumb = (0, 0)
        ih = H * 80 // 800; iw = W * 80 // 1280
        self.item_rect = [sx - iw / 1.2 + ia.get('x', 0.0),
                          sy - ih * 2.5 + ia.get('y', 0.0), iw, ih]
        if w.woody is not None:
            w.woody.freeze()                  # Woody.Freeze
            w.woody.movement_paused = True
        if self.spec['hide_object'] and self.item is not None:
            w.set_object_hidden(self.item, True)
        if self.pc_total:
            # the game is made in Woody's job pass of a level tick (the
            # use_object step, fcn.10041735: [level+0xc]) and has its first
            # update at the end of that tick (0x1004482b); the action step
            # made with it only sets up on its first run (0x100020c0, state
            # 0 -> 1)
            self._pc_update()

    def tick(self, dt):
        """FixedUpdate (DexterityComponent.cs:183-271), the running branch"""
        if not self.enabled:
            return
        w = self.world
        if self.start_again:
            self.start_again = False
            self.start()
        if self.update_aux and (w.can_mother_see_woody()
                                or w.can_rottweiler_see_woody()):
            self.update_aux = False
            self.cleanup()
            self.start_again = True
            return
        if self.pc_total:
            # the PC's thumb is the mouse (fcn.100508a1 reads it each level
            # tick): the frame's motion moves it one to one, with neither the
            # remaster's drift nor its margins
            mx, my = self.pc_move
            self.pc_move = (0.0, 0.0)
            self.input = (0.0, 0.0)
            self.pc_mouse[0] += mx
            self.pc_mouse[1] += my
            self._pc_tick(dt)
            return
        dx, dy = self.input
        self.input = (0.0, 0.0)
        rx, ry = self._random_move()
        if not self.first_time:
            self.first_time = True
        elif self._check_margins():
            self.fg[0] += (dx + rx) * dt
            self.fg[1] -= (dy + ry) * dt
            self.fill_speed = 1.0         # cs:243: unconditional, so the
                                          # margin boost never survives
        W, H = w.screen_size
        ratio_x = 1280.0 / W
        ratio_y = 800.0 / H
        w1 = abs(self.fg[0] + self.fg[2] / 2.0) * ratio_x
        w2 = abs(self.bg[0] + self.bg[2] / 2.0) * ratio_x
        h1 = abs(self.fg[1] + self.fg[3] / 2.0) * ratio_y
        h2 = abs(self.bg[1] + self.bg[3] / 2.0) * ratio_y
        sway = 25.0 - (abs(w1 - w2) + abs(h1 - h2))
        sway = max(-25.0, min(25.0, sway))
        self.percent += sway * self.fill_speed * dt
        if self.percent >= 85.0:                   # CompletedPercentage
            self._win()
        elif self.percent <= 10.0:
            if self.item is not None and self.item.dexterity_cannot_lose:
                self.percent = 12.0
            else:
                self._lose()

    def add_mouse(self, xrel, yrel):
        """the player's mouse motion, screen px: the PC's thumb follows it one
        to one (pc_move), the remaster's pick takes it as the touch delta at
        25 (the viewer's scale, DexterityComponent.FixedUpdate cs:227)"""
        if self.pc_total:
            self.pc_move = (self.pc_move[0] + xrel, self.pc_move[1] + yrel)
        else:
            self.input = (self.input[0] + xrel * 25.0, self.input[1] - yrel * 25.0)

    def middle(self):
        """the field's middle in screen px: the PC's game's (pc_mid_px), the
        remaster's field's centre"""
        if self.pc_total:
            return self.pc_mid_px
        return (self.bg[0] + self.bg[2] / 2.0, self.bg[1] + self.bg[3] / 2.0)

    def pointer(self):
        """the thumb's point in screen px: the PC's mouse, the remaster's
        pick's centre"""
        if self.pc_total:
            return tuple(self.pc_mouse)
        return (self.fg[0] + self.fg[2] / 2.0, self.fg[1] + self.fg[3] / 2.0)

    def _pc_offset(self):
        """the mouse's displacement from the field's middle as the PC's game
        reads it (pcprofile.s2_game_offset: whole px, x 10, each axis held),
        in the level's px (pc_k)"""
        ox = (self.pc_mouse[0] - self.pc_mid_px[0]) / self.pc_k
        oy = (self.pc_mouse[1] - self.pc_mid_px[1]) / self.pc_k
        return pcprofile.s2_game_offset(int(ox), int(oy))

    def _pc_push(self, px, py):
        """the level tick moves the mouse by the game's output (whole PC px)"""
        self.pc_mouse[0] += px * self.pc_k
        self.pc_mouse[1] += py * self.pc_k

    def _pc_tick(self, dt):
        """the PC's game, once a level tick (12 a second): the DoAction step
        (fcn.10001b2c) is Woody's job — the use_object step pushes it on his
        list (fcn.10049246, [actor+0x18]), his tick runs it (fcn.100492a8,
        from the actors' pass fcn.10044234 the level update 0x100442b3
        calls at 0x100445f8) — and the game's update
        (fcn.100508a1) comes after it at 0x1004482b, so a tick adds the rate
        the last update left: the step adds it to the action's elapsed count,
        clamped at its `time`, and hands the game the progress, elapsed x 100
        / time (fcn.100507dd, latching at 10); the count at the action's time
        wins it (the object's action), below 0 fails it (the `failed`
        action); then the update (_pc_update)"""
        self.pc_acc += dt
        step = 1.0 / pcprofile.TICKS_PER_SECOND
        while self.pc_acc >= step and self.enabled:
            self.pc_acc -= step
            self.pc_elapsed = min(self.pc_elapsed + self.pc_rate, self.pc_total)
            if self.pc_elapsed < 0:
                # the `failed` action: the PC game can always be lost (201's
                # toolbox too, the mobile's DexterityCannotLose); its
                # behaviour sends the neighbour running — straight or through
                # Olga's shout (203) — or reaches 201's `aux`, the tutorial's
                # director, which relays the run (TutorialPC201.on_behaviour),
                # or nobody (212's spikes, 213's pinata: PCMinigameFailed).
                # The game's job ends on the next tick (its state 2) and the
                # use_object step behind it pushes the `failed` job in front
                # of itself (0x10004d51-0x10004d69), whose first update is a
                # tick later; the job posts the behaviour as it ends, its
                # PCMinigameFailedTicks after that (fcn.1004000a,
                # 0x10002708), and it is offered on the tick after the post
                # (pc_offer_tick)
                self.pc_elapsed = 0
                self.pc_progress = 0
                self.percent = 0.0
                failed = getattr(self.item, 'pc_minigame_failed', None)
                ft = getattr(self.item, 'pc_minigame_failed_ticks', None) or 0
                self._lose(alert=False)
                if failed in ('neighbor', 'olga', 'aux'):
                    self.pc_offer = [(ft + 3) * step - self.pc_acc, failed]
                return
            self.pc_progress = self.pc_elapsed * 100 // self.pc_total
            if self.pc_progress >= 10:
                self.pc_latch = True
            self.percent = float(self.pc_progress)
            if self.pc_elapsed >= self.pc_total:
                self._win()
                return
            self._pc_update()

    def _pc_update(self):
        """GameLogic.dll's game object (fcn.100508a1): it puts the thumb back
        on the middle over its first three ticks and leaves the rate at 0;
        after them it rates the thumb by its distance to the field's middle
        and pushes it by the wobble (pcprofile.s2_game_rate / s2_game_push,
        the factor from the combination's levels, PCMinigameLevels)"""
        levels = getattr(self.item, 'pc_minigame_levels', None) or (0, 0)
        self.pc_ticks += 1
        dx, dy = self._pc_offset()
        # the state message's pair, sent before the push: the drawn thumb
        # (hud._draw_pc_game)
        self.pc_thumb = pcprofile.s2_game_thumb(dx, dy, self.pc_ticks)
        if self.pc_ticks < 4:
            self._pc_push(int(-dx * 1000 / 10000), int(-dy * 1000 / 10000))
            self.pc_rate = 0
        else:
            self.pc_rate = pcprofile.s2_game_rate(dx, dy, self.pc_progress, self.pc_latch)
            self._pc_push(*pcprofile.s2_game_push(dx, dy, self.pc_progress,
                                                  levels, self.pc_phase))
        self.wrong = self.pc_rate < 0

    def _random_move(self):
        """UpdateRandomMovement (cs:341-359); Dificulty is 2"""
        w = self.world
        if w.time - self.last_rand_time > 1.0:
            self.last_rand_time = w.time
            self.rand_vec[0] = self._rng.randrange(-20, 20)
            if self._rng.randrange(-1, 1) < 0:
                self.rand_vec[0] = -self.rand_vec[0]
            self.rand_vec[1] = self._rng.randrange(-20, 20)
            if self._rng.randrange(-1, 1) < 0:
                self.rand_vec[1] = -self.rand_vec[1]
        return self.rand_vec[0] * 2.0, self.rand_vec[1] * 2.0

    def _check_margins(self):
        """CheckMargins (cs:273-339): clamp into the inner window; touching a
        margin shows the alarm field and boosts the drain"""
        mx = self.bg[2]; my = self.bg[3]
        left = mx * 0.2 + self.bg[0]
        up = my * 0.2 + self.bg[1]
        right = self.bg[0] + self.bg[2] - mx * 0.6
        down = self.bg[1] + self.bg[3] - my * 0.6
        self.wrong = False
        if self.fg[0] <= left:
            self.fg[0] = left
            self.wrong = True
        elif self.fg[0] > right:
            self.fg[0] = right
            self.wrong = True
        if self.fg[1] <= up:
            self.fg[1] = up
            self.wrong = True
        elif self.fg[1] > down:
            self.fg[1] = down
            self.wrong = True
        # CheckMargins sets FillSpeed=1.2, but FixedUpdate's line 243
        # unconditionally resets it to 1 before the drain reads it
        # (DexterityComponent.cs:237-243, 254) — the boost is dead code;
        # only the `wrong` background art survives
        return True

    def _win(self):
        """WinDexterity (cs:369-388)"""
        w = self.world
        woody = w.woody
        if woody is not None:
            woody.mouse_click_after_dexterity = True
            woody.dexterity_done = True
        self.cleanup()
        it = self.item
        if it is None:
            return
        if it.dexterity_run_other and it.sprite is not None:
            # DexterityOtherAnimation is the literal N2TrickItemUseNormal
            # (cs:374-379) — both carriers serialize UseNormal as NONE
            w.play_item_anim(it, 'N2TrickItemUseNormal')
        if it.activate_trick_if_search:
            it.tricked = True
        if it.dexterity_trick_item or it.take_item_count > 0:
            self.start_again = True

    def _lose(self, alert=True):
        """LoseDexterity (cs:361-367)"""
        self.cleanup()
        w = self.world
        if w.woody is not None and w.woody.anim.has('DexterityFailed'):
            w.woody.anim.play_single('DexterityFailed')
        self.start_again = True
        if alert:
            self.alert()

    def _pc_failed_clip(self):
        """the PC's `failed` behaviour on an actor other than the neighbour
        plays that actor's action of the behaviour's name first — 203's Olga
        `shout`: shout_chinese, 69 frames at 12 a second, then eat_chinese
        (cn_c2's olga record; PCMinigameFailedClip) — and that action's own
        behaviour, the neighbour's `run`, is posted as its job ends, the
        clip's `ticks` after its first update (pc_offer_tick)"""
        fc = getattr(self.item, 'pc_minigame_failed_clip', None)
        pawn = self.world.pawns.get(fc['role']) if fc else None
        if pawn is None or not pawn.anim.has(fc['clip']):
            return
        anim = pawn.anim
        then = fc.get('then')
        anim.clip_pace = {fc['clip']: float(fc['secs'])}

        def back():
            anim.clip_pace = None
            anim.time_scale = 1.0
            if then and anim.has(then):
                anim.play_looping(then)
        anim.play_sequence([fc['clip']], on_end=back, as_sequence=False)

    def pc_offer_tick(self, dt):
        """a lost PC game's behaviour reaching its actor: the `failed`
        action's job posts it as it ends (state 2, fcn.1004000a), in the
        actors' pass, and the level update's walker (fcn.1003fc90, at
        0x100445f1, before that pass) makes it on the next level tick
        (fcn.1003e769) and offers it to the actor (fcn.1004b27f ->
        fcn.1004abcf), again every tick until it is taken. 201's `aux`
        relays the run (TutorialPC201.on_behaviour); 203's Olga takes her
        `shout` at once — her handler's update pushes the action, whose job
        starts in that tick's pass — and its job posts his `run` as it ends
        (_pc_failed_clip). The neighbour's jobs vote front to
        back (slot 5) and a passing job whose +4 is 0 refuses the offer:
        his level script's walks are made with 1 (fcn.1000e3e0 ->
        fcn.10007a10, the GoTo job 0x100ab3d8 storing it at 0x10007350) and
        its actions with 0 (fcn.1000efcd's push 0, the direct fcn.10002cd5
        calls' zeroed ebx) — so a walk is cut at once and an action runs to
        its end, the run then taken as his next walk begins (the mobile's
        DexterityAlert and its deferred watcher, a level tick apart)"""
        self.pc_offer[0] -= dt
        if self.pc_offer[0] > 1e-9:
            return
        left, actor = self.pc_offer
        self.pc_offer = None
        w = self.world
        step = 1.0 / pcprofile.TICKS_PER_SECOND
        if actor == 'aux':
            ls = w.level_script
            if getattr(ls, 'on_behaviour', None) is not None:
                ls.on_behaviour('run', self.item)
            return
        if actor == 'olga':
            self._pc_failed_clip()
            fc = getattr(self.item, 'pc_minigame_failed_clip', None) or {}
            self.pc_offer = [(int(fc.get('ticks') or 0) + 1) * step + left, 'neighbor']
            return
        rott = w.pawns.get('Rottweiler')
        rt = next((r for r in w.routines if r.pawn is rott), None) \
            if rott is not None else None
        if rt is None or self.item is None:
            return
        if rott.state == rott.WALK:
            _dex_surprise(w, rt, self.item)
        else:
            self.pc_offer = [step + left, 'neighbor']

    def cleanup(self):
        """CleanUp (cs:390-406)"""
        w = self.world
        w.is_dexterity_on = False
        self.enabled = False
        self.wrong = False
        if w.woody is not None:
            w.woody.unfreeze()                 # Woody.UnFreeze
            w.woody.movement_paused = False
        it = self.item
        if it is not None and (it.hide_in_dexterity or self.spec['hide_object']):
            w.set_object_hidden(it, False)

    def alert(self):
        """DexterityAlert (cs:414-426): a walking Rottweiler surprises onto
        the item at once; otherwise the item's Update watcher waits for him"""
        w = self.world
        rott = w.pawns.get('Rottweiler')
        if rott is None or self.item is None:
            return
        rt = next((r for r in w.routines if r.pawn is rott), None)
        if rt is not None and rott.state == rott.WALK:
            _dex_surprise(w, rt, self.item)
        else:
            self.rott_in_animation = True


class ProgressBarState:
    """One ProgressBar component (ProgressBar.cs): the sleep bar that fills
    while its item's use sequence sits between two element indices, putting
    the owning pawn to sleep for the duration."""

    def __init__(self, world, spec):
        self.world = world
        self.spec = spec
        self.item = world.level.items.get(spec['item'])
        self.blind = spec['blind']
        self.mother_210 = spec['mother_210']
        self.active = spec['active']     # the GameObject's active state
        self.disabled = False            # Behaviour.enabled = false
                                         # (DisableProgressBar, cs:303-307)
        # Start (cs:77-105)
        self.visible = False
        self.progress = 0.0
        self.executed_once = True        # ExecutedOnce
        self.execute_once_2 = True
        self.execute_once_3 = True
        self.execute_once_4 = True
        self.seconds = 0.0               # SecondsCount
        self.stop_progress = False       # StopProgressBar
        self.is_pawn_hud = spec['actor'] in ('Rottweiler', 'Mother')
        self.hud_tex = spec['rott_hud'] if spec['actor'] == 'Rottweiler' \
            else spec['mother_hud']
        # OnEnable (cs:108-114)
        world.subscribe('mother_urgent', self.stop_for_urgency)
        world.subscribe('mother_urgent_stop', self.resume_after_urgency)

    @property
    def pawn(self):
        """SelectedPawn; resolved late — the pawns spawn after the level
        components are built (Start does the same lookup, cs:82-105)"""
        return self.world.pawns.get(self.spec['actor'])

    def tick(self, dt):
        """Update (ProgressBar.cs:123-173)"""
        if not self.active or self.disabled or self.item is None \
                or self.pawn is None:
            return
        w = self.world
        # the once-only cancel when the pawn spots Woody or an urgency stops
        # the bar (cs:125-142); a non-Mother210 bar dies for the level
        if self.execute_once_3 and self.spec['actor'] == 'Mother' and \
                (w.can_mother_see_woody() or self.stop_progress):
            self.execute_once_3 = False
            self.set_sleeping(False)
            if not self.mother_210:
                self.active = False
        elif self.execute_once_4 and self.spec['actor'] == 'Rottweiler' and \
                (w.can_rottweiler_see_woody() or self.stop_progress):
            self.execute_once_4 = False
            self.set_sleeping(False)
            if not self.mother_210:
                self.active = False
        idx = self._check_state(self.item.current_sequence)   # cs:143
        if idx == -1:
            return
        s = self.spec['seqs'][idx]
        if s['AnimationStartIndex'] <= self.item.current_seq_index \
                < s['AnimationEndIndex']:                      # cs:148
            self.seconds += dt
            if self.executed_once:
                self.set_sleeping(True)
            if self.seconds <= s['Duration']:
                self.progress = self.seconds / s['Duration']
            else:
                self.progress = 1.0
        elif self.execute_once_2 and self.visible:             # cs:164-172
            self.execute_once_2 = False
            self.set_sleeping(False)
            if not self.mother_210:
                self.active = False

    def set_sleeping(self, value):
        """SetSleeping (cs:175-225): the pawn's IsSleeping detection gate and
        the HUD face swap with the think bubble disabled"""
        self.executed_once = False
        self.visible = value
        self.pawn.is_sleeping = value
        if self.spec['actor'] in ('Rottweiler', 'Mother'):
            self.pawn.hud_blind = bool(value and self.blind)
            self.pawn.hud_disable_think = value

    def disable(self):
        """DisableProgressBar (ProgressBar.cs:303-307), the
        GameInfo.DisableProgressBar subscriber fired by FinishAnimationEnded
        (GameInfo.cs:346, 535-541): SetSleeping(false) — the pawn wakes for
        the HUD, the bar and its face drain vanish — and the behaviour is
        disabled. Only an active bar is subscribed (OnEnable/OnDisable,
        cs:108-121); a bar killed by SetActive(false) is not."""
        if not self.active or self.disabled:
            return
        self.set_sleeping(False)
        self.disabled = True

    def stop_for_urgency(self):
        """StopForUrgency (cs:233-237)"""
        self.set_sleeping(False)
        self.stop_progress = True

    def resume_after_urgency(self):
        """ResumeAfterUrgency (cs:227-231)"""
        if self.item is not None:
            self.item.current_seq_index = -1
        self.restore()

    def restore(self):
        """RestoreVariables (cs:291-301)"""
        self.visible = False
        self.progress = 0.0
        self.executed_once = True
        self.execute_once_2 = True
        self.execute_once_3 = True
        self.execute_once_4 = True
        self.seconds = 0.0
        self.stop_progress = False

    def _check_state(self, state):
        """CheckAnimationSequenceState (cs:279-289)"""
        for i, s in enumerate(self.spec['seqs']):
            if s['AnimationSequence'] == state:
                return i
        return -1


class World:
    def __init__(self, level, sound_sink=None, music=None, defer_music=False):
        self.level = level
        self.woody = None
        self.pawns = {}
        self.routines = []
        # (catcher, target, maxd, same_zone, reach): a walk toward a pawn
        # that RoutineActionMove.Finished ends by distance
        self._hit_watches = []
        self.game = GameState(level.game_info)
        if pcprofile.is_pc() and getattr(level, '_season2', False):
            self.game.lives = 3           # the PC's three attempts (4PDA, 2017)
        self.inventory = InventoryState()
        # InventoryManager.InventoryItems is a serialized List<Inventory>
        # (InventoryManager.cs:5): Unity deserializes it before any Start,
        # so Woody holds it from the first frame with no OnInventoryAdded —
        # L209 ships the pen knife (HUD.OnGUI's FirstInventoryItem draw only
        # runs Inventory.Initialize on it, HUD.cs:972-978: the icons and the
        # localized strings, which the port resolves at draw time)
        self.inventory.items = [dict(e) for e in level.inventory_items]
        # the MusicPlayer port: the entrance clap fires at load, the level
        # track follows after the first-run delay (MusicPlayer.Start,
        # PlayLevelMusic — MusicPlayer.cs:44-51, 88-98; Level.cs:295-297)
        self.music_bank = music
        self.sound_sink = sound_sink
        self._last_input_time = 0.0      # Woody.LastInputTime
        self.pay_log = []                # (t, item, points, hot) per paid trick under the profile
        self._entrance_hello = False
        self._open_furniture = []        # SearchItem.CloseTime holders
        self.snap_request = None         # HUD face clicks -> CameraMover
        self.camera_frozen = False       # GameCamera.Freeze (FinishGame)
        # Woody.PlayFinishAnimation's deferral pair (Woody.cs:1104-1128):
        # a finish that arrives mid-door-pass or while hiding waits
        # (ShouldPlayFinish) for the arrival / the leave animation's end;
        # IsPlayingFinish routes the win/lose pose's end into
        # FinishAnimationEnded (Woody.cs:325-327)
        self.should_play_finish = False  # Woody.ShouldPlayFinish
        self.is_playing_finish = False   # Woody.IsPlayingFinish
        self._music_timer = None
        # the exit door's confirmation (Pawn.cs:1378-1383 ->
        # Woody.ShowExitConfirmation, Woody.cs:552-556): the application
        # hangs its ExitConfirmation dialog here; without one (the bare
        # viewer) the pass runs straight through
        self.show_exit_confirmation = None
        # the tutorial layer (runtime/tutorial.py): GameInfo.LevelScript;
        # the signal sites below call its hooks when the application set it
        self.level_script = None
        # GameInfo.CalculateScore's tail is Level.SaveScore (GameInfo.cs:
        # 409/429-435) — the application saves the progress here, right
        # after the numbers exist (the all-tricks win raises GameEnding
        # 2.5 s before FinishGame computes them, cs:226-236)
        self.on_score_computed = None
        if music is not None and level.music is not None and not defer_music:
            # the viewer alone: its t=0 is IntroAnimation.StartGame; the clap
            # and the 15 s Invoke started intro_total earlier, at the scene
            # load (MusicPlayer.Start cs:43-51, Level.cs:295-297): the clap
            # resumes intro_total in, the track follows at 15 - intro_total.
            # The application runs the title cards itself and calls
            # start_music(elapsed) at StartGame instead.
            intro = level.music.get('intro_total') or 0.0
            if level.music.get('clap'):
                music.play_music(level.music['clap'], loop=False,
                                 offset=intro)
            self.start_music(intro, clap=False)
        self.hud = None                  # set by the viewer; the description
                                         # bubble and whistle land here
        self.players = {id(s): AnimPlayer(s, sound_sink) for s in level.sprites}
        for d in level.doors:
            if d.sprite is not None:
                d.sprite = self.players.get(id(d.sprite))
            # Door.Start's DisableOnStart deactivation (Door.cs:63-66)
            if d.disabled and d.sprite is not None:
                d.sprite.sprite.hidden = True
        # Zone.ZoneEnter / ZoneLeave: items whose EnterZone / LeaveZone anims
        # react when a pawn passes a door of their zone
        self._zone_items = {}
        for it in level.items.values():
            if it.enter_zone or it.leave_zone:
                self._zone_items.setdefault(it.zone, []).append(it)
        # Alerter.Start: one FSM per pet; Zone.NoticeOnEnterItems from
        # TrickItem.Start's NoticeWhenEnterZone registration
        # an inactive GameObject gets no Update, hence no FSM (Level112's dog
        # is enabled later by its level script); the sprite exists only for
        # active objects
        self.alerters = {it.pid: AlerterFSM(self, it)
                         for it in level.items.values()
                         if it.kind == 'Alerter' and it.sprite is not None}
        self.notice_items = {}
        for it in level.items.values():
            if it.notice_enter:
                self.notice_items.setdefault(it.zone, []).append(it)
        # Zone.NoticeWhenNearItems from TrickItem.Start's NoticeWhenWalkNearby
        self.near_items = {}
        for it in level.items.values():
            if it.notice_near:
                self.near_items.setdefault(it.zone, []).append(it)
        self._delayed = []               # (seconds left, fn) Invoke timers
        # the PC profile's Season 2 respawn (pcprofile.s2_respawn): the catch
        # fiber's span on Woody's queue up to its case 5 (the flag 0x10000),
        # and the seconds left on the respawn timer after it
        self._pc_catch_seq = False
        self._pc_respawn_left = 0.0
        self.snake_aux_208 = False       # GameInfo.SnakeAux208 (the L208 chain)
        self._entrance_timer = None      # Woody's walk-in countdown
        self.time = 0.0                  # Time.time for the alarm intervals
        self._woody_show_after = []      # Woody.ItemToShowAfterAnim queue
        self._woody_layer_restore = []   # (pawn, depth) from the hide layers
        self._woody_use_anim_item = None  # Woody.itemAux (HideDuringWoodyUseAnim)
        self.flag_aux = False            # GameInfo.flagAux (the OlgaWCUse shot)
        self._woody_use_anim_hidden = False
        self.behavior_objs = []          # live level-behavior instances
        self.search_behavior = None      # Woody.SearchBehavior
        self.events = {}                 # the behaviors' static C# events
        # the ProgressBar components (ProgressBar.cs)
        self.progress_bars = [ProgressBarState(self, s)
                              for s in level.progress_bars]
        # the DexterityComponent minigames (DexterityComponent.cs)
        self.is_dexterity_on = False     # GameInfo.IsDexterityOn
        self.menu_open = False           # InGameMenu enabled (timeScale=0)
        self.menu_toggle_hook = None     # the application's InGameMenu.Toggle
        self.screen_size = (800, 600)    # the viewer overrides these two
        self.screen_point = self._default_screen_point
        self.snap_camera = None          # CameraMover.SnapToWoodyImmediate
        self.dex_states = {pid: DexterityState(self, s)
                           for pid, s in level.dexterity.items()}
        # Item.InvUsed (Item.cs:628): the inventory the running dexterity
        # was armed with, removed on completion (cs:1442, 1472, 1479, 1505);
        # one game-wide slot here, as only one dexterity runs at a time
        self._dex_inv_used = None
        for ds in self.dex_states.values():
            if ds.item is not None:
                ds.item.dexterity_hide_object = ds.spec['hide_object']
        # Item.Start ends in SetPrimed(Primed): the initial primed visibility
        # (Item.cs:697, 1219-1235)
        for it in level.items.values():
            if it.sprite is not None:
                if it.show_only_when_primed:
                    it.sprite.hidden = not it.primed
                if it.hide_when_primed and it.primed:
                    it.sprite.hidden = True
        # the Start-time plays that give an item controller its first
        # CurrentAnimation (every item sprite loads with none, scene.py
        # _add_sprite)
        self._start_item_animations()
        # Drawing.Start parks its smear hidden (Drawing.cs:17-22)
        for it in level.items.values():
            if it.kind == 'Drawing' and it.sprite is not None:
                it.sprite.hidden = True
        # TrickItem.OnItemAnimationCompleted (TrickItem.cs:1059-1079): the
        # zone poses and an AnimateAfterUse use pose return to idle
        for it in level.items.values():
            if it.kind in TRICK_KINDS and it.sprite is not None:
                p = self.players.get(id(it.sprite))
                if p is not None:
                    p.single_end_hook = \
                        (lambda name, i=it: self._item_anim_completed(i, name))

    def on_mouse_hover(self, item):
        """TrickItem.OnMouseHover (TrickItem.cs:557-565): the hover pose
        plays while the item is untricked and not already playing it"""
        if item.kind not in TRICK_KINDS:
            return
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None or not item.animating or not item.hover_anim:
            return
        if item.is_tricked(self.level.items):
            return
        # !AnimController.IsPlaying(HoverAnim): a null CurrentAnimation is
        # "not playing" (AnimationControllerBase.cs:403-410)
        if p.has(item.hover_anim) and \
                (p.anim is None or p.anim.name != item.hover_anim):
            self.play_item_anim(item, item.hover_anim)

    def toggle_menu(self):
        """Woody.ToggleMenu -> InGameMenu.Toggle (InGameMenu.cs:28-61):
        Enable freezes time, Disable resumes it. The application hangs the
        widget tree on menu_toggle_hook (runtime/app.py's InGameMenu); the
        bare viewer keeps the pause and the HUD fill hide alone."""
        if self.menu_toggle_hook is not None:
            self.menu_toggle_hook()
        else:
            self.menu_open = not self.menu_open

    def dexterity_focus(self):
        """the camera's point while a dexterity game is on: Woody
        (GameCamera.Freeze + SnapToWoodyImmediate, DexterityComponent.cs:149,
        171); the PC's game holds its field's middle there (GFXEngine
        0x1000ab08-0x1000ab7e: the scroll puts it at the middle of the scene,
        pcprofile.S2_GAME_HOTSPOT)"""
        for ds in self.dex_states.values():
            if ds.enabled and ds.pc_mid is not None:
                return ds.pc_mid
        return self.woody.sprite.x, self.woody.sprite.y

    def _default_screen_point(self, x, y):
        """WorldToScreenPoint with the y flip, camera on Woody — the viewer
        swaps in its real (clamped) camera"""
        W, H = self.screen_size
        cx = self.woody.sprite.x if self.woody is not None else 0.0
        cy = self.woody.sprite.y if self.woody is not None else 0.0
        aspect = W / float(H)
        sx = (x - cx) / (3.0 * aspect) * (W * 0.5) + W * 0.5
        sy = (y - cy) / 3.0 * (H * 0.5) + H * 0.5
        return sx, H - sy

    def activate_progress_bar(self, item, actor):
        """ProgressBarObject.SetActive(true) (Item.cs:831-834, 861-864,
        1110-1113, 1322-1325): the bar's GameObject ships inactive; OnEnable
        re-arms its variables (ProgressBar.cs:108-114)"""
        if not item.progress_bar_animation or item.progress_bar_object is None:
            return
        for pb in self.progress_bars:
            if pb.spec['go'] == item.progress_bar_object \
                    and pb.spec['actor'] == actor and not pb.active:
                pb.active = True
                pb.restore()

    def _on_compound_trick_done(self, item):
        """Item.OnCompoundTrickDone (Item.cs:2161-2169): counts once while
        the item has not paid its plain trick yet, with the statue strip and
        the whistle"""
        if not item.already_tricked:
            self.game.compound_tricks += 1
            if self.hud is not None:
                self.hud.statue_anim.restart()     # PlayStatueAchieved
                self.hud.play_whistle()

    def _audience_laugh(self, pawn, kind):
        """Rottweiler.PlayAudienceLaugh (Rottweiler.cs:805-818): a random
        clip from the medium/big pool"""
        import random
        pool = pawn.medium_laughs if kind == 'medium' else pawn.big_laughs
        if pool and self.sound_sink is not None:
            self.sound_sink(random.choice(pool))

    def _hud_angry(self, level):
        """Woody.HUD.PlayRottweilerAngry(level)"""
        if self.hud is not None:
            self.hud.play_rottweiler_angry(level)

    def _s2_credit(self, pawn, item, part=None):
        """the NFH2 ladder's meter arithmetic (Rottweiler.cs:613-663): the
        compounds' extras, the linked pair and the item's own AngerAmount;
        returns whether the meter overflowed. Under the PC profile the linked
        trick's own record may pay at its own tick of the linked step
        (item.pc_linked_due, PCLinkedPaysAt): `part='linked'` pays that arm
        alone, the rest leaves it for then — the arm's amount settled by
        whichever part comes first (item.pc_linked_amount), before the
        trick's OnTrickDone marks the pair (cs:785-787)."""
        items = self.level.items
        linked = items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        aux = item if item.kind in TRICK_KINDS else None
        if part == 'toilet':
            # 211's rush record at its tick of the wc's puke (wcright, 27 of
            # 40; PCToiletPaysAt) — the ladder's cs:615-619 arm alone
            item.extra_coin_toilet_211 = False
            pawn.angry_meter += 20.0
            overflow = pawn.angry_meter > pawn.angry_max
            if overflow:
                pawn.angry_meter = pawn.angry_max
                pawn.pc_rage_full = True
            return overflow
        if part == 'extra':
            # 206's linked shot's third record at its own tick (the
            # ExtraCoin206, PCExtraPaysAtLinked: rubberrabbit 50 ticks into
            # the ramp's rubberrabbit, fcn.1000140b) — the ladder's cs:625-629
            # arm alone
            item.extra_coin_206 = False
            pawn.angry_meter += self._pc_extra(item, 15.0, 'pc_extra_coin_206')
            overflow = pawn.angry_meter > pawn.angry_max
            if overflow:
                pawn.angry_meter = pawn.angry_max
                pawn.pc_rage_full = True
            return overflow
        if part == 'linked':
            pass
        elif item.extra_coin_toilet_211 and not (pcprofile.is_pc()
                                                 and item.pc_toilet_pays_at is not None):  # cs:615-619
            # (under the profile at its record's tick: the `toilet` part)
            item.extra_coin_toilet_211 = False
            pawn.angry_meter += 20.0
        elif item.compound_extra_coin and aux is not None \
                and aux.compound_tricked:      # cs:620-624
            item.compound_extra_coin = False
            # the PC pays the record the extra stands for (tricks.xml
            # rage: 206's harpoon_fifi 30, 213's tortilla_tequila 20 —
            # levels/pc overlays, PCExtraCoin); the accounting
            # fcn.1000140b credits each named record of the action once
            pawn.angry_meter += self._pc_extra(item, 20.0)
        elif item.tricked and linked is not None and linked.tricked \
                and item.extra_coin_206 and not (pcprofile.is_pc()
                                                 and item.pc_extra_pays_at_linked is not None):  # cs:625-629
            # (under the profile with its own tick: the `extra` part)
            item.extra_coin_206 = False
            # 206: the PC's three records (harpoon_fifi, harpoon_rubber,
            # rubberrabbit) are the pad, the linked harpoon and one extra
            # of 30 through whichever branch fires (PCExtraCoin206 30)
            pawn.angry_meter += self._pc_extra(item, 15.0, 'pc_extra_coin_206')
        elif item.plant_carnivore_extra and aux is not None \
                and aux.compound_tricked:      # cs:630-634
            item.plant_carnivore_extra = False
            # 213: carnivore_bigmanip 20 in me_c2/tricks.xml
            pawn.angry_meter += self._pc_extra(item, 10.0)
        elif item.extra_coin_210 and item.tricked \
                and linked is not None and linked.tricked:  # cs:635-639
            basket = items.get(item.dog_basket_210) \
                if item.dog_basket_210 else None
            if basket is not None and basket.primed:
                item.extra_coin_210 = False
                # the PC pays the drained pool as its own trick record:
                # in_b2/objects.xml `pool/divingboard_oil` lists
                # fifi_bone, fall_water and fall_empty in one
                # `fall_empty` action, fall_empty 20000 in tricks.xml
                # (the mobile's 10 is that coin halved; PCExtraCoin 20)
                pawn.angry_meter += self._pc_extra(item, 10.0)
        if item.pc_linked_amount is not None:
            # the arm settled by the other part: paid now if this is the
            # linked record's tick
            if part == 'linked':
                pawn.angry_meter += item.pc_linked_amount
                item.pc_linked_amount = 0.0
        elif linked is not None and linked.tricked and item.tricked:
            # the linked-pair arm (cs:640-654)
            if not linked.already_tricked:
                amount = linked.anger_amount
                if item.extra_coin_linked:
                    if pcprofile.is_pc() and item.pc_extra_coin_linked is not None:
                        # the PC's record for it pays later in the linked
                        # flow, as his parked angry resumes (PCExtraCoinLinked:
                        # 207's bill, 30 ticks into the billboard at Olga's
                        # lift's end)
                        item.pc_extra_due = True
                    else:
                        amount += item.extra_coin_anger
                if item.pc_linked_due and part != 'linked':
                    item.pc_linked_amount = amount     # its record's tick pays it
                else:
                    pawn.angry_meter += amount
                    if item.pc_linked_due:
                        item.pc_linked_amount = 0.0    # paid ahead of the own part
            elif item.already_tricked and linked.already_tricked \
                    and part != 'linked':
                pawn.tricked_aux = True
        if part != 'linked' and not item.dont_get_angry \
                and not pawn.tricked_aux \
                and not item.already_tricked:  # cs:655-658
            pawn.angry_meter += item.anger_amount
        overflow = False
        if pawn.angry_meter > pawn.angry_max:  # cs:659-663
            pawn.angry_meter = pawn.angry_max
            overflow = True
            pawn.pc_rage_full = True
        return overflow

    def pc_s2_credit(self, pawn, item):
        """the Season 2 trick paid as its PC action ends, before the rest of
        the tricked use (PCCreditAfter: 202's shark on the sea's `enter`,
        its 119-tick bar still to come): the meter's credit and the coin now,
        the tantrum at the use's end plays without paying again
        (play_angry)"""
        if self.game is None or item.pc_credited:
            return
        item.pc_credit_overflow = self._s2_credit(pawn, item)
        item.pc_credited = True
        if item.pc_credit_overflow:
            # the gauge fills as the record pays: the overflow's tick (the
            # collapse the PC scores) and its whistle now, not at the tantrum
            # (the level may end on this very coin)
            pawn.angry_count_ticks += 1
            self._hud_angry(3)
            if self.hud is not None:
                self.hud.play_whistle()
        if item.pc_linked_due and not item.pc_linked_paid:
            # the pair is done with its last record: the level's done count
            # is its trick table's credited records (fcn.1000140b ->
            # fcn.100522e6, the count fcn.1005225b), so the linked record
            # completes it after its rage (pc_s2_linked_credit)
            item.pc_done_due = True
            return
        self._pc_trick_done(item)

    def _pc_trick_done(self, item):
        """the trick's completion as the mobile books it (cs:785-792)"""
        if not item.dont_get_angry:
            self._on_trick_done(item)              # cs:785-787
        if self.level_script is not None:
            self.level_script.on_trick_done()      # cs:789-792

    def pc_s2_linked_credit(self, pawn, item):
        """the linked trick's own record paid at its tick of the linked step
        (PCLinkedPaysAt: fcn.1000140b credits each named record of a playing
        action at its `time` — 202's bridge_electrify on the electrify's
        fifth tick, 22 after the crash's bridge_crash): the linked arm's rage
        now, the overflow's tick and whistle with it"""
        if self.game is None or not item.pc_linked_due or item.pc_linked_paid:
            return
        item.pc_linked_paid = True
        was = pawn.angry_meter >= pawn.angry_max
        if self._s2_credit(pawn, item, part='linked') and not was \
                and not (item.pc_credited and item.pc_credit_overflow):
            item.pc_linked_overflow = True
            pawn.angry_count_ticks += 1
            self._hud_angry(3)
            if self.hud is not None:
                self.hud.play_whistle()
        if item.pc_done_due:
            item.pc_done_due = False
            self._pc_trick_done(item)

    def pc_s2_extra_credit(self, pawn, item):
        """the linked shot's third record at its tick (206's rubberrabbit,
        50 ticks into the ramp's rubberrabbit: the ExtraCoin206 the mobile
        pays with the ladder, PCExtraPaysAtLinked) or the rush's own in the
        wc (211's wcright, 27 ticks into the puke: the Toilet211 extra coin,
        PCToiletPaysAt): its rage, the overflow's tick and whistle, and its
        completion (the level's done count is its credited records,
        fcn.100522e6 — the mobile books it as the use starts,
        Item.ExtraCoin206Calculation, Item.Toilet211Behavior)"""
        if self.game is None:
            return
        part = 'extra' if item.extra_coin_206 else 'toilet' if item.extra_coin_toilet_211 else None
        if part is None:
            return
        was = pawn.angry_meter >= pawn.angry_max
        if self._s2_credit(pawn, item, part=part) and not was:
            pawn.angry_count_ticks += 1
            self._hud_angry(3)
            if self.hud is not None:
                self.hud.play_whistle()
        self.game.trick_done(item.trick_score)

    def s1_fire(self, pawn, item):
        """the PC's trick fire (game.exe fcn.0047bd00, docs/PC_ROUTINES.md "The
        fire's tail"): the bonus test, the score, the rage and the face, and
        the shout the step plays after the trick's own clip. play_angry calls
        it when the step fires after the animation (an OBJ2 station, a
        doubletake); the tricked use calls it earlier at PCFireAt (the
        five-argument stations, whose clip follows the fire) and the near
        surprise before the fall (PCFireBefore, the slips). The mobile's
        OnTrickDone score rides the fire, so the completion count and the
        level's end follow it too."""
        points = self._would_pay(item)
        bonus = points > 0 and pawn.rage_current > 0
        if points > 0:
            # the profile's payment record (the harness reads it for the chains)
            self.pay_log.append((round(self.time, 2), item.name, points, bool(bonus)))
        if bonus:
            pawn.angry_count_ticks += 1
            self._on_compound_trick_done(item)   # the mobile's arm (cs:608)
            self._audience_laugh(pawn, 'big')
        else:
            self._audience_laugh(pawn, 'medium')
        if points > 0:
            self._hud_angry(3 if bonus else 2 if points > 10 else 1)
            pawn.rage_current, pawn.rage_hold = pcprofile.s1_rage_fire(
                pawn.rage_current, item.pc_angry_time or pawn.rage_max)
            pawn.rage_bonus = bonus
            pawn.angry_meter = float(
                pcprofile.s1_rage_percent(pawn.rage_current, pawn.rage_max))
        item.pc_shout_secs = pcprofile.s1_shout_seconds(
            points, bonus, item.pc_shout_index, item.pc_shout_skip)
        if not item.dont_get_angry:
            self._on_trick_done(item)              # cs:785-787, at the PC's fire
        if self.level_script is not None:
            self.level_script.on_trick_done()      # cs:789-792
        item.pc_fired = True

    def play_angry(self, pawn, item, on_done=None):
        """Rottweiler.PlayAngryAnimation (Rottweiler.cs:552-797), the
        GameMode.Classic branch, with the name-hack heads, the extra-angry
        insert, the affected-pawn hand-off and the after-run of
        OnAnimationSequenceEnded (FixTrickedItem, the toilet rush)."""
        items = self.level.items
        routine = next((r for r in self.routines if r.pawn is pawn), None)
        # the parked angry's resume after a co-actor's hit
        # (continue_angry_animation hands the item in again)
        resume = pawn.item_to_ignore_next_time is item
        if resume and item.pc_extra_due and self.game is not None:
            # the linked flow's own record for the extra coin, paid at his
            # resume (PCExtraCoinLinked: 207's bill, 30 ticks into the
            # billboard after the lift, GameLogic 0x1001513f; fcn.1000140b
            # credits it), done with it (Item.cs:2143-2146)
            item.pc_extra_due = False
            was = pawn.angry_meter >= pawn.angry_max
            pawn.angry_meter += float(item.pc_extra_coin_linked)
            if pawn.angry_meter > pawn.angry_max:
                pawn.angry_meter = pawn.angry_max
                pawn.pc_rage_full = True
                if not was:
                    # the overflow's tick counted here, not again by the
                    # freakout branch below (its `ticked`)
                    item.pc_linked_overflow = True
                    pawn.angry_count_ticks += 1
                    self._hud_angry(3)
                    if self.hud is not None:
                        self.hud.play_whistle()
            self.game.trick_done(self.trick_score(item))
        if item.dont_get_angry:
            item.use_once = False                  # cs:564-568
            item.got_tricked = False
        self.check_final_position(pawn, item)      # cs:569
        if item.name == 'Chef' and item.activate_item_trick is not None:
            fx = items.get(item.fix_item_trick) \
                if item.fix_item_trick else None
            if fx is not None:                     # cs:570-573
                self.set_object_hidden(fx, True)
        hoda = items.get(item.hide_object_during_animation) \
            if item.hide_object_during_animation else None
        if hoda is not None:                       # cs:574-577
            self.set_object_hidden(hoda, False)
        if item.name == 'ChairAssemblyBook':       # cs:578-585
            chair = next((i for i in items.values()
                          if i.name == 'ChairAssembly'), None)
            if chair is not None:
                self.set_object_hidden(chair, False)
        if item.name == 'LiveBull':                # cs:586-592
            fx = items.get(item.fix_item_trick) \
                if item.fix_item_trick else None
            linked = items.get(item.linked_item_trick) \
                if item.linked_item_trick else None
            if fx is not None:
                fx.idle = 'N2TrickItemUseTricked'
                self.play_item_anim(fx, fx.idle)
                if fx.sprite is not None:
                    from scene import GUI_DEPTH
                    fx.sprite.depth = GUI_DEPTH['ItemsFront']
            if linked is not None:
                self.set_active(linked, True)
        self._show_objects(item)                   # Item.ShowObjects
        if item.change_item_anim_when_angry and item.item_anim_when_angry:
            p = self.players.get(id(item.sprite)) if item.sprite else None
            if p is not None and p.has(item.item_anim_when_angry):
                p.play_directly(item.item_anim_when_angry)   # Item.cs:2654-2660
        seq = []
        nfh2 = self.woody is not None and self.woody.nfh2
        pc_s1 = self.game is not None and not nfh2 and pcprofile.is_pc() \
            and pawn.rage_max > 0
        fired_early = False
        pc_shout = 0.0
        if pc_s1:
            # the PC's trick step (game.exe fcn.0047bd00, docs/PC_ROUTINES.md
            # "The anger and the bonus" and "The fire's tail"): the fire —
            # s1_fire: the bonus iff the rage current is above zero, the
            # score, the current raised to the trick's angrytime and held
            # 60 ticks, the face — then one shout, shout2_extra on a bonus
            # and a short one by the points otherwise, none on a flag-2
            # step, then the repair. The fire has already happened when the
            # PC's step scores before the trick's own clip (PCFireAt,
            # PCFireBefore); the mobile's AngryHard plays at the pace that
            # lasts the PC shout, the fix clips at the pace of the PC's
            # repair or clean action (PCFixSeconds), where the mobile's
            # levels (cs:597-607) play AngryEasyUp alone on an empty meter
            # and AngryEasyDown before AngryHard on a hot one
            fired_early = bool(getattr(item, 'pc_fired', False))
            if not fired_early:
                self.s1_fire(pawn, item)
            pc_shout = item.pc_shout_secs or 0.0
            item.pc_fired = False
            item.pc_shout_secs = None
            if item.angry_hard and pc_shout > 0.0:
                seq = [item.angry_hard]
        elif self.game is not None and not nfh2:   # Classic (cs:595-612)
            if pawn.angry_meter <= 0.0:
                if item.angry_easy_up:
                    seq = [item.angry_easy_up]
                self._hud_angry(1)                 # PlayRottweilerAngry(L1)
                self._audience_laugh(pawn, 'medium')   # cs:601
            else:
                pawn.angry_count_ticks += 1
                seq = [a for a in (item.angry_easy_down, item.angry_hard) if a]
                self._hud_angry(3)                 # PlayRottweilerAngry(L3)
                self._on_compound_trick_done(item)   # cs:608
                self._audience_laugh(pawn, 'big')      # cs:609
            if pcprofile.is_pc() and item.angry_hard:
                # the PC neighbour's one tantrum for a level without the PC
                # data (the tutorials): AngryHard alone
                seq = [item.angry_hard]
            pawn.angry_meter = pawn.angry_max
        elif self.game is not None:
            # the NFH2/Modern anger ladder (Rottweiler.cs:613-693): the
            # meter accumulates AngerAmount per trick, the extra-coin hacks
            # top it up, and only overflow costs a tick — with the freakout,
            # the statue strip and the whistle
            # the coin is credited as the trick action completes — the PC's
            # bar jumps 4-12 s before he leaves a tricked station, at the
            # reaction's start (tools/pcref/amounts.py against the bubble
            # spans of docs/PC_LAPS_DETAIL.md, 2026-09-18); tricks.xml's
            # `time` is a frame of the record's own action, not a credit tick
            if item.pc_credited:
                # paid as the PC's trick action ended (pc_s2_credit)
                overflow = item.pc_credit_overflow
            else:
                overflow = self._s2_credit(pawn, item)
            if item.pc_linked_due and not item.pc_linked_paid:
                # the linked record's tick not reached in the paced stand:
                # it pays with the rest
                self.pc_s2_linked_credit(pawn, item)
            overflow = overflow or item.pc_linked_overflow
            # cs:664 divides by Item.AngerAmount raw: a 0 gives Infinity/NaN
            # in C# float math (neither <= 1 nor <= 2), never the 20 default
            # (Item.cs:392); no shipped item serializes 0
            num = pawn.angry_meter / float(item.anger_amount) \
                if item.anger_amount else float('inf')
            if overflow:
                num = 3.0
            if num <= 1.0:                         # cs:669-673
                seq = [a for a in (item.angry_easy_up,) if a]
                self._hud_angry(1)
            elif num <= 2.0:                       # cs:674-678
                seq = [a for a in (item.angry_easy_up, item.angry_hard) if a]
                self._hud_angry(2)
            elif pawn.angry_meter < pawn.angry_max and not overflow:    # cs:679-683 (the PC credit's overflow may have decayed by the tantrum)
                seq = [a for a in (item.angry_easy_up, item.angry_hard) if a]
                self._hud_angry(3)
            else:                                  # cs:684-692
                ticked = (item.pc_credited and item.pc_credit_overflow) \
                    or item.pc_linked_overflow
                if not ticked:                     # (counted at pc_s2_credit / pc_s2_linked_credit)
                    pawn.angry_count_ticks += 1
                # RandomFreakOut: Range(0,1) is always 0 — RottFreakoutHead
                seq = ['RottFreakoutHead'] \
                    if pawn.anim.has('RottFreakoutHead') else []
                self._hud_angry(3)
                if self.hud is not None and not ticked:
                    if not pcprofile.is_pc():
                        # PlayStatueAchieved; the PC lights the statue with
                        # the last coin instead (_on_trick_done)
                        self.hud.statue_anim.restart()
                    self.hud.play_whistle()
                # GameInfo.OnStatueAchieved sets a flag nothing reads
        if item.object_to_show_before_angry_go is not None:
            self.set_go_renderer(item.object_to_show_before_angry_go, True)
        if item.kind in TRICK_KINDS:               # cs:698-706
            self.play_item_anim(item, item.before_angry)   # PlayBeforeAngry
            # the compound statue/whistle is a Classic-path arm (cs:702:
            # `!Woody.NFH2Path`); Season 2's statue rides the meter overflow
            if item.compound and item.compound_tricked and not nfh2:
                self._on_compound_trick_done(item)
        restart = item.reuse_after_fix             # cs:707-714
        if item.name == 'MumStatueFootStool' and item.tricked:
            item.tricked = False                   # cs:715-718

        def after_run(played_angry=True):
            """the OnAnimationSequenceEnded tail (Rottweiler.cs:454-484):
            FixTrickedItem -> TryFix (cs:460), which nulls TrickedItem before
            the IsPlayingAngryAnimation arm asks CheckRushToToilet (cs:478-
            484, 544) — the animated angry never rushes to the toilet; only
            the AngryWithoutAnimations branch below does (cs:721). A started
            fetch owns the resume"""
            pawn.anim.time_scale = 1.0             # (the profile's reaction pace, below)
            fetch = self._try_fix(item, pawn)
            pawn.can_decrease_angry = True         # Rottweiler.OnUseEnded
            if pcprofile.is_pc() and item.pc_fix_depart and played_angry:
                # the PC's repair walked him to the repaired object (211's
                # sign, 203's generator): his next walk leaves its hotspot
                # (the PCFixSeconds took the walk; _pc_departure_step)
                fx = items.get(item.fix_item_trick) if item.fix_item_trick else None
                cands = [fx, item] + ([routine.item] if routine is not None else [])
                src = next((c for c in cands if c is not None and pawn.zone is not None
                            and c.zone == pawn.zone.pid), None)
                if src is not None:
                    pawn._pc_depart = (float(item.pc_fix_depart[0]), float(item.pc_fix_depart[1]),
                                       pawn.sprite.x, pawn.sprite.y, src)
            if on_done and not fetch:
                on_done()

        if item.angry_without_animations:          # cs:719-736
            # source order: CheckRushToToilet, TryFix, the stop/restart,
            # FixDirectly, OnTrickDone, the meter latch (cs:721-796)
            rush = item.kind in TRICK_KINDS and item.cause_rush_to_toilet(items) \
                and routine is not None
            fetch = self._try_fix(item, pawn)      # a fetch owns the resume
            if on_done and not fetch:
                on_done()
            if item.fix_directly:                  # cs:781-784
                self._fix(item)
            item.pc_linked_due = item.pc_linked_paid = item.pc_linked_overflow = False
            item.pc_linked_amount = None
            if item.pc_done_due:               # booked at play_angry at the latest
                item.pc_done_due = False
                self._pc_trick_done(item)
            if item.pc_credited:
                item.pc_credited = False           # paid already (pc_s2_credit)
            else:
                if not item.dont_get_angry:
                    self._on_trick_done(item)      # cs:785-787
                if self.level_script is not None:
                    self.level_script.on_trick_done()  # cs:789-792
            if rush and not fetch:
                # the run started before the stop in the original (cs:721),
                # so the meter latch of cs:793-796 holds through it — the
                # port starts it after the stop, whose OnUseEnded release
                # (RoutineActionUse.cs:352 -> Rottweiler.cs:891) it follows
                if not nfh2:
                    pawn.can_decrease_angry = False
                routine.move_to_toilet(item.cause_sickness)
            return
        affected = self.pawn_by_pid(item.pawn_to_affect) \
            if item.pawn_to_affect is not None else None
        linked = items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        affect_live = affected is not None \
            and item is not pawn.item_to_ignore_next_time \
            and (not item.pawn_to_affect_only_linked
                 or (linked is not None and linked.tricked))
        if affect_live:                            # cs:737-753
            pawn.item_to_ignore_next_time = item
            self._start_wait_in_fear(pawn, on_done)
            afr = next((r for r in self.routines if r.pawn is affected), None)
            if afr is not None:
                # on PC the co-actor's walk to him is her script's run where
                # it sets her gait to 2 first (the item's PCRunTo:
                # pc_reactions.py RUNTO_S2)
                affected.pc_run_hit = bool(getattr(item, 'pc_run_to', False))
                # the PC's hit: the co-actor's `fight` ticks (PCHitSeconds; the
                # linked flow's own action, PCHitSecondsLinked)
                hs = item.pc_hit_secs
                if linked is not None and linked.tricked and item.tricked \
                        and item.use_tricked_linked and item.pc_hit_secs_linked:
                    hs = item.pc_hit_secs_linked
                affected.pc_hit_secs = (hs or {}).get(affected.role) \
                    if pcprofile.is_pc() else None
                afr.run_to_hit_pawn(pawn)          # Pawn.RunToHitPawn
                oit = afr.item
                if oit is not None and oit.change_item_anim_when_affected \
                        and oit.item_anim_when_affected:
                    p = self.players.get(id(oit.sprite)) if oit.sprite else None
                    if p is not None and p.has(oit.item_anim_when_affected):
                        p.play_directly(oit.item_anim_when_affected)
            if item.fix_directly:                  # cs:781-784
                self._fix(item)
            item.pc_linked_due = item.pc_linked_paid = item.pc_linked_overflow = False
            item.pc_linked_amount = None
            if item.pc_done_due:               # booked at play_angry at the latest
                item.pc_done_due = False
                self._pc_trick_done(item)
            if item.pc_credited:
                item.pc_credited = False           # paid already (pc_s2_credit)
            else:
                if not item.dont_get_angry:
                    self._on_trick_done(item)      # cs:785-787
                if self.level_script is not None:
                    self.level_script.on_trick_done()  # cs:789-792
            if not nfh2:
                pawn.can_decrease_angry = False    # cs:793-796
            return
        # the extra-angry insert, gated for the sand castle (cs:754-766)
        if item.sand_castle_flag:
            if linked is not None and item.tricked and linked.tricked:
                seq = list(item.rott_extra_angry) + seq
        else:
            seq = list(item.rott_extra_angry) + seq
        # the fix animation rides at the tail of the same sequence (cs:767-777)
        fix_seq = []
        if item.can_fix:
            if item.use_fix_sequence:
                fix_seq = list(item.fix_sequence)
            elif not item.fix_without_animations and item.fix_animation:
                fix_seq = [item.fix_animation]
        if not pc_s1:
            seq.extend(fix_seq)
        if item.fix_directly:                      # cs:781-784
            self._fix(item)
        item.pc_linked_due = item.pc_linked_paid = item.pc_linked_overflow = False
        item.pc_linked_amount = None
        if item.pc_done_due:               # booked at play_angry at the latest
            item.pc_done_due = False
            self._pc_trick_done(item)
        if item.pc_credited:
            item.pc_credited = False               # paid already (pc_s2_credit)
        elif not fired_early and not pc_s1:
            if not item.dont_get_angry:
                self._on_trick_done(item)          # cs:785-787
            if self.level_script is not None:
                self.level_script.on_trick_done()  # cs:789-792
        if not nfh2:
            # the meter stops decaying through the angry set — Classic only
            # (`!Woody.NFH2Path`, cs:793-796; Season 2 keeps decaying)
            pawn.can_decrease_angry = False
        seq = [a for a in seq if pawn.anim.has(a)]
        if pc_s1:
            # the PC order: the shout (paced), then the repair (paced to the
            # PC action, none when the PC object has none) — two sequences
            fixes = [a for a in fix_seq if pawn.anim.has(a)]
            fix_secs = item.pc_fix_secs
            if fix_secs is not None and fix_secs <= 0.0:
                fixes = []

            def play_fixes():
                pawn.anim.time_scale = 1.0
                if fixes:
                    if fix_secs:
                        mobile = pawn.anim.sequence_seconds(fixes)
                        if mobile > 0.0:
                            pawn.anim.time_scale = mobile / fix_secs
                    pawn.anim.play_sequence(fixes, on_end=after_run)
                else:
                    if not seq and pawn.anim.seq_end_hook is not None:
                        # nothing to play at all (a flag-3 step with no repair:
                        # 112's skates) — the angry sequence still ends for the
                        # behaviours (Rottweiler.OnAnimationSequenceEnded's
                        # BehaviorOnAnimationSequenceEnded, cs:448: the
                        # RollerSkater's SHOUT state waits for it)
                        pawn.anim.seq_end_hook()
                    after_run(bool(seq))

            if seq:
                mobile = pawn.anim.sequence_seconds(seq)
                if mobile > 0.0 and pc_shout > 0.0:
                    pawn.anim.time_scale = mobile / pc_shout
                pawn.anim.play_sequence(seq, on_end=play_fixes)
            else:
                play_fixes()
            return
        level = None
        both = linked is not None and linked.tricked and item.tricked \
            and bool(item.use_tricked_linked)
        if nfh2 and pcprofile.is_pc():
            shout = getattr(self.level_script, 'pc_shout', None)
            level = shout(pawn, item) if shout is not None else None
            if level is None and both and getattr(item, 'pc_shout_linked', None) is not None:
                # the linked variant's own SHOUT (PCShoutLinked: 202's
                # electrified rail pushes 2 where the crash alone pushes 1)
                level = item.pc_shout_linked
            elif level is None:
                level = getattr(item, 'pc_shout', None)
        if level is not None and seq:
            # the tricked step's own SHOUT and repair (fcn.1000f977: the level
            # picks the action, pcprofile.s2_reaction_seconds — the freakout
            # once the gauge has overflowed; -1 none — no
            # SHOUT in the step, or 201's buffet, whose SHOUT takes the actor
            # for the level, 0x10029a6c), then the repair at its ticks
            # (PCFixSeconds; 0: the step has none — the mobile's fix clips go):
            # the mobile's angry set at the pace of the shout, its fix clips
            # at the repair's, one after the other
            fixes = [a for a in fix_seq if pawn.anim.has(a)]
            head = [a for a in seq if a not in fixes] if level >= 0 else []
            fix_secs = getattr(item, 'pc_fix_secs', None)
            if both and getattr(item, 'pc_fix_secs_linked', None) is not None:
                fix_secs = item.pc_fix_secs_linked     # PCFixSecondsLinked
            if fix_secs is not None and fix_secs <= 0.0:
                fixes = []

            def play_fixes_s2():
                pawn.anim.time_scale = 1.0
                if fixes:
                    if fix_secs:
                        mobile = pawn.anim.sequence_seconds(fixes)
                        if mobile > 0.0:
                            pawn.anim.time_scale = mobile / fix_secs
                    pawn.anim.play_sequence(fixes, on_end=after_run)
                else:
                    after_run(bool(head))

            extra = [a for a in item.rott_extra_angry if a in head] \
                if (resume and item.pc_resume_head_secs is not None) else []

            def play_head():
                pawn.anim.time_scale = 1.0
                rest = [a for a in head if a not in extra]
                if not rest:
                    play_fixes_s2()
                    return
                pc = pcprofile.s2_reaction_seconds(level, random, pawn.pc_rage_full)   # the run's seeded module state
                mobile = pawn.anim.sequence_seconds(rest)
                if mobile > 0.0 and pc > 0.0:
                    pawn.anim.time_scale = mobile / pc
                pawn.anim.play_sequence(rest, on_end=play_fixes_s2)

            if extra:
                # the rest of the linked flow before its SHOUT, after the
                # co-actor's action (PCResumeHeadSeconds: 207's billboard,
                # its `enter` 56 ticks, 0x1001513f)
                mobile = pawn.anim.sequence_seconds(extra)
                if mobile > 0.0 and item.pc_resume_head_secs > 0.0:
                    pawn.anim.time_scale = mobile / item.pc_resume_head_secs
                pawn.anim.play_sequence(extra, on_end=play_head)
            elif head:
                play_head()
            else:
                play_fixes_s2()
        elif seq:
            if nfh2 and pcprofile.is_pc() and getattr(item, 'pc_laugh', None) is not None:
                # an item the lap model has no tricked step for: the reaction
                # clip by the trick record's laugh level (PCLaugh) over the
                # whole angry set
                pc = pcprofile.s2_reaction_seconds(item.pc_laugh, random, pawn.pc_rage_full)   # the run's seeded module state
                mobile = pawn.anim.sequence_seconds(seq)
                if mobile > 0.0 and pc > 0.0:
                    pawn.anim.time_scale = mobile / pc
            pawn.anim.play_sequence(seq, on_end=after_run)
        else:
            after_run(False)

    def _show_objects(self, item):
        """Item.ShowObjects (Item.cs:2662-2674): the MechanicalBull's coins
        and the fuckedup Hatch reveal their linked halves"""
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        rott = self.pawns.get('Rottweiler')
        if item.name == 'MechanicalBull' and linked is not None \
                and rott is not None and not rott.show_coins:
            rott.show_coins = True
            self.set_active(linked, True)
        if item.name == 'Hatch' and item.dexterity and linked is not None:
            # cs:2668 wants Dexterity, which his first Fix sets
            # (HatchFixBehavior, cs:2560): the fish come out on his second
            # fall, after Woody's shards round — not on the carpet's
            item.item_anim_when_angry = 'N2TrickItemIdleFuckedup'
            self.set_active(linked, True)

    def _start_wait_in_fear(self, pawn, resume):
        """Rottweiler.StartWaitInFearAction (cs:827-831) ->
        RoutineActionWaitInFear.OnActionStarted (cs:13-19): pause, postpone
        the alarm and loop the fear pose until the hit lands; the resume is
        parked for ContinueAngryAnimation."""
        routine = next((r for r in self.routines if r.pawn is pawn), None)
        pawn.movement_paused = True
        if routine is not None:
            if routine.state == routine.USING and routine.action is not None \
                    and routine._pending is None:
                # StartWaitInFearAction -> StartUrgentAction -> StartAction
                # stops the use in progress right here (ActionManager.cs:
                # 157-160 -> RoutineAction.StopAction(next), cs:116-120:
                # Active = false, OnActionStopped) — at the tricked use's
                # FIRST StopAction (canPostponeStop: true), not after the
                # angry: the second StopAction(false) only sets Finished and
                # the next StartAction finds the action inactive. Bench,
                # Level205's tennis tricked first (olga.js): Olga unhidden
                # and her parked mutex aborted at 133.03, the WaitInFear's
                # start; nothing at 141.18, the fix's end — so she sits
                # down on the mat at 139.4 hidden and stays, her sequence
                # frozen, until his mat visit drains the item's loop. The
                # port ran OnActionStopped at 141.18: her unhide let her
                # mat animation run out, she left for the tennis park and
                # the two waited for each other for good.
                routine._action_stopped()
                routine._stopped_for_urgent = True
            routine.postpone_alarm()
            routine._wait_in_fear_done = resume
            routine.state = routine.USING
        if pawn.wait_in_fear_anim and pawn.anim.has(pawn.wait_in_fear_anim):
            pawn.anim.play_looping(pawn.wait_in_fear_anim)

    def continue_angry_animation(self, pawn):
        """Pawn.ContinueAngryAnimation -> Rottweiler's override
        (Rottweiler.cs:820-825): the parked angry now plays, against the
        ItemToIgnoreNextTime that blocks a second affect run"""
        item, pawn.item_to_ignore_next_time = pawn.item_to_ignore_next_time, None
        routine = next((r for r in self.routines if r.pawn is pawn), None)
        resume = None
        if routine is not None:
            resume, routine._wait_in_fear_done = \
                routine._wait_in_fear_done, None

        def stopped():
            """RoutineActionWaitInFear.OnActionStopped (cs:21-27) fires when
            the resumed action starts, i.e. after the parked angry has run
            its stop: ContinueMovement, then ContinueAlarm's release of a
            parked alerter run. (The original wires that run's
            OriginalAction to the WaitInFear itself, ActionManager.cs:715-
            718, and replays the fear loop for good afterwards; the port
            resumes the routine.)"""
            if resume:
                resume()
            pawn.movement_paused = False
            if routine is not None:
                routine.continue_alarm()
        if item is None:
            stopped()
            return
        pawn.item_to_ignore_next_time = item       # the gate the re-entry sees
        self.play_angry(pawn, item, on_done=stopped)
        pawn.item_to_ignore_next_time = None       # Rottweiler.cs:824

    def trick_score(self, item):
        """Item.GetTrickScore (Item.cs:2156-2159) and the TrickItem override
        (TrickItem.cs:391-398): a compound-tricked compound item pays
        Item.CompoundTrickScore (L114's Shotgun: 13 over its 10)."""
        if item.kind in TRICK_KINDS and item.compound and item.compound_tricked:
            return item.compound_trick_score_v
        return item.trick_score

    @staticmethod
    def _pc_extra(item, mobile, field='pc_extra_coin'):
        """the NFH2 ladder's hard-coded extra coin: the mobile's amount, or
        under the PC profile the tricks.xml rage of the record it stands
        for (the overlays' PCExtraCoin / PCExtraCoin206 on the item)"""
        if pcprofile.is_pc():
            v = getattr(item, field, None)
            if v is not None:
                return float(v)
        return mobile

    def _would_pay(self, item):
        """the score _on_trick_done is about to pay for this trick, 0 when
        it pays nothing (Item.cs:2121-2154 without the side effects) — the
        PC's `points`, whose zero skips the anger (game.exe fcn.0047bd00)"""
        if self.game is None or item.dont_get_angry:
            return 0
        score = self.trick_score(item)
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        if linked is not None and linked.tricked and item.tricked:
            if item.already_tricked and linked.already_tricked:
                return 0
            return score
        return 0 if item.already_tricked else score

    def _on_trick_done(self, item):
        """Item.OnTrickDone (Item.cs:2121-2154): score once, linked pairs pay
        both; every payment goes through the virtual GetTrickScore, and a
        fresh linked pair with ExtraCoinLinkedTrick pays a second time
        (cs:2143-2146 — L207's SandCastle counts three tricks)."""
        if self.game is None:
            return
        score = self.trick_score(item)
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        if linked is not None and linked.tricked and item.tricked:
            if item.already_tricked and not linked.already_tricked:
                linked.already_tricked = True
                self.game.linked_trick = False
                self.game.trick_done(score)
            elif not item.already_tricked and linked.already_tricked:
                item.already_tricked = True
                self.game.linked_trick = False
                self.game.trick_done(score)
            elif not item.already_tricked and not linked.already_tricked:
                item.already_tricked = True
                linked.already_tricked = True
                self.game.linked_trick = True
                self.game.trick_done(score)
                if item.extra_coin_linked:                # Item.cs:2143-2146
                    if not item.pc_extra_due:
                        self.game.trick_done(score)
                    # (the PC's record for it is done as it pays: the
                    # resume, play_angry)
        elif not item.already_tricked:
            item.already_tricked = True
            self.game.trick_done(score)
        if pcprofile.is_pc() and self.hud is not None \
                and self.game.total > 0 \
                and self.game.completed >= self.game.total:
            # the PC's trophy: the statue lights with the last coin
            self.hud.statue_anim.restart()

    def _tricked_item_to_fix(self, item):
        """TrickItem.GetTrickedItemToFix (TrickItem.cs:1136-1143)"""
        if item.depends_on is not None and item.fix_depends_on:
            dep = self.level.items.get(item.depends_on)
            if dep is not None:
                return dep
        return item

    def _try_fix(self, item, pawn=None):
        """TrickItem.TryFix (TrickItem.cs:1115-1134): fix, or run to the
        fixing tool when one is named and the neighbour's hands are empty,
        or break for good; LetUntrickTrickedItem rides the tail. Returns
        True when the fetch started — the urgent chain then owns the
        resume, and the interrupted action must not advance over it."""
        fetch = False
        if item.can_fix:
            self._fix(item)
        elif item.fixing_item is not None and pawn is not None \
                and pawn.fixing_item is None:
            tool = self.level.items.get(item.fixing_item)
            routine = next((r for r in self.routines if r.pawn is pawn), None)
            if tool is not None and routine is not None:
                routine.run_to_fixing_item(tool, self._tricked_item_to_fix(item))
                fetch = True
            else:
                item.fucked_up = True
        else:
            item.fucked_up = True
        if item.let_untrick and item.set_tricked_on_item is not None:
            tgt = self.level.items.get(item.set_tricked_on_item)
            if tgt is not None:
                tgt.tricked = False
                tgt.got_tricked = True
        return fetch

    def _fix(self, item):
        """Item.Fix / TrickItem.Fix, the state core: the trick is disarmed and
        the item shows its normal idle again (Item.cs:2102, TrickItem.cs:443),
        plus the name-hack arms of both Fix bodies. The UseAtOtherPlace guard
        and the tricked-overlay swap come from TrickItem.Fix (cs:438-446)."""
        # Item.Fix opens by releasing the neighbour's linked-pair anger latch
        # (Item.cs:2065) — the Season 2 meter accumulates again after any fix
        rott = self.pawns.get('Rottweiler')
        if rott is not None:
            rott.tricked_aux = False
        # the Drawing subclass resets and skips its redo (Drawing.cs:30-42)
        if item.kind == 'Drawing':
            item.drawing_current = 1
            self.set_active(item, False)
            item.skip_action = True
            item.drawing_done_cleaning = False
            ru = item.use_anim.get('Rottweiler') or []
            if len(ru) > 1:
                item.use_anim['Rottweiler'] = [ru[1]]
        # the Item.Fix body, in source order (Item.cs:2063-2119)
        self._gold_cup_behavior(item)              # cs:2066
        if item.restart_after_tricked and item.tricked:
            rt = next((r for r in self.routines
                       if r.role == 'Rottweiler'), None)
            if rt is not None and rt.actions:      # StarActionAgain, cs:2365
                rt.index = (rt.index - 1) % len(rt.actions)
        act = self.level.items.get(item.activate_item_after_fix) \
            if item.activate_item_after_fix else None
        if act is not None:                        # ActivateItem, cs:2356-2363
            self.set_active(act, True)
        self._fix_kart_behavior(item)
        self._fix_throne_behavior(item)
        self._fix_bull_behavior(item)
        self._fix_boat_behavior(item)
        self._rabbit_behavior(item)
        if item.name == 'TurbanShop':              # cs:2074-2077
            item.used = False
        if item.name == 'BeerMat' and item.rott_prime_anim:   # cs:2078-2081
            item.rott_prime_anim[0] = 'BeachLayDown'
        if item.name == 'MechanicalBullControls' and item.tricked:
            rt = next((r for r in self.routines
                       if r.role == 'Rottweiler'), None)
            if rt is not None:                     # cs:2082-2085
                rt.index += 2
        self._fix_plant_carnivore(item)            # cs:2086
        self._hatch_fix_behavior(item)             # cs:2087
        self._stop_olga_infinite_loop(item)        # cs:2088
        # FixItemTrickLinked before the Tricked clear (Item.cs:2097-2101)
        fxl = self.level.items.get(item.fix_item_trick_linked) \
            if item.fix_item_trick_linked else None
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        if fxl is not None and linked is not None and linked.tricked \
                and item.tricked:
            fxl.tricked = False
            self._return_to_idle(fxl)
        item.tricked = False                       # cs:2102
        fx = self.level.items.get(item.fix_item_trick) \
            if item.fix_item_trick else None
        if fx is not None:
            fx.tricked = False
            self._return_to_idle(fx)
        if item.block_after_fix:                   # cs:2108-2112
            item.can_undo_trick = False
            item.use_once = True
        if item.use_fixed_strings:                 # cs:2113-2118
            item.name_string = item.name_fixed_string
            item.with_string = item.with_fixed_string
            item.description_string = item.description_fixed
        if item.block_valve_after_fix:             # TrickItem.cs:421-425
            item.required_inventory = 'IT_Balloon'
            item.change_mouse_over_after_trick = True
        # TrickItem.Fix tail (TrickItem.cs:412-455)
        self.call_later(0.3, lambda it=item: self._bbq_dirty(it))
        if item.name == 'Rope' and item.got_tricked:
            item.got_tricked = False
            item.use_once = False
        if item.depends_pig_keys and item.name == 'Pig':
            keys = self.level.items.get(item.pig_keys)
            if keys is not None:
                keys.tricked = False
                keys.primed = False
        if item.fix_all:
            item.tricked = False
            item.primed = False
            item.is_using = False
            item.next_action_after_gramaphone = True   # TrickItem.cs:436
        # a fetched-away item skips the visual tail (TrickItem.cs:438-441)
        if item.use_at_other_place and not item.at_home:
            return
        self.set_tricked_object_hidden(item, True)     # cs:442
        rott = self.pawns.get('Rottweiler')
        if (rott is None or rott.fixing_item is not item) \
                and not item.dont_show_on_fix and item.name != 'Pipe':
            self.set_object_hidden(item, False)        # cs:443-446
        if item.take_off_iron_primed:
            item.primed = False
            item.change_iron_routine = True
            item.change_iron_routine_last_path = True
            if item.name == 'Iron':
                item.use_once = False
        # Item.Fix tail (Item.cs:2089-2095)
        if item.name == 'WaterPuddle':
            item.primed = True
        if item.use_item_multiple_times:
            item.use_once = False
        self._fix_idle_tail(item)                    # TrickItem.cs:457-471

    def _gold_cup_behavior(self, item):
        """Item.GoldCupBehavior (Item.cs:2770-2776)"""
        extra = self.level.items.get(item.extra_item_aux) \
            if item.extra_item_aux else None
        if item.name == 'Polish' and extra is not None and not item.tricked:
            self.set_object_hidden(extra, True)

    def _fix_bull_behavior(self, item):
        """Item.FixBullBehavior (Item.cs:2494-2504)"""
        if not (item.fix_without_animations and item.name == 'LiveBull'):
            return
        if item.use_anim.get('Rottweiler'):
            item.use_anim['Rottweiler'][0] = 'LookRight'
        item.idle = 'N2TrickItemExtra1'
        item.primed = True
        rt = next((r for r in self.routines if r.role == 'Rottweiler'), None)
        if rt is not None and rt.action is not None:
            rt.action['object_to_hide'] = None     # ObjectToHideDuringUse = null

    def _fix_boat_behavior(self, item):
        """Item.FixBoatBehavior (Item.cs:2519-2531): the picnic boat sinks
        for good — both routines lose an action"""
        if not (item.fix_without_animations and item.name == 'BoatPicnic'):
            return
        self.set_active(item, False)
        olga = self.pawns.get('Olga')
        if olga is not None and olga.olga_aux_anim is not None:
            olga.olga_aux_anim.infinite = True
            olga.olga_workout_anim = olga.olga_aux_anim
        rt = next((r for r in self.routines if r.role == 'Rottweiler'), None)
        if rt is not None and len(rt.actions) > 3:
            del rt.actions[3]
            rt.index = max(0, rt.index - 1)
        ort = next((r for r in self.routines if r.role == 'Olga'), None)
        if ort is not None and len(ort.actions) > 1:
            del ort.actions[1]
            ort.index = max(0, ort.index - 1)

    def _rabbit_behavior(self, item):
        """Item.RabbitBehavior (Item.cs:2625-2631)"""
        rabbit = self.level.items.get(item.rabbit_206) \
            if item.rabbit_206 else None
        if item.name == 'LaunchPad' and item.tricked and rabbit is not None:
            self.set_active(rabbit, True)

    def _fix_plant_carnivore(self, item):
        """Item.FixPlantCarnivoreBehavior (Item.cs:2506-2517)"""
        if item.name != 'PlantCarnivore':
            return
        if item.compound_tricked:
            item.compound_tricked = False
        else:
            item.compound_required = 'IT_NONE'

    def _hatch_fix_behavior(self, item):
        """Item.HatchFixBehavior (Item.cs:2550-2579): the first fix turns
        the hatch into its dexterity round, the second writes it off"""
        if item.name != 'Hatch':
            return
        rt = next((r for r in self.routines if r.role == 'Rottweiler'), None)
        if not item.dexterity:
            item.idle = 'N2TrickItemPrimedNormal'
            item.idle_tricked = 'N2TrickItemPrimedNormal'
            if item.use_anim.get('Rottweiler'):
                item.use_anim['Rottweiler'][0] = 'HatchLook'
            if rt is not None and rt.action is not None:
                rt.action['hide_object'] = True
            item.animation = 'TakeOneFrameNFH2Down'
            item.already_tricked = False
            item.dexterity = True
            item.dexterity_trick_item = True
            item.use_once = False
            item.use_tricked_anim['Rottweiler'] = \
                list(item.rott_use_second_tricked)
            # cs:2567-2569: Woody's spot for the round moves 1.5 to the
            # right (onto the hatch itself) and 0.3 lower — the original
            # stands him at (3.14, -2.86) for the shards round and the
            # done pass, the port stood him at (1.65, -2.57) and so walked
            # him down and up again for the pass, 60 frames the original
            # does not spend (replay49)
            item.delta_woody_x = 1.5
            item.woody_delta_use_height = 0.7
        else:
            item.use_once = True
            item.idle = 'N2TrickItemIdleFuckedup'
            if rt is not None and len(rt.actions) > 4:
                del rt.actions[4]
                rt.index = max(0, rt.index - 1)

    def _stop_olga_infinite_loop(self, item):
        """Item.StopOlgaInfiniteLoop (Item.cs:2581-2604): the tricked
        bouquet rewires Olga's shower rage and the toilet delay"""
        if item.name != 'Bouquet' or not item.tricked:
            return
        olga = self.pawns.get('Olga')
        rt = next((r for r in self.routines if r.role == 'Rottweiler'), None)
        ort = next((r for r in self.routines if r.role == 'Olga'), None)
        if olga is not None:
            olga.anim.anim.infinite = False
            if olga.hit_pawn_action.get('sequence') is not None:
                olga.hit_pawn_action['sequence'] = \
                    ['OlgaShipShowerAngry', 'HitPawn']
            olga.delay_toilet_211 = 4.8
        if ort is not None and ort.actions:
            first = self.level.items.get(ort.actions[0]['item']) \
                if ort.actions[0]['item'] else None
            if first is not None:
                first.use_anim['Rottweiler'] = ['LookAround', 'BucketLook']
            ort.index = 0                  # cs:2601-2602
            ort.loop_from_selected = False
        if rt is not None and len(rt.actions) > 1:
            del rt.actions[1]
            rt.index = max(0, rt.index - 1)

    def _bbq_dirty(self, item):
        """TrickItem.BbqDirty (TrickItem.cs:472-480), invoked 0.3 s after Fix"""
        if item.tricked or item.primed or item.name != 'Beer':
            return
        item.idle = 'BBQDirty'
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is not None and p.has('BBQDirty'):
            p.play_single('BBQDirty')

    def _item_anim_completed(self, item, name):
        """TrickItem.OnItemAnimationCompleted (TrickItem.cs:1059-1079): the
        WaterPuddleBehavior head, then the EnterZone / LeaveZone / HoverAnim
        poses always return to idle, the use poses only with AnimateAfterUse."""
        if name is None:
            return
        # TrickItem.WaterPuddleBehavior (cs:1240-1251): the L210 Valve's
        # N2TrickItemExtra1 — its primed pose, played when the Pool's prime
        # chains into it — ends once into the hand-over: the valve's collider
        # off, its ObjectToPrimeWhenPrimed puddle's on, the puddle's
        # PrimedAnimation set to N2TrickItemIdleNormal and played
        if item.name == 'Valve' and name == 'N2TrickItemExtra1' \
                and not item.only_once_water_puddle:
            tgt = self.level.items.get(item.object_to_prime) \
                if item.object_to_prime else None
            if tgt is not None:
                item.only_once_water_puddle = True
                item.clickable = False
                tgt.clickable = True
                tgt.primed_animation = 'N2TrickItemIdleNormal'
                self.search_play(tgt, tgt.primed_animation)
        if name in (item.enter_zone, item.leave_zone, item.hover_anim):
            self._return_to_idle(item)                   # cs:1062-1073
        elif item.animate_after_use and \
                name in (item.use_normal, item.use_tricked_single):
            self._return_to_idle(item)                   # cs:1074-1077

    def _start_item_animations(self):
        """The Item family's Start-time animation calls, per item in the
        original's order. Item.Start's SetPrimed(Primed) (Item.cs:697) is
        overridden by TrickItem to play the primed pose while Primed —
        PrimedFuckedUp under FuckedUp, else PlayPrimedAnimation
        (TrickItem.cs:996-1010, 483-493); the subclass Start then follows:
        TrickItem.Start's ReturnToIdleAnimation unless DontPlayIdleOnStart
        (TrickItem.cs:214-217; Drawing/Rake/Toilet/Television inherit it),
        SearchItem.Start's PlayItemAnimation(FullAnimation) (SearchItem.cs:
        91-107), HideItem.Start's PlayAnimationDirectly(IdleAnim) (HideItem
        .cs:24-30); Alerter.Start's SleepSequence is AlerterFSM's
        constructor, a Door's idle the loader's (scene.py _add_sprite).
        Each play is the controller's first SetAnimation — before it the
        controller has no CurrentAnimation and draws nothing (Animation
        ControllerBase.cs:13, 172-189), and one that nothing here plays
        (IdleNormal NONE, Animating false — TrickItem.cs:1020, a NONE
        FullAnimation) stays that way until a later play. The dispatch is
        the runtime's own: play_item_anim's UseAnimationType / Looping /
        single split (TrickItem.cs:1028-1039), search_play's Looping flag
        (SearchItem.cs:75-82) — so a Single-typed idle under
        UseAnimationType plays once and parks (L205 SandSculpture, L208
        Snake) instead of looping."""
        for it in self.level.items.values():
            p = self.players.get(id(it.sprite)) if it.sprite else None
            if p is None:
                continue
            if it.kind in TRICK_KINDS:
                if it.primed:                            # TrickItem.cs:999-1009
                    if it.fucked_up:
                        self.play_item_anim(it, it.primed_fucked_up)
                    else:
                        self._play_primed_animation(it)
                if not it.dont_play_idle_on_start:       # TrickItem.cs:214-217
                    self._return_to_idle(it)
            elif it.kind == 'SearchItem':                # SearchItem.cs:106
                self.search_play(it, it.full_animation)
            elif it.kind == 'HideItem':                  # HideItem.cs:26-29
                if it.hide_idle and p.has(it.hide_idle):
                    p.play_directly(it.hide_idle)

    def _return_to_idle(self, item):
        """TrickItem.ReturnToIdleAnimation (TrickItem.cs:696-731): the
        FuckedUp pose, the IgnoreDependsOnWhenFixed escape, the primed hold,
        and the idle SEQUENCES where the flags ask (the Pig, the Airer, the
        bull, the carnivore, the parrot ledge)"""
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None or not item.animating:
            return
        if item.fucked_up:
            # cs:699-702: the broken pose (L103's CakeDead, L107's
            # MumStatueBroken, L110's CarnivorPlantDead / BBQDirty)
            self.play_item_anim(item, item.idle_fucked_up)
            return
        tricked = item.is_tricked(self.level.items)
        # cs:703: a fixed item with IgnoreDependsOnWhenFixed idles normally
        # even while its dependency stays tricked
        if not item.tricked and item.ignore_depends_when_fixed:
            tricked = False
        if tricked:
            self._play_idle_tricked_anim(item)          # cs:717-720
            return
        if item.primed and item.force_primed_on_start:
            return          # TrickItem.cs:705: hold the primed pose instead
        if item.play_idle_normal_seq:                   # cs:707-714
            seq = [a for a in item.idle_normal_sequence if p.has(a)]
            if seq:
                p.play_sequence(seq)
            return
        # PlayItemAnimation(IdleNormal): the UseAnimationType /
        # Looping-flag play modes, the HideWhenNotAnimating unhide, and the
        # NONE hide (cs:709, 1018-1050) — a plain PlaySingle froze the
        # UseAnimationType items' looping idles on their last frame
        self.play_item_anim(item, item.idle)

    def _play_idle_tricked_anim(self, item):
        """TrickItem.PlayIdleTrickedAnim (TrickItem.cs:723-732): the single
        IdleTricked through PlayItemAnimation, or the IdleTrickedSequence."""
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None:
            return
        if not item.play_idle_tricked_seq:
            self.play_item_anim(item, item.idle_tricked)
            return
        seq = [a for a in item.idle_tricked_sequence if p.has(a)]
        if seq:
            p.play_sequence(seq)

    def _play_primed_animation(self, item):
        """TrickItem.PlayPrimedAnimation (TrickItem.cs:483-493): PrimedTricked
        while IsTricked() and it exists, else PrimedNormal — both through
        PlayItemAnimation."""
        if item.is_tricked(self.level.items) and item.primed_tricked:
            self.play_item_anim(item, item.primed_tricked)
        else:
            self.play_item_anim(item, item.primed_normal)

    def _fix_idle_tail(self, item):
        """TrickItem.Fix's pose tail (TrickItem.cs:457-471): a still-primed
        item replays its primed pose instead of the idle (the re-primed
        WaterPuddle, Item.cs:2089-2092); the ElectricTrap disables its
        controller for good instead — nothing draws or advances it again
        (its UseOnce keeps every re-play path shut in the shipped data)."""
        if item.name == 'ElectricTrap':
            if item.sprite is not None:
                item.sprite.hidden = True                # cs:468-471
            return
        if not item.primed:
            self._return_to_idle(item)                   # cs:459-462
        else:
            self._play_primed_animation(item)            # cs:463-466

    def pawn_by_pid(self, pid):
        """resolve a serialized Pawn-component reference to the live pawn"""
        for role, spec in self.level.pawns.items():
            if spec.get('pid') == pid:
                return self.pawns.get(role)
        return None

    def play_use_item_anim(self, item, on_end=None):
        """TrickItem.PlayUseAnimation (TrickItem.cs:982-994): the item's own
        normal-use pose — the single UseNormal, or the UseNormalSequence
        with the caller's sequence-ended delegate (PlayAnimationSequence's
        AlternateOnSequenceEnded, AnimationControllerBase.cs:312-316; Olga's
        use passes Olga.OnItemAnimationSequenceEnded, TrickItem.cs:972).
        The AnimateDependant echo is unused by the shipped use flows."""
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None:
            return
        if not item.play_use_normal_seq:
            self.play_item_anim(item, item.use_normal)
            return
        seq = [x for x in item.use_normal_sequence if p.has(x)]
        if seq:
            if pcprofile.is_pc() and (item.pc_item_clip_secs or item.pc_cut_pending):
                # the item's own clips at the PC's ticks while another role
                # uses it hidden (PCItemClipSeconds: 205's mat under Olga);
                # a use the PC's script has already called off passes at once
                # (every clip skipped: 205's first mat, the `pingpong` come
                # before she lay down)
                if item.pc_cut_pending:
                    item.pc_cut_pending = False
                    p.clip_pace = {x: 0.0 for x in seq}
                else:
                    p.clip_pace = dict(item.pc_item_clip_secs)
                inner = on_end

                def on_end():
                    p.clip_pace = None
                    p.time_scale = 1.0
                    if inner is not None:
                        inner()
            p.play_sequence(seq, on_end=on_end)

    def play_tricked_item_anim(self, item, pawn=None):
        """TrickItem.PlayTrickedAnimation (TrickItem.cs:947-962): the single
        UseTricked — gated by DontUseOn — or the UseTrickedSequence."""
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None:
            return
        if not item.play_use_tricked_seq:
            if item.dont_use_on is None or \
                    (pawn is not None
                     and self.pawn_by_pid(item.dont_use_on) is not pawn):
                self.play_item_anim(item, item.use_tricked_single)
            return
        seq = [x for x in item.use_tricked_sequence if p.has(x)]
        if seq:
            p.play_sequence(seq)

    def check_destroy_when_tricked(self, item):
        """TrickItem.CheckDestroyWhenTricked (TrickItem.cs:656-665): a
        DestroyAfterUseTricked item vanishes and leaves the notice lists"""
        if not item.destroy_after_use_tricked:
            return
        self.set_object_hidden(item, True)
        self.set_tricked_object_hidden(item, True)
        if item.notice_enter:
            lst = self.notice_items.get(item.zone)
            if lst and item in lst:
                lst.remove(item)
        if item.notice_near:
            lst = self.near_items.get(item.zone)
            if lst and item in lst:
                lst.remove(item)

    def play_item_anim(self, item, name, _echo=False):
        """TrickItem.PlayItemAnimation (TrickItem.cs:1018-1050): a no-op
        unless Animating; NONE hides a HideWhenNotAnimating item; the type
        comes from UseAnimationType / Looping. AnimateDependant echoes the
        same state onto the item's Dependant — whoever names it in
        DependsOn (Start's back-link, cs:218-220); L110's Beer and L113's
        valves carry it."""
        if item.animating:
            p = self.players.get(id(item.sprite)) if item.sprite else None
            if name:
                if item.hide_when_not_animating and item.sprite is not None:
                    item.sprite.hidden = False
                if p is not None and p.has(name):
                    if item.use_anim_type:
                        p.play_directly(name)
                    elif item.looping_flag:
                        p.play_looping(name)
                    else:
                        p.play_single(name)
            elif item.hide_when_not_animating and item.sprite is not None:
                item.sprite.hidden = True
        if name and not _echo and getattr(item, 'animate_dependant', False):
            dep = next((i for i in self.level.items.values()
                        if i.depends_on == item.pid), None)
            if dep is not None:
                self.play_item_anim(dep, name, _echo=True)

    def search_play(self, it, name):
        """SearchItem.PlayItemAnimation (SearchItem.cs:68-89): unhide and
        play by the Looping flag, or hide a HideWhenNotAnimating item."""
        p = self.players.get(id(it.sprite)) if it.sprite else None
        if name:
            if p is not None and p.has(name):
                it.sprite.hidden = False       # SetObjectHidden(false)
                if it.looping_flag:
                    p.play_looping(name)
                else:
                    p.play_single(name)
        elif it.hide_when_not_animating and it.sprite is not None:
            it.sprite.hidden = True

    def _search_switch(self, it):
        """SearchItem.Update's four-state animation switcher
        (SearchItem.cs:214-244): each Tricked x Primed combination plays its
        animation once, re-arming the other three states."""
        if it.aux1 and it.tricked and it.primed:
            it.aux1 = False; it.aux2 = it.aux3 = it.aux4 = True
            self.search_play(it, it.empty_animation)
        elif it.aux2 and it.tricked and not it.primed:
            it.aux2 = False; it.aux1 = it.aux3 = it.aux4 = True
            self.search_play(it, it.tricked_animation)
        elif it.aux3 and not it.tricked and it.primed:
            it.aux3 = False; it.aux1 = it.aux2 = it.aux4 = True
            self.search_play(it, it.primed_animation)
        elif it.aux4 and not it.tricked and not it.primed:
            it.aux4 = False; it.aux1 = it.aux2 = it.aux3 = True
            self.search_play(it, it.full_animation)

    def play_alert_animation(self, item):
        """TrickItem.PlayAlertAnimation (TrickItem.cs:1150-1162): the ring
        pose, the collider, and the Football's CanUse name-hack."""
        self.play_item_anim(item, item.alert_animation)
        if item.enable_collider_when_alerted:
            item.clickable = True
            if item.name == 'Football':
                item.can_use = True

    def set_active(self, item, active):
        """GameObject.SetActive, approximated to what the port models: the
        renderer and the click collider follow the flag."""
        if item.sprite is not None:
            item.sprite.hidden = not active
        q = self.level.quads_by_go.get(item.go) if item.go is not None else None
        if q is not None:
            q['active'] = active
        item.clickable = active
        item.active = active
        if active:
            item.started = True          # Start runs on its first active frame

    def set_go_renderer(self, go, enabled):
        """Renderer.enabled on a bare object: its backdrop quad or sprite"""
        q = self.level.quads_by_go.get(go)
        if q is not None:
            q['renderer_enabled'] = enabled
            return
        for s in self.level.sprites:
            if s.go == go:
                s.hidden = not enabled
                return

    def set_go_active(self, go, active):
        """GameObject.SetActive on a bare object: the quad's active flag or
        the sprite's visibility"""
        q = self.level.quads_by_go.get(go)
        if q is not None:
            q['active'] = active
            return
        for s in self.level.sprites:
            if s.go == go:
                s.hidden = not active
                return

    def open_search_furniture(self, item):
        """SearchItem.PreUse (SearchItem.cs:125-152): the open-state object
        shows for the search; SetCloseTime — only on a SearchingItem — picks
        1.5 s, or 1 s once a take has landed (AcquiredInventoryCount > 0).
        The 19 SearchingItem=False openers (the pin boards, the toilet-paper
        holders, the bins, the mobile, the soil bag, L201's soap chest) open
        and never close: Update's tail returns for them (cs:252)."""
        if item.open_object is None and item.open_render_object is None:
            return
        if item.open_object is not None:
            self.set_go_active(item.open_object, True)
        else:
            self.set_go_renderer(item.open_render_object, True)
        if not item.searching_item:
            return
        item.close_time = 1.0 if item.acquired_inventory_count > 0 else 1.5
        if item not in self._open_furniture:
            self._open_furniture.append(item)

    def _tick_open_furniture(self, dt):
        """SearchItem.Update's closing tail (SearchItem.cs:250-268)"""
        for item in self._open_furniture[:]:
            item.close_time -= dt
            if item.close_time >= 0.0:
                continue
            self._open_furniture.remove(item)
            if item.open_object is not None and item.name != 'ToolBox' \
                    and not item.leave_toolbox_open:
                self.set_go_active(item.open_object, False)
            elif item.open_render_object is not None:
                self.set_go_renderer(item.open_render_object, False)

    def set_object_hidden(self, item, hidden):
        """Item.SetObjectHidden (Item.cs:1984-1995): the object's own
        renderer — a backdrop quad on the static items — and its controller"""
        if item.sprite is not None:
            item.sprite.hidden = hidden
        if item.go is not None:
            q = self.level.quads_by_go.get(item.go)
            if q is not None:
                q['renderer_enabled'] = not hidden

    def set_tricked_object_hidden(self, item, hidden):
        """TrickItem.SetTrickedObjectHidden (TrickItem.cs:400-410): the
        overlay's renderer, and for a ground trick the overlay's BoxCollider
        rides along (cs:405-407). That collider is the click surface of the
        GroundItem(s) living on the overlay object (57 Ground/GroundMarbles
        tricks, 107 colliders — all shipped disabled), so their clickability
        follows the overlay: the slippery patch only answers the raycast
        while the trick lies on the floor. GetComponent<BoxCollider> is
        the first collider only, but every Item on that object resolves to
        that same first collider (Item.cs:1260/1328, the raycast's
        GetComponent("Item")), which is what the port's per-item boxes are."""
        if item.tricked_object_go is None:
            return
        self.set_go_renderer(item.tricked_object_go, not hidden)
        if item.is_ground_trick:
            for other in self.level.items.values():
                if other.go == item.tricked_object_go \
                        and other.collider is not None:
                    other.clickable = not hidden

    def set_active_object_hidden(self, item, hidden):
        """Item.SetActiveObjectHidden + the TrickItem override that prefers
        the tricked overlay while tricked (Item.cs:1964-1967,
        TrickItem.cs:495-505)"""
        if item.kind in TRICK_KINDS and item.tricked \
                and item.tricked_object_go is not None:
            self.set_tricked_object_hidden(item, hidden)
        else:
            self.set_object_hidden(item, hidden)

    def set_child_renderers_hidden(self, item, hidden):
        """Item.SetChildRendererHidden (Item.cs:1969-1978): the first child
        renderer, plus the second once tricked"""
        goes = item.child_renderers[:2 if item.tricked else 1]
        for go in goes:
            if go is not None:
                self.set_go_renderer(go, not hidden)

    def unlock_door(self, door):
        """Door.Unlock (Door.cs:198-207): the alternate idle takes over. The
        zone graph does NOT change: Zone.Neighbors is built once by
        ZoneController.Start from (!Locked || TemporalLock) doors
        (ZoneController.cs:8-28) and Zone.AddNeighbor has no other caller —
        a door unlocked at runtime is crossed only by a direct own-zone
        click, never by the path search. (Only the Intro scenes ship
        TemporalLock doors; the playable levels' DoorsToUnlock — L201's
        TransitionDownwards — target a door that is not locked to begin
        with.)"""
        if not door.locked:
            return
        door.locked = False
        door.use_alternate_idle = True
        # door.sprite already IS the AnimPlayer (wired in World.__init__)
        p = door.sprite
        if p is not None and door.alternate_idle and p.has(door.alternate_idle):
            p.play_looping(door.alternate_idle)

    def check_final_position(self, pawn, item):
        """Rottweiler.CheckFinalPosition (Rottweiler.cs:1241-1291): the
        normal / tricked / linked-tricked stand shifts, exact or relative,
        with the NormalPosAux one-shot."""
        if item is None:
            return
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        fx, fy = item.final_normal
        if (fx or fy) and not item.tricked and not pawn.normal_pos_aux:
            if item.exact_normal:
                pawn.sprite.x, pawn.sprite.y = fx, fy
            else:
                pawn.sprite.x += fx
                pawn.sprite.y += fy
            pawn.pos_snap = True
            return
        fx, fy = item.final_linked
        if (fx or fy) and linked is not None and linked.tricked \
                and item.tricked:
            pawn.normal_pos_aux = True
            if item.exact_linked:
                pawn.sprite.x, pawn.sprite.y = fx, fy
            else:
                pawn.sprite.x += fx
                pawn.sprite.y += fy
            pawn.pos_snap = True
            return
        fx, fy = item.final_tricked
        if (fx or fy) and item.tricked and \
                (linked is None or not linked.tricked):
            pawn.normal_pos_aux = True
            if item.exact_tricked:
                pawn.sprite.x, pawn.sprite.y = fx, fy
            else:
                pawn.sprite.x += fx
                pawn.sprite.y += fy
            pawn.pos_snap = True

    def icon_pressed(self, entry):
        """Item.OnIconPressed (Item.cs:2176-2199), polled every frame by
        HUD.DrawInventory on the CurrentInventory's item (HUD.cs:944): the
        phones raise the alarm instead and answer false, which deselects
        the icon; true keeps it selected. Gated on !IsPassingDoor() &&
        !DonePassingToOtherZone (cs:2178)."""
        src = self.level.items.get(entry.get('item')) \
            if entry.get('item') else None
        w = self.woody
        if src is None or w is None:
            return True
        if not w.is_warping and not w.done_passing:
            if src.cause_alarm:
                if src.last_alarm_time is None or \
                        self.time - src.last_alarm_time > src.cause_alarm_interval:
                    w.steps = []
                    w.state = w.IDLE               # Woody.Stop
                    src.last_alarm_time = self.time
                    if src.direct_use and w.anim.has(src.direct_use):
                        w.anim.play_single(src.direct_use)
                    self.call_later(src.action_duration,
                                    lambda s=src: self._raise_alarm(s))
                return False
            if src.wake_alerter_flag:
                if src.direct_use and w.anim.has(src.direct_use):
                    w.anim.play_single(src.direct_use)
                for fsm in self.alerters.values():
                    fsm.wake_up()                  # GameInfo.Alerter.WakeUp
                return False
        return True

    def _raise_alarm(self, src):
        """Item.RaiseAlarm (Item.cs:2201-2205) + Rottweiler.OnAlarmRaised
        (Rottweiler.cs:1036-1045): run to the alarm item and answer it, or
        park the alarm when passing a door or postponed."""
        alarm = self.level.items.get(src.alarm_item) if src.alarm_item else None
        if alarm is None:
            return
        rt = next((r for r in self.routines if r.role == 'Rottweiler'), None)
        if rt is not None:
            # (the DonePassingToOtherZone term is Woody-only, Pawn.cs:319)
            if not rt.pawn.is_warping and not rt.is_alarm_postponed():
                rt.move_to_alarm(alarm)
            else:
                rt.pending_alarm = alarm         # PendingAlarm/PendingAlarmItem
        self.play_item_anim(alarm, alarm.alarm_animation)

    def _phone_behavior(self, item):
        """Item.PhoneBehavior (Item.cs:2429-2448), run from Woody's use tail
        (Woody.cs:428): a tricked CauseAlarmWhenTrickItem item re-raises the
        alarm or wakes the pet."""
        if not item.tricked or not item.cause_alarm_when_trick:
            return
        if item.cause_alarm:
            if item.last_alarm_time is None or \
                    self.time - item.last_alarm_time > item.cause_alarm_interval:
                if self.woody is not None:
                    self.woody.steps = []
                    self.woody.state = self.woody.IDLE     # Woody.Stop
                item.last_alarm_time = self.time
                self.call_later(item.action_duration,
                                lambda s=item: self._raise_alarm(s))
        elif item.wake_alerter_flag:
            for fsm in self.alerters.values():
                fsm.wake_up()

    def _kart_behavior(self, item):
        """Item.KartBehavior (Item.cs:2638-2644)"""
        olga = self.pawns.get('Olga')
        if item.name == 'PullKart' and item.tricked and olga is not None \
                and olga.anim.has('RickshawWaitManip'):
            olga.anim.play_single('RickshawWaitManip')

    def _fix_kart_behavior(self, item):
        """Item.FixKartBehavior (Item.cs:2646-2652)"""
        olga = self.pawns.get('Olga')
        if item.name == 'PullKart' and item.tricked and olga is not None \
                and olga.anim.has('RickshawWait'):
            olga.anim.play_single('RickshawWait')

    def _captain_door_behavior(self, item):
        """Item.CaptainDoorBehavior (Item.cs:2606-2623): the tricked door
        activates its two replacements and retargets every CaptainDoor
        action at ExtraItem"""
        if item.name != 'CaptainDoor' or not item.tricked:
            return
        item.clickable = False
        for pid in (item.captain_door_1, item.captain_door_2):
            d = self.level.door_by_pid(pid) if pid else None
            if d is None:
                continue
            # gameObject.SetActive(true) (cs:2614-2615): the DisableOnStart
            # pair (Door.cs:63-66) comes back — its collider answers the
            # raycast (Level._hit_at) and LinkNodes finds it between Zone03
            # and Zone05 again (Level.find_path), so the cabin opens for
            # Woody's click and the neighbour's retargeted action
            d.disabled = False
            if d.sprite is not None:
                # d.sprite is the door's AnimPlayer (World.__init__); the
                # drawn Sprite hangs under it, as the DisableOnStart hide
                # at load (above, `d.sprite.sprite.hidden = True`)
                d.sprite.sprite.hidden = False
        rt = next((r for r in self.routines if r.role == 'Rottweiler'), None)
        if rt is not None and item.extra_item:
            for a in rt.actions:
                a_it = self.level.items.get(a['item']) if a['item'] else None
                if a_it is not None and a_it.name == 'CaptainDoor':
                    a['item'] = item.extra_item

    def _throne_behavior_212(self, item):
        """Item.ThroneBehavior212 (Item.cs:2450-2469): the two thrones
        alternate their colliders and play the linked-tricked pose"""
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        if not (item.name in ('AztecThrone', 'AztecThrone2')
                and (self.level.objs.get(str(item.pid), {}).get('data', {})
                     .get('Throne212Behavior'))):
            return
        item.use_once = True
        if linked is not None:
            linked.use_once = True
            linked.clickable = True
        item.clickable = False
        if linked is not None and item.tricked and linked.tricked:
            if item.name == 'AztecThrone':
                self.play_item_anim(item, item.idle_linked_tricked)
            else:
                self.play_item_anim(linked, linked.idle_linked_tricked)

    def _fix_throne_behavior(self, item):
        """Item.FixThroneBehavior (Item.cs:2471-2492)"""
        if item.name not in ('AztecThrone', 'AztecThrone2'):
            return
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        item.clickable = True
        item.use_once = False
        if linked is not None:
            linked.clickable = False
            linked.use_once = False
        if linked is not None and linked.tricked:
            item.idle = 'N2TrickItemExtra1'
            self.play_item_anim(item, item.idle)
        else:
            act = self.level.items.get(item.activate_item_trick) \
                if item.activate_item_trick else None
            if act is not None:
                act.tricked = False
                self.play_item_anim(act, act.idle)

    def _plant_carnivore_behavior(self, item):
        """Item.PlantCarnivoreBehavior (Item.cs:2541-2548)"""
        if item.name == 'PlantCarnivore':
            item.compound_required = 'IT2_Piranha'

    def _fifi_bone_behavior(self, item):
        """Item.FifiBoneBehavior (Item.cs:2762-2768): the held bone at the
        unprimed basket plays the beg pose"""
        used = self.inventory.used
        if item.name == 'DogBasket' and used is not None \
                and used.get('item') is not None \
                and used.get('type') == 'IT2_Bone' and not item.primed:
            p = self.players.get(id(item.sprite)) if item.sprite else None
            if p is not None and p.has('N2TrickItemExtra2'):
                p.play_directly('N2TrickItemExtra2')

    def rott_hear_alerter(self, fsm, triggered_by_woody):
        """the CoRoutineRottweilerHearAlerter target"""
        rott = self.pawns.get('Rottweiler')
        routine = next((r for r in self.routines if r.pawn is rott), None)
        if routine is not None:
            routine.hear_alerter(fsm.item, triggered_by_woody)

    def woody_see_alerter(self, item):
        """Woody.SeeAlerter -> PlayShortFearAnimation: velocity zeroed, stand,
        PauseMovement — the path survives, movement halts. When the blocking
        FearShort ends, Woody.OnBlockingAnimationEnded runs RestartMovement:
        the stored move goes inert and movement unblocks (Woody.cs:317-320,
        Pawn.StopMovement/ContinueMovement)."""
        w = self.woody
        if w is None:
            return
        # a use animation in flight postpones the flinch until it ends
        # (Woody.SeeAlerter, Woody.cs:1033-1044; released in Update, cs:232)
        if w.animations_in_progress:
            w.postponed_alerter = item
            return
        # `!Frozen && alerter.Zone == Zone` (Woody.cs:1040): Frozen is the
        # dexterity snap (DexterityComponent.cs:172) and FinishGame's freeze
        # (GameInfo.cs:364), which the port carries as game.ending
        if w.frozen or self.game.ending:
            return
        if w.zone is None or w.zone.pid != item.zone:
            return
        w.movement_paused = True
        left = item.x < w.sprite.x
        fear = 'FearLeftShort' if left else 'FearRightShort'

        def restart_movement():
            w.steps = []
            w._step = None
            w.state = w.IDLE
            w.movement_paused = False
            # OnBlockingAnimationEnded parks him in the fear loop until the
            # next click (Woody.cs:343-353)
            rep = 'FearLeftRepeat' if left else 'FearRightRepeat'
            if w.anim.has(rep):
                w.anim.play_looping(rep)
            else:
                st = w._stand_name()
                if st:
                    w.anim.play_looping(st)
        if w.anim.has(fear):
            # PlayShortFearAnimation is a PlaySingleAnimation (Woody.cs:1005)
            w.anim.play_sequence([fear], on_end=restart_movement,
                                 as_sequence=False)
        else:
            restart_movement()

    def on_pawn_zone_changed(self, pawn, old_zone_pid):
        """zone-crossing hooks: the alerter left behind calms down
        (Rottweiler.WarpThroughDoor), the new zone may raise alarms
        (Rottweiler.OnChangeZone). Returns True when the zone change took the
        pawn over, mirroring OnChangeZone's return."""
        self.crab_animations(pawn, pawn.zone.pid if pawn.zone else None,
                             old_zone_pid)
        # Pawn.ChangeZone: CrabAnimations, then ElephantAnimations (Pawn.cs:1528-1529)
        self.elephant_animations(pawn, pawn.zone.pid if pawn.zone else None)
        if pawn.role == 'Woody' and self.level_script is not None \
                and pawn.zone is not None:
            # the tutorial's zone signal (Pawn.cs:1592-1595)
            self.level_script.on_woody_zone_entered(pawn.zone.pid)
        if pawn.role != 'Rottweiler':
            return False
        for fsm in self.alerters.values():
            if fsm.item.zone == old_zone_pid:
                fsm.on_rottweiler_leave()
        routine = next((r for r in self.routines if r.pawn is pawn), None)
        if routine is not None:
            return routine.on_zone_changed()
        return False

    def door_exit_catch(self):
        """Pawn.HasNeighborCaughtWoody / HasMotherCaughtWoody
        (Pawn.cs:366-388) — the door-exit and zone-crossing catch check.
        Unlike GameInfo's per-frame predicate it has NO sneaking escape and
        no Bed arm: sneaking past a blocking neighbour does not survive the
        frame a pass ends on."""
        woody = self.woody
        if woody is None or self.game.ending or self.game.got_caught:
            return False
        if pcprofile.is_pc() and pcprofile.s2_sight(woody.nfh2):
            # the PC has one catch, the level tick's watch predicate
            # (_pc_s2_sees): the crossing check reads it as well
            for role in ('Rottweiler', 'Mother'):
                p = self.pawns.get(role)
                if p is not None and self._pc_s2_sees(p) \
                        and not self._pc_catch_barred():
                    self._catch(p)
                    return True
            return False
        rott = self.pawns.get('Rottweiler')
        if rott is not None and woody.zone is not None \
                and rott.zone is not None \
                and woody.zone.pid == rott.zone.pid \
                and not woody.is_warping and not rott.is_warping \
                and not rott.ignore_woody and not woody.hiding \
                and not rott.anim.blocking and not rott.is_sleeping \
                and not woody.anim.blocking and not woody.done_passing \
                and not rott.passing_complex and not woody.passing_complex:
            self._catch(rott)
            return True
        mother = self.pawns.get('Mother')
        if mother is not None and woody.zone is not None \
                and mother.zone is not None \
                and woody.zone.pid == mother.zone.pid \
                and not woody.is_warping and not mother.is_warping \
                and not mother.ignore_woody and not woody.hiding \
                and not mother.anim.blocking and not mother.is_sleeping \
                and woody.at_zone_y() \
                and not woody.anim.blocking and not woody.done_passing \
                and not mother.done_passing \
                and not mother.passing_complex and not woody.passing_complex:
            self._catch(mother)
            return True
        return False

    def crab_animations(self, pawn, new_zone_pid, old_zone_pid):
        """Pawn.CrabAnimations (Pawn.cs:1560-1596), run on every zone change
        of Woody or the Rottweiler. The SearchItem crabs play INVERTED zone
        animations — entering their zone hides them (the LeaveZone strip),
        leaving un-hides and plays EnterZone (SearchItem.cs:275-293). NFH2
        adds a second TrickItem pass gated on !Primed."""
        if pawn.role not in ('Woody', 'Rottweiler'):
            return
        # SearchItem.PlayFullanimationZoneEnter / Leave (SearchItem.cs:
        # 275-293) go through SearchItem.PlayItemAnimation — no Animating
        # gate, an unconditional unhide, the Looping flag (cs:68-89) — not
        # the TrickItem twin (Animating is TrickItem-only, TrickItem.cs:54)
        for it in self._zone_items.get(new_zone_pid, ()):
            if it.kind == 'SearchItem' and it.enter_zone \
                    and not it.is_tricked(self.level.items):
                self.search_play(it, it.leave_zone)
        for it in self._zone_items.get(old_zone_pid, ()):
            if it.kind == 'SearchItem' and it.leave_zone and not it.tricked:
                if it.sprite is not None:
                    it.sprite.hidden = False       # AnimController.Hidden
                self.search_play(it, it.enter_zone)
        if self.woody is not None and self.woody.nfh2:
            for it in self._zone_items.get(old_zone_pid, ()):
                if it.kind in TRICK_KINDS and it.leave_zone and not it.primed:
                    self._play_zone_leave(it)         # Pawn.cs:1577-1583
            for it in self._zone_items.get(new_zone_pid, ()):
                if it.kind in TRICK_KINDS and it.enter_zone and not it.primed:
                    self._play_zone_enter(it)         # Pawn.cs:1584-1590

    def _play_zone_enter(self, it):
        """TrickItem.PlayZoneEnter (TrickItem.cs:1095-1101): gated on
        IsTricked(), through PlayItemAnimation (UseAnimationType keeps the
        strip's own Looping type — L110's BBQFullSmoke loops)"""
        if not it.is_tricked(self.level.items):
            self.play_item_anim(it, it.enter_zone)

    def _play_zone_leave(self, it):
        """TrickItem.PlayZoneLeave (TrickItem.cs:1103-1113): gated on the raw
        Tricked flag, unhides first, then PlayItemAnimation(LeaveZone)"""
        if not it.tricked:
            if it.sprite is not None:
                it.sprite.hidden = False           # AnimController.Hidden
            self.play_item_anim(it, it.leave_zone)

    def elephant_animations(self, pawn, new_zone_pid):
        """Pawn.ElephantAnimations (Pawn.cs:1536-1558), run on every
        ChangeZone: while Woody.ItemBehavior (L208's AngryElephant) is primed
        and Woody changes to a zone that is not the elephant's, the elephant
        plays its primed-then-idle pair (tricked or normal), its
        ObjectToPrimeWhenPrimed — the SafetyLine — locks again, and the
        ElephantBehaviorAux latch stops the repeat until the Mouse arm of
        CanWoodyUse re-arms it (Item.cs:1581)."""
        if pawn.role != 'Woody':
            return
        spec = self.level.pawns.get('Woody') or {}
        eb = self.level.items.get(spec.get('item_behavior')) \
            if spec.get('item_behavior') else None
        if eb is None or new_zone_pid == eb.zone or eb.elephant_behavior_aux:
            return
        if eb.name != 'AngryElephant' or not eb.primed:
            return
        eb.elephant_behavior_aux = True
        pair = ['N2TrickItemPrimedTricked', 'N2TrickItemIdleTricked'] \
            if eb.tricked else ['N2TrickItemPrimedNormal', 'N2TrickItemIdleNormal']
        p = self.players.get(id(eb.sprite)) if eb.sprite else None
        if p is not None:
            seq = [a for a in pair if p.has(a)]
            if seq:
                p.play_sequence(seq)
        tgt = self.level.items.get(eb.object_to_prime) \
            if eb.object_to_prime else None
        if tgt is not None:
            tgt.locked = True                      # Pawn.cs:1547, 1555

    def zone_reaction(self, zone_pid, which):
        """Zone.PlayItemsZoneEnter / PlayItemsZoneLeave (Zone.cs:64-79) —
        the TrickItem lists only; the SearchItem crabs ride CrabAnimations
        instead"""
        for it in self._zone_items.get(zone_pid, ()):
            if it.kind not in TRICK_KINDS:
                continue
            if which == 'enter':
                if it.enter_zone:
                    self._play_zone_enter(it)
            elif it.leave_zone:
                self._play_zone_leave(it)

    def player_for(self, sprite):
        """port plumbing: the AnimPlayer (AnimationControllerBase) of a
        sprite"""
        return self.players.get(id(sprite))

    # -- Woody using items -------------------------------------------------
    def call_later(self, delay, fn):
        """MonoBehaviour.Invoke, as GameInfo.InvokeMethodForSetPrime uses it"""
        self._delayed.append([delay, fn])

    def set_primed(self, item, primed):
        """Item.SetPrimed (Item.cs:1169-1243) + the TrickItem override that
        plays the primed idle (TrickItem.cs:996-1010, 483-491). PrimedOffset
        is zero throughout the shipped data; the WaterPuddle name-hack
        (Item.cs:1196-1200) is the sign flip below."""
        if item.dont_prime_while_tricked and item.tricked:
            return
        item.primed = primed
        # the WaterPuddle negates its DeltaLocation and FinalDeltaLocationNormal
        # outright and skips the delta arms (Item.cs:1196-1210)
        if item.name == 'WaterPuddle':
            item.dx = -item.dx
            item.dy = -item.dy
            item.final_normal = (-item.final_normal[0], -item.final_normal[1])
        elif item.delta_primed_x or item.delta_primed_y:
            sign = 1.0 if primed else -1.0
            item.dx += sign * item.delta_primed_x
            item.dy += sign * item.delta_primed_y
        if primed and item.primed_mouse_over:
            # the primed cursor swap (Item.cs:1215-1218)
            item.mouse_over_icon = 'Textures/GUI/cursor/' + item.primed_mouse_over
        if primed and item.primed_material and item.go is not None:
            # the material swap on the item's quad (Item.cs:1236-1239)
            q = self.level.quads_by_go.get(item.go)
            if q is not None:
                q['texture'] = item.primed_material
        if item.sprite is not None:
            if item.show_only_when_primed:
                item.sprite.hidden = not primed      # Item.cs:1219-1231
            if item.hide_when_primed:
                item.sprite.hidden = primed          # Item.cs:1232-1235
        if primed and item.kind in TRICK_KINDS:
            # TrickItem.SetPrimed (cs:996-1010): PrimedFuckedUp after a failed
            # fix, else PlayPrimedAnimation — both through PlayItemAnimation,
            # so a NONE pose hides a HideWhenNotAnimating item (L113's
            # FuseBox drops its FusePlaced strip while primed)
            if item.fucked_up:
                self.play_item_anim(item, item.primed_fucked_up)
            else:
                self._play_primed_animation(item)

    def woody_prime(self, item):
        """Item.WoodyPrime (Item.cs:1246-1300): transform the held inventory
        to PrimedInventoryType, prime, consume it when asked, chain to
        ObjectToPrimeWhenPrimed, and play the prime animation on Woody. The
        IceBucket branch is a name-hack, not ported."""
        used = self.inventory.used
        if item.primed_inventory_type and item.primed_inventory_type != 'IT_NONE' \
                and used is not None:
            used['type'] = item.primed_inventory_type   # UsedInventory.ChangeType
        self.set_primed(item, True)
        # the mesh and collider drops right after the prime
        # (Item.cs:1253-1261): the tatter disappears and stops taking clicks
        if item.disable_mesh and item.primed:
            item.disable_mesh = False
            if item.sprite is not None:
                item.sprite.hidden = True
        if item.disable_collider_when_primed:
            item.clickable = False
        if item.remove_inv_after_priming and used is not None:
            self.inventory.remove(used['type'])
        other = self.level.items.get(item.object_to_prime) \
            if item.object_to_prime else None
        if other is not None:
            self.woody_prime(other)
            if item.unlock_object_to_prime:
                other.locked = False
            if other.name == 'IceBucket':
                # the IceBucket re-arms for a second round with the bucket
                # and writes its own target off (Item.cs:1274-1281)
                tgt = self.level.items.get(other.object_to_prime) \
                    if other.object_to_prime else None
                other.primed = False
                other.require_priming = True
                other.primed_inventory_type = 'IT2_Bucket'
                if tgt is not None:
                    tgt.fucked_up = True
                other.object_to_prime = None
                if used is not None:
                    self.inventory.remove(used['type'])
        seq = [a for a in item.woody_prime_anim if self.woody.anim.has(a)]
        if seq:
            # ReturnWoodyToStand is the sequence-end delegate; the stand hook
            # in AnimPlayer covers it
            self.woody.anim.play_sequence(seq)

    def _add_inventory_to_object(self, item, object_type, entry):
        """Item.AddInventoryToObject (Item.cs:1791-1810): a one-entry refill
        of an emptied SearchItem — case 1 fills the held inventory's source
        item's InventoryToAdd (cs:1795-1801: L208's Mouse points at itself,
        so the emptied Mouse gets its rat back), case 2 this item's own
        (cs:1802-1808); only an empty stock (InventoryItems == null) is
        refilled. The `invItems` parameter of the original is unused."""
        used = self.inventory.used
        if object_type == 1:
            src = self.level.items.get(used.get('item')) \
                if used is not None and used.get('item') else None
            target = self.level.items.get(src.inventory_to_add) \
                if src is not None and src.inventory_to_add else None
        elif object_type == 2:
            target = self.level.items.get(item.inventory_to_add) \
                if item.inventory_to_add else None
        else:
            target = None
        if target is not None and not target.inventory_items:
            target.inventory_items = [dict(entry)]

    def woody_use(self, item):
        """Click on an item: walk to it, then the Woody.TryUseItem chain.
        The click gate is Woody.Frozen (Woody.cs:637) — FinishGame's freeze,
        not GameEnding: the 2.5 s win wait keeps item clicks live."""
        if self.woody is None or self.woody.frozen:
            return False
        self.woody.start_move_flags()
        return self.woody.goto_item(item,
                                    on_arrive=lambda: self._woody_try_use(item))

    def _wont_go(self):
        """Woody.PlayWontGoAnimation (Woody.cs:872-884): the held
        inventory's WrongZoneTooltip speaks at Woody — only while
        WrongZoneDescritionTooltip is up, which GetMoveDestination raises
        for the floor-item refusal alone (Pawn.cs:615) and a non-empty
        bubble consumes (Woody.cs:878-882); the door refusal (Pawn.cs:
        633-638) is a bare NoNo — then the NoNo"""
        woody = self.woody
        used = self.inventory.used
        wz = (used or {}).get('wrong_zone')
        if woody.wrong_zone_tooltip and wz and self.hud is not None:
            self.hud.show_item_tooltip(wz, woody.sprite.x, woody.sprite.y,
                                       False)
            woody.wrong_zone_tooltip = False
        if woody.anim.has('NoNo'):
            woody.anim.play_single('NoNo')

    def woody_click(self, wx, wy, item, door):
        """One world click — the Woody.ProcessMoveInput chain:
        GetMoveDestination (Pawn.cs:556-714) with Woody.CheckTargetItem /
        ShouldGoToItem (Woody.cs:848-870) and ShouldAbortMove
        (Woody.cs:782-810); a refused click clears the used inventory and
        keeps the old route (StartMoveToLocation's else, Woody.cs:736-741).
        Returns True when the click was handled."""
        woody = self.woody
        inv = self.inventory
        self._last_input_time = self.time    # FindInput's input stamp
        # GetMoveDestination's head (Pawn.cs:593-595): DoorClicked drops,
        # ItemAux takes the raw collider hit — a Door is an Item too
        # (Helpers.GetItemFromCollider, Helpers.cs:138-141), which is what
        # arms FlagAux from a walk-up door in Woody's zone (Pawn.cs:314-317)
        woody.door_clicked = None
        woody.item_aux = item if item is not None else door
        # CheckTargetItem: a floor item clicked bare-handed walks its zone
        if item is not None and item.is_floor and inv.used is None:
            item = None
        # Woody.ShouldAbortMove's WasHiding arm (Woody.cs:798-808): the
        # first click after leaving a hiding spot re-targets that same item
        # as a plain walk to its TargetLocation instead of hiding again
        if woody.was_hiding:
            woody.was_hiding = False
            if item is not None and item is woody.last_hiding_item:
                woody.last_hiding_item = None
                if self.hud is not None:
                    self.hud.colored_tooltip = False    # ClearTooltip
                dest = self.level.zone_by_pid(item.zone)
                if dest is not None:
                    woody.start_move_flags()
                    woody._capture_click(dest)
                    woody._route(dest, {'kind': 'point',
                                        'x': item.target_x}, None)
                return True
        if item is not None:
            # ShouldGoToItem: a floor item with the wrong inventory in hand
            if item.is_floor and inv.used is not None \
                    and inv.used['type'] != item.required_inventory:
                woody.wrong_zone_tooltip = True     # Pawn.cs:615
                self._wont_go()          # Pawn.cs:615-618
                self._move_refused()
                return True
            self.woody_use(item)
            return True
        if door is not None:
            woody.door_clicked = door    # Pawn.cs:624-627, before the gates
            # a locked Transition swallows the click (Pawn.cs:628-632)
            if door.is_transition and door.locked:
                self._move_refused()
                return True
            # a held item-sourced inventory (or the knife) refuses the door
            # (Pawn.cs:633-638)
            if inv.used is not None and (inv.used.get('item') is not None
                                         or inv.used['type'] == 'IT2_Knife'):
                self._wont_go()
                self._move_refused()
                return True
            woody_zone = woody.zone.pid if woody.zone else None
            if not door.locked and door.zone == woody_zone:
                # own-zone door: cross it and stop past the exit — the far
                # target's last step is cut (StopAtExitDoor, Pawn.cs:654-657;
                # BuildPathToDoor, Pawn.cs). NFH2 walks the full path.
                other = self.level.door_by_pid(door.link_to)
                if other is None:
                    return True
                # Clicking the door he is standing on — the one he just came
                # through — passes it at once, skipping the walk and the
                # repeated climb: ShouldExitDoorNow + UseDoorAtOnce ride the
                # path build (Woody.cs:777-780, Pawn.cs:744-780) inside
                # Pawn._route, for this click and for any other whose route
                # starts back through that door. InitializePath replaces
                # MovePath (Pawn.cs:480-498): the pending final item use of
                # the previous route dies with the new on_arrive=None —
                # keeping it made a wardrobe click, overridden by a door
                # click, fire its hide+SetWoodyXOnUse teleport at the end of
                # the door pass, across half the level.
                woody.start_move_flags()
                dest = self.level.zone_by_pid(other.zone)
                if dest is None:
                    return True
                woody._capture_click(dest)
                if woody.nfh2:
                    woody._route(dest, {'kind': 'point',
                                        'x': other.x + other.dx}, None)
                else:
                    woody._route(dest, [], None)
                return True
            if door.locked and door.zone == woody_zone:
                # used like an item: Door.CanWoodyUse refuses with a
                # Stand_Down loop, the door's description and a tooltip
                # clear (Pawn.cs:688-690, Door.cs:230-240)
                if woody.anim.has('Stand_Down'):
                    woody.anim.play_looping('Stand_Down')
                if self.hud is not None:
                    if door.description_string:
                        self.hud.show_item_tooltip(door.description_string,
                                                   door.x, door.y, False)
                    self.hud.colored_tooltip = False   # Woody.ClearTooltip
                return True
            # any far-zone door (locked or not): walk to the door itself
            woody.start_move_flags()
            dest = self.level.zone_by_pid(door.zone)
            if dest is None:
                return True
            woody._capture_click(dest)
            woody._route(dest, {'kind': 'point', 'x': door.x + door.dx},
                         None)
            return True
        # the bare-zone walk; a held inventory makes the miss an abort:
        # SetUsedInventory(null), ClearTooltip, and the old route continues
        # (Woody.ShouldAbortMove, Woody.cs:786-792; StartMoveToLocation's
        # else, Woody.cs:736-741)
        if inv.used is not None:
            inv.used = None
            if self.hud is not None:
                self.hud.colored_tooltip = False
            return True
        woody.start_move_flags()
        if not woody.goto(wx, wy):
            self._move_refused()
            return False
        return True

    def _move_refused(self):
        """StartMoveToLocation's else (Woody.cs:736-741): when MoveToLocation
        comes back false — no zone under the click, a WrongZone or door
        refusal of GetMoveDestination, a locked Transition — the latched
        tooltip and the used inventory drop and the old route stays
        (LoadMoveState); the port's steps are simply left alone"""
        self.inventory.used = None
        if self.hud is not None:
            self.hud.colored_tooltip = False

    def _can_woody_use(self, item):
        """Item.CanWoodyUse, the always-live gates (Item.cs:1671-1704), behind
        the subclass overrides that run first: GroundItem / InspectItem
        (GroundItem.cs:3-8, InspectItem.cs:5-22) and TrickItem.CanWoodyUse's
        compound / away / bed arms (TrickItem.cs:507-543)."""
        inv = self.inventory
        # Drawing.CanWoodyUse (Drawing.cs:81-88) is the outermost override: a
        # hidden drawing refuses before anything else runs — before the
        # TrickItem arms and before the base gate's CheckDescriptionTooltip,
        # so the EmptyDrawingString override (cs:90-100) is unreachable from
        # a click and no bubble shows
        if item.kind == 'Drawing' and item.sprite is not None \
                and item.sprite.hidden:
            return False
        if item.kind in ('GroundItem', 'InspectItem'):
            # GroundItem.CanWoodyUse / InspectItem.CanWoodyUse replace the
            # whole gate: stand, the description bubble (InspectItem's primed
            # variant once ItemThatChangesTooltip.GotTricked), refuse — no
            # use, no trick, no laugh (the 107 SlipperyGround strips, L110's
            # CarnivorPlant)
            name = self.woody._stand_name()
            if name:
                self.woody.anim.play_looping(name)   # SwitchToStandAnimation
            key = item.description_string
            if item.kind == 'InspectItem' and item.item_that_changes_tooltip:
                changer = self.level.items.get(item.item_that_changes_tooltip)
                if changer is not None and changer.got_tricked:
                    key = item.description_primed    # InspectItem.cs:13-20
            self.show_item_tooltip(item, key)
            return False
        if item.kind in TRICK_KINDS:
            # TrickItem.CanWoodyUse (TrickItem.cs:507-543) precedes the base
            # gates and their description bubble
            if item.compound and inv.used is not None and \
                    inv.used['type'] == item.compound_required:
                if item.name != 'Rake' or item.tricked:
                    # the compound trick applies immediately (cs:511-529);
                    # a DontGetAngry item drops that and becomes single-shot
                    item.compound_tricked = True
                    if item.dont_get_angry:            # cs:514-518
                        item.dont_get_angry = False
                        item.use_once = True
                    if item.animation and self.woody.anim.has(item.animation):
                        self.woody.anim.play_single(item.animation)
                    inv.remove(item.compound_required)
                    self.play_item_anim(item, item.compound_double_anim
                                        if item.tricked
                                        else item.compound_tricked_anim)
                    return None                # handled; no ordinary use follows
                # the untricked Rake refuses its compound with the HideString
                # bubble and falls through to the base gates (cs:531)
                self.show_item_tooltip(item, item.hide_string_key)
            if item.use_at_other_place and not item.at_home:
                return False                       # cs:533-536
            if item.is_bed and item.is_rottweiler_sleeping:
                # cs:537-541: the slept-in bed refuses before the base gates —
                # so before CheckDescriptionTooltip: no bubble
                self._woody_cant_use()
                return False
        # the description bubble runs first in the base gate (Item.cs:1378)
        self.check_description_tooltip(item)
        # DoubleRequiredItemsBehavior (Item.cs:1734-1758): holding the second
        # required inventory swaps the whole tricked identity — the required
        # type, the tricked use set, the tricked idle and the paid flag
        required = item.required_inventory
        if item.second_required and item.second_required != 'IT_NONE' and \
                inv.used is not None and inv.used['type'] == item.second_required:
            item.second_required, required = required, item.second_required
            item.required_inventory = required
            item.use_tricked_anim['Rottweiler'], item.rott_use_second_tricked = \
                item.rott_use_second_tricked, \
                item.use_tricked_anim.get('Rottweiler') or []
            item.idle_tricked, item.second_idle_tricked = \
                item.second_idle_tricked, item.idle_tricked
            item.already_tricked, item.second_already_tricked = \
                item.second_already_tricked, item.already_tricked
        # the Mouse/AngryElephant/ArmsBowl/Snake primed toggles at the head
        # (Item.cs:1385-1410) — the held mouse arms by target and type
        if held_pre := (self.level.items.get(inv.used.get('item'))
                        if inv.used is not None and inv.used.get('item')
                        else None):
            if held_pre.name == 'Mouse':
                t = inv.used['type']
                if item.name == 'AngryElephant':
                    held_pre.primed = (t == 'IT2_Snake')
                elif item.name == 'ArmsBowl' and t == 'IT2_Snake':
                    held_pre.primed = True
                elif item.name == 'Snake' and t == 'IT2_Rat' \
                        and self.snake_aux_208:
                    held_pre.primed = True
        # CowBehavior (Item.cs:1760-1780): flowers at the cow become a
        # priming item and the cow primes at once
        if item.name == 'Cow' and inv.used is not None \
                and inv.used['type'] == 'IT2_Flowers':
            fl = self.level.items.get(item.cow_flowers) \
                if item.cow_flowers else None
            if fl is not None:
                inv.used['item'] = fl.pid
                fl.primed_inventory_type = 'IT_NONE'
                fl.primed = False
                fl.require_priming = True
            item.prime_other = item.primed_tricked if item.tricked \
                else item.primed_normal
            self.set_primed(item, True)
            self.inventory.remove(inv.used['type'])
            # CowBehavior returns void — the gate flow continues bare-handed
        # Item.cs:1384-1390 (CanWoodyUse head): clicking the marbles makes the
        # next urgent resume advance instead of skipping (MarblesNextAction)
        if item.name == 'GroundMarbles':
            rt = next((r for r in self.routines if r.role == 'Rottweiler'), None)
            if rt is not None:
                rt.marbles_next = True
        # Item.cs:1515-1518: taken PigKeys answer with WhatsUp
        if item.item_removed and item.name == 'PigKeys':
            if self.woody.anim.has('WhatsUp'):
                self.woody.anim.play_single('WhatsUp')
            return False
        # Item.cs:1407-1413 (CanWoodyUse head): the FirstAid + key name-hack
        # — the only way Level108's locked kit opens. The key must come from
        # a source item, and the kit teleports to FirstAidPos — internal
        # initializers (-5.98, -2.544), Item.cs:640-646 — where the shipped
        # L108 transform already sits, so the assignment is a no-op there.
        if item.name == 'FirstAid' and inv.used is not None \
                and inv.used.get('item') is not None \
                and inv.used['type'] == 'IT_Key':
            item.x, item.y = -5.98, -2.544
            if item.sprite is not None:
                item.sprite.x, item.sprite.y = -5.98, -2.544
            item.locked = False
            self.woody_prime(item)
            return True
        # TakeItemMultipleTimes' already-have gate (Item.cs:1415-1420):
        # bare-handed at a repeatable source while already holding its
        # inventory refuses with the MultipleItemsString bubble
        if item.take_multiple and inv.used is None and item.inventory_items \
                and inv.has(item.inventory_items[0].get('type')):
            self._woody_cant_use()
            self.show_item_tooltip(item, item.multiple_items_string)
            return False
        # the Flowers pick with the knife (Item.cs:1421-1426): the held
        # knife becomes the flowers (WoodyPrime's ChangeType through
        # PrimedInventoryType) and a fresh knife entry lands back in the
        # inventory (AddItemToInventory)
        if item.name == 'Flowers' and item.pick_up_without_go \
                and inv.used is not None \
                and inv.used['type'] == item.required_inventory \
                and item.kind != 'TrickItem':
            item.primed_inventory_type = 'IT2_Flowers'
            self.woody_prime(item)
            inv.add([{'type': 'IT2_Knife', 'use_count': 0,
                      'name': 'PENKNIFE2_NAME', 'desc': 'PENKNIFE2_DESC',
                      'wrong_zone': '', 'long': False}])
        # DoNothingWhileBeeingUsed (Item.cs:1429-1437) reads Item.IsUsing —
        # raised at the RequireUnprime use leg and cleared only at the unprime
        # leg (Item.cs:1076, 1080; FixAll, TrickItem.cs:435) — so the refusal
        # spans the whole use->unprime stretch, neighbour present or not
        # (L114's gramophone); a nail adds its bubble
        if item.do_nothing_while_used and item.is_using:
            if inv.used is not None and inv.used['type'] == 'IT_Nail':
                self.show_item_tooltip(item, item.not_primed_tooltip)
            self._woody_cant_use()
            return False
        held_src = self.level.items.get(inv.used.get('item')) \
            if inv.used is not None and inv.used.get('item') else None
        # the dexterity minigame gate (Item.cs:1438-1507); the cs:1510 check
        # is the else of its chain
        dex = self._dexterity_gate(item, inv)
        if dex == 'armed':
            return False
        if dex == 'done':
            # the two dexterity arms end without a return (Item.cs:1462-1474,
            # 1495-1507) and the refusal cluster is their `else` — a
            # finished minigame skips straight to the tail
            return self._can_woody_use_tail(item)
        if dex is None:
            # Item.cs:1510: holding anything at a plain (non-TrickItem) item
            # that needs no priming is a flat no
            if inv.used is not None and item.kind not in TRICK_KINDS \
                    and not item.require_priming:
                self._woody_cant_use()
                return False
        # Item.cs:1520-1535: a neighbour-primed item refuses Woody until the
        # neighbour has primed it
        if item.require_priming and not item.primed and item.rott_toggles_prime:
            if inv.used is not None:
                self._woody_cant_use()
                item.wrong_trick = True
            elif item.force_whatsup_not_primed and self.woody.anim.has('WhatsUp'):
                self.woody.anim.play_single('WhatsUp')
            return False
        # Item.cs:1537-1613: the held inventory's source item wants priming —
        # clicking its PrimingItem primes it, anything else refuses (the
        # DoublePrimingItem name-hacks are not ported); the OnlyWhenTricked
        # variant fires only on a tricked target
        if held_src is not None and held_src.require_priming \
                and not held_src.primed:
            live = (not held_src.require_priming_only_tricked) or item.tricked
            if live:
                # the LionStatue accepts its priming inventory only once
                # tricked (Item.cs:1544-1553: the untricked statue raises
                # TrickedItem, which blocks the prime and falls to the no)
                blocked = item.name == 'LionStatue' and not item.tricked
                if held_src.priming_item == item.pid and not blocked:
                    if item.name == 'LionStatue' and item.tricked:
                        self.set_primed(item, True)      # Item.cs:1550-1552
                    if item.name == 'Snake':
                        # the snake round of the L208 chain (Item.cs:1554-1560):
                        # SnakeAux208, the snake primes, the held rat becomes
                        # the snake, and the emptied Mouse gets a fresh rat
                        # (AddInventoryToObject, cs:1559)
                        self.snake_aux_208 = True
                        self.set_primed(item, True)
                        inv.used['type'] = 'IT2_Snake'
                        self._add_inventory_to_object(item, 1, _RAT_ENTRY_208)
                    self.woody_prime(held_src)
                    p = self.players.get(id(item.sprite)) if item.sprite else None
                    if p is not None and item.prime_other \
                            and p.has(item.prime_other):
                        p.play_single(item.prime_other)  # PlayAnimationDirectly
                elif held_src.double_priming_item:
                    # DoublePrimingItem (Item.cs:1573-1589): the mouse's
                    # second target is the elephant, which primes and eats it
                    if held_src.priming_item != item.pid \
                            and item.name != 'AngryElephant':
                        self._woody_cant_use()
                    elif held_src.name == 'Mouse' \
                            and item.name == 'AngryElephant':
                        # Item.cs:1581 re-arms Pawn.ElephantAnimations;
                        # cs:1582 refills the emptied Mouse with a rat
                        item.elephant_behavior_aux = False
                        self._add_inventory_to_object(item, 1, _RAT_ENTRY_208)
                        self.woody_prime(item)
                        if item.prime_other:
                            seq = [x for x in item.woody_prime_anim
                                   if self.woody.anim.has(x)]
                            if seq:
                                self.woody.anim.play_sequence(seq)
                            if inv.used is not None:
                                self.inventory.remove(inv.used['type'])
                else:
                    self._woody_cant_use()
                    if not held_src.require_priming_only_tricked:
                        item.wrong_trick = True          # Item.cs:1595
                return False
        # Item.cs:1615-1641: this item wants priming and Woody holds something
        fell_through = False
        if item.require_priming and not item.primed and inv.used is not None:
            if item.prime_with_inventory and item.prime_with_inventory != 'IT_NONE':
                if inv.used['type'] == item.prime_with_inventory:
                    self.woody_prime(item)
                    self.inventory.remove(item.prime_with_inventory)
                else:
                    self._woody_cant_use()
                return False
            if item.priming_item is None:
                self._woody_cant_use()               # Item.cs:1638
                return False
            # a designated PrimingItem elsewhere: the block ends without a
            # return, and the gate cluster below sits in its else — skipped
            fell_through = True
        elif item.require_priming and not item.primed and inv.used is None \
                and item.name == 'ElectricTrapTatter':
            # Item.cs:1643-1651: the tatter primes bare-handed, and the
            # else-cluster is skipped
            self.woody_prime(item)
            fell_through = True
        if not fell_through:
            # Item.cs:1654-1669: a spent UseOnce item; Iron alone skips the
            # WrongTrick mark (cs:1665)
            if item.use_once and item.used:
                if not (item.tricked ^ item.got_tricked):
                    self._woody_cant_use()
                else:
                    # cs:1660-1663: the bubble plus a plain stand instead
                    self.show_item_tooltip(item)
                    name = self.woody._stand_name()
                    if name:
                        self.woody.anim.play_looping(name)
                if item.name != 'Iron':
                    item.wrong_trick = True
                return False
            # Item.cs:1671-1688; an unprimed held source never counts as the
            # required inventory
            if required and required != 'IT_NONE':
                unprimed_held = held_src is not None \
                    and held_src.require_priming and not held_src.primed
                if ((not inv.is_using(required)) or unprimed_held) \
                        and not item.grab_directly:
                    if inv.used is not None:
                        self._woody_cant_use()
                        item.wrong_trick = True
                    return False
            elif inv.used is not None:
                self._woody_cant_use()     # holding something at a bare item
                return False
            if item.locked:
                # Item.cs:1694-1700: the locked refusal speaks (the
                # TutorialDrawers stand variant has no data in either season)
                self._woody_cant_use()
                self.show_item_tooltip(item)
                return False
        return self._can_woody_use_tail(item)

    def _can_woody_use_tail(self, item):
        """CanWoodyUse's tail past the refusal cluster (Item.cs:1704-1730):
        the mouse-over swap and the ValveMain name-hack, then true. The
        cluster (cs:1510-1700) is the `else` of the dexterity chain, so a
        finished dexterity (cs:1462-1474 / 1495-1507) lands here directly."""
        # the ValveMain name-hack (Item.cs:1714-1726): Woody's click toggles
        # the main valve — opening arms Tricked AND GotTricked at once, which
        # is what starts Level113's sink spraying immediately
        if item.name == 'ValveMain':
            if item.main_valve_open:
                item.main_valve_open = False
                item.tricked = False
                item.got_tricked = False
            else:
                item.tricked = True
                item.got_tricked = True
                item.main_valve_open = True
                self.set_primed(item, False)
        return True

    def _dexterity_gate(self, item, inv):
        """Item.CanWoodyUse's dexterity chain (Item.cs:1438-1507): the first
        pass arms the minigame and blocks the use; after DexterityDone the
        pass falls through as done, unlocking and consuming the unlocker."""
        woody = self.woody
        used = inv.used
        unlocker_held = used is not None \
            and used['type'] == item.dexterity_unlocker
        no_req = item.dexterity_unlocker in (None, '', 'IT_NONE')
        search_branch = (
            item.dexterity
            and (unlocker_held or no_req or woody.in_dexterity)
            and not item.dexterity_trick_item
            and item.kind == 'SearchItem' and item.inventory_items
            and (not inv.has(item.inventory_items[0].get('type'))
                 or item.name == 'WhipStonePlate'))
        trick_branch = (
            not search_branch and item.dexterity
            and (unlocker_held or no_req)
            and item.dexterity_trick_item and not item.tricked)
        if not search_branch and not trick_branch:
            return None
        if not woody.in_dexterity:
            self._dex_inv_used = used              # InvUsed
            woody.in_dexterity = True
        if pcprofile.is_pc() and not woody.dexterity_done \
                and not item.pc_minigame_ticks:
            # a dexterity item with no PC game object (the overlays' PCMinigame
            # Ticks, tools/pcref/pc_minigames.py): the first click wins it
            # outright, with WinDexterity's side effects (the search item's
            # ActivateTrickIfSearch coin, the DexterityOtherAnimation)
            ds = self.dex_states.get(item.dexterity_alert) \
                if item.dexterity_alert else None
            if ds is not None:
                ds._win()
            else:
                woody.dexterity_done = True
        if not woody.dexterity_done:
            if search_branch and item.hide_in_dexterity:
                self.set_object_hidden(item, True)
            if not item.play_dexterity_seq:
                if item.dexterity_animation \
                        and woody.anim.has(item.dexterity_animation):
                    woody.anim.play_looping(item.dexterity_animation)
            else:
                seq = [x for x in item.dexterity_sequence
                       if woody.anim.has(x)]
                if seq:
                    woody.anim.play_sequence(seq)
            ds = self.dex_states.get(item.dexterity_alert) \
                if item.dexterity_alert else None
            if ds is not None:
                ds.start()
            return 'armed'
        woody.in_dexterity = False
        woody.dexterity_aux = False        # the retry one-shot re-arms (cs:1463, 1496)
        woody.dexterity_done = False
        item.locked = False
        if item.take_item_count == 1:
            item.dexterity = False
        if not no_req and not item.dexterity_keep_item \
                and not item.dexterity_keep_use_item \
                and self._dex_inv_used is not None:
            inv.remove(self._dex_inv_used['type'])
        return 'done'

    def hide_during_woody_anim(self, item, layer=True):
        """Item.InternalUse's HideDuringWoodyAnim block (Item.cs:1929-1938):
        PawnToChangeLayerDuringHide moves to LayerDepth until Woody's next
        blocking end (OriginalLayer, Woody.cs:304-307), and the item's active
        object hides until his next single ends (ShowAfterFinishAnimation,
        cs:381-385). HideItem.Leave repeats the pair without the layer swap
        (HideItem.cs:66-70) — layer=False."""
        if layer:
            from scene import GUI_DEPTH
            p = self.pawn_by_pid(item.pawn_to_change_layer_during_hide) \
                if item.pawn_to_change_layer_during_hide else None
            if p is not None and item.layer_depth in GUI_DEPTH:
                self._woody_layer_restore.append((p, p.sprite.depth))
                p.sprite.depth = GUI_DEPTH[item.layer_depth]
        self._woody_show_after.append(item)
        self.set_active_object_hidden(item, True)

    def _woody_single_ended(self, name):
        """Woody.OnSingleAnimationEnded's ItemToShowAfterAnim restore
        (Woody.cs:381-385) plus the layer restore of
        OnBlockingAnimationEnded (Woody.cs:304-307)"""
        # NFH2Path: the Entrance greeting's end unlocks the input
        # (Woody.cs:372-375) — StartGame locked it (IntroAnimation.cs:302)
        if self.woody is not None and self.woody.nfh2 \
                and name == self.woody.hello_animation_nfh2:
            self.woody.input_locked = False
        # the use chain's tail drops AnimationsInProgress (Woody.cs:376-380)
        if name in ('TrickLaugh', 'WhatsUp', 'TakeInventory') \
                and self.woody is not None:
            self.woody.animations_in_progress = False
        for it in self._woody_show_after:
            self.set_active_object_hidden(it, False)
        self._woody_show_after = []
        for pawn, depth in self._woody_layer_restore:
            pawn.sprite.depth = depth
        self._woody_layer_restore = []

    def _woody_cant_use(self):
        """Woody.PlayCantUseAnimation"""
        if self.woody.anim.has('NoNo'):
            self.woody.anim.play_single('NoNo')

    def show_item_tooltip(self, item, key=None):
        """Item.ShowItemTooltip (Item.cs:1844-1853): non-empty text opens
        the HUD's description bubble at the item plus its
        DeltaDescriptionLocation; key=None asks GetDescriptionString"""
        if self.hud is None:
            return
        if key is None:
            key = self.hud.get_description_string(item)
        if not key:
            return
        self.hud.show_item_tooltip(key, item.x + item.delta_desc[0],
                                   item.y + item.delta_desc[1],
                                   item.long_description)

    def check_description_tooltip(self, item):
        """Item.CheckDescriptionTooltip (Item.cs:1812-1830) at the head of
        CanWoodyUse (Item.cs:1378), with the TrickItem bed override
        (TrickItem.cs:545-556) and Drawing's empty-wall override
        (Drawing.cs:90-100). Both override arms are unreachable from a
        click: TrickItem.CanWoodyUse returns for a slept-in bed and
        Drawing.CanWoodyUse for a hidden drawing before base.CanWoodyUse
        gets here (TrickItem.cs:537-542, Drawing.cs:81-88), and nothing
        else calls CheckDescriptionTooltip."""
        inv = self.inventory
        if item.kind in TRICK_KINDS and item.is_bed \
                and item.is_rottweiler_sleeping:
            self.show_item_tooltip(item, item.item_in_use_string)
            return
        if item.kind == 'Drawing' and item.sprite is not None \
                and item.sprite.hidden:
            self.show_item_tooltip(item, item.empty_drawing_string)
            return
        req = item.required_inventory not in (None, '', 'IT_NONE')
        if inv.used is None and (req or item.ignore_required_for_desc):
            self.show_item_tooltip(item)
            if self.level_script is not None:
                # the tutorial's look-at signal (Item.cs:1817-1819)
                self.level_script.on_item_lookat(item)
        elif inv.used is not None \
                and inv.used['type'] != item.required_inventory:
            for t in item.inventory_tooltips:
                if t['type'] == inv.used['type']:
                    self.show_item_tooltip(item, t['desc'])
                    break
        elif item.require_priming and not item.primed:
            self.show_item_tooltip(item, item.not_primed_tooltip)

    def _woody_try_use(self, item):
        """Woody.TryUseItem (Woody.cs:499-550): Item.Use -> WoodyUse gate ->
        the use teleports -> the item's animation on Woody; the state change
        happens when it ends."""
        # Item target = MovePath.Steps[MoveIndex].Target (Woody.cs:515) —
        # kept for the dexterity retry, which re-runs TryUseItem on the same
        # step a frame after the win (Woody.cs:218-222)
        self.woody.use_target = item
        item.wrong_trick = False           # Item.WoodyUse (Item.cs:1857)
        self.woody.animations_in_progress = True   # Item.cs:1858
        ok = self._can_woody_use(item)
        if ok is not True:
            return
        if item.hide_during_woody_use_anim:
            self._woody_use_anim_item = item   # Woody.itemAux (Woody.cs:216)
        # the use teleports (Woody.cs:520-533)
        if item.teleport_woody_on_use:
            self.woody.sprite.x, self.woody.sprite.y = item.x, item.y
            self.woody.pos_snap = True
        if item.set_woody_x_on_use:
            self.woody.sprite.x = item.x
            self.woody.pos_snap = True
        if item.woody_target_y:
            self.woody.sprite.y = item.woody_target_y
            self.woody.pos_snap = True
        # Item.PreUse for the end-of-animation users (Item.cs:2225-2235)
        if item.kind == 'SearchItem':
            # SearchItem.PreUse opens the furniture (SearchItem.cs:125-152)
            self.open_search_furniture(item)
        if item.kind in TRICK_KINDS or item.kind == 'SearchItem':
            if item.hide_before_use:
                self.set_object_hidden(item, True)
            other = self.level.items.get(item.hide_other_object_woody) \
                if item.hide_other_object_woody else None
            if other is not None:
                self.set_active_object_hidden(other, True)
        # WoodyUse: remember what was held for the later decrement
        item_used_inventory = self.inventory.used
        if item.kind == 'HideItem':
            # ShouldUseAfterAnimationFinishes is UseAfterAnimation (false on
            # all 33 HideItems), so UseItem runs at once (Item.cs:1870):
            # Used, the base InternalUse — HideDuringWoodyAnim hides the bed
            # for the span of Woody's Hide_In (Item.cs:1929-1938) — then
            # HideItem.InternalUse's Woody.Hide + HideAnim (HideItem.cs:32-44)
            # and Woody plays Hide_In
            item.used = True                             # Item.cs:1893
            if self.level_script is not None:
                self.level_script.on_item_used(item)     # cs:1894-1897
            self._item_internal_use(item)
            self.woody.hide(item)
            if self.hud is not None:
                self.hud.colored_tooltip = False         # Item.cs:1916
            if item.animation and self.woody.anim.has(item.animation):
                self.woody.anim.play_single(item.animation)
            return
        seq = list(item.animation_sequence) if item.use_woody_sequence \
            else ([item.animation] if item.animation else [])
        seq = [a for a in seq if self.woody.anim.has(a)]
        searching = item.kind == 'SearchItem'
        # only a TrickItem defers its use to the animation's end
        # (ShouldUseAfterAnimationFinishes: TrickItem.cs:263-266,
        # SearchItem.cs:121-124); every other kind — the L109 parrot is the
        # one clickable Alerter — runs UseItem now (Item.cs:1865-1871) and
        # its animation ends into nothing (Woody.cs:412-444)
        deferred = item.kind in TRICK_KINDS or searching
        if not deferred:
            self._use_item(item)
        # BlockWhenItemPick: the pick animation locks the input outright and
        # nothing is buffered (Woody.cs:534-538); InternalUse's tail unlocks
        # (Item.cs:1943-1947)
        if item.block_when_item_pick:
            self.woody.input_locked = True
            self.woody.stored_input = None

        def anim_ended():
            if searching:
                self._woody_search_step(item)
            elif deferred:
                self._woody_trick_done(item, item_used_inventory)
        if seq:
            # a bare Animation is a PlaySingleAnimation (Woody.cs:539-546)
            self.woody.anim.play_sequence(seq, on_end=anim_ended,
                                          as_sequence=item.use_woody_sequence)
        else:
            anim_ended()

    def _use_item(self, item):
        """Item.UseItem (Item.cs:1879-1917) — shared by TrickItem.
        OnUseAnimationCompleted (TrickItem.cs:275), SearchItem.
        OnFinishAnimationCompelted (SearchItem.cs:114-119) and the immediate
        use of every other kind (Item.WoodyUse, cs:1870): the Dove hack, Used,
        the CowCrap and Rabbit hacks — SearchItems both, so they live here and
        not on the trick tail — the InternalUse dispatch, Woody.ClearTooltip."""
        if item.name == 'Dove':                          # cs:1881-1892
            item.clickable = False
            drawing = self.level.items.get(
                (self.level.objs.get(str(item.pid), {}).get('data', {})
                 .get('Drawing') or {}).get('path'))
            if drawing is not None and drawing.use_anim.get('Rottweiler'):
                da = drawing.use_anim['Rottweiler']
                da[1 if len(da) > 1 else 0] = 'BalconyDrawingWithoutBird'
        item.used = True                                 # cs:1893
        if self.level_script is not None:
            self.level_script.on_item_used(item)         # cs:1894-1897
        if item.name == 'CowCrap':                       # cs:1898-1910
            cow = self.level.items.get(
                (self.level.objs.get(str(item.pid), {}).get('data', {})
                 .get('CrapBehaviorCow') or {}).get('path'))
            if cow is not None:
                p = self.players.get(id(cow.sprite)) if cow.sprite else None
                name = cow.idle_tricked if cow.tricked else cow.idle
                if p is not None and name and p.has(name):
                    p.play_looping(name)
            item.clickable = False                       # the collider
            if item.sprite is not None:
                # its ItemAnimationController is disabled for good: nothing
                # draws it again
                item.sprite.hidden = True
        if item.name == 'Rabbit':
            self.set_active(item, False)                 # cs:1911-1914
        if item.kind == 'SearchItem':
            self._search_internal_use(item)              # SearchItem.cs:156-212
        else:
            self._item_internal_use(item)                # Item.cs:1919-1953
        if self.hud is not None:
            self.hud.colored_tooltip = False             # Woody.ClearTooltip, cs:1916

    def _item_internal_use(self, item):
        """Item.InternalUse (Item.cs:1919-1953): HideAfterUse / ShowAfterUse,
        HideDuringWoodyAnim with the layer swap and the show-at-next-single
        restore, the RubyThrone deactivation, the BlockWhenItemPick unlock
        (nothing buffered survives it) and the post-dexterity unlock."""
        if item.hide_after_use:                          # cs:1921-1928
            self.set_object_hidden(item, True)
        elif item.show_after_use:
            self.set_object_hidden(item, False)
        if item.hide_during_woody_anim:                  # cs:1929-1938
            from scene import GUI_DEPTH
            p = self.pawn_by_pid(item.pawn_to_change_layer_during_hide) \
                if item.pawn_to_change_layer_during_hide else None
            if p is not None and item.layer_depth in GUI_DEPTH:
                self._woody_layer_restore.append((p, p.sprite.depth))
                p.sprite.depth = GUI_DEPTH[item.layer_depth]
            # Woody.ShowAfterFinishAnimation: reappears when his next single
            # ends (Woody.cs:381-385, 304-307)
            self._woody_show_after.append(item)
            self.set_active_object_hidden(item, True)
        if item.name == 'RubyThrone':
            self.set_active(item, False)                 # cs:1939-1942
        if item.block_when_item_pick and self.woody is not None:
            self.woody.input_locked = False              # cs:1943-1947
            self.woody.stored_input = None               # ClearStoreBlockedInput
        if self.woody is not None and self.woody.mouse_click_after_dexterity:
            self.woody.mouse_click_after_dexterity = False   # cs:1948-1952
            self.woody.input_locked = False

    def _search_internal_use(self, item):
        """SearchItem.InternalUse (SearchItem.cs:156-212): the KeepFull /
        TakeItemCount head, the base InternalUse, then — with stock — the
        source stamps, Woody.OnSearchItemUsed, the hand-over, the collider
        drop, the IceBucket re-arm, AcquiredInventoryCount, the emptying and
        TrickAfterWoodyUse; without stock only AcquiredInventoryCount = 0."""
        first = item.inventory_items[0].get('type') \
            if item.inventory_items else None
        if item.take_item_count > 0 and item.keep_full \
                and first is not None and not self.inventory.has(first):
            item.take_item_count -= 1                    # cs:158-161
        else:
            item.keep_full = False                       # cs:162-165
        self._item_internal_use(item)                    # cs:166
        if not item.inventory_items:
            item.acquired_inventory_count = 0            # cs:208-211
            return
        # inventory.Item = this on every entry — or the first alone under
        # AssignFirstInventoryOnly (cs:167-177); the priming gates and the
        # door click read the stamp
        entries = [dict(e, item=item.pid)
                   if i == 0 or not item.assign_first_inventory_only
                   else dict(e)
                   for i, e in enumerate(item.inventory_items)]
        if self.search_behavior is not None:
            # Woody.OnSearchItemUsed runs between the stamps and the
            # hand-over (cs:178, Woody.cs:985-991)
            self.search_behavior.on_search_item_used(item)
        self.inventory.add(entries)                      # cs:179
        if item.disable_collider_after_use:              # cs:180-183
            item.clickable = False
        if item.name == 'IceBucket':                     # cs:184-190
            item.primed_animation = None
            item.woody_prime_anim = ['ItemFoundUp', 'TakeLow']
        item.acquired_inventory_count = len(item.inventory_items)  # cs:191
        if not item.keep_full:                           # cs:192-202
            if not item.dont_remove_inventory and not item.dexterity_keep_item:
                item.inventory_items = []
            else:
                item.item_removed = True
        if item.trick_after_woody_use:                   # cs:203-206
            self._get_tricked(item, True)

    def _woody_trick_done(self, item, used_inventory):
        """TrickItem.OnUseAnimationCompleted (TrickItem.cs:268-380)."""
        if item.wrong_trick:
            return
        self._use_item(item)               # cs:275: Item.UseItem
        if used_inventory is not None:
            used_inventory['use_count'] -= 1
            if item.required_inventory != 'IT_NONE' and not item.keep_after_use \
                    and used_inventory['use_count'] <= 0:
                self.inventory.remove(item.required_inventory)
        if item.grab_directly:
            self.inventory.add([{'type': item.required_inventory,
                                 'use_count': 0, 'name': item.name}])
        # the tricked overlay swap (TrickItem.OnUseAnimationCompleted,
        # cs:295-299) and the hide-other restore (cs:300-304)
        if item.tricked_object_go is not None:
            self.set_object_hidden(item, True)
            self.set_tricked_object_hidden(item, False)
        other = self.level.items.get(item.hide_other_object_woody) \
            if item.hide_other_object_woody else None
        if other is not None:
            self.set_active_object_hidden(other, False)
        # both arms skip ValveMain — the CanWoodyUse hack alone drives its
        # state (TrickItem.cs:305, 315)
        if item.can_undo_trick and item.tricked and item.name != 'ValveMain':
            self._get_tricked(item, False)
        else:
            # Iron and Rope become single-shot once tricked (TrickItem.cs:311)
            if item.name in ('Iron', 'Rope'):
                item.use_once = True
            if item.name != 'ValveMain':
                self._get_tricked(item, True)
            act = self.level.items.get(item.activate_item_trick) \
                if item.activate_item_trick else None
            if act is not None:
                # cs:323-332: the target arms and plays its tricked idle
                # outright (PlayIdleTrickedAnim, not ReturnToIdleAnimation);
                # the ElephantBucket also rewrites its normal idle
                act.tricked = True
                self._play_idle_tricked_anim(act)
                if act.name == 'ElephantBucket':
                    act.idle = 'N2TrickItemIdleNormal'
            aiu = self.level.items.get(item.activate_item_after_using) \
                if item.activate_item_after_using else None
            if aiu is not None:
                # cs:333-351: every routine action on "CaptainControls" is
                # retargeted at ActivateItemAfterUsingObject with
                # HideObjectDuringUse, which activates after the delay
                # (DelayActivateItem, cs:382-389, also drops LinkedItemTrick)
                # — L214's grog mug: the CaptainWheel, 11 s later
                for rt in self.routines:
                    if rt.role != 'Rottweiler':
                        continue
                    for a in rt.actions:
                        cur = self.level.items.get(a.get('item')) \
                            if a.get('item') else None
                        if cur is not None and cur.name == 'CaptainControls':
                            a['item'] = aiu.pid
                            a['hide_object'] = True
                linked = self.level.items.get(item.linked_item_trick) \
                    if item.linked_item_trick else None

                def delay_activate_item(aiu=aiu, linked=linked):
                    self.set_active(aiu, True)
                    if linked is not None:
                        self.set_active(linked, False)
                if item.delay_activate_after_using > 0.0:
                    self.call_later(item.delay_activate_after_using,
                                    delay_activate_item)
                else:
                    self.set_active(aiu, True)
            tgt = self.level.items.get(item.set_tricked_on_item) \
                if item.set_tricked_on_item else None
            if tgt is not None:
                tgt.tricked = True
        # the idle switch (cs:357-379): a compound item plays its tricked idle
        # until CompoundTricked, then CompoundDoubleTrickedAnim; else the raw
        # Tricked flag picks PlayIdleTrickedAnim (a Neutral item too — L104's
        # deodorant shows its hair), else the normal idle or its sequence
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if item.compound:
            if not item.compound_tricked:
                self._play_idle_tricked_anim(item)
            else:
                self.play_item_anim(item, item.compound_double_anim)
        elif item.tricked:
            self._play_idle_tricked_anim(item)
        elif item.play_idle_normal_seq:
            if p is not None:
                seq = [a for a in item.idle_normal_sequence if p.has(a)]
                if seq:
                    p.play_sequence(seq)
        else:
            self.play_item_anim(item, item.idle)
        # Woody laughs (Woody.OnSingleAnimationEnded, Woody.cs:418)
        if not item.dont_laugh and self.woody.anim.has('TrickLaugh'):
            self.woody.anim.play_single('TrickLaugh')
        # the BeerMat prime-pose swap (Woody.cs:421-424)
        if item.name == 'BeerMat' and item.rott_prime_anim:
            item.rott_prime_anim[0] = 'BeachPinLayDown'
        # the use tail's name-hack run (Woody.cs:426-431)
        self._kart_behavior(item)
        self._captain_door_behavior(item)
        self._phone_behavior(item)
        self._throne_behavior_212(item)
        self._plant_carnivore_behavior(item)
        self._fifi_bone_behavior(item)
        if item.use_item_multiple_times:      # Woody.cs:432-435
            item.use_once = True

    def _get_tricked(self, item, tricked):
        """Item.GetTricked (Item.cs:1957)"""
        item.tricked = tricked
        if item.get_tricked_at_once:
            item.got_tricked = tricked

    def _woody_search_step(self, item):
        """Woody.OnSingleAnimationEnded, the SearchingItem branch
        (Woody.cs:386-411): a stocked item plays the take animation, an empty
        one gets WhatsUp — and SearchAnimation is raised either way (cs:409),
        so both ends run OnFinishAnimationCompelted (cs:438-442)."""
        if item.inventory_items:
            take = list(item.take_sequence) if item.use_take_sequence \
                else ([item.take_animation] if item.take_animation else [])
            take = [a for a in take if self.woody.anim.has(a)]
            if take:
                self.woody.anim.play_sequence(
                    take, on_end=lambda: self._woody_search_done(item),
                    as_sequence=item.use_take_sequence)
            else:
                self._woody_search_done(item)
        elif self.woody.anim.has('WhatsUp'):
            self.woody.anim.play_sequence(
                ['WhatsUp'], on_end=lambda: self._woody_search_done(item),
                as_sequence=False)
        else:
            self._woody_search_done(item)

    def _woody_search_done(self, item):
        """SearchItem.OnFinishAnimationCompelted (SearchItem.cs:114-119):
        Item.UseItem — Used, the SearchItem.InternalUse hand-over and
        emptying — then the empty pose through SearchItem.PlayItemAnimation
        (its own twin: no Animating gate, the Looping flag, the NONE hide)."""
        self._use_item(item)                             # cs:117
        self.search_play(item, item.empty_animation)     # cs:118

    def _kid_update(self, kid):
        """Kid.Update (Kid.cs:25-51): the crying and remote flags raised by
        ActionManager.KidActions and SandCastleBehavior resolve into plays;
        crying also breaks Olga's current infinite loop."""
        spec = self.level.pawns.get('Kid') or {}
        if kid.kid_start_crying:
            kid.kid_start_crying = False
            olga = self.pawns.get('Olga')
            if olga is not None:
                was = olga.anim.anim.infinite
                olga.anim.anim.infinite = False   # CurrentAnimation.InfiniteLoop
                if pcprofile.is_pc() and was:
                    # the PC's Olga wakes at once: her mat state's handler
                    # of `kid_cry` (GameLogic 0x10023601 -> 0x100233ed) plays
                    # the mat's `wakeup` on the next tick, not after the
                    # sleep loop's round
                    olga.anim._stop_single()
            if spec.get('kid_use_crying_sequence'):
                seq = [a for a in spec.get('kid_crying_sequence') or ()
                       if kid.anim.has(a)]
                if seq:
                    kid.anim.play_sequence(seq)
            elif spec.get('kid_crying') and kid.anim.has(spec['kid_crying']):
                kid.anim.play_looping(spec['kid_crying'])
        elif kid.kid_using_remote:
            kid.kid_using_remote = False
            rs = spec.get('kid_remote_sequence')
            if rs and kid.anim.has(rs):
                kid.anim.play_looping(rs)
        if kid.kid_remote:
            kid.kid_remote = False
            if kid.default_anim and kid.anim.has(kid.default_anim):
                kid.anim.play_looping(kid.default_anim)

    def kid_start_crying(self):
        """Kid.StartCrying (Kid.cs:53-59): plays only with UseCryingSequence"""
        kid = self.pawns.get('Kid')
        spec = self.level.pawns.get('Kid') or {}
        if kid is not None and spec.get('kid_use_crying_sequence'):
            seq = [a for a in spec.get('kid_crying_sequence') or ()
                   if kid.anim.has(a)]
            if seq:
                kid.anim.play_sequence(seq)

    def spawn_pawn(self, role):
        spec = self.level.pawns.get(role)
        if not spec:
            return None
        if spec['zone'] is None and not (role == 'Woody'
                                         and self.level.start_zone):
            # a pawn with no serialized Zone never acts; Woody alone gets
            # parked into Level.StartZone regardless (Woody.cs:187-192 —
            # Intro102/103 ship his Zone empty)
            return None
        p = Pawn(self.level, spec['sprite'],
                 self.level.zone_by_pid(spec['zone']), spec,
                 player=self.players[id(spec['sprite'])], role=role)
        p.world = self
        self.pawns[role] = p
        if role == 'Woody':
            # Woody.OnSingleAnimationEnded restores the hidden-during-anim
            # items, and OnBlockingAnimationEnded the swapped layers
            # (Woody.cs:381-385, 304-307)
            p.anim.single_end_hook = self._woody_single_ended
            p.anim.double_end = True      # no ActionManager on Woody's controller
        if role == 'Woody' and self.level.start_location is not None:
            # Woody.Start parks him at StartLocation in the StartZone with
            # InputLocked = !FinishedEntrance (Woody.cs:187-192); with the
            # serialized FinishedEntrance false (Season 1) the EntranceTimer
            # (0.5 s, Woody.cs:114) runs after the intro (immediate here —
            # the title cards are not modelled) and he walks in
            # (Woody.cs:223-231); Season 2 ships it TRUE: no walk-in
            p.sprite.x, p.sprite.y = self.level.start_location
            p.pos_snap = True
            z = self.level.zone_by_pid(self.level.start_zone)
            if z is not None:
                p.zone = z
            p.input_locked = not p.finished_entrance
            if not p.finished_entrance:
                self._entrance_timer = 0.5
            if p.nfh2:
                # IntroAnimation.StartGame (cs:300-304): the NFH2Path Woody
                # starts locked and plays HelloAnimationNFH2 (Entrance); its
                # single end unlocks him (Woody.OnSingleAnimationEnded,
                # Woody.cs:372-375, in _woody_single_ended)
                p.input_locked = True
                name = p.hello_animation_nfh2
                if name and p.anim.has(name):
                    p.anim.play_single(name)
        return p

    def spawn_woody(self, sprite, zone, spec=None):
        """port plumbing: build the Woody pawn over his AnimController sprite
        (Unity instantiates him with the scene; the placement is Woody.Start,
        see Pawn.__init__ / _apply_level_locations)"""
        self.woody = Pawn(self.level, sprite, zone, spec,
                          player=self.players[id(sprite)], role='Woody')
        self.woody.world = self
        return self.woody

    def start_routines(self):
        """port scaffolding: one Routine per serialized ActionManager (Unity
        instantiates them with the scene); r.start() is each pawn's
        ActionManager.StartFirstAction (ActionManager.cs:103-110, called
        from Rottweiler.cs:927, Mother.cs:83, Olga.cs:36)"""
        for spec in self.level.routines:
            pawn = self.pawns.get(spec['owner'])
            if pawn is None or not spec['actions']:
                continue
            r = Routine(self.level, pawn, spec, role=spec['owner'])
            self.routines.append(r)
            r.start()
        self._build_behaviors()
        return self.routines

    # -- the level behaviors (Actor.Behavior / SecondaryBehaviors,
    #    Pawn.RoutineBehavior, Woody.SearchBehavior) -----------------------
    def subscribe(self, name, fn):
        self.events.setdefault(name, []).append(fn)

    def fire_event(self, name):
        for fn in list(self.events.get(name, ())):
            fn()

    def _build_behaviors(self):
        """wire the serialized behavior components to their owners the way
        Actor.BehaviorPlayAnimation / BehaviorOnAdvanceFrame dispatch
        (Actor.cs:93-115), Rottweiler adds the sequence-ended and caught
        hooks (Rottweiler.cs:448, 514-524, 1218-1239), ActionManager consults
        Pawn.RoutineBehavior (ActionManager.cs:119-124, 165-168) and
        SearchItem reaches Woody.SearchBehavior (Woody.cs:985-991). An
        inactive GameObject's component neither updates nor hooks."""
        import behaviors as behaviors_mod
        by_pid = {}
        for spec in self.level.behaviors:
            if not spec.get('active'):
                continue
            cls = behaviors_mod.REGISTRY.get(spec['type'])
            if cls is None:
                continue
            by_pid[spec['pid']] = cls(self, spec['data'])
        self.behavior_objs = list(by_pid.values())

        def hook_player(player, blist):
            player.on_play.append(
                lambda name, bl=tuple(blist):
                [b.play_animation(name) for b in bl])
            player.on_advance.append(
                lambda idx, bl=tuple(blist):
                [b.on_advance_frame(idx) for b in bl])
            # the animation already running when the behaviour attaches:
            # the original's ActorBehavior.PlayAnimation ran at that
            # animation's InitializeCurrentAnimation (Actor.
            # BehaviorPlayAnimation), the behaviour being enabled from its
            # Start — MugBehavior tracks the captain's idle from the first
            # cycle (the bench: the mug's collider off at 3.07 s from the
            # load, then 4 s in 8), where a hook attached after the idle's
            # start never learned its name and the mug stayed clickable
            if player.anim is not None:
                for b in blist:
                    b.play_animation(player.anim.name)
        for role, spec in self.level.pawns.items():
            pawn = self.pawns.get(role)
            if pawn is None:
                continue
            blist = []
            b = by_pid.get(spec.get('behavior'))
            if b is not None:
                blist.append(b)
            for pid in spec.get('secondary_behaviors') or ():
                b2 = by_pid.get(pid)
                if b2 is not None:
                    blist.append(b2)
            pawn.behaviors = blist
            if blist:
                hook_player(pawn.anim, blist)
            if role == 'Rottweiler' and blist:
                pawn.anim.seq_end_hook = \
                    lambda bl=tuple(blist): \
                    [b.on_animation_sequence_ended() for b in bl]
            rb = by_pid.get(spec.get('routine_behavior'))
            if rb is not None:
                for r in self.routines:
                    if r.pawn is pawn:
                        r.routine_behavior = rb
            sb = by_pid.get(spec.get('search_behavior'))
            if sb is not None:
                self.search_behavior = sb
        # items carrying the shared component get its hooks on their own
        # controller (the Vacuum, GroundSkates, PoolBoard, Bird, Mug)
        for it in self.level.items.values():
            b = by_pid.get(it.behavior) if it.behavior else None
            if b is None or it.sprite is None:
                continue
            p = self.players.get(id(it.sprite))
            if p is not None:
                hook_player(p, [b])

    def _detect_common(self, catcher):
        """the zone/door/hiding/blocking chain both predicates share
        (GameInfo.cs:189, 198): IsPassingDoor is is_warping here,
        IsMovingToAdjacentZone the TransitionMove flag, and the NFH2 terms
        are DonePassingToOtherZone and PassingComplexMove on both pawns"""
        woody = self.woody
        same_room = (woody.zone is not None and catcher.zone is not None
                     and woody.zone.pid == catcher.zone.pid
                     and not woody.is_warping and not catcher.is_warping
                     and not woody.moving_to_adjacent_zone()
                     and not catcher.moving_to_adjacent_zone()
                     and not woody.hiding
                     and not woody.done_passing and not catcher.done_passing
                     and not woody.passing_complex
                     and not catcher.passing_complex)
        if pcprofile.is_pc() and pcprofile.sees_while_busy(woody.nfh2):
            # the PC's catch is the room and the hideout flag alone
            # (pcprofile.sees_while_busy()): no IgnoreWoodyWhenUse, no
            # blocking-animation clause
            if pcprofile.door_warp_early(woody.nfh2):
                # and no door term: a pawn inside a door clip is in the room
                # its placement put it in (pcprofile.door_warp_early)
                return (woody.zone is not None and catcher.zone is not None
                        and woody.zone.pid == catcher.zone.pid
                        and not woody.hiding)
            return same_room
        return (same_room and not catcher.ignore_woody
                and (not catcher.anim.blocking or not woody.sneaking)
                and not woody.anim.blocking)

    def _pc_flag4_tick(self):
        """the catchers' flag 4 under the profile's Season 2 catch (Item.
        pc_hideout, tools/pcref/pc_catch_s2.py): the enter step of a station
        whose PC object is a neighbor_hideout sets it (GameLogic.dll
        0x100067e9) as the routine's use of the station starts, the leave
        step's end clears it (0x10006ab7) as the use ends — unless `until`
        keeps it to the next station's end (209's shoe mat, 0x10020d0e) —
        and the level steps set or clear it with the clips they name (the
        sleep and the wake of 202, 206, 210 and 214)"""
        for r in self.routines:
            p = r.pawn
            if p.role not in ('Rottweiler', 'Mother'):
                continue
            it = r.item if (r.state == r.USING and r.urgent_item is None) else None
            spec = it.pc_hideout.get(p.role) if it is not None else None
            use = (r.index, id(it)) if spec is not None else None
            if use != p._pc_use:
                if p._pc_use is not None and not p._pc_keep:
                    p.pc_flag4 = False
                p._pc_use = use
                p._pc_clip = None
                p._pc_keep = False
                if spec is not None:
                    until = spec.get('until')
                    if until is None:
                        p.pc_flag4 = True
                    elif r.actions:
                        nxt = r.actions[(r.index + 1) % len(r.actions)]
                        nit = self.level.items.get(nxt['item']) if nxt.get('item') else None
                        if nit is not None and nit.name == until:
                            p.pc_flag4 = True
                            p._pc_keep = True
            if spec is not None:
                a = p.anim.anim
                clip = a.name if a is not None else None
                if clip != p._pc_clip:
                    p._pc_clip = clip
                    if clip in spec.get('clear', ()):
                        p.pc_flag4 = False
                    elif clip in spec.get('set', ()):
                        p.pc_flag4 = True

    def _pc_s2_sees(self, catcher):
        """the Season 2 catch under the profile: generic/trigger.xml's `fight`
        on Woody, position room, type always — the watch predicate
        fcn.1003f573 under mode 1 (pcprofile.s2_sight): both room pointers
        set and equal (Pawn.pc_room), neither party's flag 4 — Woody hiding
        or in his hideout's leave clip (the leave step clears it once the
        clip has played, 0x10006ab7), the catcher's pc_flag4. No busy,
        sleep, sneak or animation term."""
        woody = self.woody
        if woody is None or catcher is None:
            return False
        rw, rc = woody.pc_room(), catcher.pc_room()
        if rw is None or rc is None or rw.pid != rc.pid:
            return False
        if woody.hiding:
            return False
        la = woody._pc_leave_anim
        if la is not None and woody.anim.anim is not None and woody.anim.anim.name == la:
            return False
        return not catcher.pc_flag4

    def can_rottweiler_see_woody(self):
        """GameInfo.CanRottweilerSeeWoody (GameInfo.cs:181-192), the Classic
        detection predicate. Pure zone containment; the Bed special case swaps
        the sleep term for a movement term."""
        rott = self.pawns.get('Rottweiler')
        woody = self.woody
        if rott is None or woody is None:
            return False
        # both branches of the original require ActionManager.CurrentAction
        # (GameInfo.cs:183, 187): ActiveAction is first assigned by the
        # StartAction after DelayStart (ActionManager.cs:103-110, 169) and
        # never nulled again — so no detection during the 1.5 s DelayStart,
        # nor for a manager that never starts (no actions / frozen at start)
        routine = next((r for r in self.routines if r.pawn is rott), None)
        if routine is None or not routine.actions or not routine.started:
            return False
        if pcprofile.is_pc() and pcprofile.s2_sight(woody.nfh2):
            return self._pc_s2_sees(rott)
        if not self._detect_common(rott):
            return False
        it = routine.item if routine else None
        if pcprofile.is_pc() and pcprofile.sees_while_busy(woody.nfh2):
            # the PC neighbour sees Woody whatever he is doing, except from
            # inside his hideout: 109's bed carries `neighbor_hideout`, and a
            # walking Woody's noise 1 wakes him there while a sneaking one's 0
            # does not (pcprofile.sees_while_busy())
            if it is not None and it.name == 'Bed':
                moving = woody.state in (woody.WALK, woody.DOOR_CLIMB,
                                         woody.DESCEND, woody.ITEM_CLIMB)
                return moving and not woody.sneaking
            return True
        # Rottweiler.CanSeeWoody defers to the primary behavior
        # (Rottweiler.cs:1218-1221)
        if rott.behaviors and not rott.behaviors[0].can_see_woody():
            return False
        if it is not None and it.name == 'Bed':
            moving = woody.state in (woody.WALK, woody.DOOR_CLIMB,
                                     woody.DESCEND, woody.ITEM_CLIMB)
            return moving                 # the Bed case demands Velocity > 0
        return not rott.is_sleeping

    def can_mother_see_woody(self):
        """GameInfo.CanMotherSeeWoody (GameInfo.cs:194-199): the neighbour's
        non-Bed chain, for the Mother; Mother.CanSeeWoody defers to level
        behaviors, which are not ported (default true)."""
        mother = self.pawns.get('Mother')
        if mother is None or self.woody is None:
            return False
        # ActionManager.CurrentAction != null (GameInfo.cs:196), as above
        routine = next((r for r in self.routines if r.pawn is mother), None)
        if routine is None or not routine.actions or not routine.started:
            return False
        if pcprofile.is_pc() and pcprofile.s2_sight(self.woody.nfh2):
            return self._pc_s2_sees(mother)
        if pcprofile.is_pc() and pcprofile.sees_while_busy(self.woody.nfh2):
            return self._detect_common(mother)
        # Mother.CanSeeWoody defers to the primary behavior (Mother.cs:103-106)
        if mother.behaviors and not mother.behaviors[0].can_see_woody():
            return False
        return self._detect_common(mother) and not mother.is_sleeping

    def _catch(self, catcher=None):
        """GameInfo.OnNeighborCaughtWoody / OnMotherCaughtWoody + FinishGame +
        the catcher's HitWoody urgent run (Mother.OnCaughtWoody calls
        HitWoody too, Mother.cs:108-111) +
        RoutineActionHitWoody.OnActionStarted."""
        import random
        # gotCaught is the neighbour's flag alone: every caller of
        # OnNeighborCaughtWoody sets it first (GameInfo.cs:216-218,
        # Pawn.cs:370-372, 1228-1230); OnMotherCaughtWoody's callers do not
        # (cs:222-224), so a Mother's catch ends the game with gotCaught
        # false. caught_by is the port's own record of who did it (the
        # runner / the recorder read it; no game rule hangs off it)
        catcher = catcher or self.pawns.get('Rottweiler')
        if os.environ.get('NFH_CATCH_TRACE'):
            import traceback
            w = self.woody
            rt = next((r for r in self.routines if r.pawn is catcher), None)
            print('CATCH t=%.2f by %s woody(zone=%s state=%s sneak=%s hiding=%s warp=%s anim=%s) catcher(zone=%s state=%s warp=%s item=%s rstate=%s anim=%s)' % (
                self.time, getattr(catcher, 'role', None),
                w.zone.pid if w and w.zone else None, getattr(w, 'state', None), getattr(w, 'sneaking', None), getattr(w, 'hiding', None), getattr(w, 'is_warping', None), w.anim.anim.name if w else None,
                catcher.zone.pid if catcher and catcher.zone else None, getattr(catcher, 'state', None), getattr(catcher, 'is_warping', None),
                rt.item.name if rt and rt.item else None, rt.state if rt else None, catcher.anim.anim.name if catcher else None), flush=True)
            traceback.print_stack(limit=6)
        if catcher is None or catcher.role == 'Rottweiler':
            self.game.got_caught = True
        self.game.caught_by = catcher.role if catcher is not None else 'Rottweiler'
        self.game.won = False             # GameInfo.cs:325/335
        self._respawning = False
        if pcprofile.is_pc() and self.game.lives > 1:
            # the PC profile's lives: the beating plays, then Woody respawns
            # and the neighbour resumes (docs/PC_FIDELITY.md 2.5); the last
            # life has no respawn — the catch fiber's case 4 skips the fall
            # on status +0x14 at 1 (fcn.1004012a, 0x1000634d) and case 5
            # ends the level (fcn.10042471, 0x100424dc)
            self._respawning = True
            self._last_catcher = catcher
            if pcprofile.s2_respawn(self.woody.nfh2):
                # the fiber heads Woody's queue up to its case 5, and the
                # catch's flag 0x10000 bars both behaviours meanwhile
                # (_pc_catch_barred); the life goes at the landing's end
                self._pc_catch_seq = True
                self.woody.input_locked = True
            else:
                self.game.lives -= 1
        else:
            if pcprofile.is_pc() and self.game.lives > 0:
                self.game.lives -= 1          # fcn.10042471 on the last life
            self._finish_game()               # FinishGame (cs:326/336)
            self._play_jingle('caught')       # PlayCaughtMusic (cs:329/339)
        woody = self.woody
        # Woody.PlayFearAnimation(catcher): face whoever caught him
        fear = woody.fear_left if catcher.sprite.x < woody.sprite.x \
            else woody.fear_right
        if woody.anim.has(fear):
            woody.anim.play_single(fear)
        woody.steps = []
        woody.state = woody.IDLE
        # Rottweiler.OnCaughtWoody / Mother.OnCaughtWoody dispatch the
        # behavior hook before HitWoody (Rottweiler.cs:1223-1239)
        for b in catcher.behaviors:
            b.on_caught_woody()
        # HitWoody: stop the routine, walk to Woody, then the hit
        for r in self.routines:
            if r.pawn is catcher:
                r.frozen = True           # ActionManager.Freeze in the action
        # HitWoody's StopCurrentAction (Rottweiler.cs:1088) drops the move
        # in progress with its arrival — the routine's use must not start
        # under the hit
        catcher.steps = []
        catcher.on_arrive = None
        catcher.in_urgent = False         # HitWoodyAction.Urgent = false

        def hit():
            self._hit_watches = [w for w in self._hit_watches
                                 if w[4] is not hit]
            # RoutineActionHitWoody.OnActionStarted (cs:24-33) opens with
            # Owner.PauseMovement: nothing integrates or arrives from here
            # on — a door descent in progress would otherwise land on the
            # floor and hand the walk's arrival to the stopped routine
            catcher.movement_paused = True
            catcher.velocity = (0.0, 0.0)
            catcher.steps = []
            catcher.on_arrive = None
            catcher.state = catcher.IDLE
            seqs = [q for q in catcher.hit_action.get('sequences', [])
                    if all(catcher.anim.has(a) for a in q)]
            # MoveToEmptySpace (Rottweiler.cs:1156-1203, Mother.cs:142): the
            # catcher snaps onto Woody's exact position — the hit sheets are
            # anchored there, not at the catcher's own floor line (his
            # PlayerHeightDelta differs) — then backs off the nearest flat
            # door of his zone by MinDistanceToNearestDoor. Only the
            # Rottweiler does this: RoutineActionMotherHitWoody never calls
            # MoveToEmptySpace (RoutineActionMotherHitWoody.cs:24-32,
            # Mother.cs:142 has no caller) — the Mother beats from where
            # her walk stopped
            if catcher.role == 'Rottweiler':
                self._move_to_empty_space(catcher)
            woody.sprite.hidden = True    # the hit sheets contain Woody
            if seqs:
                # GetRandomSequence's thresholds on Range(0,100) weight the
                # four sets 26/25/25/24 (RoutineActionHitWoody.cs)
                num = random.randrange(0, 100)
                pick = 0 if num <= 25 else 1 if num <= 50 else \
                    2 if num <= 75 else 3
                catcher.anim.play_sequence(seqs[min(pick, len(seqs) - 1)],
                                           on_end=self._after_hit)
            else:
                self._after_hit()
        # HitWoodyAction serializes Urgent=false — the catcher walks over
        catcher.in_urgent = False
        # StartAction (ActionManager.cs:146-155) walks only when the action
        # is not already at its location: RoutineActionHitWoody's test is
        # the x distance to Woody against MaximumPawnDistanceToAction
        # (RoutineActionHitWoody.cs:15-18; 0.8 in the levels' data) — a
        # catch at the foot of a door starts the hit where the pawn stands
        maxd = catcher.hit_action.get('max_distance') or 0.03
        if abs(catcher.sprite.x - woody.sprite.x) <= maxd:
            hit()
        elif catcher.goto_zone(woody.zone, woody.sprite.x, on_arrive=hit):
            # MoveToAction: the walk ends the frame the distance drops under
            # MaximumPawnDistanceToAction (RoutineActionMove.Finished,
            # cs:39-40), 0.8 in the data — well short of Woody himself
            self._hit_watches.append((catcher, woody, maxd, False, hit))
        else:
            hit()

    def _move_to_empty_space(self, catcher):
        """Rottweiler.MoveToEmptySpace (Rottweiler.cs:1156-1203); Mother's
        copy is identical. No flat door in the zone means no reposition."""
        woody = self.woody
        door = None
        best = None
        for d in self.level.doors:
            if d.should_walk_up:
                continue
            if catcher.zone is None or d.zone != catcher.zone.pid:
                continue
            dist = ((woody.sprite.x - d.x) ** 2
                    + (woody.sprite.y - d.y) ** 2) ** 0.5
            if best is None or dist < best:
                best, door = dist, d
        if door is None:
            return
        catcher.sprite.x = woody.sprite.x
        catcher.sprite.y = woody.sprite.y
        dx = woody.sprite.x - door.x
        if abs(dx) < catcher.min_door_distance:
            catcher.sprite.x += catcher.min_door_distance \
                * (1.0 if dx >= 0 else -1.0)

    def _after_hit(self):
        """the beating's end: the ending in the mobile game, a respawn under
        the PC profile's lives"""
        if getattr(self, '_respawning', False):
            self._respawn()
        else:
            self._finish_animation_ended()

    def _respawn(self):
        """PC profile only (docs/PC_FIDELITY.md 2.5): Woody reappears, the
        catcher goes back to his routine, the clock and the tricks stay as
        they are. Season 2 (pcprofile.s2_respawn) is the catch fiber's case
        4: the room of fcn.10005f58 (_pc_respawn_zone), the middle of its
        path — x the two ends' mean, 0x10006330-0x1000634a — where the
        `respawn` action lands him from 900 px up (its translation, ticks
        0-5), and the action's job holds his queue until case 5
        (_pc_respawn_landed); without a room, the level entrance"""
        self._respawning = False
        w = self.woody
        catcher = getattr(self, '_last_catcher', None)
        z_pc = self._pc_respawn_zone() if self._pc_catch_seq else None
        if w is not None:
            w.sprite.hidden = False
            w.frozen = False
            w.movement_paused = False
            w.input_locked = z_pc is not None
            w.steps = []
            w.on_arrive = None
            w.state = w.IDLE
            w.hiding = False
            if z_pc is not None:
                pr = z_pc.pc_room
                x_pc = (pr['x1'] + pr['x2']) // 2
                w.sprite.x = z_pc.left + (x_pc - pr['x1']) * (z_pc.right - z_pc.left) \
                    / float((pr['x2'] - pr['x1']) or 1)
                w.sprite.y = w.floor_y(z_pc)
                w.pos_snap = True
                w.zone = z_pc
            else:
                loc = self.level.entrance_location
                if loc:
                    w.sprite.x, w.sprite.y = loc
                    w.pos_snap = True      # a legal snap for the continuity invariant
                    z = self.level.zone_at(loc[0], loc[1])
                    if z is not None:
                        w.zone = z
            for name in ('switch_to_stand', 'stand'):
                if hasattr(w.anim, name):
                    getattr(w.anim, name)()
                    break
        if catcher is not None:
            catcher.movement_paused = False
            catcher.state = catcher.IDLE
            catcher.steps = []
            catcher.on_arrive = None
            for r in self.routines:
                if r.pawn is catcher:
                    r.unfreeze()
        self.game.got_caught = False
        if z_pc is not None:
            # the remaster has no landing sheet: he stands through the job
            self.call_later(pcprofile.S2_RESPAWN_ACTION_TICKS
                            / float(pcprofile.S2_TICK_HZ), self._pc_respawn_landed)
        elif self._pc_catch_seq:
            self._pc_respawn_landed()

    def _pc_respawn_zone(self):
        """fcn.10005f58, the room the catch fiber's case 4 drops Woody into:
        every room of the level in the order of its map (the names' — the
        iterator fcn.1004018d, the UTF-16 compare fcn.10058390) scores 50
        with more than one <neighbor> record (0x1000610c: 0 with one), 101
        more with an object flagged `hideout` in it (0x100060b7; Loader.dll
        maps the name to 0x40 at 0x10009e4e — PCRoom `hideout`), 50 less
        with a `bad` actor (0x8000, 0x10009ff2: the neighbour's and the
        Mother's generic record) in the room and in his hideout (flag 4,
        0x100060a0) and 10000 less with one out of it (0x10006139); the
        first room scoring above 0 and above every earlier one is taken
        (0x1000613f). An actor counts in the room its pointer names
        (fcn.10040a7d, Pawn.pc_room)"""
        best, score = None, 0
        bad = [p for p in (self.pawns.get('Rottweiler'), self.pawns.get('Mother'))
               if p is not None]
        for z in sorted((z for z in self.level.zones if z.pc_room is not None),
                        key=lambda z: z.pc_room['room']):
            pr = z.pc_room
            s = 50 if len(pr.get('nb') or ()) > 1 else 0
            if pr.get('hideout'):
                s += 101
            there = [p for p in bad if p.pc_room() is z]
            if any(p.pc_flag4 for p in there):
                s -= 50
            if any(not p.pc_flag4 for p in there):
                s -= 10000
            if s > score:
                best, score = z, s
        return best

    def _pc_respawn_landed(self):
        """the catch fiber's case 5 (0x10006274-0x100062c7), the respawn
        job done: the catch's flag 0x10000 off Woody and fcn.10042471 — the
        life taken, the respawn timer at respawntime (0x100424b6), the
        outline on (0x10042515)"""
        self._pc_catch_seq = False
        self.game.lives -= 1
        self._pc_respawn_left = pcprofile.S2_RESPAWN_TICKS / float(pcprofile.S2_TICK_HZ)
        w = self.woody
        if w is not None:
            w.input_locked = False

    def _pc_catch_barred(self):
        """the Season 2 catch is the catchers' `fight` behaviour on Woody and
        Woody's `die` on them (generic/trigger.xml); both predicates (slot 4
        of the vtables 0x100b0eec / 0x100b0e8c, fcn.1003d526 / fcn.1003cd8e)
        refuse while the catch's flag 0x10000 is on the behaviour's actor
        (0x1003d6b5 / 0x1003cf1d: set by both behaviours' starts,
        0x1003d4bf / 0x1003cd27, cleared off Woody by the fiber's case 5)
        and while the respawn timer runs with Woody a party (0x1003d5f9,
        0x1003d646 / 0x1003ce61, 0x1003ceae)"""
        return self._pc_catch_seq or self._pc_respawn_left > 0.0

    def pc_outlined(self):
        """GFXEngine's flag +0x39 on Woody's sprite: on at case 5
        (0x10042515), off when the level update's countdown reaches 0
        (0x10044765) — the respawn timer's span"""
        return self._pc_respawn_left > 0.0

    def blow_whistle(self):
        """PC profile only (docs/PC_FIDELITY.md 2.1): the dog whistle, an
        inventory use with no target — every sleeping alerter wakes as if it
        had heard Woody, and the neighbour's HearAlerter chain follows
        (Alerter.WakeUp -> CoRoutineRottweilerHearAlerter)"""
        if not pcprofile.is_pc() or self.woody is None:
            return False
        if not self.inventory.has('IT_Whistle'):
            return False
        n = 0
        for fsm in self.alerters.values():
            if not fsm.alert:
                fsm.animation_type = 1
                fsm.triggered_by_woody = False
                fsm.wake_up()
                n += 1
        return n > 0

    def _finish_game(self):
        """GameInfo.FinishGame (GameInfo.cs:358-371), shared by every ending:
        the neighbour drops the cake, Woody freezes and his input locks, the
        description bubble closes, GameEnding, the camera snaps to Woody and
        freezes, and the score is computed right here (CalculateScore)"""
        rott = self.pawns.get('Rottweiler')
        if rott is not None:
            rott.holding_cake = False     # Rottweiler.SetHoldCake(false), cs:362
        w = self.woody
        if w is not None:
            self._freeze_woody()          # Woody.Freeze, cs:364
            w.input_locked = True         # cs:365
        if self.hud is not None:
            self.hud.show_description = False   # cs:366
        self.game.ending = True           # cs:367
        if self.snap_camera is not None:
            self.snap_camera()            # SnapToWoodyImmediate, cs:368
        self.camera_frozen = True         # GameCamera.Freeze, cs:369
        self._score()                     # CalculateScore, cs:370

    def _freeze_woody(self):
        """Woody.Freeze (Woody.cs:993-997): Frozen — the click gate of
        CheckMouseClick (Woody.cs:637) and the alerter flinch's gate
        (Woody.cs:1040) — plus PauseMovement. The port also drops his path:
        the original keeps it and resumes it once the finish pose's stand
        switch runs ContinueMovement (PawnAnimationController.cs:97) — a
        walk under the score screen this port does not reproduce."""
        w = self.woody
        w.frozen = True
        w.movement_paused = True
        if not w.is_warping:              # a pass in flight completes as is
            w.steps = []
            w.state = w.IDLE

    def _freeze_pawn(self, pawn):
        """Rottweiler.Freeze / Mother.Freeze (Rottweiler.cs:1095-1099,
        Mother.cs:136-140): SwitchToStandAnimation, then PauseMovement — the
        pawn's own freeze, not ActionManager.Freeze: the routine keeps
        ticking on a pawn that cannot move"""
        st = pawn._stand_name()
        if st:
            pawn.anim.play_looping(st)
        pawn.movement_paused = True

    def _finish_animation_ended(self):
        """GameInfo.FinishAnimationEnded (GameInfo.cs:343-356): GameEnded
        (the score board, HUD.DrawScore cs:731), every active sleep bar is
        disabled, and the three pawns freeze"""
        self.game.ended = True
        # DisableAllProgressBars (cs:346, 535-541) -> ProgressBar.
        # DisableProgressBar on every subscribed (active) bar (cs:303-307)
        for pb in self.progress_bars:
            pb.disable()
        if self.woody is not None:
            self._freeze_woody()          # cs:347
        for role in ('Rottweiler', 'Mother'):
            p = self.pawns.get(role)      # cs:348-355
            if p is not None:
                self._freeze_pawn(p)

    def _score(self):
        """GameInfo.CalculateScore (GameInfo.cs:392-431, called from
        FinishGame at cs:370): the arithmetic lives in
        GameState.calculate_score; this hands it the two live inputs the
        original reads off other objects — Rottweiler.AngryCountTicks
        (cs:396-398, 416) and Woody.NFH2Path (cs:394)"""
        rott = self.pawns.get('Rottweiler')
        if pcprofile.is_pc():
            self.game.pc_min_rating = pcprofile.min_rating(self.level.name)
        self.game.calculate_score(
            rott.angry_count_ticks if rott is not None else 0,
            nfh2=self.woody.nfh2 if self.woody is not None else False,
            elapsed=self.time)
        if self.on_score_computed is not None:
            self.on_score_computed()      # Level.SaveScore (cs:409/429)

    def _time_up(self):
        """GameInfo.Update's clock arm (GameInfo.cs:241-249): TimeUp = true,
        then FinishGameOnHUDClick — Won is NOT touched, so a player who
        reached WinningTricksCount and let the clock run out still gets the
        success jingle and the EXCELLENT/GOOD/PASSED band (CalculateRating
        checks Won before TimeUp, cs:438-465)"""
        self.game.time_up = True
        self.finish_game_on_hud_click()

    def finish_game_on_hud_click(self):
        """GameInfo.FinishGameOnHUDClick (GameInfo.cs:373-390): FinishGame,
        Woody's win/lose animation, the neighbour and the Mother freeze,
        then the outcome jingle by Won — PlaySuccess(Perfect) or the failed
        music. GameEnded comes only from FinishAnimationEnded, at the end
        of the finish pose. The original shows the ExitConfirmation dialog
        first on an exit door (Pawn.cs:1378-1383) — the menu widgets are
        not modelled, so the pass ends the level directly."""
        g = self.game
        self._finish_game()               # cs:375
        self._play_finish_animation()     # cs:376
        for role in ('Rottweiler', 'Mother'):
            p = self.pawns.get(role)      # cs:377-381
            if p is not None:
                self._freeze_pawn(p)
        if g.won:                         # cs:382-389
            self._play_jingle('success_perfect'
                              if g.final_viewer_rating >= 100 else 'success')
        else:
            self._play_jingle('failed')

    def _play_finish_animation(self):
        """Woody.PlayFinishAnimation (Woody.cs:1104-1128): mid-door-pass the
        finish waits for the arrival (ShouldPlayFinish, replayed at
        OnDoorEnterAnimationFinished, Woody.cs:490-493); hiding, Woody
        leaves the spot first and the finish rides the leave animation's
        blocking end (OnBlockingAnimationEnded, Woody.cs:331-334); else
        IsPlayingFinish and WinAnimation / LoseAnimation by Won, whose end
        is FinishAnimationEnded (Woody.cs:325-327). Both deferrals also
        stamp LastInputTime."""
        w = self.woody
        if w is None:
            return False
        if w.is_warping:                  # IsPassingDoor(), cs:1106-1111
            self.should_play_finish = True
            self._last_input_time = self.time
            return True
        if w.hiding:                      # cs:1112-1118
            self.should_play_finish = True
            self._last_input_time = self.time
            w.unhide()                    # -> HideItem.Leave -> LeaveAnimation
            # the leave animation is a blocking single: its end replays the
            # finish (OnBlockingAnimationEnded, Woody.cs:331-334)
            if w.anim.mode == 'single':
                w.anim.on_end = self._play_finish_animation
                w.anim.as_sequence = False
            else:
                self._play_finish_animation()
            return True
        self.should_play_finish = False
        self.is_playing_finish = True     # cs:1119
        name = w.win_animation if self.game.won else w.lose_animation
        if name and w.anim.has(name):     # cs:1120-1127
            w.anim.play_sequence([name],
                                 on_end=self._finish_animation_ended,
                                 as_sequence=False)
            return True
        # the original throws on a missing pose (no data does); the port
        # ends the game at once instead of parking it
        self._finish_animation_ended()
        return False

    def _win(self):
        """GameInfo.PlayWinAnimations (GameInfo.cs:304-313): FinishGame,
        Woody's win animation, only the Rottweiler freezes here (the Mother
        keeps moving until FinishAnimationEnded, cs:343-356), and
        PlaySuccess(perfect: true) regardless of the rating"""
        self._finish_game()               # cs:306
        self._play_finish_animation()     # cs:307
        rott = self.pawns.get('Rottweiler')
        if rott is not None:
            self._freeze_pawn(rott)       # Rottweiler.Freeze, cs:308-311
        self._play_jingle('success_perfect')   # cs:312

    def start_music(self, elapsed, clap=True, music_on=True, audio_on=True):
        """IntroAnimation.StartGame's sound side (cs:309-312 ->
        PlayEntranceMusic) with the scene-load clocks `elapsed` seconds in:
        the 15 s PlayLevelMusic Invoke (MusicPlayer.cs:71-80) keeps its
        remainder; `clap` plays the EntranceClap MusicPlayer.Start fired at
        the load (cs:43-47) when nobody did yet. The settings' gates:
        the clap and the track ride Level.MusicEnabled (PlayEffectsMusic
        cs:168-176, PlayMusic cs:90-96), the entrance Level.AudioEnabled
        (IntroAnimation.cs:309-312); the bare viewer passes both True."""
        music, m = self.music_bank, self.level.music
        if music is None or m is None:
            return
        if clap and music_on and m.get('clap'):
            music.play_music(m['clap'], loop=False, offset=elapsed)
        if music_on and m.get('level'):
            self._music_timer = max(0.0, (m.get('delay') or 0.0) - elapsed)
        if audio_on and m.get('entrance'):
            music.play_entrance(m['entrance'])

    def _play_jingle(self, key):
        """MusicPlayer.PlayEffectsMusic: the jingle stops the level track
        (MusicPlayer.cs:143-176)"""
        if self.music_bank is None or self.level.music is None:
            return
        self._music_timer = None
        name = self.level.music.get(key)
        if name:
            self.music_bank.play_music(name, loop=False)
        else:
            self.music_bank.stop_music()

    def tick_ambient(self, dt):
        """the title-card span: the item/door controllers animate
        (AnimationControllerBase.OnGUI refreshes regardless of the intro,
        cs:172-189) while every actor waits for CanStart
        (IntroAnimation.StartGame, cs:293-299) and the clock holds
        (GameInfo's timer gates on IntroAnimation.Finished, cs:241) — the
        port's world clock starts at StartGame, so the cards phase advances
        only the ambient AnimPlayers"""
        pawn_players = {id(p.anim) for p in self.pawns.values()}
        for p in self.players.values():
            if id(p) not in pawn_players:
                p.tick(dt)

    def tick(self, dt):
        self.time += dt                  # Time.time
        # PlayLevelMusic's first-run delay (MusicPlayer.cs:88-98); the
        # track loops per the serialized LevelMusicSource flag
        if self._music_timer is not None:
            self._music_timer -= dt
            if self._music_timer <= 0.0:
                self._music_timer = None
                self.music_bank.play_music(
                    self.level.music['level'],
                    loop=self.level.music.get('loop', True))
        # the MonoBehaviour.Invoke queue (GameInfo.InvokeMethodForSetPrime)
        for entry in self._delayed[:]:
            entry[0] -= dt
            if entry[0] <= 0.0:
                self._delayed.remove(entry)
                entry[1]()
        # the entrance walk (Woody.cs:223-229): the timer runs down, he walks
        # to Level.EntranceLocation, and arrival unlocks the input
        # (OnFinishedEntrance)
        if self._entrance_timer is not None and self.woody is not None:
            # EntranceTimer -= Time.deltaTime in Woody.Update (Woody.cs:225):
            # 0.5 s runs out on the 30th frame (a double's countdown would
            # leave +1e-16 for a 31st)
            self._entrance_timer -= dt
            if self._entrance_timer <= WAIT_EPS:
                self._entrance_timer = None
                self.woody.start_move_flags()   # StartMoveToLocation(0)
                ex, ey = self.level.entrance_location or \
                    (self.woody.sprite.x, self.woody.sprite.y)

                def _entrance_done():
                    # the path's end plays the Hello greeting while the
                    # entrance is unfinished (Pawn.cs:1064-1067); its
                    # blocking end is what unlocks the input
                    # (Woody.OnBlockingAnimationEnded, Woody.cs:304-312)
                    w = self.woody
                    name = w.hello_animation

                    def _unlock():
                        w.input_locked = False
                        w.finished_entrance = True
                        self._entrance_hello = False
                    if name and w.anim.has(name):
                        self._entrance_hello = True
                        w.anim.play_sequence([name], on_end=_unlock,
                                             as_sequence=False)
                    else:
                        w.input_locked = False
                if not self.woody.goto(ex, ey, on_arrive=_entrance_done):
                    self.woody.input_locked = False
                    self.woody.finished_entrance = True
        elif self.woody is not None and self.woody.input_locked and \
                not self.woody.finished_entrance and \
                not getattr(self, '_entrance_hello', False) and \
                self.woody.state == self.woody.IDLE and not self.woody.steps:
            # an unfinished entrance that has nowhere to walk: unlock as
            # OnFinishedEntrance would (Season 1 only — a FinishedEntrance
            # Woody's lock is StartGame's NFH2 one, lifted by the Entrance
            # single's end, Woody.cs:372-375)
            self.woody.input_locked = False     # OnFinishedEntrance
            self.woody.finished_entrance = True
        self._tick_open_furniture(dt)
        # Woody.Update's dexterity retry (Woody.cs:218-222): the frame after
        # WinDexterity latched DexterityDone (DexterityComponent.cs:369-373),
        # TryUseItem re-runs on the same step — CanWoodyUse now falls
        # through its DexterityDone branch to the unlock and the take
        # (Item.cs:1445-1474, 1482-1507); DexterityAux is the one-shot, which
        # that branch clears again (cs:1463, 1496)
        wd = self.woody
        if wd is not None and wd.dexterity_done and not wd.dexterity_aux:
            wd.dexterity_aux = True
            if wd.use_target is not None:
                self._woody_try_use(wd.use_target)
        # the postponed flinch fires once the use chain ends (Woody.cs:232)
        if self.woody is not None and self.woody.postponed_alerter is not None \
                and not self.woody.animations_in_progress:
            it0, self.woody.postponed_alerter = self.woody.postponed_alerter, None
            self.woody_see_alerter(it0)
        # Woody.FindInput's boredom (Woody.cs:612-623): 30 idle seconds
        # play a random stretch/yawn — Season 1 only (the NFH2Path gate)
        w0 = self.woody
        if w0 is not None:
            if w0.state != w0.IDLE or self.game.ending:
                self._last_input_time = self.time
            elif not w0.hiding and \
                    self.time - self._last_input_time > w0.idle_threshold:
                self._last_input_time = self.time
                if not w0.nfh2 and w0.idle_animations:
                    import random
                    name = random.choice(w0.idle_animations)
                    if w0.anim.has(name):
                        w0.anim.play_single(name)
        # HideDuringWoodyUseAnim rides Woody.Update's itemAux watch
        # (Woody.cs:237-250): hidden while his current animation is the
        # item's use animation, shown again after
        ua = self._woody_use_anim_item
        if ua is not None and self.woody is not None:
            cur = self.woody.anim.anim.name
            if cur == ua.animation and not self._woody_use_anim_hidden:
                self.set_object_hidden(ua, True)
                self._woody_use_anim_hidden = True
            elif cur != ua.animation and self._woody_use_anim_hidden:
                self._woody_use_anim_hidden = False
                self.set_object_hidden(ua, False)
        # every AnimationControllerBase refreshes once per frame (OnGUI's
        # Repaint -> Refresh, AnimationControllerBase.cs:172-189); a pawn's
        # controller is the AnimPlayer its Pawn.tick advances, so the item
        # pass skips those — ticking them here as well ran every pawn
        # animation at twice its FrameRate
        pawn_players = {id(p.anim) for p in self.pawns.values()}
        for p in self.players.values():
            if id(p) not in pawn_players:
                p.tick(dt)
        # RoutineActionMove.Finished for a move toward a pawn (RoutineAction
        # Move.cs:26-41): the x distance to the target under
        # MaximumPawnDistanceToAction — and for a HitPawn, its zone
        # (RoutineActionHitPawn.cs:13-18) — ends the move and starts the
        # action; ActionManager.Update reads it before ProcessMovement
        for w in list(self._hit_watches):
            catcher, target, maxd, same_zone, reach = w
            if catcher.is_warping:
                continue
            if same_zone and (catcher.zone is None or target.zone is None
                              or catcher.zone.pid != target.zone.pid):
                continue
            if abs(catcher.sprite.x - target.sprite.x) < maxd:
                self._hit_watches.remove(w)
                # MoveAction.OnActionStopped: Velocity = 0, PauseMovement
                # (RoutineActionMove.cs:98-103) — the hit takes it from here
                catcher.steps = []
                catcher.on_arrive = None
                catcher.velocity = (0.0, 0.0)
                catcher.state = catcher.IDLE
                reach()
        for p in self.pawns.values():
            if p is not self.woody:
                p.tick(dt)
        for r in self.routines:
            r.tick(dt)
        # the behaviors' MonoBehaviour.Update bodies (enabled components only)
        for b in self.behavior_objs:
            if b.enabled:
                b.update(dt)
        for pb in self.progress_bars:
            pb.tick(dt)
        for ds in self.dex_states.values():
            if ds.pc_offer is not None:
                ds.pc_offer_tick(dt)
            ds.tick(dt)
        # SearchItem/TrickItem.Update's deferred dexterity alert
        # (SearchItem.cs:245-251, TrickItem.cs:243-249)
        rott = self.pawns.get('Rottweiler')
        if rott is not None and rott.state == rott.WALK:
            for it in self.level.items.values():
                if it.dexterity_alert is None:
                    continue
                ds = self.dex_states.get(it.dexterity_alert)
                if ds is not None and ds.rott_in_animation:
                    ds.rott_in_animation = False
                    rt = next((r for r in self.routines if r.pawn is rott),
                              None)
                    if rt is not None and ds.item is not None:
                        _dex_surprise(self, rt, ds.item)
        # SearchItem.Update's animation switcher (SearchItem.cs:214-244)
        # and TrickItem.Update's UseMultipleTimes sync (TrickItem.cs:226-241)
        for it in self.level.items.values():
            if it.kind == 'SearchItem' and it.sprite is not None:
                self._search_switch(it)
            if it.use_multiple_times:
                linked = self.level.items.get(it.linked_item_trick) \
                    if it.linked_item_trick else None
                if linked is not None:
                    linked.use_once = linked.tricked
                it.use_once = it.tricked
        # the Kid pawn's flag machine (Kid.cs:25-51)
        kid = self.pawns.get('Kid')
        if kid is not None:
            self._kid_update(kid)
        for fsm in self.alerters.values():
            fsm.tick(dt)
        if self.woody:
            self.woody.tick(dt)
        if pcprofile.is_pc() and self.woody is not None \
                and pcprofile.s2_sight(self.woody.nfh2):
            self._pc_flag4_tick()
        # the WinGameAnimations coroutine (GameInfo.cs:298-302): armed by
        # WinGameOnCompleteAllTricks, it runs on its own clock outside
        # Update's GameEnding gate and fires PlayWinAnimations after 2.5 s
        if self.game.win_timer is not None:
            self.game.win_timer -= dt
            if self.game.win_timer <= 0.0:
                self.game.win_timer = None
                self._win()
        # GameInfo.Update, the Classic checks (GameInfo.cs:203-256), gated
        # on !GameEnded && !GameEnding (cs:212) and in the original's order:
        # the neighbour's catch, the Mother's, the all-tricks win, the clock
        if self.game.ending or self.game.ended:
            return
        # (the PC's Season 2 respawn timer: the level update counts it down
        # after the watch walker has fired, 0x10044725 past 0x100445f1)
        barred = self._pc_catch_barred()
        if self._pc_respawn_left > 0.0:
            self._pc_respawn_left = max(0.0, self._pc_respawn_left - dt)
        if self.can_rottweiler_see_woody():
            if not self.game.got_caught and not barred:
                self._catch()             # cs:214-221
        elif self.can_mother_see_woody():
            if not barred:
                self._catch(self.pawns.get('Mother'))   # cs:222-225, no gotCaught guard
        elif self.game.all_done():
            # cs:226-236: WinGameOnCompleteAllTricks sets GameEnding at once
            # and starts the 2.5 s coroutine (cs:292-302) — the clock, the
            # catches and the HUD are dead for the wait while Woody's own
            # input stays live (Frozen comes with FinishGame at its end);
            # WinImmediate (ForceWinGame, cs:315-321) plays the win now
            if not self.game.win_immediate:
                self.game.ending = True
                self.game.win_timer = 2.5
            else:
                self._win()
        elif self.game.timed:
            # the clock (cs:237-255; the IntroAnimation.Finished gate belongs
            # to the unported title cards): timed games count down and end
            # the game at zero, untimed ones count up
            if self.game.time_seconds > 0.0:
                self.game.time_seconds -= dt
                if int(self.game.time_seconds) <= 0:
                    self._time_up()       # TimeUp + FinishGameOnHUDClick
        else:
            self.game.time_seconds += dt
