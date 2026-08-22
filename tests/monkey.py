"""The input monkey with invariants (pass 2 of docs/FINAL_AUDIT_PROMPT.md).

Layered over runtime/record.py's Recorder: the same fixed 60 Hz player loop,
but the input source is a seeded RNG that aims clicks, hovers and HUD
presses at the *transition windows* — door transits, climbs, wardrobe
exits, FearShort, single-shot uses, the catch frame, dexterity, the pause,
the score screen, the first second — instead of the calm gaps between
them.  Two clicks can land in one tick.  After every tick a set of
invariants runs over the live world; each violation is a finding, written
to findings.jsonl and summarized on exit.

    python3 tests/monkey.py --all --seeds=1,2 --seconds=180 --out=/tmp/monkey
    python3 tests/monkey.py levels/s1/Level101.json --seeds=7 --seconds=60

Determinism: a fixed 60 Hz clock (record.DT), one random.Random(seed) for
every decision, and the virtual mouse as the only input path — a finding
reproduces from (level, seed) alone on the same build.
"""
import json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))

from record import Recorder, DT, WIDTH, HEIGHT     # noqa: E402


# ---------------------------------------------------------------------------
# invariants

class Tracker:
    """per-flag hold timers: how long a predicate has been continuously
    true, so 'stuck' has a number attached"""

    def __init__(self):
        self.since = {}

    def hold(self, key, active, t):
        if not active:
            self.since.pop(key, None)
            return 0.0
        if key not in self.since:
            self.since[key] = t
        return t - self.since[key]


