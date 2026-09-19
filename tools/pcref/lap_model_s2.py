#!/usr/bin/env python3
"""The Season 2 neighbour's lap by code and data — GameLogic.dll's level scripts.

    python3 tools/pcref/lap_model_s2.py [201 ...]     # the untricked lap per step

A Season 2 level script is a chain of step functions (tools/pcref/
routine_order_s2.py); this walks the chain symbolically along the untricked
path and times the sequence each step builds from the level data, as
tools/pcref/lap_model.py does for Season 1:

- presence: level.xml's objects, actors and doors with visible="true"; the
  steps' own hides (fcn.10042b9e) and shows (fcn.10043d66) and the switch
  elements change it as the lap runs;
- the branches: IsVariant (fcn.1000fb6e) is the first present of its
  objects, fcn.1000ec67 isObjectPresent, fcn.100585c0 a name compare, a
  GoTo (fcn.1000e3e0) is not interrupted; the zero flag is followed across
  instructions; an event subscription (fcn.1000e7f2) hands over to the step
  it pushes, and a step that stores no next one is a poll (a trigger latch
  such as fcn.10013269, another actor's state), re-run as passed;
- the sequence elements (appended by fcn.1000ae19, or the builder API
  fcn.1000efcd ... fcn.1001000a of the later levels): DoAction
  (fcn.10002cd5) lasts its objects.xml `time`, or `auto` = the frames of the
  actor's animation, else the object's (an object's own action, actor = the
  object or another actor, the same way); fcn.10006bd4 is the object's
  `enter` and fcn.10006c2e its `leave` (the hideouts); the message elements
  — fcn.1000f499, fcn.1000f8cd (an object's animation), fcn.1000f41f, the
  switch fcn.1000f6c7 (hide the first, show the second), fcn.1000f82b (hide),
  fcn.1000f779 (show), fcn.1000f5c9 — run and return at once (their run
  methods return 1).

The bars: fcn.1000e7f2 walks to a `neighbor_hideout` object, enters it
(fcn.10006bd4) and makes fcn.1000b154's object (vtable 0x100ab710, update
0x1000b312), which counts its +0xc up to the pushed ticks +8 once a level
tick while the object is there (the progress bar, counter x 100 / ticks)
and then hands over to the pushed continuation: 212's bench `sleep` 60
ticks, 209's curtain and 208's platform `inactive` 120 and 60, 202's mat,
207's and 210's deck chairs `sleep` 120. `code_stays` pairs the parts with
the mobile routine items (PAIRS).

The walks (walk_ticks) are GameLogic's: the GoTo's route is the path finder
of fcn.1000a711 -> fcn.1000a421 / fcn.1000a12d, a Dijkstra over the rooms whose
hop costs the Manhattan distance to the near door's `<actor>` hotspot plus the
<neighbor> record's `costs` (500 on every record), the hop into the target room
the far door's distance to the target as well (Geometry.route); per hop the
actor walks to the near door's `<actor>_in` and passes the pair in one step
(vtable 0x100ab1b8: the doors' enter + leave where the near door has an enter
action for the actor, else a movement straight to the far `<actor>_out`,
Geometry.door_pass); a movement steps one axis a tick (fcn.10009215) at the
gait's records — mg0 / mg2 3 px up and down, mg1 / mg3 8 px along, nothing
writes the stair gait 7 for the neighbour — through the waypoints of
fcn.10009177: off the floor line and off the target's x to the floor first,
then along it, then straight to the target (Geometry.leg). The first
horizontal tick from the stand ms1 / ms3 adds the record's `start`
(0x10009332), at most a tick a walk, not counted.

Coverage (2026-09-23): the untricked lap closes on 203, 206, 208, 209, 211,
212, 213 and 214 (its hatch behind the step's own byte, its bouquet behind
IsVariant's null test — both read since the same evening); 201 (the
tutorial), 202, 204, 205, 207 and 210 stop at a step whose handover comes
from another actor's script. Not modelled: 206's and 214's waits on the
Mother, 213's polls on Olga's picnic and bull ride, 209's fakir `spit`. With
the walks the laps come to 105 s (203), 85.5 (208), 104 (209), 85 (211), 124
(212), 123 (213) and 90.3 (214) against the PC video's 84-112, 86, 97, 85, 113,
136 and 91 (214's shower to shower, docs/PC_LAPS_DETAIL.md) —
the video's stays (pc_durations_s2.py) held the walk the port's geometry did
not have until the door passes and the station runs were carried
(tools/pcref/pc_walks_s2.py); code_stays hands the profile the code's.
"""
import re, json, bisect, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from tools.pcref import canon
DUMP = os.path.expanduser('~/nfh-bench/pcref/r2/nfh2_gamelogic_text.txt')
G2 = json.load(open(os.path.join(HERE, 'exe', 'nfh2_gamelogic_globals.json')))
L = open(DUMP).read().split('\n')
addr = {}
for i, l in enumerate(L):
    m = re.match(r'(0x[0-9a-f]{8}) ', l)
    if m: addr[int(m.group(1), 16)] = i
keys = sorted(addr)
def at(a): return addr[keys[bisect.bisect_left(keys, a)]]
def ins(k):
    m = re.match(r'(0x[0-9a-f]{8})\s+[0-9a-f.]+\s+(.*)', L[k].strip())
    return (int(m.group(1), 16), m.group(2).strip()) if m else (None, None)
