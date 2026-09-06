"""the neighbour's NATURAL lap (no trick fired) on the PC against the port's:
the PC first-lap activity spans off the HUD bubble (docs/PC_LAPS_DETAIL.md)
aligned by activity name with an idle run of the port — the harness driving
a plan that only waits (Woody dodging, nothing armed), so no angry sequence
stretches an action. The plan runs with tricks (docs/PC_LAPS.md's first
table) had both sides stretched by reactions, which is what made the port
look 20-80 % slower on nine levels (2026-09-06).

usage:
  python3 tools/pcref/laps_natural.py --plans <dir>     # writes 28 idle plans
  python3 tests/run_tricks.py <dir>/s1/Level1*.txt <dir>/s2/Level2*.txt --jobs=10 --out=/tmp/nfh-idle
  python3 tools/pcref/laps_natural.py [--idle /tmp/nfh-idle] [level ...] [-v]

The table: one lap = the mobile routine list once (docs' "mobile routine"),
each mobile action paired with the PC bubble span of the same name; a
mobile sub-step the bubble does not split (MedalBox inside Hat, the shaving
chain in 104) is folded into the previous pair. Levels driven by an event
rather than a list (201's tutorial, 206's wait for the Mother) show n/a."""

import json, re, sys, glob
import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC = os.path.join(ROOT, 'docs', 'PC_LAPS_DETAIL.md')
IDLE = '/tmp/nfh-idle'
if '--idle' in sys.argv:
    k = sys.argv.index('--idle'); IDLE = sys.argv[k + 1]; del sys.argv[k:k + 2]
if '--plans' in sys.argv:
    out = sys.argv[sys.argv.index('--plans') + 1]
    for season, lo in (('s1', 101), ('s2', 201)):
        os.makedirs(os.path.join(out, season), exist_ok=True)
        for n in range(lo, lo + 14):
            open(os.path.join(out, season, 'Level%d.txt' % n), 'w').write(
                "# idle: the neighbour's natural lap, Woody only dodging\nwait 420\n")
    print('28 idle plans in', out); sys.exit()
txt = open(DOC).read()
pc = {}; routine = {}
for sec in re.split(r'^### ', txt, flags=re.M)[1:]:
    m = re.search(r'mobile Level(\d+)\)', sec)
    if not m: continue
    L = m.group(1)
    line = next((l for l in sec.splitlines() if l.startswith('PC (bubble')), '')
    spans = []
    for part in line.split(':', 1)[1].split('>'):
        mm = re.match(r'\s*(.+?)\s+(\d+)-(\d+)\s*$', part)
        if mm: spans.append((mm.group(1).strip(), int(mm.group(2)), int(mm.group(3))))
    pc[L] = spans
    rl = next((l for l in sec.splitlines() if l.startswith('mobile routine:')), '')
    routine[L] = [x.strip() for x in rl.split(':', 1)[1].split('>') if x.strip() and x.strip() != '?']
def norm(s): return re.sub(r'[^a-z]', '', s.lower())
ALIAS = {'sofatv': 'sofa', 'potterydiesel': 'dieselchair', 'puddlerail': 'waterpuddle', 'watermelon': 'melon', 'melons': 'melon',
         'mumchair': 'chair', 'teeth': 'toothbrush', 'gram': 'gramaphone', 'plant': 'plantstink', 'shezlong': 'deckchair',
         'mother': 'callrtmother', 'turban': 'turbanshop', 'bull': 'mechanicalbull', 'parrot': 'parrotledge', 'throne': 'aztecthrone',
         'rod': 'fishingrod', 'jacket': 'lifejacket', 'gear': 'divinggear', 'castle': 'sandcastle', 'shell': 'seashell', 'bar': 'beachbar',
         'board': 'surfboard', 'tennis': 'tabbletennis', 'tabletennis': 'tabbletennis', 'skis': 'waterskiis', 'waterskis': 'waterskiis', 'shoes': 'hotshoe', 'taj': 'tadjmahal', 'sink': 'sinkaftershave', 'cake': 'birthdaycake', 'meat': 'steakmeat', 'eat': 'steakchair', 'sculpture': 'sandsculpture', 'pad': 'landingpad',
         'dog': 'dogbasket', 'basket': 'dogbasket', 'mixer': 'mixer', 'kart': 'gokart', 'necklace': 'necklace', 'toilet': 'toilet'}
