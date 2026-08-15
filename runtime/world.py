"""Gameplay simulation: animation sequencing, zone navigation, door transit.

Follows docs/GAMEPLAY.md §3 and §8. Movement inside a zone is one-dimensional
along x; zones are joined only by doors, and passing one is an animation on the
*door*, during which the pawn itself is hidden — the door sheets already contain
the walking character.
"""


class AnimPlayer:
    """Drives one animation controller: a current animation, an optional queued
    sequence, and a callback when the sequence drains.

    Mirrors AnimationControllerBase: each animation ending pulls the next, and
    the sequence finishing is what ends the owning action.
    """

    def __init__(self, sprite):
        self.sprite = sprite
        self.t = 0.0
        self.queue = []
        self.on_end = None
        self.by_name = {a.name: i for i, a in enumerate(sprite.anims)}

    @property
    def anim(self):
        return self.sprite.anims[self.sprite.current]

    def has(self, name):
        return name in self.by_name

    def play_single(self, name):
        """PlaySingleAnimation: the type becomes Single, so only InfiniteLoop
        can still make it loop."""
        i = self.by_name.get(name)
        if i is None:
            return False
        self.sprite.current = i
        self.t = 0.0
        self.sprite.anims[i].loop = self.sprite.anims[i].infinite
        return True

    def play(self, name, loop=None):
        i = self.by_name.get(name)
        if i is None:
            return False
        self.sprite.current = i
        self.t = 0.0
        if loop is not None:
            self.sprite.anims[i].loop = loop
        return True

    def waiting(self):
        """parked on an infinitely looping animation with nothing queued"""
        return self.anim.loop and not self.queue

    def play_looping(self, name, abort_if_playing=True):
        if abort_if_playing and self.anim.name == name:
            return True
        return self.play(name, loop=True)

    def play_sequence(self, names, on_end=None):
        """An animation flagged InfiniteLoop keeps looping even inside a
        sequence — Refresh() checks InfiniteLoop before the Single type. That is
        how the game parks a character in a waiting pose, and how it stalls a
        routine until something clears the flag."""
        names = [n for n in names if self.has(n)]
        if not names:
            if on_end:
                on_end()
            return False
        self.play_single(names[0])
        self.queue = names[1:]
        self.on_end = on_end
        return True

    def finished(self):
        a = self.anim
        if a.loop:
            return False
        n = len(a.pattern) if a.pattern else (a.end - a.start + 1)
        return n > 0 and self.t * a.fps >= n

    def tick(self, dt):
        self.t += dt
        if not self.finished():
            return
        if self.queue:
            self.play_single(self.queue.pop(0))
            return
        cb, self.on_end = self.on_end, None
        if cb:
            cb()


class Pawn:
    """Woody, or anyone else that walks the zone graph."""

    IDLE, WALK, DOOR_ENTER, DOOR_LEAVE = 'idle', 'walk', 'door_enter', 'door_leave'

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
        self.sneaking = False
        self.state = self.IDLE
        self.facing = 'Left'
        self.hidden = False
        self.steps = []                  # [(door | None, target_x)]
        self.target_x = sprite.x
        self._door = None
        self._exit_door = None
        self.on_arrive = None            # fired once the last step completes
        self.anim.play_looping('Stand_' + self.facing)

    # -- commands --------------------------------------------------------
    def goto(self, x, y, on_arrive=None):
        """Walk to a world point; the zone is the one containing it."""
        dest = self.level.zone_at(x, y)
        if dest is None:
            return False
        return self.goto_zone(dest, x, on_arrive, clamp=True)

    def goto_zone(self, dest, x, on_arrive=None, clamp=False):
        """Walk to x in a named zone, routing through doors.

        The zone is passed explicitly because that is what the game does —
        ActionManager calls MoveToGoal(item, item.Zone, item.TargetLocation).
        An item's stand-point can sit a little outside its zone's collider, so
        deriving the zone from the point would fail.
        """
        self.on_arrive = on_arrive
        if dest is None:
            return False
        steps = []
        if dest.pid != self.zone.pid:
            hops = self.level.find_path(self.zone.pid, dest.pid)
            if hops is None:
                return False
            for _, door in hops:
                steps.append((door, door.x))
        steps.append((None, min(max(x, dest.left), dest.right) if clamp else x))
        self.steps = steps
        self._next_step()
        return True

    # -- internals -------------------------------------------------------
    def _next_step(self):
        if not self.steps:
            self.state = self.IDLE
            self.anim.play_looping('Stand_' + self.facing)
            cb, self.on_arrive = self.on_arrive, None
            if cb:
                cb()
            return
        self._door, self.target_x = self.steps.pop(0)
        self.state = self.WALK

    def _face_towards(self, dx):
        self.facing = 'Right' if dx > 0 else 'Left'

    def walk_speed(self, horizontal=True):
        """ProcessMovement multiplies the velocity by Speed (or SpeedSneaking),
        and WalkOnPath sets that velocity to direction * ForceMagnitude for a
        mostly-horizontal move, or * DoorForceMagnitude otherwise."""
        base = self.speed_sneaking if self.sneaking else self.speed
        return base * (self.force if horizontal else self.door_force)

    def _door_anims(self, door):
        """Leave belongs to the departing side, Enter to the arriving side."""
        if self.role == 'Woody':
            return door.leave, door.enter
        return door.rott_leave, door.rott_enter

    def _enter_door(self, door):
        """Pawn.MoveToDoor, portal branch. Both doors animate at once:

            PlayDoorLeaveAnimation(TargetDoor);          // source side: Leave
            PlayDoorEnterAnimation(TargetDoor.LinkTo);   // far side: Enter

        PlayDoorLeaveAnimation calls SetHidden(true), so every pawn is hidden
        during transit, not just Woody. The teleport happens when the far
        door's Enter animation finishes (OnDoorEnterAnimationFinished), which
        also plays that door's ExitAnimation looping on the pawn."""
        other = self.level.door_by_pid(door.link_to)
        if other is None:
            self.state = self.IDLE
            return
        # Door.IsOtherPawnPassing on either side: stand and wait
        if (door.passing is not None and door.passing is not self) or \
                (other.passing is not None and other.passing is not self):
            self.anim.play_looping('Stand_' + self.facing)
            return                        # state stays WALK; retried next tick
        self.state = self.DOOR_ENTER
        self.hidden = True
        self._door = door
        self._exit_door = other
        door.passing = other.passing = self
        leave_anim, _ = self._door_anims(door)
        _, enter_anim = self._door_anims(other)
        if door.sprite is not None and leave_anim:
            door.sprite.play_sequence([leave_anim],
                                      on_end=lambda: self._leave_played(door))
        else:
            door.passing = None           # Door.PlayAnimation's null branch
        if other.sprite is not None and enter_anim:
            other.sprite.play_sequence([enter_anim], on_end=self._enter_played)
        else:
            self._enter_played()          # Door.PlayAnimation's null branch

    def _leave_played(self, door):
        """OnDoorLeaveAnimationFinished does nothing for a normal door;
        the door just frees itself (PassingPawn = null)."""
        door.passing = None

    def _enter_played(self):
        """Pawn.OnDoorEnterAnimationFinished: warp to the far door plus
        DoorDistanceDelta, change zone, unhide, loop its ExitAnimation."""
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
        self._next_step()

    # -- tick ------------------------------------------------------------
    def tick(self, dt):
        self.anim.tick(dt)
        if self.state == self.WALK:
            dx = self.target_x - self.sprite.x
            step = self.walk_speed() * dt
            if abs(dx) <= step:
                self.sprite.x = self.target_x
                if self._door is not None:
                    self._enter_door(self._door)
                else:
                    self._next_step()
                return
            self.sprite.x += step if dx > 0 else -step
            self._face_towards(dx)
            self.anim.play_looping('Walk_' + self.facing)


