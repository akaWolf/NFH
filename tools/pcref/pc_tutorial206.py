#!/usr/bin/env python3
"""The PC's 206 lesson (ship2) into the levels/pc overlay.

    python3 tools/pcref/pc_tutorial206.py            # print the data
    python3 tools/pcref/pc_tutorial206.py --write    # PCTutorial into Level206.overlay.json

The PC runs 206's pillow lesson as three GameLogic.dll scripts
(docs/PC_FIDELITY.md "206's lesson"): the invisible `aux` actor's director
(fcn.1002b64d: its steps 0x1002b5e7 ... 0x1002afee, the messages through
fcn.100101f3, the markers through fcn.10042077), the Mother's (fcn.1002c41x:
0x1002c3af ... 0x1002bb39) and the neighbour's (fcn.1002f1bb: 0x1002f15a ...
0x1002e926, then the lap from 0x1002e63c), which hand each other the
behaviours `call`, `order`, `mother_pillow`, `tutorial` and `mother_fight`
(fcn.1004000a, the actions' behavior= records) and wait on them
(fcn.10013269). The runtime (runtime/tutorial.py TutorialPC206) keeps the
steps; this writes what they read from the level data:

- texts: ship2/strings.xml's `tutorial` strings, the director's messages by
  their code names (step1 ... step5, step2a, step3a);
- woody / neighbor / mother: level.xml's starts (the neighbour at Fifi,
  laughing — `laughleft` —, the Mother by her deck chair), in the mobile
  zones by the overlay's PCRoom;
- ticks: the lesson's actions' jobs (objects.xml `time` or the Loader's auto
  frames, + 2: lap_model_s2.Data.action_ticks) — the Mother's pillow_slip,
  callneighbor, order, the chair's enter and leave, the fart and the fight on
  him, the neighbour's take and give; `fart_record` the fartbag record's
  `time` into the fart;
- lower: the rooms fcn.1000ed06 tests Woody in for step3a (bottomright,
  bottomleft: the lower deck);
- items / inventory: the PC objects and inventory names against the mobile
  items (the overlay's PCApproach `obj`) and inventory ids.
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
N = 206
INVENTORY = {'fartbag': 'IT2_Fartbag'}
# the director's markers and gates, the Mother's and the neighbour's stations:
# the PC objects the scripts name, as the mobile items (the Mother's deck
# chair steps all walk to topleft/deckchair's `mother` hotspot)
ITEMS = {'bottomleft/toybox': 'ToyBox', 'topright/pillows': 'Pillows',
         'topright/pillows_manip': 'Pillows', 'topright/ventpipe': 'Pipe',
         'topleft/deckchair': 'DeckChair', 'topleft/fifi': 'DogFifi'}
# (object, action, actor) of the lesson's actions, by the name the runtime reads
ACTIONS = {'pillow_slip': ('topleft_deckchair', 'pillow_slip', 'mother'),
           'callneighbor': ('mother', 'callneighbor', 'mother'),
           'order': ('mother', 'order', 'mother'),
           'enter': ('topleft_deckchair', 'enter', 'mother'),
           'leave': ('topleft_deckchair', 'leave', 'mother'),
           'fart': ('topleft_deckchair', 'fart', 'mother'),
           'fight': ('neighbor', 'fight', 'mother'),
           'take': ('topright_pillows', 'take', 'neighbor'),
           'give': ('topleft_deckchair', 'give', 'neighbor')}


def overlay():
    return json.load(open('%s/levels/pc/Level%d.overlay.json' % (ROOT, N)))


def build():
    X = '%s/nfh2/x' % canon.ROOT
    folder = canon.pc_level(N)['folder']
    lv = canon.read('%s/%s/level.xml' % (X, folder))
    strings = canon.read('%s/%s/strings.xml' % (X, folder))
    ov = overlay()
    rooms = {}
    for p in ov['patches']:
        s = p.get('set') or {}
        if 'PCRoom' in s:
            rooms[s['PCRoom']['room']] = p['object']
    out = {'texts': {}, 'rooms': rooms, 'items': ITEMS, 'inventory': INVENTORY,
           'lower': [rooms['bottomright'], rooms['bottomleft']]}
    for m in re.finditer(r'<string name="([^"]+)" category="tutorial" text="([^"]*)"', strings):
        out['texts'][m.group(1)] = html.unescape(m.group(2)).replace('\r', '')
    pos = {}
    for rm in re.finditer(r'<room name="(\w+)"[^>]*>(.*?)</room>', lv, re.S):
        for o in re.finditer(r'<object name="([^"]+)" position="(-?\d+)/(-?\d+)"([^>]*)/>', rm.group(2)):
            a = re.search(r'animation="([^"]*)"', o.group(4))
            pos[o.group(1)] = (rm.group(1), int(o.group(2)), int(o.group(3)), a.group(1) if a else None)
    for who in ('woody', 'neighbor', 'mother'):
        room, x, y, anim = pos[who]
        out[who] = [rooms[room], x, y, anim]
    sys.path.insert(0, HERE)
    import lap_model_s2
    d = lap_model_s2.Data(N)
    out['ticks'] = {k: d.action_ticks(o, a, who) for k, (o, a, who) in ACTIONS.items()}
    recs = d.tricks('topleft_deckchair', 'fart', 'mother')
    out['fart_record'] = recs[0][1] if recs else None
    return out


NOTE = (" The lesson (tools/pcref/pc_tutorial206.py): PCTutorial on the TutorialScriptCameraNFH2206 ="
        " the PC's own 206 pillow lesson the profile runs in place of the mobile's LevelScript and"
        " camera script (runtime/tutorial.py TutorialPC206, GameLogic.dll's `aux` director, the"
        " Mother's and the neighbour's scripts): the director's texts (ship2/strings.xml), the"
        " starts of Woody, the neighbour and the Mother (level.xml, in the mobile zones by PCRoom),"
        " the lesson's actions' job ticks (objects.xml, generic/objects.xml), the lower deck's"
        " rooms, the PC objects and inventory against the mobile items.")


def main(argv):
    data = build()
    if '--write' not in argv:
        print(json.dumps({k: v for k, v in data.items() if k != 'texts'}, indent=1))
        for k, v in data['texts'].items():
            print('%-8s %s' % (k, v[:100].replace('\n', ' ')))
        return 0
    p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, N)
    ov = overlay()
    patches = ov.get('patches', [])
    e = next((e for e in patches if e.get('component') == 'TutorialScriptCameraNFH2206'), None)
    if e is None:
        e = {'object': 'TutorialScriptCamera', 'component': 'TutorialScriptCameraNFH2206', 'set': {}}
        patches.append(e)
    e['set']['PCTutorial'] = data
    ov['patches'] = patches
    src = ov.get('source', '')
    i = src.find(' The lesson (tools/pcref/pc_tutorial206.py)')
    if i >= 0:
        j = src.find(' The ', i + 1)
        src = src[:i] + (src[j:] if j >= 0 else '')
    ov['source'] = src + NOTE
    json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
    open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