class Invariants:
    """the assert set from the audit prompt; every threshold carries the
    reasoning next to it.  A violation does not stop the run — it is
    recorded once per (invariant, subject) with the first hit's state."""

    def __init__(self, level_name, seed):
        self.level = level_name
        self.seed = seed
        self.track = Tracker()
        self.findings = []
        self.seen = set()
        self.prev_time = None
        self.prev_world = None
        self.sleep_started = set()       # pawns whose is_sleeping rose at runtime
        self.game_t = 0.0                # world time: pauses freeze every
                                         # hold timer, as timeScale=0 freezes
                                         # the original's Update clocks
        self.spawn = {}                  # each pawn's load position
        self.info = {}                   # informational counters (not findings)

    def emit(self, t, inv, subject, detail, state=None):
        key = (inv, subject)
        if key in self.seen:
            return
        self.seen.add(key)
        self.findings.append({'level': self.level, 'seed': self.seed,
                              't': round(t, 2), 'invariant': inv,
                              'subject': subject, 'detail': detail,
                              'state': state or {}})

    # -- the per-tick sweep -------------------------------------------------
    def check(self, v, wall_t, paused):
        w = v.world
        if w is not self.prev_world:
            # the score-screen Restart reloaded the level: fresh trackers
            self.track = Tracker()
            self.prev_time = None
            self.sleep_started = set()
            self.prev_world = w
            self.game_t = 0.0
            self.spawn = {}
        ticked = not paused and not w.menu_open
        if ticked:
            self.game_t += DT
        t = self.game_t
        woody = v.woody
        game = w.game

        # INV1 — transits: is_warping implies a hidden sprite, and for
        # Woody a locked input (PlayDoorLeaveAnimation hides the pawn and
        # sets InputLocked, Pawn.cs:1615-1635 + Woody.cs:459-463); a door
        # claim (Door.passing / IsOtherPawnPassing) must point at a pawn
        # actually mid-transit — a stale claim is a leaked transit.
        for role, p in w.pawns.items():
            if p.is_warping:
                if not p.sprite.hidden:
                    self.emit(t, 'warp-visible', role,
                              'is_warping but sprite not hidden',
                              self._pawn(p))
                if role == 'Woody' and not p.input_locked:
                    self.emit(t, 'warp-input-open', role,
                              'is_warping but input not locked',
                              self._pawn(p))
        transit_states = ('door_anim', 'door_climb', 'descend')
        # at most one active transit per pawn: a pass claims exactly the
        # linked pair (door.passing = other.passing = self,
        # Pawn.PlayDoorLeaveAnimation/PlayDoorEnterAnimation); a third
        # claim, or two unlinked doors, is a second transit started over
        # a live one
        claims = {}
        for d in v.level.doors:
            p = getattr(d, 'passing', None)
            if p is not None:
                claims.setdefault(id(p), (p, []))[1].append(d)
        for p, ds in claims.values():
            if len(ds) > 2 or (len(ds) == 2 and ds[0].link_to != ds[1].pid
                                and ds[1].link_to != ds[0].pid):
                self.emit(t, 'double-transit', p.role,
                          'claims %s' % [d.name for d in ds], self._pawn(p))
        for d in v.level.doors:
            p = getattr(d, 'passing', None)
            if p is None:
                continue
            if not (p.is_warping or p.state in transit_states):
                held = self.track.hold(('claim', d.name), True, t)
                if held > 1.0:      # ExitAnimation keeps the far door busy
                                    # a moment after the warp; a second is
                                    # generous for a 2-4 s pass
                    self.emit(t, 'stale-door-claim', d.name,
                              'door claimed by %s in state %s for %.1fs'
                              % (p.role, p.state, held), self._pawn(p))
            else:
                self.track.hold(('claim', d.name), False, t)

        # INV2 — stuck flags.  Rule of thumb: each flag lists the states
        # that legitimately hold it; outside them it must drop within the
        # grace below, else it is the InputLocked class of bug.
        if woody is not None:
            legit = (not woody.finished_entrance or woody.is_warping
                     or woody.anim.blocking or game.ending or game.got_caught
                     or woody.in_dexterity or w.menu_open
                     or woody.state in transit_states)
            held = self.track.hold('input_locked',
                                   woody.input_locked and not legit, t)
            # a BlockWhenItemPick item locks the input for its whole
            # pick → search → take chain, none of it Blocking, until
            # InternalUse's tail (Woody.cs:534-538, Item.cs:1943-1947):
            # ~1.5 s on a search item, 6 s is a generous ceiling
            ia = woody.item_aux
            grace = 6.0 if (ia is not None
                            and getattr(ia, 'block_when_item_pick', False)) \
                else 1.0
            if held > grace:
                self.emit(t, 'stuck-input-locked', 'Woody',
                          'input_locked %.1fs with no blocker' % held,
                          self._pawn(woody))

            held = self.track.hold(
                'movement_paused',
                woody.movement_paused and not woody.anim.blocking
                and not game.ending and not game.got_caught
                and not woody.in_dexterity and not w.is_dexterity_on
                and not woody.frozen, t)
            if held > 5.0:      # PauseMovement pairs with a blocking fear /
                                # startled look (5 s outlives any of them);
                                # Woody.Freeze (the dexterity minigame, the
                                # finish) holds it for as long as it lasts
                self.emit(t, 'stuck-movement-paused', 'Woody',
                          'movement_paused %.1fs with no blocking anim'
                          % held, self._pawn(woody))

            held = self.track.hold(
                'hiding',
                woody.hiding and woody.hiding_item is None
                and not woody.is_warping and not game.got_caught
                and not game.ending, t)
            if held > 2.0:
                self.emit(t, 'stuck-hiding', 'Woody',
                          'Hiding %.1fs with no hiding item/transit/beating'
                          % held, self._pawn(woody))

            held = self.track.hold(
                'frozen', woody.frozen and not w.is_dexterity_on
                and not game.ending, t)
            if held > 10.0:
                self.emit(t, 'stuck-frozen', 'Woody',
                          'Woody.Frozen %.1fs outside dexterity' % held,
                          self._pawn(woody))

            # a hidden Woody outside the transit / wardrobe / beating set
            if (woody.sprite.hidden and not woody.hiding
                    and not woody.is_warping and not game.got_caught
                    and not game.ending):
                self.emit(t, 'sprite-hidden', 'Woody',
                          'sprite hidden outside transit/hiding/beating',
                          self._pawn(woody))

        for role, p in w.pawns.items():
            if role == 'Woody' or p.sprite is None:
                continue
            # non-Woody pawns hide only through set_hidden (transit, the
            # mutex park, HideOwnerDuringUse, the hit choreography) —
            # Pawn.cs:1464-1467; sprite.hidden without pawn.hidden is a
            # renderer-level leak
            if p.sprite.hidden and not p.hidden and not p.is_warping:
                held = self.track.hold(('ghost', role), True, t)
                if held > 1.0:   # grace: hide_owner_on_end anims (Hide_In,
                                 # BedIn...) hide the sprite directly and
                                 # the owner unhides on the next play
                    self.emit(t, 'sprite-hidden', role,
                              'sprite hidden %.1fs without set_hidden'
                              % held, self._pawn(p))
            else:
                self.track.hold(('ghost', role), False, t)

        # the colored (latched) tooltip lives for the span of a route: every
        # world tap latches it (HUD.CheckClick -> UpdateTooltip ->
        # MakePermanentTooltip, HUD.cs:1319-1327) and it clears when the
        # walk ends (Woody.OnPathFinished, Woody.cs:361-362) or the item
        # use runs its tail (Item.UseItem, Item.cs:1916) — so a latch held
        # while Woody stands idle with nothing pending is stale
        # ...except after an item click: a silent refusal (no NoNo, only the
        # description bubble) never sets UseCompleted (Woody.cs:443 rides
        # OnSingleAnimationEnded), the item step stays open and no
        # OnPathFinished runs — the latch legitimately survives until the
        # next click (ItemAux marks the last click as an item click)
        if v.hud is not None and woody is not None:
            idle = (woody.state == woody.IDLE and not woody.steps
                    and woody.on_arrive is None and not woody.anim.blocking
                    and not woody.is_warping and not woody.in_dexterity
                    and woody.stored_input is None and not game.ending
                    and woody.item_aux is None)
            # ...and the HUD latches BEFORE Woody's gates see the click
            # (HUD.CheckClick runs first, Woody.cs:631-641), so a click the
            # climb gate swallows or an item refusal leaves the latch on a
            # standing Woody in the original too — from the outside a
            # legitimate latch and a stale one are the same picture. The
            # latch contract itself (HUD.cs:1319-1327, Woody.cs:361-362 and
            # 736-741, Item.cs:1916) is guarded by tests/checks; this
            # invariant only reports the count as information
            active = v.hud.colored_tooltip and idle
            if self.track.hold('colored', active, t) > 1.0:
                self.info.setdefault('colored-latch-on-idle', 0)
                self.info['colored-latch-on-idle'] += 1
                self.track.hold('colored', False, t)

        # a runtime sleep must come with its progress bar; the bar gone
        # and the pawn still IsSleeping >10 s = a stuck detection gate
        bars = getattr(w, 'progress_bars', ())
        sleeping_bar_pawns = {pb.spec.get('actor') for pb in bars
                              if pb.visible}
        for role, p in w.pawns.items():
            if p.is_sleeping and role not in self.sleep_started:
                # serialized is_sleeping (a pawn that starts asleep) stays
                # exempt until a bar ever showed for it
                if role in sleeping_bar_pawns:
                    self.sleep_started.add(role)
            active = (role in self.sleep_started and p.is_sleeping
                      and role not in sleeping_bar_pawns)
            if self.track.hold(('sleep', role), active, t) > 10.0:
                self.emit(t, 'stuck-sleeping', role,
                          'IsSleeping >10s with its progress bar gone',
                          self._pawn(p))

        # INV6 — a stored click must replay the moment the block lifts
        # (the replay runs inside the same tick; two ticks of margin)
        if woody is not None:
            blocked = (woody.input_locked or woody.anim.blocking
                       or woody.is_warping or game.ending)
            lingering = woody.stored_input is not None and not blocked
            if self.track.hold('stored', lingering, t) > 3 * DT:
                self.emit(t, 'stored-input-lingers', 'Woody',
                          'stored_input kept while nothing blocks',
                          self._pawn(woody))

        # INV4 — routine progress, minus the documented eternal parks (the
        # mutex handshake, InfiniteLoop waiting poses, HoldOnLastFrame, a
        # Frozen manager — L112's skates ride that; and duration-timed
        # actions while their timer still runs).
        #   moving: the pawn's position must actually change — a walker
        #   pinned in place is the oscillation/pathing class of bug;
        #   using: the use sequence must drain — a 'using' pawn parked on
        #   a plain looping animation with no sequence pending (AnimPlayer
        #   .waiting) never finishes its RoutineActionUse.
        for r in w.routines:
            p = r.pawn
            key = ('routine', r.role)
            a = r.action or {}
            parked = (r.frozen or a.get('mutex')
                      or p.anim.anim.infinite or p.anim.anim.hold
                      or r.timer > 0.0)
            if r.state == r.MOVING and not game.ending:
                sig = (round(p.sprite.x, 3), round(p.sprite.y, 3))
                prev = getattr(r, '_monkey_sig', None)
                r._monkey_sig = sig
                stalled = sig == prev and not p.is_warping \
                    and not p.movement_paused
                # a pawn standing at an occupied door / claimed
                # transition legitimately waits (Pawn.MoveToDoor's
                # IsOtherPawnPassing, Pawn.cs:996-1030) — those show a
                # Stand_* pose, so only a frozen *walk* counts
                stalled = stalled and p.anim.anim.name.startswith(
                    ('Walk', 'Run'))
                if self.track.hold(key, stalled, t) > 30.0:
                    self.emit(t, 'routine-stalled', r.role,
                              'moving: %r pinned at %r for 30s'
                              % (p.anim.anim.name, sig), self._pawn(p))
            elif r.state == r.USING and not game.ending and not parked:
                waiting = p.anim.waiting()
                if self.track.hold(key, waiting, t) > 30.0:
                    self.emit(t, 'routine-stalled', r.role,
                              'using: parked on looping %r 30s with no '
                              'sequence' % p.anim.anim.name, self._pawn(p))
            else:
                self.track.hold(key, False, t)
                r._monkey_sig = None

        # INV5 — numbers: finite coordinates inside the zone envelope,
        # frames inside the sheet, pattern indices inside the pattern,
        # inventory counts non-negative, dexterity/bars in range.
        for role, p in w.pawns.items():
            x, y = p.sprite.x, p.sprite.y
            if not (abs(x) < 1e3 and abs(y) < 1e3):
                self.emit(t, 'coords-blowup', role,
                          'position (%r, %r)' % (x, y), self._pawn(p))
                continue
            # the catch parks both pawns on one spot that may sit outside
            # every play range: Woody walks onto the neighbour's position
            # (OnGetCaughtByNeighbour, Woody.cs:263-271) and the neighbour
            # takes MoveToEmptySpace (RoutineActionHitWoody.cs:28) — the
            # envelope only binds while the game runs
            # ...and a pawn still on its LevelLocations spawn is data, not
            # movement (L201's neighbour is placed 2.3 outside his zone's
            # play range and walks in with his first action)
            spawn = self.spawn.setdefault(role, (x, y))
            if (p.zone is not None and p.state == p.IDLE
                    and not p.is_warping and not p.passing_complex
                    and not game.got_caught and not game.ending
                    and (abs(x - spawn[0]) > 1e-6 or abs(y - spawn[1]) > 1e-6)):
                if not (p.zone.play_left - 1.0 <= x
                        <= p.zone.play_right + 1.0):
                    # routine stand-points sit up to ~0.6 outside the play
                    # range (the binoculars case) — 1.0 covers them
                    self.emit(t, 'x-out-of-zone', role,
                              'x=%.2f outside %s [%.2f, %.2f]'
                              % (x, p.zone.name, p.zone.play_left,
                                 p.zone.play_right), self._pawn(p))
                fy = p.floor_y()
                if fy is not None and not (-1.0 <= y - fy <= 4.0):
                    # elevated items park a pawn up to ~2.5 above the floor
                    self.emit(t, 'y-off-floor', role,
                              'y=%.2f vs floor %.2f in %s'
                              % (y, fy, p.zone.name), self._pawn(p))
        # a frame outside the sheet is legitimate only PAST the animation's
        # end: Refresh keeps stepping CurrentFrame after a single ended with
        # nothing switched, and DrawAnimation samples that by the texture's
        # wrap mode (AnimationControllerBase.cs:153-170; L207's 1x1
        # N2TrickItemIdleNormal idles do this by design) — a frame the
        # animation itself claims (<= EndFrame, or a live pattern entry)
        # landing outside the sheet is a data/logic error
        for s in v.level.sprites:
            # current None: a controller with no CurrentAnimation yet
            # (AnimationControllerBase.cs:13) — nothing to check
            if s.cur_frame is None or s.current is None:
                continue
            a = s.anims[s.current]
            total = a.rows * a.cols
            if 0 <= s.cur_frame < max(total, 1):
                continue
            pl = w.players.get(id(s))
            past_end = True
            if pl is not None:
                if a.pattern:
                    past_end = pl.pat_idx >= len(a.pattern)
                elif not a.empty_pattern:
                    past_end = s.cur_frame > a.end
            # four range animations declare an EndFrame at or past their
            # sheet (L206 Rabbit Extra1 1/1x1, L211 AnswerPhoneNFH2Tricked
            # 0..49 on 49 cells, L212 ParrotNest's two 0..1 on 1x1): the
            # original draws that frame by the wrap mode too — data, not
            # a stepping error
            if not a.pattern and a.end >= total:
                past_end = True
            if not past_end:
                self.emit(t, 'frame-out-of-sheet', s.name,
                          'live frame %d of a %dx%d sheet (anim %s)'
                          % (s.cur_frame, a.rows, a.cols, a.name))
        # sequence bookkeeping: SequenceIndex never runs past the list
        # and a LOOPING pattern animation's index wraps inside its pattern
        # (Refresh: ReachedEndFrame → LoopToStartFrame in the same call) —
        # a finished single keeps incrementing CurrentFrameIndex past the
        # end (AdvanceFrame, AnimationInstance.cs:206-215), by design
        for pl in w.players.values():
            if pl.seq and not (0 <= pl.seq_index <= len(pl.seq)):
                self.emit(t, 'seq-index-out-of-range', pl.sprite.name,
                          'index %d of %d' % (pl.seq_index, len(pl.seq)))
            a = pl.anim                   # None: no CurrentAnimation yet
            if a is None or not a.pattern:
                continue
            looping = pl.mode == 'looping' or (a.infinite
                                               and not pl.ignore_infinite)
            if pl.pat_idx < 0 or (looping and pl.pat_idx >= len(a.pattern)):
                self.emit(t, 'pattern-index-out-of-range', pl.sprite.name,
                          'pat_idx %d of %d (anim %s, %s)'
                          % (pl.pat_idx, len(a.pattern), a.name, pl.mode))
        for it in w.inventory.items:
            if it.get('use_count', 0) < 0:
                self.emit(t, 'inventory-negative', it.get('type'),
                          'use_count %d' % it['use_count'])
        for ds in getattr(w, 'dex_states', {}).values():
            if ds.enabled and not (0.0 <= ds.percent <= 100.0):
                self.emit(t, 'dex-out-of-range', 'dexterity',
                          'percent %r' % ds.percent)
        for pb in bars:
            if pb.visible and not (-0.01 <= pb.progress <= 1.01):
                self.emit(t, 'bar-out-of-range', str(pb.spec.get('actor')),
                          'progress %r' % pb.progress)

        # INV7 — the clock freezes exactly on the pause and runs off it
        # (GameInfo.Update, timed levels count down); the angry meter
        # stays inside [0, max] (Rottweiler.Update's decay clamp).
        now = game.time_seconds
        if self.prev_time is not None:
            if not ticked and abs(now - self.prev_time) > 1e-9:
                self.emit(t, 'clock-runs-paused', 'clock',
                          '%.3f -> %.3f while paused'
                          % (self.prev_time, now))
            if (ticked and game.timed and not game.ending
                    and not game.time_up and now > self.prev_time + 1e-9):
                self.emit(t, 'clock-wrong-way', 'clock',
                          'timed clock rose %.3f -> %.3f'
                          % (self.prev_time, now))
        self.prev_time = now
        for role, p in w.pawns.items():
            if not (-1e-6 <= p.angry_meter <= p.angry_max + 1e-6):
                self.emit(t, 'angry-out-of-range', role,
                          'meter %r of max %r'
                          % (p.angry_meter, p.angry_max))

    def _pawn(self, p):
        return {'role': p.role, 'x': round(p.sprite.x, 3),
                'y': round(p.sprite.y, 3), 'state': p.state,
                'anim': p.anim.anim.name, 'zone':
                p.zone.name if p.zone else None,
                'locked': p.input_locked, 'warping': p.is_warping,
                'hidden': p.sprite.hidden}


