#!/usr/bin/env python3
"""The oracle's trace against the port's replay of the same inputs, paired: the deltas, not the stream.

    python3 tools/pcoracle/cmp_pairs.py ~/nfh-bench/wine/logs/oracle_cn_b1_<tag>.jsonl ~/nfh-bench/runs/replay202_<tag>/s2_Level202

Pairs, in order of time on each side: the inputs (the PC's injected message, the port's click — equal by
construction, a check of the replay); the bubble (the PC's icon changes on the neighbour, the port's think
changes — matched by value in sequence, the slips listed); the neighbour's station actions against the
port's routine clip starts (STATION_CLIPS: the PC action -> the port's anim, by level — the ones not
listed are printed unpaired); the trick records paid (PC CREDIT, port TRICKS); the catches (the PC's
`woody fight`, the port's Woody caught). Each pair prints both times and the port minus the PC in seconds;
the summary the mean and the spread per kind."""
import json, os, re, sys

STATION_CLIPS = {
    # PC DoAction (room/object family, action) -> the port's routine anim that starts then (Level202)
    ('beachright/mat', 'enter'): 'BeachLayDown', ('beachright/mat', 'use'): 'BeachGetBeer', ('beachright/mat', 'leave'): 'BeachGetUp',
    ('beachright/theocean', 'enter'): 'EnterSea', ('beachright/theocean', 'leave'): 'LeaveSea',
    ('pond/bridge', 'look'): 'LookBridge',
}

def fam(name):
    room, _, base = name.rpartition('/')
    return room + '/' + base.split('_')[0]

def load_pc(p):
    rows = [json.loads(l) for l in open(os.path.expanduser(p))]
    inputs, icons, stations, credits, caught = [], [], [], [], []
    icon = None
    for r in rows:
        t = r['tick'] / 12.0
        if r['ev'] == 'injected':
            s = r['step']; inputs.append((t, '%s %s' % (s['kind'], ' '.join(map(str, s['args'])))))
        elif r['ev'] == 'icon' and (r['args'][0] == 'neighbor' or (isinstance(r['args'][0], str) and not isinstance(r['args'][1], str))):
            # Season 2: SetIcon(actor, icon); Season 1: SetIcon(icon) — the neighbour's bubble either way
            ic = r['args'][1] if r['args'][0] == 'neighbor' else r['args'][0]
            if ic != icon:
                icon = ic; icons.append((t, ic if isinstance(ic, str) else ''))
        elif r['ev'] == 'action':
            obj, act = r['args'][1], r['args'][2]
            if isinstance(obj, str) and '/' in obj:
                stations.append((t, fam(obj), act))
            elif obj == 'woody' and act == 'fight':
                caught.append(t)
        elif r['ev'] == 'credit':
            credits.append(t)
    return inputs, icons, stations, credits, caught

def load_port(d):
    d = os.path.expanduser(d)
    st = [json.loads(l) for l in open(os.path.join(d, 'state.jsonl'))]
    thinks, clips, tricks, caught = [], [], [], []
    last_think = None; last_anim = None; last_tricks = 0; was_caught = False
    for s in st:
        r = next(x for x in s['routines'] if x['role'] == 'Rottweiler')
        th = s['hud'].get('think') if s['hud'] else None
        if th != last_think:
            thinks.append((s['t'], th or '')); last_think = th
        if r['anim'] != last_anim:
            clips.append((s['t'], r['anim'])); last_anim = r['anim']
        if s['game']['tricks'] != last_tricks:
            tricks.append(s['t']); last_tricks = s['game']['tricks']
        c = bool(s['game'].get('caught') or s['game'].get('lives_lost'))
        if c and not was_caught: caught.append(s['t'])
        was_caught = c
    inputs = []
    try:
        for c in json.load(open(os.path.join(d, 'clicks.json'))):
            inputs.append((c['frame'] / 60.0, '%s %s' % (c.get('item'), c.get('type'))))
    except OSError:
        pass
    return inputs, thinks, clips, tricks, caught

def pc_segments(p, role='neighbor', until=90.0):
    """the actor's animation changes with his position, from the per-tick actors"""
    out = []; last = None
    for l in open(os.path.expanduser(p)):
        r = json.loads(l)
        if r['ev'] != 'tick': continue
        a = r['actors'].get(role)
        if not a: continue
        t = r['tick'] / 12.0
        if t > until: break
        if a['anim'] != last:
            out.append((t, a['anim'], a['x'], a['y'])); last = a['anim']
    return out

