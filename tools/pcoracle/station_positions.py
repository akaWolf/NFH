#!/usr/bin/env python3
"""Where the PC neighbour stands at each station, from a run's trace, against the overlay's PCApproach: for
each of his GoTo targets the place he stands as the station's action starts (the DoAction on the object he walked to), as the mode
over his visits, next to the overlay's x and its height against the floor line of the room that places the
object (px, y down) — the walk lengths of the port's laps rest on these. A line per station; a deviation of ten
px or more in x or in height is flagged.

    python3 tools/pcoracle/station_positions.py 213 ~/nfh-bench/wine/logs/oracle_me_c2_nocatch.jsonl"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

GAITS = ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3')


def main(argv):
    n = int(argv[1]); rows = [json.loads(l) for l in open(os.path.expanduser(argv[2]))]
    import pcmap
    m = pcmap.PCMap(n)
    ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
    approach = {}
    for e in ov['patches']:
        ap = ((e.get('set') or {}).get('PCApproach') or {}).get('Rottweiler')
        if isinstance(ap, dict) and ap.get('obj'):
            approach.setdefault(m.family(ap['obj']), (e['object'], ap))
    # the room an object stands in is the level.xml <room> block that places it, not its name's prefix
    # (203's wallleft/melons stands in groundleft; its groundleft/toilet up in wallleft), the floor line
    # that room's path1 y — pc_walks_s2's own frame for the overlay's px (hotspot y minus the floor line)
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref'))
    import lap_model_s2
    g = lap_model_s2.Geometry(n)
    actors = {r['name']: r['ptr'] for r in rows if r['ev'] == 'actor'}
    nb = actors.get('neighbor')
    ticks = [(r['tick'], r['actors']['neighbor']) for r in rows if r['ev'] == 'tick' and r['actors'].get('neighbor')]
    # his place as each station action starts (the DoAction on the object he walked to): the tick's state
    by_tick = {t: a for t, a in ticks}
    targets = set(r['args'][2] for r in rows if r['ev'] == 'goto' and r['args'][1] == nb and isinstance(r['args'][2], str))
    stands = collections.defaultdict(list)
    for r in rows:
        if r['ev'] == 'action' and isinstance(r['args'][1], str) and r['args'][1] in targets and r['args'][2] not in ('leave',):
            a = by_tick.get(r['tick']) or by_tick.get(r['tick'] + 1)
            if a is not None and a['anim'] not in GAITS: stands[r['args'][1]].append((a['x'], a['y']))
    print('== %d: %d stations walked to' % (n, len(stands)))
    for target, pts in sorted(stands.items()):
        (x, y), k = collections.Counter(pts).most_common(1)[0]
        room = g.room_of(target); floor = g.rooms[room]['y'] if room in g.rooms else None
        px = (y - floor) if floor is not None else None
        item, ap = approach.get(m.family(target), (None, {}))
        ax = ap.get('x'); apx = ap.get('px')
        ax = ax[0] if isinstance(ax, list) else ax; apx = apx[0] if isinstance(apx, list) else apx
        flag = ''
        if ax is not None and (abs(ax - x) >= 10 or (apx is not None and px is not None and abs(apx - px) >= 10)): flag = '  <-- off'
        print('  %-32s PC x %4d height %4s (%d visits)   overlay %-18s x %4s px %4s%s' % (target, x, px, len(pts), item, ax, apx, flag))


if __name__ == '__main__':
    main(sys.argv)
