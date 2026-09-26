#!/usr/bin/env python3
"""The neighbour's lap by code and data — the PC original's timing model.

    python3 tools/pcref/lap_model.py [-v] [101 102 ...]

For each Season 1 level the lap the walker reads out of game.exe
(`LAPS=1 tools/pcref/routine_order.py`: ICON / GOTO / ACTION tokens along
the level class's cases) is timed from the archive's data:

- a GOTO walks along the room's path at the neighbour's `<speed>` record
  (generic/objects.xml: mg1 8 px a tick, the tick 12 Hz — fcn.0047c7f0,
  docs/PC_VERIFICATION.md "the walking speed"); a room change goes through
  the doors of level.xml, each door's standing point = the door type's
  `neighbor` hotspot (objects.xml) + the door's `position`, and costs the
  door's `enter` and the far door's `leave` action times;
- an object with `neighbor`/`neighbor_out` hotspots and `enter`/`leave`
  actions (the sofa) is entered on arrival and left on departure;
- an ACTION lasts its objects.xml `time`: N ticks, or `auto` = the frames
  of its object animation (anims.xml) — or of the neighbour's own
  animation (generic/anims.xml) when the object side is `inv`.

The total is compared with the PC video's natural lap (docs/PC_LAPS.md).
Object positions come from objects.xml hotspots (room coordinates); the
sprite placements of gfxdata.xml are not needed for the walk.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canon  # noqa: E402

X = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
TICK = 12.0
# the laps of a routine's cycle, where the case order alternates: 106's tub is
# filled on one lap (case 8's give) and bathed in on the next (cases 14-15:
# Level_Bath::isBathFilled, fcn.0046bc90) — the video's lap is the whole cycle
CYCLE = {106: 2}


def xy(s):
    a, b = s.split('/')
    return int(a), int(b)


def attrs(tag):
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def frames_of(text):
    """{(object, animation): (frames, type)} of an anims.xml — type oneshot or loop"""
    out = {}
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', text, re.S):
        for am in re.finditer(r'<animation name="([^"]+)"([^>]*)>(.*?)</animation>', om.group(2), re.S):
            out[(om.group(1), am.group(1))] = (len(re.findall(r'<frame', am.group(3))),
                                               attrs(am.group(2)).get('type', 'oneshot'))
    return out


class Level:
    def __init__(self, n):
        pl = canon.pc_level(n)
        self.n = n
        self.folder = pl['folder']
        self.tricks = set(pl['tricks'])
        d = os.path.join(X, self.folder)
        lv = canon.read(d + '/level.xml')
        ob = canon.read(d + '/objects.xml')
        self.frames = frames_of(canon.read(d + '/anims.xml'))
        self.generic = frames_of(canon.read(X + '/generic/anims.xml'))
        gen_ob = canon.read(X + '/generic/objects.xml')
        m = re.search(r'<actor name="neighbor"[^>]*>(.*?)</actor>', gen_ob, re.S)
        sp = {attrs(t)['name']: attrs(t) for t in re.findall(r'<speed\b[^>]*/>', m.group(1))}
        self.speed = int(sp['mg1']['speed'])    # px a tick along the floor (facing left/right)
        self.vspeed = int(sp['mg0']['speed'])   # px a tick up and down the room (facing 0/2)
        self.start_px = int(sp['mg1']['start'])  # the first move's extra px, facing right
        self.start_px_left = int(sp['mg3']['start'])  # and facing left
        # rooms, their paths and doors
        self.rooms = {}
        self.start = None
        self.placed = {}        # the actors level.xml places: room, position
        for rm in re.finditer(r'<room name="(\w+)" offset="([^"]+)" path1="([^"]+)" path2="([^"]+)">(.*?)</room>', lv, re.S):
            name = rm.group(1)
            x1, y = xy(rm.group(3)); x2, _ = xy(rm.group(4))
            doors = {}
            for dm in re.finditer(r'<door\b([^>]*)/?>', rm.group(5)):
                a = attrs(dm.group(1))
                doors[a['name']] = xy(a['position'])
            self.rooms[name] = {'x1': min(x1, x2), 'x2': max(x1, x2), 'y': y, 'doors': doors}
            for am in re.finditer(r'<actor name="neighbor"[^>]*position="([^"]+)"', rm.group(5)):
                self.start = (name,) + xy(am.group(1))
            for am in re.finditer(r'<actor name="([^"]+)"[^>]*position="([^"]+)"', rm.group(5)):
                self.placed[am.group(1)] = (name,) + xy(am.group(2))
        # doors and objects of objects.xml: hotspots and the neighbour's action times
        self.doors = {}
        for dm in re.finditer(r'<door name="([^"]+)"([^>]*)>(.*?)</door>', ob, re.S):
            self.doors[dm.group(1)] = self._entry(dm.group(2), dm.group(3))
        self.objects = {}
        for om in re.finditer(r'<object name="([^"]+)"([^>]*)>(.*?)</object>', ob, re.S):
            self.objects[om.group(1)] = self._entry(om.group(2), om.group(3))
        # the actors' own action records of the level (the neighbour's `eat`,
        # `skip_rope`, `smokepipe` …, the parrot's `eat` of 109): an ACTION whose
        # object is an actor, or none, looks them up there
        self.actors = {}
        for am in re.finditer(r'<actor name="([^"]+)"([^>]*)>(.*?)</actor>', ob, re.S):
            self.actors[am.group(1)] = self._entry(am.group(2), am.group(3))
        # the actors' records every level shares (generic/objects.xml: the
        # neighbour's surprise, shouts, take_low, search …; the pets')
        self.gen_actors = {}
        for am in re.finditer(r'<actor name="([^"]+)"([^>]*)>(.*?)</actor>', gen_ob, re.S):
            self.gen_actors[am.group(1)] = self._entry(am.group(2), am.group(3))

    def _entry(self, head, body):
        e = {'gfx': attrs(head).get('gfx'), 'hot': {}, 'act': {}}
        for h in re.finditer(r'<hotspot name="(\w+)" offset="([^"]+)"', body):
            e['hot'][h.group(1)] = xy(h.group(2))
        for a in re.finditer(r'<action\b([^>]*)/?>', body):
            at = attrs(a.group(1))
            e['act'][(at.get('actor'), at.get('name'))] = at
        return e

    # -- durations ------------------------------------------------------------
    def _record(self, obj, name, actor='neighbor'):
        """(record, its owner's gfx, the acting actor) of an action, as the ACTION
        step finds it (fcn.004772f0): the object's record for the actor, or the
        object's own (105's football flies in), else — the object has none —
        the actor's own (the level's `<actor>` block, then generic/objects.xml's);
        None when nobody has it (the step pushes no job)"""
        e = self.objects.get(obj) or self.doors.get(obj) or self.actors.get(obj) \
            or self.gen_actors.get(obj)
        if e and (actor, name) in e['act']:
            return e['act'][(actor, name)], e['gfx'] or obj, actor
        if e and (obj, name) in e['act']:
            return e['act'][(obj, name)], e['gfx'] or obj, obj
        for blk in (self.actors.get(actor), self.gen_actors.get(actor)):
            if blk and (actor, name) in blk['act']:
                return blk['act'][(actor, name)], blk['gfx'] or actor, actor
        return None

    def _oneshot(self, gfx, anim):
        """an animation's frames as Loader.dll's lookup with its flag 1 gives them
        (0x10005340: the level's anims.xml, then generic/anims.xml): a oneshot's
        frame count, a loop or a missing one -1"""
        v = self.frames.get((gfx, anim)) or self.generic.get((gfx, anim))
        return v[0] if v and v[1] == 'oneshot' else -1

    def action_ticks(self, obj, name, actor='neighbor'):
        """the ticks of an action as Loader.dll stores its record's time (+0x28):
        time="N" as N; time="auto" as the longer of the actor's animation (its
        gfx's set) and the object's (the owner's gfx) less one, at least 0 —
        `inv` not asked, a loop or a missing animation -1 (NFH1's Loader.dll
        0x1000a865-0x1000aa05, the rule of NFH2's 0x10009704-0x10009842); None
        when no record has it"""
        r = self._record(obj, name, actor)
        if r is None:
            return None
        a, owner_gfx, actor = r
        t = a.get('time', 'auto')
        if t.isdigit():
            return int(t)
        blk = self.actors.get(actor) or self.gen_actors.get(actor)
        agfx = (blk and blk['gfx']) or (owner_gfx if actor == obj else actor)
        aa, oa = a.get('actoranim', ''), a.get('objanim', '')
        va = self._oneshot(agfx, aa) if aa and aa != 'inv' else -1
        vo = self._oneshot(owner_gfx, oa) if oa and oa != 'inv' else -1
        return max(max(va, vo) - 1, 0)

    def job_ticks(self, obj, name, actor='neighbor'):
        """the ticks an ACTION step of the action takes, from its start to the
        next step's: the step's update (fcn.004772f0, slot 2 of vtable
        0x4e546c) starts it on its first call — the animations, the noise, a
        timer job of the longest record time pushed on the actor's queue with
        the run-now flag 0 (0x477a46-0x477a62, fcn.00444d30) — and returns
        not done (0x477ad6); the timer's update (0x47e500) counts it down and
        is done on its (time + 1)th call, the first on the tick after; the
        actor's tick then pops it and updates the step again in the same tick
        (0x444db0: 0x444e05-0x444e7c), which ends it (the started flag +0x24:
        the stop fcn.00476da0, done 0x477b3b), and the sequence or the level
        class below pushes the next step with the run-now flag 0 (0x4765d4,
        the classes' cases), so it starts on the next tick — time + 2; no
        timer when the longest time is 0 (0x477975), the step's two updates
        still two ticks. None when no record has it"""
        t = self.action_ticks(obj, name, actor)
        if t is None:
            return None
        return t + 2

    def has_action(self, obj, name, actor='neighbor'):
        """the object (or the actor's blocks, the level's and the generic) has an
        action record of that name"""
        for e in (self.objects.get(obj) or self.doors.get(obj),
                  self.actors.get(obj), self.gen_actors.get(obj)):
            if e and ((actor, name) in e['act'] or (obj, name) in e['act']):
                return True
        return False

    def has_enter_leave(self, obj):
        e = self.objects.get(obj)
        return bool(e and 'neighbor_out' in e['hot'] and ('neighbor', 'enter') in e['act'] and ('neighbor', 'leave') in e['act'])

    # -- geometry -------------------------------------------------------------
    def object_point(self, obj):
        """an entity's hotspot = its position + the hotspot's offset (fcn.00445aa0:
        [+0x28/+0x2c] + the map entry's [+0x10/+0x14], else the position); objects
        sit at 0/0 of their room, an actor where level.xml places it (109's parrot),
        else at 0/0 of the room of its name (105's football, made by the script)"""
        e = self.objects.get(obj)
        base = (obj.split('/')[0], 0, 0)
        if not e and obj in self.actors and obj != 'neighbor':
            e = self.actors[obj]
            base = self.placed.get(obj) or base
        if not e: return None
        p = e['hot'].get('neighbor') or e['hot'].get('woody')
        if not p: return None
        return base[0], base[1] + p[0], base[2] + p[1]

    def door_point(self, door, out=False):
        """the standing point of a door in its room: the type's neighbour hotspot (`neighbor_out` when the
        neighbour comes out of it) + the door's position"""
        room = door.split('/')[0]
        e = self.doors.get(door)
        if not e or room not in self.rooms or door not in self.rooms[room]['doors']: return None
        h = (e['hot'].get('neighbor_out') if out else None) or e['hot'].get('neighbor')
        if not h: return None
        px, py = self.rooms[room]['doors'][door]
        return h[0] + px, h[1] + py

    def route(self, a, b):
        """the rooms from a to b through doors the neighbour may use: [(door out, door in), ...]"""
        if a == b: return []
        prev = {a: None}; queue = [a]
        while queue:
            r = queue.pop(0)
            for door in self.rooms[r]['doors']:
                far = door.split('/')[1]
                back = far + '/' + r
                if far not in self.rooms or far in prev: continue
                if self.door_point(door) is None or self.door_point(back) is None: continue
                prev[far] = (r, door, back); queue.append(far)
                if far == b:
                    path = []; cur = b
                    while prev[cur]:
                        pr, d_out, d_in = prev[cur]; path.append((d_out, d_in)); cur = pr
                    return path[::-1]
        return None

    def walk_ticks(self, dx, dy=0):
        """a mover's ticks (vtable 0x4e59e8, update 0x47cb50): one axis a tick, x
        before y, the floor at `speed`, the depth at `vspeed`, its first move
        `start` px longer (mg1's facing right, mg3's left; the vertical records'
        0), clamped at the target, found in the update of its last move"""
        t = 0
        if dx:
            a = abs(dx)
            start = self.start_px if dx > 0 else self.start_px_left
            t += 1 + (-(-(a - self.speed - start) // self.speed) if a > self.speed + start else 0)
        if dy:
            t += -(-abs(dy) // self.vspeed)
        return t


def tokens_of(levels, cache, laps=None):
    """{level: [tokens of lap 1]} from the walker; `laps` {level: k} joins a
    level's first k laps (106's cycle: the tub filled on one lap, the bath on
    the next — Level_Bath::isBathFilled, tools/pcref/routine_order.py)"""
    if cache and os.path.exists(cache):
        text = open(cache).read()
    else:
        env = dict(os.environ, LAPS='1')
        text = subprocess.run([sys.executable, os.path.join(HERE, 'routine_order.py')], env=env, capture_output=True, text=True).stdout
        if cache: open(cache, 'w').write(text)
    out = {}
    for m in re.finditer(r'^LAP (\d+) (\d+): (.*)$', text, re.M):
        n, k = int(m.group(1)), int(m.group(2))
        if k > (laps or {}).get(n, 1):
            continue
        toks = []
        for t in m.group(3).split(' | '):
            kind, _, rest = t.partition(' ')
            toks.append((kind, rest.split(' + ') if rest else []))
        out.setdefault(n, []).extend(toks)
    return out


def video_laps():
    out = {}
    for line in open(os.path.join(HERE, '..', '..', 'docs', 'PC_LAPS.md')):
        m = re.match(r'\| (\d{3}) \| (\d+) \| (\d+) \|', line)
        if m: out[int(m.group(1))] = int(m.group(2))
    return out


def model(L, toks, verbose=False, steady=True):
    """the legs of one lap: (kind, text, ticks) — kinds walk / door / action / intro / ?.
    Where the walker marks the case the lap's last `next` re-enters (WRAP),
    the steady lap is the tokens from there, walked from where lap 1 ends
    (107's painting walk, case 16, opens every lap; 108's toothbrush is the
    first lap's only); else, or with `steady` off (the stations' pairing,
    tools/pcref/pc_durations.py: every visit of lap 1), lap 1 from the
    level's start, its first walk the intro"""
    plain = [t for t in toks if t[0] != 'WRAP']
    if steady and len(plain) != len(toks):
        i = next(j for j, (k, _) in enumerate(toks) if k == 'WRAP')
        _, end = _lap(L, plain, None)
        return _lap(L, toks[i + 1:], end)[0]
    return _lap(L, plain, None)[0]


def _lap(L, toks, start):
    """the legs of the tokens and the end state (room, x, y, occupied,
    current): from the level's start with the first walk as the intro, or
    from `start` with every walk counted"""
    legs = []
    room, x, y = L.start if start is None else start[:3]
    occupied = None if start is None else start[3]      # the container object the neighbour sits in
    current = None if start is None else start[4]       # the object of the last GOTO / ENTER (the target of a bare ACTION)
    first = start is None

    def base_of(objs):
        b = [o for o in objs if o not in L.tricks]
        return (b or objs or [None])[-1]

    def walk_to(room2, x2, y2, what):
        nonlocal room, x, y
        r = L.route(room, room2)
        if r is None:
            legs.append(('?', 'no route %s -> %s (%s)' % (room, room2, what), 0)); room, x, y = room2, x2, y2; return
        after = False
        for d_out, d_in in r:
            xo, yo = L.door_point(d_out); xi, yi = L.door_point(d_in, out=True)
            t = L.walk_ticks(xo - x, yo - y)
            if after and t:
                t -= 1                # its first move in the leave's last tick (0x4760ad, run-now 1)
            legs.append(('walk', '%s %d/%d -> %s %d/%d' % (room, x, y, d_out, xo, yo), t))
            t_out = L.job_ticks(d_out, 'enter') or 0; t_in = L.job_ticks(d_in, 'leave') or 0
            legs.append(('door', '%s enter %d + %s leave %d' % (d_out, t_out, d_in, t_in), t_out + t_in))
            room, x, y = d_in.split('/')[0], xi, yi
            after = True
        t = L.walk_ticks(x2 - x, y2 - y)
        if after and t:
            t -= 1
        legs.append(('walk', '%s %d/%d -> %s %d/%d' % (room, x, y, what, x2, y2), t)); x, y = x2, y2

    def leave(obj=None, implicit=False):
        """the object's leave; the one a walk makes (the neighbour still in the
        object when the next GOTO starts) plays there before the walk, so it
        closes the station he sits in: it goes before the next station's icon"""
        nonlocal occupied
        obj = obj or occupied
        if obj:
            # the LEAVE step's ACTION `leave`: two updates without a record
            t = L.job_ticks(obj, 'leave')
            t = 2 if t is None else t
            i = len(legs)
            while implicit and i > 0 and legs[i - 1][0] == 'icon':
                i -= 1
            legs.insert(i, ('action', '%s leave' % obj, t)); occupied = None

    def enter(obj):
        nonlocal occupied
        # the ENTER step's ACTION `enter`: two updates without a record (107's stool)
        t = L.job_ticks(obj, 'enter')
        t = 2 if t is None else t
        legs.append(('action', '%s enter' % obj, t)); occupied = obj

    def goto(obj):
        nonlocal room, x, y, current, first
        pt = L.object_point(obj)
        if pt is None: legs.append(('?', 'GOTO %s: no hotspot' % obj, 0)); return False
        r2, x2, y2 = pt
        if first:
            legs.append(('intro', 'start %s %d/%d -> %s' % (room, x, y, obj), 0)); room, x, y = r2, x2, y2; first = False
        else:
            if occupied and occupied != obj: leave(implicit=True)
            moved = (r2, x2, y2) != (room, x, y)
            walk_to(r2, x2, y2, obj)
            # the GOTO's next update ends it a tick after the last move
            # (0x44aab0); with no move the walk job ends inside its first
            # update and the arrival is read on the second: three ticks
            legs.append(('goto', 'the GOTO ends', 1 if moved else 3))
        current = obj
        return True

    for kind, strs in toks:
        objs = [s for s in strs if '/' in s]
        if not objs and kind in ('GOTO', 'GOTOENTER'):     # an actor target (109's parrot)
            objs = [s for s in strs if s in L.actors and s != 'neighbor' and L.object_point(s)]
        if kind == 'ICON':
            legs.append(('icon', ' '.join(strs), 0)); continue
        if kind == 'TRICK': continue
        if kind in ('GOTO', 'GOTOENTER', 'ENTER'):
            obj = base_of(objs)
            if obj is None:
                if kind != 'ENTER': legs.append(('?', '%s without an object' % kind, 0))
                elif current: enter(current)
                continue
            if kind == 'ENTER' and current == obj and occupied == obj: continue
            # the ENTER step sets the occupied object (fcn.00444a70 in its start,
            # fcn.00473830) and pushes an ACTION `enter`, which plays nothing on
            # an object without the record (107's stool: a step of 0 ticks)
            if goto(obj) and kind != 'GOTO' and occupied != obj:
                # the intro's enter is the previous lap's: the lap's wrap (the
                # same tokens again) plays it — the stations would count it twice
                if legs[-1][0] != 'intro': enter(obj)
                else: occupied = obj
        elif kind == 'LEAVE':
            leave(base_of(objs))
        elif kind == 'GOTO2':
            r2 = strs[-1] if strs else None
            if r2 in L.rooms:
                if occupied: leave(implicit=True)
                rt = L.route(room, r2)
                if rt: walk_to(r2, *L.door_point(rt[-1][1], out=True), 'room ' + r2)
            else:
                legs.append(('?', 'GOTO2 %s' % ' + '.join(strs), 0))
        elif kind == 'ACTION':
            # the walker's pushes around the call: the action's name is the
            # string that names an action record of one of the objects (a room
            # name or an icon may precede it), the object the one that has it —
            # a pushed actor (109's parrot), the last GOTO's, or the neighbour
            # himself (his own records: `eat`, `skip_rope` …)
            acts = [s for s in strs if '/' not in s and s not in ('neighbor', 'woody', 'inv')]
            if not acts: continue
            b = base_of(objs)
            actors = [s for s in strs if s in L.actors and s != 'neighbor']
            cands = ([b] if b else []) + [o for o in objs if o != b] + actors \
                + ([current] if current else []) + ['neighbor']
            hit = next(((o, nm) for nm in acts for o in cands if L.has_action(o, nm)), None)
            if hit:
                used, name = hit
                t = L.job_ticks(used, name)
            else:               # no record: the neighbour's animation of the first name
                name = acts[0]
                used = next((o for o in cands if L.action_ticks(o, name) is not None), None)
                t = L.job_ticks(used, name) if used else None
            if t is None:
                legs.append(('?', 'ACTION %s on %s: no time' % (name, ' + '.join(objs) or current), 0))
            else:
                legs.append(('action', '%s %s' % (used, name), t))
    # the lap closes on the first station's enter; its leave opens the next lap
    return legs, (room, x, y, occupied, current)


def stations(legs):
    """the lap by ICON: [(icon, action ticks, walk+door ticks)]. A steady lap
    (model's WRAP) opens inside its first station — the actions or the walk
    before the first ICON — and closes on that station's ICON and walk: the
    two halves are the first station, put first"""
    out = []; cur = None; lead = [0, 0]
    for kind, text, t in legs:
        if kind == 'icon':
            cur = [text, 0, 0]; out.append(cur); continue
        tgt = cur if cur is not None else [None] + lead
        if kind == 'action': tgt[1] += t
        elif kind in ('walk', 'door', 'goto'): tgt[2] += t
        if cur is None: lead = tgt[1:]
    if out and (lead[0] or lead[1]):
        last = out.pop()
        last[1] += lead[0]; last[2] += lead[1]
        out.insert(0, last)
    return out


def main(argv):
    verbose = '-v' in argv
    show_stations = '--stations' in argv
    args = [a for a in argv[1:] if not a.startswith('-')]
    levels = [int(a) for a in args] or list(range(101, 115))
    cache = os.environ.get('LAP_TOKENS')
    toks = tokens_of(levels, cache, CYCLE)
    video = video_laps()
    for n in levels:
        if n not in toks:
            print('%d: no lap tokens' % n); continue
        L = Level(n)
        legs = model(L, toks[n], verbose)
        by = {}
        for kind, text, t in legs: by[kind] = by.get(kind, 0) + t
        total = sum(t for k, t, _ in [(k, t, 0) for k, _, t in legs] if k != 'intro')
        secs = total / TICK
        v = video.get(n)
        delta = ('%+d %%' % round(100.0 * (secs - v) / v)) if v else 'n/a'
        unknown = sum(1 for k, _, _ in legs if k == '?')
        print('%d %-14s lap %6.1f s = walk %5.1f + doors %5.1f + actions %5.1f | video %s | %s%s' % (
            n, L.folder, secs, (by.get('walk', 0) + by.get('goto', 0)) / TICK, by.get('door', 0) / TICK, by.get('action', 0) / TICK,
            '%d s' % v if v else '-', delta, ('  (%d unknown)' % unknown) if unknown else ''))
        if verbose:
            for kind, text, t in legs:
                print('     %-6s %4d  %s' % (kind, t, text))
        if show_stations:
            mob = canon.mobile_level(n)['routine']
            print('     mobile routine: %s' % ' > '.join(str(r[0]) for r in mob))
            for icon, ta, tw in stations(legs):
                print('     %-28s actions %5.1f s   walk+doors %5.1f s' % (icon, ta / TICK, tw / TICK))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
