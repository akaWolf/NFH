"""Gameplay simulation, following the decompiled source method by method.

The references in comments are to src/Assembly-CSharp: AnimationControllerBase
(frame stepping), AnimationInstance (frame model), Pawn (movement, doors),
Item (use range), ActionManager / RoutineAction* (the routine), Door, Zone.
"""

# `this is TrickItem` in C# is true for the subclasses too
TRICK_KINDS = ('TrickItem', 'Drawing', 'Rake', 'Toilet', 'Television')


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
        self.ignore_infinite = False     # SetIgnoreInfiniteLoop
        self.ignore_infinite_once = False
        self.sound_sink = sound_sink
        self.stand_hook = None           # PawnAnimationController falls back to
                                         # a stand pose; item controllers don't
        # behavior dispatch (Actor.BehaviorPlayAnimation / OnAdvanceFrame from
        # InitializeCurrentAnimation and Refresh; the sequence-end hook is
        # Rottweiler.OnAnimationSequenceEnded's BehaviorOnAnimationSequenceEnded)
        self.on_play = []
        self.on_advance = []
        self.seq_end_hook = None
        self.last_element_hook = None    # OnLastSequenceElementPlaying
        self.seq_step_hook = None        # PlayNextSequenceAnimation's name-hacks
        self.single_end_hook = None      # the OnAnimationEnded delegate
        self._set_start()

    # -- state -------------------------------------------------------------
    @property
    def anim(self):
        return self.sprite.anims[self.sprite.current]

    def has(self, name):
        return name in self.by_name

    def _set_start(self):
        """AnimationInstance.SetStartFrame"""
        a = self.anim
        self.pat_idx = 0
        self.frame = a.pattern[0] if a.pattern else a.start
        self.acc = 0.0
        self.sprite.cur_frame = self.frame

    def current_index(self):
        """AnimationInstance.CurrentIndex — the sound key"""
        a = self.anim
        return self.pat_idx if a.pattern else self.frame - a.start

    # -- starting animations ----------------------------------------------
    def _set(self, name, mode):
        i = self.by_name.get(name)
        if i is None:
            raise RuntimeError('No animation found !!! State: %s, Owner: %s'
                               % (name, self.sprite.name))
        self.sprite.current = i
        self.mode = mode
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
        its own serialized type instead of being forced Single."""
        i = self.by_name.get(name)
        if i is None:
            raise RuntimeError('No direct animation found !!! State: %s, '
                               'Owner: %s' % (name, self.sprite.name))
        a = self.sprite.anims[i]
        return self._set(name, 'looping' if a.type_looping else 'single')

    def play_looping(self, name, abort_if_playing=True):
        if abort_if_playing and self.anim.name == name and self.mode == 'looping':
            return True
        self.seq = []                     # PlayLoopingAnimation: sequence = null
        self.as_sequence = False
        self.on_end = None
        return self._set(name, 'looping')

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
        """AnimationControllerBase.IsPlayingBlockingAnimation"""
        return self.anim.blocking

    def waiting(self):
        """diagnostic only: parked on something that cannot finish"""
        return (self.anim.infinite or self.mode == 'looping') and not self.seq

    # -- stepping ----------------------------------------------------------
    def _reached_end(self):
        a = self.anim
        if a.pattern:
            return self.pat_idx >= len(a.pattern)
        return self.frame > a.end

    def _advance(self):
        a = self.anim
        if a.pattern:
            self.pat_idx += 1
            if self.pat_idx < len(a.pattern):
                self.frame = a.pattern[self.pat_idx]
        else:
            self.frame += 1
        self.sprite.cur_frame = min(self.frame, a.end)

    def _loop_to_start(self):
        a = self.anim
        self.pat_idx = 0
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
        cb, self.on_end = self.on_end, None
        was_seq, self.as_sequence = self.as_sequence, False
        if was_seq and self.seq_end_hook is not None:
            # Rottweiler.OnAnimationSequenceEnded opens with
            # BehaviorOnAnimationSequenceEnded (Rottweiler.cs:448), before
            # the ActionManager.StopCurrentAction the callback stands for
            self.seq_end_hook()
        if self.single_end_hook is not None:
            # OnAnimationEnded delegates: Item.OnItemAnimationCompleted and
            # Woody.OnSingleAnimationEnded's show-after restore ride here
            self.single_end_hook(self.anim.name)
        if cb:
            cb()
        elif self.stand_hook is not None:
            name = self.stand_hook()
            if name and self.has(name):
                self.play_looping(name)

    def tick(self, dt):
        self.acc -= dt
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
                       or self.mode == 'looping')
            if looping:
                self._loop_to_start()
            else:
                if a.infinite and self.ignore_infinite_once:
                    self.ignore_infinite_once = self.ignore_infinite = False
                if a.hold:
                    if not a.pattern:
                        self.frame = a.end
                        self.sprite.cur_frame = a.end
                    # held: never advances the sequence (Refresh does the same)
                else:
                    self._stop_single()
        fps = self.anim.fps or 10.0
        self.acc += 1.0 / fps
        if self.slow_factor:
            self.acc *= self.slow_factor


class Pawn:
    """Pawn movement: 2D dominant-axis walking along the floor line, portal
    climbs for walk-up doors and items."""

    IDLE, WALK = 'idle', 'walk'
    DOOR_CLIMB, DOOR_ANIM, DESCEND, ITEM_CLIMB = \
        'door_climb', 'door_anim', 'descend', 'item_climb'

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
        self.portal_up = spec.get('portal_up')
        self.portal_down = spec.get('portal_down')
        # Rottweiler's anger meter (fields on the pawn, Rottweiler.cs:50-56)
        self.angry_meter = 0.0
        self.angry_decay = spec.get('angry_decay') or 0.0
        self.angry_max = spec.get('angry_max') or 100.0
        self.can_decrease_angry = True
        self.angry_count_ticks = 0
        self.sneaking = False
        self.sneak_toggle = False        # Woody.MbSneakToggle
        self.in_urgent = False           # Pawn.InUrgentMove
        self.movement_paused = False     # Pawn.MovementPaused
        self.hiding = False              # Woody.Hiding (SetHidden override)
        self.hiding_item = None
        self.is_warping = False          # Pawn.IsWarping, set by door transit
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
        self.toilet_action = spec.get('toilet_action') or {}
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
        self.ignore_woody = spec.get('ignore_woody') or False
        self.fear_left = spec.get('fear_left') or 'FearLeft'
        self.fear_right = spec.get('fear_right') or 'FearRight'
        self.win_animation = spec.get('win_animation')
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
        self._exit_door = None
        self.world = None                # set by World, for zone reactions
        self.anim.stand_hook = self._stand_name
        start = self.default_anim if self.default_anim and \
            self.anim.has(self.default_anim) else self._stand_name()
        if start:
            self.anim.play_looping(start)

    def _stand_name(self):
        """PawnAnimationController.SwitchToStandAnimation by last facing"""
        name = self.stand.get(self.facing, 'Stand_' + self.facing)
        if self.anim.has(name):
            return name
        if self.default_anim and self.anim.has(self.default_anim):
            return self.default_anim
        return None

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
            if self.in_urgent:
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
        if self.role in ('Mother', 'Olga') and self.in_urgent:
            return 'Run_' + direction
        return 'Walk_' + direction

    def _portal_up_anim(self):
        """Rottweiler.GetPortalUpAnimation (Rottweiler.cs:398-413)"""
        if self.role == 'Rottweiler':
            if self.feel_sick:
                return 'RunWCUp'
            if self.in_urgent:
                return 'Run_Up'           # PortalRunUpAnimation's default
            if self.has_fifi:
                return 'FifiWalkUp'
        return self.portal_up

    def _portal_down_anim(self):
        """Rottweiler.GetPortalDownAnimation (Rottweiler.cs:415-434)"""
        if self.role == 'Rottweiler':
            if self.feel_sick:
                return 'RunWCDown'
            if self.in_urgent:
                return 'Run_Down'         # PortalRunDownAnimation's default
            if self.has_fifi:
                return 'FifiWalkDown'
            if self.has_skates:
                return 'SkiWalk2'
        return self.portal_down

    # -- geometry ----------------------------------------------------------
    def floor_y(self, zone=None):
        """Helpers.GetDefaultZoneY: zone y + HeightDelta + PlayerHeightDelta"""
        z = zone or self.zone
        return z.ty + z.height_delta + self.height_delta

    def at_zone_y(self):
        """Pawn.IsPawnAtZoneY"""
        return abs(self.sprite.y - self.floor_y()) < 0.1

    def moving_to_adjacent_zone(self):
        """Pawn.IsMovingToAdjacentZone = TransitionMove: the current path
        step heads through a Transition door (Pawn.cs:1281-1283, 1712)."""
        s = self._step
        return (s is not None and s.get('kind') == 'door'
                and s['door'].door_type == 'Transition')

    def at_use_range(self, it):
        """Item.IsAtUseRange — the walk-phase check, with the x term"""
        if self.zone is None or self.zone.pid != it.zone:
            return False
        mx = it.move_x(self.role)
        my = it.y + it.dy
        if it.should_walk_up:
            return (abs(self.sprite.y - my) < self.item_threshold + it.delta_use_height
                    and abs(self.sprite.x - mx) < it.use_distance)
        return abs(self.sprite.x - mx) < it.use_distance

    def at_use_location(self, obj):
        """Pawn.IsAtUseLocation — the climb-phase check: y only, against the
        object's own transform, not its move location"""
        return abs(self.sprite.y - obj.y) < self.item_threshold + obj.delta_use_height

    # -- commands ----------------------------------------------------------
    def start_move_flags(self):
        """Woody.StartMoveToLocation: sneak comes from the toggle, a plain
        click is an urgent (running) move, and moving leaves a hiding spot."""
        self.sneaking = self.sneak_toggle
        self.in_urgent = not self.sneaking
        if self.hiding:
            self.unhide()

    def hide(self, item):
        """Woody.Hide + HideItem.InternalUse"""
        self.hiding = True
        self.hiding_item = item
        if item.hide_woody:
            self.sprite.hidden = True
        p = self.world.players.get(id(item.sprite)) \
            if self.world and item.sprite else None
        if p is not None and item.hide_anim and p.has(item.hide_anim):
            p.play_single(item.hide_anim)

    def unhide(self):
        """Woody.Unhide + HideItem.Leave"""
        self.hiding = False
        self.sprite.hidden = False
        item, self.hiding_item = self.hiding_item, None
        if item is None or self.world is None:
            return
        p = self.world.players.get(id(item.sprite)) if item.sprite else None
        if p is not None and item.hide_idle and p.has(item.hide_idle):
            p.play_single(item.hide_idle)
        if item.leave_animation and self.anim.has(item.leave_animation):
            self.anim.play_single(item.leave_animation)

    def goto(self, x, y, on_arrive=None):
        dest = self.level.zone_at(x, y)
        if dest is None:
            return False
        return self._route(dest, {'kind': 'point',
                                  'x': min(max(x, dest.left), dest.right)},
                           on_arrive)

    def goto_zone(self, dest, x, on_arrive=None):
        if dest is None:
            return False
        return self._route(dest, {'kind': 'point', 'x': x}, on_arrive)

    def goto_item(self, it, on_arrive=None):
        """BuildPathToItem: route to the zone; an elevated item gets a plain
        floor step at its x first (min-dist 0.03 plus the passed-target snap),
        so the climb starts with no horizontal error."""
        dest = self.level.zone_by_pid(it.zone)
        if dest is None:
            return False
        final = {'kind': 'item', 'item': it, 'x': it.move_x(self.role)}
        if it.should_walk_up:
            final = [{'kind': 'point', 'x': it.move_x(self.role)}, final]
        return self._route(dest, final, on_arrive)

    def _route(self, dest, final_step, on_arrive):
        self.on_arrive = on_arrive
        steps = []
        # BuildPathToTarget: when starting elevated, first walk down to the floor
        if not self.at_zone_y():
            steps.append({'kind': 'point', 'x': self.sprite.x,
                          'y': self.floor_y()})
        if dest.pid != self.zone.pid:
            hops = self.level.find_path(self.zone.pid, dest.pid)
            if hops is None:
                self.on_arrive = None
                return False
            for _, door in hops:
                steps.append({'kind': 'door', 'door': door})
        if isinstance(final_step, list):
            steps.extend(final_step)
        else:
            steps.append(final_step)
        self.steps = steps
        self._next_step()
        return True

    # -- step machinery ----------------------------------------------------
    def _next_step(self):
        self._step = None
        if not self.steps:
            self.state = self.IDLE
            st = self._stand_name()
            if st:
                self.anim.play_looping(st)
            cb, self.on_arrive = self.on_arrive, None
            if cb:
                cb()
            return
        self._step = self.steps.pop(0)
        self._step_sign = None
        self.state = self.WALK

    def _step_target(self):
        """MoveLocation for the current step. CheckMoveLocationY forces y to
        the floor for door and item steps — climbs are separate states."""
        s = self._step
        if s['kind'] == 'point':
            return s['x'], s.get('y', self.floor_y())
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
        self.facing = 'Right' if dx > 0 else 'Left'

    def walk_speed_scale(self):
        return self.speed_sneaking if self.sneaking else self.speed

    # -- door transit -------------------------------------------------------
    def _door_anims(self, door):
        if self.role == 'Woody':
            return door.leave, door.enter
        return door.rott_leave, door.rott_enter

    def _begin_transit(self, door):
        """MoveToDoor's portal branch. A flat door fires both sides at once; a
        walk-up door climbs first and then runs Leave -> Enter sequentially
        (OnDoorLeaveAnimationFinished chains the far side)."""
        other = self.level.door_by_pid(door.link_to)
        if other is None:
            self.state = self.IDLE
            return
        if (door.passing is not None and door.passing is not self) or \
                (other.passing is not None and other.passing is not self):
            st = self._stand_name()
            if st:
                self.anim.play_looping(st)
            return                        # IsOtherPawnPassing: wait standing
        if door.should_walk_up:
            self.state = self.DOOR_CLIMB
            up = self._portal_up_anim()
            if up and self.anim.has(up):
                self.anim.play_looping(up)
            return
        self._transit_animations(door, other, sequential=False)

    def _transit_animations(self, door, other, sequential):
        self.state = self.DOOR_ANIM
        # PlayDoorLeaveAnimation: SetHidden(true) hides the controller for
        # every pawn, and the `is Woody` branch hides Woody's own too
        # (Pawn.cs:1615-1635) — the door sheets contain the walking figure
        self.hidden = True
        self.sprite.hidden = True
        self.is_warping = True            # PlayDoorLeaveAnimation: IsWarping
        self._exit_door = other
        door.passing = other.passing = self
        if self.world:
            self.world.zone_reaction(door.zone, 'leave')
            if not sequential:
                self.world.zone_reaction(other.zone, 'enter')
        leave_anim, _ = self._door_anims(door)
        _, enter_anim = self._door_anims(other)
        if sequential:
            # walk-up: Leave first; its end starts the far Enter
            def leave_done():
                door.passing = None
                self._door_idle(door)
                if self.world:
                    self.world.zone_reaction(other.zone, 'enter')
                self._play_enter(other, enter_anim)
            if door.sprite is not None and leave_anim:
                # Door.PlayAnimation is a PlaySingleAnimation (Door.cs:141-153)
                door.sprite.play_sequence([leave_anim], on_end=leave_done,
                                          as_sequence=False)
            else:
                leave_done()              # Door.PlayAnimation's null branch
        else:
            if door.sprite is not None and leave_anim:
                door.sprite.play_sequence(
                    [leave_anim], on_end=lambda: self._leave_played(door),
                    as_sequence=False)
            else:
                door.passing = None
            self._play_enter(other, enter_anim)

    def _door_idle(self, door):
        """Door.OnAnimationEnded ends every pass animation with
        ReturnToIdleAnimation (Door.cs:155-197)"""
        if door.sprite is not None and door.idle and door.sprite.has(door.idle):
            door.sprite.play_single(door.idle)

    def _play_enter(self, other, enter_anim):
        if other.sprite is not None and enter_anim:
            other.sprite.play_sequence([enter_anim], on_end=self._enter_played,
                                       as_sequence=False)
        else:
            self._enter_played()

    def _leave_played(self, door):
        door.passing = None
        self._door_idle(door)

    def _enter_played(self):
        """OnDoorEnterAnimationFinished: warp, unhide, loop ExitAnimation;
        a walk-up far door means climbing back down to the floor."""
        d = self._exit_door
        if d is None:
            return
        d.passing = None
        self._door_idle(d)
        old_zone = self.zone.pid if self.zone else None
        self.sprite.x = d.x + self.door_delta[0]
        self.sprite.y = d.y + self.door_delta[1]
        self.zone = self.level.zone_by_pid(d.zone) or self.zone
        # Rottweiler.OnDoorEnterAnimationFinished: a flat-door exit snaps the
        # neighbour back onto the floor line (Rottweiler.cs:168-172)
        if self.role == 'Rottweiler' and not d.should_walk_up:
            self.sprite.y = self.floor_y()
        self.hidden = False
        self.sprite.hidden = False        # SetHidden(false), Pawn.cs:1661
        self.is_warping = False           # OnDoorEnterAnimationFinished
        if self.world is not None and old_zone != (self.zone.pid if self.zone else None):
            if self.world.on_pawn_zone_changed(self, old_zone):
                return                    # OnChangeZone returned true: taken over
        if d.exit_anim and self.anim.has(d.exit_anim):
            self.anim.play_looping(d.exit_anim)
        if d.should_walk_up and self.steps:
            self.state = self.DESCEND
            down = self._portal_down_anim()
            if down and self.anim.has(down):
                self.anim.play_looping(down)
            return
        self._next_step()

    # -- tick ---------------------------------------------------------------
    def tick(self, dt):
        self.anim.tick(dt)
        # Rottweiler.Update: the meter decays while allowed
        if self.can_decrease_angry and self.angry_meter > 0.0:
            self.angry_meter = max(0.0, self.angry_meter - self.angry_decay * dt)
        if self.movement_paused:          # ProcessMovement's outer gate
            return
        scale = self.walk_speed_scale() * dt
        if self.state == self.WALK:
            tx, ty = self._step_target()
            dx, dy = tx - self.sprite.x, ty - self.sprite.y
            mag = (dx * dx + dy * dy) ** 0.5
            # HasPassedTarget: WalkOnPath also stops when the pawn has crossed
            # the target x — a step can be bigger than UseDistance, and without
            # this the pawn oscillates around the goal forever
            sign = (dx > 0) - (dx < 0)
            passed = (self._step_sign is not None and sign != 0
                      and sign != self._step_sign)
            if self._step_sign is None and sign != 0:
                self._step_sign = sign
            if passed:
                self.sprite.x = tx        # MoveToItem snaps onto the target
            if mag <= self._min_dist() or passed:
                s = self._step
                if s['kind'] == 'door':
                    self._begin_transit(s['door'])
                elif s['kind'] == 'item' and s['item'].should_walk_up:
                    it = s['item']
                    if self.at_use_location(it):
                        self._next_step()
                        return
                    self.state = self.ITEM_CLIMB
                    up = self._portal_down_anim() if it.should_walk_down \
                        else self._portal_up_anim()
                    if up and self.anim.has(up):
                        self.anim.play_looping(up)
                else:
                    self._next_step()
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
            if abs(nx) >= abs(ny):
                f = self.run_force if self.in_urgent else self.force
                vx, vy = nx * f, ny * f
                self._face_towards(nx)
                self.anim.play_looping(self._walk_anim(self.facing))
            else:
                f = self.run_door_force if self.in_urgent else self.door_force
                vx, vy = nx * f, ny * f
                self.anim.play_looping(
                    self._walk_anim('Up' if ny > 0 else 'Down'))
            self.sprite.x += vx * scale
            self.sprite.y += vy * scale
        elif self.state == self.DOOR_CLIMB:
            # checks run before the move, as MoveToDoor runs before
            # ProcessMovement applies the velocity
            d = self._step['door']
            if self.at_use_location(d):
                other = self.level.door_by_pid(d.link_to)
                if other is not None:
                    self._transit_animations(d, other, sequential=True)
                else:
                    self.state = self.IDLE
                return
            self.sprite.y += self.door_force * scale
        elif self.state == self.DESCEND:
            # IsAtPortalTargetLocation: signed, no snapping afterwards
            if self.sprite.y - self.floor_y() < self.zone_threshold:
                self._next_step()
                return
            self.sprite.y -= self.door_force * scale
        elif self.state == self.ITEM_CLIMB:
            it = self._step['item']
            if self.at_use_location(it):
                self._next_step()         # velocity zero; on_arrive fires use
                return
            direction = -1.0 if it.should_walk_down else 1.0
            self.sprite.y += direction * self.door_force * scale


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
        if self._see_delay is not None:
            self._see_delay -= dt
            if self._see_delay <= 0.0:
                self._see_delay = None
                if self.can_see_woody():
                    self.world.woody_see_alerter(self.item)
        if self._hear_delay is not None:
            self._hear_delay -= dt
            if self._hear_delay <= 0.0:
                self._hear_delay = None
                self.world.rott_hear_alerter(self, self.triggered_by_woody)

    def on_notice_woody(self):
        self.wake_up()
        self._see_delay = self.item.alerter_delay

    def wake_up(self):
        self._hear_delay = self.item.alerter_delay
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
    """InventoryManager: a flat list, a selected UsedInventory."""

    def __init__(self):
        self.items = []                  # dicts: {'type','use_count','name'}
        self.used = None                 # UsedInventory

    def add(self, new_items):
        """InventoryManager.AddInventory"""
        self.items.extend(dict(i) for i in new_items)

    def has(self, required):
        """InventoryManager.HasInventory"""
        return any(i['type'] == required for i in self.items)

    def is_using(self, required):
        """InventoryManager.IsUsingInventory"""
        return self.used is not None and self.used['type'] == required

    def remove(self, required):
        """InventoryManager.RemoveInventory: first match only"""
        for i, it in enumerate(self.items):
            if it['type'] == required:
                del self.items[i]
                break
        if self.used is not None and self.used['type'] == required and \
                not self.has(required):
            self.used = None

    def select(self, idx):
        self.used = self.items[idx] if 0 <= idx < len(self.items) else None


