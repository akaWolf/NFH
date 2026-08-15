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

    def play(self, name, loop=None):
        i = self.by_name.get(name)
        if i is None:
            return False
        self.sprite.current = i
        self.t = 0.0
        if loop is not None:
            self.sprite.anims[i].loop = loop
        return True

    def play_looping(self, name, abort_if_playing=True):
        if abort_if_playing and self.anim.name == name:
            return True
        return self.play(name, loop=True)

    def play_sequence(self, names, on_end=None):
        names = [n for n in names if self.has(n)]
        if not names:
            if on_end:
                on_end()
            return False
        self.play(names[0], loop=False)
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
            nxt = self.queue.pop(0)
            self.play(nxt, loop=False)
            return
        cb, self.on_end = self.on_end, None
        if cb:
            cb()


class Pawn:
    """Woody, or anyone else that walks the zone graph."""

    IDLE, WALK, DOOR_ENTER, DOOR_LEAVE = 'idle', 'walk', 'door_enter', 'door_leave'

    def __init__(self, level, sprite, zone, speed=1.25, player=None):
        self.level = level
        self.sprite = sprite
        self.anim = player or AnimPlayer(sprite)
        self.zone = zone
        self.speed = speed
        self.state = self.IDLE
        self.facing = 'Left'
        self.hidden = False
        self.steps = []                  # [(door | None, target_x)]
        self.target_x = sprite.x
        self._door = None
        self.anim.play_looping('Stand_' + self.facing)

    # -- commands --------------------------------------------------------
    def goto(self, x, y):
        """Walk to a world point, routing through doors when it is in another
        zone. Returns False when no route exists."""
        dest = self.level.zone_at(x, y)
        if dest is None:
            return False
        steps = []
        if dest.pid != self.zone.pid:
            hops = self.level.find_path(self.zone.pid, dest.pid)
            if hops is None:
                return False
            for _, door in hops:
                steps.append((door, door.x))
        steps.append((None, min(max(x, dest.left), dest.right)))
        self.steps = steps
        self._next_step()
        return True

    # -- internals -------------------------------------------------------
    def _next_step(self):
        if not self.steps:
            self.state = self.IDLE
            self.anim.play_looping('Stand_' + self.facing)
            return
        self._door, self.target_x = self.steps.pop(0)
        self.state = self.WALK

    def _face_towards(self, dx):
        self.facing = 'Right' if dx > 0 else 'Left'

    def _enter_door(self, door):
        self.state = self.DOOR_ENTER
        self.hidden = True
        self._door = door
        player = door.sprite
        if player is None or not door.enter:
            self._leave_door(door)
            return
        player.play_sequence([door.enter], on_end=lambda: self._leave_door(door))

    def _leave_door(self, door):
        other = self.level.door_by_pid(door.link_to)
        if other is None:
            self.hidden = False
            self.state = self.IDLE
            return
        self.sprite.x, self.sprite.y = other.x, other.y
        self.zone = self.level.zone_by_pid(other.zone) or self.zone
        self.state = self.DOOR_LEAVE
        player = other.sprite
        if player is None or not other.leave:
            self._done_door()
            return
        player.play_sequence([other.leave], on_end=self._done_door)

    def _done_door(self):
        self.hidden = False
        self._next_step()

    # -- tick ------------------------------------------------------------
    def tick(self, dt):
        self.anim.tick(dt)
        if self.state == self.WALK:
            dx = self.target_x - self.sprite.x
            step = self.speed * dt
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


class World:
    """Everything that ticks."""

    def __init__(self, level):
        self.level = level
        self.woody = None
        # exactly one player per sprite; doors point at the player of the
        # sprite sitting on them, since a transit animates the door
        self.players = {id(s): AnimPlayer(s) for s in level.sprites}
        for d in level.doors:
            s = self._sprite_at(d.x, d.y)
            d.sprite = self.players.get(id(s)) if s else None

    def _sprite_at(self, x, y, tol=0.02):
        best, bd = None, tol
        for s in self.level.sprites:
            dist = abs(s.x - x) + abs(s.y - y)
            if dist < bd:
                best, bd = s, dist
        return best

    def player_for(self, sprite):
        return self.players.get(id(sprite))

    def spawn_woody(self, sprite, zone, speed=1.25):
        self.woody = Pawn(self.level, sprite, zone, speed,
                          player=self.players[id(sprite)])
        return self.woody

    def tick(self, dt):
        for p in self.players.values():
            p.tick(dt)
        if self.woody:
            self.woody.tick(dt)
