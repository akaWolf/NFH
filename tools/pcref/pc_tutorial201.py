#!/usr/bin/env python3
"""The PC's 201 tutorial (ship1) into the levels/pc overlay.

    python3 tools/pcref/pc_tutorial201.py            # print the data
    python3 tools/pcref/pc_tutorial201.py --write    # PCTutorial into Level201.overlay.json

The PC runs 201's tutorial as two GameLogic.dll scripts (docs/PC_FIDELITY.md
"201's tutorial"): the invisible `aux` actor's director (its steps
0x1002818c ... 0x10026640, the messages through fcn.100101f3, the welcome
box fcn.1001029b) and the neighbour's (0x1002aac8 ... 0x100291cf), which hand
each other the `tutorial` behaviour (fcn.1004000a) and wait on it
(fcn.10013269). The runtime (runtime/tutorial.py TutorialPC201) keeps the
steps; this writes what they read from the level data:

- texts: ship1/strings.xml's `tutorial` strings and the `content` welcome —
  the director's messages by their code names (waypoint1 ... danke);
- waypoints: level.xml's waypoint1-4 (gfx `sign`, the woody hotspot at 0/0)
  in their rooms, the mobile zone by the overlay's PCRoom;
- at_px: fcn.1000e2bd's "actor at object" tolerance, GameLogic.dll's dword at
  0x100cc814 (the positions' y equal and |dx| at most this);
- woody: level.xml's woody (the PC's start and respawn point);
- entry / shout: objects.xml's `entry` hotspots neighbor_entry (the bridge,
  where 0x1002968d puts him after the crash_long, fcn.100418f6) and
  neighbor_shout (the spot 0x100294fc runs him to);
- wheeze: generic/anims.xml's frames of the neighbour's wheeze (0x100294fc's
  DoAction, 12 a second);
- rail_repair: the ticks of reling_open's `repair` (objects.xml, the neighbour's
  uselow0), which his first rail visit after the combo plays before the look
  (0x10029063);
- items / inventory: the PC objects and inventory names against the mobile
  items (the overlay's PCApproach `obj`) and inventory ids.
"""
import html
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canon  # noqa: E402
from exe_scripts import sections  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
N = 201
GL = os.path.expanduser('~/nfh-bench/pcref/pc/nfh2/bin/GameLogic.dll')
AT_PX_VA = 0x100cc814            # fcn.1000e2bd: cmp |dx|, [0x100cc814]
INVENTORY = {'soap': 'IT2_Soap', 'hairpin': 'IT2_Hairpin', 'knife': 'IT2_Knife',
             'pipetongs': 'IT2_Pipetongs', 'spaghetti': 'IT2_Spaghetti'}


def dword(path, va, base=0x10000000):
    b = open(path, 'rb').read()
    for sva, vsize, raw, rsize in sections(b, base):
        if sva <= va < sva + rsize:
            return struct.unpack_from('<I', b, raw + (va - sva))[0]
    return None


def overlay():
    return json.load(open('%s/levels/pc/Level%d.overlay.json' % (ROOT, N)))


def build():
    X = '%s/nfh2/x' % canon.ROOT
    folder = canon.pc_level(N)['folder']
    lv = canon.read('%s/%s/level.xml' % (X, folder))
    objs = canon.read('%s/%s/objects.xml' % (X, folder))
    strings = canon.read('%s/%s/strings.xml' % (X, folder))
    ganims = canon.read('%s/generic/anims.xml' % X)
    ov = overlay()
    rooms = {}
    items = {}
    for p in ov['patches']:
        s = p.get('set') or {}
        if 'PCRoom' in s:
            rooms[s['PCRoom']['room']] = p['object']
        for role, ap in (s.get('PCApproach') or {}).items():
            items.setdefault(ap['obj'], p['object'])
    out = {'texts': {}, 'waypoints': {}, 'rooms': rooms, 'items': items,
           'inventory': INVENTORY}
    for m in re.finditer(r'<string name="([^"]+)" category="(tutorial|content)" text="([^"]*)"', strings):
        out['texts'][m.group(1)] = html.unescape(m.group(3)).replace('\r', '')
    # the objects in their rooms (level.xml): position x/y
    pos = {}
    for rm in re.finditer(r'<room name="(\w+)"[^>]*>(.*?)</room>', lv, re.S):
        for o in re.finditer(r'<object name="([^"]+)" position="(-?\d+)/(-?\d+)"', rm.group(2)):
            pos[o.group(1)] = (rm.group(1), int(o.group(2)), int(o.group(3)))
    for w in ('waypoint1', 'waypoint2', 'waypoint3', 'waypoint4'):
        room, x, y = pos[w]
        out['waypoints'][w] = [rooms[room], x, y]
    room, x, y = pos['woody']
    out['woody'] = [rooms[room], x, y]
    ent = re.search(r'<object name="entry">(.*?)</object>', objs, re.S).group(1)
    hs = dict((m.group(1), (int(m.group(2)), int(m.group(3)))) for m in re.finditer(
        r'<hotspot name="(\w+)" offset="(-?\d+)/(-?\d+)"', ent))
    room = pos['entry'][0]
    out['entry'] = [rooms[room]] + list(hs['neighbor_entry'])
    out['shout'] = [rooms[room]] + list(hs['neighbor_shout'])
    m = re.search(r'<object name="neighbor"[^>]*>(.*?)</object>', ganims, re.S)
    body = m.group(1) if m else ''
    w = re.search(r'<animation name="wheeze"[^>]*>(.*?)</animation>', body, re.S)
    out['wheeze'] = len(re.findall(r'<frame\b', w.group(1))) if w else None
    out['at_px'] = dword(GL, AT_PX_VA)
    # the open rail's repair on his first visit after the combo (0x10029063)
    import lap_model_s2
    out['rail_repair'] = lap_model_s2.Data(N).action_ticks('topright_reling_open', 'repair')
    return out


NOTE = (" The tutorial (tools/pcref/pc_tutorial201.py): PCTutorial on the TutorialScriptCamera ="
        " the PC's own 201 tutorial the profile runs in place of the mobile's LevelScript and"
        " camera script (runtime/tutorial.py TutorialPC201, GameLogic.dll's `aux` director and"
        " neighbour scripts): the director's texts (ship1/strings.xml), the four waypoints and"
        " Woody's start (level.xml, in the mobile zones by PCRoom), the entry's neighbor_entry /"
        " neighbor_shout hotspots (objects.xml), the neighbour's wheeze frames (generic/anims.xml),"
        " the at-object tolerance of fcn.1000e2bd (GameLogic.dll 0x100cc814), the PC objects and"
        " inventory against the mobile items.")


def main(argv):
    data = build()
    if '--write' not in argv:
        print(json.dumps({k: v for k, v in data.items() if k != 'texts'}, indent=1))
        for k, v in data['texts'].items():
            print('%-14s %s' % (k, v[:90].replace('\n', ' ')))
        return 0
    p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, N)
    ov = overlay()
    patches = ov.get('patches', [])
    e = next((e for e in patches if e.get('component') == 'TutorialScriptCameraNFH2'), None)
    if e is None:
        e = {'object': 'TutorialScriptCamera', 'component': 'TutorialScriptCameraNFH2', 'set': {}}
        patches.append(e)
    e['set']['PCTutorial'] = data
    ov['patches'] = patches
    src = ov.get('source', '')
    i = src.find(' The tutorial (tools/pcref/pc_tutorial201.py)')
    if i >= 0:
        j = src.find(' The ', i + 1)
        src = src[:i] + (src[j:] if j >= 0 else '')
    ov['source'] = src + NOTE
    json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
    open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