# ---------------------------------------------------------------------------
# the monkey itself

class Monkey(Recorder):
    def __init__(self, level_path, outdir, seed=1, seconds=180.0):
        Recorder.__init__(self, level_path, outdir, script=None,
                          seconds=seconds, fps=0)
        self.rng = random.Random(seed)
        self.seed = seed
        self.inv = Invariants(self.v.level.name, seed)
        from invariants import Invariants as FrameInvariants
        self.frame_inv = FrameInvariants(self.v)
        self.frame_hooks.append(self.frame_inv.frame)
        self.next_click_ok = 0.0
        self.pause_until = None

    # -- targets -----------------------------------------------------------
    def _screen_of(self, wx, wy):
        return self.v.cam.world_to_screen(wx, wy, WIDTH, HEIGHT)

    def _random_target(self, hot):
        """one click target; the mix leans on items and doors, with the
        HUD strip and raw screen points keeping the edges honest"""
        rng = self.rng
        v = self.v
        roll = rng.random()
        if v.world.game.ending and roll < 0.6:
            # the score screen: its two buttons live mid-screen; spraying
            # the middle band hits them and everything between
            return (rng.uniform(WIDTH * 0.25, WIDTH * 0.75),
                    rng.uniform(HEIGHT * 0.35, HEIGHT * 0.75))
        if roll < 0.40:
            items = [i for i in v.level.items.values()
                     if i.collider is not None and i.clickable]
            if items:
                it = rng.choice(items)
                return self._screen_of(it.collider[0], it.collider[1])
        elif roll < 0.55:
            doors = [d for d in v.level.doors
                     if d.collider is not None and not d.disabled]
            if doors:
                d = rng.choice(doors)
                return self._screen_of(d.collider[0], d.collider[1])
        elif roll < 0.67:
            mc = v.level.mouse_cursor or {}
            strip = float(mc.get('min_mouse_y') or 90.0) * HEIGHT / 600.0
            return (rng.uniform(0, WIDTH - 1),
                    rng.uniform(HEIGHT - strip, HEIGHT - 1))
        elif roll < 0.77 and v.woody is not None:
            return self._screen_of(v.woody.sprite.x, v.woody.sprite.y)
        return (rng.uniform(0, WIDTH - 1), rng.uniform(0, HEIGHT - 1))

    def _hot(self):
        """is a transition window open right now?  (the moments the audit
        prompt orders the clicks into)"""
        v = self.v
        w = v.woody
        g = v.world.game
        if w is None:
            return False
        return (w.is_warping or w.state in ('door_anim', 'door_climb',
                                            'descend', 'item_climb')
                or w.anim.blocking
                or w.anim.anim.name.startswith('Fear')
                or (w.hiding and w.hiding_item is not None)
                or w.was_hiding
                or g.got_caught or g.ending
                or v.world.is_dexterity_on
                or self.paused or v.world.menu_open)

    # -- the input stream ---------------------------------------------------
    def _inputs(self, t):
        rng = self.rng
        v = self.v
        hot = self._hot()
        p_click = 0.10 if hot else 0.02
        if t < 1.0:
            p_click = 0.15               # the first second is a named window
        if t >= self.next_click_ok and rng.random() < p_click:
            self.next_click_ok = t + 3 * DT
            n = 2 if rng.random() < 0.10 else 1     # two clicks, one tick
            for _ in range(n):
                sx, sy = self._random_target(hot)
                self.mouse[0], self.mouse[1] = sx, sy
                self._click(sx, sy)
        if rng.random() < 0.01:          # retarget the hover glide
            items = [i for i in v.level.items.values()
                     if i.collider is not None and i.clickable]
            if items:
                it = rng.choice(items)
                self.mouse_target = list(self._screen_of(it.collider[0],
                                                         it.collider[1]))
        if rng.random() < 0.004:         # the Tab sneak toggle
            if v.woody is not None:
                v.woody.toggle_sneak()   # Woody.ToggleSneak (Woody.cs:1151)
        if rng.random() < 0.006:         # inventory digits, 0 clears
            v.world.inventory.select(rng.randrange(-1, 4))
        if rng.random() < 0.002:         # the info-button style press+hold
            self.v.virtual_mouse_down = not self.v.virtual_mouse_down
        if v.world.is_dexterity_on:      # fight the drifting pick
            for ds in v.world.dex_states.values():
                if ds.enabled:
                    ds.input = (ds.input[0] + rng.uniform(-40, 40),
                                ds.input[1] + rng.uniform(-40, 40))
        # the viewer-space pause (Space): rare, held 0.3-2 s
        if self.pause_until is not None and t >= self.pause_until:
            self.paused = False
            self.pause_until = None
        elif self.pause_until is None and rng.random() < 0.0008:
            self.paused = True
            self.pause_until = t + rng.uniform(0.3, 2.0)

    def run(self):
        t = 0.0
        self._next_shot = 0.0
        self._shot_i = 0
        while t < self.seconds + 1e-9:
            self._inputs(t)
            self.tick(t)
            self.inv.check(self.v, t, self.paused)
            t += DT
        self.log.close()
        # fold the shared frame checker (tests/invariants.py) into the
        # same findings stream — emit dedupes per (invariant, subject)
        for x in self.frame_inv.finish():
            self.inv.emit(x['t'], x['kind'], x['subject'], x['detail'])
        out = os.path.join(self.outdir, 'findings.jsonl')
        with open(out, 'w') as f:
            for x in self.inv.findings:
                f.write(json.dumps(x) + '\n')
        return self.inv.findings