def port_segments(d, role='Rottweiler', until=90.0, to_px=None):
    out = []; last = None
    for l in open(os.path.join(os.path.expanduser(d), 'state.jsonl')):
        s = json.loads(l)
        if s['t'] > until: break
        r = next(x for x in s['routines'] if x['role'] == role)
        if r['anim'] != last:
            x, y = (to_px(r['x'], r['y'], r['zone']) if to_px else (r['x'], r['y']))
            out.append((s['t'], r['anim'], x, y)); last = r['anim']
    return out

def px_mapper(n):
    """the port's world x -> the PC's level px, through the zones' PCRoom (the inverse of oracle2plan's)"""
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(ROOT, 'runtime'))
    try:
        import scene
    except Exception:
        return None
    lv = scene.Level(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n))
    zones = {z.name: z for z in lv.zones if getattr(z, 'pc_room', None)}
    def f(x, y, zone):
        z = zones.get(zone)
        if z is None: return round(x, 2), round(y, 2)
        pr = z.pc_room
        return int(round(pr['x1'] + (x - z.left) * (pr['x2'] - pr['x1']) / float(z.right - z.left))), pr['floor']
    return f

WALKS = ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3', 'ms0', 'ms1', 'ms2', 'ms3')
def phases(segs, is_walk):
    """the animation changes folded into phases: a run of walk / stand animations is one `walk`, every other
    animation its own phase — (start, name, duration)"""
    out = []
    for i, (t, anim, x, y) in enumerate(segs):
        end = segs[i + 1][0] if i + 1 < len(segs) else t
        name = 'walk' if is_walk(anim) else anim
        if out and out[-1][1] == 'walk' and name == 'walk':
            out[-1] = (out[-1][0], 'walk', round(end - out[-1][0], 2))
        else:
            out.append((t, name, round(end - t, 2)))
    return out

def blocks(ph):
    """the phases as alternating walks and stays: a stay is everything between two walks — (start, kind,
    duration, the clips)"""
    out = []
    for t, name, dur in ph:
        if name == 'walk' or not out or out[-1][1] == 'walk':
            out.append([t, 'walk' if name == 'walk' else 'stay', dur, [] if name == 'walk' else [name]])
        else:
            out[-1][2] = round(out[-1][2] + dur, 2); out[-1][3].append(name)
    return out

def show_phases(pc, port):
    """the two sides' walks and stays paired in order: a walk against a walk, the stay between two walks
    against the port's clips between its walks"""
    a = blocks(phases(pc, lambda n: n in WALKS))
    b = blocks(phases(port, lambda n: n.startswith('Walk_') or n.startswith('Stand_')))
    print('== the neighbour\'s walks and stays (PC / port: start, seconds, clips; port minus PC, the running sum)')
    i = j = 0; acc = 0.0
    while i < len(a) or j < len(b):
        x = a[i] if i < len(a) else None; y = b[j] if j < len(b) else None
        if x and y:
            d = y[2] - x[2]; acc += d
            print('  %7.2f %-4s %5.2f %-28s | %7.2f %5.2f %-40s | %+5.2f (sum %+5.2f)' % (x[0], x[1], x[2], '+'.join(x[3])[:28], y[0], y[2], '+'.join(y[3])[:40], d, acc)); i += 1; j += 1
        elif x: print('  %7.2f %-4s %5.2f %-28s |' % (x[0], x[1], x[2], '+'.join(x[3])[:28])); i += 1
        else: print('  %41s | %7.2f %5.2f %-40s' % ('', y[0], y[2], '+'.join(y[3])[:40])); j += 1

def arrivals(segs, is_walk, is_stand):
    """the times a station's action starts: the first animation that is neither a walk nor a stand after a
    walk (the stands between — the PC's arrival and dispatch ticks, the port's door claims — are no station)"""
    out = []; walking = False
    for t, anim, x, y in segs:
        if is_walk(anim): walking = True
        elif is_stand(anim): continue
        elif walking: out.append(t); walking = False
    return out