def gname(h): return G2.get(h, h)
ELEM = {'fcn.10002cd5': 'DO', 'fcn.1000f6c7': 'SWITCH', 'fcn.1000f977': 'SHOUT', 'fcn.10006c2e': 'E6c2e',
        'fcn.1000ebbf': 'Eebbf', 'fcn.1000f82b': 'Ef82b', 'fcn.1000f8cd': 'Ef8cd', 'fcn.1000f51a': 'Ef51a',
        'fcn.10006bd4': 'E6bd4', 'fcn.1000f779': 'Ef779', 'fcn.1000fac4': 'Efac4', 'fcn.10002f40': 'E2f40',
        'fcn.1000f5c9': 'SET', 'fcn.1000f41f': 'Ef41f', 'fcn.1000f499': 'Ef499', 'fcn.1000807f': 'E807f',
        'fcn.100080e1': 'RUNGO',
        # the builder API of the later scripts (213, 214, ...): each wraps one of the above
        # and appends it (fcn.1000ef28)
        'fcn.1000efcd': 'DO', 'fcn.1000f03c': 'Eebbf', 'fcn.1000f08e': 'E6bd4', 'fcn.1000f0f4': 'E6c2e',
        'fcn.1000fd91': 'Ef82b', 'fcn.1000fdee': 'Ef779', 'fcn.1000fe66': 'SWITCH', 'fcn.1000fede': 'SHOUT',
        'fcn.1000ffb8': 'Ef51a', 'fcn.1001000a': 'Ef8cd'}
class Level:
    def __init__(self, n):
        self.n = n
        pc = canon.pc_level(n)
        lvx = canon.read('%s/nfh2/x/%s/level.xml' % (canon.ROOT, pc['folder']))
        self.present = set()
        for m in re.finditer(r'<(?:object|actor|door) ([^>]*)>', lvx):
            a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            if a.get('visible', 'true') == 'true':
                self.present.add(a['name'].replace('/', '_'))
    def is_present(self, name):
        return name.replace('/', '_') in self.present
def run_step(lv, start, bytevars, maxn=4000, trace=False, unknown=0):
    """one step: returns (events, next)"""
    k = at(start); seen = set(); ev = []; nxt = None
    slots = []; al = None; vars_ = {}; regs = {}; zf = None
    for _ in range(maxn):
        a, t = ins(k)
        if t is None: k += 1; continue
        if (k, al) in seen: break
        seen.add((k, al))
        if trace: print('   %x %s   al=%s' % (a, t, al))
        if t.startswith('ret'): return ev, nxt
        m = re.match(r'mov dword \[e[a-z]+ \+ 8\], (?:0x|fcn\.)(100[0-9a-f]{5})$', t)
        if m: nxt = int(m.group(1), 16)
        m = re.match(r'mov (e[a-z]x), (?:0x|fcn\.)(100[0-9a-f]{5})$', t)
        if m: regs[m.group(1)] = int(m.group(2), 16)
        m = re.match(r'mov dword \[e[a-z]+ \+ 8\], (e[a-z]x)$', t)
        if m and m.group(1) in regs: nxt = regs[m.group(1)]
        m = re.match(r'mov ecx, dword \[(0x100[de][0-9a-f]{4})\]$', t)
        if m: slots.append(('g', gname(m.group(1))))
        m = re.match(r'mov ecx, dword \[ebp - (0x[0-9a-f]+)\]$', t)
        if m: slots.append(('v', vars_.get(m.group(1), '$' + m.group(1))))
        m = re.match(r'push (0x[0-9a-f]+|[0-9]+)$', t)
        if m and not t.startswith('push 0x100'): slots.append(('i', int(m.group(1), 0)))
        m = re.match(r'push (?:0x|fcn\.)(100[0-3][0-9a-f]{4})$', t)
        if m: slots.append(('f', int(m.group(1), 16)))
        m = re.match(r'lea eax, \[ebp - (0x[0-9a-f]+)\]$', t)
        if m: slots.append(('o', m.group(1)))
        m = re.match(r'mov byte \[ebp - (0x[0-9a-f]+)\], al$', t)
        if m: bytevars[m.group(1)] = al
        m = re.match(r'mov byte \[e(?:di|si|bx) \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|[0-9]+)$', t)
        if m: bytevars['obj' + m.group(1)] = int(m.group(2), 0)
        m = re.match(r'call (fcn\.[0-9a-f]+)', t)
        if m:
            fn = m.group(1)
            outs = [s for s in slots if s[0] == 'o']
            names = [s[1] for s in slots if s[0] in ('g', 'v')]
            imms = [s[1] for s in slots if s[0] == 'i']
            if fn == 'fcn.1000fb6e':
                # IsVariant(out, level, a, b, c...): the first present; the args pushed last-first
                cands = list(reversed(names))
                pick = next((c for c in cands if lv.is_present(c)), cands[-1] if cands else None)
                if outs: vars_[outs[-1][1]] = pick
                ev.append(('IFVAR', cands, pick))
                al = None
            elif fn == 'fcn.1000ec67':
                nm = names[-1] if names else None
                al = 1 if (nm and lv.is_present(nm)) else 0
                if not al and nm and unknown:
                    # a poll's re-run: the object it waits for has been shown
                    # by another actor's script (202's swim step waits for the
                    # `sub` Olga switches into the sea, 0x100224a8)
                    al = 1
                    lv.present.add(nm.replace('/', '_'))
                ev.append(('PRESENT', nm, al))
            elif fn == 'fcn.100585c0':
                al = 1 if len(names) >= 2 and names[-1].replace('/', '_') == names[-2].replace('/', '_') else 0
                ev.append(('STREQ', names[-2:], al))
            elif fn == 'fcn.1000e3e0':
                ev.append(('GO', names[-1] if names else None)); al = 0
            elif fn == 'fcn.1000e7f2':
                # a timed stay (the bar): fcn.1000b154's object (vtable 0x100ab710,
                # update 0x1000b312) counts its +0xc up to the pushed ticks +8 a
                # level tick while the object is there, showing counter x 100 /
                # ticks, and at the end hands over to the continuation it pushes
                fs = [i for i, x in enumerate(slots) if x[0] == 'f']
                ticks = None
                if fs:
                    nxt = slots[fs[-1]][1]
                    after = [x[1] for x in slots[fs[-1] + 1:] if x[0] == 'i']
                    ticks = after[0] if after else None
                ev.append(('WAITEVENT', names, ticks)); al = None
            elif fn == 'fcn.100422a5':
                ev.append(('IC', names)); al = None
            elif fn == 'fcn.10042b9e':
                # the level hides an object (the shoe mat's empty variant, 209)
                nm = names[-1] if names else None
                if nm: lv.present.discard(nm.replace('/', '_'))
                ev.append(('HIDE', nm)); al = None
            elif fn == 'fcn.10043d66':
                # and shows one in a room (its first argument)
                nm = names[-1] if names else None
                if nm: lv.present.add(nm.replace('/', '_'))
                ev.append(('SHOW', nm)); al = None
            elif fn in ELEM:
                args = list(reversed(names))
                kind = ELEM[fn]
                # the switches take effect when the sequence runs, before the next step
                if kind == 'SWITCH' and len(args) >= 2:
                    lv.present.discard(args[0].replace('/', '_')); lv.present.add(args[1].replace('/', '_'))
                elif kind == 'Ef82b' and args:
                    lv.present.discard(args[0].replace('/', '_'))
                elif kind == 'Ef779' and args:
                    lv.present.add(args[0].replace('/', '_'))
                ev.append((kind, args, imms)); al = None
            elif fn in ('fcn.1000aeb8', 'fcn.1000ae19', 'fcn.100088be', 'fcn.10059e30', 'fcn.10009b58',
                        'fcn.1000ee93', 'fcn.1000eec6', 'fcn.1000ef28', 'fcn.10049216'):
                pass
            else:
                al = unknown   # an unknown predicate (a trigger latch, another actor's
                               # state) reads false, or true on a poll's re-run
            slots = []
            k += 1; continue
        # the flags: ZF from the tests the scripts branch on; any other
        # flag-setting instruction leaves them unknown
        if t == 'test al, al' or re.match(r'cmp al, (bl|0)$', t):
            zf = None if al is None else (al == 0); k += 1; continue
        m = re.match(r'cmp byte \[ebp - (0x[0-9a-f]+)\], (bl|0)$', t)
        if m:
            v = bytevars.get(m.group(1)); zf = None if v is None else (v == 0); k += 1; continue
        m = re.match(r'cmp byte \[e(?:di|si|bx|cx) \+ (0x[0-9a-f]+)\], (bl|0)$', t)
        if m:
            # the step object's own byte (ecx is the step at its entry: 214's
            # hatch test at 0x1003a513)
            zf = (bytevars.get('obj' + m.group(1)) or 0) == 0; k += 1; continue
        m = re.match(r'cmp dword \[ebp - (0x[0-9a-f]+)\], (ebx|0)$', t)
        if m and m.group(1) in vars_:
            # IsVariant's out against null: set when one of its objects is
            # present (214's bouquet at 0x1003b48f)
            zf = vars_[m.group(1)] is None or not lv.is_present(vars_[m.group(1)]); k += 1; continue
        if re.match(r'(cmp|test|add|sub|and|or|xor|inc|dec|neg|sbb|adc|shl|shr|sar) ', t):
            zf = None
        m = re.match(r'j(e|ne|z|nz) (0x[0-9a-f]+)$', t)
        if m:
            if zf is not None:
                take = zf if m.group(1) in ('e', 'z') else (not zf)
                if take: k = at(int(m.group(2), 16)); continue
            k += 1; continue
        m = re.match(r'jmp (0x[0-9a-f]+)$', t)
        if m: k = at(int(m.group(1), 16)); continue
        k += 1
    return ev, nxt
