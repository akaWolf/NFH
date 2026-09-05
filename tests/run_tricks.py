"""The trick matrix (pass 3 of docs/FINAL_AUDIT_PROMPT.md): every trick of
every level driven to the score, from the data.

A plan file (tests/plans/<season>/<Level>.txt) lists the legs; this driver
executes them on the real 60 Hz viewer loop (over runtime/record.py's
Recorder) with the safety loop a player performs by hand: a leg starts
when its target zone is free of catchers, Woody flees to a parked zone
when one walks in, and the run restarts (score and all — GameInfo restart
semantics) when he is caught anyway.

Plan commands, one per line ('#' comments):
    take <Item> <Type>       click the search item until Type is held
    use <Item>               bare-hand click, success = item tricked
    usewith <Item> <Type>    select Type, click; success = tricked/armed
    prime <Item> [<Type>]    same click, success = item.primed flips (or
                             the held Type's source item primes on it)
    walk <x> <y>             click the world point, wait until Woody
                             stands there (a tutorial's location action)
    activated <Item>         park safe until the item's GameObject is
                             active (it ships inactive, an event activates it)
    tutorial <n>             park safe until the App's LevelScript has
                             completed its action n (the unlocks / the
                             neighbour's unfreeze); `tutorial end` — the
                             camera script's End state
    unlock <Item> <Type>     dexterity unlock: select Type, click, drive
                             the minigame to the win
    await <Item> [<score>]   park safe until the trick pays; assert the
                             increment equals <score> when given
    reclick <Item>           click a tricked item again: expect the
                             WrongTrick/NoNo refusal, no state change
    park <ZoneName|auto>     walk to the zone (auto = safest by routine)
    icon <Type>              click the held Type's HUD inventory icon
                             (Item.OnIconPressed: the phone alarms)
    hide <HideItem>          climb into the bed/wardrobe and stay hidden
                             (the next leg's click brings Woody out)
    wait <seconds>           idle that long (still dodging)
    sneak on|off|auto        the Tab toggle by hand; auto (the default)
                             sneaks in/into Alerter zones, runs elsewhere
    manual <text...>         a step the data cannot script — recorded as
                             such in the results (a pass-3 finding)
    entrance skip            (first line) start with the walk-in finished:
                             Woody at his StartLocation, input unlocked —
                             a manual step; no plan needs it since the
                             Season-2 FinishedEntrance fix (see apply_prelude)
    Modifiers: `op!` (usewith! / take! / await! ...) rushes — no gate wait,
    no dodging for that leg (the human's judgement call, e.g. Level108's
    toothbrush race); a trailing `+N` on a gated leg asks the gate to hold
    N more seconds (a raid into a dead-end room sized as a whole).

    python3 tests/run_tricks.py tests/plans/s1/Level101.txt
    python3 tests/run_tricks.py --all [--out=/tmp/nfh-tricks] [--jobs=4]
"""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

from record import Recorder, DT, WIDTH, HEIGHT     # noqa: E402
from app import App                                 # noqa: E402
from prefs import MemoryPrefs                       # noqa: E402
from menu import GameIntroAnimation                 # noqa: E402

LEG_TIMEOUT = 75.0      # a walk + search anywhere fits well inside this
STATE_EVERY = 10          # state.jsonl rows per 60 Hz ticks (6 Hz)
AWAIT_TIMEOUT = 150.0   # a routine lap is ~35 s; alarms and toilets stall it
GATE_TIMEOUT = 160.0    # a Season-2 lap is ~100 s (L210: 98 s) — the room may open only next lap
MAX_RESTARTS = 4


def parse_plan(path):
    legs = []
    for ln in open(path):
        ln = ln.split('#')[0].strip()
        if ln:
            legs.append(ln.split())
    return legs


