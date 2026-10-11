#!/usr/bin/env python3
"""A port run's clicks (tests/run_tricks.py's clicks.json, frames at 60 a second) as the oracle's input
script: {tick, kind, args} per click — an item click = UseObjectMsg on the item's PC object (the overlay's
PCApproach Woody obj), with an inventory type = CombineMsg (IT2_X -> x), a floor click = GoToPosMsg in the
zone's PC room at pc_room_x (runtime/world.py).

    NFH_PROFILE=pc python3 tools/pcoracle/port2script.py <level number> <run dir> > script.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
n = int(sys.argv[1]); run = sys.argv[2]
import scene
lv = scene.Level(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n))
ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
objs = {}
for e in ov['patches']:
    ap = (e.get('set') or {}).get('PCApproach')
    if ap and 'Woody' in ap and 'obj' in ap['Woody']:
        objs[e['object']] = ap['Woody']['obj']
def pc_room_x(zone, x):
    pr = zone.pc_room; w = (zone.right - zone.left) or 1.0
    return pr['x1'] + (x - zone.left) * (pr['x2'] - pr['x1']) / w
out = []
for c in json.load(open(os.path.join(run, 'clicks.json'))):
    tick = int(round(c['frame'] / 5.0))
    if c.get('item'):
        obj = objs.get(c['item'])
        if obj is None:
            sys.stderr.write('no PC object for %s\n' % c['item']); continue
        # (the port's take after an unlock keeps the unlocker in hand: a plain use on the PC)
        prev = out[-1] if out else None
        if c.get('type') and not (prev and prev['kind'] == 'combine' and prev['args'][0] == obj
                                  and prev['args'][1] == c['type'].split('_', 1)[1].lower()):
            out.append({'tick': tick, 'kind': 'combine', 'args': [obj, c['type'].split('_', 1)[1].lower()], 'port': c})
        else:
            out.append({'tick': tick, 'kind': 'use', 'args': [obj], 'port': c})
    else:
        wx, wy = c['world']
        z = lv.zone_at(wx, wy)
        if z is None or getattr(z, 'pc_room', None) is None:
            sys.stderr.write('no zone/room at %s\n' % c['world']); continue
        out.append({'tick': tick, 'kind': 'goto', 'args': [z.pc_room['room'], int(round(pc_room_x(z, wx)))], 'port': c})
for a, b in zip(out, out[1:]):
    if b['tick'] <= a['tick']: b['tick'] = a['tick'] + 1     # one message a tick
json.dump(out, sys.stdout, indent=0)
