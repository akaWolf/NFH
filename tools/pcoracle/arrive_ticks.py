#!/usr/bin/env python3
"""The ticks an actor stands at a station between its walk's last move and the station's first animation —
the arrival's step dispatch (the GoTo's job ends, the next step's DoAction runs, its animation shows a tick
on: two ticks at 202's mat and rail; one at the sea, whose icon step sets the animation itself), from the
oracle's trace, per station: the twin of exit_ticks.py / pc_depart_ticks.py.

    python3 tools/pcoracle/arrive_ticks.py <n> <trace> [role] [--write]

--write puts the most frequent value per station into the overlay as PCArriveTicks per role."""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref')); sys.path.insert(0, HERE)
import pc_depart_ticks as pdt

WALKS = pdt.WALKS; STANDS = pdt.STANDS

def arrivals(rows, role):
    """(station object walked to, stand ticks, the first animation) per arrival of the actor"""
    ticks = []; gotos = []
    for r in rows:
        if r['ev'] == 'tick':
            a = r['actors'].get(role)
            if a: ticks.append((r['tick'], a['anim'], a['x'], a['y']))
        elif r['ev'] == 'goto' and isinstance(r['args'][2], str):
            gotos.append((r['tick'], r['args'][1], r['args'][2]))
    targets = pdt.actor_gotos(rows, ticks, gotos)
    out = []; i = 0
    while i < len(ticks):
        if ticks[i][1] not in WALKS:
            i += 1; continue
        # the walk's last move: the last walk tick whose position changed
        j = i
        while j < len(ticks) and ticks[j][1] in WALKS: j += 1
        if j >= len(ticks): break
        k = j - 1
        while k > i and (ticks[k][2], ticks[k][3]) == (ticks[k - 1][2], ticks[k - 1][3]): k -= 1
        last_move = ticks[k][0]
        # the first animation that is neither a walk nor a stand after the walk
        m = j
        while m < len(ticks) and ticks[m][1] in STANDS: m += 1
        if m >= len(ticks): break
        if ticks[m][1] in WALKS:
            i = m; continue              # a stand between two walks (a door claim): no station
        first = ticks[m]
        g = [t for t in targets if t[0] <= ticks[i][0] + 2]
        station = g[-1][1] if g else None
        if station: out.append((station, first[0] - last_move, first[1]))
        i = m
    return out

def main(argv):
    n = int(argv[1]); rows = [json.loads(l) for l in open(os.path.expanduser(argv[2]))]
    roles = [a for a in argv[3:] if not a.startswith('--')] or list(pdt.ROLES)
    write = '--write' in argv
    ov_path = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n); ov = json.load(open(ov_path))
    stations = {}
    for e in ov['patches']:
        ap = (e.get('set') or {}).get('PCApproach') or {}
        for role, d in ap.items():
            if isinstance(d, dict) and d.get('obj'):
                stations.setdefault(role, {})[pdt.family(d['obj'])] = e['object']
    import pc_durations_s2
    changed = 0
    for pc_role in roles:
        role = pdt.ROLES.get(pc_role, pc_role)
        by = collections.defaultdict(list)
        for station, stand, first in arrivals(rows, pc_role):
            by[station].append((stand, first))
        for station, lst in sorted(by.items()):
            item = stations.get(role, {}).get(pdt.family(station))
            stands = collections.Counter(s for s, f in lst); val = stands.most_common(1)[0][0]
            print('%-10s %-34s %-26s stands %s (first %s) -> %d' % (role, station, item or '(no item)', dict(stands), sorted(set(f for s, f in lst)), val))
            if item and write:
                cur = {}
                for e in ov['patches']:
                    if e.get('object') == item and isinstance(e.get('set'), dict) and 'PCArriveTicks' in e['set']:
                        cur = dict(e['set']['PCArriveTicks']); break
                cur[role] = val
                pc_durations_s2._set_key(ov['patches'], item, 'PCArriveTicks', cur); changed += 1
    if write and changed:
        json.dump(ov, open(ov_path, 'w'), ensure_ascii=False, indent=1); open(ov_path, 'a').write('\n')
        print('written %d keys to %s' % (changed, ov_path))

if __name__ == '__main__':
    main(sys.argv)