class Driver(Recorder):
    def __init__(self, level_path, plan_path, outdir):
        Recorder.__init__(self, level_path, outdir, script=None,
                          seconds=1e9, fps=0)
        self._tick_i = 0
        # the level runs in the App, not the bare Viewer: the App builds
        # and ticks the tutorial layer (LevelScript + the camera script,
        # app.py load_level / _tick_level) — Level206's script freezes
        # Woody until the neighbour's fourth in-game action, and a bare
        # Viewer took clicks the original drops (Woody.Frozen, cs:637)
        self.level_name = os.path.splitext(os.path.basename(level_path))[0]
        GameIntroAnimation.finished = False
        self.app = App(headless=True, prefs=MemoryPrefs())
        self._enter_level()
        self.plan_path = plan_path
        self.legs = parse_plan(plan_path)
        self.results = []                # one dict per leg
        self.restarts = 0
        self.t = 0.0
        self.clicks = []
        self.paid = {}                   # item pid -> score it was paid
        self._apply_collider_enabled()
        self._install_anim_probes()
        from invariants import Invariants
        self.inv = Invariants(self.v)
        self.frame_hooks.append(self.inv.frame)

    def _install_anim_probes(self):
        """count each pawn's AnimPlayer.tick calls per world tick: the port
        ticks a pawn's player twice per frame (once in World.tick's
        `players` loop, once in Pawn.tick's `self.anim.tick(dt)`), so his
        animations run at 2x the sheet's FrameRate — the original's Refresh
        runs once per Repaint (AnimationControllerBase.cs:172-189, 102-142).
        The timing model reads the sheets, so it divides by the measured
        rate; a runtime fix drops the rate to 1 on its own."""
        self._anim_calls = {}
        self._anim_rate = {}
        for role, p in self.world.pawns.items():
            pl = p.anim
            if getattr(pl, '_probe_role', None) == role:
                continue
            orig = pl.tick
            def wrapped(dt, _o=orig, _r=role):
                self._anim_calls[_r] = self._anim_calls.get(_r, 0) + 1
                return _o(dt)
            pl.tick = wrapped
            pl._probe_role = role

    def anim_rate(self, p):
        """animation ticks per world tick for pawn p (1 = the sheet rate)"""
        return max(1, self._anim_rate.get(getattr(p, 'role', None), 1))

    def _apply_collider_enabled(self):
        """Collider.enabled as shipped: Physics.Raycast never hits a
        collider whose component is disabled, and 100+ items serialize
        `enabled: false` (Level202's Fence1/Fence2/Rocks are 15x10 boxes
        over the whole yard, dead template items with no zone; Level206's
        DeckChair/DogFifi and Level207's PoolLadder/BeachLogo too). The
        port used to initialize Item.clickable = True regardless of the
        byte — a pass-3 PORT finding (docs/audit/verified/plans_s2a.md),
        fixed by the fix agents during the pass (scene.py reads the byte
        at load now); this mirror from the data is kept as a no-op
        safety so the plans stay independent of that fix. The runtime's
        own toggles (EnableColliderAfterPrime, the Pipe hack, ...) still
        flip clickable afterwards, as they do in the original."""
        L = self.v.level
        for it in L.items.values():
            o = L._o(it.pid)
            if o is None:
                continue
            go = L._go_of(o)
            box = L._component(go, 'BoxCollider')
            if box and 'data' in box and box['data'].get('enabled') is False:
                it.clickable = False

    # -- state helpers ------------------------------------------------------
    @property
    def world(self):
        return self.v.world

    def item(self, name):
        """an item by name; twins disambiguate as Name@ZoneName"""
        zone = None
        if '@' in name:
            name, zone = name.split('@', 1)
        for it in self.v.level.items.values():
            if it.name != name:
                continue
            if zone is None or self.zone_name(it.zone) == zone:
                return it
        raise SystemExit('plan names no such item: %r' % name)

    def zone_name(self, pid):
        z = self.v.level.zone_by_pid(pid)
        return z.name if z else None

    def catchers(self):
        """the pawns whose sight ends the game (GameInfo.Update's Classic
        checks: the Rottweiler chain and the Mother else-if,
        GameInfo.cs:181-199, 222-224)"""
        out = []
        for role in ('Rottweiler', 'Mother'):
            p = self.world.pawns.get(role)
            if p is not None:
                # an IgnoreWoodyWhenUse use (Level205's WaterSkiis,
                # Item.cs:828-831) blinds him only until the use ends and
                # OnUseEnded clears the flag — a catcher again where he
                # stands; eta_to_zone reads the use's remainder for him
                out.append(p)
        return out

    def routine_zones(self):
        """zones the routines visit — unsafe to park in; the serialized
        ToiletAction's zone counts too (the laxative rush,
        Rottweiler.MoveToToilet -> StartToiletAction)"""
        pids = set()
        for r in self.world.routines:
            for a in r.actions:
                it = self.v.level.items.get(a['item'])
                if it is not None:
                    pids.add(it.zone)
            ta = getattr(r.pawn, 'toilet_action', None) or {}
            it = self.v.level.items.get(ta.get('item')) if ta.get('item') \
                else None
            if it is not None:
                pids.add(it.zone)
        return pids

    def parkable(self, z):
        """a zone Woody may stand in without ending the level: not the
        exit zone (the street) — a finished-entrance pass through the
        ExitDoor ends the game (Pawn.cs:1662-1665; the ExitConfirmation
        dialog is not modelled)"""
        return not z.exit

    def corridor_zones(self):
        """zones a routine walks THROUGH between consecutive actions (the
        shortest path, as ActionManager's MoveAction routes) — a corridor
        is no place to park either (Level208's hub Zone05)"""
        pids = set()
        L = self.v.level
        for r in self.world.routines:
            zs = [L.items[a['item']].zone for a in r.actions
                  if a.get('item') in L.items
                  and L.items[a['item']].zone is not None]
            for i in range(len(zs)):
                a, b = zs[i], zs[(i + 1) % len(zs)]
                for zp, _door in (L.find_path(a, b) or []):
                    pids.add(zp)
        return pids

    def safe_zone(self):
        """the nearest parkable zone no routine action visits or walks
        through; else the nearest parkable zone at all (the await leg then
        prefers a hiding spot, see _hide_spot)"""
        woody = self.v.woody
        visited = self.routine_zones() | self.corridor_zones()
        here = woody.zone.pid if woody is not None and woody.zone else None
        # (a zone with no route from here — Level214's captain cabin behind
        # its DisableOnStart doors — is no parking spot)
        def reachable(z):
            return here is None or self.hops(here, z.pid) < 99
        zones = [z for z in self.v.level.zones
                 if z.pid not in visited and self.parkable(z) and reachable(z)]
        if not zones:
            # every zone is on some routine (the S2 yards): park where the
            # catchers arrive last, not nearest — Level207's nearest was
            # the Mother's own deck-chair zone, and her nap ends
            zones = [z for z in self.v.level.zones
                     if self.parkable(z) and reachable(z)]
            if not zones:
                return None
            def latest(z):
                etas = [self.eta_to_zone(p, z.pid, horizon=90.0)
                        for p in self.catchers()]
                etas = [e for e in etas if e is not None]
                return (-(min(etas) if etas else 90.0),
                        self.hops(here, z.pid) if here else 0)
            zones.sort(key=latest)
            return zones[0]
        zones.sort(key=lambda z: self.hops(here, z.pid) if here else 0)
        return zones[0]

    def _hide_spot(self):
        """the nearest HideItem Woody can reach (a bed / wardrobe / basket
        with a live collider) — None when the level has none"""
        w = self.v.woody
        here = w.zone.pid if w is not None and w.zone is not None else None
        spots = [i for i in self.v.level.items.values()
                 if i.kind == 'HideItem' and i.collider is not None
                 and i.zone is not None]
        if not spots or here is None:
            return None
        spots.sort(key=lambda i: (self.hops(here, i.zone),
                                  abs(i.target_x - w.sprite.x)))
        return spots[0] if self.hops(here, spots[0].zone) < 99 else None

    def hops(self, a_pid, b_pid):
        if a_pid == b_pid:
            return 0
        path = self.v.level.find_path(a_pid, b_pid)
        return len(path) if path else 99

    # -- the timing model ---------------------------------------------------
    # A human raids a room by reading the neighbour's routine: how long
    # until he is back HERE versus how long the job takes.  The driver
    # estimates both from the live world — his remaining path/use plus the
    # next actions of the routine, Woody's hops and walk — with a margin.
    HOP_TIME = 4.0          # a door pass: walk-up climb + Leave/Enter anims
    ESCAPE_MARGIN = 15.0    # slack to leave a room its owner is walking to
    USE_TIME = 3.5          # Woody's use/take animations at the item
                            # (MakeTrick+TrickLaugh ~1.5 s, a take ~1.3 s)
    MARGIN = 1.5

    def _speed(self, p):
        force = p.run_force if p.in_urgent else p.force
        return max(0.2, (force or 1.0) * (p.walk_speed_scale() or 1.0))

    def door_time(self, door, p=None):
        """seconds a catcher spends in a door pass: a flat door fires
        Leave and Enter at once (Pawn._begin_transit's non-sequential
        branch — the longer sheet, ~2.0 s at 20 frames/10 fps), a walk-up
        door climbs first and runs them one after the other (~3.5 s);
        the old flat 4.0 s over-read the flat doors by 2× and the flee
        started when the neighbour was already through"""
        if door is None:
            return self.HOP_TIME
        # Season 2: the walked transitions — a flat pair is ~1.4 units at
        # the neighbour's walk (0.875 u/s), the stairs a diagonal climb
        # at DoorForceMagnitude that the traces put at ~4 s
        if door.is_transition and door.complex_move:
            return 4.0 if door.nfh2_stairs else 1.6
        if door.should_walk_up:
            return 3.5
        return 2.0

    def _anim_left(self, player):
        """seconds left in the current animation plus the pending sequence"""
        def length(a):
            n = len(a.pattern) if a.pattern else (a.end - a.start + 1)
            return max(1, n) / float(a.fps or 10.0)
        a = player.anim
        done = player.pat_idx if a.pattern else (player.frame - a.start)
        left = max(0.0, length(a) - max(0, done) / float(a.fps or 10.0))
        for name in player.seq[player.seq_index:]:
            i = player.by_name.get(name)
            if i is not None:
                left += length(player.sprite.anims[i])
        # the sheet times over the measured tick rate (anim_rate)
        role = getattr(player, '_probe_role', None)
        return left / float(max(1, self._anim_rate.get(role, 1)))

    def sleep_left(self, p):
        """seconds until a sleeping catcher wakes: the bar's sleep window
        ends when the item's sequence index leaves [start, end)
        (ProgressBar.cs:148 — the elements after AnimationEndIndex are the
        get-up), so count the current element's remainder plus the elements
        up to that index; 0 when no bar explains the sleep"""
        best = None
        player = p.anim
        for pb in getattr(self.world, 'progress_bars', ()):
            if pb.pawn is not p or not pb.visible or pb.item is None:
                continue
            idx = pb._check_state(pb.item.current_sequence)
            if idx == -1:
                continue
            end = pb.spec['seqs'][idx]['AnimationEndIndex']
            def length(a):
                # one frame per 1/fps (AnimationControllerBase.Refresh's
                # accumulator); a 1-frame element at 1 fps is 1 s
                n = len(a.pattern) if a.pattern else (a.end - a.start + 1)
                return max(1, n) / float(a.fps or 10.0)
            a = player.anim
            done = player.pat_idx if a.pattern else (player.frame - a.start)
            left = max(0.0, length(a) - max(0, done) / float(a.fps or 10.0))
            # the stamp is post-increment (Item.CurrentSequenceIndex =
            # SequenceIndex after the pull, AnimationControllerBase.cs:
            # 277-284, world.py's _seq_step_hack): element k plays with
            # the stamp at k+1, so the window [start, end) covers elements
            # start-1 .. end-2 and the sleep ends when element end-1
            # (the get-up / the pool leave) STARTS — Level207's Mother
            # read 5.6 s (MotherPoolLadderLeave) too long with `end`
            for k in range(player.seq_index, min(end - 1, len(player.seq))):
                i = player.by_name.get(player.seq[k])
                if i is not None:
                    left += length(player.sprite.anims[i])
            best = left if best is None else min(best, left)
        return best if best is not None else 0.0

    def eta_to_zone(self, p, zone_pid, horizon=60.0, after=0.0):
        """seconds until catcher p stands in zone_pid, or None past the
        horizon; his current step list is real, the following actions of
        the routine an estimate. `after`: the caller only cares from that
        moment on — a catcher standing in the zone now but walking out of
        it before then (his live path) counts by his RETURN, not by 0"""
        r = next((r for r in self.world.routines if r.pawn is p), None)
        if p.zone is None:
            return None
        if r is not None and r.frozen and r.state == r.IDLE \
                and r.urgent_item is None and not p.steps \
                and p._step is None:
            # a frozen manager parked in place (ActionManager.Frozen —
            # Level201's tutorial neighbour before the script's Unfreeze,
            # the FreezeAfterCompletion park): he stands where he is, and
            # urgents are swallowed too (cs:604-606, 657-660)
            return 0.0 if p.zone.pid == zone_pid else None
        if r is not None and r.state == r.USING and r.action is not None \
                and r.action.get('mutex') and r.urgent_item is None:
            # a MutexAction never ends on its own (RoutineActionUse.cs:
            # 172-177; the release is another pawn's PawnToAbortMutexOnFinish,
            # cs:342-351): Level205's neighbour stands watching the mat —
            # a human reads that as "not coming until Olga is done"
            return 0.0 if p.zone.pid == zone_pid else None
        if p.zone.pid == zone_pid and not p.is_warping:
            dwell = self._dwell(p, zone_pid) if after > 0.0 else None
            if dwell is None or dwell >= after:
                # a sleeping catcher (IsSleeping gates both catch
                # predicates, GameInfo.cs:189/198) is harmless until his
                # bar's window ends; an ignoring one until his use ends
                if p.is_sleeping:
                    return self.sleep_left(p)
                if p.ignore_woody:
                    return self._anim_left(p.anim)
                return 0.0
            # else: gone before `after` — fall through to his return
        exit_door = getattr(p, '_exit_door', None)
        if p.is_warping and exit_door is not None:
            if exit_door.zone == zone_pid:
                return 1.0
        t = 0.0
        speed = self._speed(p)
        x = p.sprite.x
        y = p.sprite.y
        zone = p.zone.pid
        if p.is_warping and exit_door is not None:
            t += 1.5
            zone = exit_door.zone
            x = exit_door.x
        # a use in progress delays everything after it — the live steps
        # included: a surprise/toilet detour pauses the pawn with his
        # route still queued (Level103's neighbour sat 10 s of angry on
        # the loo with the door step to the hall next in line)
        if r is not None and r.state == r.USING:
            t += self._anim_left(p.anim)
        # the live path
        steps = ([p._step] if p._step is not None else []) + list(p.steps)
        for s in steps:
            kind = s.get('kind')
            if kind in ('point', 'cpoint', 'item'):
                tx = s.get('x', x)
                ty = s.get('y', y)
                # a Season-2 stair step walks the diagonal (normalized
                # velocity, Pawn.cs Move): its length is the hypotenuse —
                # a same-x descent is not free
                t += ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5 / speed
                x, y = tx, ty
                # a Season-2 walk-through stair/flat transition: the pawn's
                # zone flips at the 'transfer' step (Helpers.LinkNodes'
                # TransferToZone, README "The walk-through stairs")
                if s.get('transfer') is not None:
                    zone = s['transfer']
                    if zone == zone_pid:
                        return t
            elif kind == 'door':
                d = s['door']
                t += abs(d.x - x) / speed + self.door_time(d, p)
                other = self.v.level.door_by_pid(d.link_to)
                if other is None:
                    break
                zone = other.zone
                x = other.x
                if zone == zone_pid:
                    return t
            if t > horizon:
                return None
        if r is None:
            return None

        def travel_to(it, t, x, zone, spd=None):
            """walk from (zone, x) to it's use spot; None past the target
            zone (the caller returns t then), else (t, x, zone). `spd`
            overrides the pace: an Urgent routine action is approached at
            a run (RoutineActionMove.OnActionStarted, cs:68-75 — Level206's
            DeckChair/Pillows legs), a walker's estimate reads twice too
            long there"""
            sp = spd or speed
            path = self.v.level.find_path(zone, it.zone) \
                if zone != it.zone else []
            if path is None:
                return None, t, x, zone
            for zp, door in path:
                # the walk to this hop's door, then the pass; the far
                # door is where the next stretch starts (a lap of the
                # sofa->beer walk is 5 s of floor before the 2 s door)
                t += abs(door.x - x) / sp + self.door_time(door, p)
                other = self.v.level.door_by_pid(door.link_to)
                if other is not None:
                    x = other.x
                if zp == zone_pid:
                    return 'hit', t, x, zp
            zone = it.zone
            t += abs(it.target_x - x) / sp
            x = it.target_x
            if zone == zone_pid:
                return 'hit', t, x, zone
            return 'ok', t, x, zone
        run_speed = max(0.2, (p.run_force or p.force or 1.0)
                        * (p.walk_speed_scale() or 1.0))

        # the detour he is on and the action he has not reached yet come
        # before the actions ahead: an urgent run (a surprise, the toilet
        # rush, an alarm) with its use, then the interrupted routine
        # action's own travel and use — the old tail skipped straight to
        # the NEXT action and read a 25 s toilet trip as 14 s
        ahead = []
        if r.urgent_item is not None and not p.at_use_range(r.urgent_item):
            ahead.append(r.urgent_item)
        elif r.urgent_item is not None and r.state != r.USING:
            t += self.use_len(p, r.urgent_item)   # at it, not started
        if r.item is not None and r.item is not r.urgent_item \
                and (r.urgent_item is not None
                     or (r.state != r.USING
                         and not p.at_use_range(r.item))):
            # (a use in progress is already the _anim_left above — the
            # Level208 platform's hover puts him out of at_use_range while
            # he is on it, and re-adding its whole sequence read 47 s for
            # a 15 s walk)
            ahead.append(r.item)
        elif r.item is not None and r.item is not r.urgent_item \
                and r.urgent_item is None and r.state != r.USING:
            # arrived, the use not started yet (MOVING with the last step
            # done): the whole use is still ahead — Level105's piano read
            # as 3 s to the kitchen the frame he reached the stool
            t += self.use_len(p, r.item)
        for it in ahead:
            hit, t, x, zone = travel_to(it, t, x, zone)
            if hit is None:
                return None
            if hit == 'hit':
                return t
            t += self.use_len(p, it)
            if t > horizon:
                return None
            # a tricked use that ends in the loo rush (CauseSickness /
            # RushToToilet -> MoveToToilet, Rottweiler.cs:542-550): the
            # toilet is the next stop, at the run
            toilet = self._rush_target(p, it)
            if toilet is not None:
                hit, t, x, zone = travel_to(toilet, t, x, zone, run_speed)
                if hit is None:
                    return None
                if hit == 'hit':
                    return t
                t += self.use_len(p, toilet)
        # the use he is in right now, when it will end in the loo rush
        cur = r.urgent_item if r.urgent_item is not None else r.item
        if r.state == r.USING and cur is not None and cur not in ahead:
            toilet = self._rush_target(p, cur)
            if toilet is not None:
                hit, t, x, zone = travel_to(toilet, t, x, zone, run_speed)
                if hit is None:
                    return None
                if hit == 'hit':
                    return t
                t += self.use_len(p, toilet)
        # the actions ahead
        n = len(r.actions)
        for k in range(1, n + 1):
            a = r.actions[(r.index + k) % n]
            it = self.v.level.items.get(a['item'])
            if it is None:
                continue
            hit, t, x, zone = travel_to(it, t, x, zone,
                                        run_speed if a.get('urgent') else None)
            if hit is None:
                return None
            if hit == 'hit':
                return t
            t += self.use_len(p, it)
            if t > horizon:
                return None
            toilet = self._rush_target(p, it)
            if toilet is not None:
                hit, t, x, zone = travel_to(toilet, t, x, zone, run_speed)
                if hit is None:
                    return None
                if hit == 'hit':
                    return t
                t += self.use_len(p, toilet)
        return None

    def _rush_target(self, p, it):
        """the ToiletAction item when a use of `it` (as it stands now)
        would end in the rush: tricked, and RushToToilet or a RushToToilet
        dependency (TrickItem.CauseRushToToilet, cs:683-686)"""
        try:
            items = self.v.level.items
            if it.kind not in ('TrickItem', 'Toilet', 'Television') \
                    or not it.is_tricked(items) \
                    or not it.cause_rush_to_toilet(items):
                return None
        except Exception:
            return None
        ta = getattr(p, 'toilet_action', None) or {}
        toilet = items.get(ta.get('item')) if ta.get('item') else None
        return toilet if toilet is not it else None

    def use_len(self, p, it):
        """seconds the catcher spends at `it`: his use sequence for its
        current tricked state (Item.sequence_for) plus the angry/fix tail
        when it will go angry; 8 s when nothing is known"""
        try:
            role = getattr(p, 'role', 'Rottweiler')
            tricked = it.is_tricked(self.v.level.items) \
                if hasattr(it, 'is_tricked') else it.tricked
            seq = it.sequence_for(role, tricked, self.v.level.items) or []
        except Exception:
            return 8.0
        def length(names):
            s = 0.0
            for name in names:
                i = p.anim.by_name.get(name) if name else None
                if i is None:
                    continue
                a = p.anim.sprite.anims[i]
                n = len(a.pattern) if a.pattern else (a.end - a.start + 1)
                s += max(1, n) / float(a.fps or 10.0)
            return s
        t = length(seq)
        if t <= 0.0:
            return 8.0 / self.anim_rate(p)
        if tricked:
            # Rottweiler.PlayAngryAnimation, Classic (cs:597-611): a cold
            # meter plays AngryEasyUp, a hot one AngryEasyDown + AngryHard
            # (9 s on the S1 sheets); the fix rides the tail (cs:767-777)
            hot = getattr(p, 'angry_meter', 0.0) > 0.0
            angry = length([it.angry_easy_down, it.angry_hard]) if hot \
                else length([it.angry_easy_up])
            fix = length(it.fix_sequence) if it.use_fix_sequence \
                else length([it.fix_animation])
            t += (angry or 2.4) + fix
        return t / self.anim_rate(p)

    def woody_door_time(self, door):
        """Woody's own pass: a walk-up door is climb + Leave (10 fr) +
        Enter (16 fr) + descend, ~4.4 s; a flat door plays both sheets at
        once, ~2.5 s (WoodyDoorLeftEnter is 25 fr). Season 2's ComplexMove
        transitions are walked, not warped (Helpers.LinkNodes, README "The
        walk-through stairs"): a flat pair is ~1.4 units of floor at his
        run speed, the NFH2Stairs pair a ~1-unit diagonal climb"""
        if door.is_transition and door.complex_move:
            return 1.5 if door.nfh2_stairs else 1.0
        return 4.4 if door.should_walk_up else 2.5

    def use_time(self, item):
        """seconds Woody's use of `item` takes: the length of his use
        animation (or sequence) plus the TrickLaugh / TakeInventory tail —
        the S2 rake is a 0.3 s TakeRight, the S1 sofa cushion a 4 s
        crouch; the flat USE_TIME over-read the quick ones by 4x and kept
        the gate shut on rooms the neighbour leaves for ~10 s per lap"""
        if item is None:
            return self.USE_TIME
        if item.kind == 'HideItem':
            # HideItem.InternalUse -> Woody.Hide sets Hiding the moment he
            # arrives (README "Hiding"): the climb-in animation plays with
            # him already out of both catch predicates
            return 0.5
        w = self.v.woody
        names = list(item.animation_sequence) if item.use_woody_sequence \
            else ([item.animation] if item.animation else [])
        t = 0.0
        for n in names:
            i = w.anim.by_name.get(n)
            if i is None:
                continue
            a = w.anim.sprite.anims[i]
            frames = len(a.pattern) if a.pattern else (a.end - a.start + 1)
            t += max(1, frames) / float(a.fps or 10.0)
        if t <= 0.0:
            return self.USE_TIME
        # no cap: Level102's saw is SawSofa x3 = 14.3 s at 13 fps and the
        # trick lands only at the sequence end (Woody.cs:412-416) — a cap
        # sent Woody up for a job the beer run cannot hold; the sheet time
        # over the measured tick rate (the port runs Woody at 2x, see
        # _install_anim_probes)
        return max(2.0, (t + 1.5) / self.anim_rate(w))

    def woody_need(self, zone_pid, x, item=None):
        """seconds for Woody to reach (zone, x) and finish a use there:
        the walk to each door of the route at his run speed (force 1.6 x
        speed 1.25 = 2.0), the pass, the last stretch, the use"""
        w = self.v.woody
        if w.zone is None:
            return 99.0
        path = self.v.level.find_path(w.zone.pid, zone_pid) \
            if w.zone.pid != zone_pid else []
        if path is None:
            return 99.0
        t = 0.0
        wx = w.sprite.x
        cur = w.zone.pid
        for zp, door in path:
            # the door stands in the zone Woody is leaving (`cur`); the
            # auto-sneak crawls through the Alerter rooms at 0.52
            # (woody_speed), 4x the run the flat /2.0 assumed
            t += abs(door.x - wx) / self.woody_speed(cur) \
                + self.woody_door_time(door)
            other = self.v.level.door_by_pid(door.link_to)
            if other is not None:
                wx = other.x
            cur = zp
        return t + abs(x - wx) / self.woody_speed(zone_pid) \
            + self.use_time(item)

    def in_use_now(self, item):
        """a routine is using `item` (or the item its trick lands on) this
        very moment — a trick planted mid-use is checked by that use's
        stop flow (StopAction's postponed angry, RoutineActionUse.cs) and
        the fix wipes its FixItemTrick/LinkedItemTrick partner with it
        (Item.cs:2103-2107): a human waits for the use to end"""
        if item is None:
            return False
        related = {item.pid, item.activate_item_trick, item.linked_item_trick,
                   item.set_tricked_on_item}
        for r in self.world.routines:
            if r.state != r.USING or r.item is None:
                continue
            if r.role not in ('Rottweiler', 'Mother'):
                # Olga's use has no stop-flow check and no fix (Item.Use ->
                # OlgaUse, Item.cs:1139-1141): Level204's Olga sits in the
                # PullKart for good — the grease still goes on the axle.
                # (By role, not by catchers(): a neighbour who ignores
                # Woody during a use — IgnoreWoodyWhenUse, Level208's
                # platform hover — still runs the stop flow at its end)
                continue
            # the item under his hands: an urgent detour's (the toilet, a
            # surprise) while one runs — r.item is then only the routine
            # action he will come back to (Level103's candle stayed
            # "in use" through the whole first-aid rush)
            cur = r.urgent_item if r.urgent_item is not None else r.item
            if cur is None:
                continue
            if cur.pid in related or item.pid in (
                    cur.linked_item_trick, cur.fix_item_trick):
                return True
        return False

    def gate_open(self, zone_pid, x, item=None):
        """start (or retry) a leg aimed at (zone, x)? The target zone must
        stay clear for the whole job, and every zone Woody crosses on the
        way must be clear while he passes it (he is through zone k of the
        path about (k+1) hops after the click) — a human reads the whole
        route, not just the room he is heading for"""
        if self.in_use_now(item):
            return False
        need = self.woody_need(zone_pid, x, item) + self.MARGIN \
            + getattr(self, '_extra_need', 0.0)      # the plan's `+N`
        w = self.v.woody
        path = []
        if w is not None and w.zone is not None and w.zone.pid != zone_pid:
            path = self.v.level.find_path(w.zone.pid, zone_pid) or []
        # the zone he starts from counts too: leaving a hiding spot or
        # crossing his own room to the first door takes time, and a
        # catcher walking in meanwhile catches him there
        leave = None
        # Woody's arrival time in each zone of the route (his real pace:
        # the sneak crawl in Alerter rooms, the per-door pass) — he is out
        # of zone k once he has arrived in zone k+1 (the pass itself is
        # IsPassingDoor-safe)
        arrive = []
        if path:
            first = path[0][1]
            leave = abs(first.x - w.sprite.x) / 2.0 \
                + (2.0 if w.hiding else 0.0) + self.MARGIN
            t = 2.0 if w.hiding else 0.0
            wx = w.sprite.x
            cur = w.zone.pid
            for zp, door in path:
                t += abs(door.x - wx) / self.woody_speed(cur) \
                    + self.woody_door_time(door)
                other = self.v.level.door_by_pid(door.link_to)
                if other is not None:
                    wx = other.x
                cur = zp
                arrive.append(t)
        for p in self.catchers():
            eta = self.eta_to_zone(p, zone_pid)
            # a catcher whose current routine action is IN the target zone
            # is on his way here: the job must end with room to walk out
            # again (Level208's ShoeMachine room has no wardrobe and two
            # doors that both lead onto his path) — a human wants that
            # slack, not just the use time
            r = next((r for r in self.world.routines if r.pawn is p), None)
            # (a hide leg needs no way out: the bed/wardrobe IS the way
            # out — Level114's balcony run ends in the bedroom bed with
            # the neighbour due there in ten seconds)
            hiding_leg = item is not None and item.kind == 'HideItem'
            heading = r is not None and r.item is not None \
                and r.item.zone == zone_pid and not hiding_leg \
                and (p.zone is None or p.zone.pid != zone_pid)
            if eta is not None and eta < need + (
                    self.ESCAPE_MARGIN if heading else 0.0):
                return False
            # a dead-end target with no wardrobe (Level110's balcony): the
            # job must end AND Woody must be through its only door before
            # the catcher walks in — the door pair he passes is held
            # (Pawn.cs:1359), so the exit has to start before his own pass
            exits = self.v.level.graph.get(zone_pid, [])
            if eta is not None and len(exits) == 1 and not any(
                    i.kind == 'HideItem' and i.zone == zone_pid
                    and i.collider is not None
                    for i in self.v.level.items.values()):
                _oz, exit_door = exits[0]
                walk_out = abs(exit_door.x - x) / self.woody_speed(zone_pid)
                if eta < need + walk_out + self.woody_door_time(exit_door):
                    return False
            if leave is not None:
                eta = self.eta_to_zone(p, w.zone.pid, horizon=30.0)
                if eta is not None and eta < leave:
                    return False
        # the route: the shortest one first; when a room on it is hot, the
        # way round it (Level210's Zone03 -> Zone01 goes by Zone02 OR
        # Zone04) — the leg then clicks that waypoint before the item
        self._route_via = None
        if path and not self._route_clear(path, arrive, zone_pid):
            hot = {zp for zp, _d in path if zp != zone_pid}
            alt = self.find_path_avoiding(w.zone.pid, zone_pid, hot) \
                if w is not None and w.zone is not None else None
            if not alt or [z for z, _d in alt] == [z for z, _d in path]:
                return False
            arrive2 = []
            t = 2.0 if w.hiding else 0.0
            wx = w.sprite.x
            cur = w.zone.pid
            for zp, door in alt:
                t += abs(door.x - wx) / self.woody_speed(cur) \
                    + self.woody_door_time(door)
                other = self.v.level.door_by_pid(door.link_to)
                if other is not None:
                    wx = other.x
                cur = zp
                arrive2.append(t)
            if not self._route_clear(alt, arrive2, zone_pid):
                return False
            self._route_via = alt[0][0]
        # and the way back out: a dead-end room (Level104's bathroom, only
        # through the hall) is a trap when the catcher walks into its
        # gateway while Woody is still busy inside — the job may fit, the
        # escape does not; a human does not go in then
        # (a room nobody reaches for a long while is a room Woody can wait
        # in until a way out clears — Level210's Zone01 with the neighbour
        # off to the shop for 40 s and both exits hot for the first 12)
        soon = [self.eta_to_zone(p, zone_pid) for p in self.catchers()]
        soon = [e for e in soon if e is not None]
        if not (item is not None and item.kind == 'HideItem') \
                and (not soon or min(soon) < 30.0) \
                and self._escape_slack(zone_pid, x, need) < 1.0:
            return False
        return True

    def _click_via(self, it, click):
        """the leg's first click: straight at the item, or — when the gate
        opened on the way-round route (_route_via) — at that route's first
        zone; the item click follows once Woody stands there (wait_until's
        waypoint poke). Woody's own path is the shortest one (Woody.cs
        FindPath), so the waypoint is how a human walks round a hot room"""
        via = getattr(self, '_route_via', None)
        w = self.v.woody
        if via is not None and w.zone is not None and via != w.zone.pid:
            z = self.v.level.zone_by_pid(via)
            if z is not None:
                self._waypoint = (via, click)
                self.click_zone(z)
                return
        self._waypoint = None
        click()

    def _route_clear(self, path, arrive, zone_pid):
        """every zone Woody crosses on `path` is clear while he passes it
        (he is out of zone k once he has arrived in zone k+1)"""
        for p in self.catchers():
            for k, (zp, _door) in enumerate(path):
                if zp == zone_pid:
                    continue
                eta = self.eta_to_zone(p, zp, horizon=30.0)
                out = arrive[k + 1] if k + 1 < len(arrive) \
                    else arrive[k] + self.HOP_TIME
                if eta is not None and eta < out + self.MARGIN:
                    return False
        return True

    def _escape_slack(self, zone_pid, x, t0):
        """seconds of margin the best way out of (zone, x) keeps once the
        job there is done at t0: for every parkable zone reachable from
        it (and every wardrobe/bed on the way) the catchers' ETA to each
        zone crossed minus the moment Woody would be through it; 60 when
        no catcher touches the route"""
        cs = self.catchers()
        if not cs:
            return 60.0
        best = None
        for z in self.v.level.zones:
            if z.pid == zone_pid or not self.parkable(z):
                continue
            path = self.v.level.find_path(zone_pid, z.pid)
            if not path:
                continue
            # arrivals: t at which Woody stands in each zone of the path
            t = t0
            wx = x
            cur = zone_pid
            arrive, xs, hides, safe_at = [], [], [], []
            for zp, door in path:
                t += abs(door.x - wx) / self.woody_speed(cur)
                # out of the zone he leaves the moment the pass begins
                # (IsPassingDoor; a walk-up door climbs ~1.2 s first)
                safe_at.append(t + (1.2 if door.should_walk_up else 0.0))
                t += self.woody_door_time(door)
                other = self.v.level.door_by_pid(door.link_to)
                nx = other.x if other is not None else door.x
                arrive.append(t)
                xs.append(nx)
                hides.append(next((i for i in self.v.level.items.values()
                                   if i.kind == 'HideItem' and i.zone == zp
                                   and i.collider is not None), None))
                wx = nx
                cur = zp
            slack = None
            for k, (zp, door) in enumerate(path):
                # (the catcher's presence counts from Woody's arrival on:
                # one standing there now but leaving first is read by his
                # return)
                eta = min((self.eta_to_zone(p, zp, horizon=60.0,
                                            after=arrive[k]) or 60.0)
                          for p in cs)
                # a wardrobe/bed in this zone: hidden after the walk to it
                # plus the blocking Hide_In (~2 s) — a way out by itself
                if hides[k] is not None:
                    th = arrive[k] + abs(hides[k].target_x - xs[k]) \
                        / self.woody_speed(zp) + 2.0
                    if best is None or eta - th > best:
                        best = eta - th
                # through a crossed zone once his next pass begins; the
                # destination he stays in
                out = safe_at[k + 1] if k + 1 < len(safe_at) else arrive[k]
                s = eta - out
                slack = s if slack is None else min(slack, s)
            if slack is not None and (best is None or slack > best):
                best = slack
        return 60.0 if best is None else best

    def danger(self, zone_pid):
        """a catcher in that zone or warping into it"""
        for p in self.catchers():
            if p.zone is not None and p.zone.pid == zone_pid:
                return True
            ed = getattr(p, '_exit_door', None)
            if p.is_warping and ed is not None and ed.zone == zone_pid:
                return True
        return False

    def _occupied(self):
        """zones a catcher stands in — plus the far side of any door pair
        it is warping through right now (its .zone flips only at the warp)"""
        occ = set()
        for p in self.catchers():
            warping_out = p.is_warping and p._exit_door is not None
            if p.zone is not None and not warping_out:
                # a catcher asleep for a while yet (the sleep bar's window,
                # IsSleeping gates the catch) does not hold his room — a
                # human walks past the sleeper
                if not (p.is_sleeping and self.sleep_left(p) > 8.0):
                    occ.add(p.zone.pid)
            if warping_out:
                # mid-pass he holds the far room, not the one he is
                # leaving: both pawns in a door pass are IsPassingDoor
                # (GameInfo.cs:189) and Woody reaches that room only after
                # his own pass, when the catcher has long flipped
                occ.add(p._exit_door.zone)
            # Season 2: the far zone of the walk-through transition he is on
            s = p._step
            if s is not None and s.get('transfer') is not None:
                occ.add(s['transfer'])
        return occ

    def find_path_avoiding(self, start_pid, end_pid, avoid):
        """Level.find_path's BFS over the zone graph, skipping the zones in
        `avoid` — the way round a room a catcher stands in (Level210's
        Zone01 -> Zone03 goes through Zone04 OR Zone02; the plain BFS
        picks the first neighbour and calls the target unreachable when
        that room is held)"""
        import collections
        if start_pid == end_pid:
            return []
        prev = {start_pid: None}
        q = collections.deque([start_pid])
        graph = self.v.level.graph
        while q:
            cur = q.popleft()
            for nb, door in graph.get(cur, ()):
                if nb in prev or (nb in avoid and nb != end_pid):
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

    def _safe_route(self, dest_pid):
        """a route whose hops cross no zone holding a catcher exists"""
        w = self.v.woody
        if w.zone is None or dest_pid == w.zone.pid:
            return True
        occ = self._occupied()
        if dest_pid in occ:
            return False
        return bool(self.find_path_avoiding(w.zone.pid, dest_pid, occ))

    # -- primitives ---------------------------------------------------------
    def _auto_sneak_tick(self):
        """a human tiptoes past the sleeping pet: Alerter.CanSeeWoody spots
        a moving Woody in its zone unless he sneaks — while it is asleep
        (Alerter.cs:73-76, the Chili dog / the parrot); so sneak whenever
        Woody stands in, or his next door leads into, a zone holding an
        Alerter, and run everywhere else. `sneak on|off` in a plan takes
        the toggle over by hand; `sneak auto` hands it back."""
        if getattr(self, 'sneak_manual', False):
            return
        w = self.v.woody
        if w is None or w.zone is None:
            return
        if getattr(w, 'nfh2', False):
            # Season 2: Woody runs everywhere — Woody.ToggleSneak only flips
            # the flag there (Woody.cs:1151, the HUD's SneakRect does the
            # same) and the S2 sheets have no Walk_* states: setting
            # Sneaking is the KNOWN "sneak toggle crashes S2"
            return
        az = getattr(self, '_alerter_zones', None)
        if az is None:
            az = self._alerter_zones = {
                it.zone for it in self.v.level.items.values()
                if it.kind == 'Alerter' and it.zone is not None}
        here = w.zone.pid in az
        want = here
        # mid-pass into a pet's room the flag is set now, before the warp:
        # Woody.Sneaking is read live (the walk anim, the speed, and
        # Alerter.CanSeeWoody on the very landing tick — a one-frame gap
        # there woke Level111's dog and brought the alarm run every lap);
        # the walk up to the door stays a run
        ed = getattr(w, '_exit_door', None)
        room = w.zone.pid
        if w.is_warping and ed is not None:
            want = ed.zone in az
            room = ed.zone
        # the classic sneak past the busy neighbour: both catch predicates
        # carry `!IsPlayingBlockingAnimation() || !Woody.Sneaking`
        # (GameInfo.cs:185/189/198) — a sneaking Woody is invisible while
        # the catcher plays a blocking animation — and the Bed branch drops
        # the IsSleeping gate for a Velocity>0 term (cs:183-185): the
        # sleeper in Level109's bedroom hears a running Woody, not a
        # tiptoeing one. So tiptoe whenever a catcher shares the room
        # Woody is in (or is warping into); the gates only send him into
        # such a room while the catcher sleeps or is busy
        shared = False
        for p in self.catchers():
            if p.zone is not None and p.zone.pid == room \
                    and not p.is_warping:
                shared = True
                break
        if shared:
            want = True
        # a catcher about to walk in outranks the pet: sneaking is a
        # quarter of the running speed (force 0.8 x 0.65 vs 1.6 x 1.25),
        # and a woken pet only sends him searching — being seen ends the
        # level. Run when one is due in THIS pet room within a few seconds.
        if want and here and not shared and not w.hiding \
                and not w.is_warping:
            # ... but only when the tiptoe would not get him out in time:
            # the crawl to the flee route's first door plus the pass start
            _tz, first_door, _slack = self._flee_target(w.zone.pid)
            dist = abs(first_door.x - w.sprite.x) if first_door is not None \
                else 3.0
            crawl = dist / max(0.2, (w.force or 0.8)
                               * (w.speed_sneaking or 0.65)) + 2.0
            for p in self.catchers():
                eta = self.eta_to_zone(p, w.zone.pid, horizon=20.0)
                if eta is not None and eta < min(8.0, crawl):
                    want = False
                    break
        if want != w.sneak_toggle:
            w.sneak_toggle = want               # the Tab, Woody.ToggleSneak
            w.sneaking = want

    def step_world(self):
        game = self.world.game
        n0 = len(game.log)
        self._auto_sneak_tick()
        for k in self._anim_calls:
            self._anim_calls[k] = 0
        self.tick(self.t)
        for k, n in self._anim_calls.items():
            if n:
                self._anim_rate[k] = n
        self.t += DT
        if os.environ.get('TRICKS_DEBUG') and int(self.t * 60) % 30 == 0:
            w = self.v.woody
            bits = ['t=%.2f woody %s x=%.2f %s%s' % (
                self.t, self.zone_name(w.zone.pid) if w.zone else None,
                w.sprite.x, w.state, ' warp' if w.is_warping else '')]
            for p in self.catchers():
                bits.append('%s %s x=%.2f%s %s' % (
                    p.role, self.zone_name(p.zone.pid) if p.zone else None,
                    p.sprite.x, ' warp' if p.is_warping else '',
                    p.anim.anim.name))
            print('DBG ' + ' | '.join(bits))
        # attribute each new GameInfo.TrickDone entry to the item whose
        # AlreadyTricked flipped this tick (Item.OnTrickDone, Item.cs:2121)
        if self.world.game is game and len(game.log) > n0:
            fresh = [it for it in self.v.level.items.values()
                     if it.already_tricked and it.pid not in self.paid]
            new = game.log[n0:]
            if len(fresh) == 1:
                self.paid[fresh[0].pid] = sum(new)
            else:
                for it, sc in zip(fresh, new):
                    self.paid[it.pid] = sc
                for it in fresh[len(new):]:
                    self.paid[it.pid] = 0

    def run_seconds(self, s, dodge=True):
        end = self.t + s
        while self.t < end:
            if dodge:
                self._dodge_tick()
            self._dex_tick()
            self.step_world()
            if self.world.game.got_caught or self.world.game.ending:
                return False
        return True

    def run_entrance(self, max_seconds=4.0):
        """the start. Season 1 (Woody serializes FinishedEntrance false):
        the walk-in and its Hello — the fixed 4.0 s the S1 plans were tuned
        against. Season 2 (FinishedEntrance ships TRUE: no walk-in, Woody.cs:
        191, 223-231): a human clicks the moment StartGame's Entrance
        greeting releases the input (~1.0 s, IntroAnimation.cs:300-304,
        Woody.cs:372-375) — waiting the old 4.0 s cost Level206's Pillows
        race. Bounded by max_seconds either way."""
        w = self.v.woody
        spec = self.v.level.pawns.get('Woody') or {}
        if not spec.get('finished_entrance'):
            return self.run_seconds(max_seconds, dodge=False)
        end = self.t + max_seconds
        while self.t < end:
            if w is not None and not w.input_locked \
                    and w.state == w.IDLE and not w.anim.blocking:
                return True
            self._dex_tick()
            self.step_world()
            if self.world.game.got_caught or self.world.game.ending:
                return False
        return True

    def _dodge_tick(self):
        # the dodge loop's clicks are the flee — a replay on the original
        # sends those at once, where a leg's or a parking click waits for
        # Woody to be free (tools/livediff/tap.py's busy rule)
        self._click_kind = 'dodge'
        try:
            return self._dodge_tick_inner()
        finally:
            self._click_kind = 'leg'
    def _dodge_tick_inner(self):
        """the by-hand loop of a human run: when a catcher will be in
        Woody's zone sooner than Woody can leave it, hide in the zone's
        wardrobe if there is one, else flee along a route that crosses no
        occupied zone"""
        w = self.v.woody
        if w is None or w.zone is None or w.is_warping or w.hiding \
                or w.input_locked:
            return
        if getattr(self, '_rush', False):
            return                  # a `!` leg: the human's call, no dodging
        if w.state in (w.DOOR_CLIMB, w.DOOR_ANIM):
            # already at the door, climbing into the pass: a click now
            # ('climb' is swallowed by handle_click, but a Run_Up-less
            # frame lets it through) rebuilds the route and turns him
            # round mid-room — Level102's loo rush caught him that way
            return
        here = w.zone.pid
        soonest = None
        for p in self.catchers():
            eta = self.eta_to_zone(p, here, horizon=20.0)
            if eta is not None and (soonest is None or eta < soonest):
                soonest = eta
        if w.state == w.IDLE and w.anim.mode == 'single' and not w.hiding \
                and soonest is not None:
            # mid-use (a Single plays on an idle Woody): a click now aborts
            # the use and the trick with it; let a use that ends before the
            # catcher is here finish (Level105's football swap, with the
            # neighbour already walking over from the piano)
            left = self._anim_left(w.anim)
            if left + 0.5 < soonest:
                return
        # the route ahead: Woody walking into a zone a catcher holds or is
        # about to enter — a human stops short of that door and turns to
        # a safe room (or the wardrobe here) instead of running into him
        nxt = self._next_zone(w)
        if nxt is not None and nxt != here and w.state == w.WALK:
            # a catcher standing in the next zone blocks it unless his own
            # live path takes him out of it before Woody reaches the door
            # (the gate let Woody go because he is on his way out — the
            # sofa->beer walk of Level102 leaves the room 2 s after the
            # gate opens); a catcher warping into it always blocks
            ahead = False
            wd = self._woody_door_eta(w)
            for p in self.catchers():
                if p.zone is not None and p.zone.pid == nxt \
                        and not p.is_warping \
                        and not (p.is_sleeping
                                 and self.sleep_left(p) > 8.0):
                    # (a catcher asleep for a while yet does not block
                    # the room — IsSleeping gates the catch)
                    dwell = self._dwell(p, nxt)
                    if dwell is None or wd is None or dwell > wd:
                        ahead = True
                        break
                ed = getattr(p, '_exit_door', None)
                if p.is_warping and ed is not None and ed.zone == nxt:
                    ahead = True
                    break
                s = p._step
                if s is not None and s.get('transfer') == nxt:
                    ahead = True
                    break
            if not ahead:
                for p in self.catchers():
                    if p.zone is not None and p.zone.pid == nxt \
                            and not p.is_warping:
                        continue     # standing there: the dwell rule above
                    eta = self.eta_to_zone(p, nxt, horizon=20.0)
                    if eta is not None and eta < self.HOP_TIME + 3.0:
                        ahead = True
                        break
            if ahead and (getattr(self, '_flee_at', None) is None
                          or self.t - self._flee_at >= 2.5):
                self._flee_at = self.t
                hide = next((i for i in self.v.level.items.values()
                             if i.kind == 'HideItem' and i.zone == here
                             and i.collider is not None), None)
                target, _door, _slack = self._flee_target(here)
                if hide is not None and (soonest is None or soonest < 8.0):
                    r = self.click_item(hide)
                elif target is not None and target.pid != nxt:
                    r = self.click_zone(target)
                else:
                    r = self.click_zone(w.zone)      # stop where he is
                if r == 'transit':
                    self._flee_at = None   # swallowed mid-stairs: retry
                return
            if not ahead and soonest is not None:
                # already on his way out of the hot room into a clear one:
                # keep walking — turning back toward the wardrobe or a
                # farther door is what gets him caught mid-room
                wd_left = self._woody_door_eta(w)
                if wd_left is not None and wd_left < soonest + 1.5:
                    return
        # the flee route: the reachable parkable zone whose route keeps
        # the most slack (_flee_target); Woody's own exit time is the walk
        # to that route's first door plus a walk-up climb — he is safe once
        # the pass begins (IsWarping gates the catch, GameInfo.cs:189/198).
        # A route about to be sealed behind its first door (the slack of a
        # dead-end room's gateway) is taken now, before the catcher walks
        # into that gateway — waiting for him to head HERE is too late
        target, first_door, slack = self._flee_target(here)
        # (a route already sealed — no slack left — is not taken: walking
        # into the gateway the catcher holds is the catch; the route-ahead
        # check above then stops him and the two clicks alternate every
        # frame, Level102's kitchen during the loo rush)
        # (only from a dead-end room — one door out; a room with a second
        # exit is not sealed by a catcher heading for the first, and
        # leaving it toward him is what got Woody caught in Level108's
        # kitchen while the neighbour watered the plant next door)
        # (and only when a catcher will actually come HERE within the long
        # horizon: a bathroom nobody visits — Level105's, off the routine
        # unless the cheese rush — is not a trap, staying put is the safe
        # move; leaving it toward the hall he is heading for is not)
        coming = any(self.eta_to_zone(p, here, horizon=60.0) is not None
                     for p in self.catchers())
        # (and only with real slack left — under ~1.5 s Woody lands in the
        # gateway as the catcher does, Level110's balcony at the beer)
        sealing = slack is not None and 1.5 < slack < self.SLACK_MIN \
            and target is not None and w.state == w.IDLE and coming \
            and len(self.v.level.graph.get(here, [])) <= 1
        if target is None and soonest is not None and soonest < 8.0:
            # trapped: every route out crosses a held zone (Level206's
            # Zone03 between the Mother's deck chairs and the neighbour's
            # weights) — the wardrobe/pipe is the only move, and a human
            # takes it early, not at the last second the flee math allows
            hide = next((i for i in self.v.level.items.values()
                         if i.kind == 'HideItem' and i.zone == here
                         and i.collider is not None), None)
            if hide is not None and (getattr(self, '_flee_at', None) is None
                                     or self.t - self._flee_at >= 2.5):
                self._flee_at = self.t
                self.click_item(hide)
                return
        if soonest is None and not sealing:
            self._flee_at = None
            return
        exit_time = 1.5 + (2.0 if w.anim.blocking else 0.0)
        if first_door is not None:
            exit_time += abs(first_door.x - w.sprite.x) \
                / self.woody_speed(here) \
                + (1.2 if first_door.should_walk_up else 0.0)
        # a sleeper's wake time is a sequence-length estimate (sleep_left,
        # ~2 s off on Level207's Mother: read 2.8 s at the moment she got
        # up) — leave with the same margin the gate keeps
        exit_time += self.MARGIN
        if (soonest is None or soonest > exit_time) and not sealing:
            return
        # one flee click, not a storm: a re-click every tick rebuilds the
        # route and the door step never begins
        if getattr(self, '_flee_at', None) is not None \
                and self.t - self._flee_at < 2.5:
            return
        self._flee_at = self.t
        # (a sealing route with nobody heading here is left, not hidden
        # from — the wardrobe would keep Woody in the trap)
        hide = next((i for i in self.v.level.items.values()
                     if i.kind == 'HideItem' and i.zone == here
                     and i.collider is not None
                     and abs(i.target_x - w.sprite.x) / 2.0 + 1.0 < soonest),
                    None) if soonest is not None else None
        if hide is not None:
            if self.click_item(hide) == 'transit':
                self._flee_at = None       # swallowed mid-stairs: retry
            return
        if target is not None:
            if self.click_zone(target) == 'transit':
                self._flee_at = None

    def _dwell(self, p, zone_pid):
        """seconds until catcher p walks out of zone_pid on his live step
        list (the walk to its first door step), None when no door is
        ahead — he is staying"""
        if p.zone is None or p.zone.pid != zone_pid:
            return 0.0
        steps = ([p._step] if p._step is not None else []) + list(p.steps)
        x = p.sprite.x
        t = 0.0
        speed = self._speed(p)
        for s in steps:
            kind = s.get('kind')
            if kind == 'door':
                return t + abs(s['door'].x - x) / speed
            if s.get('transfer') is not None:
                return t + abs(s.get('x', x) - x) / speed
            if kind in ('point', 'cpoint', 'item'):
                tx = s.get('x', x)
                t += abs(tx - x) / speed
                x = tx
        return None

    def _woody_door_eta(self, w):
        """seconds until Woody reaches the first door on his live steps"""
        steps = ([w._step] if getattr(w, '_step', None) is not None
                 else []) + list(getattr(w, 'steps', []))
        x = w.sprite.x
        t = 0.0
        for s in steps:
            if s.get('kind') == 'door':
                return t + abs(s['door'].x - x) / 2.0
            if s.get('kind') in ('point', 'cpoint', 'item'):
                tx = s.get('x', x)
                t += abs(tx - x) / 2.0
                x = tx
                # Season 2: the zone flips at the walk-through transition's
                # 'transfer' step (no door warp)
                if s.get('transfer') is not None:
                    return t
        return None

    def _next_zone(self, w):
        """the zone behind the next door on Woody's live step list"""
        steps = ([w._step] if getattr(w, '_step', None) is not None
                 else []) + list(getattr(w, 'steps', []))
        for s in steps:
            if s.get('kind') == 'door':
                other = self.v.level.door_by_pid(s['door'].link_to)
                return other.zone if other is not None else None
            if s.get('transfer') is not None:
                return s['transfer']
        return None

    SLACK_MIN = 3.0         # flee before a route's slack drops below this

    def _route_slack(self, here, path):
        """seconds of margin the route keeps: for every zone Woody crosses
        after the first door, and for the destination, the catchers' ETA
        there minus the moment Woody would be through it (or standing in
        it) if he left now — a dead-end room (Level111's balcony and study
        behind the bedroom, the basement behind the hall) is sealed when
        the neighbour walks into its gateway zone, not into the room:
        the human leaves while the gateway is still clear"""
        w = self.v.woody
        # find_path lists (zone entered, the door walked through to enter
        # it) — that door stands in the previous zone
        zones = [here] + [zp for zp, _d in path]
        doors = [d for _zp, d in path]
        cs = self.catchers()
        t = 0.0
        x = w.sprite.x
        slack = None
        for i, door in enumerate(doors):
            # through zones[i]: the walk to its exit door and the pass —
            # he is out of the catch the moment the pass begins (a flat
            # door at once, a walk-up one after the ~1.2 s climb:
            # IsPassingDoor, GameInfo.cs:189), not when he lands beyond
            t += abs(door.x - x) / self.woody_speed(zones[i])
            safe_at = t + (1.2 if door.should_walk_up else 0.0)
            t += self.woody_door_time(door)
            if i > 0:
                eta = min((self.eta_to_zone(p, zones[i], horizon=60.0)
                           or 60.0) for p in cs) if cs else 60.0
                slack = eta - safe_at if slack is None \
                    else min(slack, eta - safe_at)
            other = self.v.level.door_by_pid(door.link_to)
            x = other.x if other is not None else door.x
        eta = min((self.eta_to_zone(p, zones[-1], horizon=60.0) or 60.0)
                  for p in cs) if cs else 60.0
        slack = eta - t if slack is None else min(slack, eta - t)
        return slack

    def woody_speed(self, zone_pid):
        """Woody's floor speed in a zone: the run (2.0) everywhere but the
        Alerter zones, which the auto-sneak crosses at the sneak speed
        (force 0.8 x SpeedSneaking 0.65 = 0.52 — a 6-unit living room is
        11 s tiptoeing against 3 s running)"""
        w = self.v.woody
        if getattr(self, 'sneak_manual', False):
            sneak = w is not None and w.sneak_toggle
        else:
            az = getattr(self, '_alerter_zones', None)
            if az is None:
                az = self._alerter_zones = {
                    it.zone for it in self.v.level.items.values()
                    if it.kind == 'Alerter' and it.zone is not None}
            sneak = zone_pid in az
            # the shared-room tiptoe (_auto_sneak_tick): a catcher standing
            # in that zone — the sleeper of Level109's bedroom — is passed
            # at the sneak speed too
            if not sneak:
                sneak = any(p.zone is not None and p.zone.pid == zone_pid
                            and not p.is_warping for p in self.catchers())
        if not sneak or w is None:
            return 2.0
        return max(0.2, (w.force or 0.8) * (w.speed_sneaking or 0.65))

    def _flee_target(self, here):
        """(zone, first door of the route, slack) — the parkable zone with
        a catcher-free route that keeps the most slack (_route_slack); the
        slack is None when no catcher touches the route within the horizon"""
        best = None
        # zones a catcher is walking to for his current action: he will
        # stand there for the whole use — no place to run to unless the
        # slack is generous (Level208: fleeing INTO the ShoeMachine room as
        # the neighbour comes for it)
        heading = set()
        for r in self.world.routines:
            # the item he walks to: an urgent detour's while one runs (the
            # loo rush — r.item then names the routine action he will
            # come back to, whose room is the one to run TO, Level106)
            tgt = r.urgent_item if r.urgent_item is not None else r.item
            if r.role in ('Rottweiler', 'Mother') and tgt is not None \
                    and r.state == r.MOVING and tgt.zone is not None:
                heading.add(tgt.zone)
        occ = self._occupied()
        for z in self.v.level.zones:
            if z.pid == here or not self.parkable(z) or z.pid in occ:
                continue
            path = self.find_path_avoiding(here, z.pid, occ)
            if not path:
                continue
            # not through the door pair a catcher is coming in by (a pawn
            # in transit holds both halves, IsOtherPawnPassing makes Woody
            # wait at it — standing there as the catcher steps out)
            first = path[0][1]
            pair = self.v.level.door_by_pid(first.link_to)
            if any(p.is_warping and getattr(p, '_exit_door', None) is not None
                   and p._exit_door in (first, pair)
                   for p in self.catchers()):
                continue
            slack = self._route_slack(here, path)
            if z.pid in heading and (slack is None or slack < 10.0):
                continue
            if slack is not None and slack < 0.0:
                # a route already lost (Level208: Zone02 -> Zone04 through
                # the ShoeMachine room the neighbour reaches first) — running
                # into it is worse than waiting for the next opening
                continue
            key = (60.0 if slack is None else slack, -len(path))
            if best is None or key > best[0]:
                # the click goes to the route's FIRST hop when the route is
                # not the shortest one: Woody's own FindPath (the runtime
                # BFS) would otherwise walk him through the room the
                # detour avoids (Level210: Zone01 -> Zone03 by Zone02, not
                # by the stairs the neighbour is coming down)
                bfs = self.v.level.find_path(here, z.pid) or []
                zone_click = z
                if [q for q, _d in bfs] != [q for q, _d in path]:
                    zone_click = self.v.level.zone_by_pid(path[0][0]) or z
                best = (key, zone_click, path[0][1], slack)
        if best is None:
            return None, None, None
        return best[1], best[2], best[3]

    def look_at(self, wx, wy):
        """scroll the free camera onto a world point before clicking it —
        what the player does with the 5 px edge scroll / arrows
        (CameraMover.UpdateWindowsInput, dead in headless mode). The
        Season-2 yards are ~14 units wide against the 8-unit view, so
        half the items sit off-screen from the entrance camera and a
        click on their projected point lands past the window or in the
        HUD strip (handle_click's 'hud-strip' swallow) — the clamp keeps
        the view inside the level bounds (CameraMover.cs:378-394)"""
        v = self.v
        if v.world.is_dexterity_on or v.world.camera_frozen or v.follow:
            return
        v.cam.x, v.cam.y = wx, wy
        v._clamp_camera()

    def _click(self, sx, sy):
        """Recorder._click with one guard: no click while Woody is on a
        walk-through transition (DonePassingToOtherZone latched,
        Pawn.cs:319-342). A re-click there feeds the Helpers.StepIndex /
        FirstStepIndex / DonePassingHelper statics a shape LinkNodes
        expands only for a few index deltas (Helpers.cs:253-335), and a
        Level203 trace showed a hop expanding to no steps at all: Woody
        walked from Zone02 to x=-3.7 in a straight line with his Zone
        unchanged, then climbed to a Zone03 item from below. A human lets
        him finish the stairs too. The guard lifts after 4 s so a latched
        flag can never freeze the driver."""
        w = self.v.woody
        if w is not None and getattr(w, 'done_passing', False) \
                and w.state != w.IDLE:
            t0 = getattr(self, '_passing_since', None)
            if t0 is None:
                self._passing_since = self.t
                return 'transit'
            if self.t - t0 < 4.0:
                return 'transit'
        else:
            self._passing_since = None
        r = Recorder._click(self, sx, sy)
        # the click log (clicks.json): every click the driver makes — the
        # item clicks and the dodges / stagings / detours alike, so a
        # replay on the original (tools/livediff/run.py --taps) walks
        # Woody the same way: the frame from play (the runner's clock,
        # the title cards skipped), the item when it was one, the
        # inventory in hand, the world point, the viewer's answer
        wx, wy = self.v.cam.screen_to_world(sx, sy, WIDTH, HEIGHT)
        inv = self.world.inventory
        cur = inv.used or inv.current
        self.clicks.append({'frame': int(round(self.t * 60)),
                            'item': getattr(self, '_click_item_name', None),
                            'type': cur['type'] if cur else None, 'result': r,
                            'kind': getattr(self, '_click_kind', 'leg'),
                            'world': [round(wx, 4), round(wy, 4)]})
        return r

    def _click_point_of(self, it):
        """the world point to click for `it`: its collider centre unless a
        nearer collider covers it there (Level112's SportsBag sits inside
        the back door's box; the raycast picks the door's nearer face,
        Viewer._hit_at) — then the first point of a grid over the item's
        own box that the raycast resolves to the item, the way a player
        taps the sliver of the bag that peeks out"""
        c = it.collider
        cx, cy = c[0], c[1]
        hit = getattr(self.v, '_hit_at', None)
        if hit is None or hit(cx, cy)[0] is it:
            return cx, cy
        n = 7
        for i in range(n):
            for j in range(n):
                wx = cx - c[2] * 0.5 + c[2] * (i + 0.5) / n
                wy = cy - c[3] * 0.5 + c[3] * (j + 0.5) / n
                if hit(wx, wy)[0] is it:
                    return wx, wy
        return cx, cy

    def click_item(self, it):
        if it.collider is None:
            return 'no-collider'
        wx, wy = self._click_point_of(it)
        self.look_at(wx, wy)
        sx, sy = self.v.cam.world_to_screen(wx, wy, WIDTH, HEIGHT)
        self.mouse[0], self.mouse[1] = sx, sy
        self._click_item_name = it.name    # for the click log (_click)
        r = self._click(sx, sy)
        self._click_item_name = None
        if os.environ.get('TRICKS_DEBUG'):
            w = self.v.woody
            print('t=%.2f click %s -> %s (woody %s x=%.2f %s%s)' % (
                self.t, it.name, r, self.zone_name(w.zone.pid) if w.zone
                else None, w.sprite.x, w.state,
                ' hiding' if w.hiding else ''))
        return r

    def free_floor_x(self, zone, x, y):
        """the floor x nearest to `x` in `zone` whose click hits no item
        or door collider — a floor click that lands on a hitbox becomes
        an item click (Level203's DieselGenerator box covers Zone03's
        centre: the walk turned into a climb-and-refuse), so scan
        outward in 0.3-unit steps inside the play range"""
        lo, hi = zone.play_left + 0.1, zone.play_right - 0.1
        cands = [x]
        for k in range(1, 40):
            cands.extend([x - 0.3 * k, x + 0.3 * k])
        for cx in cands:
            if cx < lo or cx > hi:
                continue
            it, door = self.v._hit_at(cx, y)
            if it is None and door is None:
                return cx
        return min(max(x, lo), hi)

    def click_zone(self, zone):
        x = (zone.play_left + zone.play_right) * 0.5
        y = zone.ty + zone.height_delta + 0.2
        x = self.free_floor_x(zone, x, y)
        self.look_at(x, y)
        sx, sy = self.v.cam.world_to_screen(x, y, WIDTH, HEIGHT)
        return self._click(sx, sy)

    def select_type(self, typ):
        """pick the inventory entry by its type (the digits in the viewer);
        '0'/None clears"""
        inv = self.world.inventory
        if typ in (None, '0'):
            inv.select(-1)
            return True
        idx = next((i for i, e in enumerate(inv.items)
                    if e['type'] == typ), None)
        if idx is None:
            return False
        inv.select(idx)
        return True

    # -- legs ---------------------------------------------------------------
    def _poke_danger(self):
        """the current leg's target is hot — hold the retry"""
        z = getattr(self, '_leg_zone', None)
        return z is not None and not self.gate_open(
            z, self._leg_x, getattr(self, '_leg_item', None))

    def _dex_tick(self):
        """drive an enabled dexterity minigame to the win: steer the pick
        (fg) onto the field (bg) — the fill rises while the two centres
        align (sway = 25 - the centre distance, DexterityComponent.cs:
        246-252); fg.x += input.x*dt and fg.y -= input.y*dt (cs:227).
        Returns True while a game is on."""
        on = False
        for ds in self.world.dex_states.values():
            if ds.enabled:
                on = True
                ddx = (ds.bg[0] + ds.bg[2] / 2.0) - (ds.fg[0] + ds.fg[2] / 2.0)
                ddy = (ds.bg[1] + ds.bg[3] / 2.0) - (ds.fg[1] + ds.fg[3] / 2.0)
                ds.input = (ddx * 30.0, -ddy * 30.0)
        return on

    def wait_until(self, pred, timeout, dodge=True, poke=None,
                   poke_every=3.0, fire=None):
        """dodge-loop until pred() or timeout; poke() re-fires the click
        when the walk was aborted by a flee — and at once after a won
        dexterity game (WinDexterity leaves DexterityDone up and the
        NEXT click passes the take/use, Item.cs:1462-1473); fire() going
        True pokes at once, gate or not — the item just became usable
        (Level105's football rolls in with the piano's AlertNext and the
        neighbour is already on his way to it)"""
        deadline = self.t + timeout
        next_poke = self.t + poke_every
        next_detour = self.t + 4.0
        fired = fire() if fire is not None else False
        while self.t < deadline:
            if pred():
                return True
            if poke is not None and self.t >= next_detour \
                    and getattr(self, '_leg_zone', None) is not None:
                # the leg's own walk was abandoned by a flee and the BFS
                # route back runs through a held room: walk round
                self._detour_toward(self._leg_zone, self._leg_x,
                                    getattr(self, '_leg_item', None))
                next_detour = self.t + 4.0
            if self.world.game.got_caught or self.world.game.ending:
                return False
            if dodge:
                self._dodge_tick()
            dexing = self._dex_tick()
            w = self.v.woody
            won = w is not None and w.dexterity_done and not dexing
            if fire is not None and not fired and fire():
                if w is not None and not w.hiding and not dexing \
                        and not w.input_locked:
                    # swallowed mid-stairs ('transit') or mid-climb
                    # ('climb', Woody.cs:657-667): the fire stays pending
                    if poke() not in ('transit', 'climb'):
                        fired = True
                        next_poke = self.t + poke_every
                # (input locked / hiding: the fire stays pending)
            wp = getattr(self, '_waypoint', None)
            if wp is not None and w is not None and w.zone is not None \
                    and w.zone.pid == wp[0] and w.state == w.IDLE \
                    and not w.input_locked and not w.anim.blocking:
                # the way-round waypoint reached: now the item itself
                self._waypoint = None
                wp[1]()
                next_poke = self.t + poke_every
            if poke is not None and (self.t >= next_poke or won):
                # a Woody parked in a wardrobe by the dodge comes out for
                # the poke once the leg's gate is open again (the click
                # is what un-hides him, Woody.StartMoveToLocation)
                if w is not None and self._woody_free(w) \
                        and (not w.hiding or not self._poke_danger()) \
                        and not dexing and (won or not self._poke_danger()):
                    poke()
                    next_poke = self.t + poke_every
                elif not won:
                    # a withheld poke (gate shut, Woody hidden or busy) is
                    # re-tried within a second: the clear windows of a
                    # tight routine are shorter than the poke cadence
                    # (Level108's bathroom stay opens Zone01 for 4 s)
                    next_poke = self.t + min(poke_every, 1.0)
            self.step_world()
        return pred()

    def _woody_free(self, w):
        """Woody stands idle — not mid-use: a use plays as a Single (or a
        sequence) on an IDLE pawn, and a re-click then restarts the use
        from scratch (Level102's 3x SawSofa was re-started by the 8 s poke)"""
        if w.state != w.IDLE:
            return False
        if w.hiding:
            return True                  # the click is what brings him out
        return w.anim.mode == 'looping' and not w.anim.seq

    def click_point(self, zone, x):
        """a floor click at x inside zone (Woody walks there)"""
        y = zone.ty + zone.height_delta + 0.2
        x = self.free_floor_x(zone, x, y)
        self.look_at(x, y)
        sx, sy = self.v.cam.world_to_screen(x, y, WIDTH, HEIGHT)
        return self._click(sx, sy)

    def _stage_toward(self, zone_pid):
        """while a leg's gate is shut, stand at the foot of the route's
        first door — the way a player waits at the stairs and goes up
        the moment the neighbour leaves; only inside a zone no catcher
        is about to enter, and only when idle"""
        w = self.v.woody
        if w is None or w.zone is None or w.zone.pid == zone_pid \
                or w.state != w.IDLE or w.hiding or w.input_locked:
            return
        path = self.v.level.find_path(w.zone.pid, zone_pid)
        if not path:
            return
        door = path[0][1]
        if door.zone != w.zone.pid or abs(door.x - w.sprite.x) < 1.0:
            return
        for p in self.catchers():
            eta = self.eta_to_zone(p, w.zone.pid, horizon=20.0)
            if eta is not None and eta < 8.0:
                return
        z = w.zone
        side = 1.0 if w.sprite.x > door.x else -1.0
        # past the door's own collider (a back door box is 0.8 wide) so
        # the floor click does not become a door click
        x = door.x + side * 0.75
        x = min(max(x, z.play_left + 0.1), z.play_right - 0.1)
        self.click_point(z, x)

    def wait_gate(self, zone_pid, x, item=None, timeout=GATE_TIMEOUT):
        """dodge-loop until the leg's gate opens, staging at the door
        meanwhile; a `!` leg (usewith! / take! ...) is the human's
        judgement call that he can make it — it skips the wait and clicks
        at once (Level108's toothbrush must be armed before the neighbour's
        first and only brushing, a race the margins of the ETA model
        would refuse)"""
        if getattr(self, '_rush', False):
            return True
        deadline = self.t + timeout
        next_stage = self.t
        next_detour = self.t + 4.0
        while self.t < deadline:
            if self.gate_open(zone_pid, x, item):
                return True
            if self.world.game.got_caught or self.world.game.ending:
                return False
            self._dodge_tick()
            if self.t >= next_stage:
                self._stage_toward(zone_pid)
                next_stage = self.t + 3.0
            if self.t >= next_detour:
                self._detour_toward(zone_pid, x, item)
                next_detour = self.t + 4.0
            self.step_world()
        return self.gate_open(zone_pid, x, item)

    def _detour_toward(self, zone_pid, x, item=None):
        """the S2 yards are a ring of four zones: FindPath's BFS route may
        run THROUGH the neighbour's room while the other way round is
        free (Level201: Zone01 -> Zone04 -> Zone03 to the deck rail while
        he stands in Zone04, with Zone01 -> Zone02 -> Zone03 open). A human
        walks round: when the target zone is clear but the BFS route is
        not, and a neighbouring zone off that route is safe and reaches
        the target without the held zones, walk there first"""
        w = self.v.woody
        if w is None or w.zone is None or w.zone.pid == zone_pid \
                or w.state != w.IDLE or w.hiding or w.input_locked:
            return
        here = w.zone.pid
        # only when the target itself is free for the whole job
        need = self.woody_need(zone_pid, x, item) + self.MARGIN
        for p in self.catchers():
            eta = self.eta_to_zone(p, zone_pid)
            if eta is not None and eta < need:
                return
        path = self.v.level.find_path(here, zone_pid) or []
        on_route = {zp for zp, _d in path}
        occ = self._occupied()
        if not any(zp in occ for zp in on_route):
            return                       # the plain route is not the problem
        for nz, door in self.v.level.graph.get(here, ()):
            if nz in on_route or nz == zone_pid or nz in occ:
                continue
            z = self.v.level.zone_by_pid(nz)
            if z is None or not self.parkable(z):
                continue
            rest = self.v.level.find_path(nz, zone_pid)
            if rest is None or any(zp in occ for zp, _d in rest):
                continue
            safe = True
            for p in self.catchers():
                eta = self.eta_to_zone(p, nz, horizon=30.0)
                if eta is not None and eta < self.woody_door_time(door) \
                        + abs(door.x - w.sprite.x) / 2.0 + self.MARGIN + 3.0:
                    safe = False
                    break
            if safe:
                self.click_zone(z)
                return

    def leg_take(self, name, typ):
        it = self.item(name)
        self._leg_zone = it.zone
        self._leg_x = it.target_x
        self._leg_item = it
        inv = self.world.inventory
        if any(e['type'] == typ for e in inv.items):
            return True, 'already held'
        self.select_type(None)
        ok = self.wait_gate(it.zone, it.target_x, it)
        if not ok:
            return False, 'zone never clear'
        def usable():
            return it.collider is not None and it.clickable and it.can_use
        # a source that is not clickable yet (Level210's OlgaBra: the
        # collider comes on with Olga's OlgaShowerPutBra, OlgaBraBehavior)
        # gets the click the moment it turns usable, not at the 8 s poke
        fire = None if usable() else usable
        self._click_via(it, lambda: self.click_item(it))
        got = self.wait_until(
            lambda: any(e['type'] == typ for e in inv.items),
            LEG_TIMEOUT, poke=lambda: self.click_item(it), fire=fire)
        return got, None if got else 'no %s after take' % typ

    def _use_leg(self, name, typ, pred_of, wait_prime=False):
        it = self.item(name)
        self._leg_zone = it.zone
        self._leg_x = it.target_x
        self._leg_item = it
        if wait_prime and it.require_priming and it.rott_toggles_prime \
                and not it.primed:
            # a neighbour-primed item refuses Woody until his prime visit
            # (Item.cs:1520-1535: RequirePriming && !Primed &&
            # RottweilerUseTogglesPrime -> the no); a human waits for that
            # visit where he stands (the bed he hid in, the room the plan
            # parked him in — the dodge keeps him safe) instead of standing
            # at the item through the lap — Level111's Iron/Airer,
            # Level114's Pipe/Gramaphone
            self._leg_zone = None
            self._leg_item = None
            ok = self.wait_until(lambda: it.primed, AWAIT_TIMEOUT)
            self._leg_zone = it.zone
            self._leg_item = it
            if not ok:
                return False, 'never primed by the neighbour'
        ok = self.wait_gate(it.zone, it.target_x, it)
        if not ok:
            return False, 'zone never clear'
        if typ is not None and not self.select_type(typ):
            return False, '%s not in inventory' % typ
        pred = pred_of(it)
        if typ is not None and pred():
            # a repeat use — Level201's second soap on the puddle after the
            # camera script turned UseOnce off (TutorialScriptCameraNFH2.cs:
            # 159): the trick flags still hold from the first use and the
            # leg would pass without the click; success is then the
            # inventory entry consumed (Item.cs' UseCount tail) or a fresh
            # Tricked
            inv = self.world.inventory
            sig = lambda: [(e['type'], e['use_count']) for e in inv.items if e['type'] == typ]
            before, tricked0 = sig(), it.tricked
            pred = lambda: sig() != before or (it.tricked and not tricked0)
        def poke():
            if typ is not None and not self.select_type(typ):
                return
            self.click_item(it)
        def usable():
            return it.collider is not None and it.clickable and it.can_use
        fire = None
        if not usable():
            # not clickable yet (CanUse false / collider off until an
            # alert enables it): the first click lands on the floor under
            # it and walks Woody there; fire the real click the moment it
            # turns usable
            fire = usable
        self._click_via(it, lambda: self.click_item(it))
        # an item that turns usable only on a game event (the Football's
        # collider comes with the routine's AlertNext ring once a lap,
        # TrickItem.cs:1154) is waited for on the await scale
        done = self.wait_until(pred, AWAIT_TIMEOUT if fire else LEG_TIMEOUT,
                               poke=poke, fire=fire)
        return done, None if done else 'predicate never held'

    def leg_use(self, name, typ=None):
        def pred_of(it):
            # the compound inventory on a Compound item lands as
            # CompoundTricked (TrickItem.CanWoodyUse cs:509-529, before the
            # base gates) — Level114's cork in the shotgun; the item may
            # already be Tricked by the shells, so the plain predicate
            # would pass before the click even walked Woody there
            if typ is not None and it.compound \
                    and typ == it.compound_required:
                return lambda: it.compound_tricked
            return lambda: it.tricked or it.got_tricked \
                or it.already_tricked or it.fucked_up
        return self._use_leg(name, typ, pred_of, wait_prime=True)

    def leg_prime(self, name, typ=None):
        """success = the clicked item primed, or the held inventory's
        SOURCE item primed — Item.cs:1537-1573: a held type whose source
        has RequirePriming primes on its designated PrimingItem (the
        Sandbucket on Level202's EelBox, the RiceBowl on Level204's
        GongGrease, the Glasses on Level205's LionStatue), the click
        target's own Primed flag never flips there"""
        def pred_of(it):
            # select_type stages the entry as CurrentInventory (the icon
            # click); the click that follows promotes it to Used. Current
            # first: a finished item path keeps the previous Used entry
            # (Level209's air pump after the coal's dexterity win), and
            # measuring that stale entry's source never sees the prime
            inv = self.world.inventory
            used = inv.current or inv.used or {}
            src = self.v.level.items.get(used.get('item')) \
                if used.get('item') is not None else None
            entry = used if used else None
            typ0 = used.get('type') if used else None
            def changed():
                # WoodyPrime's ChangeType (Item.cs:1246-1300 —
                # PrimedInventoryType turns the held rusty dagger into the
                # dagger, the crowbar into TNT) or its consumption
                # (RemoveInventoryAfterRequirePriming): the prime happened
                # even where no Primed flag survives (Level212's ClosedMine1
                # deactivates itself, Item.cs:1561-1566)
                if entry is None:
                    return False
                if entry not in inv.items:
                    return True
                if entry.get('type') != typ0:
                    return True
                # or the source's PrimedInventoryType landed as a new entry
                pit = getattr(src, 'primed_inventory_type', None) \
                    if src is not None else None
                return bool(pit and pit != 'IT_NONE' and pit != typ0
                            and inv.has(pit))
            if src is not None and getattr(src, 'require_priming', False):
                # a held type whose source needs priming (Level106's empty
                # bottle on the tub): the SOURCE primes; the click target
                # (the tub, primed by the neighbour already) is no measure
                return lambda: src.primed or changed()
            return lambda: it.primed or (src is not None and src.primed) \
                or changed()
        return self._use_leg(name, typ, pred_of)

    def leg_tutorial(self, index):
        """`tutorial N`: the App's own LevelScript (runtime/tutorial.py) —
        the level runs in the App now — completes its Actions[N]
        (LevelScriptAction.Complete, cs:110-160: DoorsToUnlock,
        ItemsToUnlock, UnfreezeNeighbor); the leg parks safe until
        LevelScript.ActionIndex has moved past N. `tutorial end`: the
        camera script reached its End state (TutorialScriptCameraNFH2's
        End1, cs:186-196). Before the runner ran the level in the App the
        driver applied the actions' effects itself and recorded a manual
        step; the plans keep the legs as the points the human sees the
        tutorial act."""
        tut = getattr(self.app, 'tutorial', None)
        cam = getattr(self.app, 'tutorial_camera', None)
        if index == 'end':
            if cam is None:
                return False, 'no tutorial camera script in the level'
            done = lambda: cam.state == 'End' or not cam.active
            what = 'the camera script\'s End'
        else:
            if tut is None:
                return False, 'no LevelScript in the level'
            i = int(index)
            done = lambda: tut.action_index > i or not tut.active
            what = 'LevelScript action %d' % i
        self._leg_zone = None
        self._leg_item = None
        self._leg_x = 0.0
        deadline = self.t + GATE_TIMEOUT
        while self.t < deadline:
            if done():
                return True, None
            if self.world.game.got_caught or self.world.game.ending:
                return False, 'caught before %s' % what
            self._dodge_tick()
            self.step_world()
        return False, '%s never completed' % what

    def leg_unlock(self, name, typ=None):
        """the dexterity gate: click with the unlocker held, then hold the
        pick center-ward each tick until DexterityDone passes the take;
        no Type (or IT_NONE) is the bare-handed game of a DexterityUnlocker
        IT_NONE item (Level203's OlgaBag, 204's ToyDispenser, 205's
        DuckCage, 206's DentureAdhesive)"""
        if typ == 'IT_NONE':
            typ = None
        it = self.item(name)
        self._leg_zone = it.zone
        self._leg_x = it.target_x
        self._leg_item = it
        ok = self.wait_until(lambda: self.gate_open(it.zone, it.target_x, it),
                             90.0)
        if not ok:
            return False, 'zone never clear'
        if typ is not None and not self.select_type(typ):
            return False, '%s not in inventory' % typ
        w = self.v.woody
        def poke():
            if typ is not None and not self.select_type(typ):
                return
            self.click_item(it)
        # 1. the arming click, then the steer (wait_until's _dex_tick)
        #    until WinDexterity raises DexterityDone (cs:369-372)
        self.click_item(it)
        won = self.wait_until(lambda: w.dexterity_done, LEG_TIMEOUT,
                              poke=poke)
        if not won:
            return False, 'minigame never won'
        # 2. the follow-up click that CanWoodyUse's done-pass lets through
        #    (Item.cs:1462-1473: DexterityDone cleared, Locked=false, the
        #    unlocker spent unless the keep flags) — wait_until pokes at
        #    once on `won`; success = the pass consumed
        def consumed():
            return not w.dexterity_done and not any(
                ds.enabled for ds in self.world.dex_states.values())
        ok = self.wait_until(consumed, LEG_TIMEOUT, poke=poke)
        if not ok:
            return False, 'done-pass never consumed'
        # 3. a dexterity SEARCH source (Level210's ToolBelt: Dexterity on a
        #    SearchItem, unlocker the fish net) hands its inventory over
        #    only when the take animation ends (SearchItem.OnFinish
        #    AnimationCompelted -> InternalUse, SearchItem.cs:114-119,
        #    156-212), ~1.4 s after the done-pass; the leg is done when the
        #    stock landed — no poke, a click would cancel the take
        first = it.inventory_items[0].get('type') \
            if it.kind == 'SearchItem' and it.inventory_items else None
        if first is not None:
            inv = self.world.inventory
            ok = self.wait_until(lambda: inv.has(first) or not it.inventory_items,
                                 LEG_TIMEOUT)
            return ok, None if ok else 'no %s after the take' % first
        return True, None

    def leg_await(self, name, score=None):
        """park safe until THIS item's trick pays (step_world attributes
        the TrickDone entries per item, so a trick that already paid while
        an earlier leg ran passes at once and the routine order need not
        be guessed); assert the paid score when given"""
        # `await <N>` (a bare number): wait for GameInfo.CompletedTricksCount
        # to reach N — for a TrickDone that no item's AlreadyTricked
        # explains (Level211's Toilet211Behavior extra coin, Item.cs:2373-2384
        # calls GameInfo.TrickDone straight)
        count = int(name) if name.isdigit() else None
        it = None if count is not None else self.item(name)
        self._leg_zone = None
        self._leg_item = None
        self._leg_x = 0.0
        game = self.world.game
        def paid_now():
            return game.completed >= count if count is not None \
                else it.pid in self.paid
        if not paid_now():
            safe = self.safe_zone()
            poke = None
            hide_spot = self._hide_spot() \
                if safe is not None and safe.pid in (
                    self.routine_zones() | self.corridor_zones()) \
                else None
            # a Woody already tucked into a bed/wardrobe (a `hide` leg)
            # stays there: the hiding spot is the parking spot, and the
            # walk out would only expose him
            if hide_spot is not None and not self.v.woody.hiding:
                # every zone is on some routine (Level208: the hub Zone05
                # is a corridor, the Mother owns Zone02): the wardrobe /
                # basket is the human's parking spot — Woody.Hiding gates
                # both catch predicates (GameInfo.cs:189/198)
                self._leg_zone, self._leg_x = hide_spot.zone, hide_spot.target_x
                self._leg_item = hide_spot
                def poke():
                    w = self.v.woody
                    if w.hiding:
                        return
                    if self.gate_open(hide_spot.zone, hide_spot.target_x,
                                      hide_spot):
                        self.select_type(None)
                        self.click_item(hide_spot)
                        return
                    # the wardrobe is not reachable yet: do not idle in a
                    # room somebody is walking to — stage in the zone the
                    # catchers reach last (a human keeps moving away)
                    here = w.zone.pid if w.zone is not None else None
                    if here is None or w.state != w.IDLE:
                        return
                    soonest = None
                    for p in self.catchers():
                        eta = self.eta_to_zone(p, here, horizon=25.0)
                        if eta is not None and (soonest is None
                                                or eta < soonest):
                            soonest = eta
                    if soonest is None:
                        return
                    target, _door, _slack = self._flee_target(here)
                    if target is not None and target.pid != here:
                        self.click_zone(target)
                poke()
                self._rush = False
            elif safe is not None and not self.v.woody.hiding:
                # the walk to the parking spot is a leg like any other:
                # it starts (and re-fires) only while its route is clear
                sx = (safe.play_left + safe.play_right) * 0.5
                self._leg_zone, self._leg_x = safe.pid, sx
                first = [True]
                spot = [safe, sx]
                def poke():
                    w = self.v.woody
                    # `await!`: the first parking click goes out at once
                    # (the human running out of the room he just tricked
                    # as the neighbour walks in through the same door)
                    rush = first[0] and getattr(self, '_rush', False)
                    first[0] = False
                    # the parking spot is re-chosen at every poke: on the
                    # S2 yards every room is on some routine, and the room
                    # the catchers reach LAST changes as they walk (Level214:
                    # Zone04 is fine while he showers, a trap once he heads
                    # for the bouquet with the Mother holding the only
                    # other exit)
                    if not rush:
                        z2 = self.safe_zone()
                        if z2 is not None and z2.pid != spot[0].pid:
                            spot[0] = z2
                            spot[1] = (z2.play_left + z2.play_right) * 0.5
                            self._leg_zone, self._leg_x = z2.pid, spot[1]
                    safe2, sx2 = spot
                    if w.zone is not None and w.zone.pid != safe2.pid \
                            and (rush or self.gate_open(safe2.pid, sx2)):
                        self.click_zone(safe2)
                poke()
                self._rush = False
            ok = self.wait_until(paid_now, AWAIT_TIMEOUT,
                                 poke=poke, poke_every=4.0)
            if not ok:
                return False, 'trick never paid' if count is None \
                    else 'count never reached (%d/%d)' % (game.completed, count)
        if count is None and score is not None \
                and self.paid[it.pid] != int(score):
            return False, 'paid %s, expected %s' % (self.paid[it.pid], score)
        return True, None

    def leg_reclick(self, name):
        it = self.item(name)
        game = self.world.game
        before = (game.completed, len(self.world.inventory.items),
                  it.tricked, it.primed)
        self.click_item(it)
        self.run_seconds(3.0)
        after = (game.completed, len(self.world.inventory.items),
                 it.tricked, it.primed)
        ok = before == after
        return ok, None if ok else 'state changed: %s -> %s' % (before,
                                                                after)

    def leg_activated(self, name):
        """`activated <Item>`: park safe until the item's GameObject is
        active — an item that ships inactive and a game event activates
        (SetActive(true)): Level206's Rabbit on the LaunchPad's Fix
        (Item.cs:2626-2631), Level212's coins on the bull's ShowObjects
        (cs:2662-2667), Level214's dead bird two seconds after the shot
        (BirdMovementBehavior.cs:149-156). A take before that clicks air."""
        it = self.item(name)
        self._leg_zone = None
        self._leg_item = None
        self._leg_x = 0.0
        deadline = self.t + AWAIT_TIMEOUT
        while self.t < deadline:
            if it.active:
                return True, None
            if self.world.game.got_caught or self.world.game.ending:
                return False, 'caught before %s activated' % name
            self._dodge_tick()
            self.step_world()
        return False, '%s never activated' % name

    def leg_walk(self, x, y):
        """`walk <x> <y>`: click the world point and wait for Woody to
        stand there — a tutorial's location action (LevelScriptAction's
        Location / Threshold, Woody.IsAtLocation on x alone, cs:293-296:
        Level201's action 1 wants him at x=5.0 before the neighbour
        unfreezes)"""
        x, y = float(x), float(y)
        w = self.v.woody
        if w is None:
            return False, 'no Woody'
        self._leg_zone = None
        self._leg_item = None
        self._leg_x = x
        deadline = self.t + 60.0
        next_click = self.t
        while self.t < deadline:
            # the tutorial's own threshold is 0.5 (LevelScriptAction's
            # Threshold); Woody stops a little short of the click point
            if abs(w.sprite.x - x) < 0.25 and w.state == w.IDLE:
                return True, None
            if self.world.game.got_caught or self.world.game.ending:
                return False, 'caught on the walk'
            if self.t >= next_click:
                self.look_at(x, y)
                sx, sy = self.v.cam.world_to_screen(x, y, WIDTH, HEIGHT)
                self.mouse[0], self.mouse[1] = sx, sy
                self._click(sx, sy)
                next_click = self.t + 3.0
            self.step_world()
        return False, 'never arrived at x=%.2f (at %.2f)' % (x, w.sprite.x)

    def leg_park(self, arg):
        if arg == 'auto':
            z = self.safe_zone()
        else:
            z = next((z for z in self.v.level.zones if z.name == arg), None)
        if z is None:
            return False, 'no such zone'
        w = self.v.woody
        cx = (z.play_left + z.play_right) * 0.5
        # a named zone is entered like any target: when its gate is open
        # (a walk into the neighbour's room is not a park), re-clicked
        # after a flee
        self._leg_zone = z.pid
        self._leg_x = cx
        self._leg_item = None
        if not self.wait_gate(z.pid, cx, None):
            return False, 'zone never clear'
        self.click_zone(z)
        ok = self.wait_until(
            lambda: w.zone is not None and w.zone.pid == z.pid, 60.0,
            poke=lambda: self.click_zone(z))
        return ok, None if ok else 'never arrived'

    def leg_icon(self, typ):
        """click the held Type's inventory icon in the HUD strip —
        HUD.CheckClick consults the source item's OnIconPressed
        (HUD.cs:944, Item.cs:2176-2199): a CauseAlarm item (Level105's
        mobile) stops Woody, plays its DirectUse and raises the alarm on
        its AlarmItem after ActionDuration; success = the alarm clock
        moved (or the entry became Current for a plain item)"""
        inv = self.world.inventory
        idx = next((i for i, e in enumerate(inv.items) if e['type'] == typ),
                   None)
        if idx is None:
            return False, '%s not in inventory' % typ
        hud = self.v.hud
        if hud is None:
            return False, 'no HUD'
        w = self.v.woody
        # a real player presses the icon standing still, out of a door
        self.wait_until(lambda: w.state == w.IDLE and not w.is_warping
                        and not w.input_locked and not w.anim.blocking, 20.0)
        rects = hud._inventory_rects()
        k = idx - hud.displayed_begin
        if not (0 <= k < len(rects)):
            return False, 'icon not on the strip'
        r = rects[k]
        entry = inv.items[idx]
        src = self.v.level.items.get(entry.get('item')) \
            if entry.get('item') else None
        before = getattr(src, 'last_alarm_time', None) if src else None
        self.mouse[0], self.mouse[1] = r[0] + r[2] / 2.0, r[1] + r[3] / 2.0
        self._click(self.mouse[0], self.mouse[1])
        self.run_seconds(1.0)
        moved = src is not None and \
            getattr(src, 'last_alarm_time', None) != before
        ok = moved or inv.current is entry
        return ok, None if ok else 'icon click had no effect'

    def leg_hide(self, name):
        """climb into a HideItem (the bed / wardrobe) and stay there:
        Woody.Hide keeps him out of both catch predicates until the next
        click un-hides him (Woody.cs Hide/Unhide, GameInfo.cs:189/198) —
        the human's way to let the neighbour walk through a room that
        has no other way out (Level107's balcony behind the bedroom)"""
        it = self.item(name)
        self._leg_zone = it.zone
        self._leg_x = it.target_x
        self._leg_item = it
        w = self.v.woody
        ok = self.wait_gate(it.zone, it.target_x, it)
        if not ok:
            return False, 'zone never clear'
        self.select_type(None)
        self.click_item(it)
        ok = self.wait_until(lambda: w.hiding, LEG_TIMEOUT,
                             poke=lambda: self.click_item(it))
        return ok, None if ok else 'never hidden'

    # -- the run ------------------------------------------------------------
    def _enter_level(self):
        """the App's load, the title cards skipped: the clock then runs
        from play, as the original's StartGame"""
        self.app.load_level(self.level_name)
        self.app.tick(DT, events=(False, True, False, False))
        self.v = self.app.viewer
        self.v.virtual_mouse = self.mouse

    def tick(self, t):
        """Recorder.tick on the App: its level frame is the world tick,
        the tutorial layer, the stored-click replay, the camera, the draw"""
        v = self.v
        if self.tour:
            self._tour_tick()
        self._mouse_tick()
        v._frame_dt = DT
        if not self.paused and not v.world.menu_open:
            v.t += DT
            self.app.tick(DT, events=(False, False, False, False))
        for hook in self.frame_hooks:
            hook(t, DT)
        # the state line every STATE_EVERY ticks: a plan run is minutes of
        # 60 Hz rows, and a stuck one grew a 190 MB log on /tmp
        self._tick_i += 1
        if self._tick_i % STATE_EVERY == 0:
            self.log.write(json.dumps(self._state(t)) + '\n')

    def restart(self):
        self._enter_level()
        self.restarts += 1
        self.t = 0.0
        self.clicks = []                  # the click log is the last attempt's
        self.paid = {}
        self._alerter_zones = None
        # the flee throttle is a clock stamp: left over from the previous
        # attempt it reads as "fled a moment ago" for the whole new run
        # (t restarts at 0) and the dodge never fires again — every retry
        # then dies at the same spot the first one survived
        self._flee_at = None
        self._apply_collider_enabled()
        self._install_anim_probes()

    def apply_prelude(self):
        """plan directives that must act before the entrance walk-in:
        `entrance skip` — start Woody at his StartLocation with the
        entrance already finished (FinishedEntrance/InputLocked,
        Woody.cs:190-191, 304-312), recorded as a manual step. It was
        written for Level210, whose port walk-in ended in a catch at
        t=3.15; the walk-in itself was the port's error — every Season-2
        Woody serializes FinishedEntrance=true, so the original never
        starts the entrance walk (Woody.cs:191, 223-231; docs/audit/
        verified/s2_plans.md) — and no plan needs the directive now."""
        for leg in self.legs:
            if leg[:2] == ['entrance', 'skip']:
                w = self.v.woody
                self.world._entrance_timer = None
                w.input_locked = False
                w.finished_entrance = True
                self._entrance_skipped = True
                return True
        return False

    def run_plan(self):
        i = 0
        while i < len(self.legs):
            leg = self.legs[i]
            op, args = leg[0], leg[1:]
            # `op!` — rush: skip the gate wait, click at once (wait_gate)
            self._rush = op.endswith('!')
            if self._rush:
                op = op[:-1]
            # a trailing `+N` — the gate must hold N more seconds beyond
            # this leg: the human sizing up a whole raid into a dead-end
            # room (the legs after this one and the way back) before the
            # first step of it
            self._extra_need = 0.0
            if args and args[-1].startswith('+') \
                    and args[-1][1:].replace('.', '', 1).isdigit():
                self._extra_need = float(args[-1][1:])
                args = args[:-1]
            g = self.world.game
            if g.ending and g.caught_by is None and (g.won or g.all_done()):
                # the win, not a catch: WinGameOnCompleteAllTricks froze
                # the world (GameInfo.cs:226-231, 304-313) — a plan that
                # scores every trick ends here; the awaits still read the
                # paid table, anything else is moot
                if op == 'await':
                    ok, why = self.leg_await(*args)
                    self.results.append({'leg': ' '.join(leg), 'ok': ok,
                                         'why': why, 't': round(self.t, 1),
                                         'restarts': self.restarts})
                else:
                    self.results.append({'leg': ' '.join(leg), 'ok': None,
                                         'why': 'level won before this leg'})
                i += 1
                continue
            if g.got_caught or g.ending:
                if self.restarts >= MAX_RESTARTS:
                    self.results.append({'leg': ' '.join(leg),
                                         'ok': False,
                                         'why': 'caught, out of restarts'})
                    break
                self.restart()
                self.apply_prelude()
                self.run_entrance()                  # the entrance
                i = 0
                self.results = []
                continue
            if op == 'entrance':
                self.results.append({'leg': ' '.join(leg), 'ok': None,
                                     'why': 'entrance walk-in skipped by the '
                                     'driver (manual step, finding)'})
                i += 1
                continue
            if op == 'manual':
                self.results.append({'leg': ' '.join(leg), 'ok': None,
                                     'why': 'manual step (finding)'})
                i += 1
                continue
            if op == 'wait':
                self.run_seconds(float(args[0]))
                i += 1
                continue
            if op == 'sneak':
                w = self.v.woody
                self.sneak_manual = args[0] != 'auto'
                if self.sneak_manual:
                    w.sneak_toggle = args[0] == 'on'
                    w.sneaking = w.sneak_toggle
                i += 1
                continue
            fn = {'take': self.leg_take, 'use': self.leg_use,
                  'usewith': self.leg_use, 'prime': self.leg_prime,
                  'unlock': self.leg_unlock, 'await': self.leg_await,
                  'reclick': self.leg_reclick, 'park': self.leg_park,
                  'hide': self.leg_hide, 'icon': self.leg_icon,
                  'tutorial': self.leg_tutorial,
                  'walk': self.leg_walk,
                  'activated': self.leg_activated}.get(op)
            if fn is None:
                self.results.append({'leg': ' '.join(leg), 'ok': False,
                                     'why': 'unknown op'})
                i += 1
                continue
            ok, why = fn(*args)
            self.results.append({'leg': ' '.join(leg), 'ok': ok,
                                 'why': why, 't': round(self.t, 1),
                                 'restarts': self.restarts})
            if os.environ.get('TRICKS_VERBOSE'):
                # the live leg log (attempt, time, result) — the trace of
                # a run that restarts keeps only the last attempt's results
                print('  [%d] t=%6.1f %s %-38s %s' % (
                    self.restarts, self.t,
                    {True: 'ok  ', False: 'FAIL', None: 'MAN '}[ok],
                    ' '.join(leg), why or ''), flush=True)
            i += 1
        self.log.close()
        return self.results


