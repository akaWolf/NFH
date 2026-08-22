"""Frame invariants over the real viewer loop — the bug-hunting layer.

Every existing suite drives Recorder.tick (the player's 60 Hz loop);
this checker rides that tick and flags states the original code cannot
produce. Each check is a contract lifted from the decompile plus a bug
class the port has actually shipped once:

- dead clicks:    a collider on an inactive GameObject catches no
  raycast in Unity, so an Item whose quad is SetActive(false) cannot be
  clickable (World.set_active keeps the pair in step; the Level101
  binoculars shipped the converse split — a view not following the
  model — and this watches the same seam from the observable side).
  No level ships such a pair (verified across all 37 scenes), so any
  hit is a runtime desync.
- teleports:      Pawn.ProcessMovement (Pawn.cs:871-879) integrates
  position += Velocity * dt * Speed; the discontinuities the original
  DOES make are enumerated and marked in the port — door transits set
  IsWarping (Pawn.cs:1174/1284), and the snap writers (MoveToItem's
  crossing snap Pawn.cs:1032-1035, the use teleports Woody.cs:520-533 /
  RoutineActionUse.cs:205-208 / Olga.cs:146-152, the stand shifts, the
  restart, the behavior warps) raise Pawn.pos_snap for their frame. A
  jump with neither flag is a move the original cannot make (the
  Intro103 "teleport to the door" report).
- lost sheets:    Resources.Load-ed animation textures resolve at export
  time (SheetTexture); a sheet the draw cache cannot find means an
  animation silently not drawn (the s2 SheetTexture=null regression).

(zone containment was tried and dropped: the original changes zones on
the path's TransferToZone step — Pawn.cs:1054-1057, 1526-1534 — not on
box crossings, so a pawn standing in another zone's box is normal.)

Violations are collected (deduped per subject), not raised: a run
reports them at the end, so one bad frame cannot mask another.
"""


def _pawn_vmax(p):
    """the largest per-frame speed ProcessMovement can integrate
    (Pawn.cs:871-879): the biggest force on either axis times the
    biggest speed multiplier"""
    force = max(p.force, p.run_force, p.door_force, p.run_door_force)
    speed = max(p.speed, getattr(p, 'speed_sneaking', 0.0) or 0.0)
    return force * speed


class Invariants:
    # per-frame distance allowance: 2x the fastest legal step, so frame
    # jitter (a step landing exactly on a waypoint) never false-flags
    CONTINUITY_SLACK = 2.0
    def __init__(self, viewer):
        self.v = viewer
        self.violations = []
        self._seen = set()
        self._prev = {}          # id(pawn) -> (x, y, warping, caught)

    # -- plumbing -----------------------------------------------------------
    def _flag(self, t, kind, subject, detail):
        key = (kind, subject)
        if key in self._seen:
            return
        self._seen.add(key)
        self.violations.append({'t': round(t, 2), 'kind': kind,
                                'subject': subject, 'detail': detail})

    def _pawns(self):
        w = self.v.world
        out = []
        if self.v.woody is not None:
            out.append(('Woody', self.v.woody))
        for r in w.routines:
            out.append((r.role, r.pawn))
        return out

    # -- checks -------------------------------------------------------------
    def _check_dead_click(self, t):
        lv = self.v.level
        for it in lv.items.values():
            if it.go is None or it.collider is None:
                continue
            q = lv.quads_by_go.get(it.go)
            if q is not None and not q.get('active') and it.clickable:
                self._flag(t, 'dead-click', it.name,
                           'clickable on an inactive object (a Unity '
                           'collider dies with its GameObject; '
                           'World.set_active keeps the pair in step)')

    def _check_continuity(self, t, dt):
        caught = self.v.world.game.got_caught
        for role, p in self._pawns():
            key = id(p)
            prev = self._prev.get(key)
            cur = (p.sprite.x, p.sprite.y, p.is_warping, caught)
            self._prev[key] = cur
            snapped = getattr(p, 'pos_snap', False)
            p.pos_snap = False           # one frame of grace per snap
            if prev is None:
                continue
            px, py, pwarp, pcaught = prev
            if p.is_warping or pwarp or caught or pcaught or p.hidden \
                    or snapped:
                continue
            dist = ((p.sprite.x - px) ** 2 + (p.sprite.y - py) ** 2) ** 0.5
            allow = _pawn_vmax(p) * dt * self.CONTINUITY_SLACK + 1e-6
            if dist > allow:
                self._flag(t, 'teleport', '%s@%s' % (role, self.v.level.name),
                           'moved %.3f in one frame (max legal %.3f), '
                           'state=%s not warping/snapping (Pawn.cs:871-879)'
                           % (dist, allow, p.state))

    # -- driver API ---------------------------------------------------------
    def frame(self, t, dt):
        self._check_dead_click(t)
        self._check_continuity(t, dt)

    def finish(self):
        """end-of-run checks + the report; call once, returns violations"""
        missing = getattr(self.v.cache, 'missing', None)
        if missing:
            for name in sorted(missing):
                self._flag(-1, 'missing-sheet', name,
                           'a drawn animation never found its sheet '
                           '(SheetTexture resolution)')
        return self.violations
