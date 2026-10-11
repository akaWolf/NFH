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
import json, os, sys

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
        elif r['ev'] == 'icon' and r['args'][0] == 'neighbor':
            ic = r['args'][1]
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

WALKS = ('mg0', 'mg1', 'mg2', 'mg3', 'ms0', 'ms1', 'ms2', 'ms3')
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

def show_segments(pc, port):
    print('== the neighbour\'s animations (PC anim at x,y / port anim at x,y in PC px) to %.0f s' % max([t for t, *_ in pc] + [0]))
    i = j = 0
    while i < len(pc) or j < len(port):
        a = pc[i] if i < len(pc) else None; b = port[j] if j < len(port) else None
        if b is None or (a is not None and a[0] <= b[0]):
            print('  %7.2f PC   %-18s %5s,%-4s' % (a[0], a[1], a[2], a[3])); i += 1
        else:
            print('  %7.2f port %-18s %5s,%-4s' % (b[0], b[1], b[2], b[3])); j += 1

def pair_by_value(pc, port, key=lambda v: v):
    """both sides in order; a value missing on one side is skipped (listed as a slip)"""
    out = []; j = 0
    for t, v in pc:
        k = j
        while k < len(port) and key(port[k][1]) != key(v): k += 1
        if k < len(port):
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
    show('bubble (PC icon / port think)', pair_by_value(pc_ic, po_th))
    mapped = [(t, STATION_CLIPS[(f, a)]) for t, f, a in pc_st if (f, a) in STATION_CLIPS]
    show('stations (PC action / port clip)', pair_by_value(mapped, [(t, c) for t, c in po_cl if c in STATION_CLIPS.values()]))
    rest = sorted(set((f, a) for t, f, a in pc_st if (f, a) not in STATION_CLIPS))
    print('  (unmapped PC actions: %s)' % ', '.join('%s %s' % x for x in rest))
    show('records paid (PC CREDIT / port TRICKS)', [((a, 'credit'), (b, 'trick')) for a, b in zip(pc_cr, po_tr)] + [((a, 'credit'), None) for a in pc_cr[len(po_tr):]] + [(None, (b, 'trick')) for b in po_tr[len(pc_cr):]])
    show('caught', [((a, 'fight'), (b, 'caught')) for a, b in zip(pc_ca, po_ca)] + [((a, 'fight'), None) for a in pc_ca[len(po_ca):]] + [(None, (b, 'caught')) for b in po_ca[len(pc_ca):]])
    until = float(next((a[len('--segments='):] for a in argv if a.startswith('--segments=')), '0'))
    if until:
        n = int(next(x for x in os.path.basename(os.path.normpath(argv[2])).split('_') if x.startswith('Level'))[5:])
        pcs, pos = pc_segments(argv[1], until=until), port_segments(argv[2], until=until, to_px=px_mapper(n))
        show_segments(pcs, pos); show_phases(pcs, pos)

if __name__ == '__main__':
    main(sys.argv)