def show_arrivals(pc, port):
    """station to station: the stations' action starts paired in order, the legs between them on both sides
    — free of the stay / walk boundary"""
    a = arrivals(pc, lambda n: n in WALKS and not n.startswith('ms'), lambda n: n in ('ms0', 'ms1', 'ms2', 'ms3'))
    b = arrivals(port, lambda n: n.startswith(('Walk_', 'Run_')), lambda n: n.startswith('Stand_'))
    print('== stations (PC / port: the action start, the leg since the last one; port minus PC per leg, the running sum)')
    acc = 0.0
    for i in range(min(len(a), len(b))):
        la = a[i] - a[i - 1] if i else a[i]; lb = b[i] - b[i - 1] if i else b[i]
        d = lb - la; acc += d
        print('  %7.2f %6.2f | %7.2f %6.2f | %+5.2f (sum %+5.2f)' % (a[i], la, b[i], lb, d, acc))


def actor_gotos(rows, role_ticks, gotos, role='neighbor', rooms=None):
    """the actor's walks' targets as (tick, target): the `goto` records of the actor's object — the trace's
    `actor` record names it (the path finder's registration), else the pointer whose targets' rooms agree
    most with the rooms the actor's walks end in (`rooms`: {zone: PCRoom} of the level — the room of a
    target is its name's prefix, the room of a position the PCRoom whose x range and floor hold it), else
    (Season 1: no GoTo hook) the first DoAction on a room/object within four ticks after an arrival"""
    WALKS_ = ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3')
    firsts = []; last = None
    for t, ptr, target in gotos:
        if (ptr, target) != last: firsts.append((t, ptr, target)); last = (ptr, target)
    named = [r for r in rows if r.get('ev') == 'actor' and r.get('name') == role and r.get('ptr')]
    mine = named[0]['ptr'] if named else None
    if mine is None and firsts:
        # the walks' ends: the last walk tick before a stand or another animation
        ends = []
        for i in range(1, len(role_ticks)):
            if role_ticks[i - 1][1] in WALKS_ and role_ticks[i][1] not in WALKS_:
                ends.append(role_ticks[i - 1])
        def room_of(x, y):
            for z, pr in (rooms or {}).items():
                if pr['x1'] - 150 <= x <= pr['x2'] + 150 and abs(y - pr['floor']) <= 200: return pr['room']
            return None
        score = {}
        for t, ptr, target in firsts:
            e = next((e for e in ends if e[0] >= t), None)
            if e is None: continue
            if room_of(e[2], e[3]) == target.split('/')[0]: score[ptr] = score.get(ptr, 0) + 1
        if score: mine = max(score, key=score.get)
    if mine is not None:
        return [(t, target) for t, ptr, target in firsts if ptr == mine]
    # the fallback: arrivals and the actions right after them
    actions = [(r['tick'], r['args'][1]) for r in rows if r['ev'] == 'action' and isinstance(r['args'][1], str) and '/' in r['args'][1]]
    out = []; walking = False; start = None
    for t, anim, x, y in role_ticks:
        if anim in WALKS_:
            if not walking: start = t
            walking = True
        elif walking:
            walking = False
            a = next((obj for at, obj in actions if t <= at <= t + 4), None)
            if a: out.append((start if start is not None else t, a))
    return out

