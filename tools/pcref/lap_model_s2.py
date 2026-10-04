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
(0x10009332), at most a tick a walk, not counted: on the seven closed laps
no walk within a room starts on the floor line facing its way from ms1 /
ms3 (checked 2026-10-03: the stations end in ms0 or ms2, or their hotspots
lie off the floor line, the first move a vertical one).

Coverage (2026-09-23): the untricked lap closes on 203, 206, 208, 209, 211,
212, 213 and 214 (its hatch behind the step's own byte, its bouquet behind
IsVariant's null test — both read since the same evening); 201 (the
tutorial), 202, 204, 205, 207 and 210 stop at a step whose handover comes
from another actor's script — 204, 205, 207 and 210 are timed from a start
step round to that handover since 2026-09-24 (LAP_START; their handshakes
are the runtime's, docs/PC_FIDELITY.md "205's table", "207's board", "210's
call"; 204's is its own gong's message). Not modelled:
206's and 214's waits on the Mother, 213's polls on Olga's bull ride (its
picnic's `boat` latch is set before he arrives on the video's laps: his
tortilla step sends her to the boat, 0x100386ad), 209's fakir `spit`. With
the walks the laps come to 105 s (203), 85.5 (208), 106.7 (209: its coal walk
leaves him 190 px on, an action's <translation>, Data.translation), 85 (211),
124 (212), 123 (213) and 90.3 (214) against the PC video's 84-112, 86, 97, 85,
113, 136 and 91 (214's shower to shower, docs/PC_LAPS_DETAIL.md) —
the video's stays (pc_durations_s2.py) held the walk the port's geometry did
not have until the door passes and the station runs were carried
(tools/pcref/pc_walks_s2.py); code_stays hands the profile the code's.
206's since 2026-10-03: its lap after the pillow lesson (the waits on the
Mother are the lesson's, 0x1002f11d and 0x1002ecb5) is the mobile's loop
from its selected index, 118.5 s; a visit whose parts span steps takes the
walks between them (_visit_walks: the dynamite bag's take, then the
reling's step).
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
        'fcn.1000ffb8': 'Ef51a', 'fcn.1001000a': 'Ef8cd', 'fcn.1000ff47': 'SET',
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
def run_step(lv, start, bytevars, maxn=4000, trace=False, unknown=0, streq=0, latch=0):
    """one step: returns (events, next); `unknown` takes a poll's awaited
    object as shown, `streq` a name compare the walker cannot resolve (an
    object's animation against a name, fcn.1004948f) as holding — the poll
    that waits for another actor's action —, `latch` the step's event
    latches (fcn.10013269: the byte fcn.10013319 sets when a behaviour of
    the latch's name reaches the script) as set, the scene's tests left to
    the scene (213's picnic waits for Olga's `boat`, then asks which
    picnic is shown)"""
    k = at(start); seen = set(); ev = []; nxt = None
    slots = []; al = None; vars_ = {}; regs = {}; zf = None
    this_k = None         # the slot of an ecx load no argument took (the thiscall's this)
    edx_g = None; edx_names = []   # names stored into argument slots through edx
    first_push = None     # the first argument pushed since the last call (its last parameter)
    consts = {}; pending_push = None
    pose = False          # the element E2f40 appends is a pose element (fcn.10014c5c / fcn.1000de51)
    stepv = None          # the local the prologue saves the step object (ecx) in
    stepr = set()         # the registers loaded from it: 213's limberwall step tests its
                          # own byte +0x28 through eax (0x10038ab1)
    entered = False       # past the prologue (its SEH call fcn.10059e30)
    gpush = []            # names pushed by their globals' addresses (fcn.10014cf7's)
    lea_ecx = None        # the local `lea ecx` points at: a string assignment's target
    pushed_lea = None     # the last such local pushed (an out argument)
    ecx_var = None        # the local ecx was loaded from (a thiscall's `this`)
    arg_vars = []         # locals stored into argument slots through ecx
    actor_vars = set()    # locals holding another actor (fcn.1004ba02's out)
    seq_vars = {}         # locals holding a sequence built for another queue
                          # (fcn.1000aeb8) -> the indices of the events appended
    last_elem = None      # the index of the last element event built
    other_builders = set()  # builder locals set up for another actor (fcn.1000ee93)
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
        m = re.match(r'mov edx, dword \[(0x100[de][0-9a-f]{4})\]$', t)
        if m:
            edx_g = gname(m.group(1))
        elif t == 'mov dword [eax], edx' and edx_g is not None:
            # a name put in its argument's slot through edx (205's put step,
            # 0x10024e62-0x10024e6d: beachleft_waterski_guarded) — the GoTo's
            edx_names.append(edx_g)
        m = re.match(r'mov ecx, dword \[ebp - (0x[0-9a-f]+)\]$', t)
        if m:
            slots.append(('v', vars_.get(m.group(1), '$' + m.group(1))))
            this_k = len(slots) - 1       # a thiscall's `this` unless ecx is stored or pushed
        elif this_k is not None and (re.match(r'mov dword \[e[a-z]x\], ecx$', t) or t == 'push ecx'
                                     or t.startswith('mov ecx,')):
            this_k = None
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
        m = re.match(r'mov dword \[ebp - (0x[0-9a-f]+)\], ecx$', t)
        if m and not entered and stepv is None:
            stepv = m.group(1)
        m = re.match(r'mov (e[a-z]x), dword \[ebp - (0x[0-9a-f]+)\]$', t)
        if m:
            if m.group(2) == stepv:
                stepr.add(m.group(1))
            else:
                stepr.discard(m.group(1))
        elif re.match(r'(mov|lea|pop|xor|add|sub|and|or|inc|dec|imul|movzx|movsx) (e[a-z]x)\b', t):
            stepr.discard(re.match(r'\w+ (e[a-z]x)', t).group(1))
        m = re.match(r'push (0x100e[0-9a-f]{4})$', t)
        if m:
            gpush.append(gname(m.group(1)))
        m = re.match(r'lea ecx, \[ebp - (0x[0-9a-f]+)\]$', t)
        if m:
            lea_ecx = m.group(1)
        elif re.match(r'(mov|lea|pop|xor) ecx\b', t):
            lea_ecx = None
        if t == 'push ecx' and lea_ecx:
            pushed_lea = lea_ecx
        m = re.match(r'mov ecx, dword \[ebp - (0x[0-9a-f]+)\]$', t)
        if m:
            ecx_var = m.group(1)
        elif re.match(r'(mov|lea|pop|xor) ecx\b', t):
            ecx_var = None
        if t == 'mov dword [eax], ecx' and ecx_var:
            arg_vars.append(ecx_var)
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
        m = re.match(r'mov byte \[(e[a-z]x) \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|[0-9]+|bl)$', t)
        if m and m.group(1) in stepr:
            # the step object's byte through the register loaded from its
            # saved local (213: 0x10038c18 after the bull's charge)
            bytevars['obj' + m.group(2)] = 0 if m.group(3) == 'bl' else int(m.group(3), 0)
        if t.startswith('call '):
            for r in ('eax', 'ecx', 'edx'):
                consts.pop(r, None)
                stepr.discard(r)
            if not t.startswith('call fcn.10059e30'):
                entered = True
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
            elif fn == 'fcn.10007a10':
                # a GoTo the step builds and appends to its sequence
                # (fcn.1000ef28): its object and hotspot name, the
                # arguments pushed last-first (213's picnic 0x10038516:
                # the water's `beat`; 211's toilet 0x1003102b: wcright's)
                ev.append(('GOEL', list(reversed(names))))
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
                if streq and len(names) < 2:
                    al = 1
                ev.append(('STREQ', names[-2:], al))
            elif fn == 'fcn.1000e3e0':
                # the object's name: the step's `this` loaded into ecx for
                # the call is none of its arguments (203's toilet step,
                # 0x10033e6e-0x10033e8e: groundleft_toilet, then ecx =
                # [ebp-0x20] and the call)
                gn = [s2[1] for i2, s2 in enumerate(slots) if s2[0] in ('g', 'v') and i2 != this_k]
                if not gn and edx_names:
                    gn = edx_names[-1:]
                ev.append(('GO', gn[-1] if gn else (names[-1] if names else None))); al = 0
            elif fn == 'fcn.1000ea30':
                # the go-and-enter helper: its GoTo (fcn.1000e3e0), and on the
                # arrival the hideout's `enter` job (fcn.10006bd4, pushed by
                # fcn.10049216) unless the actor is in it already (fcn.10049190
                # and the name compare, 0x1000ea90-0x1000eac2); 0 once inside
                # (210's Olga into the shower, 0x1001bb5d)
                gn = [s2[1] for i2, s2 in enumerate(slots) if s2[0] in ('g', 'v') and i2 != this_k]
                if not gn and edx_names:
                    gn = edx_names[-1:]
                obj = gn[-1] if gn else (names[-1] if names else None)
                ev.append(('GO', obj)); ev.append(('EA30', [obj] if obj else [], [])); al = 0
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
            elif fn == 'fcn.10014cf7':
                # the show element (fcn.10014772: vtable 0x100ab978, Ef779's)
                # built by hand, its object and room pushed by their globals'
                # addresses (212's aux: the parrot's shit on the ledge, 0x10034f09)
                args = list(reversed(gpush))
                if args:
                    lv.present.add(args[0].replace('/', '_'))
                ev.append(('Ef779', args, [])); al = None
            elif fn in ('fcn.10014c5c', 'fcn.1000de51'):
                # 207's pose element (fcn.1000de51: vtable 0x100ab990, update
                # 0x1000cfaa sets the actor's animation and returns 1 at once)
                pose = True
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
                if kind == 'E2f40' and pose:
                    ev.append((kind, args, imms, 'instant')); pose = False
                else:
                    ev.append((kind, args, imms))
                last_elem = len(ev) - 1
                if lea_ecx is not None and lea_ecx in other_builders:
                    # appended to a builder of another actor's (214's pistol
                    # step: the deck chair's `die` into the Mother's)
                    ev[-1] = ('O' + ev[-1][0],) + tuple(ev[-1][1:])
                al = None
            elif nxt is not None and fn == 'fcn.%x' % nxt:
                # the step runs its next one itself, in its own tick (208's
                # fakir step 0x1001eff3, 210's 0x100197ac)
                ev.append(('CALLNEXT',))
            elif fn == 'fcn.1000ee93' and lea_ecx:
                # a sequence builder set up for an actor (its argument): one
                # found by name (fcn.1004ba02's out) is another actor's, its
                # elements that actor's and pushed onto its queue
                # (fcn.1000eec6: 214's pistol step builds the Mother's the
                # deck chair's `die`, 0x1003ad04-0x1003ad3f)
                if arg_vars and arg_vars[-1] in actor_vars:
                    other_builders.add(lea_ecx)
                else:
                    other_builders.discard(lea_ecx)
            elif fn == 'fcn.1004ba02' and pushed_lea:
                # an actor found by its name (its out argument): a job pushed
                # onto its queue is that actor's (208's fakir, 202's kid)
                actor_vars.add(pushed_lea)
            elif fn == 'fcn.1000aeb8' and outs:
                seq_vars[outs[-1][1]] = []
            elif fn == 'fcn.1000ae19' and ecx_var in seq_vars and last_elem is not None:
                seq_vars[ecx_var].append(last_elem)
            elif fn == 'fcn.10049216' and ecx_var in actor_vars:
                # a job pushed onto another actor's queue (fcn.10049216 on
                # the actor fcn.1004ba02 found): its elements are that
                # actor's — the step does not wait for them (208's step
                # 0x1001ee76 pushes the fakir's `play` onto the fakir,
                # 0x1001efba-0x1001efc4, and runs its next step at once;
                # 202's dive step the kid's sequence, 0x100221dd-0x100221e3)
                arg = arg_vars[-1] if arg_vars else None
                idx = seq_vars.get(arg, [last_elem] if last_elem is not None else [])
                for i in idx:
                    if i is not None and i < len(ev) and not ev[i][0].startswith('O'):
                        ev[i] = ('O' + ev[i][0],) + tuple(ev[i][1:])
            elif fn == 'fcn.10009b58' and lea_ecx and gpush:
                # a string assigned to a local from a global's address (211's
                # toilet step: the women's or the men's wc by the sign,
                # 0x10030e34-0x10030e45)
                vars_[lea_ecx] = gpush[-1]
            elif fn in ('fcn.1000aeb8', 'fcn.1000ae19', 'fcn.100088be', 'fcn.10059e30', 'fcn.10009b58',
                        'fcn.1000ee93', 'fcn.1000eec6', 'fcn.1000ef28', 'fcn.10049216'):
                pass
            elif fn == 'fcn.10013269' and latch:
                al = 1
            else:
                al = unknown   # an unknown predicate (a trigger latch, another actor's
                               # state) reads false, or true on a poll's re-run
            slots = []; this_k = None; edx_g = None; edx_names = []
            gpush = []; lea_ecx = None; pushed_lea = None; ecx_var = None; arg_vars = []
            first_push = None
            k += 1; continue
        # the flags: ZF from the tests the scripts branch on; any other
        # flag-setting instruction leaves them unknown
        if t == 'test al, al' or re.match(r'cmp al, (bl|0)$', t):
            zf = None if al is None else (al == 0); k += 1; continue
        m = re.match(r'cmp byte \[ebp - (0x[0-9a-f]+)\], (bl|0)$', t)
        if m:
            v = bytevars.get(m.group(1)); zf = None if v is None else (v == 0); k += 1; continue
        m = re.match(r'cmp byte \[(e[a-z]x) \+ (0x[0-9a-f]+)\], (bl|0)$', t)
        if m and m.group(1) in stepr:
            zf = (bytevars.get('obj' + m.group(2)) or 0) == 0; k += 1; continue
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
def walk(lv, start, maxsteps=80, trace=False, bytes0=None, snaps=None):
    """the steps from `start`: [(step, events, next)] and the index the lap
    loops back to (None when it stops); `snaps` collects the scene and the
    step bytes as the walk enters each step"""
    steps = []; cur = start; seenkeys = {}; bytevars = dict(bytes0 or {})
    for _ in range(maxsteps):
        key = (cur, tuple(sorted((k, v) for k, v in bytevars.items() if k.startswith('obj'))))
        if key in seenkeys: return steps, seenkeys[key]
        seenkeys[key] = len(steps)
        if snaps is not None:
            snaps.append((set(lv.present), dict(bytevars)))
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


def _loops_of(text):
    """{(object, animation)} of an anims.xml's type="loop" animations"""
    out = set(); obj = None
    for m in re.finditer(r'<(/?)(object|animation)\b([^>]*?)(/?)>', text):
        close, tag, attrs, empty = m.groups()
        if tag == 'object':
            nm = re.search(r'name="([^"]+)"', attrs)
            obj = nm.group(1) if (nm and not close and not empty) else None
        elif not close and obj is not None and re.search(r'\btype="loop"', attrs):
            nm = re.search(r'name="([^"]+)"', attrs)
            if nm:
                out.add((obj, nm.group(1)))
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
                # its <trick> records, their attributes by name (Loader.dll
                # reads each by its atom, 0x10009b8f-0x10009c9f: 211's
                # phone_normal carries jingle before time): fcn.1000140b
                # credits each named one once, on the level tick its `time`
                # equals the action's elapsed count (the cmp at 0x10001455),
                # and plays jingle_joke on that tick for each with
                # jingle="true", named or not (0x10001528-0x1000153f)
                recs = [dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
                        for m in re.finditer(r'<trick\b([^>]*)>', inner)]
                at['_tricks'] = [(r['name'], int(r['time'])) for r in recs
                                 if r.get('name') and r.get('time', '').isdigit()]
                at['_jingles'] = [int(r['time']) for r in recs
                                  if r.get('jingle') == 'true' and r.get('time', '').isdigit()]
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
        self.loops = _loops_of(canon.read('%s/%s/anims.xml' % (X, folder))) \
            | _loops_of(canon.read('%s/generic/anims.xml' % X))
        # the code's constants spell 'room/object' as 'room_object'; rooms have
        # underscores of their own (fire_fakir, tadj_mahal, coal_area)
        self.real = {k.replace('/', '_'): k for k in self.objects}
        self.n = n
        self._geom = None

    def geom(self):
        """the level's Geometry (the walks a flow's GoTo elements make)"""
        if self._geom is None:
            self._geom = Geometry(self.n)
        return self._geom

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

    def jingles(self, obj, name, actor='neighbor'):
        """the action's jingle_joke ticks: the `time` of each of its <trick>
        records with jingle="true", named or not (fcn.1000140b,
        0x10001528-0x1000153f) — by the actor's record, else the object's
        own action of that name"""
        e = self.objects.get(self.real.get(obj, obj)) or self.generic.get(obj) or {}
        acts = e.get('act') or {}
        a = acts.get((actor, name))
        if a is None:
            a = next((v for (ac, nm), v in acts.items() if nm == name), None)
        return list((a or {}).get('_jingles') or [])

    def _record(self, obj, name, actor='neighbor'):
        """(the owner's entry, the action record, the owner's name) of an
        action: the actor's record in the object's (a level's own actor
        record adds to the generic one: 205's neighbor — crash, pant, talk —
        over lookaround, shout …), else the object's own action of that
        name (the fakir's `play`: actor = the object; else another actor's
        but Woody's); None if the data has none"""
        o = self.real.get(obj, obj)
        e = self.objects.get(o) or self.generic.get(obj)
        if e is None:
            return None
        g = self.generic.get(obj)
        if (actor, name) not in e['act'] and g is not None and (actor, name) in g['act']:
            e = g
        a = e['act'].get((actor, name))
        if a is None:
            own = [v for (ac, nm), v in e['act'].items() if nm == name and ac == o] \
                or [v for (ac, nm), v in e['act'].items() if nm == name and ac not in ('woody',)]
            if not own:
                return None
            a = own[0]
        return e, a, o

    def _auto_frames(self, e, a, o):
        """the longer of the action's actor's animation (the actor's set)
        and its object's (the gfx's set) as Loader.dll counts them for
        time="auto" (0x10009704-0x100097fc): a oneshot's frames, a loop or
        a missing animation -1 (0x10004781 with its flag 1: the anim's
        loop byte, 0x10004812-0x10004823), "inv" not asked (0x10009730);
        None when the data has neither animation at all"""
        seen = False

        def frames(owner, anim, *alts):
            nonlocal seen
            for k in (owner,) + alts:
                if (k, anim) in self.loops:
                    seen = True
                    return -1
                f = self.frames.get((k, anim))
                if f is None:
                    f = self.gframes.get((k, anim))
                if f is not None:
                    seen = True
                    return f
            return -1
        v = 0
        ac, aa = a.get('actor'), a.get('actoranim')
        if ac and aa and aa != 'inv':
            v = frames(ac, aa)
        oa = a.get('objanim')
        if oa and oa != 'inv':
            v = max(v, frames(e['gfx'] or o, oa, o))
        if not seen and ((aa and aa != 'inv') or (oa and oa != 'inv')):
            return None
        return v

    def action_ticks(self, obj, name, actor='neighbor'):
        """the ticks an action takes in its actor's queue: its DoActions
        job's (job_ticks, the Loader's time + 2 — an auto action its
        governing animation's frames and one, a time="N" one N + 2); None
        if unknown. Until 2026-09-25 an auto action counted its actor's
        animation's frames first, loops included, and a time="N" one N:
        202's sub `dive` was the kid's play_remote (62) where the sub's
        sub_dive (191) governs, 205's chef `cut_eel` the neighbour's `wait`
        loop (63) where the chef's `cut` (31) does"""
        return self.job_ticks(obj, name, actor)

    def loader_time(self, obj, name, actor='neighbor'):
        """the action record's time as Loader.dll stores it (+0x28 of its
        action record, 0x10009842): time="N" as N; auto the governing
        animation's frames (_auto_frames) less one, at least 0
        (0x1000982b-0x10009842); None if the action is not in the data or
        its animations are not"""
        r = self._record(obj, name, actor)
        if r is None:
            return None
        e, a, o = r
        t = a.get('time', 'auto')
        if t.isdigit():
            return int(t)
        v = self._auto_frames(e, a, o)
        if v is None:
            return None
        return max(v - 1, 0)

    def job_ticks(self, obj, name, actor='neighbor'):
        """the ticks of the action's DoActions job from its first update to
        its last — the state 0 update, a count up to the record's time
        (fcn.100011f2: +0x28 past +0x24), the state 2 update that sets the
        next animations and posts the action's behavior (fcn.1004000a,
        0x10002708) and ends the job: the Loader's time + 2"""
        t = self.loader_time(obj, name, actor)
        return None if t is None else t + 2


# the elements done on their first update (the sequence's element returns 1 at
# once): Ef82b hides an object (vtable 0x100ab984, update 0x1000cf2a:
# fcn.10042b9e), Efac4 sets an actor's flag (vtable 0x100ab9a8, update
# 0x1000d037: fcn.100450bf with the element's two values)
INSTANT = {'Ef499', 'Ef8cd', 'Ef41f', 'SWITCH', 'SET', 'Ef82b', 'Efac4', 'Ef779'}


# the elements a sequence finishes on their first update: each takes its
# tick (the sequence, vtable 0x100ab6c0, update 0x1000ad52, pushes an
# element with a first run, fcn.10049246, and returns 0, so the queue's
# runner, fcn.100492a8, goes on no further that tick)
TICK_ELEMENTS = INSTANT | {'Eebbf', 'Ef51a'}


# a step's own ticks before its sequence's first element where it walks: the
# GoTo's done tick, in which the step runs again and pushes the sequence
# without a first run, and the sequence's first update (step_ticks) — one
# where it does not
WALK_STEP_TICKS = 2


def _go_target(ev, inside=None):
    """the object the step's GoTo walks to: its own (fcn.1000e3e0), or the
    bar helper's — fcn.1000e7f2 calls fcn.1000e3e0 with its hideout
    (0x1000e98d-0x1000e9b3) and returns while the GoTo walks, unless the
    actor is in the hideout already (its first branch, fcn.10049190 and the
    name compare, makes the bar at once: 209's curtain, entered from the shoe
    mat by the shoe step's own `enter` element, fcn.10006bd4, which walks
    nowhere); None where the step has neither"""
    go = next((e[1] for e in ev if e[0] == 'GO'), None)
    if go is None:
        we = next((e for e in ev if e[0] == 'WAITEVENT'), None)
        if we is not None:
            go = next((x for x in we[1] if isinstance(x, str) and '_' in x and not x.startswith('$')), None)
            if go is not None and inside is not None and go.replace('/', '_') == str(inside).replace('/', '_'):
                go = None
    return go


def _place(ctx, go):
    """the step's GoTo target as a place: the room and the `neighbor` hotspot
    where ctx carries the level's Geometry and Data (two objects at one
    hotspot are one place: the GoTo finds him there — 210's deck chair and
    the guarded one), else its name"""
    g, d = ctx.get('geom'), ctx.get('data')
    if go is None or g is None:
        return go
    obj = d.real.get(go, go) if d is not None else go
    p = g.point(obj)
    return (g.room_of(obj), tuple(p)) if p is not None else go


def step_ticks(ev, ctx):
    """the step's own ticks besides its parts: its instant elements' (a tick
    each) and the script's — the script's job (213's neighbour: update
    0x10037726 -> fcn.1000e131) runs the step and returns 0, the step's
    sequence pushed without a first run (fcn.10049216) starting on the
    tick after; a step that walks returns once its GoTo is pushed
    (fcn.1000e3e0 -> fcn.10007a10, the same way; 0x1001e0ce-0x1001e0d5),
    the walk's first step is the GoTo's first update's (walk_span), and
    after the arrival — the GoTo's +0x14 set in its tick (0x10007670) —
    the GoTo is done on its next update (0x10007409) and the step, run
    again there, pushes its sequence: 2 ticks besides the walk, 1 for a
    step at the place of the last (ctx['go']). Until 2026-09-27 a tick
    more, a first GoTo tick before the walk"""
    n = sum(1 for e in ev if e[0] in TICK_ELEMENTS
            or (e[0] == 'E2f40' and len(e) > 3 and e[3] == 'instant'))
    go = _place(ctx, _go_target(ev, ctx.get('inside_before')))
    walks = go is not None and go != ctx.get('go')
    if go is not None:
        ctx['go'] = go
    ctx['walks'] = walks
    # a step that calls its next step itself (CALLNEXT) builds no sequence
    # of its own: the next one's starts in the tick it runs again in
    own = 1 if any(e[0] == 'CALLNEXT' for e in ev) else 0
    return n + (WALK_STEP_TICKS if walks else 1) - own


def station_ticks(d, ev, ctx=None):
    """the step's parts [(object, action, ticks)] — DoActions, the enter/leave of
    E6bd4/E6c2e, a bar's enter and ticks (action 'bar'); the message elements
    instant; the rest unknown (ticks None). `ctx` carries the last hideout
    across steps (a leave whose object is a local of an earlier step). The
    step's own ticks (step_ticks) go with its first timed part, or with the
    next step's where it has none (a walk-by: 202's rake)"""
    ctx = {} if ctx is None else ctx
    ctx['inside_before'] = ctx.get('inside')
    parts = _station_parts(d, ev, ctx)
    extra = step_ticks(ev, ctx) + ctx.pop('carry', 0)
    # (the other actor's instants he waits through, a tick each)
    extra += sum(1 for i in _waited(d, ev, ctx.get('actor', 'neighbor'))
                 if ev[i][0][1:] in TICK_ELEMENTS)
    hid = ctx['inside_before']
    if ctx.get('walks') and hid and not any(e[0] in ('E6bd4', 'E6c2e') for e in ev[:1]):
        # a walk from inside a hideout: the route's first update pushes the
        # hideout's leave (fcn.10049190 -> fcn.10006c2e, with a first run,
        # 0x1000a840-0x1000a87e) and paths from the next — the leave's job
        # before the walk, from its `<actor>_out` (lap_steps puts it on the
        # step before: 208's platform, left on the way to the shoe cleaner)
        ctx['route_leave'] = hid
        if ctx.get('inside') == hid:
            ctx['inside'] = None
    k = next((i for i, p in enumerate(parts) if p[2] is not None), None)
    if k is None:
        ctx['carry'] = extra
    else:
        o, a, t = parts[k]
        parts[k] = (o, a, t + extra)
    return parts


def _station_parts(d, ev, ctx):
    parts = []
    for e in ev:
        k = e[0]
        if k == 'DO':
            names = [x for x in e[1] if not x.startswith('$')]
            who = ctx.get('actor', 'neighbor')
            rec = d._record(names[0], names[1], who) if len(names) >= 2 else None
            owner = rec[1].get('actor') if rec is not None else None
            if owner is not None and owner != who and owner.replace('/', '_') == names[0]:
                # an action of the object's own actor (209's fakir: `spit`,
                # actor="fire_fakir/fakir"): the job goes on its queue and his
                # steps go on without it (fcn.10049216 pushes it there)
                continue
            if len(names) >= 2:
                parts.append((names[0], names[1], d.action_ticks(names[0], names[1], who)))
                if ctx.get('pos'):
                    # the action's <translation> moves him (Data.translation)
                    tx, ty = d.translation(names[0], names[1], ctx.get('actor', 'neighbor'))
                    r, x, y = ctx['pos']
                    ctx['pos'] = (r, x + tx, y + ty)
            else:
                parts.append((names[0] if names else '?', '?', None))
                ctx['pos'] = None
        elif k == 'EA30':
            # fcn.1000ea30's enter: none when the actor is in the hideout
            # already (202's beer step on the mat he lies on)
            names = [x for x in e[1] if not x.startswith('$')]
            if names and ctx.get('inside') != names[0]:
                who = ctx.get('actor', 'neighbor')
                parts.append((names[0], 'enter', d.action_ticks(names[0], 'enter', who)))
                ctx['pos'] = None
            if names:
                ctx['hideout'] = names[0]; ctx['inside'] = names[0]
        elif k in ('E6bd4', 'E6c2e'):
            names = [x for x in e[1] if not x.startswith('$')]
            if not names and ctx.get('hideout'):
                names = [ctx['hideout']]
            act = 'enter' if k == 'E6bd4' else 'leave'
            if names: ctx['hideout'] = names[0]
            ctx['inside'] = names[0] if (names and act == 'enter') else None
            who = ctx.get('actor', 'neighbor')
            parts.append((names[0] if names else '?', act, d.action_ticks(names[0], act, who) if names else None))
            if act == 'leave' and names:
                # the leave places him at the hideout's `<actor>_out`
                # (_leave_place) — where a GoTo element after it walks from
                g = d.geom()
                q = _leave_place(g, d, names[0], who)
                tx, ty = d.translation(names[0], 'leave', who)
                ctx['pos'] = (g.room_of(d.real.get(names[0], names[0])), q[0] + tx, q[1] + ty) \
                    if q is not None else None
            elif act == 'enter':
                ctx['pos'] = None
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
        elif k == 'ODO':
            # another actor's job (run_step: pushed onto its queue): his
            # steps go on without it, but for one whose record posts him a
            # behaviour, which the step after it waits for (204's gong: the
            # Elvis's `use`, behavior="gong" behavioractor="neighbor", and
            # the idle step 0x10031b70's latch); the fakir's `play` and
            # `stop` (208) and the kid's dive (202) and sand lion (205) none
            who = ctx.get('actor', 'neighbor')
            names = [x for x in e[1] if not x.startswith('$')]
            if _waits_on(d, e, who):
                parts.append((names[0], names[1], d.action_ticks(names[0], names[1], who)))
        elif k == 'WAIT':
            parts.append(('-', 'wait', e[2][-1] if e[2] else None))
        elif k == 'GOEL':
            # a GoTo element: pushed with a first run (the sequence's
            # update 0x1000ad52, fcn.10049246), its walk from its first
            # update to the arrival (walk_span's ticks); done on its next
            # update, in the tick the sequence pushes the next element —
            # from where the flow's last hideout leave put him, else unknown
            names = [x for x in e[1] if not x.startswith('$')]
            obj = d.real.get(names[0], names[0]) if names else None
            hs = names[1] if len(names) > 1 else None
            t = None
            if obj and ctx.get('pos'):
                t, pos = walk_span(d.geom(), ctx['pos'], obj, ctx.get('actor', 'neighbor'), d, hotspot=hs)
                ctx['pos'] = pos if t is not None else None
            parts.append((names[0] if names else '?', 'goto', t))
        elif k == 'E2f40' and len(e) > 3 and e[3] == 'instant':
            continue
        elif k == 'Ef779':
            # an object shown in a room: vtable 0x100ab978, update 0x1000ce9c
            # (fcn.10043d66, then 1 at once)
            continue
        elif k == 'Eebbf':
            # the camera back (fcn.1000ebbf -> fcn.1000dc0c: vtable
            # 0x100ab954, the camera's update 0x1000d70b): its flags from
            # the builder's argument, bit 0 clear -> fcn.1000d559, whose one
            # return is `mov al, 1` (0x1000d6fd) — done on its first update
            # (206's being_hit after the SHOUT, 0x1002df34)
            continue
        elif k == 'Ef51a':
            # the camera on the neighbour, done on its first update: the
            # builder fcn.1000f51a sets the flag 8 for a nonzero last
            # argument, with which the update (0x1000d70b -> fcn.1000d31a,
            # 0x1000d33d-0x1000d354) waits while the level's slot 0x50 holds
            # — [level+0xc] set, Woody's mini-game running (the level update
            # runs the game object at +0xc, 0x10044816-0x1004482b); no
            # mini-game in the lap, no wait
            continue
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
    out = []; ctx = {'geom': Geometry(n), 'data': d}
    for i, (cur, ev, nxt) in enumerate(steps):
        ic = [e[1] for e in ev if e[0] == 'IC']
        objs = set()
        for e in ev:
            if len(e) < 2:
                continue
            for x in (e[1] if isinstance(e[1], list) else [e[1]]):
                if isinstance(x, str) and not x.startswith('$'):
                    objs.add(x)
        parts = station_ticks(d, ev, ctx)
        hid = ctx.pop('route_leave', None)
        if hid and out:
            # the route's leave of the hideout the last step left him in
            # (station_ticks): its time and placement the last row's
            out[-1][4].append((hid, 'leave', d.action_ticks(hid, 'leave')))
            LAP_LEAVES.setdefault(n, {})[out[-1][0]] = hid
        out.append((i, cur, (ic[0][0] if ic and ic[0] else '-'), objs, parts))
        LAP_WALKS.setdefault(n, {})[i] = ctx.get('walks', False)
        LAP_GOS.setdefault(n, {})[i] = _lap_target(ev, ctx.get('inside_before'))
        if any(e[0] == 'E6c2e' for e in ev):
            LAP_LEAVES.setdefault(n, {})[i] = ctx.get('hideout')
    hid = ctx.get('inside')
    if loop is not None and out and hid and LAP_WALKS[n].get(loop):
        # (the lap's last step left him inside and the loop's first walks)
        out[-1][4].append((hid, 'leave', d.action_ticks(hid, 'leave')))
        LAP_LEAVES.setdefault(n, {})[out[-1][0]] = hid
    return out, loop


def role_lap(n, start, actor):
    """another actor's lap by her script from `start` (212's Mother
    0x10035048, 213's 0x100372f0, 214's 0x1003a0b8): [(step, parts)] as
    lap_steps times the neighbour's — station_ticks with the actor's
    records (her DoActions' jobs, the step's own ticks), a walk from inside
    a hideout starting with the route's leave of it (the last step's part)"""
    d = Data(n)
    steps, loop = walk(Level(n), start)
    ctx = {'geom': Geometry(n), 'data': d, 'actor': actor}
    if loop is not None:
        # the lap is a cycle: a first round sets where the last step leaves
        # her (inside a hideout — 214's chair, entered by 0x10039e6c's
        # go-and-enter, so the bar step after it finds her in it) and the
        # ticks a step hands on; the second is the lap's
        steps = steps[loop:]
        for _cur, ev, _nxt in steps:
            station_ticks(d, ev, ctx)
            ctx.pop('route_leave', None)
    out = []; lead = None
    for cur, ev, _nxt in steps:
        parts = station_ticks(d, ev, ctx)
        hid = ctx.pop('route_leave', None)
        if hid:
            leave = (hid, 'leave', d.action_ticks(hid, 'leave', actor))
            if out:
                out[-1][1].append(leave)
            else:
                # the first step's walk leaves the hideout the lap's last
                # row left her in (209's dressing room, on the way to the
                # fakir's shop)
                lead = leave
        out.append((cur, parts))
    if lead is not None and out:
        out[-1][1].append(lead)
    return out


# {level: {lap row: whether its step walks}} (lap_steps, step_ticks): a tricked
# visit's stand starts as the row's own stay does (_flow)
LAP_WALKS = {}
# {level: {lap row: the hideout its step leaves}} (lap_steps): the leave places
# him at the hideout's `<actor>_out` (_leave_place, code_places)
LAP_LEAVES = {}
# {level: {lap row: the object its step walks to}} (lap_steps, _lap_target): a
# visit whose parts span steps walks between them (_visit_walks, code_places)
LAP_GOS = {}


def _lap_target(ev, inside=None):
    """the object the step walks to on the lap: its GoTo's (fcn.1000e3e0) —
    where the name is a local, the IsVariant's pick or the first DoAction's
    object —, else the bar helper's (_go_target)"""
    for e in ev:
        if e[0] == 'GO':
            target = e[1] if e[1] and not str(e[1]).startswith('$') else None
            if target is None:
                pick = [x[2] for x in ev if x[0] == 'IFVAR' and x[2] and not str(x[2]).startswith('$')]
                dos = [x[1][0] for x in ev if x[0] == 'DO' and x[1] and not x[1][0].startswith('$') and x[1][0] != 'neighbor']
                target = (pick or dos or [None])[0]
            return target
    return _go_target(ev, inside)


def _leave_place(g, d, obj, actor='neighbor'):
    """where a hideout leave (fcn.10006c2e: vtable 0x100ab334, update
    0x1000690a) puts the actor before its `leave` plays: the object's
    `<actor>_out` hotspot — the actor's name and "out" joined
    (fcn.10049057), looked up and set as his position (fcn.10049e01,
    fcn.100418f6; 0x1000699c-0x10006a3d) — 213's picnic 5 px left of its
    `neighbor` hotspot and 10 up, the tricked picnic 225 px right, 209's
    hot coal 293 px right; None where the object has none (the lookup,
    fcn.10049a08, gives (0, 0), the object's own position: not taken)"""
    o = d.real.get(obj, obj) if (d is not None and obj) else obj
    return g.point(o, actor + '_out', exact=True) if o else None


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
        first horizontal tick of a movement that starts from the stand
        ms1 / ms3 facing its way adds the record's `start` (0x10009332,
        the movement's +0x2c) — a movement after another's vertical run
        starts from that run's stand, so at most a tick a walk, not
        counted here"""
        d = abs(d)
        return -(-d // s) if d else 0

    def leg_direct(self, x, y, tx, ty, actor='neighbor', gait='mg'):
        """a movement made with +0x31 set (fcn.10008f6a's last argument, 1
        from the door pass: its walk to `<actor>_in`, fcn.10003130, and its
        run back to the far room's floor, fcn.10003454): fcn.10009177 takes
        x first at the current y, then y — no floor line"""
        sp = self.speed[actor]
        v = sp[gait + '0'][0]; vd = sp[gait + '2'][0]
        h = sp[gait + '1'][0]
        return self.run(tx - x, h) + self.run(ty - y, v if ty < y else vd)

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


def walk_span(g, frm, to, actor='neighbor', data=None, detail=None, hotspot=None):
    """(room, x, y) -> an object's `<actor>` hotspot — or the one the GoTo
    names (`hotspot`: its +0xc, fcn.10049e01 at 0x1000744d; the actor's
    name where it has none, fcn.1003cc45 at 0x10007430) — as GameLogic.dll
    runs a GoTo: (the ticks from the step that pushes it to the arrival's,
    the position). The step returns once fcn.1000e3e0 has pushed the GoTo
    without a first run (0x1001e0ce-0x1001e0d5) and runs again when it is
    done. The GoTo's first update pushes the route (fcn.1000a4aa, vtable
    0x100ab688, update 0x1000a80c) with a first run (0x10007504 ->
    fcn.10049246), and the route pushes its jobs the same way, each in the
    tick the last is done (the runner, fcn.100492a8, goes on past a done
    job, 0x10049338-0x10049386): per hop a movement to the near door's
    `<actor>` hotspot (fcn.1000901b, 0x1000ab8d; the route tests the point
    first, 0x1000aac2) and the door pass (fcn.10003d50, 0x1000ab17), then
    the movement to the target (0x1000ac45). A movement (vtable
    0x100ab4f0, update 0x10009a90) steps on every update, its first
    included (fcn.10009889 -> fcn.10009215), and is done in the update of
    its last step (fcn.10007a96 after the step, 0x10009a55): s steps
    pushed with a first run end s - 1 ticks after the tick it starts in.
    The pass (update 0x10003a19) goes by states, each job it pushes with a
    first run — one with no step is done at once and the next state waits
    for the next update: 0 the walk to `<actor>_in` (fcn.10003130:
    fcn.10008f6a, +0x31 set — Geometry.leg_direct); 2 the near door's
    `enter` where it has one for the actor (fcn.10003647), else the
    movement straight to the far door's `<actor>_out` (fcn.100037f8 ->
    fcn.100090bd, the start's y the floor line); 3 the placement at
    `<actor>_out` and the far door's `leave` (fcn.10003236); 4 the far
    room and a movement back to its floor line, x kept within it
    (fcn.10003454, 0x10003544-0x100035ba: +0x31 set, pushed without a
    first run — from the next tick; its test against L"fro" matches no
    room); 5 done (0x10003b47), in the tick that movement is. The last
    movement's arrival makes the route done (0x1000acb5) and sets the
    GoTo's +0x14 (0x10007670) in its tick; the GoTo is done on its next
    update (0x10007409) and the step, run again, pushes its sequence
    without a first run: the step's own 2 ticks (step_ticks). `detail`
    collects (kind, ticks) parts"""
    room, x, y = frm
    if isinstance(to, tuple):
        # a point (room, x, y): the GoTo's position mode (fcn.1000e601's
        # walk to another actor)
        r2, p2 = to[0], (to[1], to[2])
    else:
        r2 = g.room_of(to); p2 = g.point(to, hotspot, exact=True) if hotspot else g.point(to, actor)
    if p2 is None or r2 not in g.rooms or room not in g.rooms:
        return None, frm
    if room == r2 and (x, y) == tuple(p2):
        return 0, frm             # there: fcn.1000e3e0 pushes no GoTo
    rt = g.route(room, (x, y), r2, p2, actor)
    if rt is None:
        return None, frm
    t = 1                         # the GoTo's first update: the route's, its first job's
    for din, dout in rt:
        nb = g.point(din, actor, exact=True)
        a = g.point(din, actor + '_in', exact=True)
        b = g.point(dout, actor + '_out', exact=True)
        if nb is None or a is None or b is None:
            return None, frm
        t0 = t
        s = g.leg(x, y, nb[0], nb[1], g.floor(room), actor)
        if s:
            t += s - 1            # to the `<actor>` hotspot
        if detail is not None:
            detail.append(('room', t - t0)); t0 = t
        s = g.leg_direct(nb[0], nb[1], a[0], a[1], actor)
        t += s - 1 if s else 1    # state 0: to `<actor>_in`
        if actor in g.door_acts.get(din, ()):
            je = data.action_ticks(din, 'enter', actor) if data is not None else None
            jl = data.action_ticks(dout, 'leave', actor) if data is not None else None
            if je is None or jl is None:
                return None, frm
            t += je + jl          # states 2 and 3: the enter, the leave
        else:
            s = g.leg(a[0], a[1], b[0], b[1], a[1], actor)
            t += s - 1 if s else 1
        room = g.room_of(dout)
        if room not in g.rooms:
            return None, frm
        fr = g.rooms[room]
        cx, cy = min(max(b[0], fr['x1']), fr['x2']), fr['y']
        s = g.leg_direct(b[0], b[1], cx, cy, actor)
        t += s if s else 1        # state 4's movement, from the next tick
        x, y = cx, cy
        if detail is not None:
            detail.append(('pass %s' % din, t - t0))
    t0 = t
    s = g.leg(x, y, p2[0], p2[1], g.floor(room), actor)
    if s:
        t += s - 1
    if detail is not None:
        detail.append(('room', t - t0))
    return t, (r2, p2[0], p2[1])


def lap_estimate(n, verbose=False):
    """the lap's seconds: the stays of lap_steps plus the walks between the steps'
    targets (walk_span; walk_ticks' sum of the legs until 2026-09-27); None
    parts counted as 0 and reported"""
    d = Data(n); g = Geometry(n)
    st = level_start(n); lv = Level(n)
    steps, loop = walk(lv, st)
    if loop is None:
        return None
    ctx = {'geom': g, 'data': d}
    pos = None; total = 0; walks = 0; stays = 0; unknown = []
    # the lap, closed on its first step: the steps from the loop's (the walk
    # up to it — 213's tub repair, 206's reling — is the level's start, not
    # the lap's; rotated in until 2026-10-03)
    order = steps[loop:] + steps[loop:loop + 1]
    for k, (cur, ev, nxt) in enumerate(order):
        parts = station_ticks(d, ev, ctx)
        rl = ctx.pop('route_leave', None)
        if rl and pos is not None:
            # the route leaves the hideout first (station_ticks): its leave's
            # job, the walk from its `<actor>_out`
            q = _leave_place(g, d, rl)
            if q is not None:
                tx, ty = d.translation(rl, 'leave')
                pos = (g.room_of(d.real.get(rl, rl)), q[0] + tx, q[1] + ty)
            lt = d.action_ticks(rl, 'leave')
            if lt is None:
                unknown.append('%s.leave' % short(rl))
            elif k > 0:
                stays += lt
            if verbose: print('   stay %-30s %5.1f s' % ('%s.leave' % short(rl), (lt or 0) / 12.0))
        target = _lap_target(ev, ctx.get('inside_before'))
        if target:
            real = d.real.get(target, target)
            if pos is None:
                p = g.point(real)
                pos = (g.room_of(real), p[0], p[1]) if p else None
            else:
                t, pos2 = walk_span(g, pos, real, data=d)
                if t is None:
                    unknown.append('walk to %s' % real)
                else:
                    if k > 0: walks += t
                    pos = pos2
                if verbose: print('   walk -> %-30s %5.1f s' % (real, (t or 0) / 12.0))
        if k == len(order) - 1:
            break            # the closing step: its walk ends the lap
        hid = ctx.get('hideout') if any(e[0] == 'E6c2e' for e in ev) else None
        place = _leave_place(g, d, hid) if hid else None
        kl = next((k for k in range(len(parts) - 1, -1, -1)
                   if parts[k][1] == 'leave' and parts[k][0] == hid), None) if place else None
        if pos is not None and kl is not None:
            # a hideout's leave places him at its `<actor>_out` (_leave_place:
            # 212's water exit after the ledge), the leave's and the later
            # parts' translations from there
            pos = (g.room_of(d.real.get(hid, hid)), place[0], place[1])
            for o, a, _t in parts[kl:]:
                tx, ty = d.translation(o, a)
                pos = (pos[0], pos[1] + tx, pos[2] + ty)
        elif pos is not None and not any(a == 'leave' for _o, a, _t in parts):
            # the actions' translations move the actor off the hotspot: the
            # next walk leaves from there
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
          # (the fakir's `play` and `stop` his own queue's: pushed onto the
          # fakir, 0x1001efba-0x1001efc4, not waited for; the platform left by
          # the walk to the shoe cleaner, the route's first job)
          'IndianPlatform': [(None, 'platform', 'enter'), (None, 'platform', 'bar'),
                             (None, 'platform', 'leave')],
          'ShoeMachine': [(None, 'shoe_cleaner', 'use')],
          'AngryElephant': [('elephant', 'neighbor', 'lookaround'), (None, 'elephant', 'fool')]},
    # the fakir's step: his `burn` at the groove, the fakir's `spit` its own
    # actor's job (fire_fakir/fakir's queue)
    209: {'FireFakir': [(None, 'groove', 'burn')],
          'Cow': [('cow', 'neighbor', 'lookaround'), (None, 'cow', 'ride')],
          # the shoe step puts the shoes on the mat and enters the curtain
          # (0x10020c72) — the mobile's first HotShoe visit, ShoeOff and
          # TadjMahalEnter —, the curtain's bar and its leave are the Taj's,
          # the take the second shoe visit's (0x10020806)
          'TadjMahal': [(None, 'curtain', 'bar'), (None, 'curtain', 'leave')],
          'HotShoe': [[(None, 'shoe_mat', 'put'), (None, 'curtain', 'enter')],
                      [(None, 'shoe_mat_empty', 'take')]],
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
          # the picnic: its step waits for Olga's `boat` (the latch +0x18,
          # 0x100383f6 — her `enter` of the picnic posts it, sent there by
          # his tortilla step's `boat` as he arrives, 0x100386ad), then his
          # `enter` and `leave`
          'BoatPicnic': [(None, 'picnic', 'enter'), (None, 'picnic', 'leave')],
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
    # his lap after the pillow lesson (0x1002e926 -> 0x1002e63c; the mobile's
    # loop from its selected index, DogFifi to the dynamite): Fifi taken off
    # her used blanket and put on the ramp, loaded; the harpoon taken, the
    # bear shot, the harpoon put back, Fifi taken; put down at the dumbbell,
    # Olga's marvel at his workout, taken again; put back on her blanket;
    # the dynamite bag's take, and the next step's reling (its GoTo walks
    # him on, _visit_walks): the lookaround and the fishing. Per visit: the
    # mobile's two DogFifi visits (the take, the put), three LaunchPad (the
    # load, the shot, Fifi taken at the ramp), two Harpoon (the take, the
    # put)
    206: {'DogFifi': [[(None, 'topleft_usedblanket', 'empty'), (None, 'topleft_fifi', 'take')],
                      [(None, 'topleft_fifi', 'put'), (None, 'topleft_usedblanket', 'ms')]],
          'LaunchPad': [[(None, 'bottomleft_fifi', 'put'), (None, 'bottomleft_ramp', 'load')],
                        [(None, 'bottomleft_ramp', 'shootbear')],
                        [(None, 'bottomleft_fifi', 'take')]],
          'Harpoon': [[(None, 'bottomleft_harpoon', 'take')], [(None, 'bottomleft_harpoon', 'put')]],
          'FifiWeightsDrop': [(None, 'bottomright_fifi', 'put')],
          'Weights': [(None, 'olga', 'marvel'), (None, 'bottomright_dumbbell', 'use'), (None, 'olga', 'ms')],
          'FifiWeightsGrab': [(None, 'bottomright_fifi', 'take')],
          'DynamiteBox': [(None, 'topright_dynamitebag', 'take'), (None, 'neighbor', 'lookaround'),
                          (None, 'topright_reling', 'fish')]},
    # his lap after the dive (the bar's drink, the elephant, the shell on
    # Olga's mat, the kid's castle, his towel's bar); the board waits for
    # the Mother in her deck chair and is timed per clip (pc_durations_s2.py
    # CLIPS, Level207MotherBehavior)
    # his lap from the gong's `leave` (the hot dogs, the jade, the rickshaw
    # Olga sits in, the headbanger, the gong the elvis figure strikes — its
    # behavior="gong" on him, posted as the strike's job ends, sends him out
    # of it)
    204: {'HotDog': [('hotdogshop', 'neighbor', 'lookaround'), (None, 'hotdogshop', 'use')],
          'JadeNecklace': [(None, 'jadedummy', 'look')],
          'PullKart': [(None, 'rickshaw', 'use')],
          'Karate': [(None, 'headbanging', 'use')],
          # the gong step goes to it and enters it (fcn.1000ea30: the
          # `enter`, time 0, before the strike's `use`)
          'GongDrumstick': [(None, 'gong', 'enter'), (None, 'gong', 'use')]},
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
    by PAIRS[n] and the walks between a visit's steps (_visit_walks); an item
    whose part is missing or untimed is left out. A lap the walk does not close
    (210's: his chair waits for the Mother's call, a message the walk does not
    follow) is the walk from its start (LAP_START), each of its stations once"""
    out = {}
    lap, pairs = _paired_parts(n)
    d, g = Data(n), Geometry(n)
    for item, (many, visits) in pairs.items():
        if all(v is not None and None not in [t for _i, _j, (_o, _a, t) in v] for v in visits):
            walks = [_visit_walks(n, d, g, lap, v) for v in visits]
            if None in walks:
                continue
            secs = [round((sum(t for _i, _j, (_o, _a, t) in v) + w) / 12.0, 2) for v, w in zip(visits, walks)]
            out[item] = secs if many else secs[0]
    return out


def _end_of(d, g, go, parts, hid=None):
    """(room, x, y) where a step leaves him (lap_estimate's position): a
    hideout's leave at its `<actor>_out` (_leave_place) and the translations
    of the parts from the leave on, else the GoTo object's hotspot and the
    parts' translations (none where a part is a leave); None where it is not
    known"""
    place = _leave_place(g, d, hid) if hid else None
    kl = next((k for k in range(len(parts) - 1, -1, -1)
               if parts[k][1] == 'leave' and parts[k][0] == hid), None) if place else None
    if kl is not None:
        room, x, y = g.room_of(d.real.get(hid, hid)), place[0], place[1]
        rest = parts[kl:]
    else:
        real = d.real.get(go, go) if go else None
        p = g.point(real) if real else None
        if p is None:
            return None
        room, x, y = g.room_of(real), p[0], p[1]
        rest = [] if any(a == 'leave' for _o, a, _t in parts) else parts
    for o, a, _t in rest:
        tx, ty = d.translation(o, a)
        x, y = x + tx, y + ty
    return (room, x, y)


def _visit_walks(n, d, g, lap, v):
    """the ticks of the walks inside a visit whose parts span steps: from
    where one step leaves him (_end_of) to the next one's GoTo object
    (LAP_GOS, walk_span) — 206's dynamite: the bag's `take` (0x1002caa1),
    then 0x1002c674 walks him to the reling, 12 ticks, before its lookaround
    and the fishing; 0 for a visit of one step or of steps at one object,
    None where a walk has no known end"""
    rows = sorted(set(i for i, _j, _p in v))
    gos = LAP_GOS.get(n, {})
    total = 0
    for a, b in zip(rows, rows[1:]):
        ta, tb = gos.get(lap[a][0]), gos.get(lap[b][0])
        if tb is None or (ta is not None and d.real.get(ta, ta) == d.real.get(tb, tb)):
            continue
        pos = _end_of(d, g, ta, lap[a][4], LAP_LEAVES.get(n, {}).get(lap[a][0]))
        t, _pos = walk_span(g, pos, d.real.get(tb, tb), data=d) if pos is not None else (None, None)
        if t is None:
            return None
        total += t
    return total


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


def code_places(n):
    """{mobile item: [(x, y) or None per visit]}: where the next walk leaves
    from after a visit whose step leaves a hideout (_leave_place) — the
    placement at the hideout's `<actor>_out`, then the translations of the
    leave and the parts after it —, or whose last step walks him on to
    another object (_visit_walks: 206's dynamite, fished at the reling 86 px
    right of the bag); items with no such visit left out"""
    d = Data(n); g = Geometry(n)
    lap, pairs = _paired_parts(n)
    out = {}
    for item, (many, visits) in pairs.items():
        if any(v is None for v in visits):
            continue
        per = []
        for v in visits:
            i, j = max((i, j) for i, j, _p in v)
            parts = lap[i][4]
            hid = LAP_LEAVES.get(n, {}).get(lap[i][0])
            place = _leave_place(g, d, hid) if hid else None
            k = next((k for k in range(len(parts) - 1, -1, -1)
                      if parts[k][1] == 'leave' and parts[k][0] == hid), None)
            if place is not None and k is not None and j == len(parts) - 1:
                dx = sum(d.translation(o, a)[0] for o, a, _t in parts[k:])
                dy = sum(d.translation(o, a)[1] for o, a, _t in parts[k:])
                per.append((place[0] + dx, place[1] + dy))
                continue
            i0 = min(i2 for i2, _j, _p in v)
            g0, g1 = LAP_GOS.get(n, {}).get(lap[i0][0]), LAP_GOS.get(n, {}).get(lap[i][0])
            if i0 != i and j == len(parts) - 1 and g0 and g1 \
                    and d.real.get(g0, g0) != d.real.get(g1, g1):
                # the visit's last step walks him on to another object
                # (_visit_walks): his next walk leaves from there
                q = _end_of(d, g, g1, parts)
                per.append((q[1], q[2]) if q else None)
                continue
            per.append(None)
        if any(x is not None for x in per):
            out[item] = per
    return out


# a station's tricked-with-its-linked-item variant where it is another step of
# the script than the lap's: 201's puddle by the open rail (the combo,
# 0x100297c5: crash_long; the lap's puddle step 0x1002847f plays crash_short)
LINKED_STEP = {201: {'WaterPuddle': 0x100297c5}}
# a linked variant whose step hands over to a poll step before its SHOUT:
# {level: {item: (the poll step, the object, its animation, the co-actor)}} —
# 207's sand castle over the hedgehog's towel ends with the castle's fall
# (its behavior kid_cry on Olga), and 0x1001513f re-runs until the destroyed
# castle shows Olga's `n_lift` (fcn.1004948f, the object's animation, against
# the global n_lift, 0x100151dd-0x10015229), then plays the neighbour's
# `enter` of beachleft/bill (the billboard, record `bill` at 30), its
# `leave`, SHOUT 2, the flag 0x40000 and the camera off, and goes back to
# the lap's next step 0x10014d46
LINKED_CONT = {207: {'SandCastle': (0x1001513f, 'beachleft_sandcastle_destroyed', 'n_lift', 'olga')}}
# a tricked visit whose reaction is not in the station's step: {level: {item:
# (kind, co-actor, steps)}} — 'steps': the steps the tricked flow goes on to,
# in order (204's gong: the elvis hits him, the action's behavior `gong` on
# him sends his script to 0x10032f52 — its tricked branch the leave, SHOUT
# 3, the camera off and the repair, 0x10033046-0x10033140; 205's nailed
# skis: the run back, pant, SHOUT 1 and the repair, 0x10024fc2); 'fight':
# the co-actor's run to him and the generic `fight` (fcn.1000eb19; the
# action's behavior olga_fight / mother_fight on him), then the neighbour's
# step his behaviour handler picks for it (204's rickshaw: olga_fight ->
# 0x10032b6f, 0x100331e4-0x1003322d; 207's shell: 0x1001596a, 0x1001736a;
# 210's elephant: the Mother, mother_fight -> 0x1001a379, 0x1001b597-
# 0x1001b5ba; 214's shower 0x1003ba90 and bouquet 0x1003b677 on
# olga_fight, the pistol 0x1003b328 on mother_fight, 0x1003bb9a-0x1003bbff)
# — 'stand' fourth: the continuation's parts before its SHOUT go on the
# tricked stand where the port has no mechanism of its own for them (204's
# gong: the gong's `leave` in 0x10032f52 before SHOUT 3; 205's skis run back
# with PCTrickReturn, 211's rush with RUSH)
TRICKED_CONT = {204: {'GongDrumstick': ('steps', None, (0x10032f52,), 'stand'),
                      'PullKart': ('fight', 'olga', (0x10032b6f,))},
                205: {'WaterSkiis': ('steps', None, (0x10024fc2,))},
                207: {'Shell': ('fight', 'olga', (0x1001596a,))},
                210: {'Elephant': ('fight', 'mother', (0x1001a379,))},
                211: {'Sweets': ('steps', None, (0x10030dc2, 0x10030d0f, 0x10030b9d))},
                214: {'CaptainDoor': ('steps', None, (0x1003af18,)),
                      'Shower': ('fight', 'olga', (0x1003ba90,)),
                      'Bouquet': ('fight', 'olga', (0x1003b677,)),
                      'Pistol': ('fight', 'mother', (0x1003b328,))},
                # 213's termites: the crash and the `leave` of the tricked
                # picnic, the jump into the water and out, to its `beat`
                # (the GoTo element 0x10038516) in `fear` — his `leave`
                # sends Olga (`leave`) out of the boat into the water and on
                # to him (0x100391cc, 0x1003917e: fcn.1000eb19), whose fight
                # the step 0x10038221 waits for (its latch +0x10), SHOUT 1
                213: {'BoatPicnic': ('fight', 'olga', (0x10038221,))}}
# the co-actor's own steps between the behaviour his tricked flow posts her
# and her walk to him: {level: {item: (her step, the actor, his part that
# posts it)}} — 213's termites: his `leave` of the tricked picnic carries
# behavior="leave" for Olga (me_c2 objects.xml); her step 0x100391cc (its
# latch +0x14) leaves the boat, jumps into the water and climbs out
# (bottomright/water2), and 0x1003917e sends her to him (fcn.1000eb19 ->
# fcn.1000e601: a GoTo to his x less or plus FIGHT_GAP on her side) and on to
# the fight
FIGHT_BEFORE = {213: {'BoatPicnic': (0x100391cc, 'olga', ('bottomright_picnic_manip', 'leave'))}}
# a tricked visit that pays in another actor's job her own script starts on
# his part: {level: {item: ((his object, action), the actor, (her object,
# action))}} — 210's elephant: Fifi's step 0x10018239 waits while she is
# `inv` (0x1001826c, her animation against `inv`) — his `put1` shows her —
# and then builds her sequence, the bat's `disappear` set at once
# (fcn.100419a3), bar/elefant's `dogattack_bat` (its record at 5 ticks),
# the bat hidden and her `fall` (0x10018337-0x100183fc): the attack's first
# update the tick after the offer's (the sequence pushed without a first
# run), the record its `time` into it
CREDIT_BY = {210: {'Elephant': (('fifi', 'put1'), 'fifi', ('bar_elefant', 'dogattack_bat'))}}
# ... and the job of hers whose record posts the fighter her behaviour, where
# his flow's own parts post none: {level: {item: her step}} — 210's
# elephant: Fifi's sequence (0x10018239: the attack, the bat hidden, her
# `fall`, whose record posts `crash` to the Mother as its job ends), her
# first update the tick after the offer of his `put1`'s end
POST_BY = {210: {'Elephant': 0x10018239}}


# the gap fcn.1000e601 leaves between a fighter and the actor she walks to:
# [0x100cc814] = 50 px, taken off his x from her side (0x1000e706/0x1000e70e)
FIGHT_GAP = 50


def _hit_after(n, d, lv, bytes0, ev, own, walked, spec):
    """the ticks from the end of his tricked flow to the first update of the
    co-actor's fight (FIGHT_BEFORE): his part posts her behaviour as its job
    ends (the DoActions' state 2); her step reads its latch on the tick after
    (the offer's tick, as the call of 210), builds its sequence (its own
    tick) and plays it (_flow for her records); the step after it pushes her
    GoTo to him without a first run (fcn.1000e601, fcn.10049216) — walk_span
    from where her flow's last leave put her to his place less FIGHT_GAP —
    and, run again once she is there, the fight without one: its first
    update two ticks after her arrival's. None where a part is unknown"""
    stp, actor, (po, pa) = spec
    fl = _flow(d, ev, own, walked)
    post = next((t + x[2] for t, kind, x in fl
                 if kind == 'part' and x[0] == po and x[1] == pa and x[2] is not None), None)
    if post is None or any(kind == 'unknown' for _t, kind, _x in fl):
        return None
    end = fl[-1][0]
    evh, _nx = run_step(lv, stp, dict(bytes0), latch=1)
    flh = _flow(d, evh, walked=False, actor=actor)
    if any(kind == 'unknown' for _t, kind, _x in flh):
        return None
    her_end = post + 1 + flh[-1][0]
    ctxh = {'actor': actor}
    _station_parts(d, evh, ctxh)
    ctx = {}
    _station_parts(d, ev, ctx)
    frm, his = ctxh.get('pos'), ctx.get('pos')
    if frm is None or his is None:
        return None
    x = his[1] - FIGHT_GAP if frm[1] < his[1] else his[1] + FIGHT_GAP
    t, _p = walk_span(d.geom(), frm, (his[0], x, his[2]), actor, d)
    if t is None:
        return None
    return her_end + t + 2 - end


# the scene a tricked continuation needs besides the item's own trick: 211's
# sweets with the toilet sign tricked (the mobile's LinkedTrickRushToilet)
# run to the women's toilet (0x10030dc2: wcright's puke, the beat, then SHOUT
# 1 in 0x10030d0f and the sign's repair in 0x10030b9d)
CONT_SCENE = {211: {'Sweets': ('ToiletSign',)},
              # 214's door opened: up to the bridge, the steering with the
              # drugged captain (no SHOUT), then the pistol
              214: {'CaptainDoor': ('CaptainMug',)}}
# a mobile station the lap reaches only through another's tricked flow:
# {level: {item: (the step, the tricks in the scene)}} — 214's wheel, up on
# the bridge from the opened captain's door (0x1003af18: the steering's
# variant, the manipulated one first; the captain drugged by the mug)
TRICKED_VIA = {214: {'CaptainWheel': (0x1003af18, ('CaptainDoor', 'CaptainMug', 'CaptainWheel'))}}
# a tricked visit read from one lap row's step apart from its pairing, whose
# flow hands over to a step off the lap: {level: {item: (the walk's row,
# the objects of its parts that are the item's)}} — the row's step run
# with the item's trick in the scene, then the step it hands over to, up
# to its SHOUT, after that step's walk (206's dynamite bag, the adhesive's:
# taken, then 0x1002c550 walks him to the reling, the lookaround and the
# explode, SHOUT 1; the untricked visit's second step, 0x1002c674, is the
# lap's own)
TRICKED_ROWS = {206: {'DynamiteBox': (9, ('dynamitebag',))}}
# the item whose trick puts a station's tricked variant in the scene where
# the mobile station takes no inventory of its own, with what else the
# variant needs shown: 214's shower, tricked by the fish in the wash bucket
# (ActivateItemTrick; bottomleft/washbucket_manip) while Olga showers — the
# step's bucket branch is the guarded shower's (0x1003b87b; the mobile's
# trigger is her shower pose, WashbucketBehavior)
TRICKED_BY = {214: {'Shower': ('Washbucket', {'bottomleft_shipshower_guarded'}, {'bottomleft_shipshower'})},
              # 203's stage: the PC breaks it through the generator's tights
              # alone (cn_c2 combine.xml has no microphone trick; the stage
              # step asks for generator_manip, 0x1003450b); the mobile's
              # DieselGenerator activates the Microphone's trick
              # (ActivateItemTrick)
              203: {'Microphone': ('DieselGenerator', set(), set())}}
# the level's aux script, whose update runs each level tick (the `aux` entry
# of the scripts' factory table: me_c1's factory 0x10034dba, registered at
# 0x1001265b, builds the handler of vtable 0x100af928, whose update 0x10034fec
# calls these two): what it does to a trick's scene belongs to the trick —
# 212's fed parrot eats (parrot_manip's `use`, actor aux) and leaves its shit
# on the ledge (fcn.10034e05: the show element at 0x10034f09) before his
# ledge visit finds it (0x10035577); the throne's halves turn the wheel
# (fcn.10034c0f)
AUX_UPDATE = {212: (0x10034c0f, 0x10034e05)}
# a trick one step arms and a later step fires: 206's rabbit on the ramp.
# The load step 0x1002e3df asks IfVariant ramp / ramp_manip: with the rabbit
# on, the manipulated ramp's `load` and the hand-over to the harpoon step
# 0x1002e27f (its IfVariant harpoon / harpoon_manip decides the shot: the
# plain take -> 0x1002df9b's shootrabbit, the rubber's -> 0x1002e0fd's
# rubberrabbit), whose shot's behavior fifi_crash sends the Mother to him;
# 0x1002de6a waits for her hit (the latch at [step+0x24], fcn.10013269) and
# plays SHOUT 1, 0x1002dbc4 the ramp's repair. The shoot step of the lap
# (0x1002d948) asks nothing: a rabbit put on after the load waits for the
# next load. Without the rabbit the take step 0x1002dd0a's rubber branch
# shoots the rubber bear at once (0x1002da29: the ramp's rubberbear, SHOUT
# 1) and goes on to the put (0x1002d578), past the lap's shoot step; the put
# step switches a manipulated harpoon back (a rubber put on after the take
# is gone). The mobile's pad visits (RottweilerActionManager: LaunchPad,
# Harpoon, LaunchPad, Harpoon, LaunchPad) are the rows 2-6: the load, the
# take, the shoot, the put, Fifi's take. (item: the arming row, the shot's
# step in the flow from it, the co-actor, the arming and the firing visit
# of the item among its lap visits; the linked item: the visit whose
# variant decides it (the take), the visit that drops a late one (the put),
# the take's row)
TRICKED_ARM = {206: {'LaunchPad': (2, 2, 'mother', 1, 2)}}
TRICKED_ARM_LINKED = {206: {'Harpoon': (1, 2, 3)}}
# a tricked flow's toilet rush and what the co-actor does on it: 211's
# sweets — the run's puke at the women's wc (0x10030dc2) carries the
# wcright record and the behavior `puke` on Olga, whose handler (0x100318ce)
# queues her wc `mad` and makes her fight step 0x1003183a (fcn.1000eb19's
# approach, the generic `fight`) her next; the fight's olga_fight sets his
# step's latch +0xd (0x100301fb), on which 0x10030d0f plays SHOUT 1. The
# puke's job posts `puke` as it ends (state 2, fcn.1004000a at 0x10002708),
# Olga's mad starts on the offer and her fight follows it at the same
# hotspot, so his SHOUT comes mad + fight after the puke's end: the port's
# hit after the toilet. (item: the wc object, its action, the co-actor, her
# action at it)
TRICKED_RUSH = {211: {'Sweets': ('topleft_wcright', 'puke', 'olga', 'mad')}}
# a station's tricked variant where the lap's step has none and other steps of
# the script play it, their events in order: 201's damaged buffet in the
# tutorial (0x10029c4a: the flirt that sends Olga's buffet_crash, his crash;
# 0x10029a6c after her fight: the SHOUT that takes the actor for its level,
# the repair; the knife is spent by then)
TRICKED_STEP = {201: {'Buffet': (0x10029c4a, 0x10029a6c)}}
# the tricked flows of stations code_stays_tricked does not reach, read for
# their scene alone (scene_steps): the steps in order and the objects shown
# and hidden for the trick — 205's egg on the table (0x100254d5: Ef51a before
# the `play`; 0x1002577a: SHOUT 0, Eebbf), 208's rake (0x1001d828: crash,
# SHOUT, the wrapper), 211's cabin phone (0x1002fcbe: crash, SHOUT 1, the
# wrapper), 213's bull controls (0x10037de6: Ef51a, the `use`; 0x10037d3b:
# the hurt icon, Eebbf — no SHOUT)
SCENE_STEPS = {202: {'BeerMat': ((0x1002299f,), None, None)},
               205: {'TabbleTennis': ((0x100254d5, 0x1002577a), {'beachright_pingpong_egg_guarded'},
                                      {'beachright_pingpong', 'beachright_pingpong_guarded'})},
               208: {'Rake': ((0x1001d828,), set(), set())},
               209: {'FireFakir': ((0x10020e3e,), {'fire_fakir_groove_fuel'}, {'fire_fakir_groove'})},
               211: {'CabinPhone': ((0x1002fcbe,), set(), set())},
               212: {'BoatCoinSlot': ((0x10035388,), None, None),
                     # the second ruby fills the throne (combine.xml: throne_half
                     # or throne_half_2 with the other ruby -> throne_full), and
                     # the step checks half, half_2 and full (0x10036c42-
                     # 0x10036c9d, half_right's result dropped): full plays the
                     # hands' `hit` (0x10036d42), half or half_2 `miss`, none
                     # `sit`; no poll, so absent objects stay absent (unknown 0)
                     'AztecThrone2': ((0x10036bb2,), {'topright_throne_full'},
                                      {'topright_throne_empty', 'topright_throne_half',
                                       'topright_throne_half_2', 'topright_throne_half_right'}, 0)},
               213: {'MechanicalBullControls': ((0x10037de6, 0x10037d3b), None, None),
                     # (the beehive's combination: tricked_presence pairs no inventory)
                     'Pinata': ((0x1003809b,), {'bottomleft_pinata_manip'}, {'bottomleft_pinata'})}}


# the SCENE_STEPS flows that are the item's whole tricked visit — the
# station's own tricked step, its stand, SHOUT, repair and records — read as
# code_stays_tricked reads a lap's (209's fire fakir: the fuelled groove's
# `burn`, SHOUT 0, the repair; 213's pinata: the beehive's `use`, SHOUT 1)
TRICKED_SCENE = {209: ('FireFakir',), 213: ('Pinata',)}
# the scene of a linked variant whose combination is not the union of the
# two items' (the linked loop of code_stays_tricked): 212's two rubies fill
# the throne — throne_full, the halves gone (combine.xml) — where each ruby's
# own combinations show a half and the full throne both
LINKED_PRESENT = {212: {'AztecThrone': ({'topright_throne_full'},
                                        {'topright_throne_empty', 'topright_throne_half',
                                         'topright_throne_half_2', 'topright_throne_half_right'})}}


def _scene_step_events(n, item):
    """the events of an item's SCENE_STEPS steps, run with its trick in the
    scene (tricked_presence, else the table's)"""
    steps, shown, hidden = SCENE_STEPS[n][item][:3]
    unknown = SCENE_STEPS[n][item][3] if len(SCENE_STEPS[n][item]) > 3 else 1
    if shown is None:
        shown, hidden = tricked_presence(n).get(item, (set(), set()))
    lv = Level(n)
    lv.present = (set(lv.present) - set(hidden)) | set(shown)
    ev = []
    for st in steps:
        evs, _nx = run_step(lv, st, dict(LAP_BYTES.get(n) or {}), unknown=unknown, latch=1)
        ev += ([('STEP',)] if ev else []) + evs
    return ev


def scene_steps(n):
    """{mobile item: PCScene} of SCENE_STEPS (_scene_span over the steps'
    events with the trick in the scene: tricked_presence, else the table's)"""
    d = Data(n)
    return {item: _scene_secs(_scene_span(d, _scene_step_events(n, item)))
            for item in SCENE_STEPS.get(n, {})}


def _repair_walk(n, d, ev):
    """(ticks, (x, px) | None): the walk a tricked flow makes to its repair —
    from the station its last GoTo before the repair's took him to (the
    object of the first action after that GoTo) to the repaired object's
    `neighbor` hotspot (walk_ticks), and where it leaves him (the hotspot's x
    and height against the room's floor); (0, None) when the repair is where
    he stands or no GoTo placed him before it (211's sign after the women's
    wc: 34 ticks; 203's generator after the stage)"""
    pos, go, target = None, False, None
    for e in ev or []:
        if e[0] == 'GO':
            go = True
            continue
        if e[0] == 'DO' and e[1]:
            names = [x for x in e[1] if not str(x).startswith('$')]
            if len(names) >= 2 and names[1] == 'repair':
                target = names[0]
                break
            if go and names and names[0] != 'neighbor':
                pos, go = names[0], False
    if target is None or pos is None:
        return 0, None
    g = Geometry(n)
    a, b = d.real.get(pos, pos), d.real.get(target, target)
    p, q = g.point(a), g.point(b)
    if a == b or p is None or q is None:
        return 0, None
    t, _pos = walk_span(g, (g.room_of(a), p[0], p[1]), b, data=d)
    if not t:
        return 0, None
    return t, (q[0], q[1] - g.floor(g.room_of(b)))


def _waits_on(d, e, who='neighbor'):
    """another actor's job (ODO) whose record posts `who` a behaviour — the
    step after it waits for it (204's gong: the Elvis's `use`)"""
    if e[0] != 'ODO':
        return False
    names = [x for x in e[1] if not str(x).startswith('$')]
    r = d._record(names[0], names[1], who) if len(names) >= 2 else None
    return bool(r is not None and r[1].get('behavior') and r[1].get('behavioractor') == who)


def _waited(d, ev, who='neighbor'):
    """the indices of the other actor's elements the flow's actor waits
    through: those of a step (up to a STEP mark or a GO) up to a job of
    that actor's he waits for (_waits_on) — 204's Elvis's camera before
    his `use`, a tick of the wait"""
    out, run = set(), []
    for i, e in enumerate(ev or []):
        if e[0] in ('STEP', 'GO'):
            run = []
            continue
        if e[0].startswith('O'):
            run.append(i)
            if _waits_on(d, e, who):
                out.update(run)
                run = []
    return out


def _is_instant(e):
    """an element the sequence finishes on its first update: a tick
    (step_ticks)"""
    return e[0] in TICK_ELEMENTS or (e[0] == 'E2f40' and len(e) > 3 and e[3] == 'instant')


def _flow(d, ev, own=None, walked=True, actor='neighbor'):
    """a flow's events on the lap's clock (step_ticks, station_ticks): [(tick,
    kind, payload)] — 'part' (object, action, ticks) at the tick it starts,
    'shout' its level at its tick, 'step' at each step's start after the
    first. Each step of the flow takes its own start — 2 where it walks (its
    GoTo, walk_span; the flow's first step only where the visit walked to
    it, `walked`), else 1 —, an instant element a tick, a part its ticks. A
    step starts at a ('STEP',) mark or at a GO after the step's first element
    (fcn.1000e3e0 runs before the step builds its sequence). `own(object,
    action)` keeps a station's own parts where the step is shared with
    another mobile station (212's cliff: the ledge's `enter` is the
    pre-ledge's); `actor` whose records time the parts (213's Olga out of
    the tricked boat)"""
    out = []
    t = 0
    first, started, go, elems = True, False, False, 0
    ctx = {'actor': actor}
    waited = _waited(d, ev, actor)
    for ie, e in enumerate(ev or []):
        if e[0] == 'STEP' or (e[0] == 'GO' and elems):
            if elems:
                first = False
            started, go, elems = False, False, 0
            if e[0] == 'STEP':
                continue
        if e[0] == 'GO':
            go = True
            # the step's GoTo leaves him at the object's `<actor>` hotspot
            # (fcn.1000e3e0): where a GoTo element of the flow walks from
            g = d.geom()
            obj = d.real.get(e[1], e[1]) if len(e) > 1 and e[1] else None
            q = g.point(obj, actor) if obj else None
            ctx['pos'] = (g.room_of(obj), q[0], q[1]) if q is not None else None
            continue
        instant = _is_instant(e) or (ie in waited and e[0][1:] in TICK_ELEMENTS)
        parts = [] if (instant or e[0] == 'SHOUT') else _station_parts(d, [e], ctx)
        if not (instant or e[0] == 'SHOUT' or parts):
            continue
        if not started:
            if not first:
                out.append((t, 'step', go))
            t += 2 if (go and (walked or not first)) else 1
            started = True
        elems += 1
        if e[0] == 'SHOUT':
            imms = e[2] if len(e) > 2 else []
            # the level is the SHOUT's last parameter (fcn.1000f977's
            # arg_14h, its first push: a constant or the zeroed ebx — 201's
            # buffet pushes ebx, 0); a register the walker does not follow
            # leaves it unknown (None)
            out.append((t, 'shout', imms[0] if imms else None))
            continue
        if instant:
            out.append((t, 'instant', e[0]))
            t += 1
            continue
        for o, a, jt in parts:
            if a in ('-', '?') and jt is None:
                continue
            if own is not None and a not in ('-', '?') and not own(o, a):
                continue
            out.append((t, 'part', (o, a, jt)))
            if jt is None:
                out.append((t, 'unknown', (o, a)))   # the clock stops being known
                continue
            t += jt
    return out + [(t, 'end', None)]


def _step_parts_split(d, ev, own=None, walked=True):
    """a tricked flow cut at its SHOUT (fcn.1000f977 / fcn.1000fede): (the
    ticks before it — the tricked stand, from the arrival —, the SHOUT's
    level, -1 when the flow has no SHOUT, None when its level is no
    constant the walker follows, the repair's ticks after it — from the
    SHOUT's end to the repair's and the instant elements right after it
    (what the step plays after that is _shout_tail's) — or None, the tick of
    the stand its first named trick record pays at — its action's start
    plus the record's `time` — or None); a part of unknown length leaves
    the stand None. On the lap's clock (_flow) since 2026-09-27: until then
    each part took a step's tick of its own and the instant elements and
    the steps' starts none (station_ticks run on each event alone)"""
    fl = _flow(d, ev, own, walked)
    level, shout_t, repair, credit = None, None, None, None
    unknown = False                       # before the SHOUT: no stand
    after_repair = False
    for t, kind, x in fl:
        if shout_t is None:
            if kind == 'unknown':
                unknown = True
            elif kind == 'shout':
                shout_t, level = t, x
            elif kind == 'part' and credit is None and not unknown \
                    and x[1] not in ('-', '?', 'bar') and x[2] is not None:
                recs = d.tricks(x[0], x[1])
                if recs:
                    credit = t + recs[0][1]
            continue
        if kind == 'part' and x[1] == 'repair':
            repair = t + (x[2] or 0) - shout_t
            after_repair = True
        elif kind == 'instant' and after_repair:
            repair = t + 1 - shout_t
        elif kind != 'unknown':
            after_repair = False
    if shout_t is None:
        return (None if unknown else fl[-1][0]), -1, None, credit
    return (None if unknown else shout_t), level, repair, credit


# the elements that raise and drop the level's scene flag +0x6e, which the
# completion check fcn.10041086 reads (done == reachable counts only while it
# is clear): the camera callback's update 0x1000d70b runs fcn.1000d31a for a
# start (its flags' bit 0) and fcn.1000d559 for an end, and both store the
# flag first (fcn.10040137(1) at 0x1000d338, fcn.10040137(0) at 0x1000d57a)
# whatever the camera does after — fcn.1000f51a (Ef51a) builds a start,
# fcn.1000ebbf (Eebbf) an end, and the wrapper fcn.1000f5c9 (SET) puts a start
# before the list built so far and an end after it
SCENE_ON, SCENE_OFF = ('Ef51a',), ('SET', 'Eebbf')
# (an element appended to another actor's sequence — 'O' before its kind —
# stores the same flag: 204's gong step raises it in the Elvis's, before his
# `use`, 0x10031f72)


def _scene_span(d, ev, own=None, walked=True):
    """the scene of a tricked flow — the level's flag +0x6e (SCENE_ON /
    SCENE_OFF) on the flow's clock (_flow): a step whose list the wrapper
    closes (a SET in it) raises it at its first element, Ef51a raises it, the
    first SET or Eebbf after drops it. (the tick it rises at, where it drops:
    'shout' right after the flow's SHOUT — the read flows' own: fcn.1000f5c9
    or fcn.1000ebbf follows fcn.1000f977 —, 'use' where no SHOUT comes first
    and no part after (the stand's end: 213's bull controls, the `use` then
    the hurt step's Eebbf), else the tick it drops at, None past another
    part or the flow's end); None: no scene"""
    fl = _flow(d, ev, own, walked)
    segs, cur = [], []
    for row in fl:
        if row[1] == 'step':               # a step's start after the first
            segs.append(cur)
            cur = []
        cur.append(row)
    segs.append(cur)
    rise, shout, part_after = None, None, False
    for seg in segs:
        if rise is None and any(k == 'instant' and x.lstrip('O') == 'SET' for _t, k, x in seg):
            rise = seg[0][0]               # the wrapper's start: the list's first element
        for t, kind, x in seg:
            if kind == 'shout':
                shout, part_after = t, False
            elif kind == 'part' and shout is not None:
                part_after = True
            elif kind == 'instant' and x.lstrip('O') in SCENE_ON and rise is None:
                rise = t
            elif kind == 'instant' and x.lstrip('O') in SCENE_OFF and rise is not None:
                if shout is None:
                    # before any SHOUT: its tick, or the stand's end where no
                    # part follows
                    later = any(k == 'part' and tt >= t for tt, k, _x in fl)
                    return rise, (t if later else 'use')
                return rise, (None if part_after else 'shout')
    return (rise, None) if rise is not None else None


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
    for name, (shown, hidden) in out.items():
        # the aux update's doing on the tricked scene (AUX_UPDATE)
        for fn in AUX_UPDATE.get(n, ()):
            lv = Level(n)
            lv.present = (lv.present - hidden) | shown
            before = set(lv.present)
            run_step(lv, fn, {})
            shown |= lv.present - before
            hidden |= before - lv.present
    return out


def lap_state(n):
    """[(the scene, the step bytes)] as the untricked lap's walk enters each
    of its steps (lap_steps' indices): a station's tricked run starts from
    the scene the lap has there — 209's shoe mat holds his shoes when he
    comes out of the curtain, which the level's opening scene does not"""
    st = LAP_START.get(n) or level_start(n)
    lv = Level(n)
    for hid, shown in LAP_PRESENT.get(n, ()):
        lv.present.discard(hid); lv.present.add(shown)
    snaps = []
    walk(lv, st, bytes0=LAP_BYTES.get(n), snaps=snaps)
    return snaps


def _row_level(n, snaps, row):
    """(a Level with the lap's scene at the walk's step `row`, its bytes)"""
    pres, by = snaps[row]
    lv = Level(n)
    lv.present = set(pres)
    return lv, by


def _tricked_run(n, lv, item, cur, trick, bytes0=None, latch=0):
    """the step `cur` run with the item's trick in the scene (tricked_presence);
    None when the trick changes none of its DoActions or hideout elements.
    `latch`: the step polls its event latch on the lap (a POLL row: 213's
    picnic waits for Olga's `boat`), taken as set as the lap's walk does"""
    shown, hidden = trick.get(item, (set(), set()))
    if not shown:
        return None
    by = bytes0 if bytes0 is not None else (LAP_BYTES.get(n) or {})
    lv2 = Level(n)
    lv2.present = (set(lv.present) - hidden) | shown
    ev2, _nx = run_step(lv2, cur, dict(by), latch=latch)
    lv1 = Level(n)
    lv1.present = set(lv.present)
    ev1, _nx = run_step(lv1, cur, dict(by), latch=latch)
    dos = lambda ev: [(e[0],) + tuple(e[1]) for e in ev
                      if e[0] in ('DO', 'ODO') or (latch and e[0] in ('E6bd4', 'E6c2e'))]
    if dos(ev2) == dos(ev1):
        return None
    return ev2


def trick_rage(n):
    """{record: rage in the port's units} — tricks.xml's rage / 1000"""
    folder = canon.pc_level(n)['folder']
    tr = canon.read('%s/nfh2/x/%s/tricks.xml' % (canon.ROOT, folder))
    return {m.group(1): int(m.group(2)) // 1000
            for m in re.finditer(r'<trick name="([^"]+)"[^>]*rage="(\d+)"', tr)}


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


def _secs(t):
    return round(t / 12.0, 2) if t is not None else None


def _scene_secs(span):
    """a _scene_span for the overlay (PCScene): [the second it rises at, the
    second it drops at or 'shout'] into the flow, [] for none"""
    if span is None:
        return []
    rise, drop = span
    return [_secs(rise), _secs(drop) if isinstance(drop, int) else drop]


def _shout_tail(d, ev, own=None, walked=True):
    """the ticks the SHOUT's step plays after its repair and the instant
    elements right after it (_step_parts_split's `repair`) — or after the
    SHOUT where it has no repair — to the end of its sequence: the SET and
    SWITCH of a SHOUT with no repair (203's melons, 204's hot dog), the
    take after it (210's turban shop: its take3, 15 ticks with the SET,
    SWITCH and the hide after) — before the step's next one takes over (a
    ('STEP',) mark or a GO); None where the flow has no SHOUT or a part of
    unknown length follows it. (205's sand lion's kid laughs on his own
    queue, 0x10024426-0x1002443e, as the neighbour shouts and repairs: no
    tail since 2026-10-03)"""
    fl = _flow(d, ev, own, walked)
    k = next((i for i, (_t, kind, _x) in enumerate(fl) if kind == 'shout'), None)
    if k is None:
        return None
    # (a repair in a later step — its walk's — has the SHOUT's step's tail
    # in `repair` already: the tail is the repair's step's)
    start, end = fl[k][0], None
    after_repair = False
    for t, kind, x in fl[k + 1:]:
        if kind == 'unknown':
            return None
        if kind == 'part' and x[1] == 'repair':
            start, end = t + (x[2] or 0), None
            after_repair = True
            continue
        if kind == 'instant' and after_repair:
            start = t + 1
            continue
        after_repair = False
        if kind in ('step', 'end') and end is None:
            end = t
    return max(0, (end if end is not None else start) - start)


def _step_records(d, ev, own=None, walked=True):
    """the flow's named trick records before its SHOUT, in order: [(name,
    tick)], its action's start on the lap's clock (_flow) plus the record's
    `time` (fcn.1000140b credits each at its own); up to a part of unknown
    length"""
    out = []
    for t, kind, x in _flow(d, ev, own, walked):
        if kind == 'shout':
            break
        if kind == 'part' and x[1] not in ('-', '?', 'bar'):
            out += [(nm, t + tm) for nm, tm in d.tricks(x[0], x[1])]
        if kind == 'unknown':
            break
    return out


def _step_jingles(d, ev, own=None, walked=True):
    """the flow's jingle_joke ticks before its SHOUT, in order: each
    jingle="true" record's action start on the lap's clock (_flow) plus its
    `time` (fcn.1000140b plays it on that tick, named record or not,
    0x10001528-0x1000153f); up to a part of unknown length"""
    out = []
    for t, kind, x in _flow(d, ev, own, walked):
        if kind == 'shout':
            break
        if kind == 'part' and x[1] not in ('-', '?', 'bar'):
            out += [t + tm for tm in d.jingles(x[0], x[1])]
        if kind == 'unknown':
            break
    return sorted(out)


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
    for item, (by, more, less) in TRICKED_BY.get(n, {}).items():
        if by in trick:
            trick[item] = (set(trick[by][0]) | more, set(trick[by][1]) | less)

    def entry(ev2, own=None, walked=True):
        stand, level, repair, credit = _step_parts_split(d, ev2, own, walked)
        return {'tricked': round(stand / 12.0, 2) if stand is not None else None, 'shout': level,
                'repair': round(repair / 12.0, 2) if repair is not None else None,
                'credit': round(credit / 12.0, 2) if credit is not None else None,
                'jingles': [_secs(t) for t in _step_jingles(d, ev2, own, walked)],
                'tail': _secs(_shout_tail(d, ev2, own, walked)),
                'scene': _scene_secs(_scene_span(d, ev2, own, walked))}
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
    snaps = lap_state(n)
    # (the visits read apart: TRICKED_ROWS, TRICKED_ARM, TRICKED_ARM_LINKED)
    apart = set(TRICKED_ROWS.get(n, {})) | set(TRICKED_ARM.get(n, {})) | set(TRICKED_ARM_LINKED.get(n, {}))
    for item, (many, visits) in pairs.items():
        for v in visits:
            if v is None or item in out or item in apart:
                continue
            rows_v = sorted(set(i for i, _j, _p in v))
            prefix = []
            for i in rows_v:
                lvi, byi = _row_level(n, snaps, lap[i][0])
                # a row the lap's walk passes as a poll: its latch set
                lat = int(any(a == 'POLL' for _o, a, _t in lap[i][4]))
                ev2 = _tricked_run(n, lvi, item, lap[i][1], trick, byi, latch=lat)
                if ev2 is None:
                    # a row of the visit the trick leaves as it is leads its
                    # flow (212's bench: the manipulated bench entered and
                    # slept on — the bar step — before the leave step's crash)
                    if item in trick:
                        lvp = Level(n)
                        lvp.present = (set(lvi.present) - trick[item][1]) | trick[item][0]
                        prefix += run_step(lvp, lap[i][1], dict(byi), latch=lat)[0] + [('STEP',)]
                    continue
                if prefix:
                    ev2 = prefix + ev2
                own_i = own_of(item, i) if not prefix else \
                    (lambda o, a, ks=rows_v: all(own_of(item, k)(o, a) for k in ks))
                e = entry(ev2, own_i, LAP_WALKS.get(n, {}).get(lap[rows_v[0] if prefix else i][0], True)) \
                    if ev2 is not None else None
                if e is not None and e['credit'] is None and item in CREDIT_BY.get(n, {}):
                    (po, pa), who, (ho, ha) = CREDIT_BY[n][item]
                    fl = _flow(d, ev2, own_i, LAP_WALKS.get(n, {}).get(lap[rows_v[0] if prefix else i][0], True))
                    end = next((t + x[2] for t, kind, x in fl
                                if kind == 'part' and x[0] == po and x[1] == pa and x[2] is not None), None)
                    recs = d.tricks(ho, ha, who)
                    if end is not None and recs:
                        e['credit'] = _secs(end + 2 + recs[0][1])
                        # (and the co-actor's action's jingles on its clock)
                        e['jingles'] = sorted(e['jingles'] + [
                            _secs(end + 2 + jt) for jt in d.jingles(ho, ha, who)])
                if e is not None:
                    cont = TRICKED_CONT.get(n, {}).get(item)
                    if cont is not None and e['shout'] == -1:
                        # the reaction's steps: the scene the tricked step
                        # leaves, each step's events in turn (polls passed)
                        kind, actor, steps = cont[:3]
                        s1, h1 = trick[item]
                        lvc = Level(n)
                        lvc.present = (set(lvi.present) - h1) | s1
                        for other in CONT_SCENE.get(n, {}).get(item, ()):
                            if other in trick:
                                lvc.present = (lvc.present - trick[other][1]) | trick[other][0]
                        run_step(lvc, lap[i][1], dict(byi), latch=lat)
                        evc = []
                        for stp in steps:
                            evc += [('STEP',)] + run_step(lvc, stp, dict(byi), unknown=1, streq=1)[0]
                        cstand, clevel, crepair, _c = _step_parts_split(d, evc)
                        wk, dep = _repair_walk(n, d, evc) if crepair is not None else (0, None)
                        e.update({'shout': clevel,
                                  'tail': _secs(_shout_tail(d, evc)),
                                  'repair': round((crepair + wk) / 12.0, 2) if crepair is not None else None,
                                  'cont': round(cstand / 12.0, 2) if cstand is not None else None})
                        # the scene across the tricked step and its reaction's
                        e['scene'] = _scene_secs(_scene_span(
                            d, ev2 + [('STEP',)] + evc, own_i,
                            LAP_WALKS.get(n, {}).get(lap[rows_v[0] if prefix else i][0], True)))
                        if cont[3:] == ('stand',) and cstand is not None and e['tricked'] is not None:
                            e['tricked'] = round(e['tricked'] + cstand / 12.0, 2)
                        if dep is not None:
                            # the repair's walk leaves him at the repaired
                            # object (211's sign)
                            e['fix_depart'] = dep
                        if kind == 'fight':
                            ft = d.action_ticks('neighbor', 'fight', actor=actor)
                            e['hit'] = {actor: round(ft / 12.0, 2) if ft is not None else None}
                            spec = FIGHT_BEFORE.get(n, {}).get(item)
                            if spec is not None:
                                # her own steps and her walk before the fight
                                lvh = Level(n)
                                lvh.present = (set(lvi.present) - h1) | s1
                                ha = _hit_after(n, d, lvh, byi, ev2, own_of(item, i),
                                                LAP_WALKS.get(n, {}).get(lap[i][0], True), spec)
                                e['hit_after'] = {spec[1]: _secs(ha)}
                            else:
                                # her step reads his part's behaviour on the
                                # tick after its post and pushes her GoTo
                                # without a first run: her first move two
                                # ticks after the post, where the port starts
                                # her run at his stand's end
                                fl = _flow(d, ev2, own_i, LAP_WALKS.get(n, {}).get(
                                    lap[rows_v[0] if prefix else i][0], True))
                                post = next((t + x[2] for t, kind, x in fl if kind == 'part'
                                             and x[2] is not None
                                             and (d._record(x[0], x[1]) or (0, {}))[1].get('behavioractor') == actor),
                                            None)
                                if post is None and item in POST_BY.get(n, {}) \
                                        and item in CREDIT_BY.get(n, {}):
                                    # posted by the co-actor's own job his part
                                    # starts (POST_BY): her sequence from the
                                    # tick after the offer of his part's end
                                    (po, pa), who, _h = CREDIT_BY[n][item]
                                    endp = next((t + x[2] for t, kind, x in fl
                                                 if kind == 'part' and x[0] == po and x[1] == pa
                                                 and x[2] is not None), None)
                                    lvf = Level(n)
                                    lvf.present = (set(lvi.present) - h1) | s1
                                    evf, _nf = run_step(lvf, POST_BY[n][item], dict(byi), latch=1)
                                    flf = _flow(d, evf, walked=False, actor=who)
                                    first = next((t for t, kind, _x in flf if kind == 'part'), None)
                                    pend = next((t + x[2] for t, kind, x in flf if kind == 'part'
                                                 and x[2] is not None
                                                 and (d._record(x[0], x[1], who) or (0, {}))[1].get('behavioractor') == actor),
                                                None)
                                    if endp is not None and first is not None and pend is not None:
                                        post = endp + 2 + (pend - first)
                                if post is not None and post + 2 - fl[-1][0] > 0:
                                    e['hit_after'] = {actor: _secs(post + 2 - fl[-1][0])}
                    # a tricked step with no SHOUT whose flow goes on to the
                    # lap's next step plays no reaction at all
                    lvj = Level(n); lvj.present = (set(lvi.present) - trick[item][1]) | trick[item][0]
                    _e, nx2 = run_step(lvj, lap[i][1], dict(byi), latch=lat)
                    lvk = Level(n); lvk.present = set(lvi.present)
                    _e, nx1 = run_step(lvk, lap[i][1], dict(byi), latch=lat)
                    e['rejoins'] = nx2 == nx1
                    if e['shout'] is not None and e['shout'] >= 0 and e['repair'] is None \
                            and nx2 is not None and nx2 != nx1:
                        # the repair in the step the tricked flow hands over
                        # to off the lap (203's generator after the stage's
                        # crash, 0x100343a5: its walk, `repair` and switch back)
                        evr, _nr = run_step(lvj, nx2, dict(byi))
                        rp = [t for _o, a, t in station_ticks(d, evr, {}) if a == 'repair']
                        if rp and None not in rp:
                            # (and the walk to it: 203's stage to the generator)
                            wk, dep = _repair_walk(n, d, ev2 + evr)
                            e['repair'] = round((sum(rp) + wk) / 12.0, 2)
                            e['tail'] = _secs(_shout_tail(d, ev2 + [('STEP',)] + evr))
                            if dep is not None:
                                e['fix_depart'] = dep
                    out[item] = e
                    where[item] = (i, ev2)
                    break
    if TRICKED_ROWS.get(n):
        rows, _loop = lap_steps(n)
        for item, (row, owns) in TRICKED_ROWS[n].items():
            if item in out or item not in trick:
                continue
            cur = rows[row][1]
            lvi, byi = _row_level(n, snaps, row)
            own = lambda o, a, owns=owns: any(x in o for x in owns)
            ev2 = _tricked_run(n, lvi, item, cur, trick, byi)
            if ev2 is None:
                continue
            e = entry(ev2, own, LAP_WALKS.get(n, {}).get(rows[row][0], True))
            s1, h1 = trick[item]
            lvc = Level(n); lvc.present = (set(lvi.present) - h1) | s1
            _e, nx2 = run_step(lvc, cur, dict(byi))
            lvk = Level(n); lvk.present = set(lvi.present)
            _e, nx1 = run_step(lvk, cur, dict(byi))
            if e['shout'] == -1 and nx2 != nx1 and nx2 is not None:
                # the tricked flow's own step off the lap: its parts up to
                # its SHOUT go on the stand, its records after the item's
                evc, _nx = run_step(lvc, nx2, dict(byi), unknown=1, streq=1)
                cstand, clevel, crepair, ccredit = _step_parts_split(d, evc)
                base = round(e['tricked'] * 12) if e['tricked'] is not None else None
                # ... after its GoTo's walk from where the row's step left
                # him (206's dynamite: 0x1002c550 walks him from the bag to
                # the reling, 12 ticks, before the lookaround and the explode)
                gt = Geometry(n)
                pos = _end_of(d, gt, _lap_target(ev2), station_ticks(d, ev2, {}))
                tgt = _lap_target(evc)
                wk = walk_span(gt, pos, d.real.get(tgt, tgt), data=d)[0] \
                    if (pos is not None and tgt) else 0
                if base is not None:
                    base += wk or 0
                if cstand is not None and base is not None:
                    e['tricked'] = round((base + cstand) / 12.0, 2)
                    if e['credit'] is None and ccredit is not None:
                        e['credit'] = round((base + ccredit) / 12.0, 2)
                    e['jingles'] = sorted(e['jingles'] + [
                        _secs(base + t) for t in _step_jingles(d, evc)])
                e['shout'] = clevel
                e['repair'] = round(crepair / 12.0, 2) if crepair is not None else None
                e['tail'] = _secs(_shout_tail(d, evc))
                e['cont'] = 0.0
                # the scene across the row's step and the flow's own
                e['scene'] = _scene_secs(_scene_span(d, ev2 + [('STEP',)] + evc, own,
                                                     LAP_WALKS.get(n, {}).get(rows[row][0], True)))
            e['rejoins'] = nx2 == nx1
            out[item] = e
    for item, (row, k_shot, actor, arm, fire) in TRICKED_ARM.get(n, {}).items():
        if item in out or item not in trick:
            continue
        rows, _loop = lap_steps(n)
        lvi, byi = _row_level(n, snaps, row)
        lnk = mobile_linked(n).get(item)

        def flow(items):
            # the armed flow from the arming step to the shot, then the step
            # that waits for the co-actor's hit (its latch taken as set) and
            # the one after it (the repair)
            lv2 = Level(n)
            lv2.present = set(lvi.present)
            for x in items:
                lv2.present = (lv2.present - trick[x][1]) | trick[x][0]
            by = dict(byi)
            cur, shot = rows[row][1], None
            for _k in range(k_shot + 1):
                if cur is None:
                    return None
                shot, cur = run_step(lv2, cur, by)
            if cur is None:
                return None
            ev_s, nx_s = run_step(lv2, cur, by, unknown=1)
            ev_r = run_step(lv2, nx_s, by)[0] if nx_s else []
            return shot, shot + [('STEP',)] + ev_s + [('STEP',)] + ev_r

        f1 = flow((item,))
        if f1 is None:
            continue
        shot1, all1 = f1
        stand, level, repair, credit = _step_parts_split(d, all1)
        ft = d.action_ticks('neighbor', 'fight', actor=actor)
        e = {'tricked': round(stand / 12.0, 2) if stand is not None else None, 'shout': level,
             'repair': round(repair / 12.0, 2) if repair is not None else None,
             'credit': round(credit / 12.0, 2) if credit is not None else None,
             'jingles': [_secs(t) for t in _step_jingles(d, all1)],
             'hit': {actor: round(ft / 12.0, 2) if ft is not None else None},
             'tail': _secs(_shout_tail(d, all1)),
             'scene': _scene_secs(_scene_span(d, all1)),
             'arm': [arm, fire], 'rejoins': True}
        f2 = flow((item, lnk)) if lnk in trick else None
        if f2 is not None:
            shot2, all2 = f2
            stand2, level2, repair2, _c = _step_parts_split(d, all2)
            mine = set(nm for nm, _t in _step_records(d, shot1))
            recs = _step_records(d, all2)
            credit2 = next((t for nm, t in recs if nm in mine), None)
            others = [(nm, t) for nm, t in recs if nm not in mine]
            e.update({'linked': round(stand2 / 12.0, 2) if stand2 is not None else None,
                      'linked_shout': level2,
                      'linked_repair': round(repair2 / 12.0, 2) if repair2 is not None else None,
                      'linked_tail': _secs(_shout_tail(d, all2)),
                      'linked_scene': _scene_secs(_scene_span(d, all2)),
                      'linked_credit': round(credit2 / 12.0, 2) if credit2 is not None else None,
                      'linked_jingles': [_secs(t) for t in _step_jingles(d, all2)],
                      'linked_pays': round(others[0][1] / 12.0, 2) if others else None})
            if len(others) > 1:
                # the third record of the linked shot (206's rubberrabbit: the
                # mobile's ExtraCoin206)
                e.update({'linked_extra': others[1][0], 'linked_extra_at': round(others[1][1] / 12.0, 2)})
        out[item] = e
    for item, (fire_v, drop_v, trow) in TRICKED_ARM_LINKED.get(n, {}).items():
        if item in out or item not in trick:
            continue
        # the linked item's own shot where the other is not armed: the take
        # step's tricked branch hands over to the shot at the other object
        # (0x1002da29: the GoTo there, the rubber bear, SHOUT) and on to the
        # put step. The mobile plays that shot at the pad's shoot through the
        # pad's DependsOn (the harpoon's UseAtOtherPlace): the walks there and
        # back are the port's own between the stations, the stand the shot
        rows, _loop = lap_steps(n)
        lvi, byi = _row_level(n, snaps, trow)
        lv2 = Level(n)
        lv2.present = (set(lvi.present) - trick[item][1]) | trick[item][0]
        by = dict(byi)
        _ev1, nx = run_step(lv2, rows[trow][1], by)
        ev2 = run_step(lv2, nx, by)[0] if nx else []
        stand, level, repair, credit = _step_parts_split(d, ev2)
        out[item] = {'tricked': round(stand / 12.0, 2) if stand is not None else None, 'shout': level,
                     'repair': round(repair / 12.0, 2) if repair is not None else None,
                     'credit': round(credit / 12.0, 2) if credit is not None else None,
                     'jingles': [_secs(t) for t in _step_jingles(d, ev2)],
                     'tail': _secs(_shout_tail(d, ev2)),
                     'scene': _scene_secs(_scene_span(d, ev2)),
                     'arm': [fire_v, drop_v], 'rejoins': True}
    for item, (obj, act, actor, her) in TRICKED_RUSH.get(n, {}).items():
        if item not in out:
            continue
        puke = d.action_ticks(obj, act)
        mad = d.action_ticks(obj, her, actor=actor)
        ft = d.action_ticks('neighbor', 'fight', actor=actor)
        recs = d.tricks(obj, act)
        if puke is not None and recs:
            out[item]['toilet_pays_at'] = round(recs[0][1] / 12.0, 2)
        if None not in (mad, ft):
            out[item]['hit'] = {actor: round((mad + ft) / 12.0, 2)}
    for item, (stp, tricks) in TRICKED_VIA.get(n, {}).items():
        lv2 = Level(n)
        lv2.present = set(lv.present)
        for it in tricks:
            if it in trick:
                lv2.present = (lv2.present - trick[it][1]) | trick[it][0]
        e = entry(run_step(lv2, stp, dict(LAP_BYTES.get(n) or {}), unknown=1)[0])
        if e is not None and item not in out:
            out[item] = e
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
    for item in TRICKED_SCENE.get(n, ()):
        e = entry(_scene_step_events(n, item))
        if e is not None and item not in out:
            e['rejoins'] = True
            out[item] = e
    for item, step in LINKED_STEP.get(n, {}).items():
        lv2 = Level(n)
        lv2.present = set(lv.present)
        evl = run_step(lv2, step, dict(LAP_BYTES.get(n) or {}))[0]
        stand, _level, _repair, credit = _step_parts_split(d, evl)
        if stand is not None and item in out:
            out[item]['linked'] = round(stand / 12.0, 2)
            out[item]['linked_credit'] = round(credit / 12.0, 2) if credit is not None else None
            out[item]['linked_jingles'] = [_secs(t) for t in _step_jingles(d, evl)]
            out[item]['linked_scene'] = _scene_secs(_scene_span(d, evl))
    # the linked trick in the same step: the station's step run with both
    # tricks in the scene
    dos = lambda ev: [tuple(e[1]) for e in ev if e[0] in ('DO', 'ODO')]
    for item, lnk in sorted(mobile_linked(n).items()):
        if item not in where or 'linked' in out[item] or lnk not in trick:
            continue
        i, ev1 = where[item]
        (s1, h1), (s2, h2) = trick[item], trick[lnk]
        lvi, byi = _row_level(n, snaps, lap[i][0])
        lv2 = Level(n)
        lv2.present = (set(lvi.present) - h1 - h2) | s1 | s2
        if item in LINKED_PRESENT.get(n, {}):
            shown, hidden = LINKED_PRESENT[n][item]
            lv2.present = (set(lvi.present) - set(hidden)) | set(shown)
        ev2, _nx = run_step(lv2, lap[i][1], dict(byi))
        if dos(ev2) == dos(ev1):
            continue
        own = own_of(item, i)
        wk_i = LAP_WALKS.get(n, {}).get(lap[i][0], True)
        stand, level, repair, _first = _step_parts_split(d, ev2, own, wk_i)
        if stand is None:
            continue
        # the item's own records are the ones its variant alone plays
        mine = set(nm for nm, _t in _step_records(d, ev1, own, wk_i))
        recs = _step_records(d, ev2, own, wk_i)
        credit = next((t for nm, t in recs if nm in mine), None)
        pays = next((t for nm, t in recs if nm not in mine), None)
        e = {'linked': round(stand / 12.0, 2), 'linked_shout': level,
             'linked_repair': round(repair / 12.0, 2) if repair is not None else None,
             'linked_tail': _secs(_shout_tail(d, ev2, own, wk_i)),
             'linked_scene': _scene_secs(_scene_span(d, ev2, own, wk_i)),
             'linked_credit': round(credit / 12.0, 2) if credit is not None else None,
             'linked_jingles': [_secs(t) for t in _step_jingles(d, ev2, own, wk_i)],
             'linked_pays': round(pays / 12.0, 2) if pays is not None else None}
        cont = LINKED_CONT.get(n, {}).get(item)
        if cont is not None and level == -1:
            # the poll step after it: the co-actor's action the poll waits
            # for (its start ends the poll), then the step's parts up to its
            # SHOUT — the part the co-actor's action covers, the rest after
            # it, the record they pay and its second from the action's start
            step, obj, anim, actor = cont
            evc, _nx = run_step(lv2, step, dict(byi), unknown=1, streq=1)
            lift = d.action_ticks(obj, anim, actor=actor)
            cstand, clevel, crepair, _c = _step_parts_split(d, evc)
            crecs = _step_records(d, evc)
            if lift is not None and cstand is not None and crecs:
                # (the lift's own jingle records, on the co-actor's action
                # from its start: 207's n_lift, jingle on its tick 0)
                e['linked_hit_jingles'] = {actor: [_secs(t) for t in d.jingles(obj, anim, actor)]}
                e.update({'linked_shout': clevel,
                          'linked_repair': round(crepair / 12.0, 2) if crepair is not None else None,
                          'linked_tail': _secs(_shout_tail(d, evc)),
                          'linked_hit': round(lift / 12.0, 2),
                          'linked_after_hit': round(max(0, cstand - lift) / 12.0, 2),
                          'linked_extra': crecs[0][0],
                          'linked_extra_at': round(crecs[0][1] / 12.0, 2),
                          'linked_scene': _scene_secs(_scene_span(d, ev2 + [('STEP',)] + evc, own, wk_i))})
        out[item].update(e)
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
    snaps = []
    steps, _loop = walk(lv, st, bytes0=LAP_BYTES.get(n), snaps=snaps)
    events = {cur: ev for cur, ev, _nxt in steps}
    out = {}
    for item, (many, visits) in pairs.items():
        if any(v is None for v in visits):
            continue
        if many:
            # a two-way station: each visit's step run with its variants
            # (201's puddle: the slip's crash_short and the left slip's)
            base = moves.get(item) or [0] * len(visits)
            per = []
            for k, v in enumerate(visits):
                i = max(i for i, _j, _p in v)
                per.append(_tricked_move(n, d, lap, events, snaps, i, base[k]))
            if per != base:
                out[item] = per
            continue
        i = max(i for i, _j, _p in visits[0])
        dx = _tricked_move(n, d, lap, events, snaps, i, moves.get(item, 0))
        if dx != moves.get(item, 0):
            out[item] = dx
    return out


def code_places_tricked(n):
    """{mobile item: (x, y), or a list per visit}: code_places after a TRICKED
    visit — the station's step run with the tricked variants of its
    IsVariant pairs shown (_tricked_move's), where it leaves a hideout
    (209's hot coal: out at 1365 px, 293 right of the coal; 213's tricked
    picnic out of the water at its `beat`, 1175 px; 212's tricked bench 75
    right; 210's hedgehog chair 47 left); items without such a variant left
    out"""
    d = Data(n); g = Geometry(n)
    lap, pairs = _paired_parts(n)
    st = LAP_START.get(n) or level_start(n)
    lv = Level(n)
    for hid, shown in LAP_PRESENT.get(n, ()):
        lv.present.discard(hid); lv.present.add(shown)
    snaps = []
    steps, _loop = walk(lv, st, bytes0=LAP_BYTES.get(n), snaps=snaps)
    events = {cur: ev for cur, ev, _nxt in steps}
    out = {}
    for item, (many, visits) in pairs.items():
        if any(v is None for v in visits):
            continue
        per = []
        for v in (visits if many else visits[:1]):
            i = max(i for i, _j, _p in v)
            per.append(_tricked_place(n, d, g, lap, events, snaps, i))
        if any(x is not None for x in per):
            out[item] = per if many else per[0]
    for item, (stp, shown, hidden) in TRICKED_PLACES.get(n, {}).items():
        lv2 = Level(n)
        for hid, sh in LAP_PRESENT.get(n, ()):
            lv2.present.discard(hid); lv2.present.add(sh)
        lv2.present.discard(hidden); lv2.present.add(shown)
        ev2, _nx = run_step(lv2, stp, dict(LAP_BYTES.get(n) or {}))
        if stp == 0x1003613a:
            # the leave step names no hideout: the one the bench's bar step
            # entered with the variant shown (its IsVariant's pick)
            ev2 = [('E6bd4', [shown], [])] + ev2
        q = _place_of(d, g, ev2)
        if q is not None:
            out[item] = q
    return out


# the tricked visits whose hideout leave is in a step the IsVariant swap of
# the visit's last row does not reach: {level: {mobile item: (the step, the
# variant shown, the one hidden)}} — 212's bench: its leave step 0x1003613a
# with bank_manip present leaves it (then the bull's crash and SHOUT 1);
# 210's chair: 0x1001964b with the hedgehog's picks it, enters and leaves it
# (SHOUT 0, the repair). (213's tricked picnic is the lap row's own step,
# its latch set: out of the water at its `neighbor_out` and on to its `beat`)
TRICKED_PLACES = {212: {'SleepBench': (0x1003613a, 'midleft_bank_manip', 'midleft_bank')},
                  210: {'DeckChair': (0x1001964b, 'beachleft_deckchair_hedgehog', 'beachleft_deckchair')}}


def _place_of(d, g, ev):
    """the placement of the flow's last hideout leave and the translations of
    the parts from it on (code_places) — and a GoTo element's walk after it
    (213's tricked picnic: out of the water to its `beat`) —, None without
    one (_station_parts' position)"""
    if not any(e[0] == 'E6c2e' for e in ev):
        return None
    ctx = {}
    _station_parts(d, ev, ctx)
    pos = ctx.get('pos')
    return (pos[1], pos[2]) if pos else None


def _tricked_place(n, d, g, lap, events, snaps, i):
    """the placement after the lap row i's step run with its tricked
    variants (_tricked_move), where it leaves a hideout; else None"""
    cur = lap[i][1]
    lv, byi = _row_level(n, snaps, lap[i][0])
    alts = []
    for e in events.get(cur) or []:
        if e[0] != 'IFVAR':
            continue
        cands = [c for c in e[1] if not str(c).startswith('$')]
        if len(cands) > 1 and e[2] == cands[0]:
            alts.append((cands[0], cands[1]))
    if not alts:
        return None
    lv2 = Level(n)
    lv2.present = set(lv.present)
    for pick, alt in alts:
        lv2.present.discard(pick); lv2.present.add(alt)
    # (a row the lap's walk passes as a poll: its latch set)
    lat = int(any(a == 'POLL' for _o, a, _t in lap[i][4]))
    ev2, _nx = run_step(lv2, cur, dict(byi), latch=lat)
    return _place_of(d, g, ev2)


def _tricked_move(n, d, lap, events, snaps, i, untricked):
    """the move after the lap row i's step run with the tricked variants of
    its IsVariant pairs shown (the untricked move where it has none)"""
    if True:
        cur = lap[i][1]
        lv, byi = _row_level(n, snaps, lap[i][0])
        alts = []
        for e in events.get(cur) or []:
            if e[0] != 'IFVAR':
                continue
            cands = [c for c in e[1] if not str(c).startswith('$')]
            # the untricked lap picks the first; the second is the tricked one
            if len(cands) > 1 and e[2] == cands[0]:
                alts.append((cands[0], cands[1]))
        if not alts:
            return untricked
        lv2 = Level(n)
        lv2.present = set(lv.present)
        for pick, alt in alts:
            lv2.present.discard(pick); lv2.present.add(alt)
        ev2, _nx = run_step(lv2, cur, dict(byi))
        parts = station_ticks(d, ev2, {})
        if any(a == 'leave' for _o, a, _t in parts):
            return 0
        return sum(d.translation(o, a)[0] for o, a, _t in parts)


def _paired_parts(n):
    """(the lap's rows, {mobile item: (per visit, [its parts [(row, part
    index, (object, action, ticks))] per visit, None where a pair is
    missing])}) by PAIRS[n] over the lap's parts (each part paired once, in
    the lap's order)"""
    rows, loop = lap_steps(n)
    if loop is None and n not in OPEN_LAPS:
        return [], {}
    lap = rows if loop is None else rows[loop:]
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


if __name__ == '__main__':
    for n in [int(x) for x in sys.argv[1:]] or range(201, 215):
        report(n)
