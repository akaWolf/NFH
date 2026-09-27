"""The neighbour's routine order of every Season 1 level, read from the PC
game.exe rather than from a video.

Each level is a compiled class whose run method is a switch over the step
index ([this+0xc]); every case ends in a yield, fcn.0045c600 /
fcn.004706a0 / fcn.0045e640 (next, current, resume-after-interruption),
so the walk is the chain of `next` values from case 0. The chain is
simulated over the radare2 listing of game.exe: string-compare, IFVARIANT
(fcn.0047a130) and class-local helpers are taken as false (no trick has
fired), the engine's waits as true, class byte fields as their current
value (0 after the constructor, set along the walk), OBJ3 — isObjectPresent
(fcn.00479ff0: the object looked up and its flag 0x20 tested, "isObjectPresent
: Object not found") — as the object's presence along the lap: the level's
level.xml places the objects, each SWITCH (fcn.00451de0, the new object and
the old) swaps one for the other (113's valve: bas/valve_on placed, case 2
switches it off, case 6 on again; 111's board: case 8 puts the clothes on
it, case 16 irons them) — and a case that returns without yielding is a
poll whose condition is assumed to flip. The stations are the ICON names of the cases, else the object
walked to or acted on. The switch tables are read from the binary, the
class is matched to a level by the object names it uses.

Inputs: the radare2 text listing of game.exe (default
~/nfh-bench/pcref/r2/nfh1_game_text.txt, made with
`r2 -q -e scr.color=0 -c 'aaa; pD 0xdb000 @ 0x401000' game.exe`), the
string map tools/pcref/exe/nfh1_globals.json, the binary at
~/nfh-bench/pcref/pc/nfh1/bin/game.exe (canon.py's tree).

    python3 tools/pcref/routine_order.py            # the laps beside the mobile routines
    EDGES=all python3 tools/pcref/routine_order.py  # every branch of every case
    python3 tools/pcref/routine_order.py --dump <switch addr> <case>...   # a case's code

Results (2026-09-16): the laps equal the mobile routines on all fourteen
levels; the stations off the natural lap are conditional — 102's toilet on
the laxative flag, 103's first aid on the mailbox trap, 105's toilet on the
flower, 106's toilet and towel, 114's phono chain on the record playing.
"""
import re, json, bisect, struct, os, sys, collections, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from tools.pcref import canon
X = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
DUMP = os.environ.get('NFH1_R2', os.path.expanduser('~/nfh-bench/pcref/r2/nfh1_game_text.txt'))
if '--r2' in sys.argv:
    i = sys.argv.index('--r2'); DUMP = sys.argv[i + 1]; del sys.argv[i:i + 2]
