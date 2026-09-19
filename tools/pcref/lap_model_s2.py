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
from another actor's script — 204, 205, 207 and 210 are timed from a start
step round to that handover since 2026-09-24 (LAP_START; their handshakes
are the runtime's, docs/PC_FIDELITY.md "205's table", "207's board", "210's
call"; 204's is its own gong's message). Not modelled:
206's and 214's waits on the Mother, 213's polls on Olga's picnic and bull
ride, 209's fakir `spit`. With
the walks the laps come to 105 s (203), 85.5 (208), 106.7 (209: its coal walk
leaves him 190 px on, an action's <translation>, Data.translation), 85 (211),
124 (212), 123 (213) and 90.3 (214) against the PC video's 84-112, 86, 97, 85,
113, 136 and 91 (214's shower to shower, docs/PC_LAPS_DETAIL.md) —
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
        'fcn.1000ffb8': 'Ef51a', 'fcn.1001000a': 'Ef8cd',
        # a wait of so many ticks (vtable 0x100ab804: its run 0x1000c9de counts
        # the pushed ticks down; 205's mat step waits 72 after the `talk`)
        'fcn.1000ca24': 'WAIT'}
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
    first_push = None     # the first argument pushed since the last call (its last parameter)
    consts = {}; pending_push = None
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
        if first_push is None and t.startswith('push '):
            m = re.match(r'push (0x[0-9a-f]+|[0-9]+)$', t)
            m2 = re.match(r'push (e[a-z][a-z])$', t)
            if m and not t.startswith('push 0x100'):
                first_push = int(m.group(1), 0)
            elif m2 and m2.group(1) in consts:
                first_push = consts[m2.group(1)]
            else:
                first_push = 'reg'        # a register or a slot written after it
        m = re.match(r'push (0x[0-9a-f]+|[0-9]+)$', t)
        if m and not t.startswith('push 0x100'): slots.append(('i', int(m.group(1), 0)))
        # the constants the general registers hold (a SHOUT's level is often
        # one: the zeroed ebx of the prologue, 212's bull's `xor edi, edi`,
        # 203's toilet's `push 2; pop eax` or `xor eax, eax` by its bytes)
        m = re.match(r'xor (e[a-z][a-z]), (e[a-z][a-z])$', t)
        m3 = re.match(r'(inc|dec) (e[a-z][a-z])$', t)
        if m and m.group(1) == m.group(2):
            consts[m.group(1)] = 0
        elif m3 and m3.group(2) in consts:
            # 201's buffet step: `xor ebx, ebx; inc ebx` — its SHOUT pushes 1
            consts[m3.group(2)] += 1 if m3.group(1) == 'inc' else -1
        elif re.match(r'(mov|lea|pop|add|sub|and|or|inc|dec|imul|movzx|movsx|sete|setne) (e[a-z][a-z])\b', t):
            r = re.match(r'\w+ (e[a-z][a-z])', t).group(1)
            m2 = re.match(r'mov e[a-z][a-z], (0x[0-9a-f]+|[0-9]+)$', t)
            if m2 and not t.startswith('mov e%s, 0x100' % r[1:]):
                consts[r] = int(m2.group(1), 0)
            elif t.startswith('pop ') and pending_push is not None:
                consts[r] = pending_push
            else:
                consts.pop(r, None)
        pending_push = None
        m = re.match(r'push (0x[0-9a-f]+|[0-9]+)$', t)
        if m and not t.startswith('push 0x100'):
            pending_push = int(m.group(1), 0)
        if t == 'xor ebx, ebx':
            regs['ebx0'] = True
        m = re.match(r'push (e[a-z][a-z])$', t)
        if m and m.group(1) in consts:
            # a register holding a constant pushed as an argument (the
            # steps zero ebx in their prologue: 208's shoe machine SHOUT,
            # 0x1001e762)
            slots.append(('i', consts[m.group(1)]))
        m = re.match(r'push (?:0x|fcn\.)(100[0-3][0-9a-f]{4})$', t)
        if m: slots.append(('f', int(m.group(1), 16)))
        m = re.match(r'lea eax, \[ebp - (0x[0-9a-f]+)\]$', t)
        if m: slots.append(('o', m.group(1)))
        m = re.match(r'mov byte \[ebp - (0x[0-9a-f]+)\], al$', t)
        if m: bytevars[m.group(1)] = al
        m = re.match(r'mov byte \[e(?:di|si|bx) \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|[0-9]+|bl)$', t)
        if m: bytevars['obj' + m.group(1)] = 0 if m.group(2) == 'bl' else int(m.group(2), 0)
        if t.startswith('call '):
            for r in ('eax', 'ecx', 'edx'):
                consts.pop(r, None)
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
                if kind == 'SHOUT':
                    # the level is the SHOUT's last parameter, its first push:
                    # a constant, or the step's own argument written into the
                    # reserved slot (201's buffet: [ebp+0xc], the actor)
                    imms = [first_push] if isinstance(first_push, int) else []
                ev.append((kind, args, imms)); al = None
            elif fn in ('fcn.1000aeb8', 'fcn.1000ae19', 'fcn.100088be', 'fcn.10059e30', 'fcn.10009b58',
                        'fcn.1000ee93', 'fcn.1000eec6', 'fcn.1000ef28', 'fcn.10049216'):
                pass
            else:
                al = unknown   # an unknown predicate (a trigger latch, another actor's
                               # state) reads false, or true on a poll's re-run
            slots = []
            first_push = None
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
def walk(lv, start, maxsteps=80, trace=False, bytes0=None):
    steps = []; cur = start; seenkeys = {}; bytevars = dict(bytes0 or {})
    for _ in range(maxsteps):
        key = (cur, tuple(sorted((k, v) for k, v in bytevars.items() if k.startswith('obj'))))
        if key in seenkeys: return steps, seenkeys[key]
        seenkeys[key] = len(steps)
        ev, nxt = run_step(lv, cur, dict(bytevars), trace=trace)
        if nxt is None or nxt == cur:
            b2 = dict(bytevars)
            run_step(lv, cur, b2)
            if any(k.startswith('obj') and b2.get(k) != bytevars.get(k) for k in b2):
                # a step in phases: its first pass writes its own byte and
                # returns, the next one goes on (205's mat: the `talk`, then —
                # the byte cleared — the 72-tick wait and the table)
                ev2, nxt2 = run_step(lv, cur, dict(b2), trace=trace)
                if nxt2 is not None and nxt2 != cur:
                    bytevars.update(b2)
                    run_step(lv, cur, bytevars)
                    steps.append((cur, ev + ev2, nxt2))
                    cur = nxt2
                    continue
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
    """{(object, animation): frames} of an anims.xml, tag by tag: an empty
    `<object … />` or `<animation … />` holds nothing (the pairing of an
    open tag with the next close one had given 205's `putski` and 204's gong
    and jade dummy to their neighbours)"""
    out = {}; obj = None; anim = None
    for m in re.finditer(r'<(/?)(object|animation|frame)\b([^>]*?)(/?)>', text):
        close, tag, attrs, empty = m.groups()
        if tag == 'object':
            nm = re.search(r'name="([^"]+)"', attrs)
            obj = nm.group(1) if (nm and not close and not empty) else None
            anim = None
        elif tag == 'animation':
            nm = re.search(r'name="([^"]+)"', attrs)
            if close:
                anim = None
            elif obj is not None and nm:
                out[(obj, nm.group(1))] = 0
                anim = None if empty else nm.group(1)
        elif anim is not None:
            out[(obj, anim)] += 1
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
            if not a.group(1).rstrip().endswith('/'):
                # the action's <translation object="false">: the actor moved by
                # `destination` over the action (the object's own with "true")
                close = body.find('</action>', a.end())
                inner = body[a.end():close if close >= 0 else len(body)]
                tr = [tuple(int(v) for v in m.split('/')) for m in re.findall(
                    r'<translation object="false"[^>]*destination="(-?\d+/-?\d+)"', inner)]
                if tr:
                    at['_tr'] = (sum(x for x, _y in tr), sum(y for _x, y in tr))
                # its named <trick> records: fcn.1000140b credits each once, on
                # the level tick its `time` equals the action's elapsed count
                # (the cmp at 0x10001455)
                at['_tricks'] = [(m.group(1), int(m.group(2))) for m in re.finditer(
                    r'<trick name="([^"]+)" time="(\d+)"', inner)]
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

    def translation(self, obj, name, actor='neighbor'):
        """the actor's net move over an action (its <translation object="false">
        destinations summed, px), (0, 0) without one — 205's skiing leaves the
        neighbour 400 px left of the skis, 209's coal walk 190 px right of the
        coal, 212's cliff enter 175 px left of the cliff"""
        e = self.objects.get(self.real.get(obj, obj)) or self.generic.get(obj) or {}
        a = (e.get('act') or {}).get((actor, name)) or {}
        return a.get('_tr', (0, 0))

    def tricks(self, obj, name, actor='neighbor'):
        """the action's named trick records [(name, time)] — by the actor's
        record, else the object's own action of that name"""
        e = self.objects.get(self.real.get(obj, obj)) or self.generic.get(obj) or {}
        acts = e.get('act') or {}
        a = acts.get((actor, name))
        if a is None:
            a = next((v for (ac, nm), v in acts.items() if nm == name), None)
        return list((a or {}).get('_tricks') or [])

    def action_ticks(self, obj, name, actor='neighbor'):
        """the ticks of an action: time="N", or auto = the frames of the actor's
        animation (the level's anims.xml, else generic/anims.xml), else of the
        object's (under its gfx); None if unknown"""
        o = self.real.get(obj, obj)
        e = self.objects.get(o) or self.generic.get(obj)
        if e is None:
            return None
        g = self.generic.get(obj)
        if (actor, name) not in e['act'] and g is not None and (actor, name) in g['act']:
            # a level's own actor record (205's neighbor: crash, pant, talk)
            # adds to the generic one (lookaround, shout …)
            e = g
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


# the elements done on their first update (the sequence's element returns 1 at
# once): Ef82b hides an object (vtable 0x100ab984, update 0x1000cf2a:
# fcn.10042b9e), Efac4 sets an actor's flag (vtable 0x100ab9a8, update
# 0x1000d037: fcn.100450bf with the element's two values)
INSTANT = {'Ef499', 'Ef8cd', 'Ef41f', 'SWITCH', 'SET', 'Ef82b', 'Efac4'}


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
        elif k == 'WAIT':
            parts.append(('-', 'wait', e[2][-1] if e[2] else None))
        elif k in ('WAITEVENT', 'POLL', 'SHOUT', 'Eebbf', 'Ef51a', 'Ef779', 'E2f40', 'E807f', 'RUNGO'):
            parts.append(('-', k, None))
    return parts


# the step a lap starts from where it is not the level's first: 210's lap runs
# from the Mother's `order` (his handler 0x1001b4f6 -> 0x1001aecc: the walk to
# Fifi and her `tickle`, then the take 0x1001aac8, the level's first step)
LAP_START = {210: 0x1001aecc,
             # 205's from his play at the table (0x100254d5 -> 0x100251eb: the
             # skis), which waits for Olga, round to the table again
             205: 0x100251eb,
             # 207's from his dive (0x100169c5's continuation, the bar) round
             # to the board again, which waits for the Mother in her chair
             207: 0x100164ee,
             # 204's from the gong's `leave` (his handler's `gong`, 0x10033236)
             # round to the gong, where the idle step 0x10031b70 waits for it
             204: 0x10032f52,
             # 201's free lap (the tutorial's end, 0x1002947b -> 0x100291cf, joins it
             # at the puddle): the rail's look round to the puddle again
             201: 0x10028f86}
# the switches the co-actors' scripts keep over the lap, (hidden, shown)
# (207's Olga lies on her mat when he brings the shell: mat_guarded, whose
# `shell` he plays, in the plain mat's place)
LAP_PRESENT = {207: (('beachright_mat', 'beachright_mat_guarded'),),
               # 201's director has shown the trickable puddle in the closed
               # one's place (0x10027ac5) before the lap is free
               201: (('topright_waterpuddle_closed', 'topright_waterpuddle'),)}
# the step object's bytes at a lap's start (205's script arms its mat step's
# `talk` in its constructor, 0x10025a9f, and the table step re-arms it)
LAP_BYTES = {205: {'obj0xd': 1}}


def lap_steps(n):
    """the untricked lap: [(index, step address, icon, objects, parts)] and the
    loop's first index (None when the walk stops)"""
    d = Data(n)
    st = LAP_START.get(n) or level_start(n); lv = Level(n)
    for hid, shown in LAP_PRESENT.get(n, ()):
        lv.present.discard(hid); lv.present.add(shown)
    steps, loop = walk(lv, st, bytes0=LAP_BYTES.get(n))
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
        if pos is not None and not any(a == 'leave' for _o, a, _t in parts):
            # the actions' translations move the actor off the hotspot: the
            # next walk leaves from there (a `leave` places him at another
            # object — 212's water exit — not modelled)
            for o, a, _t in parts:
                tx, ty = d.translation(o, a)
                pos = (pos[0], pos[1] + tx, pos[2] + ty)
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
    # the free lap after the tutorial: the rail looked at, the puddle's left
    # slip, the captain's hat, the flirt at the buffet, the puddle's slip (the
    # mobile's two WaterPuddle visits: the use rightwards, the prime leftwards)
    201: {'CaptainHat': [('captncap', 'neighbor', 'lookaround'), (None, 'captncap', 'use')],
          'Buffet': [(None, 'buffet', 'flirt')],
          'WaterPuddle': [[(None, 'waterpuddle', 'slip')], [(None, 'waterpuddle', 'slipleft')]],
          'DeckRail': [(None, 'reling', 'look')]},
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
    # his lap after the table (the skis ridden, walked back and put — the
    # mobile's two WaterSkiis visits —, the chef's eel, the rocket, the sand
    # lion's look and kick, whose `dirt` and `build` are the kid's own
    # sequences) and the mat: the `talk` that calls Olga to the table and the
    # 72-tick wait; the table's play waits for her (pc_durations_s2.py CLIPS)
    205: {'WaterSkiis': [[(None, 'waterski_guarded', 'skiing')], [(None, 'waterski_guarded', 'putski')]],
          'Chef': [(None, 'chef', 'cut_eel'), (None, 'chef', 'eat_eel')],
          'Rockets': [(None, 'rocket', 'ignite')],
          'SandSculpture': [('sandlion', 'neighbor', 'lookaround'), (None, 'sandlion', 'kick')],
          'OlgaMatBeach': [(None, 'neighbor', 'talk'), (None, '-', 'wait')]},
    # his lap after the dive (the bar's drink, the elephant, the shell on
    # Olga's mat, the kid's castle, his towel's bar); the board waits for
    # the Mother in her deck chair and is timed per clip (pc_durations_s2.py
    # CLIPS, Level207MotherBehavior)
    # his lap from the gong's `leave` (the hot dogs, the jade, the rickshaw
    # Olga sits in, the headbanger, the gong the elvis figure strikes — its
    # behavior="gong" on him sends him out of it as it starts)
    204: {'HotDog': [('hotdogshop', 'neighbor', 'lookaround'), (None, 'hotdogshop', 'use')],
          'JadeNecklace': [(None, 'jadedummy', 'look')],
          'PullKart': [(None, 'rickshaw', 'use')],
          'Karate': [(None, 'headbanging', 'use')],
          'GongDrumstick': [(None, 'gong', 'use')]},
    207: {'Bartender': [(None, 'keeper', 'order_drink')],
          'Elephant': [('elefant', 'neighbor', 'lookaround'), (None, 'elefant', 'spit_at_elefant')],
          'Shell': [(None, 'beachright_mat_guarded', 'shell')],
          'SandCastle': [('kid', 'neighbor', 'lookaround'), (None, 'kid', 'splash')],
          'BeachTowel': [(None, 'beachleft_mat_guarded', 'enter'), (None, 'beachleft_mat_guarded', 'bar'),
                         (None, 'beachleft_mat_guarded', 'leave')]},
}


# the levels whose unclosed walk still covers every station (code_stays)
OPEN_LAPS = (204, 205, 207, 210)


def code_stays(n):
    """{mobile item: seconds, or a list of seconds per visit} from the lap's parts
    by PAIRS[n]; an item whose part is missing or untimed is left out. A lap the
    walk does not close (210's: his chair waits for the Mother's call, a message
    the walk does not follow) is the walk from its start (LAP_START), each of
    its stations once"""
    out = {}
    _lap, pairs = _paired_parts(n)
    for item, (many, visits) in pairs.items():
        if all(v is not None and None not in [t for _i, _j, (_o, _a, t) in v] for v in visits):
            secs = [round(sum(t for _i, _j, (_o, _a, t) in v) / 12.0, 2) for v in visits]
            out[item] = secs if many else secs[0]
    return out


def code_moves(n):
    """{mobile item: px, or a list per visit}: where the next walk leaves from
    along the floor, off the station's hotspot — the neighbour's net move
    over the step whose last part is the item's (its actions' <translation>s,
    Data.translation; 205's skiing -400, 209's coal walk +190). An item whose
    parts do not end their step has none (212's cliff `enter`: its `use`
    follows in the same step, no GoTo between them), nor a step with a
    `leave` (the placement at another object: 212's water exit); items
    without a move left out"""
    d = Data(n)
    lap, pairs = _paired_parts(n)
    out = {}
    for item, (many, visits) in pairs.items():
        if any(v is None for v in visits):
            continue
        dx = []
        for v in visits:
            i, j = max((i, j) for i, j, _p in v)
            parts = lap[i][4]
            if j != len(parts) - 1 or any(a == 'leave' for _o, a, _t in parts):
                dx.append(0)
            else:
                dx.append(sum(d.translation(o, a)[0] for o, a, _t in parts))
        if any(dx):
            out[item] = dx if many else dx[0]
    return out


# a station's tricked-with-its-linked-item variant where it is another step of
# the script than the lap's: 201's puddle by the open rail (the combo,
# 0x100297c5: crash_long; the lap's puddle step 0x1002847f plays crash_short)
LINKED_STEP = {201: {'WaterPuddle': 0x100297c5}}
# a station's tricked variant where the lap's step has none and other steps of
# the script play it, their events in order: 201's damaged buffet in the
# tutorial (0x10029c4a: the flirt that sends Olga's buffet_crash, his crash;
# 0x10029a6c after her fight: the SHOUT that takes the actor for its level,
# the repair; the knife is spent by then)
TRICKED_STEP = {201: {'Buffet': (0x10029c4a, 0x10029a6c)}}


def _step_parts_split(d, ev, own=None):
    """a tricked step's parts cut at its SHOUT (fcn.1000f977 / fcn.1000fede):
    (the ticks before it — the tricked stand —, the SHOUT's level, -1 when
    the step has no SHOUT, None when its level is no constant the walker
    follows, the repair's ticks after
    it or None, the tick of the stand its first named trick record pays
    at — the parts before its action plus the record's `time` — or None);
    a part of unknown length leaves the stand None. `own(object, action)`
    keeps a station's own parts where the step is shared with another
    mobile station (212's cliff: the ledge's `enter` is the pre-ledge's)"""
    before, level, shout, repair, credit = 0, None, False, None, None
    unknown = False
    for e in ev or []:
        if e[0] == 'SHOUT':
            shout = True
            imms = e[2] if len(e) > 2 else []
            # the level is the SHOUT's last parameter (fcn.1000f977's
            # arg_14h, its first push: a constant or the zeroed ebx — 201's
            # buffet pushes ebx, 0); a register the walker does not follow
            # leaves it unknown (None)
            level = imms[0] if imms else None
            continue
        parts = station_ticks(d, [e], {})
        for o, a, t in parts:
            if a in ('-', '?') and t is None:
                continue
            if own is not None and a not in ('-', '?') and not own(o, a):
                continue
            if not shout:
                if credit is None and not unknown and a not in ('-', '?', 'bar'):
                    recs = d.tricks(o, a)
                    if recs:
                        credit = before + recs[0][1]
                if t is None:
                    unknown = True        # a part of unknown length: no stand
                else:
                    before += t
            elif a == 'repair':
                repair = (repair or 0) + (t or 0)
    return (None if unknown else before), (level if shout else -1), repair, credit


def tricked_presence(n):
    """{mobile item: (shown, hidden)}: what the item's trick leaves in the
    PC scene — the combine.xml combinations that take the inventory the
    mobile TrickItem requires (RequiredInventory, SecondRequiredInventory;
    canon.norm pairs the names), none `wrong`: each combination's object is
    shown, its object ingredients with remove="true" hidden (201's soap on
    the puddle: soappuddle shown, waterpuddle hidden; 214's shower trick is
    the wash bucket's, washbucket_manip)"""
    folder = canon.pc_level(n)['folder']
    cb = canon.read('%s/nfh2/x/%s/combine.xml' % (canon.ROOT, folder))
    combos = []
    for m in re.finditer(r'<combination name="([^"]+)"([^>]*)>(.*?)</combination>', cb, re.S):
        if 'wrong="true"' in m.group(2):
            continue
        ings = re.findall(r'<ingredient name="([^"]+)"([^>]*)/?>', m.group(3))
        combos.append((m.group(1), [(i, 'remove="true"' in a) for i, a in ings]))
    raw = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), 'levels', 's2', 'Level%d.json' % n)))
    out = {}
    for o in raw['objects'].values():
        if o.get('type') != 'TrickItem':
            continue
        d = o.get('data') or {}
        name = (d.get('m_GameObject') or {}).get('name')
        req = [canon.norm(x) for x in (d.get('RequiredInventory'), d.get('SecondRequiredInventory'))
               if x and x != 'IT_NONE']
        shown, hidden = set(), set()
        for cname, ings in combos:
            if any(canon.norm(i) in req for i, _r in ings):
                shown.add(cname.replace('/', '_'))
                hidden |= {i.replace('/', '_') for i, r in ings if r and '/' in i}
        if shown:
            out.setdefault(name, (set(), set()))
            out[name][0].update(shown); out[name][1].update(hidden)
    return out


