"""The neighbour's routine of every Season 2 level, read from GameLogic.dll.

A Season 2 level script is a chain of step functions: each step walks
(fcn.1000e3e0), acts (fcn.10002cd5), shows an icon (fcn.100422a5), then
stores the next step's address in the step object (`mov [obj+8], fn`,
directly or through a register or a local helper) and returns. The walk
follows that chain from the level's main routine function with no trick
fired (IsVariant fcn.1000fb6e and IsTricked fcn.1000ec67 false, a walk or
an action not interrupted, byte flags zero) and closes when a step
repeats. Steps that wait for an event re-arm themselves and hand the
continuation to a watch-table callback; those chains stop here (`[end]`),
and a step that loops on itself is re-run with its polls flipped.

Inputs: the radare2 listing of GameLogic.dll (default
~/nfh-bench/pcref/r2/nfh2_gamelogic_text.txt), the string map
tools/pcref/exe/nfh2_gamelogic_globals.json, the level folders of
canon.py. `TAILS=1` prints every branch of the step a chain stops at.

Coverage (2026-09-16): the lap closes on 201, 203, 205, 206, 208, 211,
213 (and 210 up to a self-arming step); 202, 204, 207, 209, 212, 214 stop
at an event-driven step.
"""
import re, json, bisect, collections, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from tools.pcref import canon
DUMP = os.environ.get('NFH2_R2', os.path.expanduser('~/nfh-bench/pcref/r2/nfh2_gamelogic_text.txt'))
G2 = json.load(open(os.path.join(HERE, 'exe', 'nfh2_gamelogic_globals.json'))); L2 = open(DUMP).read().split('\n'); hdrs = []; addr = {}
hdr = re.compile(r'^\s*(\d+): (fcn\.[0-9a-f]+)')
for i, l in enumerate(L2):
    m = re.match(r'\s*(0x[0-9a-f]{8}) ', l)
    if m: addr[int(m.group(1), 16)] = i
    h = hdr.match(l)
    if h: hdrs.append((i, h.group(2)))
keys = sorted(addr); hk = [h[0] for h in hdrs]
def at(a): return addr[keys[min(bisect.bisect_left(keys, a), len(keys) - 1)]]
def ins(k):
    t = L2[k].strip(); m = re.match(r'(0x[0-9a-f]{8})\s+[0-9a-f.]+\s+(.*)', t)
    return (int(m.group(1), 16), m.group(2)) if m else (None, None)
NATFALSE = {'fcn.1000fb6e', 'fcn.1000ec67', 'fcn.1000e3e0', 'fcn.10002cd5'}
ACTORS = {'woody', 'neighbor', 'olga', 'mother', 'kid', 'fifi', 'use_object', 'combine', 'true', 'false'}
def objname(k, n=40):
    for j in range(k - 1, k - n, -1):
        for m in re.finditer(r'0x100[a-f][0-9a-f]{4}', L2[j]):
            nm = G2.get(m.group(0))
            if nm and str(nm) not in ACTORS and not str(nm).endswith('.wav') and not str(nm).endswith('.mp3'): return str(nm)
    return '?'