def lap_orders(pc_path, port_dir, role='neighbor', port_role='Rottweiler', until=400.0):
    """the station sequence on both sides: the PC's GoTo targets of the actor (the `goto` hook's records,
    the actor pointer voted by the walks it starts) against the port's routine item changes"""
    rows = [json.loads(l) for l in open(os.path.expanduser(pc_path))]
    ticks = []; gotos = []
    for r in rows:
        if r['ev'] == 'tick':
            a = r['actors'].get(role)
            if a: ticks.append((r['tick'], a['anim'], a['x'], a['y']))
        elif r['ev'] == 'goto' and isinstance(r['args'][2], str):
            gotos.append((r['tick'], r['args'][1], r['args'][2]))
    ROOT_ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    n_ = re.search(r'(?<!\d)([12]\d\d)(?!\d)', os.path.basename(os.path.normpath(port_dir)) + ' ' + port_dir).group(1)
    ov_ = json.load(open(os.path.join(ROOT_, 'levels', 'pc', 'Level%s.overlay.json' % n_)))
    rooms_ = {e['object']: e['set']['PCRoom'] for e in ov_['patches'] if (e.get('set') or {}).get('PCRoom')}
    pc_seq = [(t / 12.0, target) for t, target in actor_gotos(rows, ticks, gotos, role, rooms_) if t / 12.0 <= until]
    port_seq = []; last = None
    for l in open(os.path.join(os.path.expanduser(port_dir), 'state.jsonl')):
        st = json.loads(l)
        if st['t'] > until: break
        r = next(x for x in st['routines'] if x['role'] == port_role)
        if r['item'] != last: port_seq.append((st['t'], r['item'])); last = r['item']
    # the visits: consecutive GoTos to one object's family are one visit; the port's items the same way;
    # paired in order while the names agree (the item whose PCApproach for the role names the family),
    # the deltas per visit
    n = int(re.search(r'(?<!\d)([12]\d\d)(?!\d)', os.path.basename(os.path.normpath(port_dir)) + ' ' + port_dir).group(1))
    ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
    fam_item = {}
    for e in ov['patches']:
        ap = ((e.get('set') or {}).get('PCApproach') or {}).get(port_role)
        if isinstance(ap, dict) and ap.get('obj'):
            room, _, base = ap['obj'].rpartition('/'); fam_item.setdefault((room, base.split('_')[0]), e['object'])
    if n < 200:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import pcmap_s1
        for it, obj in pcmap_s1.PCMap(n).objs.items():
            room, _, base = obj.rpartition('/'); fam_item.setdefault((room, base.split('_')[0]), it)
    def famof(name):
        room, _, base = name.rpartition('/'); return room, base.split('_')[0]
    visits = []
    for t, target in pc_seq:
        if not visits or famof(visits[-1][1]) != famof(target): visits.append((t, target))
    print('== the visits (PC: the neighbour\'s GoTo to a station / port: the routine\'s item; port minus PC)')
    i = j = 0; acc = []
    while i < len(visits) or j < len(port_seq):
        a = visits[i] if i < len(visits) else None; b = port_seq[j] if j < len(port_seq) else None
        it = fam_item.get(famof(a[1])) if a else None
        if a and b and it == b[1]:
            d = b[0] - a[0]; acc.append(d)
            print('  %7.2f %-32s | %7.2f %-22s | %+6.2f' % (a[0], a[1], b[0], b[1], d)); i += 1; j += 1
        elif a and (b is None or (it is not None and it in [x[1] for x in port_seq[j:j + 3]]) is False):
            print('  %7.2f %-32s | %7s %-22s |' % (a[0], a[1] + ('' if it else ' (no item)'), '', '')); i += 1
        else:
            print('  %7s %-32s | %7.2f %-22s |' % ('', '', b[0], b[1])); j += 1
    if acc:
        print('  -> %d visits paired, port - PC mean %+.2f s, min %+.2f, max %+.2f' % (len(acc), sum(acc) / len(acc), min(acc), max(acc)))

def show_segments(pc, port):
    print('== the neighbour\'s animations (PC anim at x,y / port anim at x,y in PC px) to %.0f s' % max([t for t, *_ in pc] + [0]))
    i = j = 0
    while i < len(pc) or j < len(port):
        a = pc[i] if i < len(pc) else None; b = port[j] if j < len(port) else None
        if b is None or (a is not None and a[0] <= b[0]):
            print('  %7.2f PC   %-18s %5s,%-4s' % (a[0], a[1], a[2], a[3])); i += 1
        else:
            print('  %7.2f port %-18s %5s,%-4s' % (b[0], b[1], b[2], b[3])); j += 1

BUBBLE_ALIASES = {'zahnbuerste': 'toothbrush', 'kaffee': 'coffee', 'what': 'noise',   # (108's German names; 'what' is the PC's noise icon)
                  'milkbottle': 'babybottle', 'cookies': 'cookiebox', 'parrot': 'chili', 'mail': 'mailbox',
                  'klavier': 'piano', 'blume': 'flower', 'fussball': 'football'}
def bubble_key(v):
    """the PC's icon name and the port's think name (bubble_<mobile name>) on one key: the prefix and the
    underscores dropped (alarm_clock / alarmclock), the few the mobile names otherwise aliased"""
    k = (v or '').replace('bubble_', '').replace('_', '').lower()
    return BUBBLE_ALIASES.get(k, k)