def _tricked_run(n, lv, item, cur, trick):
    """the step `cur` run with the item's trick in the scene (tricked_presence);
    None when the trick changes none of its DoActions"""
    shown, hidden = trick.get(item, (set(), set()))
    if not shown:
        return None
    lv2 = Level(n)
    lv2.present = (set(lv.present) - hidden) | shown
    ev2, _nx = run_step(lv2, cur, dict(LAP_BYTES.get(n) or {}))
    ev1, _nx = run_step(lv, cur, dict(LAP_BYTES.get(n) or {}))
    dos = lambda ev: [tuple(e[1]) for e in ev if e[0] == 'DO']
    if dos(ev2) == dos(ev1):
        return None
    return ev2


def mobile_linked(n):
    """{mobile item: the item its LinkedItemTrick names}: the mobile's linked
    pairs (TrickItem.LinkedItemTrick, the ladder's linked arm
    Rottweiler.cs:640-654), DoNothingLinkedTrick ones left out"""
    raw = json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), 'levels', 's2', 'Level%d.json' % n)))
    out = {}
    for o in raw['objects'].values():
        if o.get('type') != 'TrickItem':
            continue
        d = o.get('data') or {}
        li = d.get('LinkedItemTrick') or {}
        if li.get('name') and not d.get('DoNothingLinkedTrick'):
            out[(d.get('m_GameObject') or {}).get('name')] = li['name']
    return out


