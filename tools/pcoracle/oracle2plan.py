#!/usr/bin/env python3
"""The oracle run's inputs, as the game itself logged them, as a port plan replaying them at their ticks:
the GameLogicLog's player messages (UseObjectMsg name= / CombineMsg object= object2= / GoToPosMsg room=
position=) become `until <tick/12>` + the port's op on the mobile item, marked `!` (ungated, no dodging: the
PC's inputs at the PC's seconds and nothing else) (the overlay's PCApproach Woody
`obj` inverted; an inventory item x -> IT2_X by the level's TrickItem inventory names), so the port's run
takes the same inputs at the same level seconds and the two traces compare on one clock (cmp_run.py).

    NFH_PROFILE=pc python3 tools/pcoracle/oracle2plan.py <level number> <GameLogicLog00.xml> > plan.txt"""
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
n = int(sys.argv[1]); logp = sys.argv[2]
ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
items = {}; families = {}
def family(name):
    room, _, base = name.rpartition('/')
    return room, base.split('_')[0]
for e in ov['patches']:
    ap = (e.get('set') or {}).get('PCApproach')
    if ap and 'Woody' in ap and 'obj' in ap['Woody']:
        items.setdefault(ap['Woody']['obj'], e['object'])
        # (the message names the variant the input went to — beachleft/crayfish for the container's
        # item, pond/rake for the rake_ground's: one family)
        families.setdefault(family(ap['Woody']['obj']), e['object'])
if n < 200:
    # Season 1: the items' PC objects by name (pcmap_s1.py — no PCApproach in those overlays)
    sys.path.insert(0, HERE)
    import pcmap_s1
    for it, obj in pcmap_s1.PCMap(n).objs.items():
        items.setdefault(obj, it); families.setdefault(family(obj), it)
def item_of(obj):
    return items.get(obj) or families.get(family(obj))
raw = json.load(open(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n)))
inv = set(); gives = {}; primes = {}; unlockers = {}; hides = set()
for o in raw['objects'].values():
    d = o.get('data') or {}
    name = (d.get('m_GameObject') or {}).get('name')
    if name and o.get('type') == 'HideItem': hides.add(name)      # the port's `hide` leg: he climbs in and stays
    for k in ('RequiredInventory', 'SecondRequiredInventory', 'PrimedInventoryType', 'DexterityUnlocker'):
        v = d.get(k)
        if isinstance(v, str) and v.startswith('IT'): inv.add(v)
    for e in d.get('InventoryItems') or []:
        inv.add(e['Type']); gives.setdefault(name, e['Type'])
    if d.get('PrimingItem') and gives.get(name):
        primes[d['PrimingItem']['name']] = gives[name]        # the priming station <- the held type it primes
    if isinstance(d.get('DexterityUnlocker'), str) and d['DexterityUnlocker'].startswith('IT2'):
        unlockers[name] = d['DexterityUnlocker']
def it_of(pc):
    cands = [v for v in inv if v.split('_', 1)[-1].lower() == pc.lower()]
    return cands[0] if cands else 'IT2_' + pc.capitalize()
import scene
lv = scene.Level(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n))
def _room_of(z):
    # Season 2's PCRoom, Season 1's PCWalkRoom: both {room, x1, x2, floor}
    return getattr(z, 'pc_room', None) or getattr(z, 'pc_walk_room', None)
rooms = {_room_of(z)['room']: z for z in lv.zones if _room_of(z)}
def world_x(room, x):
    z = rooms[room]; pr = _room_of(z)
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
            it = item_of(a['name'])
            if not it: out.append('# no item for %s' % a['name'])
            elif gives.get(it): out.append('take! %s %s' % (it, gives[it]))
            elif it in hides: out.append('hide! %s' % it)
            else: out.append('use! %s' % it)
        elif l.startswith('<CombineMsg'):
            it = item_of(a['object']); held = it_of(a['object2'])
            if not it: out.append('# no item for %s' % a['object'])
            elif primes.get(it) == held: out.append('prime! %s %s' % (it, held))
            elif unlockers.get(it) == held:
                # (the PC's combination takes the item as its game is won; the port's SearchItem wants
                # the take click after its unlock — right after, no clock)
                out.append('unlock! %s %s' % (it, held))
                if gives.get(it): out.append('take! %s %s' % (it, gives[it]))
            else: out.append('usewith! %s %s' % (it, held))
        else:
            wx, zone = world_x(a['room'], int(a['position'].split('/')[0]))
            out.append('park! %s   # x %.3f' % (zone, wx))
print('# replayed from %s (tools/pcoracle/oracle2plan.py)' % os.path.basename(logp))
print('\n'.join(out))
until = next((a[len('--until='):] for a in sys.argv if a.startswith('--until=')), None)
if until:
    print('until %s' % until)          # the run goes on to the clock: an idle lap's record after the park
