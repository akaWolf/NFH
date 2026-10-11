#!/usr/bin/env python3
"""The neighbour's PCDepartTicks calibrated as the net ticks a level's legs lack: the port's replay of the
oracle's lap run WITHOUT departure ticks (NFH_NO_DEPART=1) against the PC trace, leg by leg from one
station's action start to the next's. A leg is the station's stay, its exit's dispatch, the walk and the
next arrival; where the port's leg is shorter the difference, in ticks, is written as the exit's
PCDepartTicks of the station the leg leaves (the PC's GoTo target before the action start, the item by the
overlay's PCApproach). The absolute stands of pc_depart_ticks.py over-correct a level whose station seconds
already carry them (205: its legs paired within a tick before any were written). A station whose legs the
port runs long gets 0 (reported); a station without a paired leg gets 0 too, so a run with the keys
applied is the level's own measure.

    python3 tools/pcoracle/calib_depart.py 205 ~/nfh-bench/wine/logs/oracle_cn_b2_park.jsonl ~/nfh-bench/runs/replay205_nodep/s2_Level205 [--write]"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref')); sys.path.insert(0, HERE)
import cmp_pairs, pc_depart_ticks as pdt

STANDS = ('ms0', 'ms1', 'ms2', 'ms3')

def strip(n):
    """--strip: the level's PCDepartTicks of every role and the PCStart departs removed — a level whose legs
    paired within a tick before any were written (its station seconds carry the stands already)"""
    ov_path = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n); ov = json.load(open(ov_path)); k = 0
    for e in ov['patches']:
        s = e.get('set') or {}
        if 'PCDepartTicks' in s: del s['PCDepartTicks']; k += 1
        if isinstance(s.get('PCStart'), dict) and 'depart' in s['PCStart']: del s['PCStart']['depart']; k += 1
    ov['patches'] = [e for e in ov['patches'] if e.get('set') != {} ]
    json.dump(ov, open(ov_path, 'w'), ensure_ascii=False, indent=1); open(ov_path, 'a').write('\n')
    print('stripped %d departure keys from %s' % (k, ov_path))

def main(argv):
    if '--strip' in argv:
        strip(int(argv[1])); return
    n = int(argv[1]); trace = os.path.expanduser(argv[2]); run = os.path.expanduser(argv[3]); write = '--write' in argv
    until = 200.0
    rows = [json.loads(l) for l in open(trace)]
    ticks = [(r['tick'], r['actors']['neighbor']['anim'], r['actors']['neighbor']['x'], r['actors']['neighbor']['y'])
             for r in rows if r['ev'] == 'tick' and r['actors'].get('neighbor')]
    gotos = [(r['tick'], r['args'][1], r['args'][2]) for r in rows if r['ev'] == 'goto' and isinstance(r['args'][2], str)]
    ov0 = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
    rooms0 = {e['object']: e['set']['PCRoom'] for e in ov0['patches'] if (e.get('set') or {}).get('PCRoom')}
    targets = pdt.actor_gotos(rows, ticks, gotos, 'neighbor', rooms0)
    # the PC's action starts (the first animation that is neither a walk nor a stand after a walk) with the
    # station walked to
    pc_starts = []; walking = False; wstart = None
    for t, anim, x, y in ticks:
        if anim in cmp_pairs.WALKS and anim not in STANDS:
            if not walking: wstart = t
            walking = True
        elif anim in STANDS:
            continue
        elif walking:
            walking = False
            g = [tg for tg in targets if tg[0] <= (wstart if wstart is not None else t) + 2]
            pc_starts.append((t / 12.0, g[-1][1] if g else None))
    # the port's action starts
    segs = cmp_pairs.port_segments(run, role='Rottweiler', until=until)
    po_starts = cmp_pairs.arrivals(segs, lambda a: a.startswith(('Walk_', 'Run_')), lambda a: a.startswith('Stand_'))
    ov_path = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n); ov = json.load(open(ov_path))
    fam_item = {}
    for e in ov['patches']:
        ap = ((e.get('set') or {}).get('PCApproach') or {}).get('Rottweiler')
        if isinstance(ap, dict) and ap.get('obj'):
            fam_item.setdefault(pdt.family(ap['obj']), e['object'])
    m = min(len(pc_starts), len(po_starts))
    print('%d PC action starts, %d port ones; paired in order:' % (len(pc_starts), len(po_starts)))
    by_item = collections.defaultdict(list); seen = set()
    for i in range(m - 1):
        (ta, station), tb = pc_starts[i], pc_starts[i + 1][0]
        pa, pb = po_starts[i], po_starts[i + 1]
        if ta > until or tb > until: break
        item = fam_item.get(pdt.family(station)) if station else None
        pc_dt, po_dt = tb - ta, pb - pa
        d = int(round((pc_dt - po_dt) * 12))
        flag = '' if abs(pa - ta) < 3.0 else '   (the sides %+.1f s apart: not used)' % (pa - ta)
        print('  %7.2f %-30s leg %6.2f | port %7.2f leg %6.2f | %+4d ticks%s' % (ta, (station or '?') + (' -> ' + item if item else ''), pc_dt, pa, po_dt, d, flag))
        if item and not flag: by_item[item].append(d); seen.add(item)
    paired = sum(1 for i in range(m - 1) if abs(po_starts[i] - pc_starts[i][0]) < 3.0)
    if m >= 2 and paired < (m - 1) / 2.0:
        # the action starts do not pair one to one (205's two-part ski, 209's clap at the fakir, 212): the
        # bubble's intervals instead — from an icon to the next is the visit of the station the port's
        # routine turns to at that icon
        print('only %d of %d legs pair: the bubble intervals instead' % (paired, m - 1))
        by_item = collections.defaultdict(list)
        pc_in, pc_ic, pc_st, pc_cr, pc_ca = cmp_pairs.load_pc(trace)
        po_in, po_th, po_cl, po_tr, po_ca = cmp_pairs.load_port(run)
        items_at = {}; last = None
        for l in open(os.path.join(run, 'state.jsonl')):
            st = json.loads(l); th = (st['hud'] or {}).get('think')
            if th != last:
                r = next(x for x in st['routines'] if x['role'] == 'Rottweiler'); items_at[round(st['t'], 3)] = r['item']; last = th
        bp = [(a, b) for a, b in cmp_pairs.pair_by_value(pc_ic, po_th, key=cmp_pairs.bubble_key) if a and b]
        for (a, b), (a2, b2) in zip(bp, bp[1:]):
            pc_dt = a2[0] - a[0]; po_dt = b2[0] - b[0]
            if pc_dt <= 0 or po_dt <= 0 or pc_dt > 120: continue
            d = int(round((pc_dt - po_dt) * 12))
            k = next((t for t in sorted(items_at) if t >= b[0] - 0.05), None)
            item = items_at.get(k) if k is not None else None
            print('  %7.2f %-12s PC %6.2f port %6.2f %+4d ticks  %s' % (a[0], a[1], pc_dt, po_dt, d, item))
            if item: by_item[item].append(d)
    # the level's start: the first bubble change on both sides — the PCStart depart of the neighbour
    pc_in, pc_ic, pc_st, pc_cr, pc_ca = cmp_pairs.load_pc(trace)
    po_in, po_th, po_cl, po_tr, po_ca = cmp_pairs.load_port(run)
    bp0 = [(a, b) for a, b in cmp_pairs.pair_by_value(pc_ic, po_th, key=cmp_pairs.bubble_key) if a and b]
    first = [(a, b) for a, b in bp0 if a[0] > 0.5]
    start_val = None
    if first:
        a, b = first[0]; start_val = int(round((a[0] - b[0]) * 12))
        print('the start: the first bubble %r at PC %.2f, port %.2f -> %+d ticks' % (a[1], a[0], b[0], start_val))
    import pc_durations_s2
    changed = 0
    if write and start_val is not None:
        for e in ov['patches']:
            st = (e.get('set') or {}).get('PCStart')
            if st and e.get('component') == 'Rottweiler':
                v = max(0, min(6, start_val))
                if st.get('depart') != v: st['depart'] = v; changed += 1
                print('PCStart depart (Rottweiler) -> %d' % v)
    items_with_keys = [e['object'] for e in ov['patches'] if 'PCDepartTicks' in (e.get('set') or {}) and 'Rottweiler' in e['set']['PCDepartTicks']]
    for item in sorted(set(items_with_keys) | set(by_item)):
        lst = by_item.get(item, [])
        if lst:
            c = collections.Counter(lst); val = c.most_common(1)[0][0]
            note = ''
            if val < 0: note = ' (the port is long here: 0)'; val = 0
            if val > 6: note = ' (past six: a wait or a divergence: kept out)'
        else:
            c = {}; val = 0; note = ' (no paired leg: 0)'
        print('%-26s deficits %s -> %d%s' % (item, dict(c), val, note))
        if write and val <= 6:
            cur = {}
            for e in ov['patches']:
                if e.get('object') == item and isinstance(e.get('set'), dict) and 'PCDepartTicks' in e['set']:
                    cur = dict(e['set']['PCDepartTicks']); break
            cur['Rottweiler'] = val
            pc_durations_s2._set_key(ov['patches'], item, 'PCDepartTicks', cur); changed += 1
    if write and changed:
        json.dump(ov, open(ov_path, 'w'), ensure_ascii=False, indent=1); open(ov_path, 'a').write('\n')
        print('written %d keys to %s' % (changed, ov_path))

if __name__ == '__main__':
    main(sys.argv)