def _step_records(d, ev, own=None):
    """the step's named trick records before its SHOUT, in order: [(name,
    tick)], the tick the parts before the record's action plus its `time`
    (fcn.1000140b credits each at its own); up to a part of unknown length"""
    before, out = 0, []
    for e in ev or []:
        if e[0] == 'SHOUT':
            break
        for o, a, t in station_ticks(d, [e], {}):
            if a in ('-', '?') and t is None:
                continue
            if own is not None and a not in ('-', '?') and not own(o, a):
                continue
            if a not in ('-', '?', 'bar'):
                out += [(nm, before + tm) for nm, tm in d.tricks(o, a)]
            if t is None:
                return out
            before += t
    return out


def code_stays_tricked(n):
    """{mobile item: {'tricked': s[, 'linked': s], 'shout': level,
    'repair': s|None, 'credit': s|None}}: a TRICKED visit of the lap's
    station — its step run again with the item's trick in the scene
    (tricked_presence: the combination's object shown, its removed
    ingredients hidden), where that changes the step's DoActions: the stand
    is the DoActions before its SHOUT (the tricked action and whatever the
    step plays before the shout), the SHOUT's level (fcn.1000f977's clip
    table: 0 shout2_light, 1 shout2 / shout2_hard, 2 shout2_hard and the
    shout2 set, 3 the freakouts; -1: the step has no SHOUT; None: a level
    the walker does not follow), the repair after it, the
    second its first named trick record pays (fcn.1000140b: the record's
    `time` into its action); 'linked' the variant the linked trick plays:
    the same step run with both tricks in the scene where that changes its
    DoActions (202's damaged rail over the eels' pond: crash, electrify and
    leave, SHOUT 2; the ladder's linked arm, Rottweiler.cs:640-654), or
    another step of the script (LINKED_STEP) — its stand, 'linked_shout',
    'linked_repair', 'linked_credit' (the item's own record) and
    'linked_pays' (the first record the item-only variant does not play:
    the linked trick's, bridge_electrify); TRICKED_STEP a tricked variant
    only another step plays. Items the trick leaves the lap's steps
    unchanged in are left out"""
    d = Data(n)
    lap, pairs = _paired_parts(n)
    if not lap:
        return {}
    st = LAP_START.get(n) or level_start(n)
    lv = Level(n)
    for hid, shown in LAP_PRESENT.get(n, ()):
        lv.present.discard(hid); lv.present.add(shown)
    trick = tricked_presence(n)

    def entry(ev2, own=None):
        stand, level, repair, credit = _step_parts_split(d, ev2, own)
        return {'tricked': round(stand / 12.0, 2) if stand is not None else None, 'shout': level,
                'repair': round(repair / 12.0, 2) if repair is not None else None,
                'credit': round(credit / 12.0, 2) if credit is not None else None}
    # the parts of each lap row the stations pair with: a tricked part is
    # another station's where its action and object (the variant's name
    # starts with the object's: altar_statue_snake) are one of that
    # station's; the parts no station pairs with — the trick's own actions —
    # are the station's that is tricked
    owner = {}
    for other, (_m, ovs) in pairs.items():
        for v in ovs:
            for i, _j, (o, a, _t) in v or []:
                owner.setdefault(i, []).append((other, o, a))

    def own_of(item, i):
        def own(o, a):
            for other, oo, aa in owner.get(i, ()):
                if aa == a and (o == oo or o.startswith(oo + '_')) and other != item:
                    return False
            return True
        return own
    out = {}
    where = {}
    for item, (many, visits) in pairs.items():
        for v in visits:
            if v is None or item in out:
                continue
            for i in sorted(set(i for i, _j, _p in v)):
                ev2 = _tricked_run(n, lv, item, lap[i][1], trick)
                e = entry(ev2, own_of(item, i)) if ev2 is not None else None
                if e is not None:
                    out[item] = e
                    where[item] = (i, ev2)
                    break
    for item, stps in TRICKED_STEP.get(n, {}).items():
        lv2 = Level(n)
        lv2.present = set(lv.present)
        ev = []
        for step in stps:
            # a step that waits on its latch is taken as passed (unknown=1)
            ev += run_step(lv2, step, dict(LAP_BYTES.get(n) or {}), unknown=1)[0]
        e = entry(ev)
        if e is not None and item not in out:
            out[item] = e
    for item, step in LINKED_STEP.get(n, {}).items():
        lv2 = Level(n)
        lv2.present = set(lv.present)
        stand, _level, _repair, credit = _step_parts_split(d, run_step(lv2, step, dict(LAP_BYTES.get(n) or {}))[0])
        if stand is not None and item in out:
            out[item]['linked'] = round(stand / 12.0, 2)
            out[item]['linked_credit'] = round(credit / 12.0, 2) if credit is not None else None
    # the linked trick in the same step: the station's step run with both
    # tricks in the scene
    dos = lambda ev: [tuple(e[1]) for e in ev if e[0] == 'DO']
    for item, lnk in sorted(mobile_linked(n).items()):
        if item not in where or 'linked' in out[item] or lnk not in trick:
            continue
        i, ev1 = where[item]
        (s1, h1), (s2, h2) = trick[item], trick[lnk]
        lv2 = Level(n)
        lv2.present = (set(lv.present) - h1 - h2) | s1 | s2
        ev2, _nx = run_step(lv2, lap[i][1], dict(LAP_BYTES.get(n) or {}))
        if dos(ev2) == dos(ev1):
            continue
        own = own_of(item, i)
        stand, level, repair, _first = _step_parts_split(d, ev2, own)
        if stand is None:
            continue
        # the item's own records are the ones its variant alone plays
        mine = set(nm for nm, _t in _step_records(d, ev1, own))
        recs = _step_records(d, ev2, own)
        credit = next((t for nm, t in recs if nm in mine), None)
        pays = next((t for nm, t in recs if nm not in mine), None)
        out[item].update({'linked': round(stand / 12.0, 2), 'linked_shout': level,
                          'linked_repair': round(repair / 12.0, 2) if repair is not None else None,
                          'linked_credit': round(credit / 12.0, 2) if credit is not None else None,
                          'linked_pays': round(pays / 12.0, 2) if pays is not None else None})
    return out