def walk(lv, start, maxsteps=80, trace=False):
    steps = []; cur = start; seenkeys = {}; bytevars = {}
    for _ in range(maxsteps):
        key = (cur, tuple(sorted((k, v) for k, v in bytevars.items() if k.startswith('obj'))))
        if key in seenkeys: return steps, seenkeys[key]
        seenkeys[key] = len(steps)
        ev, nxt = run_step(lv, cur, dict(bytevars), trace=trace)
        if nxt is None or nxt == cur:
            # a poll: the step re-runs each tick until its trigger holds (a latch
            # fcn.10013269, another actor's state) — the pass that hands over
            ev2, nxt2 = run_step(lv, cur, bytevars, trace=trace, unknown=1)
            if nxt2 is not None and nxt2 != cur:
                ev, nxt = [('POLL',)] + ev2, nxt2
            else:
                run_step(lv, cur, bytevars)
        else:
            run_step(lv, cur, bytevars)
        steps.append((cur, ev, nxt))
        if nxt is None: return steps, None
        cur = nxt
    return steps, None
def level_start(n):
    """the level's main routine step, found as routine_order_s2.py does: the function whose
    GoTo/DoAction names best match the level's objects"""
    import collections
    hdrs = []
    hdr = re.compile(r'^\s*(\d+): (fcn\.[0-9a-f]+)')
    for i, l in enumerate(L):
        h = hdr.match(l)
        if h: hdrs.append((i, h.group(2)))
    pc = canon.pc_level(n)
    objs = set(x.replace('/', '_') for x in re.findall(r'<object name="([^"]+)"', canon.read('%s/nfh2/x/%s/objects.xml' % (canon.ROOT, pc['folder']))))
    best = (0, None, None)
    for j, (i0, name) in enumerate(hdrs):
        i1 = hdrs[j + 1][0] if j + 1 < len(hdrs) else len(L)
        cnt = 0
        for k in range(i0, i1):
            if 'call fcn.1000e3e0' in L[k] or 'call fcn.10002cd5' in L[k]:
                for jj in range(k - 1, k - 40, -1):
                    ms = re.findall(r'0x100[de][0-9a-f]{4}', L[jj])
                    hit = [G2.get(x) for x in ms if G2.get(x) in objs]
                    if hit: cnt += 1; break
        if cnt > best[0]: best = (cnt, name, i0)
    k0 = best[2]
    while 'call fcn.1000e3e0' not in L[k0] and 'call fcn.10002cd5' not in L[k0]: k0 += 1
    while k0 > 0 and 'call fcn.10059e30' not in L[k0]: k0 -= 1
    return ins(k0)[0] - 5


