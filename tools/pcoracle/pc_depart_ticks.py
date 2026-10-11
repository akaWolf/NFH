#!/usr/bin/env python3
"""The ticks a Season 2 actor stands after a station's last animation before its next walk's first move,
from the oracle's idle trace, into the overlays as PCDepartTicks — the step dispatch between the station's
action and the GoTo: the level script's next step runs the tick the action ends or the one after (a
hand-over), the GoTo's mover (fcn.10009177 / fcn.10009215) makes its first move two ticks after the call.
202's neighbour: the mat 4 (the leave's objanim ends, the icon step, the GoTo step a tick on, the move two
ticks on), the rail 2 (the GoTo in the tick the look ends), the sea 1 (the hideout's leave runs under the
GoTo already given); Olga's mat and sub 3.

    python3 tools/pcoracle/pc_depart_ticks.py 202 ~/nfh-bench/wine/logs/oracle_cn_b1_idle.jsonl [--write]

Per actor (the trace's neighbor / olga / mother / kid names, the port's roles) and station (the PC object
the actor's previous GoTo walked to, the mobile item whose PCApproach for the role names that object's
family): the stand ticks of each exit seen, the value written the most frequent one."""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref')); sys.path.insert(0, HERE)
import pcmap

STANDS = ('ms0', 'ms1', 'ms2', 'ms3')
WALKS = ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3')   # the walk and run gaits
ROLES = {'neighbor': 'Rottweiler', 'olga': 'Olga', 'mother': 'Mother', 'kid': 'Kid', 'fifi': 'Fifi'}

def family(name):
    room, _, base = name.rpartition('/')
    return room, base.split('_')[0]


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

ROOMS = {}        # the level's {zone: PCRoom}, set by main for the attribution of the walks' targets
def exits(rows, role):
    """(station object left, after-anim, stand ticks) per walk start of the actor"""
    ticks = []; gotos = []
    for r in rows:
        if r['ev'] == 'tick':
            a = r['actors'].get(role)
            if a: ticks.append((r['tick'], a['anim'], a['x'], a['y']))
        elif r['ev'] == 'goto' and isinstance(r['args'][2], str):
            gotos.append((r['tick'], r['args'][1], r['args'][2]))
    firsts = [(t, None, target) for t, target in actor_gotos(rows, ticks, gotos, role, ROOMS.get('rooms'))]
    out = []; i = 0; station = None
    while i < len(ticks):
        t, anim, x, y = ticks[i]
        if anim in WALKS:
            j = i
            while j < len(ticks) and ticks[j][1] in WALKS and (ticks[j][2], ticks[j][3]) == (x, y): j += 1
            move = ticks[j][0] if j < len(ticks) else None
            k = i - 1
            while k >= 0 and ticks[k][1] in STANDS: k -= 1
            after = ticks[k][1] if k >= 0 else '-'
            end = ticks[k + 1][0] if k + 1 < len(ticks) else t
            if after not in WALKS and after != '-' and move is not None and station is not None \
                    and not after.startswith(('fight', 'shout', 'fear', 'respawn')):
                # (a catch's fight is no station exit: the run's Woody stood in the lap's way)
                out.append((station, after, move - end))
            elif station is None and move is not None and not out and i == 0 or (station is None and move is not None and not out and after == '-'):
                # the level start: the first GoTo's dispatch, the stand before the first move
                out.append(('(start)', '-', move - 1))          # from the level's first tick
            # the walk's GoTo: the actor's last GoTo record up to the first move (a hideout's leave runs
            # under a GoTo given before it) — its target is the station left at the next exit
            g = [gt for gt in firsts if gt[0] <= (move if move is not None else t) + 2]
            station = g[-1][2] if g else station
            while i < len(ticks) and ticks[i][1] in WALKS: i += 1
            continue
        i += 1
    return out

def main(argv):
    n = int(argv[1]); rows = [json.loads(l) for l in open(os.path.expanduser(argv[2]))]
    write = '--write' in argv
    m = pcmap.PCMap(n)
    ov_path = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
    ov = json.load(open(ov_path))
    ROOMS['rooms'] = {e['object']: e['set']['PCRoom'] for e in ov['patches'] if (e.get('set') or {}).get('PCRoom')}
    # the stations by role: the item whose PCApproach for the role names the object's family
    stations = {}
    for e in ov['patches']:
        ap = (e.get('set') or {}).get('PCApproach') or {}
        for role, d in ap.items():
            if isinstance(d, dict) and d.get('obj'):
                stations.setdefault(role, {})[family(d['obj'])] = e['object']
    import pc_durations_s2
    changed = 0
    for pc_role, role in ROLES.items():
        ex = exits(rows, pc_role)
        if not ex: continue
        by = collections.defaultdict(list)
        for station, after, stand in ex:
            by[station].append((after, stand))
        for station, lst in sorted(by.items()):
            stands = collections.Counter(s for a, s in lst)
            val = stands.most_common(1)[0][0]
            if station == '(start)':
                # PCStart's `depart`: the ticks from the level's first tick to the actor's first move — an
                # actor whose lap begins with a stay (206's neighbour, 108 ticks) has none to write
                print('%-10s %-34s %-26s stands %s -> %d%s' % (role, station, 'PCStart', dict(stands), val, '' if val <= 12 else ' (a stay first: not written)'))
                if write and val <= 12:
                    for e in ov['patches']:
                        st = (e.get('set') or {}).get('PCStart')
                        if st and e.get('component') == role:
                            st['depart'] = val; changed += 1
                continue
            item = stations.get(role, {}).get(family(station))
            # (a stand past six ticks is the station's own wait, not the dispatch — 213's bull controls 75,
            # 214's glass 35: the port's stay models those)
            print('%-10s %-34s %-26s stands %s -> %d%s' % (role, station, item or '(no item)', dict(stands), val, '' if val <= 6 else ' (a wait: not written)'))
            if item and write and val <= 6:
                for e in ov['patches']:
                    if e.get('object') == item and isinstance(e.get('set'), dict) and 'PCDepartTicks' in e['set']:
                        cur = e['set']['PCDepartTicks']; break
                else:
                    cur = {}
                cur = dict(cur); cur[role] = val
                pc_durations_s2._set_key(ov['patches'], item, 'PCDepartTicks', cur); changed += 1
    if write and changed:
        json.dump(ov, open(ov_path, 'w'), ensure_ascii=False, indent=1); open(ov_path, 'a').write('\n')
        print('written %d keys to %s' % (changed, ov_path))

if __name__ == '__main__':
    main(sys.argv)