def code_moves_tricked(n):
    """{mobile item: px}: the same move after a TRICKED visit — the station's
    step run again with the tricked variants of its IsVariant pairs shown in
    the normal ones' place (the level scripts pick the first present: 207's
    sand castle with the crayfish has him splash the kid, -154; 214's
    manipulated pistol +95; 209's hot coal walks +110, then enters and
    leaves it — a placement, 0), for the items where it differs from
    code_moves; items without a tricked variant left out"""
    d = Data(n)
    lap, pairs = _paired_parts(n)
    moves = code_moves(n)
    st = LAP_START.get(n) or level_start(n)
    lv = Level(n)
    for hid, shown in LAP_PRESENT.get(n, ()):
        lv.present.discard(hid); lv.present.add(shown)
    steps, _loop = walk(lv, st, bytes0=LAP_BYTES.get(n))
    events = {cur: ev for cur, ev, _nxt in steps}
    out = {}
    for item, (many, visits) in pairs.items():
        if many or visits[0] is None:
            continue
        i = max(i for i, _j, _p in visits[0])
        cur = lap[i][1]
        alts = []
        for e in events.get(cur) or []:
            if e[0] != 'IFVAR':
                continue
            cands = [c for c in e[1] if not str(c).startswith('$')]
            # the untricked lap picks the first; the second is the tricked one
            if len(cands) > 1 and e[2] == cands[0]:
                alts.append((cands[0], cands[1]))
        if not alts:
            continue
        lv2 = Level(n)
        lv2.present = set(lv.present)
        for pick, alt in alts:
            lv2.present.discard(pick); lv2.present.add(alt)
        ev2, _nx = run_step(lv2, cur, dict(LAP_BYTES.get(n) or {}))
        parts = station_ticks(d, ev2, {})
        if any(a == 'leave' for _o, a, _t in parts):
            dx = 0
        else:
            dx = sum(d.translation(o, a)[0] for o, a, _t in parts)
        if dx != moves.get(item, 0):
            out[item] = dx
    return out