# -- durations (the Season 1 rule of tools/pcref/lap_model.py) ----------------------
def _frames_of(text):
    out = {}
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', text, re.S):
        for am in re.finditer(r'<animation name="([^"]+)"[^>]*>(.*?)</animation>', om.group(2), re.S):
            out[(om.group(1), am.group(1))] = len(re.findall(r'<frame', am.group(2)))
    return out


def _actions_of(text):
    """{object or actor name: {'gfx': .., 'act': {(actor, name): attrs}}}"""
    out = {}
    for om in re.finditer(r'<(object|actor|door) name="([^"]+)"([^>]*?)(/?)>', text):
        if om.group(4):
            continue                     # a self-closing tag holds no actions
        end = text.find('</%s>' % om.group(1), om.end())
        body = text[om.end():end if end >= 0 else len(text)]
        gfx = dict(re.findall(r'(\w+)="([^"]*)"', om.group(3))).get('gfx')
        e = out.setdefault(om.group(2), {'gfx': gfx, 'act': {}, 'flags': set()})
        e['flags'] |= set(re.findall(r'<flag name="([^"]+)"', body))
        for a in re.finditer(r'<action ([^>]*)>', body):
            at = dict(re.findall(r'(\w+)="([^"]*)"', a.group(1)))
            e['act'][(at.get('actor'), at.get('name'))] = at
    return out


class Data:
    def __init__(self, n):
        folder = canon.pc_level(n)['folder']
        X = '%s/nfh2/x' % canon.ROOT
        self.objects = _actions_of(canon.read('%s/%s/objects.xml' % (X, folder)))
        self.generic = _actions_of(canon.read('%s/generic/objects.xml' % X))
        self.frames = _frames_of(canon.read('%s/%s/anims.xml' % (X, folder)))
        self.gframes = _frames_of(canon.read('%s/generic/anims.xml' % X))
        # the code's constants spell 'room/object' as 'room_object'; rooms have
        # underscores of their own (fire_fakir, tadj_mahal, coal_area)
        self.real = {k.replace('/', '_'): k for k in self.objects}

    def flags_of(self, obj):
        """the object's objects.xml flags"""
        e = self.objects.get(self.real.get(obj, obj)) or self.generic.get(obj) or {}
        return e.get('flags') or set()

    def action_ticks(self, obj, name, actor='neighbor'):
        """the ticks of an action: time="N", or auto = the frames of the actor's
        animation (the level's anims.xml, else generic/anims.xml), else of the
        object's (under its gfx); None if unknown"""
        o = self.real.get(obj, obj)
        e = self.objects.get(o) or self.generic.get(obj)
        if e is None:
            return None
        if (actor, name) not in e['act']:
            # an object's own action (the fakir's `play`: actor = the object)
            own = [v for (ac, nm), v in e['act'].items() if nm == name and ac == o] \
                or [v for (ac, nm), v in e['act'].items() if nm == name and ac not in ('woody',)]
            if not own:
                return None
            a = own[0]
            t = a.get('time', 'auto')
            if t.isdigit():
                return int(t)
            # auto: the action's actor's animation first (202's kid plays
            # play_remote while the sub dives), else the object's
            ac, aa = a.get('actor'), a.get('actoranim')
            if ac and ac != o and aa and aa not in ('inv', 'ms'):
                f = self.frames.get((ac, aa)) or self.gframes.get((ac, aa))
                if f:
                    return f
            g = e['gfx'] or o
            for an in (a.get('actoranim'), a.get('objanim')):
                if an and an not in ('inv', 'ms'):
                    f = self.frames.get((g, an)) or self.frames.get((o, an))
                    if f:
                        return f
            return None
        a = e['act'][(actor, name)]
        t = a.get('time', 'auto')
        if t.isdigit():
            return int(t)
        aa = a.get('actoranim', 'inv')
        if aa not in ('inv', 'ms', ''):
            f = self.frames.get((actor, aa)) or self.gframes.get((actor, aa))
            if f:
                return f
        oa = a.get('objanim', '')
        if oa not in ('', 'ms', 'inv'):
            g = e['gfx'] or o
            f = self.frames.get((g, oa)) or self.frames.get((o, oa))
            if f:
                return f
        return None


INSTANT = {'Ef499', 'Ef8cd', 'Ef41f', 'SWITCH', 'SET'}


