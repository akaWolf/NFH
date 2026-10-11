#!/usr/bin/env python3
"""A plan run's catches on the original against the port's replay of the same inputs: for each PC catch
(Woody's fear / fight), the rooms of Woody and the catchers over the seconds before it on the PC (the trace)
and in the port (state.jsonl, zones -> PC rooms by the overlay), and whether the port's Woody shares a room
with a catcher at that moment — a yes says the port's catch is more lenient than the PC's, a no that the
port's catcher is elsewhere (its routine's timing or route) or its Woody is.

    python3 tools/pcoracle/catch_report.py 101 ~/nfh-bench/wine/logs1/oracle_level_peep_gated.jsonl ~/nfh-bench/runs/replay101_gated/s1_Level101"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

CATCH = ('fear1', 'fear2', 'fear3', 'fight')
CATCHERS = {'neighbor': 'Rottweiler', 'mother': 'Mother', 'chili': 'chili', 'dog': 'dog'}


def main(argv):
    n = int(argv[1]); rows = [json.loads(l) for l in open(os.path.expanduser(argv[2]))]
    run = os.path.expanduser(argv[3])
    m = (__import__('pcmap_s1') if n < 200 else __import__('pcmap')).PCMap(n)   # (Season 1's rooms are by name)
    zone_room = {z: pr['room'] for z, pr in m.rooms.items()}
    def pc_room(a):
        if a is None: return None
        if a.get('room') is not None: return a['room']
        for z, pr in m.rooms.items():
            if pr['x1'] - 60 <= a['x'] <= pr['x2'] + 60 and abs(a['y'] - pr['floor']) <= 150: return pr['room']
        return None
    ticks = {r['tick']: r['actors'] for r in rows if r['ev'] == 'tick'}
    catches = [(r['tick'], r['args'][2]) for r in rows if r['ev'] == 'action' and r['args'][1] == 'woody' and r['args'][2] in CATCH]
    port = [json.loads(l) for l in open(os.path.join(run, 'state.jsonl'))]
    def port_at(t):
        return min(port, key=lambda st: abs(st['t'] - t))
    last = -100
    for tick, what in catches:
        if tick - last < 60: last = tick; continue        # (a fear and its fight are one catch)
        last = tick
        print('== PC catch at tick %d (%.2f s): %s' % (tick, tick / 12.0, what))
        for t in range(tick - 36, tick + 1, 6):
            a = ticks.get(t) or {}
            pc = {k: (pc_room(v), v['anim']) for k, v in a.items() if k == 'woody' or k in CATCHERS}
            st = port_at(t / 12.0); w = st.get('woody') or {}
            po = {'woody': (zone_room.get(w.get('zone')), w.get('anim'))}
            for r in st['routines']:
                if r['role'] in CATCHERS.values(): po[r['role']] = (zone_room.get(r.get('zone')), r.get('anim'))
            print('  %6.2f  PC %-60s port %s' % (t / 12.0, pc, po))
        st = port_at(tick / 12.0); w = st.get('woody') or {}; wr = zone_room.get(w.get('zone'))
        shared = [r['role'] for r in st['routines'] if r['role'] in CATCHERS.values() and zone_room.get(r.get('zone')) == wr]
        print('  the port at the catch: Woody in %s, a catcher there: %s' % (wr, shared or 'no'))


if __name__ == '__main__':
    main(sys.argv)