def run_one(args):
    level, seed, seconds, outroot = args
    name = os.path.splitext(os.path.basename(level))[0]
    season = os.path.basename(os.path.dirname(level))
    outdir = os.path.join(outroot, '%s_%s_s%d' % (season, name, seed))
    os.makedirs(outdir, exist_ok=True)
    # a subprocess per run keeps SDL state and a crash isolated
    import subprocess
    r = subprocess.run([sys.executable, os.path.abspath(__file__), level,
                        '--seeds=%d' % seed, '--seconds=%s' % seconds,
                        '--out=' + outroot, '--child'],
                       env=dict(os.environ, SDL_VIDEODRIVER='offscreen'),
                       capture_output=True, text=True)
    fpath = os.path.join(outdir, 'findings.jsonl')
    finds = [json.loads(l) for l in open(fpath)] if os.path.exists(fpath) \
        else []
    crashed = r.returncode not in (0, 1)
    return (level, seed, finds, crashed,
            (r.stdout + r.stderr)[-2000:] if crashed else '')


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    opts = {a.split('=')[0][2:]: (a.split('=', 1)[1] if '=' in a else '1')
            for a in argv[1:] if a.startswith('--')}
    seconds = float(opts.get('seconds', 180))
    seeds = [int(s) for s in opts.get('seeds', '1,2').split(',')]
    outroot = opts.get('out', '/tmp/nfh-monkey')
    if 'all' in opts:
        import glob
        args = sorted(glob.glob(os.path.join(ROOT, 'levels', 's*',
                                             'Level*.json')))
    if not args:
        print(__doc__)
        return 2
    if 'child' in opts or (len(args) == 1 and len(seeds) == 1):
        level = args[0]
        name = os.path.splitext(os.path.basename(level))[0]
        season = os.path.basename(os.path.dirname(level))
        outdir = os.path.join(outroot, '%s_%s_s%d' % (season, name,
                                                      seeds[0]))
        finds = Monkey(level, outdir, seed=seeds[0],
                       seconds=seconds).run()
        for x in finds:
            print('FINDING %(invariant)s %(subject)s t=%(t)s: %(detail)s'
                  % x)
        print('%s seed %d: %d findings' % (name, seeds[0], len(finds)))
        return 1 if finds else 0
    from concurrent.futures import ThreadPoolExecutor
    jobs = [(lv, sd, seconds, outroot) for lv in args for sd in seeds]
    total = []
    crashes = []
    with ThreadPoolExecutor(max_workers=int(opts.get('jobs', 4))) as ex:
        for level, seed, finds, crashed, tail in ex.map(run_one, jobs):
            name = os.path.basename(level)
            if crashed:
                crashes.append((name, seed, tail))
                print('%-24s seed %d  CRASH' % (name, seed))
                continue
            print('%-24s seed %d  %d findings%s' % (name, seed, len(finds),
                  ':' if finds else ''))
            for x in finds:
                print('    %(invariant)s %(subject)s t=%(t)s: %(detail)s'
                      % x)
            total += finds
    print('---')
    by_inv = {}
    for x in total:
        by_inv.setdefault(x['invariant'], []).append(x)
    for inv, xs in sorted(by_inv.items(), key=lambda kv: -len(kv[1])):
        print('%-24s %d  (e.g. %s %s)' % (inv, len(xs), xs[0]['level'],
                                          xs[0]['subject']))
    for name, seed, tail in crashes:
        print('CRASH %s seed %d:\n%s' % (name, seed, tail))
    print('monkey: %d findings, %d crashes over %d runs'
          % (len(total), len(crashes), len(jobs)))
    return 1 if total or crashes else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