def station_ticks(d, ev, ctx=None):
    """the step's parts [(object, action, ticks)] — DoActions, the enter/leave of
    E6bd4/E6c2e, a bar's enter and ticks (action 'bar'); the message elements
    instant; the rest unknown (ticks None). `ctx` carries the last hideout
    across steps (a leave whose object is a local of an earlier step)"""
    ctx = {} if ctx is None else ctx
    parts = []
    for e in ev:
        k = e[0]
        if k == 'DO':
            names = [x for x in e[1] if not x.startswith('$')]
            if len(names) >= 2:
                parts.append((names[0], names[1], d.action_ticks(names[0], names[1])))
            else:
                parts.append((names[0] if names else '?', '?', None))
        elif k in ('E6bd4', 'E6c2e'):
            names = [x for x in e[1] if not x.startswith('$')]
            if not names and ctx.get('hideout'):
                names = [ctx['hideout']]
            act = 'enter' if k == 'E6bd4' else 'leave'
            if names: ctx['hideout'] = names[0]
            ctx['inside'] = names[0] if (names and act == 'enter') else None
            parts.append((names[0] if names else '?', act, d.action_ticks(names[0], act) if names else None))
        elif k == 'WAITEVENT' and isinstance(e[2], int):
            # fcn.1000e7f2: to the hideout, its `enter` (fcn.10006bd4), then the bar
            # the hideout the step has just shown, when it shows one (202's mat
            # step swaps beachright/mat_hn for mat_hn_guarded, 0x10022d86-
            # 0x10022db9, and the bar holds him in that one), else the named one
            shown = [x[1] for x in ev[:ev.index(e)] if x[0] == 'SHOW' and x[1]]
            obj = next((x for x in reversed(shown) if 'neighbor_hideout' in d.flags_of(x)), None) \
                or next((x for x in e[1] if d.real.get(x) or x in d.objects), None)
            # (already inside — 209's curtain entered by the step — no second enter:
            # the helper's first branch makes the bar at once)
            if obj and ctx.get('inside') != obj:
                t = d.action_ticks(obj, 'enter')
                if t is not None:
                    parts.append((obj, 'enter', t))
            if obj: ctx['hideout'] = obj; ctx['inside'] = obj
            parts.append((obj or '?', 'bar', e[2]))
        elif k in ('WAITEVENT', 'POLL', 'SHOUT', 'Eebbf', 'Ef82b', 'Ef51a', 'Ef779', 'Efac4', 'E2f40', 'E807f', 'RUNGO'):
            parts.append(('-', k, None))
    return parts


# the step a lap starts from where it is not the level's first: 210's lap runs
# from the Mother's `order` (his handler 0x1001b4f6 -> 0x1001aecc: the walk to
# Fifi and her `tickle`, then the take 0x1001aac8, the level's first step)
LAP_START = {210: 0x1001aecc}


def lap_steps(n):
    """the untricked lap: [(index, step address, icon, objects, parts)] and the
    loop's first index (None when the walk stops)"""
    d = Data(n)
    st = LAP_START.get(n) or level_start(n); lv = Level(n)
    steps, loop = walk(lv, st)
    out = []; ctx = {}
    for i, (cur, ev, nxt) in enumerate(steps):
        ic = [e[1] for e in ev if e[0] == 'IC']
        objs = set()
        for e in ev:
            if len(e) < 2:
                continue
            for x in (e[1] if isinstance(e[1], list) else [e[1]]):
                if isinstance(x, str) and not x.startswith('$'):
                    objs.add(x)
        out.append((i, cur, (ic[0][0] if ic and ic[0] else '-'), objs, station_ticks(d, ev, ctx)))
    return out, loop


def short(obj):
    return obj.split('_', 1)[-1] if '_' in obj else obj


def report(n):
    rows, loop = lap_steps(n)
    print('== %d  loop at step %s' % (n, loop))
    lap = 0
    for i, cur, icon, objs, parts in rows:
        tot = sum(t for _o, _a, t in parts if t is not None)
        unk = [a for _o, a, t in parts if t is None]
        if loop is not None and i >= loop: lap += tot
        print('  %s %-12s %6.2f s  %s%s' % ('>>' if i == loop else '  ', icon, tot / 12.0,
              ', '.join('%s.%s %s' % (short(o), a, '?' if t is None else round(t / 12.0, 2)) for o, a, t in parts),
              '  [unknown: %s]' % ', '.join(unk) if unk else ''))
    print("  the lap's actions: %.1f s" % (lap / 12.0))


if __name__ == '__main__':
    for n in [int(x) for x in sys.argv[1:]] or range(201, 215):
        report(n)