class GameState:
    """GameInfo: trick counters and the win flags."""

    def __init__(self, info):
        self.total = info.get('total', 0)
        self.winning = info.get('winning', 0)
        self.completed = 0
        self.won = False
        self.linked_trick = False
        self.compound_tricks = 0
        self.log = []
        self.got_caught = False          # GameInfo.gotCaught
        self.ending = False              # GameInfo.GameEnding (FinishGame)
        self.ended = False               # GameInfo.GameEnded (FinishAnimationEnded)
        self.win_timer = None            # WinGameOnCompleteAllTricks' 2.5s wait
        # the clock: TimedGame counts down from TimeMinutes, else up
        # (GameInfo.Start 171-177, Update 239-254; PlayerPrefs default is on)
        self.timed = True
        self.time_seconds = (info.get('time_minutes') or 0.0) * 60.0
        self.time_up = False
        self.is_tutorial = bool(info.get('is_tutorial'))
        self.compound_trick_score = info.get('compound_trick_score') or 0
        self.dont_show_angry_count = bool(info.get('dont_show_angry_count'))
        # the score screen strings (GameInfo.CalculateScore)
        self.rating = ''
        self.trick_ratio = ''
        self.viewer_rating = ''
        self.final_viewer_rating = 0
        self.on_trick_done = None        # Woody.PlayTrickDone -> the HUD

    def calculate_score(self, angry_count_ticks, nfh2=False):
        """GameInfo.CalculateScore + CalculateRating (GameInfo.cs:392-465).
        The label lines ride localization files that are not extracted, so
        only the value halves render."""
        if not nfh2:
            compound = self.compound_trick_score
            if not self.is_tutorial and angry_count_ticks < compound:
                compound = angry_count_ticks
            final = sum(self.log) + self.completed * compound
        else:
            final = int(self.completed * 90.0 / max(1, self.total))
            if angry_count_ticks == 1:
                final += 10
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

    def trick_done(self, score):
        """GameInfo.TrickDone (GameInfo.cs:467): Woody.PlayTrickDone leads"""
        if self.on_trick_done is not None:
            self.on_trick_done()
        if self.linked_trick:
            self.linked_trick = False
            self.completed += 1
        self.completed += 1
        self.log.append(score)
        if self.completed >= self.winning:
            self.won = True

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
        self.frozen = spec['frozen']
        self.state = self.IDLE
        self.timer = 0.0
        self.on_use = None
        self.log = []
        self._pending = None
        self.urgent_item = None          # ActionManager.UrgentAction's item
        self.was_alerted = None          # Rottweiler.WasAlerted + RottAlerter
        self.pending_alarm = None        # ShouldStartSurpriseActionFar
        self._urgent_handler = None      # a chain step's own arrival handler
        self._fix_tool = None            # the FixingItem being fetched
        self._fix_target = None          # the tricked item it fixes
        self.marbles_next = False        # ActionManager.MarblesNextAction
        self.remove_watering_can = False  # the L108 watering-can dance
        self.remove_now = False
        self.routine_behavior = None     # Pawn.RoutineBehavior instance
        self.alarm_next_action = False   # ActionManager.AlarmNextAction
        self.action_changed = False      # ActionManager.ActionChanged
        self.cont_aux = -1               # ActionManager.ContAux (KidActions)
        self._same_zone = False          # ActionManager.SameZone (Dog/Chili)
        self._same_zone_yelled = False   # ActionManager.AngryAnimationStarted
        self._alarm_use = False          # the AlarmAction urgent runs a full Use
        self._angry_target = None        # the item the current angry set is for
        self._wait_in_fear_done = None   # the parked resume of the affect flow
        self._hit_target = None          # RoutineActionHitPawn.Target
        self._toilet_run = False         # the ToiletAction urgent is running
        # Rottweiler.Start wires the controller delegates (Rottweiler.cs:152)
        if role == 'Rottweiler':
            self.pawn.anim.last_element_hook = self._on_last_seq_element
            self.pawn.walk_hook = self._update_walking
        self.pawn.anim.seq_step_hook = self._seq_step_hack

    @property
    def action(self):
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

    def _on_last_seq_element(self):
        """Rottweiler.OnLastSequenceElementPlaying (Rottweiler.cs:256-263):
        an AlertNext use makes the next action's item ring while the last
        sequence element still plays — Level105's phones."""
        a = self.action
        it = self.item
        if (self.state == self.USING and self.urgent_item is None
                and a is not None and a.get('alert_next') and it is not None
                and not it.is_tricked(self.level.items)):
            i = self.index + 1
            if i >= len(self.actions):    # AdvanceActionIndex's wrap
                i = self.start_index if self.loop_from_start else \
                    (self.selected_index or 0)
            nxt = self.level.items.get(self.actions[i]['item']) \
                if self.actions[i]['item'] else None
            if nxt is not None and self.pawn.world is not None:
                self.pawn.world.play_alert_animation(nxt)

    def _seq_step_hack(self, player, idx):
        """PlayNextSequenceAnimation's two name-hacks
        (AnimationControllerBase.cs:261-275): the ChairAssembly hide at
        sequence index 1 when the book is armed, and Olga's TowelSleep
        element turning its own instance into an infinite loop."""
        it = self.item if self.urgent_item is None else self.urgent_item
        if idx == 1 and it is not None and it.name == 'ChairAssembly':
            book = next((b for b in self.level.items.values()
                         if b.name == 'ChairAssemblyBook'), None)
            if book is not None and book.got_tricked and it.sprite is not None:
                it.sprite.hidden = True   # SetObjectHidden(true)
        if self.role == 'Olga' and idx < len(player.seq) \
                and player.seq[idx] == 'TowelSleep' \
                and player.has('TowelSleep'):
            player.sprite.anims[player.by_name['TowelSleep']].infinite = True

    def _advance(self):
        self.index += 1
        if self.index >= len(self.actions):
            if self.loop_from_start:
                self.index = self.start_index
            elif self.selected_index:
                self.index = self.selected_index
            else:
                self.index = 0

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

    def _start_action(self, start_next=False):
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
        if a is not None and a.get('move_only'):
            if self.routine_behavior is not None:
                # ActionManager.MoveToAction (ActionManager.cs:119-124)
                self.routine_behavior.on_move_to_routine_action(None, a)
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
            # RoutineActionMove.cs:68-75)
            self.pawn.in_urgent = bool(a.get('urgent'))
            if not self.pawn.goto_item(it, on_arrive=self._use):
                self._pending = 'advance'
                self.state = self.IDLE

    def _use(self):
        it = self.item
        a = self.action
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
        if a.get('mutex'):
            # MutexAction parks on its looping animation until another action's
            # PawnToAbortMutexOnFinish releases it (RoutineActionUse.cs:172-179)
            self.state = self.USING
            self.timer = 0.0
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
            if leg is not None:
                seq = [x for x in leg if self.pawn.anim.has(x)]
                self.state = self.USING
                self.timer = a['duration']
                if a.get('hide_owner'):
                    self.pawn.set_hidden(True)   # cs:213-216
                self._after_use_side_effects(a, it)
                if seq:
                    self.pawn.anim.play_sequence(seq, on_end=self._finish)
                else:
                    # no prime animation: StopCurrentAction(canPostponeStop:
                    # false) — no angry postpone (Item.cs RottweilerPrime tail)
                    self._action_stopped()
                    self._pending = 'advance'
                    self.state = self.IDLE
                return
        # Item.RottweilerUse's FixingItem dispatch (Item.cs:836-858): a raw-
        # Tricked item that names a fixing tool sends him fetching (neutral or
        # ForceUseFixingItem), and with the right tool in hand the item is
        # fixed and the tool used instead
        if self.role == 'Rottweiler' and w is not None and it.tricked \
                and it.fixing_item is not None:
            if self._fixing_dispatch(it):
                return
            tool = self.level.items.get(it.fixing_item)
            if tool is not None and self.pawn.fixing_item is tool:
                w._fix(it)                     # Item.cs:854-857: Fix(); tool use
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
            if it.tricked:
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
        seq = it.sequence_for(self.role, tricked, self.level.items)
        if self.role == 'Olga' and it.is_tricked(self.level.items) \
                and it.use_olga_tricked_flag:
            seq = it.use_tricked_anim.get('Olga') or []
        # the LaunchPad name-hack (TrickItem.cs:896-902): an untricked pad
        # with a tricked harpoon plays the harpoon's tricked set instead and
        # arms the StopAction hand-off
        linked = self.level.items.get(it.linked_item_trick) \
            if it.linked_item_trick else None
        if self.role == 'Rottweiler' and it.name == 'LaunchPad' \
                and not it.tricked and linked is not None and linked.tricked:
            it.harpoon_aux = True
            seq = linked.sequence_for(self.role, True, self.level.items)
            if w is not None:
                w.play_tricked_item_anim(linked)
        # the pig-pen gate (TrickItem.cs:837-841): primed-and-tricked keys
        # with the milk still clean play the surprise set instead
        if it.depends_pig_keys and self.role == 'Rottweiler' and w is not None:
            keys = self.level.items.get(it.pig_keys)
            milk = self.level.items.get(it.pig_milk)
            if keys is not None and keys.primed and keys.tricked and \
                    (milk is None or not milk.tricked):
                seq = it.rott_surprise
        # TrickItem.RottweilerUse's own side arms (TrickItem.cs:566-630)
        if self.role == 'Rottweiler' and w is not None:
            hoda = self.level.items.get(it.hide_object_during_animation) \
                if it.hide_object_during_animation else None
            if hoda is not None:              # cs:574-578
                w.set_object_hidden(hoda, True)
                w.set_tricked_object_hidden(hoda, True)
            dep = self.level.items.get(it.depends_on) \
                if it.depends_on is not None else None
            if it.hide_during_rott_animation:  # cs:579-593
                if it.tricked or (dep is not None and dep.tricked):
                    if it.tricked_object_go is not None:
                        w.set_tricked_object_hidden(it, True)
                    else:
                        w.set_object_hidden(it, True)
                elif not it.tricked and it.name != 'ChairAssembly':
                    w.set_object_hidden(it, True)
            if it.disable_collider_after_use:  # cs:594-598
                it.clickable = False
                it.can_use = False
            if it.use_at_other_place:          # cs:599-607
                if it.should_return:
                    it.at_home = not it.at_home
                    w.set_active_object_hidden(it, not it.at_home)
                    it.clickable = it.at_home
            elif it.tricked:                   # cs:608-611
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
        if it.set_olga_x_on_use and self.role == 'Olga':
            self.pawn.sprite.x = it.x
        self.log.append((it.name, tricked))
        if self.on_use:
            self.on_use(it, tricked)
        # the item plays its own use pose alongside the pawn's sequence
        # (TrickItem.PlayUseAnimation / PlayTrickedAnimation, cs:947-994)
        if w is not None and it.kind in TRICK_KINDS:
            if tricked or (self.role == 'Rottweiler' and it.tricked):
                w.play_tricked_item_anim(it)
            elif not it.fucked_up:
                w.play_use_item_anim(it)
        if seq:
            self.pawn.anim.play_sequence(list(seq), on_end=self._finish)
        else:
            # an empty sequence completes at once, and the angry postpone
            # still rides StopAction (OnUseAnimationsCompleted ->
            # StopAction(canPostponeStop: true)) — the invisible valves
            # of Level113 depend on this
            self._finish()

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
        if w is None or a is None or a.get('move_only'):
            return
        items = self.level.items
        for pid in a.get('doors_to_unlock') or ():     # cs:390-393
            d = self.level.door_by_pid(pid)
            if d is not None:
                w.unlock_door(d)
        for pid in a.get('items_to_unlock') or ():     # cs:394-397
            tgt = items.get(pid)
            if tgt is not None:
                tgt.locked = False
        if it.tricked:                                 # cs:398-404
            for pid in a.get('items_to_unlock_tricked') or ():
                tgt = items.get(pid)
                if tgt is not None:
                    tgt.locked = False
        dont_on_owner = it.dont_use_on is not None and \
            w.pawn_by_pid(it.dont_use_on) is self.pawn
        dx, dy = it.rott_use_item_exit_delta
        if (dx > 0 or dy > 0) and not it.exit_delta_aux and it.tricked:
            if not dont_on_owner:                      # cs:428-440
                self.pawn.sprite.x += dx
                self.pawn.sprite.y += dy
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

    def _finish(self):
        """RoutineActionUse.StopAction(canPostponeStop: true): the side
        effects run, then a tricked TrickItem does not finish the action —
        the owner plays the angry sequence first (RoutineActionUse.cs:
        541-553). The stop also removes spent actions (cs:415-427)."""
        it = self.item
        a = self.action
        if it is not None:
            self._stop_side_effects(a, it)
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
            if it.kind == 'TrickItem' and it.is_tricked(self.level.items):
                target = self._tricked_item(it)
                if target is not None:
                    self._angry_target = target
                    w.play_angry(self.pawn, target, on_done=self._angry_done)
                    return
        self._action_stopped()
        self._pending = 'advance'

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
        self._action_stopped()
        if target is not None and target.reuse_after_fix:
            self._pending = 'start'
        else:
            self._pending = 'advance'

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

    def _action_stopped(self):
        """RoutineActionUse.OnActionStopped (RoutineActionUse.cs:319-353):
        MoveOnly returns first; then the ignore flags reset, the once-on-end
        target fires, HideOwnerDuringUse unhides (cs:481-484), and a
        non-mutex action releases PawnToAbortMutexOnFinish's parked mutex."""
        a = self.action
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
        if a.get('hide_owner'):
            self.pawn.set_hidden(False)   # cs:481-484
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
        if not a.get('mutex'):
            self._abort_parked_mutex(a.get('abort_mutex_pawn'))

    def _abort_parked_mutex(self, pid):
        """OnActionStopped's PawnToAbortMutexOnFinish branch
        (RoutineActionUse.cs:344-351): SetHidden(false) on the named pawn,
        then AbortActiveMutex (cs:127-134) finishes its mutex action with
        *no* OnActionStopped — flags set at its start deliberately stay."""
        if pid is None or self.pawn.world is None:
            return
        role = next((r for r, s in self.level.pawns.items()
                     if s.get('pid') == pid), None)
        if role is None:
            return
        for rt in self.pawn.world.routines:
            if rt.role == role:
                rt.pawn.set_hidden(False)
                act = rt.action
                if act is not None and act.get('mutex'):
                    rt._pending = 'advance'
                return

    # -- urgent interruptions (ActionManager.StartUrgentAction and the
    #    Rottweiler alarm plumbing) -----------------------------------------
    def is_alarm_postponed(self):
        """RoutineActionUse.IsAlarmPostponed: the current action's flag"""
        a = self.action
        return bool(a and a.get('postpone_alarm')) and self.state == self.USING

    def moving_to_alarm(self):
        """Rottweiler.MovingToAlarm"""
        return self.urgent_item is not None and self.urgent_item.kind == 'Alerter'

    def start_urgent(self, item, arrived=None, alarm_use=False):
        """Rottweiler.StartSurpriseActionFar -> ActionManager.StartUrgentAction:
        drop the move in progress and run (SurpriseActionFar.Urgent) to the
        item; the interrupted action stays current for the resume. A chain
        step (the fixing-tool run) brings its own arrival handler; alarm_use
        marks the AlarmAction, whose arrival runs a full Item.Use."""
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
        self.urgent_item = item
        self._urgent_handler = arrived
        self._alarm_use = alarm_use
        self.pawn.steps = []
        self.pawn.in_urgent = True
        self.state = self.MOVING
        # the SameZone shortcut (RoutineActionMove.SameZone + ActionManager.
        # Update, ActionManager.cs:442-458): an urgent run to Dog or Chili in
        # the pawn's own zone starts the action at once, and the walk with
        # the proximity yell follows
        if (item.name in ('Dog', 'Chili') and self.pawn.zone is not None
                and item.zone == self.pawn.zone.pid
                and not self.pawn.is_warping
                and not self.pawn.at_use_range(item) and arrived is None):
            self._same_zone = True
            self._same_zone_yelled = False
            self._urgent_arrived()
            return
        if self.routine_behavior is not None:
            # StartAction interposes MoveToAction for the away case
            # (ActionManager.cs:152-154, 119-124)
            if not self.pawn.at_use_range(item):
                self.routine_behavior.on_move_to_routine_action(item, None)
        if self.pawn.at_use_range(item):
            self._urgent_arrived()
        elif not self.pawn.goto_item(item, on_arrive=self._urgent_arrived):
            self._urgent_finished()

    def _urgent_arrived(self):
        """RoutineActionSurpriseFar.OnActionStarted"""
        handler, self._urgent_handler = self._urgent_handler, None
        if handler is not None:
            handler()
            return
        it = self.urgent_item
        if it is None:
            return
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
            if seq:
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
        if it is not None and it.kind in TRICK_KINDS \
                and it.is_tricked(self.level.items) \
                and self.pawn.world is not None:
            self.pawn.world.play_angry(self.pawn, it,
                                       on_done=self._urgent_finished)
        else:
            self._urgent_finished()

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
        self.urgent_item = None
        self.pawn.in_urgent = False
        self.pawn.can_decrease_angry = True
        if getattr(self, '_toilet_run', False):
            # Rottweiler.OnUseEnded ends the sickness (cs:879-892) and
            # OnActionStopped drops IsUsingToilet (cs:354-357)
            self._toilet_run = False
            self.pawn.feel_sick = False
            self.pawn.is_using_toilet = False
        self._same_zone = False
        self._same_zone_yelled = False
        self._alarm_use = False
        if self.role == 'Mother' and self.pawn.world is not None:
            # StopUrgentAction fires the Mother event (ActionManager.cs:592-595)
            self.pawn.world.fire_event('mother_urgent_stop')
        if self.frozen:
            # a frozen manager swallows the resume (ActionManager.cs:604-606);
            # the Unfreeze that lifts it starts the routine again
            self.state = self.IDLE
            return
        if finished is not None and finished.name == 'GroundMarbles':
            self.marbles_next = False
        it = self.item
        if it is not None and it.got_tricked and not self.marbles_next and \
                it.name not in ('WateringCan', 'ValveHot', 'ValveMain'):
            # the skip goes straight to StartAction, without the
            # StartNextAction extras (ActionManager.cs:614-619)
            self._pending = 'skip'
        else:
            self._pending = 'start'
        self.state = self.IDLE

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

    def run_to_fixing_item(self, tool, tricked):
        """Rottweiler.RunToFixingItem (Rottweiler.cs:1077-1082): shift the
        tricked item's stand spot by DeltaFixLocation, wire the chain, and
        run to the tool as an urgent action."""
        tricked.dx += tricked.delta_fix_x
        tricked.dy += tricked.delta_fix_y
        self._fix_tool = tool
        self._fix_target = tricked
        self.start_urgent(tool, arrived=self._grab_arrived)

    def _grab_arrived(self):
        """RoutineActionGrab.OnActionStarted -> OnSequenceEnded: play the
        GrabSequence, hide the tool, carry it, hop to the tricked item."""
        seq = [x for x in self.pawn.grab_action.get('sequence', [])
               if self.pawn.anim.has(x)]
        self.state = self.USING

        def grabbed():
            tool = self._fix_tool
            if tool is not None and tool.sprite is not None:
                tool.sprite.hidden = True    # SetActiveObjectHidden(true)
            self.pawn.fixing_item = tool     # Rottweiler.FixingItem = Item
            self.start_urgent(self._fix_target,
                              arrived=self._use_fixing_arrived)
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
                w.play_angry(self.pawn, tool, on_done=self._use_fixing_arrived)
            self.state = self.USING
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
        if seq:
            self.pawn.anim.play_sequence(seq, on_end=self._fixing_done)
        else:
            self._fixing_done()

    def _fixing_done(self):
        """RoutineActionUseFixingItem.StopAction clears Rottweiler.FixingItem;
        OnActionStopped starts the Return urgent when ShouldReturnFixingItem
        (its Item is pre-serialized to the tool)."""
        self.pawn.fixing_item = None
        if self.pawn.use_fixing_action.get('should_return') \
                and self._fix_tool is not None:
            self.start_urgent(self._fix_tool, arrived=self._return_arrived)
        else:
            self._fix_tool = self._fix_target = None
            self._urgent_finished()

    def _return_arrived(self):
        """RoutineActionReturn: the ReturnSequence, then the tool reappears
        (SetObjectHidden(false)) and the routine resumes."""
        seq = [x for x in self.pawn.use_fixing_action.get('return_sequence', [])
               if self.pawn.anim.has(x)]
        self.state = self.USING

        def returned():
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
        cur = self.item if self.state == self.USING else None
        postponed = self.is_alarm_postponed() and \
            not (cur is not None and cur.tricked)
        if not self.pawn.is_warping and not postponed:
            if self.pawn.alarm_postponed:
                # Rottweiler.cs:275-279: a behavior's PostponeAlarm parks it
                self.pending_alarm = alerter_item
                return
            if self.state == self.MOVING:
                self.start_urgent(alerter_item)
                return
            if self.state == self.USING and \
                    (self.item is None or self.item.name != 'Bed'):
                self.was_alerted = alerter_item     # consumed when he moves
            if self.pawn.animal_tutorial:
                # Intro103's frozen tutorial neighbour: Unfreeze and run
                # (Rottweiler.cs:290-295; CheckHiddenItem is a no-op here,
                # HideObjectDuringUse being unported)
                self.frozen = False
                self.start_urgent(alerter_item)
        else:
            self.pending_alarm = alerter_item       # PostponeAlerterAction

    def _update_walking(self):
        """Rottweiler.UpdateWalking (Rottweiler.cs:833-849): a tricked
        NoticeWhenWalkNearby item within NoticeWhenNearTrickedDistance slips
        (CauseSlip -> FallAction) or startles (SurpriseActionNear) — both are
        RoutineActionSurpriseNear instances."""
        w = self.pawn.world
        if w is None or self.pawn.zone is None or self.urgent_item is not None:
            return
        for it in w.near_items.get(self.pawn.zone.pid, ()):
            if it.tricked and \
                    abs(self.pawn.sprite.x - it.target_x) \
                    < self.pawn.notice_near_distance:
                self._on_surprise_near(it)
                return

    def _on_surprise_near(self, it):
        """Rottweiler.OnSurpriseNear / OnFall -> StartUrgentAction ->
        RoutineActionSurpriseNear.OnActionStarted (cs:12-37): pause, postpone
        the alarm, and the facing-matched surprise sequence shifted by
        SurpriseDeltaLocation."""
        self.urgent_item = it
        self.pawn.steps = []
        self.pawn.state = self.pawn.IDLE
        self.pawn.movement_paused = True      # Owner.PauseMovement
        self.postpone_alarm()                 # Owner.PostponeAlarm
        seq = it.surprise_right if self.pawn.facing == 'Right' \
            else it.surprise_left             # Owner.IsMovingRight
        self.pawn.sprite.x += it.surprise_delta[0]
        self.pawn.sprite.y += it.surprise_delta[1]
        self.state = self.USING
        seq = [a for a in seq if self.pawn.anim.has(a)]
        if seq:
            self.pawn.anim.play_sequence(seq, on_end=self._surprise_near_done)
        else:
            self._surprise_near_done()

    def _surprise_near_done(self):
        """the drain reaches StopAction(canPostponeStop: true): a tricked
        item goes angry first (RoutineActionSurpriseNear.cs:47-57)"""
        it = self.urgent_item
        if it is not None and it.tricked and self.pawn.world is not None:
            self.pawn.world.play_angry(self.pawn, it,
                                       on_done=self._surprise_near_stopped)
        else:
            self._surprise_near_stopped()

    def _surprise_near_stopped(self):
        """OnActionStopped (cs:39-45): ContinueMovement, ContinueAlarm and
        the pending-alarm check, then the interrupted action resumes"""
        self.pawn.movement_paused = False
        self.continue_alarm()
        self._urgent_finished()

    def run_to_hit_pawn(self, target_pawn):
        """Pawn.RunToHitPawn (Pawn.cs:1837-1841) -> StartUrgentAction(
        HitPawnAction): walk into the target's zone within
        MaximumPawnDistanceToAction, then the hit choreography
        (RoutineActionHitPawn.cs:13-45)."""
        if self.frozen:
            return
        if self._pending in ('advance', 'skip'):
            self._advance()
        self._pending = None
        self._hit_target = target_pawn
        self.urgent_item = None
        self.pawn.steps = []
        self.pawn.in_urgent = True
        self.state = self.MOVING
        maxd = self.pawn.hit_pawn_action.get('max_distance') or 0.03
        if self.pawn.zone is target_pawn.zone and \
                abs(self.pawn.sprite.x - target_pawn.sprite.x) < maxd:
            self._hit_pawn_arrived()
        elif target_pawn.zone is None or not self.pawn.goto_zone(
                target_pawn.zone, target_pawn.sprite.x,
                on_arrive=self._hit_pawn_arrived):
            self._hit_pawn_arrived()

    def _hit_pawn_arrived(self):
        """RoutineActionHitPawn.OnActionStarted (cs:20-38): the target —
        the neighbour being hit — hides (the hit sheets contain him), the
        owner's current item can reveal itself, and the HitPawnSequence
        plays. The Olga toilet-delay arm rides the unported Bouquet hack."""
        target = getattr(self, '_hit_target', None)
        w = self.pawn.world
        if target is None or w is None:
            self._urgent_finished()
            return
        target.sprite.hidden = True       # Target.AnimController.Hidden
        oit = self.item
        if oit is not None and oit.show_item_when_affected:
            w.set_object_hidden(oit, False)    # cs:32-36
        seq = [x for x in self.pawn.hit_pawn_action.get('sequence', ())
               if self.pawn.anim.has(x)]
        self.state = self.USING
        if seq:
            self.pawn.anim.play_sequence(seq, on_end=self._hit_pawn_done)
        else:
            self._hit_pawn_done()

    def _hit_pawn_done(self):
        """RoutineActionHitPawn.OnActionStopped (cs:40-45): the target
        reappears and its parked angry resumes"""
        target, self._hit_target = getattr(self, '_hit_target', None), None
        w = self.pawn.world
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
        self.start_urgent(it, alarm_use=True)

    def postpone_alarm(self):
        """Rottweiler.PostponeAlarm (Rottweiler.cs:1126-1130)"""
        self.pawn.alarm_postponed = True

    def continue_alarm(self):
        """Rottweiler.ContinueAlarm (Rottweiler.cs:1132-1137): drop the
        postpone and fire the parked alerter run; a frozen manager keeps it
        parked until the Unfreeze"""
        self.pawn.alarm_postponed = False
        if self.pending_alarm is not None and not self.frozen:
            it, self.pending_alarm = self.pending_alarm, None
            self.start_urgent(it)
            return True
        return False

    def on_zone_changed(self):
        """Rottweiler.OnChangeZone: tricked noticing items, pending alarms,
        and calming the alerter he was called by. Returns True when it took
        over the pawn — OnChangeZone's own return value."""
        w = self.pawn.world
        for it in w.notice_items.get(self.pawn.zone.pid, ()):
            # the DirtyCarpet is excluded from the generic run
            # (Rottweiler.cs:188) — its urgent rides the Dog/Chili yell
            # choreography instead, which is not modelled
            if it.name == 'DirtyCarpet':
                continue
            if it.tricked:
                # RunToTrickedItem: PauseMovement + a startled look, then the
                # urgent run (consumed in OnSingleAnimationEnded)
                self.pawn.steps = []
                self.pawn.state = self.pawn.IDLE
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
        if self.pending_alarm is not None and not self.is_alarm_postponed() \
                and self._can_check_surprise_far():
            it, self.pending_alarm = self.pending_alarm, None
            self.start_urgent(it)
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
        if self._fix_tool is not None and \
                (self.pawn.grab_action.get('postpone_alarm')
                 or self.pawn.use_fixing_action.get('postpone_alarm')):
            return False                  # IsFixingBlockingItem
        if self.pawn.behaviors:
            return self.pawn.behaviors[0].can_check_surprise_action_far()
        return True

    def tick(self, dt):
        if self.frozen:
            return
        # Rottweiler.Update: a deferred alert fires once he moves again
        if self.was_alerted is not None and self.state == self.MOVING:
            it, self.was_alerted = self.was_alerted, None
            self.start_urgent(it)
            return
        # Rottweiler.Update (Rottweiler.cs:897-901): an AlarmNextAction gate
        # re-checks the pending alarm when the routine advances
        if self.action_changed and self.alarm_next_action:
            self.action_changed = False
            if self.pending_alarm is not None and not self.is_alarm_postponed():
                it, self.pending_alarm = self.pending_alarm, None
                self.start_urgent(it)
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
                    self.state = self.IDLE
                    return
            if what in ('advance', 'skip'):
                self._advance()
            # 'first' and 'advance' are StartNextAction; 'skip' and 'start'
            # go straight to StartAction (ActionManager.cs:608-648)
            self._start_action(start_next=what in ('first', 'advance'))
            return
        if self.state == self.USING and self.timer > 0.0:
            self.timer -= dt
            if self.timer <= 0.0:
                self._finish()