class Routine:
    """ActionManager: the neighbour walks a cyclic list of actions.

    Follows docs/GAMEPLAY.md §4. An action with Duration 0 ends when its
    animation sequence drains, which is the usual case — the sequence *is* the
    action.
    """

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
        self.on_use = None               # (item, tricked) when an action fires
        self.log = []
        self._pending = None             # 'advance' | 'start', handled in tick

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
        """AdvanceActionIndex: wrap to the configured restart point"""
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
            if zone is not None:
                self.state = self.MOVING
                if self.pawn.goto_zone(zone, a['move_x'], on_arrive=self._finish):
                    return
            self._pending = 'advance'
            self.state = self.IDLE
            return
        if it is None:
            self._pending = 'advance'
            self.state = self.IDLE
            return
        at_place = (abs(self.pawn.sprite.x - it.target_x) <= a['max_distance']
                    and self.pawn.zone is not None and self.pawn.zone.pid == it.zone)
        if at_place:
            self._use()
        else:
            self.state = self.MOVING
            zone = self.level.zone_by_pid(it.zone)
            if not self.pawn.goto_zone(zone, it.target_x, on_arrive=self._use):
                self._pending = 'advance'
                self.state = self.IDLE

    def _use(self):
        """RoutineActionUse.OnActionStarted -> Item.Use(owner)"""
        it = self.item
        if it is None:
            self._pending = 'advance'; self.state = self.IDLE; return
        a = self.action
        if a.get('mutex'):
            # MutexAction: park on a looping animation and wait to be released
            self.state = self.USING
            self.timer = 0.0
            if a.get('mutex_anim'):
                self.pawn.anim.play_looping(a['mutex_anim'])
            return
        if a.get('move_only') or it is None:
            self._pending = 'advance'
            self.state = self.IDLE
            return
        tricked = it.is_tricked()
        seq = it.sequence_for(self.role, tricked)
        if not seq:
            # Item.PlayAnimation would index an empty array here, so the game
            # never reaches this with a routine that is meant to run. Treat it
            # as "not this character's item" and move on.
            self._pending = 'advance'
            self.state = self.IDLE
            return
        self.state = self.USING
        self.timer = self.action['duration']
        self.log.append((it.name, tricked))
        if self.on_use:
            self.on_use(it, tricked)
        self.pawn.anim.play_sequence(list(seq), on_end=self._finish)

    def _finish(self):
        """An action ending never chains straight into the next one: the game
        advances in ActionManager.Update, so a zero-length action cannot spin
        the whole routine inside a single frame."""
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
    """Everything that ticks."""

    def __init__(self, level):
        self.level = level
        self.woody = None
        self.pawns = {}
        self.routines = []
        # exactly one player per sprite; a door's controller was resolved by
        # hierarchy in the scene (GetComponentInChildren), wrap it in a player
        self.players = {id(s): AnimPlayer(s) for s in level.sprites}
        for d in level.doors:
            if d.sprite is not None:
                d.sprite = self.players.get(id(d.sprite))

    def player_for(self, sprite):
        return self.players.get(id(sprite))

    def spawn_woody(self, sprite, zone, spec=None):
        self.woody = Pawn(self.level, sprite, zone, spec,
                          player=self.players[id(sprite)], role='Woody')
        return self.woody

    def spawn_pawn(self, role):
        spec = self.level.pawns.get(role)
        if not spec or spec['zone'] is None:
            return None
        p = Pawn(self.level, spec['sprite'],
                 self.level.zone_by_pid(spec['zone']), spec,
                 player=self.players[id(spec['sprite'])], role=role)
        self.pawns[role] = p
        return p

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
