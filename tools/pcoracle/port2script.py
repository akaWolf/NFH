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
# the PC data: combine.xml's combinations (an inventory item on an object) and objects.xml's own `use`
# actions of Woody's, for the targets of a combine and of a bare-hand use (tools/pcref/canon.py's folder)
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref'))
import canon, re
folder = canon.pc_level(n)['folder']
X = os.path.expanduser('~/nfh-bench/pcref/pc/%s/x/%s' % ('nfh1' if n < 200 else 'nfh2', folder))
def rd(name):
    b = open(os.path.join(X, name), 'rb').read()
    return b.decode('utf-16') if b[:2] in (b'\xff\xfe', b'\xfe\xff') else b.decode('latin-1')
combos = []
for m in re.finditer(r'<combination name="([^"]+)"([^>]*)>(.*?)</combination>', rd('combine.xml'), re.S):
    if 'wrong="true"' in m.group(2): continue
    combos.append((m.group(1), re.findall(r'<ingredient name="([^"]+)"', m.group(3))))
uses = set()
for m in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', rd('objects.xml'), re.S):
    if re.search(r'<action name="use" actor="woody"', m.group(2)): uses.add(m.group(1))
raw = json.load(open(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n)))
kinds = {}
for o in raw['objects'].values():
    d = o.get('data') or {}
    if d.get('m_GameObject') and ('Item' in str(o.get('type')) or o.get('type') in ('Rake',)):
        kinds[d['m_GameObject']['name']] = o['type']
def family(obj):
    base = obj.split('/')[-1].split('_')[0]
    return [name for name, _ in combos if name.split('/')[-1].split('_')[0] == base] + [obj]
def combine_target(obj, item):
    """the object the PC combines `item` with: the combination whose ingredients are the item and an
    object of the item's PC family (pond/rake_ground_weed: weed on pond/rake_ground)"""
    base = obj.split('/')[-1].split('_')[0]
    for name, ings in combos:
        if item in ings:
            objs = [i for i in ings if '/' in i and i.split('/')[-1].split('_')[0] == base]
            if objs: return objs[0]
    return obj
def use_target(mobile_item, obj):
    """a bare-hand use of a TrickItem: the PC object of its family with Woody's own `use` (pond/rake, not
    the laid rake the neighbour walks to); a SearchItem's click is its take on the overlay's object"""
    if kinds.get(mobile_item) != 'SearchItem':
        base = obj.split('/')[-1].split('_')[0]
        cands = sorted(u for u in uses if u.split('/')[-1].split('_')[0] == base and u.split('/')[0] == obj.split('/')[0])
        if cands: return cands[0]
    return obj
out = []
for c in json.load(open(os.path.join(run, 'clicks.json'))):
    tick = int(round(c['frame'] / 5.0))
    if c.get('item'):
        obj = objs.get(c['item'])
        if obj is None:
            sys.stderr.write('no PC object for %s\n' % c['item']); continue
        # (the port's take after an unlock keeps the unlocker in hand: a plain use on the PC)
        prev = out[-1] if out else None
        item = c['type'].split('_', 1)[1].lower() if c.get('type') else None
        if item and prev and prev['kind'] == 'combine' and prev['port'].get('item') == c['item'] and prev['args'][1] == item:
            continue        # the take after the unlock: the PC's minigame success takes the item itself
        if item:
            out.append({'tick': tick, 'kind': 'combine', 'args': [combine_target(obj, item), item], 'port': c})
        else:
            out.append({'tick': tick, 'kind': 'use', 'args': [use_target(c['item'], obj)], 'port': c})
    else:
        wx, wy = c['world']
        z = lv.zone_at(wx, wy)
        if z is None or getattr(z, 'pc_room', None) is None:
            sys.stderr.write('no zone/room at %s\n' % c['world']); continue
        out.append({'tick': tick, 'kind': 'goto', 'args': [z.pc_room['room'], int(round(pc_room_x(z, wx)))], 'port': c})
for a, b in zip(out, out[1:]):
    if b['tick'] <= a['tick']: b['tick'] = a['tick'] + 1     # one message a tick
json.dump(out, sys.stdout, indent=0)
