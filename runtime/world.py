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
        """StopSingleAnimation: pull the next sequence element, else finish."""
        if self.queue:
            self.play_single(self.queue.pop(0))
            return
        cb, self.on_end = self.on_end, None
        if cb:
            cb()

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
        self.sneaking = False
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
        self.sprite.x = d.x + self.door_delta[0]
        self.sprite.y = d.y + self.door_delta[1]
        self.zone = self.level.zone_by_pid(d.zone) or self.zone
        self.hidden = False
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
            # WalkOnPath: dominant axis picks the force and the animation
            if abs(nx) >= abs(ny):
                vx, vy = nx * self.force, ny * self.force
                self._face_towards(nx)
                self.anim.play_looping('Walk_' + self.facing)
            else:
                vx, vy = nx * self.door_force, ny * self.door_force
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
        if self.pawn.at_use_range(it):
            self._use()
        else:
            self.state = self.MOVING
            if not self.pawn.goto_item(it, on_arrive=self._use):
                self._pending = 'advance'
                self.state = self.IDLE

    def _use(self):
        it = self.item
        a = self.action
        if it is None:
            self._pending = 'advance'; self.state = self.IDLE; return
        if a.get('mutex'):
            # MutexAction parks on its looping animation until another action's
            # PawnToAbortMutexOnFinish releases it
            self.state = self.USING
            self.timer = 0.0
            if a.get('mutex_anim'):
                self.pawn.anim.play_looping(a['mutex_anim'])
            return
        tricked = it.is_tricked()
        seq = it.sequence_for(self.role, tricked)
        if not seq:
            self._pending = 'advance'
            self.state = self.IDLE
            return
        self.state = self.USING
        self.timer = a['duration']
        self.log.append((it.name, tricked))
        if self.on_use:
            self.on_use(it, tricked)
        self.pawn.anim.play_sequence(list(seq), on_end=self._finish)

    def _finish(self):
        self._pending = 'advance'

    def tick(self, dt):
        if self.frozen:
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

    def zone_reaction(self, zone_pid, which):
        """Zone.PlayItemsZoneEnter / PlayItemsZoneLeave"""
        for it in self._zone_items.get(zone_pid, ()):
            if it.is_tricked():
                continue                  # PlayZoneEnter checks IsTricked
            anim = it.enter_zone if which == 'enter' else it.leave_zone
            if not anim or it.sprite is None or not it.animating:
                continue
            p = self.players.get(id(it.sprite))
            if p is not None and p.has(anim):
                p.play_single(anim)

    def player_for(self, sprite):
        return self.players.get(id(sprite))

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

    def tick(self, dt):
        for p in self.players.values():
            p.tick(dt)
        for p in self.pawns.values():
            if p is not self.woody:
                p.tick(dt)
        for r in self.routines:
            r.tick(dt)
        if self.woody:
            self.woody.tick(dt)
