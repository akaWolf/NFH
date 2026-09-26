"""The tricked branches of game.exe's Season 1 scripts around every trick
fire (2026-09-22): what the neighbour does before and after the step that
scores, read off the radare2 text listing the way tools/pcref/fire_sites.py
reads the fire itself. A level class's `run` is a linear script — every
posted step (`mov byte [esp + N], case; call fcn.004766e0`) is its own
resume case, and the compiler lays a tricked branch out as one straight run
of code from the variant test to the `jmp` that rejoins the normal path — so
the branch is the instruction range around the fire site up to the nearest
jump on either side, and its calls in code order are its steps: DoAction
(fcn.00477f60: result, object, action — the object and the action are the
two String slots, read through the stack emulation), GoTo (fcn.00479da0),
Switch (fcn.00451de0), the repair helper (fcn.0047ae70: the tricked object's
`repair`, else `clean`), a sub-sequence (fcn.00476770), the waits and the
fire itself (OBJ2 = fcn.0047c290 scores after the steps before it; FIRE5 =
fcn.0047c320 scores before its own clip; FIRE4 = fcn.0047c3b0 scores after
its ready step, the clip queued just before it). The seconds are objects.xml's
`time` ticks or the actor clip's frames at 12 a second, an action looked up
on its `<object>` or `<actor>` (the neighbour's own smokepipe_explosive,
riphat, spit …) in the level's file, then generic/objects.xml.

    python3 tools/pcref/trick_branches.py [--json out] [106 110 ...]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fire_sites as FS   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
X = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
LEVEL_DIR = {101: 'level_peep', 102: 'level_sofa', 103: 'level_mail', 104: 'level_pie', 105: 'level_piano',
             106: 'level_bath', 107: 'level_art', 108: 'level_suntan', 109: 'level_pig', 110: 'level_barbecue',
             111: 'level_laundry', 112: 'level_fitness', 113: 'level_DIY', 114: 'level_hunter'}
FPS = 12.0
CALLS = {'fcn.00477f60': 'ACTION', 'fcn.00479da0': 'GOTO', 'fcn.00451de0': 'SWITCH', 'fcn.0047a130': 'IFVARIANT',
         'fcn.00451e80': 'OBJ1', 'fcn.00479ff0': 'OBJ3', 'fcn.0047ae70': 'REPAIR', 'fcn.00476770': 'SUBSEQ',
         'fcn.00437f70': 'ICON', 'fcn.0047c290': 'OBJ2', 'fcn.0047c320': 'FIRE5', 'fcn.0047c3b0': 'FIRE4',
         'fcn.004766e0': 'post', 'fcn.0044bb80': 'dtor', 'fcn.0047c640': 'wait', 'fcn.0045f670': 'wait2',
         'fcn.00457610': 'obj', 'fcn.0044ac80': 'GOTO', 'fcn.00444ad0': 'GOTO', 'fcn.00479f10': 'GOTOENTER',
         'fcn.00473e20': 'ENTER', 'fcn.0047c6c0': 'STOPMSG', 'fcn.00413780': 'IFTRICKED',
         'fcn.00479e30': 'GOTOENTER', 'fcn.00473ea0': 'LEAVE', 'fcn.00448bf0': 'LOOKUP', 'fcn.00444ad0': 'GOTO2',
         'fcn.00446020': 'INV'}
L = FS.L
G = FS.G
parse = FS.parse


def _frames(text):
    """{(object, animation): (frames, type)} of an anims.xml (the actors are
    objects of it too: neighbor, woody, chili, dog) — type oneshot or loop"""
    out = {}
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', text, re.S):
        for am in re.finditer(r'<animation name="([^"]+)"([^>]*)>(.*?)</animation>', om.group(2), re.S):
            at = dict(re.findall(r'(\w+)="([^"]*)"', am.group(2)))
            out[(om.group(1), am.group(1))] = (len(re.findall(r'<frame\b', am.group(3))),
                                               at.get('type', 'oneshot'))
    return out


class Level(object):
    def __init__(self, n):
        d = os.path.join(X, LEVEL_DIR[n])
        self.n = n
        self.texts = [open(os.path.join(d, 'objects.xml'), encoding='utf-8', errors='replace').read(),
                      open(os.path.join(X, 'generic/objects.xml'), encoding='utf-8', errors='replace').read()]
        self.generic = _frames(open(os.path.join(X, 'generic/anims.xml'), encoding='utf-8', errors='replace').read())
        self.fr = _frames(open(os.path.join(d, 'anims.xml'), encoding='utf-8', errors='replace').read())
        self.names = set()
        self.gfx = {}
        for t in self.texts:
            for m in re.finditer(r'<(?:object|actor)\b([^>]*)>', t):
                at = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
                if 'name' in at:
                    self.names.add(at['name'])
                    if at.get('gfx'):
                        self.gfx[at['name']] = at['gfx']

    def _anim(self, obj, anim):
        return self.fr.get((obj, anim)) or self.generic.get((obj, anim)) \
            or self.fr.get((self.gfx.get(obj, obj), anim)) or self.generic.get((self.gfx.get(obj, obj), anim))

    def frames(self, obj, anim):
        v = self._anim(obj, anim)
        return v[0] if v else 0

    def oneshot(self, obj, anim):
        """Loader.dll's lookup with its flag 1 (0x10005340): a oneshot's
        frames, a loop or a missing animation -1"""
        v = self._anim(obj, anim)
        return v[0] if v and v[1] == 'oneshot' else -1

    def blocks(self, obj):
        """the object's or actor's blocks: the level's file first, then generic's
        (the neighbour's `hurt`, `take_low`, the shouts live in generic)"""
        out = []
        for t in self.texts:
            for m in re.finditer(r'<(object|actor)\b[^>]*\bname="%s"[^>]*>(.*?)</\1>' % re.escape(obj), t, re.S):
                out.append(m.group(2))
        return out

    def block(self, obj):
        b = self.blocks(obj)
        return b[0] if b else None

    def action(self, obj, name):
        """seconds of the action `name` of the PC object or actor, or None: the
        record's time as Loader.dll stores it — time="N" as N, time="auto" as
        the longer of the actor's and the object's oneshot animation less one,
        at least 0 (`inv` not asked; NFH1's Loader.dll 0x1000a865-0x1000aa05)
        — as the ACTION step, the time + 2 ticks (lap_model.job_ticks), at 12
        a second"""
        for b in self.blocks(obj):
            for a in re.finditer(r'<action\b([^>]*)/?>', b):
                at = dict(re.findall(r'(\w+)="([^"]*)"', a.group(1)))
                if at.get('name') != name:
                    continue
                tm = at.get('time', 'auto')
                if tm.isdigit():
                    t = int(tm)
                else:
                    actor = at.get('actor', 'neighbor')
                    aa, oa = at.get('actoranim', ''), at.get('objanim', '')
                    va = self.oneshot(actor, aa) if aa and aa != 'inv' else -1
                    vo = self.oneshot(obj, oa) if oa and oa != 'inv' else -1
                    t = max(max(va, vo) - 1, 0)
                # the ACTION step: its start and the timer's time + 1
                # updates (lap_model.Level.job_ticks)
                return (t + 2) / FPS
        return None

    def clip(self, name, actor='neighbor'):
        n = self.frames(actor, name)
        return n / FPS if n else None

    def owner_of(self, name):
        """the objects and actors carrying an action of that name"""
        out = []
        for t in self.texts:
            for m in re.finditer(r'<(object|actor)\b[^>]*\bname="([^"]+)"[^>]*>(.*?)</\1>', t, re.S):
                if re.search(r'<action\b[^>]*\bname="%s"' % re.escape(name), m.group(3)):
                    out.append(m.group(2))
        return out

    def fix(self, obj):
        """fcn.0047ae70: the tricked object's repair, else clean, else 0"""
        for nm in ('repair', 'clean'):
            v = self.action(obj, nm)
            if v:
                return nm, v
        return None, 0.0


# ---- the listing ------------------------------------------------------------
INS = FS.INS


def _line_of(addr):
    for i, ln in enumerate(L):
        a, _ = parse(ln)
        if a == addr:
            return i
    return None


LINE = {}
for _i, _ln in enumerate(L):
    _a, _ = parse(_ln)
    if _a is not None:
        LINE[_a] = _i
import bisect   # noqa: E402
_KEYS = sorted(LINE)


def at(addr):
    """the line of the instruction at or after the address"""
    i = bisect.bisect_left(_KEYS, addr)
    return LINE[_KEYS[min(i, len(_KEYS) - 1)]]


def prologue(i):
    for j in range(i, max(0, i - 8000), -1):
        a, ins = parse(L[j])
        if ins and ins.startswith('push 0xffffffffffffffff'):
            return a
    return None


def _boundary(a, ins):
    """a real branch edge: an unconditional jump, a return, or a conditional
    jump that leaps further than the compiler's five-byte null-check skip
    (`cmp ecx, edi; je +5; mov eax, [ecx]; call [eax + 4]`)"""
    if ins.startswith('ret') or ins.startswith('jmp '):
        return True
    m = re.match(r'^j[a-z]+ 0x([0-9a-f]+)$', ins)
    if m:
        t = int(m.group(1), 16)
        return not (0 < t - a <= 0x10)
    return False


def bounds(i):
    """the branch around line i: back to the nearest branch edge (the variant
    test or the previous branch's rejoin), forward to the nearest (the rejoin)"""
    lo = i
    for j in range(i - 1, max(0, i - 3000), -1):
        a, ins = parse(L[j])
        if ins is None:
            continue
        if _boundary(a, ins) or ins.startswith('push 0xffffffffffffffff'):
            lo = j + 1
            break
    hi = i
    for j in range(i + 1, min(len(L), i + 3000)):
        a, ins = parse(L[j])
        if ins is None:
            continue
        if _boundary(a, ins):
            hi = j
            break
    return lo, hi


def regvalue(i, reg):
    """the string a register carries at line i (the last global load into it
    on the straight path above; None when it is a copy or an address)"""
    for j in range(i - 1, max(0, i - 3000), -1):
        a, ins = parse(L[j])
        if ins is None:
            continue
        m = re.match(r'^mov %s, dword \[(0x5[0-9a-f]{5})\]$' % reg, ins)
        if m:
            return G.get(m.group(1))
        if re.match(r'^(mov|xor|pop|lea) %s\b' % reg, ins):
            m2 = re.match(r'^mov %s, (e[a-z]{2})$' % reg, ins)
            if m2:
                return regvalue(j, m2.group(1))
            return None
        if ins.startswith('push 0xffffffffffffffff'):
            return None
    return None


def strings_near(j, n=14):
    """the string globals loaded in the n lines before the call at j"""
    out = []
    for jj in range(max(0, j - n), j):
        for mm in re.finditer(r'(0x5[0-9a-f]{5})', L[jj]):
            nm = G.get(mm.group(1))
            if isinstance(nm, str):
                out.append(nm)
    return out


def _resolved(v):
    return isinstance(v, str) and not v.startswith(('dword [', 'addr')) and v not in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi', 'ebp', '?')


def call_args(i, n):
    """the n arguments of the call at line i, top-first, registers resolved"""
    st = FS.decode(i)
    args = list(reversed(st[-n:] if len(st) >= n else st))
    out = []
    for v in args:
        if v in ('eax', 'ecx', 'edx', 'ebx', 'esi', 'edi', 'ebp'):
            r = regvalue(i, v)
            out.append(r if r is not None else v)
        else:
            out.append(v)
    return out


def branch(i):
    """the steps of the straight branch around the fire at line i (the
    walk-trigger handlers, which are no switch cases)"""
    lo, hi = bounds(i)
    return lo, hi, tokens_between(lo, hi, i)


def tokens_between(lo, hi, site_line=None):
    steps = []
    for j in range(lo, hi + 1):
        a, ins = parse(L[j])
        if ins is None:
            continue
        m = re.match(r'^call (fcn\.[0-9a-f]{8})$', ins)
        if not m:
            continue
        t = token(j, m.group(1), site_line)
        if t is not None:
            steps.append(t)
    return steps


def token(j, f, site_line=None):
    """one call of the script as a step token, or None for the plumbing"""
    a, _ = parse(L[j])
    kind = CALLS.get(f, f)
    if kind == 'ACTION':
        args = call_args(j, 5)          # result, object, action, 0, 0
        args = (args + ['?'] * 5)[:5]
        obj, act = args[1], args[2]
        if not _resolved(act):
            # the name loaded before a helper that picks the object (the
            # sofa's variant for sit_beer): back to the previous posted step
            back = 14
            for jj in range(j - 1, max(0, j - 60), -1):
                if re.search(r'call fcn\.(004766e0|0045f670|0047c640)$', L[jj]):
                    back = j - jj; break
            near = [x for x in strings_near(j, back) if '/' not in x]
            act = near[-1] if near else act
        return dict(a=a, kind='ACTION', obj=obj, act=act, fire=(j == site_line), raw=args)
    if kind in ('GOTO', 'GOTOENTER', 'ENTER', 'LEAVE', 'GOTO2'):
        args = call_args(j, 2)
        obj = args[-1] if args else '?'
        if not _resolved(obj):
            near = [x for x in strings_near(j) if '/' in x]
            obj = near[-1] if near else obj
        return dict(a=a, kind=kind, obj=obj, fire=False)
    if kind == 'REPAIR':
        return dict(a=a, kind='REPAIR', args=call_args(j, 4), fire=False)
    if kind == 'ICON':
        return dict(a=a, kind='ICON', args=call_args(j, 2), fire=False)
    if kind in ('OBJ2', 'FIRE5', 'FIRE4'):
        return dict(a=a, kind=kind, args=call_args(j, FS.NARGS[kind]), fire=(j == site_line))
    if kind in ('post', 'dtor', 'wait', 'wait2', 'obj', 'STOPMSG'):
        return None
    if kind == 'LOOKUP':
        names = []
        for jj in range(max(0, j - 16), j):
            for mm in re.finditer(r'\[(0x5[0-9a-f]{5})\]', L[jj]):
                nm = G.get(mm.group(1))
                if isinstance(nm, str) and '/' in nm:
                    names.append(nm)
        return dict(a=a, kind='LOOKUP', args=names, fire=False)
    if kind in ('SWITCH', 'IFVARIANT', 'IFTRICKED', 'OBJ1', 'OBJ3', 'SUBSEQ', 'INV'):
        args = [G.get('0x%x' % x, x) if isinstance(x, int) and x > 0x500000 else x for x in call_args(j, 3)]
        return dict(a=a, kind=kind, args=args, fire=False)
    return None


# ---- the level classes: a switch of cases, each ending in a yield ----------
import struct   # noqa: E402
EXE = open(FS.EXE, 'rb').read()
YIELDS = re.compile(r'call fcn\.(0045c600|004706a0|0045e640)')
NATFALSE_FN = {'fcn.0047a130', 'fcn.00479ff0', 'fcn.0047c290', 'fcn.00413780', 'fcn.0047ac20', 'fcn.0047ad20',
               'fcn.0047a0b0', 'fcn.00422c40'}
NATTRUE = {'fcn.0047c640', 'fcn.0047c6c0', 'fcn.004766e0', 'fcn.00476770', 'fcn.00444d30', 'fcn.0044bb80',
           'fcn.0047c320', 'fcn.0047ae70'}
TESTS = {'fcn.0047a130', 'fcn.00413780', 'fcn.00479ff0'}      # IsVariant(tricked, object), IsTricked(object), OBJ3(object, n)


def _switches():
    out = []
    for k, ln in enumerate(L):
        a, t = parse(ln)
        if t is None:
            continue
        m = re.search(r'jmp dword \[e[a-z]x\*4 \+ (0x[0-9a-f]+)\]', t)
        if not m or not (0x435000 <= a < 0x480000):
            continue
        bound = None
        for j in range(k - 1, k - 12, -1):
            aa, tt = parse(L[j])
            mm = tt and re.search(r'cmp e[a-z]x, (0x[0-9a-f]+|[0-9]+)', tt)
            if mm:
                bound = int(mm.group(1), 0); break
        if bound and bound >= 4:
            out.append((a, int(m.group(1), 16), bound))
    return out


class Fiber(object):
    """one level class's run: its cases and a simulation of one case's path
    with one object tricked (routine_order.py's walker, the tricked test of
    that object answering true)"""
    def __init__(self, sw):
        a_sw, tb, n = sw
        self.a_sw = a_sw
        self.starts = list(struct.unpack_from('<%dI' % (n + 1), EXE, tb - 0x400000))
        self.ok = all(0x401000 <= x < 0x4dc000 for x in self.starts)
        if not self.ok:
            return
        self.lo = min(self.starts); self.hi = max(self.starts) + 0x400
        self.case_of = {}
        for i, s in enumerate(self.starts):
            self.case_of.setdefault(s, []).append(i)
        self.tails = set()
        for k in range(at(self.lo), at(self.hi)):
            a, t = parse(L[k])
            if t and YIELDS.search(t):
                self.tails.add(a)
                for j in range(k - 1, k - 3, -1):
                    aa, tt = parse(L[j])
                    if tt and re.match(r'mov ecx, e', tt):
                        self.tails.add(aa)
                self.hi = max(self.hi, a + 0x40)
        self.tested = set()      # the names the class's resolved variant tests carry
        for k in range(at(self.lo), at(self.hi)):
            a, t = parse(L[k])
            if t and re.search(r'call (fcn\.0047a130|fcn\.00413780|fcn\.00479ff0)$', t):
                self.tested.update(x for x in call_args(k, 3) if isinstance(x, str) and '/' in x)
        self.prologue = {}
        for j in range(at(a_sw) - 60, at(a_sw)):
            aa, tt = parse(L[j])
            mm = tt and re.match(r'mov (e[a-z]x|e[sd]i|ebp), (0x[0-9a-f]+|[0-9]+)$', tt)
            if mm:
                self.prologue[mm.group(1)] = int(mm.group(2), 0)

    def _resolve(self, val, regs):
        if re.match(r'^(0x[0-9a-f]+|[0-9]+)$', val):
            return int(val, 0)
        if val in regs:
            return regs[val]
        if val in self.prologue:
            return self.prologue[val]
        return val

    def _yield_next(self, k, regs):
        for j in range(k - 1, k - 8, -1):
            aa, tt = parse(L[j])
            if tt and tt.startswith('push '):
                return self._resolve(tt[5:], regs)
        return '?'

    def simulate(self, start_a, objflags, tricked, flip=False, depth=0, present=None, gone=None):
        """(tokens, next case) along the path from start_a: the waits true,
        a variant test true when its variant is in `tricked` or `present`
        (the objects switched in so far — a Switch or the repair helper
        takes the old one out), class byte fields as set, the level's own
        helpers followed one level deep"""
        present = set() if present is None else present
        gone = set() if gone is None else gone
        lookup_present = None
        tokens = []; k = LINE[start_a]; seen = set(); pred = False; regs = {}; lastcall = None
        flags = {}; inverted = False
        for _ in range(900):
            if k in seen:
                return tokens, 'loop'
            seen.add(k); a, t = parse(L[k])
            if t is None:
                k += 1; continue
            mm = re.match(r'mov (e[a-z]x|e[sd]i|ebp), (0x[0-9a-f]+|[0-9]+)$', t)
            if mm:
                regs[mm.group(1)] = int(mm.group(2), 0)
            elif re.match(r'xor (e[a-z]x|e[sd]i|ebp), \1$', t):
                regs[t.split()[1].rstrip(',')] = 0
            else:
                mm = re.match(r'(mov|lea|pop) (e[a-z]x|e[sd]i|ebp),', t)
                if mm:
                    regs.pop(mm.group(2), None)
            if a in self.tails or YIELDS.search(t):
                return tokens, self._yield_next(k, regs)
            if t.startswith('ret'):
                return tokens, 'ret'
            m = re.match(r'call (fcn\.[0-9a-f]+)', t)
            if m:
                fn = m.group(1)
                pred = False; lastcall = fn
                tk = token(k, fn)
                if tk is not None:
                    tokens.append(tk)
                elif depth < 1 and self.lo - 0x2000 <= int(fn[4:], 16) < self.hi + 0x2000 and fn not in NATTRUE \
                        and fn not in NATFALSE_FN and fn not in CALLS and not YIELDS.search(t) and fn != 'fcn.0047f740':
                    sub, _ = self.simulate(int(fn[4:], 16), objflags, tricked, False, depth + 1, present, gone)
                    tokens.extend(sub)
                    vals = [t['value'] for t in sub if t['kind'] == 'TESTVAL']
                    lvals = [t['value'] for t in sub if t['kind'] == 'LOOKUPVAL']
                    if vals:
                        # a wrapper of a variant test answers as its test does
                        lastcall = ('test', vals[-1])
                    elif lvals:
                        # a helper asking after an object answers by its presence
                        lastcall = ('test', 'true' if 'true' in lvals else 'false')
                if fn in TESTS:
                    names = [x for x in call_args(k, 3) if isinstance(x, str) and '/' in x]
                    if fn == 'fcn.00479ff0':
                        names = [x for x in strings_near(k, 10) if '/' in x] or names
                    variant = names[-1] if names else None
                    if variant is None and fn == 'fcn.00413780':
                        # IsTricked on a name held in a stack slot (the beer of
                        # 102, the candle box of 103, the aftershave of 104):
                        # true while a tricked object remains that no test of
                        # the class names — the chain is only trusted where it
                        # reaches the fire site
                        val = 'true' if any(x not in self.tested for x in tricked) else 'false'
                    elif variant is not None and len(names) == 1 and variant not in tricked and variant not in present \
                            and any(x.startswith(variant + '_') for x in tricked):
                        # IsVariant(normal, variant) with the variant's name in a
                        # register (kit/stool of kit/stool_pins): the twin is tricked
                        val = 'true'
                    else:
                        val = 'true' if variant in tricked or variant in present else 'false'
                    lastcall = ('test', val)
                    tokens.append(dict(a=a, kind='TESTVAL', value=lastcall[1], variant=variant, fire=False))
                if tk is not None and tk['kind'] == 'LOOKUP':
                    # a helper asking after an object (the bath's tub_empty)
                    # answers true once a Switch has taken it out of the
                    # world: the level fills the tub first, bathes after
                    lookup_present = any(x in gone for x in tk['args'])
                    tokens.append(dict(a=a, kind='LOOKUPVAL', value='true' if lookup_present else 'false', fire=False))
                if tk is not None and tk['kind'] == 'SWITCH':
                    objs = [x for x in tk['args'] if isinstance(x, str) and '/' in x]
                    if len(objs) == 2:
                        present.discard(objs[0]); tricked.discard(objs[0]); present.add(objs[1])
                        gone.add(objs[0]); gone.discard(objs[1])
                if tk is not None and tk['kind'] == 'REPAIR':
                    objs = [x for x in tk['args'] if isinstance(x, str) and '/' in x]
                    for o in objs:
                        present.discard(o); tricked.discard(o)
                    if objs:
                        gone.add(objs[-1])
                k += 1; continue
            if t == 'test al, al':
                if lastcall is None:
                    pred = 'false'
                elif isinstance(lastcall, tuple):
                    pred = lastcall[1]
                elif lastcall == 'fcn.00422c40' and lookup_present is not None:
                    pred = 'true' if lookup_present else 'false'
                elif lastcall in NATFALSE_FN:
                    pred = 'false'
                elif 0x44c000 <= int(lastcall[4:], 16) < 0x478000:
                    pred = 'false'
                else:
                    pred = 'true'
                if flip and not (isinstance(lastcall, str) and (lastcall in NATFALSE_FN or 0x44c000 <= int(lastcall[4:], 16) < 0x478000)):
                    pred = 'false' if pred == 'true' else 'true'
                k += 1; continue
            m = re.match(r'jmp (0x[0-9a-f]+)', t)
            if m:
                tgt = int(m.group(1), 16)
                if tgt in self.tails:
                    return tokens, self._yield_next(k, regs)
                if tgt not in LINE:
                    return tokens, 'out'
                k = LINE[tgt]; continue
            m = re.match(r'j(e|ne|z|nz) (0x[0-9a-f]+)', t)
            if m:
                cc, tgt = m.group(1), int(m.group(2), 16)
                if pred:
                    nat = pred; pred = False; lastcall = False
                    jump_if_zero = cc in ('e', 'z')
                    take = (jump_if_zero and nat == 'false') or ((not jump_if_zero) and nat == 'true')
                    if take and tgt in LINE:
                        k = LINE[tgt]; continue
                    k += 1; continue
                k += 1; continue
            mm = re.match(r'set(e|ne) byte \[esp \+ (0x[0-9a-f]+)\]', t)
            if mm:
                flags[mm.group(2)] = 'true' if mm.group(1) == 'e' else 'false'
            if t == 'sbb al, al':
                inverted = True
            mm = re.match(r'mov byte \[esp \+ (0x[0-9a-f]+)\], al', t)
            if mm:
                if inverted:
                    flags[mm.group(1)] = 'false'; inverted = False
                elif isinstance(lastcall, str) and lastcall.startswith('fcn.'):
                    flags[mm.group(1)] = 'false' if (lastcall in NATFALSE_FN or 0x44c000 <= int(lastcall[4:], 16) < 0x478000) else 'true'
                elif isinstance(lastcall, tuple):
                    flags[mm.group(1)] = lastcall[1]
            mm = re.match(r'mov al, byte \[esp \+ (0x[0-9a-f]+)\]', t)
            if mm:
                lastcall = ('flag', flags.get(mm.group(1), 'false'))
            else:
                mm = re.match(r'mov al, byte \[e[ds]i \+ (0x[0-9a-f]+)\]', t)
                if mm:
                    lastcall = ('flag', 'true' if objflags.get(mm.group(1), 0) else 'false')
                elif t.startswith('mov al,'):
                    lastcall = ('flag', 'false')
            mm = re.match(r'mov byte \[e[ds]i \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|[0-9]+)$', t)
            if mm:
                objflags[mm.group(1)] = int(mm.group(2), 0)
            mm = re.match(r'mov byte \[e[ds]i \+ (0x[0-9a-f]+)\], al$', t)
            if mm:
                # IsTricked's answer kept in a class byte (the candle box's
                # [edi+0x18], the beer's [esi+0x1c], the basin's two)
                if isinstance(lastcall, tuple):
                    objflags[mm.group(1)] = 1 if lastcall[1] == 'true' else 0
                elif isinstance(lastcall, str) and lastcall.startswith('fcn.'):
                    objflags[mm.group(1)] = 0 if (lastcall in NATFALSE_FN or 0x44c000 <= int(lastcall[4:], 16) < 0x478000) else 1
            mm = re.match(r'cmp byte \[e[ds]i \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|[0-9]+)$', t)
            if mm:
                pred = 'true' if objflags.get(mm.group(1), 0) != int(mm.group(2), 0) else 'false'
                k += 1; continue
            if re.match(r'(cmp |xor eax|movzx eax)', t):
                lastcall = None
            k += 1
        return tokens, 'toolong'

    def chain(self, tricked, limit=160):
        """the case chain from case 0 with `tricked` tricked: [(case, tokens)]"""
        seq = []; c = 0; objflags = {}; states = set(); tricked = set(tricked); present = set(); gone = set()
        for _ in range(limit):
            key = (c, tuple(sorted(objflags.items())), tuple(sorted(tricked)), tuple(sorted(present)), tuple(sorted(gone)))
            if key in states:
                break
            states.add(key)
            if c >= len(self.starts):
                break
            start = self.starts[c]
            tokens, nxt = self.simulate(start, objflags, tricked, present=present, gone=gone)
            if nxt == 'ret':
                t2, n2 = self.simulate(start, objflags, tricked, flip=True, present=present, gone=gone)
                if isinstance(n2, int):
                    tokens, nxt = t2, n2
            seq.append((c, tokens, nxt))
            if isinstance(nxt, int):
                c = nxt
            else:
                break
        return seq


FIBERS = None


def fibers():
    global FIBERS
    if FIBERS is None:
        FIBERS = [f for f in (Fiber(sw) for sw in _switches()) if f.ok]
    return FIBERS


def fiber_of(addr, depth=0):
    """the level class whose run holds the address, or calls the handler
    that holds it (one level of callers)"""
    i = LINE.get(addr)
    if i is None:
        return None
    pro = prologue(i)
    if pro is None:
        return None
    for f in fibers():
        if pro <= f.a_sw < f.hi and f.lo >= pro:
            return f
    if depth >= 1:
        return None
    for j, ln in enumerate(L):
        if ln.endswith('call fcn.%08x' % pro):
            a, _ = parse(ln)
            f = fiber_of(a, depth + 1)
            if f is not None:
                return f
    return None


def level_of(pro, levels):
    """the level whose objects.xml names the fiber's strings most"""
    if pro is None:
        return None
    lo = LINE.get(pro)
    if lo is None:
        return None
    refs = set()
    for j in range(lo, min(len(L), lo + 12000)):
        a, ins = parse(L[j])
        if ins is None:
            continue
        if ins.startswith('push 0xffffffffffffffff') and j > lo:
            break
        for m in re.finditer(r'\[(0x5[0-9a-f]{5})\]', ins):
            s = G.get(m.group(1))
            if s and '/' in s:
                refs.add(s)
    best = None
    for n, lv in levels.items():
        hit = len(refs & lv.names)
        if best is None or hit > best[0]:
            best = (hit, n)
    return best[1] if best and best[0] else None


def seconds(lv, obj, act, prefer=()):
    """the action's seconds; an unresolved owner (a register or a stack slot)
    is the site's object or one named in the stand when it has the action,
    else the one owner of that action name, else any owner when they all agree"""
    if obj in (None, '?') or isinstance(obj, int) or (isinstance(obj, str) and lv.block(obj) is None):
        owners = lv.owner_of(act) if isinstance(act, str) else []
        pick = [o for o in prefer if o in owners]
        if pick:
            obj = pick[0]
        elif len(owners) == 1:
            obj = owners[0]
        elif owners:
            vals = {lv.action(o, act) for o in owners}
            if len(vals) == 1:
                return vals.pop(), '%s.%s' % ('/'.join(sorted({o.split('/')[-1] for o in owners}))[:20] + '…', act)
            return None, '%s? (%s)' % (act, '/'.join(owners))
        else:
            return None, '%s.%s?' % (obj, act)
    v = lv.action(obj, act) if isinstance(act, str) else None
    return v, '%s.%s' % (obj, act)


def _flat(seq):
    flat = []
    for c, tokens, nxt in seq:
        for t in tokens:
            if t['kind'] in ('TESTVAL', 'LOOKUPVAL'):
                continue
            t = dict(t); t['case'] = c; flat.append(t)
    return flat


def _stand(flat, j):
    """the station stand around token j: the tokens between the walks (GOTO,
    GOTOENTER) and the bubbles (ICON) on either side"""
    def is_edge(t):
        # a walk (GoTo, GoTo-and-enter) or a bubble; the in-stand step
        # fcn.00444ad0 (GOTO2: the piano's step to the smeared score) is none
        return t['kind'] in ('ICON', 'GOTO', 'GOTOENTER')
    g0 = max([x for x in range(j, -1, -1) if is_edge(flat[x])] or [-1]) + 1
    g1 = min([x for x in range(j + 1, len(flat)) if is_edge(flat[x])] or [len(flat)])
    icon = None
    for x in range(g0 - 1, -1, -1):
        if flat[x]['kind'] == 'ICON':
            icon = flat[x]['args'][0] if flat[x]['args'] else None
            break
    if g0 > 0 and flat[g0 - 1]['kind'] == 'GOTOENTER':
        # the walk-and-enter helper (fcn.00479e30) plays the object's `enter`
        # on arrival: the shower's 2.83 s clip before the tub's hair
        flat.insert(g0, dict(flat[g0 - 1], kind='ENTER', synthetic=True))
        g1 += 1
    return g0, g1, icon


def analyse(levels):
    rows = []
    sites = FS.sites()
    meta = []
    for i, a, kind, top, notes, regs in sites:
        pro = prologue(i)
        n = level_of(pro, levels)
        name = top[0] if top and isinstance(top[0], str) else '?'
        meta.append((i, a, kind, top, n, pro, name, fiber_of(a)))
    chains = {}
    for i, a, kind, top, n, pro, name, f in meta:
        row = dict(addr=a, kind=kind, args=top, level=n, fiber=pro, name=name, steps=None, group=None)
        if f is not None and name != '?':
            key = (f.a_sw, n)
            if key not in chains:
                allnames = {m[6] for m in meta if m[7] is f and m[6] != '?'}
                chains[key] = (allnames, _flat(f.chain(allnames)))
            allnames, flat_all = chains[key]
            flat = _flat(f.chain({name}))
            hit = [j for j, t in enumerate(flat) if t['kind'] in ('OBJ2', 'FIRE5', 'FIRE4') and t['a'] == a]
            used = 'this tricked'
            if not hit:
                flat = list(flat_all)
                hit = [j for j, t in enumerate(flat) if t['kind'] in ('OBJ2', 'FIRE5', 'FIRE4') and t['a'] == a]
                used = 'all tricked'
            if hit:
                j = hit[0]
                flat[j]['fire'] = True
                g0, g1, icon = _stand(flat, j)
                row['steps'] = flat[g0:g1]
                row['group'] = (icon, g0, g1)
                row['class'] = '%x' % f.a_sw
                row['chain'] = used
            else:
                row['note'] = 'no case chain reaches the site'
        if row['steps'] is None:
            lo, hi, steps = branch(i)
            row['steps'] = steps; row['lo'] = parse(L[lo])[0]; row['hi'] = parse(L[hi])[0]
        rows.append(row)
    return rows


def _pair_rule(steps):
    """of doubletake1/doubletake3 and slip1/slip3 pairs only the second plays"""
    out = []
    for s in steps:
        if out and s['kind'] == 'ACTION' and out[-1]['kind'] == 'ACTION' \
                and (out[-1]['act'], s['act']) in (('doubletake1', 'doubletake3'), ('slip1', 'slip3')):
            out[-1] = s
            continue
        out.append(s)
    return out


def summarise(row, lv):
    """before/after seconds around the fire, the fire's own clip, the fix"""
    before = []; after = []; seen_fire = False; fix = None; walks = []
    unknown = []; fixes = []
    prefer = [row['name']]
    if '_' in row['name'].split('/')[-1]:
        prefer.append(row['name'].rsplit('_', 1)[0])       # the normal twin (lir/tabacbox of lir/tabacbox_explosive)
    for s in row['steps']:
        for v in (s.get('obj'), s.get('args')):
            if isinstance(v, str) and '/' in v and v not in prefer:
                prefer.append(v)
            if isinstance(v, list):
                prefer.extend(x for x in v if isinstance(x, str) and '/' in x and x not in prefer)
    for s in _pair_rule(row['steps']):
        if s.get('fire'):
            seen_fire = True
            continue
        if s['kind'] == 'ACTION':
            v, label = seconds(lv, s['obj'], s['act'], prefer)
            if v is None:
                unknown.append(label)
                v = 0.0
            if seen_fire and s['act'] in ('repair', 'clean'):
                fixes.append((label, v))
            else:
                (after if seen_fire else before).append((label, v))
        elif s['kind'] in ('ENTER', 'LEAVE'):
            act = s['kind'].lower()
            v, label = seconds(lv, s['obj'], act, prefer)
            if v is None:
                unknown.append(label); v = 0.0
            (after if seen_fire else before).append((label, v))
        elif s['kind'] in ('GOTO', 'GOTOENTER'):
            walks.append(('%s:%s' % (s['kind'].lower(), s['obj']), seen_fire))
            if seen_fire:
                break               # a walk after the fire ends the stand (the skate's way back)
        elif s['kind'] == 'REPAIR':
            fix = s['args']
            # fcn.0047ae70(normal, tricked, …): the tricked object is the
            # last name (wor/cups_black at the black polish's site)
            named = [x for x in s['args'] if isinstance(x, str) and '/' in x]
            obj = named[-1] if named else row['name']
            nm, v = lv.fix(obj)
            if nm:
                fixes.append(('%s.%s' % (obj, nm), v))
    own = None
    if row['kind'] == 'FIRE5':
        anim = row['args'][3] if len(row['args']) > 3 else None
        actor = row['args'][4] if len(row['args']) > 4 else None
        v = lv.action(actor, anim) if isinstance(actor, str) and isinstance(anim, str) else None
        if v is None and isinstance(anim, str):
            v = lv.clip(anim)
        own = ('%s.%s' % (actor, anim), v)
    return dict(before=before, after=after, own=own, fix=fix, fixes=fixes, unknown=unknown, walks=walks)


def dump_cases(n, levels):
    """every case of the level's class(es) with all its tricks tricked"""
    names = set()
    fs = {}
    for i, a, kind, top, notes, regs in FS.sites():
        if level_of(prologue(i), levels) != n:
            continue
        f = fiber_of(a)
        if f is None:
            continue
        fs[f.a_sw] = f
        if top and isinstance(top[0], str):
            names.add(top[0])
    for f in fs.values():
        print('class %x, %d cases, tricked %s' % (f.a_sw, len(f.starts), sorted(names)))
        seq = f.chain(names)
        print('  chain: ' + ' > '.join('%s' % c for c, _, _ in seq) + ' | last next %s' % (seq[-1][2] if seq else '-'))
        for st in sorted(set(f.starts), key=lambda x: f.starts.index(x)):
            toks, nxt = f.simulate(st, {}, set(names), present=set(), gone=set())
            print('  case %-14s %08x -> %-5s %s' % (f.case_of[st], st, nxt, ' '.join(
                ('%s:%s.%s' % (t['kind'][:3], t.get('obj'), t.get('act'))) if t['kind'] == 'ACTION' else
                ('%s:%s' % (t['kind'], t.get('obj') or t.get('value') or t.get('args'))) for t in toks)[:400]))


def dump_chain(n, levels):
    """the case chain of the level's class(es) with all its tricks tricked, the
    carried state applied (the tests' answers shown)"""
    names = set(); fs = {}
    for i, a, kind, top, notes, regs in FS.sites():
        if level_of(prologue(i), levels) != n:
            continue
        f = fiber_of(a)
        if f is None:
            continue
        fs[f.a_sw] = f
        if top and isinstance(top[0], str):
            names.add(top[0])
    for f in fs.values():
        print('class %x, %d cases, tricked %s' % (f.a_sw, len(f.starts), sorted(names)))
        for c, toks, nxt in f.chain(names):
            print('  case %-3s -> %-5s %s' % (c, nxt, ' '.join(
                ('%s:%s.%s' % (t['kind'][:3], t.get('obj'), t.get('act'))) if t['kind'] == 'ACTION' else
                ('%s:%s' % (t['kind'], t.get('obj') or t.get('value') or t.get('args'))) for t in toks)[:420]))


def dump_code(lo, hi):
    """the calls, tests and jumps of an address range with the strings near them"""
    for k in range(at(lo), at(hi)):
        a, t = parse(L[k])
        if t and re.search(r'call fcn|cmp|test|j[a-z]+ 0x|push (0x|[0-9])|mov e[a-z]x, (0x[0-9a-f]+|[0-9]+)$|sete|setne|movzx|mov al|mov byte|ret', t):
            ss = [x for x in strings_near(k, 1)]
            print('%x  %-52s%s' % (a, t[:52], ('   ; ' + '/'.join(ss)) if ss else ''))


def main(argv):
    want = [int(x) for x in argv if x.isdigit()]
    if '--dump' in argv:
        i = argv.index('--dump')
        dump_code(int(argv[i + 1], 16), int(argv[i + 2], 16))
        return
    levels = {n: Level(n) for n in LEVEL_DIR}
    if '--cases' in argv:
        for n in want:
            dump_cases(n, levels)
        return
    if '--chain' in argv:
        for n in want:
            dump_chain(n, levels)
        return
    rows = analyse(levels)
    out = []
    for r in rows:
        if want and r['level'] not in want:
            continue
        lv = levels.get(r['level']) or levels[106]
        sm = summarise(r, lv)
        r['summary'] = sm
        out.append(r)
        tot_b = sum(v for _, v in sm['before']); tot_a = sum(v for _, v in sm['after'])
        where = ('class %s icon %s (%s)' % (r.get('class'), r['group'][0], r.get('chain'))) if r.get('group') else ('range %08x-%08x' % (r.get('lo', 0), r.get('hi', 0)))
        print('%08x %-5s L%s %-26s idx=%s flags=%s  %s%s' % (
            r['addr'], r['kind'], r['level'], r['name'], r['args'][1] if len(r['args']) > 1 else '?',
            r['args'][2] if len(r['args']) > 2 else '?', where, ('  ' + r['note']) if r.get('note') else ''))
        for s in r['steps']:
            if s['kind'] not in ('ACTION', 'ICON', 'REPAIR', 'OBJ2', 'FIRE5', 'FIRE4', 'GOTO', 'GOTOENTER', 'ENTER', 'LEAVE', 'SWITCH'):
                continue
            desc = '%s.%s' % (s.get('obj'), s.get('act')) if s['kind'] == 'ACTION' else (s.get('obj') or s.get('args'))
            print('      %s case %-3s %-9s %s' % ('*' if s.get('fire') else ' ', s.get('case', '-'), s['kind'], desc))
        for label, v in sm['before']:
            print('      before %-40s %s' % (label, '%.3f' % v if v else '-'))
        if sm['own']:
            print('      own    %-40s %s' % (sm['own'][0], '%.3f' % sm['own'][1] if sm['own'][1] else '?'))
        for label, v in sm['after']:
            print('      after  %-40s %s' % (label, '%.3f' % v if v else '-'))
        for label, v in sm['fixes']:
            print('      fix    %-40s %.3f' % (label, v))
        if sm['unknown']:
            print('      UNKNOWN %s' % ', '.join(sm['unknown']))
        print('      sums: before %.3f  own %s  after %.3f  fix %.3f' % (
            tot_b, ('%.3f' % sm['own'][1]) if sm['own'] and sm['own'][1] else '-', tot_a, sum(v for _, v in sm['fixes'])))
    if '--json' in argv:
        p = argv[argv.index('--json') + 1]
        json.dump(out, open(p, 'w'), indent=1, default=str)


if __name__ == '__main__':
    main(sys.argv[1:])
