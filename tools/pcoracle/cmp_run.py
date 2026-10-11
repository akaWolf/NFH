#!/usr/bin/env python3
"""The oracle's trace against the port's run of the same inputs, side by side.

    python3 tools/pcoracle/cmp_run.py ~/nfh-bench/wine/logs/oracle_cn_b1.jsonl ~/nfh-bench/runs/<run>/s2_Level202 [--all]

The PC side (oracle.py's trace): the neighbour's station actions (DoAction enter / use / leave and the
others on his objects), his icon changes, behaviour posts and SHOUTs, Woody's actions, the injected inputs —
by level tick (12 a second). The port side (state.jsonl + clicks.json): the Rottweiler routine's item /
state / anim transitions, the think icon, the trick count, the clicks — by seconds. Printed interleaved on
one clock so the first divergence stands out; --all keeps the walk-step transitions too."""
import json, os, sys

def load_oracle(p):
    rows = [json.loads(l) for l in open(os.path.expanduser(p))]
    ev = []
    icon = None
    for r in rows:
        t = r['tick'] / 12.0
        if r['ev'] == 'action':
            a = r['args']
            obj, act = a[1], a[2]
            if obj == 'woody' and act == 'start':
                continue
            ev.append((t, 'PC', 'action %s %s' % (obj, act)))
        elif r['ev'] == 'icon' and r['args'][0] == 'neighbor':
            ic = r['args'][1]
            if ic != icon:
                icon = ic; ev.append((t, 'PC', 'icon %r' % (ic,)))
        elif r['ev'] in ('post', 'shout'):
            ev.append((t, 'PC', '%s %s' % (r['ev'], r['args'][:3])))
        elif r['ev'] == 'injected':
            s = r['step']; ev.append((t, 'PC', 'INPUT %s %s' % (s['kind'], ' '.join(map(str, s['args'])))))
    return ev

def load_port(d, walks=False):
    d = os.path.expanduser(d)
    st = [json.loads(l) for l in open(os.path.join(d, 'state.jsonl'))]
    ev = []
    last = None; tricks = 0
    for s in st:
        r = next(x for x in s['routines'] if x['role'] == 'Rottweiler')
        k = (s['hud'].get('think') if s['hud'] else None, r['item'], r['state'], r['anim'])
        if k != last:
            if walks or last is None or k[3] not in ('Walk_Left', 'Walk_Right', 'Walk_Up', 'Walk_Down', 'Stand_Left', 'Stand_Right', 'Stand_Up', 'Stand_Down') \
                    or k[:3] != last[:3]:
                ev.append((s['t'], 'port', 'think=%r %s %s %s' % (k[0], k[1], k[2], k[3])))
            last = k
        if s['game']['tricks'] != tricks:
            tricks = s['game']['tricks']; ev.append((s['t'], 'port', 'TRICKS %d' % tricks))
    try:
        for c in json.load(open(os.path.join(d, 'clicks.json'))):
            ev.append((c['frame'] / 60.0, 'port', 'INPUT %s %s' % (c.get('item'), c.get('type'))))
    except OSError:
        pass
    return ev

def main(argv):
    walks = '--all' in argv
    args = [a for a in argv[1:] if not a.startswith('--')]
    ev = load_oracle(args[0]) + load_port(args[1], walks)
    ev.sort(key=lambda e: (e[0], e[1] != 'PC'))
    for t, side, text in ev:
        print('%7.2f %-4s %s' % (t, side, text))

if __name__ == '__main__':
    main(sys.argv)