def _paired_parts(n):
    """(the lap's rows, {mobile item: (per visit, [its parts [(row, part
    index, (object, action, ticks))] per visit, None where a pair is
    missing])}) by PAIRS[n] over the lap's parts (each part paired once, in
    the lap's order)"""
    rows, loop = lap_steps(n)
    if loop is None and n not in OPEN_LAPS:
        return [], {}
    lap = rows if loop is None else rows[loop:] + rows[:loop]
    used = set(); out = {}

    def match(sels):
        got = []
        for sel, osuf, act in sels:
            hit = None
            for i, cur, icon, objs, parts in lap:
                if sel and not any(sel in o for o in objs):
                    continue
                for j, (o, a, t) in enumerate(parts):
                    if (i, j) in used or a != act:
                        continue
                    if o == osuf or o.endswith('_' + osuf):
                        hit = (i, j, (o, a, t)); break
                if hit: break
            if hit is None:
                return None
            used.add(hit[:2]); got.append((lap.index(next(r for r in lap if r[0] == hit[0])), hit[1], hit[2]))
        return got

    for item, sels in PAIRS.get(n, {}).items():
        if sels and isinstance(sels[0], list):
            out[item] = (True, [match(v) for v in sels])
        else:
            out[item] = (False, [match(sels)])
    return lap, out