def run_one(plan, outroot):
    name = os.path.splitext(os.path.basename(plan))[0]
    season = os.path.basename(os.path.dirname(plan))
    level = os.path.join(ROOT, 'levels', season, name + '.json')
    outdir = os.path.join(outroot, '%s_%s' % (season, name))
    os.makedirs(outdir, exist_ok=True)
    import subprocess
    r = subprocess.run([sys.executable, os.path.abspath(__file__), plan,
                        '--out=' + outroot, '--child'],
                       env=dict(os.environ, SDL_VIDEODRIVER='offscreen'),
                       capture_output=True, text=True)
    res = os.path.join(outdir, 'results.json')
    data = json.load(open(res)) if os.path.exists(res) else None
    return plan, data, r.returncode, (r.stdout + r.stderr)[-1500:]


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: (a.split('=', 1)[1] if '=' in a else '1')
            for a in argv[1:] if a.startswith('--')}
    outroot = opts.get('out', '/tmp/nfh-tricks')
    if 'all' in opts:
        args = sorted(glob.glob(os.path.join(ROOT, 'tests', 'plans', 's*',
                                             'Level*.txt')))
    if not args:
        print(__doc__)
        return 2
    if 'child' in opts or len(args) == 1:
        plan = args[0]
        name = os.path.splitext(os.path.basename(plan))[0]
        season = os.path.basename(os.path.dirname(plan))
        level = os.path.join(ROOT, 'levels', season, name + '.json')
        outdir = os.path.join(outroot, '%s_%s' % (season, name))
        d = Driver(level, plan, outdir)
        d.apply_prelude()
        d.run_entrance()                     # the entrance walk-in / greeting
        results = d.run_plan()
        json.dump(results, open(os.path.join(outdir, 'results.json'), 'w'),
                  indent=1)
        json.dump(d.clicks, open(os.path.join(outdir, 'clicks.json'), 'w'),
                  indent=1)
        vio = d.inv.finish()
        json.dump(vio, open(os.path.join(outdir, 'invariants.json'), 'w'),
                  indent=1)
        for x in vio:
            print('INV %-14s %-28s %s' % (x['kind'], x['subject'],
                                          x['detail']))
        bad = [r for r in results if r['ok'] is False]
        for r in results:
            mark = {True: 'ok  ', False: 'FAIL', None: 'MAN '}[r['ok']]
            print('%s %-40s %s' % (mark, r['leg'], r.get('why') or ''))
        print('%s: %d legs, %d failed, %d restarts'
              % (name, len(results), len(bad), d.restarts))
        return 1 if bad else 0
    from concurrent.futures import ThreadPoolExecutor
    total_bad = 0
    with ThreadPoolExecutor(max_workers=int(opts.get('jobs', 4))) as ex:
        for plan, data, code, tail in ex.map(
                lambda p: run_one(p, outroot), args):
            name = os.path.basename(plan)
            if data is None:
                print('%-18s CRASH\n%s' % (name, tail))
                total_bad += 1
                continue
            bad = [r for r in data if r['ok'] is False]
            man = [r for r in data if r['ok'] is None]
            total_bad += len(bad)
            base = os.path.splitext(name)[0]
            season = os.path.basename(os.path.dirname(plan))
            ipath = os.path.join(outroot, '%s_%s' % (season, base),
                                 'invariants.json')
            vio = json.load(open(ipath)) if os.path.exists(ipath) else []
            print('%-18s %d legs, %d failed, %d manual, %d invariant'
                  % (name, len(data), len(bad), len(man), len(vio)))
            for r in bad:
                print('    FAIL %-36s %s' % (r['leg'], r.get('why') or ''))
            for x in vio:
                print('    INV  %-14s %-22s %s'
                      % (x['kind'], x['subject'], x['detail']))
    return 1 if total_bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
