#!/usr/bin/env python3
"""The Season 1 walk of the PC original into the levels/pc overlays (the neighbour and Woody).

    python3 tools/pcref/pc_walks_s1.py            # print the map, the doors and the stations
    python3 tools/pcref/pc_walks_s1.py --write    # PCWalkRoom, PCWalkDoor, PCWalkPoint, PCDoorTicks

game.exe walks a GOTO (the step's vtable 0x4e19e8, update 0x44a7b0) through a walk
job it pushes with the run-now flag 1 (vtable 0x4e53d0, update 0x475c80): the room
list of the path, and for each next room a mover to the near door's standing point
— the door's entity position plus the door type's hotspot of the actor (`neighbor`,
`woody`; fcn.00445aa0) — then the door step (vtable 0x4e5370, update 0x474590: the
actor placed at the far door's point, and one ACTION step of the near door's `enter`
and the far door's `leave` started together, fcn.004741e0 over fcn.00478030), and at
the end a mover to the target's hotspot; the movers are pushed with the run-now flag
1, so a leg's first move falls in the tick the one before it ends. A mover (vtable
0x4e59e8, update 0x47cb50) moves one axis a tick at the facing's speed record: while
x is off the target's, y goes to the room's floor line first (fcn.0044bac0 on the
actor's room: its path's y), then x along it, and once x is the target's, y to the
target's height; clamped at the target, the arrival read in the update of its last
move. A walk between two raised points — two back doors' hotspots 50 px above the
floor, two stations' 30 — so goes down to the floor and up again, as the mobile
scene's paths do on their own geometry.

The overlay entries, in px of the PC scene (the room's own coordinates):
  Zone       PCWalkRoom   {'room', 'x1', 'x2' (the room's path), 'floor'}
  Door       PCWalkDoor   {role: {'near': [x, y], 'far': [x, y]}}: the near door's
                          standing point and the far door's (`<actor>_out`), the
                          neighbour's and Woody's
             PCDoorTicks  {role: {'enter': ticks, 'leave': ticks}}: the door's own
                          `enter` / `leave` ACTION steps (time + 2, lap_model.
                          job_ticks) where they differ from its type's
                          (pcprofile.DOOR_TICKS) — the front door's pair for Woody:
                          anc/fro's `enter` 18 where a right door has 15, fro/anc's
                          `leave` 23 or 25 where a left door has 24 (107 and 112
                          the type's)
  items      PCWalkPoint  {'Rottweiler': [x, y, room], 'Woody': [x, y, room]}: the
                          hotspot of the PC object the neighbour's station walks to
                          (the lap model's GOTO of the station tools/pcref/
                          pc_durations.py pairs the item with) — a list of them
                          where the visits walk to different objects — and the
                          `woody` hotspot of the object Woody's action on the item
                          takes place at (`woody_targets`)
The zones map to the rooms geometrically (the rooms' path centres against the
zones', the house at 96 px a unit, one shift a level), the exit porch through the
door graph; a door pair of the mobile scene is the PC door of its two rooms.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import canon       # noqa: E402
import lap_model   # noqa: E402
import pc_durations  # noqa: E402
from runtime import pcprofile  # noqa: E402

SCRATCH = os.environ.get('LAP_TOKENS')


def pc_rooms(n):
    """room -> {ox, oy, x1, x2, y} of level.xml"""
    pl = canon.pc_level(n)
    lv = canon.read(lap_model.X + '/' + pl['folder'] + '/level.xml')
    out = {}
    for rm in re.finditer(r'<room name="(\w+)" offset="([^"]+)" path1="([^"]+)" path2="([^"]+)">', lv):
        ox, oy = lap_model.xy(rm.group(2))
        x1, y1 = lap_model.xy(rm.group(3))
        x2, _ = lap_model.xy(rm.group(4))
        out[rm.group(1)] = dict(ox=ox, oy=oy, x1=min(x1, x2), x2=max(x1, x2), y=y1)
    return out


def zone_map(M, R, L):
    """zone name -> PC room: one shift of the house for the level, the zone's
    floor centre to the nearest room's; a room claimed twice goes to the
    nearer zone, the other one to a free room its neighbour zone has a door to"""
    zs = [(z.name, (z.play_left + z.play_right) / 2.0, z.y) for z in M.zones]
    rs = [(k, (r['ox'] + (r['x1'] + r['x2']) / 2.0) / 96.0, -(r['oy'] + r['y']) / 96.0) for k, r in R.items()]
    best = None
    for _zn, zx, zy in zs:
        for _rn, rx, ry in rs:
            bx, by = zx - rx, zy - ry
            cost = 0.0
            assign = {}
            for zn2, zx2, zy2 in zs:
                d, rb = min((abs(zx2 - (rx2 + bx)) + 3 * abs(zy2 - (ry2 + by)), rn2) for rn2, rx2, ry2 in rs)
                cost += d
                assign[zn2] = (rb, d)
            if best is None or cost < best[0]:
                best = (cost, assign)
    assign = best[1]
    out = {}
    taken = {}
    for zn, (rn, d) in sorted(assign.items(), key=lambda kv: kv[1][1]):
        if rn not in taken:
            out[zn] = rn
            taken[rn] = zn
    zname = {z.pid: z.name for z in M.zones}
    for zn in [z for z in assign if z not in out]:
        # the door graph: a room with a door to a neighbour zone's room, not taken
        nbs = set()
        for d in M.doors:
            if zname.get(d.zone) != zn or d.link_to is None:
                continue
            o = M.door_by_pid(d.link_to)
            if o is not None and zname.get(o.zone) in out:
                nbs.add(out[zname[o.zone]])
        cands = [r for r in R if r not in taken and any(('%s/%s' % (nb, r)) in L.rooms.get(nb, {}).get('doors', {}) for nb in nbs)]
        if len(cands) == 1:
            out[zn] = cands[0]
            taken[cands[0]] = zn
    return out


def station_targets(n):
    """mobile item -> the PC object its station walks to (the last GOTO of the
    paired ICON group of the lap model's lap 1, before the paired actions)"""
    L = lap_model.Level(n)
    toks = lap_model.tokens_of([n], SCRATCH, lap_model.CYCLE)
    legs = lap_model.model(L, toks[n], steady=False)
    groups = []
    for kind, text, t in legs:
        if kind == 'icon':
            groups.append({'icon': text.split()[-1], 'seq': []})
            continue
        if not groups:
            continue
        if kind in ('walk', 'intro'):
            obj = text.split(' -> ')[-1].split()[0]
            if obj not in L.doors and not obj.startswith('room'):
                groups[-1]['seq'].append(('goto', obj))
        elif kind == 'action':
            groups[-1]['seq'].append(('act', text.split()[-1]))
    # the lap's wrap: the first station's GOTO is the intro of lap 1
    k_of = {}
    out = {}
    for g in groups:
        k_of.setdefault(g['icon'], []).append(g)
    for entry in pc_durations.PAIRS.get(n, ()):
        item, icon, k = entry[0], entry[1], entry[2]
        acts = entry[3] if len(entry) > 3 and isinstance(entry[3], tuple) else None
        gs = k_of.get(icon) or []
        if k >= len(gs):
            continue
        seq = gs[k]['seq']
        target = None
        for kind, v in seq:
            if kind == 'goto':
                target = v
            elif kind == 'act' and acts and any(v == a or v in a.split('+') for a in acts):
                break
        if target is None:
            # no walk in the group: the station of the group before it
            i = groups.index(gs[k])
            for g in reversed(groups[:i]):
                gt = [v for kd, v in g['seq'] if kd == 'goto']
                if gt:
                    target = gt[-1]
                    break
        if target is not None:
            out.setdefault(item, []).append(target)
    return out


def woody_targets(n):
    """mobile item -> the PC object Woody's action on it takes place at
    (tools/pcref/pc_woody.py's pairing): the base object of the trick's
    combination (combine.xml, the item's PC trick of pc_reactions.TABLE), the
    one container whose `<content>`s hold the SearchItem's inventory, the
    hideout of the HideItem's name; a trick laid on a room's floor has none"""
    import pc_reactions
    import pc_woody
    L = lap_model.Level(n)
    combos = pc_woody.combinations(L)
    items = pc_woody.mobile_items(n)
    out = {}
    for item, spec in pc_reactions.TABLE.get(n, {}).items():
        if item not in items:
            continue
        base = next((i for i in (combos.get(spec['pc']) or []) if '/' in i), None)
        if base is not None:
            out[item] = base
    d = json.load(open(os.path.join(ROOT, 'levels', 's1', 'Level%d.json' % n)))['objects']
    ob = canon.read(os.path.join(lap_model.X, L.folder, 'objects.xml'))
    contents = {}
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', ob, re.S):
        cs = set(re.findall(r'<content name="([^"]+)"', om.group(2)))
        if cs:
            contents[om.group(1)] = cs
    for o in d.values():
        dd = o.get('data') or {}
        nm = (dd.get('m_GameObject') or {}).get('name')
        if not nm or nm in out:
            continue
        if o.get('type') == 'SearchItem':
            invs = {canon.norm(i.get('Type')) for i in (dd.get('InventoryItems') or [])
                    if isinstance(i, dict) and i.get('Type')}
            cands = [obj for obj, cs in contents.items() if invs & cs]
            if len(cands) == 1:
                out[nm] = cands[0]
        elif o.get('type') == 'HideItem':
            cands = [obj for obj in L.objects if obj.split('/')[-1] == nm.lower()
                     and re.search(r'<object name="%s"[^>]*>(?:(?!</object>).)*<flag name="hideout"'
                                   % re.escape(obj), ob, re.S)]
            if len(cands) == 1:
                out[nm] = cands[0]
    return out


def level_data(n):
    from runtime.scene import Level
    M = Level(os.path.join(ROOT, 'levels', 's1', 'Level%d.json' % n))
    L = lap_model.Level(n)
    R = pc_rooms(n)
    zmap = zone_map(M, R, L)
    zname = {z.pid: z.name for z in M.zones}
    rooms = {}
    for z in M.zones:
        rn = zmap.get(z.name)
        if rn is None or rn == 'fro':
            # the porch: the PC's `fro` is the street's whole path (50-1840 px,
            # its floor 218), the mobile's zone the steps by the front door —
            # no room to map a place of it into
            continue
        r = L.rooms.get(rn)
        if r is None:
            continue
        rooms[z.name] = {'room': rn, 'x1': r['x1'], 'x2': r['x2'], 'floor': r['y']}
    doors = {}
    own = {}
    for d in M.doors:
        if d.link_to is None:
            continue
        o = M.door_by_pid(d.link_to)
        if o is None:
            continue
        a, b = zmap.get(zname.get(d.zone)), zmap.get(zname.get(o.zone))
        if a is None or b is None:
            continue
        entry = {}
        side = (d.door_type or '').replace('DT_', '')
        for role, actor in (('Rottweiler', 'neighbor'), ('Woody', 'woody')):
            near = L.door_point('%s/%s' % (a, b), actor=actor)
            far = L.door_point('%s/%s' % (b, a), out=True, actor=actor)
            if near is not None and far is not None:
                entry[role] = {'near': list(near), 'far': list(far)}
            # the door's own figures against its type's (the strips' pace)
            typ = pcprofile.DOOR_TICKS.get((role, side))
            for i, act in enumerate(('enter', 'leave')):
                t = L.job_ticks('%s/%s' % (a, b), act, actor=actor)
                if t is not None and typ is not None and t != typ[i]:
                    own.setdefault((d.name, zname.get(d.zone)), {}).setdefault(role, {})[act] = t
        if entry:
            doors[(d.name, zname.get(d.zone))] = entry
    points = {}
    for item, objs in station_targets(n).items():
        pts = [list(L.object_point(o)[1:]) + [L.object_point(o)[0]] for o in objs if L.object_point(o)]
        if not pts:
            continue
        # one point, or one a visit where the visits walk to different objects
        # (107's camera: the posing spot, then the camera) — the
        # visits cycle as PCUseSeconds' do (Routine._pc_visit_seconds)
        points[item] = {'Rottweiler': pts[0] if all(p == pts[0] for p in pts) else pts}
    for item, obj in woody_targets(n).items():
        p = L.object_point(obj, actor='woody')
        if p is not None:
            points.setdefault(item, {})['Woody'] = [p[1], p[2], p[0]]
    return zmap, rooms, doors, points, own


def item_kind_hide(n, name):
    """the component of a hideout (Woody's walk points reach the HideItems too)"""
    d = json.load(open(os.path.join(ROOT, 'levels', 's1', 'Level%d.json' % n)))['objects']
    for o in d.values():
        dd = o.get('data') or {}
        if o['type'] == 'HideItem' and (dd.get('m_GameObject') or {}).get('name') == name:
            return 'HideItem'
    return None


def write(n, rooms, doors, points, own):
    p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
    ov = json.load(open(p))
    keys = ('PCWalkRoom', 'PCWalkDoor', 'PCWalkPoint', 'PCDoorTicks')
    for e in ov['patches']:
        for k in keys:
            (e.get('set') or {}).pop(k, None)
    ov['patches'] = [e for e in ov['patches'] if e.get('set') != {}]
    src = ("the Season 1 walk (tools/pcref/pc_walks_s1.py: game.exe's GOTO, walk job and "
           "movers; level.xml's rooms and doors, objects.xml's hotspots)")
    for zn, v in sorted(rooms.items()):
        ov['patches'].append({'object': zn, 'component': 'Zone', 'set': {'PCWalkRoom': v}, 'source': src})
    for dk in sorted(set(doors) | set(own)):
        dn, zn = dk
        st = {}
        if dk in doors:
            st['PCWalkDoor'] = doors[dk]
        if dk in own:
            st['PCDoorTicks'] = own[dk]
        ov['patches'].append({'object': dn, 'component': 'Door', 'zone': zn, 'set': st,
                              'source': src if dk not in own else
                              src[:-1] + "; the door's own `enter`/`leave` records where they differ "
                              "from its type's, pcprofile.DOOR_TICKS)"})
    for item, v in sorted(points.items()):
        kind = pc_durations.item_kind(n, item) or item_kind_hide(n, item) or 'TrickItem'
        ov['patches'].append({'object': item, 'component': kind, 'set': {'PCWalkPoint': v},
                              'source': src})
    json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
    open(p, 'a').write('\n')


def main(argv):
    do_write = '--write' in argv
    levels = [int(a) for a in argv[1:] if a.isdigit()] or list(range(101, 115))
    for n in levels:
        zmap, rooms, doors, points, own = level_data(n)
        print('%d: rooms %s' % (n, ' '.join('%s=%s' % kv for kv in sorted(zmap.items()))))
        print('   doors %s' % ' '.join('%s@%s %s' % (dn, zn, ' '.join('%s %s>%s' % (r[0], e['near'], e['far'])
                                                                   for r, e in sorted(v.items())))
                                     for (dn, zn), v in sorted(doors.items())))
        print('   points %s' % ' '.join('%s %s' % (k, v) for k, v in sorted(points.items())))
        print('   own door ticks %s' % ' '.join('%s@%s %s' % (dn, zn, v) for (dn, zn), v in sorted(own.items())))
        if do_write:
            write(n, rooms, doors, points, own)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