exe = open(os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/bin/game.exe'), 'rb').read()
G = json.load(open(os.path.join(HERE, 'exe', 'nfh1_globals.json'))); L = open(DUMP).read().split('\n')
addr = {}
for i, l in enumerate(L):
    m = re.match(r'\s*(0x[0-9a-f]{8}) ', l)
    if m: addr[int(m.group(1), 16)] = i
keys = sorted(addr)
def at(a):
    i = bisect.bisect_left(keys, a)
    return addr[keys[min(i, len(keys) - 1)]]
def ins(k):
    t = L[k].strip(); m = re.match(r'(0x[0-9a-f]{8})\s+[0-9a-f.]+\s+(.*)', t)
    return (int(m.group(1), 16), m.group(2)) if m else (None, None)
LABEL = {'fcn.00437f70': 'ICON', 'fcn.00479da0': 'GOTO', 'fcn.0044ac80': 'GOTO', 'fcn.00479f10': 'GOTOENTER', 'fcn.00479e30': 'GOTOENTER', 'fcn.00473e20': 'ENTER', 'fcn.00473ea0': 'LEAVE', 'fcn.0047c3b0': 'TRICK', 'fcn.00457610': 'STATE', 'fcn.00451e80': 'STATE', 'fcn.00448bf0': 'LOOKUP', 'fcn.00446020': 'INV', 'fcn.00477f60': 'ACTION', 'fcn.00479c70': 'ACTION', 'fcn.00479ba0': 'ACTION', 'fcn.0047a130': 'IFVARIANT', 'fcn.00479ff0': 'OBJ3', 'fcn.00451de0': 'SWITCH', 'fcn.004764b0': 'GOTO2', 'fcn.0047a960': 'GOTO', 'fcn.0047a4a0': 'GOTO'}
# the instant steps a case's list carries (tools/pcref/lap_model.py counts a
# tick each): the list itself (fcn.00476770 — the case pushes it with the
# run-now flag 0, its first update only pushes its first element, the
# sequence update 0x476530), a message step (fcn.0047c640 over a message:
# SWITCH, OBJ1, the switch back after a take …; update 0x47c550 done on its
# first call) and a StopMsg (fcn.0047c6c0, the same wrapper) — they carry no
# arguments of their own and leave the call's argument strings to the next
# labelled call
LABEL.update({'fcn.00476770': 'SUBSEQ', 'fcn.0047c640': 'MSG', 'fcn.0047c6c0': 'STOPMSG'})
INSTANT = ('SUBSEQ', 'MSG', 'STOPMSG')
# fcn.0047a960 and fcn.0047a4a0 are GoTo builders too (their asserts: CreateGoToObjectJob,
# CreateGoToObjXJob — the object in the actor's room): 114's case 7 walks to lir/tabacbox
PRED = ('fcn.0047a130', 'fcn.00479ff0', 'fcn.0047c290', 'fcn.0047c6c0', 'fcn.00413780')
ALLPRED = os.environ.get('ALLPRED') == '1'
NATFALSE_FN = {'fcn.0047a130', 'fcn.00479ff0', 'fcn.0047c290', 'fcn.00413780', 'fcn.0047ac20', 'fcn.0047ad20', 'fcn.0047a0b0', 'fcn.00422c40'}
# a level class's own presence test: Level_Bath::isBathFilled (fcn.0046bc90, its
# assert names it) looks toi/tub up and answers its flag 0x20 clear — the full tub
# case 8's SWITCH shows: true once the walk's presence holds toi/tub
PRESENCE_FN = {'fcn.0046bc90': 'toi/tub'}
NATTRUE = {'fcn.0047c640', 'fcn.0047c6c0', 'fcn.004766e0', 'fcn.00476770', 'fcn.00444d30', 'fcn.0044bb80', 'fcn.0047c320', 'fcn.0047ae70'}
def strings_before(k, n=8):
    out = []
    for j in range(max(0, k - n), k):
        for m in re.finditer(r'0x(5[01][0-9a-f]{4})', L[j]):
            nm = G.get('0x' + m.group(1))
            if nm: out.append(str(nm))
    return out
def line_strings(k):
    """the string globals line k refers to"""
    return [str(G['0x' + m.group(1)]) for m in re.finditer(r'0x(5[01][0-9a-f]{4})', L[k]) if G.get('0x' + m.group(1))]
def strings_since_call(k, n=60):
    """the string globals loaded since the previous labelled call in the listing's
    order — the arguments of the call at k where no branch lies between (the case
    walk reads them off its own path: simulate's `pstr`)"""
    j0 = max(0, k - n)
    for j in range(k - 1, j0, -1):
        tt = ins(j)[1] or ''
        if (mm := re.match(r'call (fcn\.[0-9a-f]+)', tt)) and (mm.group(1) in LABEL or re.search(r'fcn\.(0045c600|004706a0|0045e640)', tt)): j0 = j; break
    out = []
    for j in range(j0, k):
        for m in re.finditer(r'0x(5[01][0-9a-f]{4})', L[j]):
            nm = G.get('0x' + m.group(1))
            if nm: out.append(str(nm))
    return out
# 1. run functions by shape: a switch whose cases hold yields
switches = []
for k in range(len(L)):
    a, t = ins(k)
    if t and (m := re.search(r'jmp dword \[e[a-z]x\*4 \+ (0x[0-9a-f]+)\]', t)) and 0x435000 <= a < 0x480000:
        bound = None
        for j in range(k - 1, k - 12, -1):
            aa, tt = ins(j)
            if tt and (mm := re.search(r'cmp e[a-z]x, (0x[0-9a-f]+|[0-9]+)', tt)): bound = int(mm.group(1), 0); break
        if bound and bound >= 4: switches.append((a, int(m.group(1), 16), bound))
levels_objs = {}
for f in glob.glob(X + '/level_*/objects.xml'):
    levels_objs[os.path.basename(os.path.dirname(f))] = set(re.findall(r'<object name="([^"]+)"', canon.read(f)))
def run_level(sw):
    a_sw, tb, n = sw
    if not (0x401000 <= tb - 0x400000 + 0x400000 < 0x4dc000): return None
    starts = list(struct.unpack_from('<%dI' % (n + 1), exe, tb - 0x400000))
    if any(not (0x401000 <= x < 0x4dc000) for x in starts): return None
    lo = min(starts); hi = max(starts) + 0x400
    case_of = {}
    for i, s in enumerate(starts): case_of.setdefault(s, []).append(i)
    tails = set()
    for k in range(at(lo), at(hi)):
        a, t = ins(k)
        if t and re.search(r'call fcn\.(0045c600|004706a0|0045e640)', t):
            tails.add(a)
            for j in range(k - 1, k - 3, -1):
                aa, tt = ins(j)
                if tt and re.match(r'mov ecx, e', tt): tails.add(aa)
            hi = max(hi, a + 0x40)
    if not tails: return None
    prologue = {}
    for j in range(at(a_sw) - 60, at(a_sw)):
        aa, tt = ins(j)
        if tt and (mm := re.match(r'mov (e[a-z]x|e[sd]i|ebp), (0x[0-9a-f]+|[0-9]+)$', tt)): prologue[mm.group(1)] = int(mm.group(2), 0)
    def resolve(val, regs):
        if re.match(r'^(0x[0-9a-f]+|[0-9]+)$', val): return int(val, 0)
        if val in regs: return regs[val]
        if val in prologue: return prologue[val]
        return val
    def yield_next(k, regs):
        for j in range(k - 1, k - 8, -1):
            aa, tt = ins(j)
            if tt and tt.startswith('push '): return resolve(tt[5:], regs)
        return '?'
    TRACE = os.environ.get('TRACE')
    def simulate(start_a, objflags=None, flip=False, depth=0, present=None):
        objflags = {} if objflags is None else objflags
        labels = []; k = at(start_a); seen = set(); pred = False; regs = {}; lastcall = None; flags = {}; inverted = False
        trace = TRACE and int(TRACE, 16) == start_a
        # the string globals on the path since the last labelled call: a call's
        # arguments (the listing's order would cross into the branch not taken —
        # 109's case 11 takes its teeth, where the tabasco branch above it spits fire)
        pstr = []
        for _ in range(600):
            if k in seen: return labels, 'loop'
            seen.add(k); a, t = ins(k)
            if t is None: k += 1; continue
            m = re.match(r'call (fcn\.[0-9a-f]+)', t)
            if not (m and m.group(1) in LABEL):
                pstr += line_strings(k)
            if trace and re.search(r'call|j[a-z]+ 0x|push|test', t): print('      trace %x %s pred=%s' % (a, t[:50], pred))
            if (mm := re.match(r'mov (e[a-z]x|e[sd]i|ebp), (0x[0-9a-f]+|[0-9]+)$', t)): regs[mm.group(1)] = int(mm.group(2), 0)
            elif (mm := re.match(r'xor (e[a-z]x|e[sd]i|ebp), \1$', t)): regs[mm.group(1)] = 0
            elif (mm := re.match(r'(mov|lea|pop) (e[a-z]x|e[sd]i|ebp),', t)): regs.pop(mm.group(2), None)
            if a in tails or re.search(r'call fcn\.(0045c600|004706a0|0045e640)', t): return labels, yield_next(k, regs)
            if t.startswith('ret'): return labels, 'ret'
            m = re.match(r'call (fcn\.[0-9a-f]+)', t)
            if m:
                fn = m.group(1)
                if fn in LABEL: labels.append((LABEL[fn], [] if LABEL[fn] in INSTANT else pstr[-4:]))
                elif depth < 1 and lo - 0x2000 <= int(fn[4:], 16) < hi + 0x2000 and fn not in NATTRUE and fn not in NATFALSE_FN and not re.search(r'fcn\.(0045c600|004706a0|0045e640|0047f740)', fn):
                    # a helper of the class (the sofa's sit/sit_remo picker, fcn.004707e0): its own
                    # GoTo/DoAction calls belong to the case that calls it
                    labels.extend(simulate(int(fn[4:], 16), objflags, False, depth + 1, present)[0])
                pred = False; lastcall = fn
                if present is not None and fn in PRESENCE_FN:
                    lastcall = ('flag', 'true' if PRESENCE_FN[fn] in present else 'false')
                if present is not None and fn in ('fcn.00479ff0', 'fcn.00451de0'):
                    ss = [x for x in pstr if '/' in x]
                    if fn == 'fcn.00479ff0' and ss:
                        lastcall = ('flag', 'true' if ss[-1] in present else 'false')
                    elif fn == 'fcn.00451de0' and len(ss) >= 2:
                        present.discard(ss[-1]); present.add(ss[-2])
                if fn in LABEL and LABEL[fn] != 'IFVARIANT' and LABEL[fn] not in INSTANT:
                    # an IFVARIANT's pick is the next call's object (107's ENTER of
                    # the stool or its pinned twin)
                    pstr = []
                k += 1; continue
            if t == 'test al, al':
                if lastcall is None: pred = 'false'
                elif isinstance(lastcall, tuple): pred = lastcall[1]
                elif lastcall in NATFALSE_FN: pred = 'false'
                elif 0x44c000 <= int(lastcall[4:], 16) < 0x478000: pred = 'false'
                else: pred = 'true'
                if flip and not (isinstance(lastcall, str) and (lastcall in NATFALSE_FN or 0x44c000 <= int(lastcall[4:], 16) < 0x478000)):
                    pred = 'false' if pred == 'true' else 'true'
                k += 1; continue
            m = re.match(r'jmp (0x[0-9a-f]+)', t)
            if m:
                tgt = int(m.group(1), 16)
                if tgt in tails: return labels, yield_next(k, regs)
                k = at(tgt); continue
            m = re.match(r'j(e|ne|z|nz) (0x[0-9a-f]+)', t)
            if m:
                cc, tgt = m.group(1), int(m.group(2), 16)
                if pred:
                    nat = pred; pred = False; lastcall = False
                    jump_if_zero = cc in ('e', 'z')
                    take = (jump_if_zero and nat == 'false') or ((not jump_if_zero) and nat == 'true')
                    if take: k = at(tgt); continue
                    k += 1; continue
                k += 1; continue
            if (mm := re.match(r'set(e|ne) byte \[esp \+ (0x[0-9a-f]+)\]', t)): flags[mm.group(2)] = 'true' if mm.group(1) == 'e' else 'false'
            if t == 'sbb al, al': inverted = True
            if (mm := re.match(r'mov byte \[esp \+ (0x[0-9a-f]+)\], al', t)):
                if inverted: flags[mm.group(1)] = 'false'; inverted = False
                elif isinstance(lastcall, str) and lastcall.startswith('fcn.'):
                    flags[mm.group(1)] = 'false' if (lastcall in NATFALSE_FN or 0x44c000 <= int(lastcall[4:], 16) < 0x478000) else 'true'
                elif isinstance(lastcall, tuple): flags[mm.group(1)] = lastcall[1]
            if (mm := re.match(r'mov al, byte \[esp \+ (0x[0-9a-f]+)\]', t)): lastcall = ('flag', flags.get(mm.group(1), 'false'))
            elif (mm := re.match(r'mov al, byte \[e[ds]i \+ (0x[0-9a-f]+)\]', t)): lastcall = ('flag', 'true' if objflags.get(mm.group(1), 0) else 'false')
            elif t.startswith('mov al,'): lastcall = ('flag', 'false')
            if (mm := re.match(r'mov byte \[e[ds]i \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|[0-9]+)$', t)): objflags[mm.group(1)] = int(mm.group(2), 0)
            if (mm := re.match(r'cmp byte \[e[ds]i \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|[0-9]+)$', t)):
                pred = 'true' if objflags.get(mm.group(1), 0) != int(mm.group(2), 0) else 'false'; k += 1; continue
            if re.match(r'(cmp |xor eax|movzx eax)', t): lastcall = None
            k += 1
        return labels, 'toolong'
    if DUMPCASE and DUMPCASE[0] == a_sw:
        for c in DUMPCASE[1]:
            st = starts[c]; nxt_starts = [x for x in sorted(set(starts)) if x > st]; en = nxt_starts[0] if nxt_starts else st + 0x300
            print('  ---- case %d at %x-%x' % (c, st, en))
            for k in range(at(st), at(en)):
                aa, tt = ins(k)
                if tt and re.search(r'call fcn|cmp|test|j[a-z]+ 0x|push|mov e[a-z]x, (0x[0-9a-f]+|[0-9]+)$|xor e[a-z]x, e[a-z]x|sete|setne|movzx|mov e[a-z]x, dword \[e[a-z]+ \+ 0x[0-9a-f]+\]', tt):
                    ss = strings_before(k, 1)
                    print('     %x  %s%s' % (aa, tt[:60], ('   ; ' + '/'.join(ss)) if ss else ''))
    def explore(start_a, forced):
        # forced: list of branch decisions to apply in order (True = take the jump); returns (labels, nxt, decisions)
        labels = []; k = at(start_a); seen = set(); pred = False; regs = {}; lastcall = None; decisions = []; di = 0; flags = {}; inverted = False
        for _ in range(600):
            if k in seen: return labels, 'loop', decisions
            seen.add(k); a, t = ins(k)
            if t is None: k += 1; continue
            if (mm := re.match(r'mov (e[a-z]x|e[sd]i|ebp), (0x[0-9a-f]+|[0-9]+)$', t)): regs[mm.group(1)] = int(mm.group(2), 0)
            elif (mm := re.match(r'xor (e[a-z]x|e[sd]i|ebp), \1$', t)): regs[mm.group(1)] = 0
            elif (mm := re.match(r'(mov|lea|pop) (e[a-z]x|e[sd]i|ebp),', t)): regs.pop(mm.group(2), None)
            if a in tails: return labels, yield_next(k, regs), decisions
            if t.startswith('ret'): return labels, 'ret', decisions
            m = re.match(r'call (fcn\.[0-9a-f]+)', t)
            if m:
                fn = m.group(1)
                if fn in LABEL: labels.append((LABEL[fn], strings_before(k)[-2:]))
                pred = False; lastcall = (fn, strings_before(k, 10)[-2:]); k += 1; continue
            if t == 'test al, al': pred = lastcall or ('flag', []); k += 1; continue
            m = re.match(r'jmp (0x[0-9a-f]+)', t)
            if m:
                tgt = int(m.group(1), 16)
                if tgt in tails: return labels, yield_next(k, regs), decisions
                k = at(tgt); continue
            m = re.match(r'j(e|ne|z|nz|l|g|le|ge|a|b|ae|be) (0x[0-9a-f]+)', t)
            if m:
                cc, tgt = m.group(1), int(m.group(2), 16)
                if pred:
                    fn, ss = pred; pred = False; lastcall = None
                    take = forced[di] if di < len(forced) else False
                    val = (cc in ('e', 'z')) != take
                    decisions.append((fn, '/'.join(ss), val)); di += 1
                    if take: k = at(tgt); continue
                    k += 1; continue
                prev = ''
                for j in range(k - 1, k - 6, -1):
                    tt = ins(j)[1] or ''
                    if tt.startswith(('cmp', 'test')): prev = tt; break
                take = forced[di] if di < len(forced) else False
                decisions.append(('cmp', (prev[:34] + ' j' + cc), take)); di += 1
                if take: k = at(tgt); continue
                k += 1; continue
            if (mm := re.match(r'set(e|ne) byte \[esp \+ (0x[0-9a-f]+)\]', t)): flags[mm.group(2)] = 'true' if mm.group(1) == 'e' else 'false'
            if t == 'sbb al, al': inverted = True
            if (mm := re.match(r'mov byte \[esp \+ (0x[0-9a-f]+)\], al', t)):
                if inverted: flags[mm.group(1)] = 'false'; inverted = False
                elif isinstance(lastcall, str) and lastcall.startswith('fcn.'):
                    flags[mm.group(1)] = 'false' if (lastcall in NATFALSE_FN or 0x44c000 <= int(lastcall[4:], 16) < 0x478000) else 'true'
                elif isinstance(lastcall, tuple): flags[mm.group(1)] = lastcall[1]
            if (mm := re.match(r'mov al, byte \[esp \+ (0x[0-9a-f]+)\]', t)): lastcall = ('flag', flags.get(mm.group(1), 'false'))
            elif t.startswith('mov al,'): lastcall = ('flag', 'false')
            if re.match(r'(cmp |xor eax|movzx eax)', t): lastcall = None
            k += 1
        return labels, 'toolong', decisions
    def all_edges(start_a, maxpaths=40):
        out = {}; frontier = [[]]
        while frontier and len(out) < maxpaths:
            forced = frontier.pop(0)
            labels, nxt, dec = explore(start_a, forced)
            key = (nxt, tuple(dec))
            if key in out: continue
            out[key] = labels
            for i in range(len(forced), len(dec)): frontier.append(forced + [False] * (i - len(forced)) + [True])
        return out
    graph = {}
    for s in sorted(case_of):
        labels, nxt = simulate(s)
        for c in case_of[s]: graph[c] = (labels, nxt)
    if os.environ.get('EDGES'):
        want = [int(x) for x in os.environ['EDGES'].split(',')] if os.environ['EDGES'] != 'all' else sorted(case_of.values())
        for s in sorted(case_of):
            c = case_of[s][0]
            if os.environ['EDGES'] != 'all' and c not in want: continue
            eds = all_edges(s)
            if len({k[0] for k in eds}) > 1 or os.environ['EDGES'] != 'all':
                print('     class %x case %d edges:' % (a_sw, c))
                for (nxt, dec), labels in eds.items():
                    print('        -> %-5s %s   labels %s' % (nxt, ' & '.join('%s(%s)=%s' % (LABEL.get(f, f[4:]), ss, 'T' if v else 'F') for f, ss, v in dec), ' '.join('%s:%s' % (k, '/'.join(v)) for k, v in labels if k in ('ICON', 'GOTO', 'GOTO2', 'ACTION'))[:80]))
    names = set()
    for c, (labels, nxt) in graph.items():
        for kind, ss in labels:
            if kind in ('GOTO', 'GOTO2', 'ACTION', 'IFVARIANT', 'SWITCH'): names.update(s for s in ss if '/' in s)
    level = max(levels_objs, key=lambda lv: len(names & levels_objs[lv])) if names else '?'
    score = len(names & levels_objs.get(level, set()))
    if score < 2:
        icons = set()
        for c, (labels, nxt) in graph.items():
            for kind, ss in labels:
                if kind == 'ICON': icons.update(ss)
        KW = {'level_peep': {'binoculars'}, 'level_sofa': {'beer'}, 'level_mail': {'cake', 'mail', 'first_aid'}, 'level_pie': {'whippedcream', 'basin', 'microwave'}, 'level_bath': {'photo_album', 'candy', 'towel', 'bath', 'milk_bottle'}}
        best = max(KW, key=lambda lv: len(icons & KW[lv]))
        if icons & KW[best]: level, score = best, len(icons & KW[best])
    seq = []; c = 0; visited = []; objflags = {}; states = set()
    lx = os.path.join(X, level, 'level.xml')
    present = set(re.findall(r'<object name="([^"]+)"', canon.read(lx))) if os.path.exists(lx) else None
    for _ in range(120):
        key = (c, tuple(sorted(objflags.items())), tuple(sorted(present or ())))
        if key in states: break
        states.add(key); visited.append(c)
        if c not in case_of.values() and c not in [ci for cs in case_of.values() for ci in cs]: break
        start = starts[c]
        before = set(present) if present is not None else None
        labels, nxt = simulate(start, objflags, present=present)
        if nxt == 'ret':
            present = before
            labels2, nxt2 = simulate(start, objflags, flip=True, present=present)
            if isinstance(nxt2, int): labels, nxt = labels2 + [('POLL', [])], nxt2
        seq.append((c, labels, nxt))
        if isinstance(nxt, int): c = nxt
        else: break
    return level, score, n + 1, graph, seq, visited
if os.environ.get('CANDS') == '1':
    hdrs = []; hdr = re.compile(r'^\s*(\d+): (fcn\.[0-9a-f]+)')
    for i, l in enumerate(L):
        h = hdr.match(l)
        if h: hdrs.append((i, h.group(2)))
    hk = [h[0] for h in hdrs]
    def fo(k): j = bisect.bisect_right(hk, k) - 1; return hdrs[j][1] if j >= 0 else None
    ys = collections.defaultdict(list)
    for k in range(len(L)):
        a, t = ins(k)
        if t and 'call fcn.0045c600' in t: ys[fo(k)].append(a)
    known = {fo(at(a)) for a, tb, n in switches}
    for f, sites in sorted(ys.items()):
        j = [h for h in hdrs if h[1] == f][0][0]; hi = hdrs[hdrs.index([h for h in hdrs if h[1] == f][0]) + 1][0]
        icons = []
        for k in range(j, hi):
            a, t = ins(k)
            if t and 'call fcn.00437f70' in t: icons += strings_before(k)[-1:]
        print('  yield fn %s: %d yield sites, known=%s, icons %s' % (f, len(sites), f in known, sorted(set(icons))[:10]))
DUMPCASE = None
if len(sys.argv) > 2 and sys.argv[1] == '--dump':
    DUMPCASE = (int(sys.argv[2], 16), [int(x) for x in sys.argv[3:]])
results = {}
for sw in switches:
    r = run_level(sw)
    if r: results.setdefault(r[0], []).append((sw, r))
for lv, rs in results.items():
    for sw, (level, score, ncases, graph, seq, visited) in rs:
        icons = sorted({x for c, (labels, nxt) in graph.items() for kind, ss in labels if kind == 'ICON' for x in ss})
        if os.environ.get('CLASSES'): print('  class %x -> %s (score %d, %d cases) icons %s' % (sw[0], lv, score, ncases, icons[:10]))
order = ['level_peep','level_sofa','level_mail','level_pie','level_piano','level_bath','level_art','level_suntan','level_pig','level_barbecue','level_laundry','level_fitness','level_DIY','level_hunter']
nums = {lv: 101 + i for i, lv in enumerate(order)}
for lv in order:
    rs = results.get(lv, [])
    if not rs: print('==', lv, ': no run function found'); continue
    sw, (level, score, ncases, graph, seq, visited) = max(rs, key=lambda x: x[1][1])
    toks = []
    for c, labels, nxt in seq:
        names = [ '/'.join(v) for k, v in labels if k in ('ICON', 'GOTO', 'GOTO2')]
        names = [n for n in names if n]
        toks.append('%d%s' % (c, ('(' + ','.join(names) + ')') if names else ''))
    print('== %s (%d) class %x, %d cases: %s | last next: %s' % (lv, nums[lv], sw[0], ncases, ' > '.join(toks), seq[-1][2]))
    m = canon.mobile_level(nums[lv])
    print('   mobile: %s' % ' > '.join(r[0] for r in m.get('routine', [])))
    if not os.environ.get('WALK_ONLY'):
        st = []; laps = []; seen_c = set()
        for c, labels, nxt in seq:
            if c in seen_c and st: laps.append(st); st = []; seen_c = set()
            seen_c.add(c)
            name = None
            for k, v in labels:
                if k == 'ICON' and v and v[-1] and '/' not in v[-1]: name = v[-1]; break
            if name is None:
                for k, v in labels:
                    if k in ('GOTO', 'GOTO2', 'ACTION'):
                        objs = [x for x in v if '/' in x]
                        if objs: name = objs[-1].split('/')[-1]; break
            if name and (not st or st[-1] != name): st.append(name)
        laps.append(st)
        for i, lp in enumerate(laps[:3]):
            print('   PC lap %d by code: %s' % (i + 1, ' > '.join(lp)))
        if os.environ.get('LAPS'):
            # the ordered ICON/GOTO/ACTION tokens of each lap, for tools/pcref/lap_model.py
            # WRAP marks where the last case's `next` re-enters lap 1 — a walk
            # of one lap, no case repeated: the steady lap runs from there
            # (108's toothbrush, cases 0 and 2, is the first lap's only)
            toks = []; seen_c = set(); n = 0
            wrap = seq[-1][2] if len({c for c, _, _ in seq}) == len(seq) else None
            for c, labels, nxt in seq:
                if c in seen_c and toks: n += 1; print('LAP %d %d: %s' % (nums[lv], n, ' | '.join(toks))); toks = []; seen_c = set()
                seen_c.add(c)
                if n == 0 and c == wrap and c != seq[0][0]:
                    toks.append('WRAP')
                toks += ['%s %s' % (k, ' + '.join(v)) for k, v in labels if k in ('ICON', 'GOTO', 'GOTOENTER', 'GOTO2', 'ENTER', 'LEAVE', 'ACTION', 'TRICK') + INSTANT]
            if toks: n += 1; print('LAP %d %d: %s' % (nums[lv], n, ' | '.join(toks)))