def pair_by_value(pc, port, key=lambda v: v, window=20.0):
    """both sides in order; a value missing on one side is skipped (listed as a slip) — a match is taken
    only within `window` seconds, so a PC icon the port never shows (206's flicker between `mother` and
    `get_pillow`) does not drag the pairing forward"""
    out = []; j = 0
    for t, v in pc:
        k = j
        while k < len(port) and (key(port[k][1]) != key(v) or port[k][0] < t - window) and port[k][0] <= t + window: k += 1
        if k < len(port) and key(port[k][1]) == key(v) and abs(port[k][0] - t) <= window:
            for s in range(j, k): out.append((None, port[s]))
            out.append(((t, v), port[k])); j = k + 1
        else:
            out.append(((t, v), None))
    for s in range(j, len(port)): out.append((None, port[s]))
    return out

def show(title, pairs):
    print('== %s' % title)
    ds = []
    for a, b in pairs:
        if a and b:
            d = b[0] - a[0]; ds.append(d)
            print('  %7.2f PC %-28s %7.2f port %-28s %+6.2f' % (a[0], a[1], b[0], b[1], d))
        elif a: print('  %7.2f PC %-28s         (port: none)' % (a[0], a[1]))
        else: print('          PC %-28s %7.2f port %-28s' % ('(none)', b[0], b[1]))
    if ds:
        print('  -> %d pairs, port - PC mean %+.2f s, min %+.2f, max %+.2f' % (len(ds), sum(ds) / len(ds), min(ds), max(ds)))

def main(argv):
    argv = [a for a in argv if not a.startswith('--')] + [a for a in argv if a.startswith('--')]
    pc_in, pc_ic, pc_st, pc_cr, pc_ca = load_pc(argv[1])
    po_in, po_th, po_cl, po_tr, po_ca = load_port(argv[2])
    show('inputs', [((a[0], a[1]), (b[0], b[1])) for a, b in zip(pc_in, po_in)] + [((a[0], a[1]), None) for a in pc_in[len(po_in):]] + [(None, (b[0], b[1])) for b in po_in[len(pc_in):]])
    show('bubble (PC icon / port think)', pair_by_value(pc_ic, po_th, key=bubble_key))
    mapped = [(t, STATION_CLIPS[(f, a)]) for t, f, a in pc_st if (f, a) in STATION_CLIPS]
    show('stations (PC action / port clip)', pair_by_value(mapped, [(t, c) for t, c in po_cl if c in STATION_CLIPS.values()]))
    rest = sorted(set((f, a) for t, f, a in pc_st if (f, a) not in STATION_CLIPS))
    print('  (unmapped PC actions: %s)' % ', '.join('%s %s' % x for x in rest))
    show('records paid (PC CREDIT / port TRICKS)', [((a, 'credit'), (b, 'trick')) for a, b in zip(pc_cr, po_tr)] + [((a, 'credit'), None) for a in pc_cr[len(po_tr):]] + [(None, (b, 'trick')) for b in po_tr[len(pc_cr):]])
    show('caught', [((a, 'fight'), (b, 'caught')) for a, b in zip(pc_ca, po_ca)] + [((a, 'fight'), None) for a in pc_ca[len(po_ca):]] + [(None, (b, 'caught')) for b in po_ca[len(pc_ca):]])
    until = float(next((a[len('--segments='):] for a in argv if a.startswith('--segments=')), '0'))
    if until:
        m = re.search(r'(?<!\d)([12]\d\d)(?!\d)', os.path.basename(os.path.normpath(argv[2]))) or re.search(r'(?<!\d)([12]\d\d)(?!\d)', argv[2])
        n = int(m.group(1))
        role = next((a[len('--role='):] for a in argv if a.startswith('--role=')), 'Rottweiler')
        pc_role = {'Rottweiler': 'neighbor', 'Olga': 'olga', 'Mother': 'mother', 'Woody': 'woody'}.get(role, role.lower())
        pcs, pos = pc_segments(argv[1], role=pc_role, until=until), port_segments(argv[2], role=role, until=until, to_px=px_mapper(n))
        print('== %s' % role)
        show_segments(pcs, pos); show_phases(pcs, pos); show_arrivals(pcs, pos)
        lap_orders(argv[1], argv[2], pc_role, role, until)

if __name__ == '__main__':
    main(sys.argv)
