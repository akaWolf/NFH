#!/usr/bin/env python3
"""The oracle run's inputs, as the game itself logged them, as a port plan replaying them at their ticks:
the GameLogicLog's player messages (UseObjectMsg name= / CombineMsg object= object2= / GoToPosMsg room=
position=) become `until <tick/12>` + the port's op on the mobile item (the overlay's PCApproach Woody
`obj` inverted; an inventory item x -> IT2_X by the level's TrickItem inventory names), so the port's run
takes the same inputs at the same level seconds and the two traces compare on one clock (cmp_run.py).

    NFH_PROFILE=pc python3 tools/pcoracle/oracle2plan.py <level number> <GameLogicLog00.xml> > plan.txt"""
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
n = int(sys.argv[1]); logp = sys.argv[2]
ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
items = {}
for e in ov['patches']:
    ap = (e.get('set') or {}).get('PCApproach')
    if ap and 'Woody' in ap and 'obj' in ap['Woody']:
        items.setdefault(ap['Woody']['obj'], e['object'])
raw = json.load(open(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n)))
inv = set()
for o in raw['objects'].values():
    d = o.get('data') or {}
    for k in ('RequiredInventory', 'SecondRequiredInventory', 'PrimedInventoryType', 'InventoryType', 'DexterityUnlocker'):
        v = d.get(k)
        if isinstance(v, str) and v.startswith('IT'): inv.add(v)
def it_of(pc):
    cands = [v for v in inv if v.split('_', 1)[-1].lower() == pc.lower()]
    return cands[0] if cands else 'IT2_' + pc.capitalize()
import scene
lv = scene.Level(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n))
rooms = {z.pc_room['room']: z for z in lv.zones if getattr(z, 'pc_room', None)}
def world_x(room, x):
    z = rooms[room]; pr = z.pc_room
    return z.left + (x - pr['x1']) * (z.right - z.left) / float(pr['x2'] - pr['x1']), z.name
s = open(logp, 'rb').read().decode('utf-16')
t = None; t0 = None; out = []
for l in s.split('\n'):
    l = l.strip()
    if l.startswith('<time value='): t = int(l.split('"')[1])
    elif '<StartLevelMsg' in l and t0 is None: t0 = t
    elif l.startswith('<UseObjectMsg') or l.startswith('<CombineMsg') or l.startswith('<GoToPosMsg'):
        a = dict(re.findall(r'(\w+)="([^"]*)"', l)); tick = t - (t0 or 0)
        out.append('until %.4f' % (tick / 12.0))
        if l.startswith('<UseObjectMsg'):
            it = items.get(a['name'])
            out.append('take %s' % it if it else '# no item for %s' % a['name'])
        elif l.startswith('<CombineMsg'):
            it = items.get(a['object'])
            out.append('usewith %s %s' % (it, it_of(a['object2'])) if it else '# no item for %s' % a['object'])
        else:
            wx, zone = world_x(a['room'], int(a['position'].split('/')[0]))
            out.append('park %s   # x %.3f' % (zone, wx))
print('# replayed from %s (tools/pcoracle/oracle2plan.py)' % os.path.basename(logp))
print('\n'.join(out))