def run_step(start, maxsteps=1500, flip=False):
    """one step function from its body start: (labels, next step address or None)"""
    k = at(start); seen = set(); seq = []; lastcall = None; pred = None; nxt = None; regs = {}; lastlocal = None
    for _ in range(maxsteps):
        if k in seen: return seq, nxt
        seen.add(k); a, t = ins(k)
        if t is None: k += 1; continue
        if t.startswith('ret'):
            if nxt is None and lastlocal:
                # a local helper may set the next step
                h0 = [h for h in hdrs if h[1] == lastlocal]
                if h0:
                    i0 = h0[0][0]; i1 = hdrs[hdrs.index(h0[0]) + 1][0]
                    for kk in range(i0, i1):
                        mm = re.match(r'mov dword \[e[a-z]+ \+ 8\], (0x100[0-9a-f]{5})$', ins(kk)[1] or '')
                        if mm: nxt = int(mm.group(1), 16); break
            return seq, nxt
        m = re.match(r'mov dword \[e[a-z]+ \+ 8\], (0x100[0-9a-f]{5})$', t)
        if m: nxt = int(m.group(1), 16)
        m = re.match(r'mov (e[a-z]x), (0x100[0-9a-f]{5})$', t)
        if m: regs[m.group(1)] = int(m.group(2), 16)
        m = re.match(r'mov dword \[e[a-z]+ \+ 8\], (e[a-z]x)$', t)
        if m and m.group(1) in regs: nxt = regs[m.group(1)]
        if (m := re.match(r'cmp byte \[e[a-z]+ \+ 0x[0-9a-f]+\], (bl|0)$', t)): pred = 'true' if flip else 'false'; k += 1; continue
        if 'call fcn.1000e7f2' in t:
            pm = re.search(r'push (0x100[0-9a-f]{5})$', ins(k - 1)[1] or '')
            if pm: nxt = int(pm.group(1), 16)
        m = re.match(r'call (fcn\.[0-9a-f]+)', t)
        if m:
            fn = m.group(1)
            if fn == 'fcn.1000e3e0': seq.append('GO:' + objname(k))
            elif fn == 'fcn.10002cd5': seq.append('DO:' + objname(k))
            elif fn == 'fcn.100422a5': seq.append('IC:' + objname(k, 10))
            lastcall = fn; pred = None
            if 0x10013000 <= int(fn[4:], 16) < 0x1003d000: lastlocal = fn
            k += 1; continue
        if t == 'test al, al' or re.match(r'cmp al, (bl|0)$', t):
            pred = 'false' if lastcall in NATFALSE else 'true'
            if flip and lastcall not in NATFALSE: pred = 'false' if pred == 'true' else 'true'
            k += 1; continue
        m = re.match(r'jmp (0x[0-9a-f]+)', t)
        if m: k = at(int(m.group(1), 16)); continue
        m = re.match(r'j(e|ne|z|nz) (0x[0-9a-f]+)', t)
        if m:
            if pred:
                jz = m.group(1) in ('e', 'z'); take = (jz and pred == 'false') or ((not jz) and pred == 'true'); pred = None
                if take: k = at(int(m.group(2), 16)); continue
            k += 1; continue
        if re.match(r'(cmp |xor eax|mov al,|movzx eax|set)', t): lastcall = None
        k += 1
    return seq, nxt
def explore_step(start, forced, maxsteps=1500):
    k = at(start); seen = set(); seq = []; lastcall = None; pred = None; nxt = None; regs = {}; dec = []; di = 0
    for _ in range(maxsteps):
        if k in seen: return seq, nxt, dec
        seen.add(k); a, t = ins(k)
        if t is None: k += 1; continue
        if t.startswith('ret'): return seq, nxt, dec
        m = re.match(r'mov dword \[e[a-z]+ \+ 8\], (0x100[0-9a-f]{5})$', t)
        if m: nxt = int(m.group(1), 16)
        m = re.match(r'mov (e[a-z]x), (0x100[0-9a-f]{5})$', t)
        if m: regs[m.group(1)] = int(m.group(2), 16)
        m = re.match(r'mov dword \[e[a-z]+ \+ 8\], (e[a-z]x)$', t)
        if m and m.group(1) in regs: nxt = regs[m.group(1)]
        m = re.match(r'call (fcn\.[0-9a-f]+)', t)
        if m:
            fn = m.group(1)
            if fn == 'fcn.1000e3e0': seq.append('GO:' + objname(k))
            elif fn == 'fcn.10002cd5': seq.append('DO:' + objname(k))
            lastcall = fn; pred = None; k += 1; continue
        if t == 'test al, al' or re.match(r'cmp al, (bl|0)$', t): pred = (lastcall or 'flag'); k += 1; continue
        if re.match(r'cmp byte \[e[a-z]+ \+ 0x[0-9a-f]+\], (bl|0)$', t): pred = ('byte', t[9:30]); k += 1; continue
        m = re.match(r'jmp (0x[0-9a-f]+)', t)
        if m: k = at(int(m.group(1), 16)); continue
        m = re.match(r'j(e|ne|z|nz|l|g|le|ge|a|b|ae|be) (0x[0-9a-f]+)', t)
        if m:
            take = forced[di] if di < len(forced) else False
            label = pred if pred else ('cmp', (ins(k - 1)[1] or '')[:24])
            dec.append((label, m.group(1), take)); di += 1; pred = None
            if take: k = at(int(m.group(2), 16)); continue
            k += 1; continue
        if re.match(r'(cmp |xor eax|mov al,|movzx eax|set)', t): lastcall = None
        k += 1
    return seq, nxt, dec
