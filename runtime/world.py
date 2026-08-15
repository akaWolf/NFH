"""Gameplay simulation, following the decompiled source method by method.

The references in comments are to src/Assembly-CSharp: AnimationControllerBase
(frame stepping), AnimationInstance (frame model), Pawn (movement, doors),
Item (use range), ActionManager / RoutineAction* (the routine), Door, Zone.
"""


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
        self.queue = []
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
        return True

    def play_single(self, name):
        """PlaySingleAnimation: type forced to Single"""
        return self._set(name, 'single')

    def play_looping(self, name, abort_if_playing=True):
        if abort_if_playing and self.anim.name == name and self.mode == 'looping':
            return True
        self.queue = []
        self.on_end = None
        return self._set(name, 'looping')

    def play_sequence(self, names, on_end=None):
        """PlayAnimationSequence: each element via PlaySingleAnimation; the
        sequence draining is what ends the owning action."""
        names = list(names)
        if not names:
            if on_end:
                on_end()
            return False
        self.queue = names[1:]
        self.on_end = on_end
        self.play_single(names[0])
        return True

    @property
    def blocking(self):
        """AnimationControllerBase.IsPlayingBlockingAnimation"""
        return self.anim.blocking

    def waiting(self):
        """diagnostic only: parked on something that cannot finish"""
        return (self.anim.infinite or self.mode == 'looping') and not self.queue

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
        callback, else SwitchToStandAnimation (a no-op on item controllers,
        the facing-matched stand on pawns)."""
        if self.queue:
            self.play_single(self.queue.pop(0))
            return
        cb, self.on_end = self.on_end, None
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
        self.is_sleeping = spec.get('is_sleeping') or False
        self.ignore_woody = spec.get('ignore_woody') or False
        self.fear_left = spec.get('fear_left') or 'FearLeft'
        self.fear_right = spec.get('fear_right') or 'FearRight'
        self.win_animation = spec.get('win_animation')
        self.run_force = spec.get('run_force') or 0.0
        self.run_door_force = spec.get('run_door_force') or 0.0
        self.hit_action = spec.get('hit_action') or {}
        self.stand = spec.get('stand') or {}
        self.default_anim = spec.get('default')
        self.state = self.IDLE
        self.facing = 'Left'
        self.hidden = False
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

    # -- geometry ----------------------------------------------------------
    def floor_y(self, zone=None):
        """Helpers.GetDefaultZoneY: zone y + HeightDelta + PlayerHeightDelta"""
        z = zone or self.zone
        return z.ty + z.height_delta + self.height_delta

    def at_zone_y(self):
        """Pawn.IsPawnAtZoneY"""
        return abs(self.sprite.y - self.floor_y()) < 0.1

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
            if self.portal_up and self.anim.has(self.portal_up):
                self.anim.play_looping(self.portal_up)
            return
        self._transit_animations(door, other, sequential=False)

    def _transit_animations(self, door, other, sequential):
        self.state = self.DOOR_ANIM
        self.hidden = True                # PlayDoorLeaveAnimation: SetHidden(true)
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
                if self.world:
                    self.world.zone_reaction(other.zone, 'enter')
                self._play_enter(other, enter_anim)
            if door.sprite is not None and leave_anim:
                door.sprite.play_sequence([leave_anim], on_end=leave_done)
            else:
                leave_done()              # Door.PlayAnimation's null branch
        else:
            if door.sprite is not None and leave_anim:
                door.sprite.play_sequence(
                    [leave_anim], on_end=lambda: self._leave_played(door))
            else:
                door.passing = None
            self._play_enter(other, enter_anim)

    def _play_enter(self, other, enter_anim):
        if other.sprite is not None and enter_anim:
            other.sprite.play_sequence([enter_anim], on_end=self._enter_played)
        else:
            self._enter_played()

    def _leave_played(self, door):
        door.passing = None

    def _enter_played(self):
        """OnDoorEnterAnimationFinished: warp, unhide, loop ExitAnimation;
        a walk-up far door means climbing back down to the floor."""
        d = self._exit_door
        if d is None:
            return
        d.passing = None
        old_zone = self.zone.pid if self.zone else None
        self.sprite.x = d.x + self.door_delta[0]
        self.sprite.y = d.y + self.door_delta[1]
        self.zone = self.level.zone_by_pid(d.zone) or self.zone
        # Rottweiler.OnDoorEnterAnimationFinished: a flat-door exit snaps the
        # neighbour back onto the floor line (Rottweiler.cs:168-172)
        if self.role == 'Rottweiler' and not d.should_walk_up:
            self.sprite.y = self.floor_y()
        self.hidden = False
        self.is_warping = False           # OnDoorEnterAnimationFinished
        if self.world is not None and old_zone != (self.zone.pid if self.zone else None):
            if self.world.on_pawn_zone_changed(self, old_zone):
                return                    # OnChangeZone returned true: taken over
        if d.exit_anim and self.anim.has(d.exit_anim):
            self.anim.play_looping(d.exit_anim)
        if d.should_walk_up and self.steps:
            self.state = self.DESCEND
            if self.portal_down and self.anim.has(self.portal_down):
                self.anim.play_looping(self.portal_down)
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
                    up = self.portal_down if it.should_walk_down else self.portal_up
                    if up and self.anim.has(up):
                        self.anim.play_looping(up)
                else:
                    self._next_step()
                return
            nx, ny = dx / mag, dy / mag
            # WalkOnPath: dominant axis picks the force and the animation, and
            # IsInUrgentMove switches to the Running magnitudes
            if abs(nx) >= abs(ny):
                f = self.run_force if self.in_urgent else self.force
                vx, vy = nx * f, ny * f
                self._face_towards(nx)
                self.anim.play_looping('Walk_' + self.facing)
            else:
                f = self.run_door_force if self.in_urgent else self.door_force
                vx, vy = nx * f, ny * f
                self.anim.play_looping('Walk_Up' if ny > 0 else 'Walk_Down')
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

    def trick_done(self, score):
        """GameInfo.TrickDone (GameInfo.cs:467)"""
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
            self._pending = 'start'

    def _advance(self):
        self.index += 1
        if self.index >= len(self.actions):
            if self.loop_from_start:
                self.index = self.start_index
            elif self.selected_index:
                self.index = self.selected_index
            else:
                self.index = 0

    def _start_action(self):
        it = self.item
        a = self.action
        if a is not None and a.get('move_only'):
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
        # RoutineActionUse.OnActionStarted releases the named infinite loops
        # right at action start, before any movement (RoutineActionUse.cs:152-171)
        self._infinite_flags_on_start(a, it)
        if self.pawn.at_use_range(it):
            self._use()
        else:
            self.state = self.MOVING
            if not self.pawn.goto_item(it, on_arrive=self._use):
                # port-side failure path (the original's pathing cannot fail
                # on shipped data): keep the flags symmetric
                self._action_stopped()
                self._pending = 'advance'
                self.state = self.IDLE

    def _use(self):
        it = self.item
        a = self.action
        if it is None:
            self._pending = 'advance'; self.state = self.IDLE; return
        if a.get('mutex'):
            # MutexAction parks on its looping animation until another action's
            # PawnToAbortMutexOnFinish releases it (RoutineActionUse.cs:172-179)
            self.state = self.USING
            self.timer = 0.0
            if a.get('hide_owner'):
                self.pawn.hidden = True   # HideOwnerDuringUse, cs:174-177
            if a.get('mutex_anim'):
                self.pawn.anim.play_looping(a['mutex_anim'])
            return
        tricked = it.is_tricked(self.level.items)
        seq = it.sequence_for(self.role, tricked)
        if not seq:
            # port-side: shipped use actions always carry a sequence
            self._action_stopped()
            self._pending = 'advance'
            self.state = self.IDLE
            return
        self.state = self.USING
        self.timer = a['duration']
        if a.get('hide_owner'):
            self.pawn.hidden = True       # HideOwnerDuringUse, cs:213-216
        self.log.append((it.name, tricked))
        if tricked and self.role == 'Rottweiler':
            it.got_tricked = True          # Item.RottweilerUse (Item.cs:838)
        if self.on_use:
            self.on_use(it, tricked)
        self.pawn.anim.play_sequence(list(seq), on_end=self._finish)

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

    def _finish(self):
        """RoutineActionUse.StopAction(canPostponeStop: true): a tricked
        TrickItem does not finish the action — the owner plays the angry
        sequence first (RoutineActionUse.cs:546-553)."""
        it = self.item
        if (self.role == 'Rottweiler' and it is not None
                and it.kind == 'TrickItem' and it.is_tricked(self.level.items)
                and self.pawn.world is not None):
            target = self._tricked_item(it)
            if target is not None:
                self.pawn.world.play_angry(self.pawn, target,
                                           on_done=self._angry_done)
                return
        self._action_stopped()
        self._pending = 'advance'

    def _angry_done(self):
        """the second StopAction arrives with canPostponeStop=false, so the
        angry branch is skipped and the action finally finishes"""
        self._action_stopped()
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
            self.pawn.hidden = False
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
                rt.pawn.hidden = False
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

    def start_urgent(self, item):
        """Rottweiler.StartSurpriseActionFar -> ActionManager.StartUrgentAction:
        drop the move in progress and run (SurpriseActionFar.Urgent) to the
        item; the interrupted action stays current for the resume."""
        self.urgent_item = item
        self.pawn.steps = []
        self.pawn.in_urgent = True
        self.state = self.MOVING
        if self.pawn.at_use_range(item):
            self._urgent_arrived()
        elif not self.pawn.goto_item(item, on_arrive=self._urgent_arrived):
            self._urgent_finished()

    def _urgent_arrived(self):
        """RoutineActionSurpriseFar.OnActionStarted"""
        it = self.urgent_item
        if it is None:
            return
        if it.is_tricked(self.level.items):
            it.got_tricked = True          # Item.RottweilerUse via PlayAngry path
            self.pawn.world.play_angry(self.pawn, it,
                                       on_done=self._urgent_finished)
        elif it.kind == 'Alerter' or it.rott_surprise:
            seq = [a for a in it.rott_surprise if self.pawn.anim.has(a)]
            self.state = self.USING
            if seq:
                self.pawn.anim.play_sequence(seq, on_end=self._urgent_finished)
            else:
                self._urgent_finished()
        else:
            self._urgent_finished()

    def _urgent_finished(self):
        """ActionManager.StopUrgentAction (ActionManager.cs:586-649): a routine
        item that has already fired is skipped, otherwise the interrupted
        action restarts."""
        self.urgent_item = None
        self.pawn.in_urgent = False
        self.pawn.can_decrease_angry = True
        it = self.item
        if it is not None and it.got_tricked and \
                it.name not in ('WateringCan', 'ValveHot', 'ValveMain'):
            self._pending = 'advance'
        else:
            self._pending = 'start'
        self.state = self.IDLE

    def hear_alerter(self, alerter_item, triggered_by_woody):
        """Rottweiler.HearAlerter (Rottweiler.cs:265)"""
        if self.moving_to_alarm():
            return
        if not self.pawn.is_warping and not self.is_alarm_postponed():
            if self.state == self.MOVING:
                self.start_urgent(alerter_item)
            elif self.state == self.USING and \
                    (self.item is None or self.item.name != 'Bed'):
                self.was_alerted = alerter_item     # consumed when he moves
        else:
            self.pending_alarm = alerter_item       # PostponeAlerterAction

    def on_zone_changed(self):
        """Rottweiler.OnChangeZone: tricked noticing items, pending alarms,
        and calming the alerter he was called by. Returns True when it took
        over the pawn — OnChangeZone's own return value."""
        w = self.pawn.world
        for it in w.notice_items.get(self.pawn.zone.pid, ()):
            if it.tricked:
                # RunToTrickedItem: PauseMovement + a startled look, then the
                # urgent run (consumed in OnSingleAnimationEnded)
                self.pawn.steps = []
                self.pawn.state = self.pawn.IDLE
                startle = it.surprise_far_left if self.pawn.facing == 'Right' \
                    else it.surprise_far_right
                if startle and self.pawn.anim.has(startle):
                    self.pawn.anim.play_sequence(
                        [startle], on_end=lambda i=it: self.start_urgent(i))
                else:
                    self.start_urgent(it)
                return True
        if self.pending_alarm is not None and not self.is_alarm_postponed():
            it, self.pending_alarm = self.pending_alarm, None
            self.start_urgent(it)
            return True
        if self.moving_to_alarm() and self.urgent_item.zone == self.pawn.zone.pid:
            fsm = w.alerters.get(self.urgent_item.pid)
            if fsm is not None:
                fsm.on_rottweiler_enter()
        return False

    def tick(self, dt):
        if self.frozen:
            return
        # Rottweiler.Update: a deferred alert fires once he moves again
        if self.was_alerted is not None and self.state == self.MOVING:
            it, self.was_alerted = self.was_alerted, None
            self.start_urgent(it)
            return
        if self._pending:
            what, self._pending = self._pending, None
            if what == 'advance':
                self._advance()
            self._start_action()
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

    def play_angry(self, pawn, item, on_done=None):
        """Rottweiler.PlayAngryAnimation, GameMode.Classic branch
        (Rottweiler.cs:595-612, 768-787), followed on sequence end by
        FixTrickedItem -> TryFix (Rottweiler.cs:461, TrickItem.cs:1115)."""
        seq = []
        if self.game is not None:
            if pawn.angry_meter <= 0.0:
                if item.angry_easy_up:
                    seq = [item.angry_easy_up]
                # HUD anger level 1, medium laugh — presentation only
            else:
                pawn.angry_count_ticks += 1
                seq = [a for a in (item.angry_easy_down, item.angry_hard) if a]
                self.game.compound_tricks += 1     # Item.OnCompoundTrickDone
            pawn.angry_meter = pawn.angry_max
        # the fix animation rides at the tail of the same sequence
        if item.can_fix:
            if item.use_fix_sequence:
                seq.extend(item.fix_sequence)
            elif not item.fix_without_animations and item.fix_animation:
                seq.append(item.fix_animation)
        if not item.dont_get_angry:
            self._on_trick_done(item)              # Rottweiler.cs:787
        pawn.can_decrease_angry = False            # Rottweiler.cs:795

        def done():
            self._try_fix(item)                    # FixTrickedItem on seq end
            pawn.can_decrease_angry = True         # Rottweiler.OnUseEnded
            if on_done:
                on_done()

        seq = [a for a in seq if pawn.anim.has(a)]
        if seq:
            pawn.anim.play_sequence(seq, on_end=done)
        else:
            done()

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

    def _try_fix(self, item):
        """TrickItem.TryFix (TrickItem.cs:1115): fix, or run to the fixing
        item (not modelled), or break for good."""
        if item.can_fix:
            self._fix(item)
        elif item.fix_item_trick is None:
            item.fucked_up = True

    def _fix(self, item):
        """Item.Fix / TrickItem.Fix, the state core: the trick is disarmed and
        the item shows its normal idle again (Item.cs:2102, TrickItem.cs:443)."""
        item.tricked = False
        fx = self.level.items.get(item.fix_item_trick) \
            if item.fix_item_trick else None
        if fx is not None:
            fx.tricked = False
            self._return_to_idle(fx)
        self._return_to_idle(item)

    def _return_to_idle(self, item):
        """TrickItem.ReturnToIdleAnimation, the reachable branches"""
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is None or not item.animating:
            return
        if item.fucked_up:
            return
        name = item.idle_tricked if item.is_tricked(self.level.items) else item.idle
        if name and p.has(name):
            p.play_single(name)

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
            w.anim.play_sequence([fear], on_end=restart_movement)
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
                inv.used['type'] == item.compound_required:
            # TrickItem.CanWoodyUse: the compound trick applies immediately
            item.compound_tricked = True
            self.woody.anim.play_single(item.animation)
            inv.remove(item.compound_required)
            p = self.players.get(id(item.sprite)) if item.sprite else None
            anim = item.compound_double_anim if item.tricked else item.compound_tricked_anim
            if p is not None and anim and p.has(anim):
                p.play_single(anim)
            return None                    # handled; no ordinary use follows
        if required and required != 'IT_NONE':
            if (not inv.is_using(required)) and not item.grab_directly:
                if inv.used is not None:
                    self._woody_cant_use()
                    item.wrong_trick = True
                return False
        elif inv.used is not None:
            self._woody_cant_use()         # holding something at a bare item
            return False
        if item.locked:
            self._woody_cant_use()
            return False
        return True

    def _woody_cant_use(self):
        """Woody.PlayCantUseAnimation"""
        if self.woody.anim.has('NoNo'):
            self.woody.anim.play_single('NoNo')

    def _woody_try_use(self, item):
        """Woody.TryUseItem: Item.Use -> WoodyUse gate -> play the item's
        animation on Woody; the state change happens when it ends."""
        item.wrong_trick = False           # Item.WoodyUse (Item.cs:1857)
        ok = self._can_woody_use(item)
        if ok is not True:
            return
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
            self.woody.anim.play_sequence(seq, on_end=anim_ended)
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
        if item.can_undo_trick and item.tricked:
            self._get_tricked(item, False)
        else:
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
        # idle switch (the tail of OnUseAnimationCompleted)
        self._return_to_idle(item)
        # Woody laughs (Woody.OnSingleAnimationEnded, Woody.cs:418)
        if not item.dont_laugh and self.woody.anim.has('TrickLaugh'):
            self.woody.anim.play_single('TrickLaugh')

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
                    take, on_end=lambda: self._woody_search_done(item))
            else:
                self._woody_search_done(item)
        elif self.woody.anim.has('WhatsUp'):
            self.woody.anim.play_single('WhatsUp')

    def _woody_search_done(self, item):
        """SearchItem.OnFinishAnimationCompelted -> UseItem -> InternalUse
        (SearchItem.cs:114, 156): hand over the inventory, empty the item."""
        self.inventory.add(item.inventory_items)
        if not item.dont_remove_inventory:
            item.inventory_items = []
        p = self.players.get(id(item.sprite)) if item.sprite else None
        if p is not None and item.empty_animation and p.has(item.empty_animation):
            p.play_single(item.empty_animation)

    def spawn_pawn(self, role):
        spec = self.level.pawns.get(role)
        if not spec or spec['zone'] is None:
            return None
        p = Pawn(self.level, spec['sprite'],
                 self.level.zone_by_pid(spec['zone']), spec,
                 player=self.players[id(spec['sprite'])], role=role)
        p.world = self
        self.pawns[role] = p
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
        return self.routines

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
        common = (woody.zone is not None and rott.zone is not None
                  and woody.zone.pid == rott.zone.pid
                  and not woody.is_warping and not rott.is_warping
                  and not rott.ignore_woody and not woody.hiding
                  and (not rott.anim.blocking or not woody.sneaking)
                  and not woody.anim.blocking)
        if not common:
            return False
        it = routine.item if routine else None
        if it is not None and it.name == 'Bed':
            moving = woody.state in (woody.WALK, woody.DOOR_CLIMB,
                                     woody.DESCEND, woody.ITEM_CLIMB)
            return moving                 # the Bed case demands Velocity > 0
        return not rott.is_sleeping

    def _catch(self):
        """GameInfo.OnNeighborCaughtWoody + FinishGame + Rottweiler.HitWoody +
        RoutineActionHitWoody.OnActionStarted."""
        import random
        self.game.got_caught = True
        self.game.won = False
        self.game.ending = True           # FinishGame: input locked
        rott = self.pawns.get('Rottweiler')
        woody = self.woody
        # Woody.PlayFearAnimation(Rottweiler): face the neighbour
        fear = woody.fear_left if rott.sprite.x < woody.sprite.x else woody.fear_right
        if woody.anim.has(fear):
            woody.anim.play_single(fear)
        woody.steps = []
        woody.state = woody.IDLE
        # Rottweiler.HitWoody: stop the routine, walk to Woody, then the hit
        for r in self.routines:
            if r.pawn is rott:
                r.frozen = True           # ActionManager.Freeze in the action
        rott.steps = []
        rott.in_urgent = False            # HitWoodyAction.Urgent = false

        def hit():
            seqs = [q for q in rott.hit_action.get('sequences', [])
                    if all(rott.anim.has(a) for a in q)]
            woody.sprite.hidden = True    # the hit sheets contain Woody
            if seqs:
                rott.anim.play_sequence(random.choice(seqs),
                                        on_end=self._finish_animation_ended)
            else:
                self._finish_animation_ended()
        if not rott.goto_zone(woody.zone, woody.sprite.x, on_arrive=hit):
            hit()

    def _finish_animation_ended(self):
        """GameInfo.FinishAnimationEnded: everything freezes"""
        self.game.ended = True
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
            w.anim.play_sequence([w.win_animation],
                                 on_end=self._finish_animation_ended)
        else:
            self._finish_animation_ended()

    def tick(self, dt):
        for p in self.players.values():
            p.tick(dt)
        for p in self.pawns.values():
            if p is not self.woody:
                p.tick(dt)
        for r in self.routines:
            r.tick(dt)
        for fsm in self.alerters.values():
            fsm.tick(dt)
        if self.woody:
            self.woody.tick(dt)
        # GameInfo.Update, the Classic win/lose checks (GameInfo.cs:203-232)
        if self.game.ending or self.game.ended:
            return
        if self.can_rottweiler_see_woody():
            if not self.game.got_caught:
                self._catch()
        elif self.game.all_done():
            # WinGameOnCompleteAllTricks waits 2.5 seconds before the win pose
            if self.game.win_timer is None:
                self.game.win_timer = 2.5
            else:
                self.game.win_timer -= dt
                if self.game.win_timer <= 0.0:
                    self._win()
