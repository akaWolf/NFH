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


def xy(s):
    a, b = s.split('/')
    return int(a), int(b)


def attrs(tag):
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def frames_of(text):
    """{(object, animation): frames} of an anims.xml"""
    out = {}
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', text, re.S):
        for am in re.finditer(r'<animation name="([^"]+)"[^>]*>(.*?)</animation>', om.group(2), re.S):
            out[(om.group(1), am.group(1))] = len(re.findall(r'<frame', am.group(2)))
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
        self.start_px = int(sp['mg1']['start'])  # the first step off the standing animation
        # rooms, their paths and doors
        self.rooms = {}
        self.start = None
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
        # doors and objects of objects.xml: hotspots and the neighbour's action times
        self.doors = {}
        for dm in re.finditer(r'<door name="([^"]+)"([^>]*)>(.*?)</door>', ob, re.S):
            self.doors[dm.group(1)] = self._entry(dm.group(2), dm.group(3))
        self.objects = {}
        for om in re.finditer(r'<object name="([^"]+)"([^>]*)>(.*?)</object>', ob, re.S):
            self.objects[om.group(1)] = self._entry(om.group(2), om.group(3))

    def _entry(self, head, body):
        e = {'gfx': attrs(head).get('gfx'), 'hot': {}, 'act': {}}
        for h in re.finditer(r'<hotspot name="(\w+)" offset="([^"]+)"', body):
            e['hot'][h.group(1)] = xy(h.group(2))
        for a in re.finditer(r'<action\b([^>]*)/?>', body):
            at = attrs(a.group(1))
            e['act'][(at.get('actor'), at.get('name'))] = at
        return e

    # -- durations ------------------------------------------------------------
    def action_ticks(self, obj, name, actor='neighbor'):
        """the ticks of an action: time="N", or auto = the frames of the actor's animation
        (the level's anims.xml `neighbor` entry, else generic/anims.xml), else of the object's
        animation (the level's anims.xml under the object's name or gfx); None if unknown"""
        e = self.objects.get(obj) or self.doors.get(obj)
        if e and (actor, name) in e['act']:
            a = e['act'][(actor, name)]
            t = a.get('time', 'auto')
            if t.isdigit(): return int(t)
            aa = a.get('actoranim', 'inv')
            if aa not in ('inv', 'ms', ''):
                f = self.frames.get((actor, aa)) or self.generic.get((actor, aa))
                if f: return f
            oa = a.get('objanim', '')
            if oa not in ('', 'ms', 'inv'):
                f = self.frames.get((obj, oa)) or self.frames.get((e['gfx'] or obj, oa))
                if f: return f
            return None
        return self.frames.get((actor, name)) or self.generic.get((actor, name))

    def has_enter_leave(self, obj):
        e = self.objects.get(obj)
        return bool(e and 'neighbor_out' in e['hot'] and ('neighbor', 'enter') in e['act'] and ('neighbor', 'leave') in e['act'])

    # -- geometry -------------------------------------------------------------
    def object_point(self, obj):
        e = self.objects.get(obj)
        if not e: return None
        p = e['hot'].get('neighbor') or e['hot'].get('woody')
        if not p: return None
        return obj.split('/')[0], p[0], p[1]

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
        """one axis a tick (fcn.0047c7f0's four facing branches): the floor at `speed`, the depth at `vspeed`;
        the first step off the standing animation adds `start` px"""
        dx, dy = abs(dx), abs(dy)
        if dx == 0 and dy == 0: return 0
        t = 0
        if dx: t += max(1, -(-(dx - self.start_px) // self.speed) + 1) if dx > self.start_px else 1
        if dy: t += -(-dy // self.vspeed)
        return t


def tokens_of(levels, cache):
    """{level: [tokens of lap 1]} from the walker"""
    if cache and os.path.exists(cache):
        text = open(cache).read()
    else:
        env = dict(os.environ, LAPS='1')
        text = subprocess.run([sys.executable, os.path.join(HERE, 'routine_order.py')], env=env, capture_output=True, text=True).stdout
        if cache: open(cache, 'w').write(text)
    out = {}
    for m in re.finditer(r'^LAP (\d+) 1: (.*)$', text, re.M):
        toks = []
        for t in m.group(2).split(' | '):
            kind, _, rest = t.partition(' ')
            toks.append((kind, rest.split(' + ') if rest else []))
        out[int(m.group(1))] = toks
    return out


def video_laps():
    out = {}
    for line in open(os.path.join(HERE, '..', '..', 'docs', 'PC_LAPS.md')):
        m = re.match(r'\| (\d{3}) \| (\d+) \| (\d+) \|', line)
        if m: out[int(m.group(1))] = int(m.group(2))
    return out


def model(L, toks, verbose=False):
    """the legs of one lap: (kind, text, ticks) — kinds walk / door / action / intro / ?"""
    legs = []
    room, x, y = L.start
    occupied = None      # the container object the neighbour sits in
    current = None       # the object of the last GOTO / ENTER (the target of a bare ACTION)
    first = True

    def base_of(objs):
        b = [o for o in objs if o not in L.tricks]
        return (b or objs or [None])[-1]

    def walk_to(room2, x2, y2, what):
        nonlocal room, x, y
        r = L.route(room, room2)
        if r is None:
            legs.append(('?', 'no route %s -> %s (%s)' % (room, room2, what), 0)); room, x, y = room2, x2, y2; return
        for d_out, d_in in r:
            xo, yo = L.door_point(d_out); xi, yi = L.door_point(d_in, out=True)
            t = L.walk_ticks(xo - x, yo - y); legs.append(('walk', '%s %d/%d -> %s %d/%d' % (room, x, y, d_out, xo, yo), t))
            t_out = L.action_ticks(d_out, 'enter') or 0; t_in = L.action_ticks(d_in, 'leave') or 0
            legs.append(('door', '%s enter %d + %s leave %d' % (d_out, t_out, d_in, t_in), t_out + t_in))
            room, x, y = d_in.split('/')[0], xi, yi
        t = L.walk_ticks(x2 - x, y2 - y); legs.append(('walk', '%s %d/%d -> %s %d/%d' % (room, x, y, what, x2, y2), t)); x, y = x2, y2

    def leave(obj=None):
        nonlocal occupied
        obj = obj or occupied
        if obj:
            t = L.action_ticks(obj, 'leave') or 0; legs.append(('action', '%s leave' % obj, t)); occupied = None

    def enter(obj):
        nonlocal occupied
        t = L.action_ticks(obj, 'enter') or 0; legs.append(('action', '%s enter' % obj, t)); occupied = obj

    def goto(obj):
        nonlocal room, x, y, current, first
        pt = L.object_point(obj)
        if pt is None: legs.append(('?', 'GOTO %s: no hotspot' % obj, 0)); return False
        r2, x2, y2 = pt
        if first:
            legs.append(('intro', 'start %s %d/%d -> %s' % (room, x, y, obj), 0)); room, x, y = r2, x2, y2; first = False
        else:
            if occupied and occupied != obj: leave()
            walk_to(r2, x2, y2, obj)
        current = obj
        return True

    for kind, strs in toks:
        objs = [s for s in strs if '/' in s]
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
            if goto(obj) and kind != 'GOTO' and L.action_ticks(obj, 'enter') is not None and occupied != obj:
                if not (len(legs) == 1 and legs[0][0] == 'intro'): enter(obj)
                else: occupied = obj
        elif kind == 'LEAVE':
            leave(base_of(objs))
        elif kind == 'GOTO2':
            r2 = strs[-1] if strs else None
            if r2 in L.rooms:
                if occupied: leave()
                rt = L.route(room, r2)
                if rt: walk_to(r2, *L.door_point(rt[-1][1], out=True), 'room ' + r2)
            else:
                legs.append(('?', 'GOTO2 %s' % ' + '.join(strs), 0))
        elif kind == 'ACTION':
            acts = [s for s in strs if '/' not in s and s not in ('neighbor', 'woody', 'inv')]
            if not acts: continue
            name = acts[0]
            b = base_of(objs)
            cands = ([b] if b else []) + [o for o in objs if o != b] + ([current] if current else [])
            t = None; used = None
            for o in cands:
                t = L.action_ticks(o, name)
                if t is not None: used = o; break
            if t is None:
                legs.append(('?', 'ACTION %s on %s: no time' % (name, ' + '.join(objs) or current), 0))
            else:
                legs.append(('action', '%s %s' % (used, name), t))
    # the lap closes on the first station's enter; its leave opens the next lap
    return legs


def main(argv):
    verbose = '-v' in argv
    args = [a for a in argv[1:] if not a.startswith('-')]
    levels = [int(a) for a in args] or list(range(101, 115))
    cache = os.environ.get('LAP_TOKENS')
    toks = tokens_of(levels, cache)
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
            n, L.folder, secs, by.get('walk', 0) / TICK, by.get('door', 0) / TICK, by.get('action', 0) / TICK,
            '%d s' % v if v else '-', delta, ('  (%d unknown)' % unknown) if unknown else ''))
        if verbose:
            for kind, text, t in legs:
                print('     %-6s %4d  %s' % (kind, t, text))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