def match(pcname, mobname):
    a, b = norm(pcname), norm(mobname)
    a = ALIAS.get(a, a)
    if a == b: return True
    if len(a) >= 4 and (b.startswith(a) or a.startswith(b) or a in b or b in a): return True
    return False
def mobile_spans(L):
    d = glob.glob(IDLE + '/s*_Level%s' % L)
    if not d: return None
    rows = []; prev = -1
    for l in open(d[0] + '/state.jsonl'):
        r = json.loads(l)
        if r['t'] < prev - 5: break
        prev = r['t']
        rt = next((x for x in r['routines'] if x['role'] == 'Rottweiler'), None)
        if rt and rt.get('item'): rows.append((r['t'], rt.get('item'), rt.get('state')))
    seq = []; last = None
    for t, it, st in rows:
        if it != last: seq.append((t, it)); last = it
    acts = []
    for k, (t, it) in enumerate(seq):
        t1 = seq[k + 1][0] if k + 1 < len(seq) else rows[-1][0]
        acts.append((it, t1 - t))
    return acts
verbose = '-v' in sys.argv
levels = [a for a in sys.argv[1:] if a != '-v'] or sorted(pc)
summary = []
for L in levels:
    rt = routine.get(L) or []
    n = len(rt)
    m = mobile_spans(L)
    if not m or not n or not pc.get(L):
        print('== Level%s: no data' % L); continue
    mob = m[:n]                                   # one natural lap = the routine once
    # a mobile lap may be shorter than the routine list when actions vanish; fine
    pcs = pc[L]
    pairs = []; unmatched_pc = []
    pi = next((j for j, sp in enumerate(pcs) if match(sp[0], mob[0][0])), 0)
    for k, (name, dur) in enumerate(mob):
        # look ahead up to 2 PC spans for a match (PC-only reactions in between)
        hit = None
        for j in range(pi, min(pi + 3, len(pcs))):
            if match(pcs[j][0], name): hit = j; break
        if hit is None:
            # a mobile sub-step the PC bubble does not split: merge into the previous pair
            if pairs: pairs[-1] = (pairs[-1][0], pairs[-1][1], pairs[-1][2] + dur, pairs[-1][3] + '+' + name)
            else: pairs.append((name, 0, dur, name))
            continue
        for j in range(pi, hit): unmatched_pc.append(pcs[j][0])
        end = pcs[hit + 1][1] if hit + 1 < len(pcs) else pcs[hit][2]
        pairs.append((pcs[hit][0], end - pcs[hit][1], dur, name)); pi = hit + 1
    tp = sum(p[1] for p in pairs); tm = sum(p[2] for p in pairs)
    delta = 100.0 * (tm - tp) / tp if tp else 0
    print('== Level%s  lap: PC %d s | mobile %.0f s (%+.0f %%)%s' % (L, tp, tm, delta, ('  [PC-only: %s]' % ','.join(unmatched_pc)) if unmatched_pc else ''))
    big = [(p[3], p[1], p[2]) for p in pairs if abs(p[2] - p[1]) >= 5]
    if verbose or big:
        print('   ' + ' > '.join('%s %d/%.0f' % (p[3], p[1], p[2]) for p in pairs))
    summary.append((L, tp, tm, delta, big))
print()
print('%-6s %5s %6s %6s  %s' % ('level', 'PC', 'mob', 'delta', 'actions off by >=5 s (name PC/mobile)'))
for L, tp, tm, d, big in summary:
    print('%-6s %5d %6.0f %+5.0f%%  %s' % (L, tp, tm, d, '; '.join('%s %d/%.0f' % b for b in big)))