# -- the walks (GameLogic.dll) -------------------------------------------------------
class Geometry:
    """the level's rooms (level.xml <room>: the floor line path1-path2 at path1's y,
    its <neighbor> records — the far room, the door pair, the `costs`), the
    placements (an object's room is the <room> block it stands in; a hotspot is
    relative to its object's level.xml position) and the actors' speed records
    of generic/objects.xml"""
    def __init__(self, n):
        folder = canon.pc_level(n)['folder']
        X = '%s/nfh2/x' % canon.ROOT
        lvx = canon.read('%s/%s/level.xml' % (X, folder))
        self.ob = canon.read('%s/%s/objects.xml' % (X, folder))
        go = canon.read('%s/generic/objects.xml' % X)
        self.speed = {}
        for am in re.finditer(r'<actor name="(\w+)"[^>]*>(.*?)</actor>', go, re.S):
            recs = [dict(re.findall(r'(\w+)="([^"]*)"', t)) for t in re.findall(r'<speed\b[^>]*/>', am.group(2))]
            if recs:
                self.speed[am.group(1)] = {r['name']: (int(r['speed']), int(r['start'])) for r in recs}
        self.rooms = {}
        # an object's room is the level.xml <room> it is placed in — not its
        # name's prefix (203: 'wallleft/melons' stands in groundleft)
        self.room = {}
        for rm in re.finditer(r'<room name="(\w+)" offset="[^"]+" path1="([^"]+)" path2="([^"]+)">(.*?)</room>', lvx, re.S):
            x1, y1 = map(int, rm.group(2).split('/')); x2, _ = map(int, rm.group(3).split('/'))
            nb = [dict(re.findall(r'(\w+)="([^"]*)"', t)) for t in re.findall(r'<neighbor ([^>]*)/>', rm.group(4))]
            self.rooms[rm.group(1)] = {'x1': min(x1, x2), 'x2': max(x1, x2), 'y': y1, 'nb': nb}
            for on in re.findall(r'<(?:object|actor|door) name="([^"]+)"', rm.group(4)):
                self.room[on] = rm.group(1)
        self.pos = {}
        for m2 in re.finditer(r'<(?:object|door|actor) ([^>]*)>', lvx):
            at = dict(re.findall(r'(\w+)="([^"]*)"', m2.group(1)))
            if 'name' in at and 'position' in at:
                self.pos[at['name']] = tuple(map(int, at['position'].split('/')))
        self.hot = {}
        for om in re.finditer(r'<(object|door|actor) name="([^"]+)"[^>]*?(/?)>', self.ob):
            if om.group(3):
                continue
            end = self.ob.find('</%s>' % om.group(1), om.end())
            body = self.ob[om.end():end]
            self.hot[om.group(2)] = {h: tuple(map(int, o.split('/'))) for h, o in re.findall(r'<hotspot name="(\w+)" offset="([^"]+)"', body)}
        # the doors whose pass is the actor's enter + leave (fcn.10003647):
        # {door: {actor: True}}
        self.door_acts = {}
        for dm in re.finditer(r'<door name="([^"]+)"[^>]*>(.*?)</door>', self.ob, re.S):
            self.door_acts[dm.group(1)] = set(re.findall(r'<action name="enter" actor="(\w+)"', dm.group(2)))

    def room_of(self, obj):
        return self.room.get(obj) or (obj.split('/')[0] if '/' in obj else None)

    def floor(self, room):
        return self.rooms[room]['y']

    def point(self, obj, key='neighbor', exact=False):
        h = self.hot.get(obj) or {}
        p = h.get(key) if exact else (h.get(key) or h.get('neighbor') or h.get('woody'))
        if p is None:
            return None
        ox, oy = self.pos.get(obj, (0, 0))
        return p[0] + ox, p[1] + oy

    def route(self, room, pos, room2, target, actor='neighbor'):
        """the path finder (fcn.1000a421 over fcn.1000a12d, from the GoTo's
        fcn.1000a711): Dijkstra over the rooms. A hop out of a node costs the
        Manhattan distance from the node's point to the near door's `<actor>`
        hotspot (fcn.10049e01) plus the record's `costs`, and a hop into the
        target room the far door's hotspot's distance to the target as well
        (fcn.1000a5b7, the position mode); a room is entered at the far door's
        hotspot; the open list is kept sorted by cost, a new node going before
        the equal ones (fcn.1000a097), a known room re-parented only for a lower
        cost; the goal is tested as a node is popped. The GoTo then takes, per
        pair of rooms, the room's first <neighbor> record naming the next one
        (fcn.1004ca13). Returns [(near door, far door)] or None."""
        if room == room2:
            return []
        start = {'room': room, 'pos': pos, 'cost': 0, 'parent': None}
        nodes = {room: start}
        opn = [start]

        def insert(nd):
            k = 0
            while k < len(opn) and nd['cost'] > opn[k]['cost']:
                k += 1
            opn.insert(k, nd)
        while opn:
            nd = opn.pop(0)
            if nd['room'] == room2:
                rooms = []
                while nd is not None:
                    rooms.append(nd['room']); nd = nd['parent']
                rooms.reverse()
                out = []
                for ra, rb in zip(rooms, rooms[1:]):
                    rec = next(r for r in self.rooms[ra]['nb'] if r['name'] == rb)
                    out.append((rec['doorin'], rec['doorout']))
                return out
            for rec in self.rooms.get(nd['room'], {}).get('nb', []):
                far = rec['name']
                a = self.point(rec.get('doorin'), actor, exact=True)
                b = self.point(rec.get('doorout'), actor, exact=True)
                if a is None or b is None or far not in self.rooms:
                    continue
                c = abs(nd['pos'][1] - a[1]) + abs(nd['pos'][0] - a[0]) + int(rec.get('costs', 0))
                if far == room2 and target is not None:
                    c += abs(b[1] - target[1]) + abs(b[0] - target[0])
                ex = nodes.get(far)
                if ex is not None:
                    if ex['cost'] > nd['cost'] + c:
                        ex.update(cost=nd['cost'] + c, parent=nd, pos=b)
                        if ex in opn:
                            opn.remove(ex)
                        insert(ex)
                    continue
                new = {'room': far, 'pos': b, 'cost': nd['cost'] + c, 'parent': nd}
                nodes[far] = new
                insert(new)
        return None

    def run(self, d, s):
        """ticks of one axis run of d px at s px a tick: the walk step
        (fcn.10009215) moves one axis a tick, clamped at the waypoint. The
        first horizontal tick of a walk that starts from the stand ms1/ms3
        adds the record's `start` (0x10009332) — at most a tick a walk, not
        counted here"""
        d = abs(d)
        return -(-d // s) if d else 0

    def leg(self, x, y, tx, ty, fy, actor='neighbor', gait='mg'):
        """a movement's ticks from (x, y) to (tx, ty) with floor line fy, by the
        waypoints of fcn.10009177 (+0x31 clear): off the floor and off the
        target's x, down or up to the floor first; along it to the target's x;
        then straight to the target"""
        sp = self.speed[actor]
        v = sp[gait + '0'][0]; vd = sp[gait + '2'][0]
        h = sp[gait + '1'][0]
        t = 0
        if y != fy and x != tx:
            t += self.run(fy - y, v if fy < y else vd); y = fy
        if x != tx:
            t += self.run(tx - x, h); x = tx
        t += self.run(ty - y, v if ty < y else vd)
        return t

    def door_pass(self, din, dout, actor='neighbor', gait='mg', data=None):
        """the door-pass step (vtable 0x100ab1b8, fcn.1000340b / 0x10003a19)
        after the walk to the near door's `<actor>_in`: the near door's `enter`
        and the far door's `leave` when the near door has an enter action for
        the actor (fcn.10003647, fcn.10003236: the actor placed at the far
        door's `<actor>_out` between them), else a movement straight from
        `<actor>_in` to the far door's `<actor>_out` whose floor line is the
        start's y (fcn.100037f8 -> fcn.100090bd). Returns (ticks, in, out)."""
        a = self.point(din, actor + '_in', exact=True)
        b = self.point(dout, actor + '_out', exact=True)
        if a is None or b is None:
            return None, a, b
        if actor in self.door_acts.get(din, ()):
            if data is None:
                return None, a, b
            t1 = data.action_ticks(din, 'enter', actor)
            t2 = data.action_ticks(dout, 'leave', actor)
            return (None if t1 is None or t2 is None else t1 + t2), a, b
        return self.leg(a[0], a[1], b[0], b[1], a[1], actor, gait), a, b


def walk_ticks(g, frm, to, actor='neighbor', data=None, detail=None):
    """(room, x, y) -> an object's `<actor>` hotspot: the GoTo's route
    (Geometry.route), per hop the walk to the near door's `<actor>_in` along
    the room's floor (Geometry.leg) and the door pass (Geometry.door_pass),
    then the walk to the target. `detail` collects (kind, ticks) parts:
    'room' the in-room legs, 'pass' the door passes."""
    room, x, y = frm
    r2 = g.room_of(to); p2 = g.point(to, actor)
    if p2 is None or r2 not in g.rooms or room not in g.rooms:
        return None, frm
    rt = g.route(room, (x, y), r2, p2, actor)
    if rt is None:
        return None, frm
    t = 0
    for din, dout in rt:
        a = g.point(din, actor + '_in', exact=True)
        if a is None:
            return None, frm
        t1 = g.leg(x, y, a[0], a[1], g.floor(room), actor)
        t2, _a, b = g.door_pass(din, dout, actor, data=data)
        if t2 is None:
            return None, frm
        if detail is not None:
            detail.append(('room', t1)); detail.append(('pass %s' % din, t2))
        t += t1 + t2
        x, y = b; room = g.room_of(dout)
    t3 = g.leg(x, y, p2[0], p2[1], g.floor(room), actor)
    if detail is not None:
        detail.append(('room', t3))
    return t + t3, (r2, p2[0], p2[1])


def lap_estimate(n, verbose=False):
    """the lap's seconds: the stays of lap_steps plus the walks between the steps'
    targets (walk_ticks); None parts counted as 0 and reported"""
    d = Data(n); g = Geometry(n)
    st = level_start(n); lv = Level(n)
    steps, loop = walk(lv, st)
    if loop is None:
        return None
    ctx = {}
    pos = None; total = 0; walks = 0; stays = 0; unknown = []
    order = steps[loop:] + steps[:loop] + steps[loop:loop + 1]    # the lap, closed on its first step
    for k, (cur, ev, nxt) in enumerate(order):
        parts = station_ticks(d, ev, ctx)
        target = None
        for e in ev:
            if e[0] == 'GO':
                target = e[1] if e[1] and not str(e[1]).startswith('$') else None
                if target is None:
                    pick = [x[2] for x in ev if x[0] == 'IFVAR' and x[2] and not str(x[2]).startswith('$')]
                    dos = [x[1][0] for x in ev if x[0] == 'DO' and x[1] and not x[1][0].startswith('$') and x[1][0] != 'neighbor']
                    target = (pick or dos or [None])[0]
                break
        if target:
            real = d.real.get(target, target)
            if pos is None:
                p = g.point(real)
                pos = (g.room_of(real), p[0], p[1]) if p else None
            else:
                t, pos2 = walk_ticks(g, pos, real, data=d)
                if t is None:
                    unknown.append('walk to %s' % real)
                else:
                    if k > 0: walks += t
                    pos = pos2
                if verbose: print('   walk -> %-30s %5.1f s' % (real, (t or 0) / 12.0))
        if k == len(order) - 1:
            break            # the closing step: its walk ends the lap
        s = sum(t for _o, _a, t in parts if t is not None)
        unknown += ['%s.%s' % (short(o), a) for o, a, t in parts if t is None]
        stays += s
        if verbose: print('   stay %-30s %5.1f s' % ('+'.join('%s.%s' % (short(o), a) for o, a, _t in parts), s / 12.0))
    return (walks + stays) / 12.0, walks / 12.0, stays / 12.0, unknown


def video_laps():
    out = {}
    for line in open(os.path.join(os.path.dirname(os.path.dirname(HERE)), 'docs', 'PC_LAPS.md')):
        m = re.match(r'\| (2\d\d) [^|]*\|[^|]*\| ([^|]*) \|', line)
        if m:
            v = re.findall(r'\d+', m.group(2))
            if v: out[int(m.group(1))] = v
    return out


# the mobile stations against the code's parts, for the levels whose lap closes:
# item -> [(step selector, object suffix, action)]; a selector is a substring of
# one of the step's objects (None: any step)
PAIRS = {
    203: {'Microphone': [(None, 'stage', 'enter'), (None, 'stage', 'use'), (None, 'stage', 'leave')],
          'ToiletPaper': [(None, 'toilet', 'shit')], 'ToiletFlush': [(None, 'toilet', 'flush')],
          'Watermelon': [(None, 'melons', 'use')], 'Bicycle': [(None, 'bike', 'use')]},
    208: {'ArmsBowl': [('statue', 'neighbor', 'lookaround'), (None, 'statue', 'take')],
          'IndianPlatform': [(None, 'fakir', 'play'), (None, 'platform', 'enter'), (None, 'platform', 'bar'),
                             (None, 'fakir', 'stop')],
          'ShoeMachine': [(None, 'shoe_cleaner', 'use')],
          'AngryElephant': [('elephant', 'neighbor', 'lookaround'), (None, 'elephant', 'fool')]},
    209: {'Cow': [('cow', 'neighbor', 'lookaround'), (None, 'cow', 'ride')],
          'TadjMahal': [(None, 'curtain', 'enter'), (None, 'curtain', 'bar'), (None, 'curtain', 'leave')],
          'HotShoe': [(None, 'shoe_mat_empty', 'take')],
          'Coal': [(None, 'coal', 'walk')], 'IceCream': [(None, 'icecream_machine', 'take')]},
    211: {'Sweets': [(None, 'dish', 'use')], 'FishingRod': [(None, 'rod', 'use')],
          'LifeBoat': [('boat', 'neighbor', 'lookaround'), (None, 'boat', 'use')],
          'LifeJacket': [(None, 'lifevest', 'use')], 'DivingGear': [(None, 'diving', 'use')]},
    212: {'PreAztecThrone': [('hands', 'neighbor', 'lookaround')], 'AztecThrone': [(None, 'hands', 'sit')],
          'Whip': [(None, 'whip', 'use')], 'CigarBox': [(None, 'cigars', 'use')],
          'SleepBench': [(None, 'bank', 'enter'), (None, 'bank', 'bar'), (None, 'bank', 'leave')],
          'MechanicalBull': [(None, 'bullride', 'use')],
          'PreParrotLedge': [(None, 'cliff', 'enter')],
          'ParrotLedge': [(None, 'cliff', 'use'), (None, 'water', 'use'), (None, 'water_exit', 'leave')]},
    213: {'LiveBull': [(None, 'limberwall', 'use')],
          'PlantCarnivore': [('carnivore', 'neighbor', 'lookaround'), (None, 'carnivore', 'use')],
          'Tortilla': [(None, 'tortilla', 'use')], 'Pinata': [(None, 'pinata', 'use')],
          'CementBath': [('washingtub', 'neighbor', 'lookaround'), (None, 'washingtub', 'use')]},
    # the untricked lap: the hatch looked into open (the step's byte +0xe is
    # set only once the fish round has written it off), the shower, the
    # bouquet shown to Olga, the captain's door tried, the pistol played
    214: {'Hatch': [(None, 'hatch_open', 'use')], 'Shower': [(None, 'shipshower', 'use')],
          'Bouquet': [(None, 'bouquet', 'use')], 'CaptainDoor': [(None, 'door_closed', 'use')],
          'Pistol': [(None, 'pistol', 'use')]},
    # per visit (a list of part lists): the mobile's two BeerMat visits are his
    # lay-down (the prime) and the rest of the mat and the beer (the profile
    # times the mat and the swim per clip: pc_durations_s2.py CLIPS)
    202: {'BeerMat': [[(None, 'mat_hn_guarded', 'enter')],
                      [(None, 'mat_hn_guarded', 'bar'), (None, 'mat_hn_guarded', 'use'),
                       (None, 'mat_hn_guarded', 'leave')]],
          'BridgeRail': [('bridge', 'neighbor', 'lookaround'), (None, 'bridge', 'look')]},
    # his Fifi errands (the tickle and the take at her basket, the turban
    # shop, the elephant, the put back); the chair is timed per clip and waits
    # for the Mother's call (pc_durations_s2.py CLIPS, MotherWakeSleepBehavior)
    210: {'DogBasket': [(None, 'pool_fifi_sleep', 'tickle'), (None, 'pool_fifi_sleep', 'take')],
          'TurbanShop': [(None, 'fifi', 'put3'), (None, 'turbanshop', 'try_turban'), (None, 'fifi', 'take3')],
          'Elephant': [(None, 'fifi', 'put1'), (None, 'fifi', 'take1')],
          'DogBasketPut': [(None, 'pool_fifi_sleep', 'put')]},
}


# the levels whose unclosed walk still covers every station (code_stays)
OPEN_LAPS = (210,)


def code_stays(n):
    """{mobile item: seconds, or a list of seconds per visit} from the lap's parts
    by PAIRS[n]; an item whose part is missing or untimed is left out. A lap the
    walk does not close (210's: his chair waits for the Mother's call, a message
    the walk does not follow) is the walk from its start (LAP_START), each of
    its stations once"""
    rows, loop = lap_steps(n)
    if loop is None and n not in OPEN_LAPS:
        return {}
    lap = rows if loop is None else rows[loop:] + rows[:loop]
    used = set(); out = {}

    def ticks(sels):
        tot = 0
        for sel, osuf, act in sels:
            hit = None
            for i, cur, icon, objs, parts in lap:
                if sel and not any(sel in o for o in objs):
                    continue
                for j, (o, a, t) in enumerate(parts):
                    if (i, j) in used or a != act:
                        continue
                    if o == osuf or o.endswith('_' + osuf):
                        hit = (i, j, t); break
                if hit: break
            if hit is None or hit[2] is None:
                return None
            used.add(hit[:2]); tot += hit[2]
        return tot

    for item, sels in PAIRS.get(n, {}).items():
        if sels and isinstance(sels[0], list):
            per = [ticks(v) for v in sels]
            if None not in per:
                out[item] = [round(t / 12.0, 2) for t in per]
        else:
            t = ticks(sels)
            if t is not None:
                out[item] = round(t / 12.0, 2)
    return out