def all_nexts(start, maxpaths=40):
    out = {}; frontier = [[]]
    while frontier and len(out) < maxpaths:
        forced = frontier.pop(0)
        seq, nxt, dec = explore_step(start, forced)
        key = (nxt, tuple(dec))
        if key in out: continue
        out[key] = seq
        for i2 in range(len(forced), len(dec)): frontier.append(forced + [False] * (i2 - len(forced)) + [True])
    return out
def walk(start, maxsteps=200):
    seq = []; steps = {}; cur = start; walk.visited = []
    for _ in range(maxsteps):
        if cur in steps: return seq, ('loop', steps[cur])
        steps[cur] = len(seq); walk.visited.append(cur)
        labels, nxt = run_step(cur)
        if nxt == cur:
            l2, n2 = run_step(cur, flip=True)
            if n2 is not None and n2 != cur: labels, nxt = l2 + ['POLL'], n2
        seq += labels
        if nxt is None: return seq, ('end', None)
        cur = nxt
    return seq, ('toolong', None)
import glob
X2 = os.path.expanduser('~/nfh-bench/pcref/pc/nfh2/x')
# every function's GoTo/DoAction object names
fn_names = {}
for j, (i0, name) in enumerate(hdrs):
    i1 = hdrs[j + 1][0] if j + 1 < len(hdrs) else len(L2)
    names = []
    for k in range(i0, i1):
        if 'call fcn.1000e3e0' in L2[k] or 'call fcn.10002cd5' in L2[k]:
            names.append(objname(k))
    if names: fn_names[name] = names
for n in range(201, 215):
    pc = canon.pc_level(n); folder = pc.get('folder')
    objs = set(x.replace('/', '_') for x in re.findall(r'<object name="([^"]+)"', canon.read(X2 + '/' + folder + '/objects.xml')))
    scored = sorted(((sum(1 for x in v if x in objs), name) for name, v in fn_names.items()), reverse=True)
    best = scored[0]
    k0 = [h for h in hdrs if h[1] == best[1]][0][0]
    while 'call fcn.1000e3e0' not in L2[k0] and 'call fcn.10002cd5' not in L2[k0]: k0 += 1
    while k0 > 0 and 'call fcn.10059e30' not in L2[k0]: k0 -= 1
    start = ins(k0)[0] - 5
    seq, (end, loop_at) = walk(start)
    if end == 'loop' and loop_at is not None: intro, lap = seq[:loop_at], seq[loop_at:]
    else: intro, lap = seq, []
    fmt = lambda q: ' > '.join(x.split(':', 1)[1].split('_', 1)[-1] for x in q if x.startswith(('GO:', 'DO:')))
    print('%d %-6s %s (%d names in level): intro: %s' % (n, folder, best[1], best[0], fmt(intro)[:150]))
    print('           lap  : %s [%s]' % (fmt(lap)[:210], end))
    m = canon.mobile_level(n)
    print('           mobile: %s' % ' > '.join(str(r[0]) for r in m.get('routine', []))[:170])
    if end == 'end' and os.environ.get('TAILS'):
        last = walk.visited[-1]; k = at(last); lines = []
        for kk in range(k, k + 600):
            a, t = ins(kk)
            if t is None: continue
            lines.append('%x %s' % (a, t[:58]))
            if t.startswith('ret'): break
        print('           last step %x nexts:' % last)
        for (nx, dec), sq in all_nexts(last).items():
            print('              -> %s  %s  %s' % ('%x' % nx if nx else None, ' & '.join('%s j%s=%s' % (str(l)[:26], c, 'T' if tk else 'F') for l, c, tk in dec)[:150], ' '.join(x.split(':',1)[1].split('_',1)[-1] for x in sq if x.startswith(('GO:','DO:')))[:60]))
