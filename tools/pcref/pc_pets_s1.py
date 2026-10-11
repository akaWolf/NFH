#!/usr/bin/env python3
"""The Season 1 pets where the PC has them: level.xml's `dog` / `chili`
actors against the mobile's Alerters.

    python3 tools/pcref/pc_pets_s1.py            # print the pets side by side
    python3 tools/pcref/pc_pets_s1.py --write    # the overlays' patches

Seven of the eight pets stand in the same room on both. The eighth is
112's dog: level_fitness's level.xml lays it asleep in the kitchen (`kit`,
330/410: E12's frames show it there, woken as the skate takes the
neighbour out of the window), where the remaster's Dog is an inactive
GameObject in the living room that nothing references (runtime/README.md,
"Alerters"). A pet the mobile has elsewhere or inactive is placed in the
PC's room: its GameObject active, its Transform at the PC x mapped onto the
room's zone (the zone's walking span onto the room's path, the inverse of
Pawn._pc1_map) at its own height over the floor, its Alerter's Zone that
zone. Written in place; another writer's patches are left alone.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
sys.path.insert(0, ROOT)
X = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
LEVEL_DIR = {101: 'level_peep', 102: 'level_sofa', 103: 'level_mail', 104: 'level_pie', 105: 'level_piano',
             106: 'level_bath', 107: 'level_art', 108: 'level_suntan', 109: 'level_pig', 110: 'level_barbecue',
             111: 'level_laundry', 112: 'level_fitness', 113: 'level_DIY', 114: 'level_hunter'}
PETS = {'dog': 'Dog', 'chili': 'Chili'}
SOURCE = ("the PC's pet (tools/pcref/pc_pets_s1.py): level.xml's actor in its room, the remaster's "
          "Alerter placed there — active, the PC x on the room's zone, its zone")


def pc_pets(n):
    """[(mobile name, PC room, x, y)] of level.xml's pets"""
    room = None
    out = []
    for line in open(os.path.join(X, LEVEL_DIR[n], 'level.xml'), encoding='latin-1'):
        m = re.search(r'<room name="(\w+)"', line)
        if m:
            room = m.group(1)
        m = re.search(r'<actor name="(dog|chili)"[^>]*position="(\d+)/(\d+)"', line)
        if m:
            out.append((PETS[m.group(1)], room, int(m.group(2)), int(m.group(3))))
    return out


def zone_rooms(n):
    """{zone name: PCWalkRoom} from the level's overlay"""
    p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
    ov = json.load(open(p))
    return {e['object']: e['set']['PCWalkRoom'] for e in ov['patches']
            if e.get('component') == 'Zone' and 'PCWalkRoom' in (e.get('set') or {})}


def placements(n):
    """[(name, active, mobile zone, PC room, patches)] — patches None where the
    mobile's pet stands active in the PC's room"""
    import scene
    lv = scene.Level(os.path.join(ROOT, 'levels', 's1', 'Level%d.json' % n))
    objs = lv.objs
    rooms = zone_rooms(n)
    zcomp = {}
    for pid, o in objs.items():
        if o.get('type') == 'Zone':
            zcomp[o['data']['m_GameObject']['name']] = int(pid)
    out = []
    for name, room, px, py in pc_pets(n):
        al = next(((pid, o) for pid, o in objs.items() if o.get('type') == 'Alerter'
                   and o['data']['m_GameObject']['name'] == name), None)
        if al is None:
            continue
        go = objs[str(al[1]['data']['m_GameObject']['path'])]
        active = bool(go['data'].get('active'))
        zname = (al[1]['data'].get('Zone') or {}).get('name')
        if active and rooms.get(zname, {}).get('room') == room:
            out.append((name, active, zname, room, None))
            continue
        zto = next((z for z, r in rooms.items() if r['room'] == room), None)
        z = next(zz for zz in lv.zones if zz.name == zto) if zto else None
        zfrom = next((zz for zz in lv.zones if zz.name == zname), None)
        r = rooms[zto]
        tr = next(o['data'] for o in objs.values() if o.get('type') == 'Transform'
                  and o['data'].get('gameObject') == al[1]['data']['m_GameObject']['path'])
        pos = list(tr.get('world_position') or tr['position'])
        x = z.play_left + (px - r['x1']) / float(r['x2'] - r['x1']) * (z.play_right - z.play_left)
        y = pos[1]
        if zfrom is not None:
            # its own height over its zone's floor, over the new zone's
            y = pos[1] - (zfrom.ty + zfrom.height_delta) + (z.ty + z.height_delta)
        pos = [round(x, 3), round(y, 3), pos[2]]
        patches = [
            {'component': 'GameObject', 'match': {'name': name}, 'set': {'active': True}, 'source': SOURCE},
            {'object': name, 'component': 'Transform', 'set': {'position': pos, 'world_position': pos},
             'source': SOURCE},
            {'object': name, 'component': 'Alerter',
             'set': {'Zone': {'path': zcomp[zto], 'name': zto, 'type': 'Zone'}}, 'source': SOURCE},
        ]
        out.append((name, active, zname, room, patches))
    return out


def write(n, pls):
    p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
    ov = json.load(open(p))
    keep = [e for e in ov['patches'] if e.get('source') != SOURCE]
    for name, _a, _z, _r, patches in pls:
        if patches:
            keep.extend(patches)
    ov['patches'] = keep
    json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
    open(p, 'a').write('\n')


def main(argv):
    do_write = '--write' in argv
    for n in sorted(LEVEL_DIR):
        pls = placements(n)
        for name, active, zname, room, patches in pls:
            print('%d %-6s mobile %s %s, PC %s%s' % (n, name, zname, 'active' if active else 'inactive', room,
                                                   '' if patches is None else ' -> ' + json.dumps(patches[1]['set']['position'])
                                                   + ' ' + patches[2]['set']['Zone']['name']))
        if do_write and any(pl[4] for pl in pls):
            write(n, pls)
            print('   written')


if __name__ == '__main__':
    main(sys.argv[1:])