class World:
    def __init__(self, level, sound_sink=None):
        self.level = level
        self.woody = None
        self.pawns = {}
        self.routines = []
        self.game = GameState(level.game_info)
        self.inventory = InventoryState()
        self.players = {id(s): AnimPlayer(s, sound_sink) for s in level.sprites}
        for d in level.doors:
            if d.sprite is not None:
                d.sprite = self.players.get(id(d.sprite))
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
        self.snake_aux_208 = False       # GameInfo.SnakeAux208 (the L208 chain)
        self._entrance_timer = None      # Woody's walk-in countdown
        self.time = 0.0                  # Time.time for the alarm intervals
        self._woody_show_after = []      # Woody.ItemToShowAfterAnim queue
        self._woody_layer_restore = []   # (pawn, depth) from the hide layers
        self._woody_use_anim_item = None  # Woody.itemAux (HideDuringWoodyUseAnim)
        self._woody_use_anim_hidden = False
        self.behavior_objs = []          # live level-behavior instances
        self.search_behavior = None      # Woody.SearchBehavior
        self.events = {}                 # the behaviors' static C# events
        # Item.Start ends in SetPrimed(Primed): the initial primed visibility
        # (Item.cs:697, 1219-1235)
        for it in level.items.values():
            if it.sprite is not None:
                if it.show_only_when_primed:
                    it.sprite.hidden = not it.primed
                if it.hide_when_primed and it.primed:
                    it.sprite.hidden = True
        # TrickItem.OnItemAnimationCompleted (TrickItem.cs:1059-1079): the
        # zone poses and an AnimateAfterUse use pose return to idle
        for it in level.items.values():
            if it.kind in TRICK_KINDS and it.sprite is not None:
                p = self.players.get(id(it.sprite))
                if p is not None:
                    p.single_end_hook = \
                        (lambda name, i=it: self._item_anim_completed(i, name))

    def _on_compound_trick_done(self, item):
        """Item.OnCompoundTrickDone (Item.cs:2161-2169): counts once while
        the item has not paid its plain trick yet"""
        if not item.already_tricked:
            self.game.compound_tricks += 1

    def play_angry(self, pawn, item, on_done=None):
        """Rottweiler.PlayAngryAnimation (Rottweiler.cs:552-797), the
        GameMode.Classic branch, with the name-hack heads, the extra-angry
        insert, the affected-pawn hand-off and the after-run of
        OnAnimationSequenceEnded (FixTrickedItem, the toilet rush)."""
        items = self.level.items
        routine = next((r for r in self.routines if r.pawn is pawn), None)
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
        if self.game is not None:                  # cs:595-612
            if pawn.angry_meter <= 0.0:
                if item.angry_easy_up:
                    seq = [item.angry_easy_up]
                # HUD anger level 1, medium laugh — presentation only
            else:
                pawn.angry_count_ticks += 1
                seq = [a for a in (item.angry_easy_down, item.angry_hard) if a]
                self._on_compound_trick_done(item)   # cs:608
            pawn.angry_meter = pawn.angry_max
        if item.object_to_show_before_angry_go is not None:
            self.set_go_renderer(item.object_to_show_before_angry_go, True)
        if item.kind in TRICK_KINDS:               # cs:698-706
            self.play_item_anim(item, item.before_angry)   # PlayBeforeAngry
            if item.compound and item.compound_tricked:
                self._on_compound_trick_done(item)
        restart = item.reuse_after_fix             # cs:707-714
        if item.name == 'MumStatueFootStool' and item.tricked:
            item.tricked = False                   # cs:715-718

        def after_run(played_angry=True):
            """the OnAnimationSequenceEnded tail (Rottweiler.cs:454-484):
            FixTrickedItem -> TryFix, then the toilet rush; a started fetch
            or toilet run owns the resume"""
            fetch = self._try_fix(item, pawn)
            pawn.can_decrease_angry = True         # Rottweiler.OnUseEnded
            rushed = False
            if not fetch and item.kind in TRICK_KINDS \
                    and item.cause_rush_to_toilet(items) \
                    and routine is not None:       # cs:478-484, 542-550
                if on_done:
                    on_done()
                routine.move_to_toilet(item.cause_sickness)
                rushed = True
            if on_done and not fetch and not rushed:
                on_done()

        if item.angry_without_animations:          # cs:719-736
            if item.kind in TRICK_KINDS and item.cause_rush_to_toilet(items) \
                    and routine is not None:
                if not item.dont_get_angry:
                    self._on_trick_done(item)
                pawn.can_decrease_angry = False
                self._try_fix(item, pawn)
                if on_done:
                    on_done()
                routine.move_to_toilet(item.cause_sickness)
                return
            self._try_fix(item, pawn)
            if not item.dont_get_angry:
                self._on_trick_done(item)
            if on_done:
                on_done()
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
                afr.run_to_hit_pawn(pawn)          # Pawn.RunToHitPawn
                oit = afr.item
                if oit is not None and oit.change_item_anim_when_affected \
                        and oit.item_anim_when_affected:
                    p = self.players.get(id(oit.sprite)) if oit.sprite else None
                    if p is not None and p.has(oit.item_anim_when_affected):
                        p.play_directly(oit.item_anim_when_affected)
            if item.fix_directly:                  # cs:781-784
                self._fix(item)
            if not item.dont_get_angry:
                self._on_trick_done(item)          # cs:785-787
            pawn.can_decrease_angry = False
            return
        # the extra-angry insert, gated for the sand castle (cs:754-766)
        if item.sand_castle_flag:
            if linked is not None and item.tricked and linked.tricked:
                seq = list(item.rott_extra_angry) + seq
        else:
            seq = list(item.rott_extra_angry) + seq
        # the fix animation rides at the tail of the same sequence (cs:767-777)
        if item.can_fix:
            if item.use_fix_sequence:
                seq.extend(item.fix_sequence)
            elif not item.fix_without_animations and item.fix_animation:
                seq.append(item.fix_animation)
        if item.fix_directly:                      # cs:781-784
            self._fix(item)
        if not item.dont_get_angry:
            self._on_trick_done(item)              # cs:785-787
        pawn.can_decrease_angry = False            # cs:793-796
        seq = [a for a in seq if pawn.anim.has(a)]
        if seq:
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
        if item.name == 'Hatch' and linked is not None:
            # the Dexterity arm rides the unported dexterity flow; the
            # LinkedItemTrick activation is the live half
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
            # RoutineActionWaitInFear.OnActionStopped (cs:21-27)
            pawn.movement_paused = False
            routine.continue_alarm()
        if item is None:
            if resume:
                resume()
            return
        pawn.item_to_ignore_next_time = item       # the gate the re-entry sees
        self.play_angry(pawn, item, on_done=resume)
        pawn.item_to_ignore_next_time = None       # Rottweiler.cs:824

    def _on_trick_done(self, item):
        """Item.OnTrickDone (Item.cs:2121): score once, linked pairs pay both."""
        if self.game is None:
            return
        linked = self.level.items.get(item.linked_item_trick) \
            if item.linked_item_trick else None
        if linked is not None and linked.tricked and item.tricked:
            if item.already_tricked and not linked.already_tricked:
                linked.already_tricked = True
                self.game.linked_trick = False
                self.game.trick_done(item.trick_score)
            elif not item.already_tricked and linked.already_tricked:
                item.already_tricked = True
                self.game.linked_trick = False
                self.game.trick_done(item.trick_score)
            elif not item.already_tricked and not linked.already_tricked:
                item.already_tricked = True
                linked.already_tricked = True
                self.game.linked_trick = True
                self.game.trick_done(item.trick_score)
        elif not item.already_tricked:
            item.already_tricked = True
            self.game.trick_done(item.trick_score)

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
        item.tricked = False
        fx = self.level.items.get(item.fix_item_trick) \
            if item.fix_item_trick else None
        if fx is not None:
            fx.tricked = False
            self._return_to_idle(fx)
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
        self._return_to_idle(item)

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
        EnterZone / LeaveZone poses always return to idle, the use poses only
        with AnimateAfterUse. The WaterPuddle Valve arm rides the unported
        hover machinery."""
        if name is None:
            return
        if name in (item.enter_zone, item.leave_zone):
            self._return_to_idle(item)
        elif item.animate_after_use and \
                name in (item.use_normal, item.use_tricked_single):
            self._return_to_idle(item)

    def _return_to_idle(self, item):
        """TrickItem.ReturnToIdleAnimation, the reachable branches"""
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None or not item.animating:
            return
        if item.fucked_up:
            return
        tricked = item.is_tricked(self.level.items)
        if not tricked and item.primed and item.force_primed_on_start:
            return          # TrickItem.cs:705: hold the primed pose instead
        name = item.idle_tricked if tricked else item.idle
        if name and p.has(name):
            p.play_single(name)

    def pawn_by_pid(self, pid):
        """resolve a serialized Pawn-component reference to the live pawn"""
        for role, spec in self.level.pawns.items():
            if spec.get('pid') == pid:
                return self.pawns.get(role)
        return None

    def play_use_item_anim(self, item):
        """TrickItem.PlayUseAnimation (TrickItem.cs:982-994): the item's own
        normal-use pose — the single UseNormal, or the UseNormalSequence.
        The AnimateDependant echo is unused by the shipped use flows."""
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None:
            return
        if not item.play_use_normal_seq:
            self.play_item_anim(item, item.use_normal)
            return
        seq = [x for x in item.use_normal_sequence if p.has(x)]
        if seq:
            p.play_sequence(seq)

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

    def play_item_anim(self, item, name):
        """TrickItem.PlayItemAnimation (TrickItem.cs:1018-1050): a no-op
        unless Animating; NONE hides a HideWhenNotAnimating item; the type
        comes from UseAnimationType / Looping. The AnimateDependant arm is
        unused by the shipped behaviors."""
        if not item.animating:
            return
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if name:
            if item.hide_when_not_animating and item.sprite is not None:
                item.sprite.hidden = False
            if p is None or not p.has(name):
                return
            if item.use_anim_type:
                p.play_directly(name)
            elif item.looping_flag:
                p.play_looping(name)
            else:
                p.play_single(name)
        elif item.hide_when_not_animating and item.sprite is not None:
            item.sprite.hidden = True

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
        overlay's renderer, and the ground tricks' collider rides along —
        approximated by the item's own clickability, the port's only
        click surface."""
        if item.tricked_object_go is None:
            return
        self.set_go_renderer(item.tricked_object_go, not hidden)

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
        """Door.Unlock (Door.cs:198-207): the alternate idle takes over and
        the zone graph gains the link"""
        if not door.locked:
            return
        door.locked = False
        door.use_alternate_idle = True
        p = self.players.get(id(door.sprite)) if door.sprite else None
        if p is not None and door.alternate_idle and p.has(door.alternate_idle):
            p.play_looping(door.alternate_idle)
        self.level._build_graph()

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

    def icon_pressed(self, entry):
        """HUD.CheckClick consults the held item's OnIconPressed before
        selecting (HUD.cs:944); the phones raise the alarm instead
        (Item.OnIconPressed, Item.cs:2176-2199). True lets the selection
        happen."""
        src = self.level.items.get(entry.get('item')) \
            if entry.get('item') else None
        w = self.woody
        if src is None or w is None:
            return True
        if not w.is_warping:
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
            if not rt.pawn.is_warping and not rt.is_alarm_postponed():
                rt.start_urgent(alarm, alarm_use=True)
            else:
                rt.pending_alarm = alarm
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
        if w is None or w.zone is None or w.zone.pid != item.zone:
            return
        w.movement_paused = True
        fear = 'FearLeftShort' if item.x < w.sprite.x else 'FearRightShort'

        def restart_movement():
            w.steps = []
            w._step = None
            w.state = w.IDLE
            w.movement_paused = False
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
        if pawn.role != 'Rottweiler':
            return False
        for fsm in self.alerters.values():
            if fsm.item.zone == old_zone_pid:
                fsm.on_rottweiler_leave()
        routine = next((r for r in self.routines if r.pawn is pawn), None)
        if routine is not None:
            return routine.on_zone_changed()
        return False

    def zone_reaction(self, zone_pid, which):
        """Zone.PlayItemsZoneEnter / PlayItemsZoneLeave"""
        for it in self._zone_items.get(zone_pid, ()):
            if it.is_tricked(self.level.items):
                continue                  # PlayZoneEnter checks IsTricked
            anim = it.enter_zone if which == 'enter' else it.leave_zone
            if not anim or it.sprite is None or not it.animating:
                continue
            p = self.players.get(id(it.sprite))
            if p is not None and p.has(anim):
                p.play_single(anim)

    def player_for(self, sprite):
        return self.players.get(id(sprite))

    # -- Woody using items -------------------------------------------------
    def call_later(self, delay, fn):
        """MonoBehaviour.Invoke, as GameInfo.InvokeMethodForSetPrime uses it"""
        self._delayed.append([delay, fn])

    def set_primed(self, item, primed):
        """Item.SetPrimed (Item.cs:1169-1243) + the TrickItem override that
        plays the primed idle (TrickItem.cs:996-1010, 483-491). PrimedOffset
        is zero throughout the shipped data and the WaterPuddle name-hack is
        not ported."""
        if item.dont_prime_while_tricked and item.tricked:
            return
        item.primed = primed
        # the WaterPuddle negates its DeltaLocation outright and skips the
        # delta arms (Item.cs:1196-1210)
        if item.name == 'WaterPuddle':
            item.dx = -item.dx
            item.dy = -item.dy
        elif item.delta_primed_x or item.delta_primed_y:
            sign = 1.0 if primed else -1.0
            item.dx += sign * item.delta_primed_x
            item.dy += sign * item.delta_primed_y
        if item.sprite is not None:
            if item.show_only_when_primed:
                item.sprite.hidden = not primed      # Item.cs:1219-1231
            if item.hide_when_primed:
                item.sprite.hidden = primed          # Item.cs:1232-1235
        if primed and item.kind in TRICK_KINDS:
            p = self.players.get(id(item.sprite)) if item.sprite else None
            if p is None or not item.animating:
                return
            if item.fucked_up:
                name = item.primed_fucked_up
            elif item.is_tricked(self.level.items) and item.primed_tricked:
                name = item.primed_tricked
            else:
                name = item.primed_normal
            if name and p.has(name):
                p.play_single(name)

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

    def woody_use(self, item):
        """Click on an item: walk to it, then the Woody.TryUseItem chain."""
        if self.woody is None or self.game.ending:
            return False
        self.woody.start_move_flags()
        return self.woody.goto_item(item,
                                    on_arrive=lambda: self._woody_try_use(item))

    def _can_woody_use(self, item):
        """Item.CanWoodyUse, the always-live gates (Item.cs:1671-1704), plus
        TrickItem.CanWoodyUse's compound branch (TrickItem.cs:507-543)."""
        inv = self.inventory
        # SecondRequiredInventory acts as an accepted alternative (Item.cs:1736)
        required = item.required_inventory
        if item.second_required and item.second_required != 'IT_NONE' and \
                inv.used is not None and inv.used['type'] == item.second_required:
            item.second_required, required = required, item.second_required
            item.required_inventory = required
        if item.compound and inv.used is not None and \
                inv.used['type'] == item.compound_required and \
                (item.name != 'Rake' or item.tricked):
            # TrickItem.CanWoodyUse: the compound trick applies immediately;
            # the Rake accepts its compound only once tricked (TrickItem.cs:511)
            item.compound_tricked = True
            self.woody.anim.play_single(item.animation)
            inv.remove(item.compound_required)
            p = self.players.get(id(item.sprite)) if item.sprite else None
            anim = item.compound_double_anim if item.tricked else item.compound_tricked_anim
            if p is not None and anim and p.has(anim):
                p.play_single(anim)
            return None                    # handled; no ordinary use follows
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
        # Item.cs (CanWoodyUse head): the FirstAid + key name-hack — the only
        # way Level108's locked kit opens. FirstAidPos is not serialized in
        # either season's data, so the teleport half is unverifiable; skipped.
        if item.name == 'FirstAid' and inv.used is not None \
                and inv.used['type'] == 'IT_Key':
            item.locked = False
            self.woody_prime(item)
            return True
        held_src = self.level.items.get(inv.used.get('item')) \
            if inv.used is not None and inv.used.get('item') else None
        # a slept-in bed refuses Woody outright (TrickItem.CanWoodyUse,
        # TrickItem.cs:537-541)
        if item.kind in TRICK_KINDS and item.is_bed \
                and item.is_rottweiler_sleeping:
            self._woody_cant_use()
            return False
        # Item.cs:1510: holding anything at a plain (non-TrickItem) item that
        # needs no priming is a flat no
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
                        # the snake round of the L208 chain (Item.cs:1554-1560);
                        # the InventoryToAdd rat grant rides the unported
                        # InventoryToAdd machinery
                        self.snake_aux_208 = True
                        self.set_primed(item, True)
                        inv.used['type'] = 'IT2_Snake'
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
                self._woody_cant_use()
                return False
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

    def _woody_single_ended(self, name):
        """Woody.OnSingleAnimationEnded's ItemToShowAfterAnim restore
        (Woody.cs:381-385) plus the layer restore of
        OnBlockingAnimationEnded (Woody.cs:304-307)"""
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

    def _woody_try_use(self, item):
        """Woody.TryUseItem (Woody.cs:499-550): Item.Use -> WoodyUse gate ->
        the use teleports -> the item's animation on Woody; the state change
        happens when it ends."""
        item.wrong_trick = False           # Item.WoodyUse (Item.cs:1857)
        ok = self._can_woody_use(item)
        if ok is not True:
            return
        if item.hide_during_woody_use_anim:
            self._woody_use_anim_item = item   # Woody.itemAux (Woody.cs:216)
        # the use teleports (Woody.cs:520-533)
        if item.teleport_woody_on_use:
            self.woody.sprite.x, self.woody.sprite.y = item.x, item.y
        if item.set_woody_x_on_use:
            self.woody.sprite.x = item.x
        if item.woody_target_y:
            self.woody.sprite.y = item.woody_target_y
        # Item.PreUse for the end-of-animation users (Item.cs:2225-2235)
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
            # HideItem.InternalUse runs at once (ShouldUseAfterAnimationFinishes
            # is UseAfterAnimation, normally false), then Woody plays Hide_In
            self.woody.hide(item)
            if item.animation and self.woody.anim.has(item.animation):
                self.woody.anim.play_single(item.animation)
            return
        seq = list(item.animation_sequence) if item.use_woody_sequence \
            else ([item.animation] if item.animation else [])
        seq = [a for a in seq if self.woody.anim.has(a)]
        searching = item.kind == 'SearchItem'
        tricked_use = item.kind in ('TrickItem', 'GroundItem', 'HideItem',
                                    'InspectItem') or not searching

        def anim_ended():
            if searching:
                self._woody_search_step(item)
            else:
                self._woody_trick_done(item, item_used_inventory)
        if seq:
            # a bare Animation is a PlaySingleAnimation (Woody.cs:539-546)
            self.woody.anim.play_sequence(seq, on_end=anim_ended,
                                          as_sequence=item.use_woody_sequence)
        else:
            anim_ended()

    def _woody_trick_done(self, item, used_inventory):
        """TrickItem.OnUseAnimationCompleted (TrickItem.cs:268-380)."""
        if item.wrong_trick:
            return
        item.used = True                   # Item.UseItem
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
                act.tricked = True
                self._return_to_idle(act)
            tgt = self.level.items.get(item.set_tricked_on_item) \
                if item.set_tricked_on_item else None
            if tgt is not None:
                tgt.tricked = True
        # Item.InternalUse's own hide/show flags (Item.cs:1919-1938)
        if item.hide_after_use:
            self.set_object_hidden(item, True)
        elif item.show_after_use:
            self.set_object_hidden(item, False)
        if item.hide_during_woody_anim:
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
        # idle switch (the tail of OnUseAnimationCompleted)
        self._return_to_idle(item)
        # Woody laughs (Woody.OnSingleAnimationEnded, Woody.cs:418)
        if not item.dont_laugh and self.woody.anim.has('TrickLaugh'):
            self.woody.anim.play_single('TrickLaugh')
        # the use tail also runs the item's PhoneBehavior (Woody.cs:428)
        self._phone_behavior(item)

    def _get_tricked(self, item, tricked):
        """Item.GetTricked (Item.cs:1957)"""
        item.tricked = tricked
        if item.get_tricked_at_once:
            item.got_tricked = tricked

    def _woody_search_step(self, item):
        """Woody.OnSingleAnimationEnded, the SearchingItem branch
        (Woody.cs:386-411): a stocked item plays the take animation, an empty
        one gets WhatsUp."""
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
            self.woody.anim.play_single('WhatsUp')

    def _woody_search_done(self, item):
        """SearchItem.OnFinishAnimationCompelted -> UseItem -> InternalUse
        (SearchItem.cs:114, 156): hand over the inventory, empty the item.
        Each Inventory keeps its source (inventory.Item = this,
        SearchItem.cs:172) — the priming gates read it."""
        if self.search_behavior is not None:
            # Woody.OnSearchItemUsed runs between the source stamps and the
            # hand-over (SearchItem.cs:178, Woody.cs:985-991)
            self.search_behavior.on_search_item_used(item)
        self.inventory.add([dict(e, item=item.pid)
                            for e in item.inventory_items])
        # SearchItem.InternalUse's emptying (SearchItem.cs:192-206): a keeper
        # marks ItemRemoved instead, and TrickAfterWoodyUse arms the trick
        if not item.keep_full:
            if not item.dont_remove_inventory:
                item.inventory_items = []
            else:
                item.item_removed = True
        if item.trick_after_woody_use:
            self._get_tricked(item, True)
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is not None and item.empty_animation and p.has(item.empty_animation):
            p.play_single(item.empty_animation)

    def _kid_update(self, kid):
        """Kid.Update (Kid.cs:25-51): the crying and remote flags raised by
        ActionManager.KidActions and SandCastleBehavior resolve into plays;
        crying also breaks Olga's current infinite loop."""
        spec = self.level.pawns.get('Kid') or {}
        if kid.kid_start_crying:
            kid.kid_start_crying = False
            olga = self.pawns.get('Olga')
            if olga is not None:
                olga.anim.anim.infinite = False   # CurrentAnimation.InfiniteLoop
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
        if not spec or spec['zone'] is None:
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
        if role == 'Woody' and self.level.start_location is not None:
            # Woody.Start parks him at StartLocation in the StartZone with
            # input locked (Woody.cs:187-192); after the intro (immediate
            # here — the title cards are not modelled) the EntranceTimer
            # (0.5 s, Woody.cs:114) runs and he walks in
            p.sprite.x, p.sprite.y = self.level.start_location
            z = self.level.zone_by_pid(self.level.start_zone)
            if z is not None:
                p.zone = z
            p.input_locked = True
            self._entrance_timer = 0.5
        return p

    def spawn_woody(self, sprite, zone, spec=None):
        self.woody = Pawn(self.level, sprite, zone, spec,
                          player=self.players[id(sprite)], role='Woody')
        self.woody.world = self
        return self.woody

    def start_routines(self):
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
        """the zone/door/hiding/blocking chain both predicates share. The
        IsMovingToAdjacentZone terms are the TransitionMove flag; the
        PassingComplexMove terms are covered by is_warping here, since this
        port routes Transition passages through the same transit code.
        DonePassingToOtherZone rides the unported NFH2 GoZone pathing."""
        woody = self.woody
        return (woody.zone is not None and catcher.zone is not None
                and woody.zone.pid == catcher.zone.pid
                and not woody.is_warping and not catcher.is_warping
                and not woody.moving_to_adjacent_zone()
                and not catcher.moving_to_adjacent_zone()
                and not catcher.ignore_woody and not woody.hiding
                and (not catcher.anim.blocking or not woody.sneaking)
                and not woody.anim.blocking)

    def can_rottweiler_see_woody(self):
        """GameInfo.CanRottweilerSeeWoody (GameInfo.cs:181-192), the Classic
        detection predicate. Pure zone containment; the Bed special case swaps
        the sleep term for a movement term."""
        rott = self.pawns.get('Rottweiler')
        woody = self.woody
        if rott is None or woody is None:
            return False
        # both branches of the original require ActionManager.CurrentAction
        routine = next((r for r in self.routines if r.pawn is rott), None)
        if routine is None:
            return False
        if not self._detect_common(rott):
            return False
        # Rottweiler.CanSeeWoody defers to the primary behavior
        # (Rottweiler.cs:1218-1221)
        if rott.behaviors and not rott.behaviors[0].can_see_woody():
            return False
        it = routine.item if routine else None
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
        routine = next((r for r in self.routines if r.pawn is mother), None)
        if routine is None:
            return False
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
        self.game.got_caught = True
        self.game.won = False
        self.game.ending = True           # FinishGame: input locked
        catcher = catcher or self.pawns.get('Rottweiler')
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
        catcher.steps = []
        catcher.in_urgent = False         # HitWoodyAction.Urgent = false

        def hit():
            seqs = [q for q in catcher.hit_action.get('sequences', [])
                    if all(catcher.anim.has(a) for a in q)]
            woody.sprite.hidden = True    # the hit sheets contain Woody
            if seqs:
                catcher.anim.play_sequence(random.choice(seqs),
                                           on_end=self._finish_animation_ended)
            else:
                self._finish_animation_ended()
        if not catcher.goto_zone(woody.zone, woody.sprite.x, on_arrive=hit):
            hit()

    def _finish_animation_ended(self):
        """GameInfo.FinishAnimationEnded: everything freezes"""
        self.game.ended = True
        self._score()
        for r in self.routines:
            r.frozen = True

    def _score(self):
        rott = self.pawns.get('Rottweiler')
        self.game.calculate_score(
            rott.angry_count_ticks if rott is not None else 0,
            nfh2=self.woody.nfh2 if self.woody is not None else False)

    def _time_up(self):
        """GameInfo.Update's TimeUp -> FinishGameOnHUDClick: FinishGame plus
        the immediate freeze of everyone (GameInfo.cs:245-248, 373-381)"""
        self.game.won = False
        self.game.ending = True
        self.game.ended = True
        self._score()
        for r in self.routines:
            r.frozen = True

    def _win(self):
        """GameInfo.PlayWinAnimations: FinishGame, Woody's win animation,
        freeze the neighbour."""
        self.game.ending = True
        for r in self.routines:
            r.frozen = True
        w = self.woody
        if w is not None and w.win_animation and w.anim.has(w.win_animation):
            w.steps = []
            w.state = w.IDLE
            # Woody.PlayFinishAnimation is a PlaySingleAnimation (Woody.cs:1122)
            w.anim.play_sequence([w.win_animation],
                                 on_end=self._finish_animation_ended,
                                 as_sequence=False)
        else:
            self._finish_animation_ended()

    def tick(self, dt):
        self.time += dt                  # Time.time
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
            self._entrance_timer -= dt
            if self._entrance_timer <= 0.0:
                self._entrance_timer = None
                self.woody.start_move_flags()   # StartMoveToLocation(0)
                ex, ey = self.level.entrance_location or \
                    (self.woody.sprite.x, self.woody.sprite.y)
                if not self.woody.goto(ex, ey):
                    self.woody.input_locked = False
        elif self.woody is not None and self.woody.input_locked and \
                self.woody.state == self.woody.IDLE and not self.woody.steps:
            self.woody.input_locked = False     # OnFinishedEntrance
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
        for p in self.players.values():
            p.tick(dt)
        for p in self.pawns.values():
            if p is not self.woody:
                p.tick(dt)
        for r in self.routines:
            r.tick(dt)
        # the behaviors' MonoBehaviour.Update bodies (enabled components only)
        for b in self.behavior_objs:
            if b.enabled:
                b.update(dt)
        # SearchItem.Update's animation switcher (SearchItem.cs:214-244)
        for it in self.level.items.values():
            if it.kind == 'SearchItem' and it.sprite is not None:
                self._search_switch(it)
        # the Kid pawn's flag machine (Kid.cs:25-51)
        kid = self.pawns.get('Kid')
        if kid is not None:
            self._kid_update(kid)
        for fsm in self.alerters.values():
            fsm.tick(dt)
        if self.woody:
            self.woody.tick(dt)
        # GameInfo.Update, the Classic win/lose checks (GameInfo.cs:203-232)
        if self.game.ending or self.game.ended:
            return
        # the clock (GameInfo.Update 239-254): timed games count down and end
        # the game at zero, untimed ones count up
        if self.game.timed:
            if self.game.time_seconds > 0.0:
                self.game.time_seconds -= dt
                if int(self.game.time_seconds) <= 0:
                    self.game.time_up = True
                    self._time_up()
                    return
        else:
            self.game.time_seconds += dt
        if self.can_rottweiler_see_woody():
            if not self.game.got_caught:
                self._catch()
        elif self.can_mother_see_woody():
            # GameInfo.Update's second branch (GameInfo.cs:222-224)
            if not self.game.got_caught:
                self._catch(self.pawns.get('Mother'))
        elif self.game.all_done():
            # WinGameOnCompleteAllTricks waits 2.5 seconds before the win pose
            if self.game.win_timer is None:
                self.game.win_timer = 2.5
            else:
                self.game.win_timer -= dt
                if self.game.win_timer <= 0.0:
                    self._win()
