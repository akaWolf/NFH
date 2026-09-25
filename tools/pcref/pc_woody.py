#!/usr/bin/env python3
"""Woody's trick actions from the PC data into the Season 1 overlays.

    python3 tools/pcref/pc_woody.py            # write PCWoodySeconds
    python3 tools/pcref/pc_woody.py --show     # print them only

A Season 1 trick is a combination of combine.xml — the object and the
inventory item it takes (`<ingredient>`s), the tricked object its name — and
Woody plays it as the object's action of his named after the inventory item
(lir/sofa's `fartbag`, kit/binoculars' `superglue`), or `use` where the trick
takes no item (lir/tv's twisted antenna); the action's time is the record's
as Loader.dll stores it (lap_model.Level.action_ticks: time="N", or the longer
oneshot animation less one). The mobile item of each trick is
tools/pcref/pc_reactions.py's TABLE (its PC tricked object); the overlay entry
PCWoodySeconds maps the mobile inventory type Woody holds (RequiredInventory,
SecondRequiredInventory) — or `use` — to the seconds, and World.woody_use
plays the remaster's use clip at the pace that lasts them. A trick laid on a
room's floor (the combination of the room and the banana or the marbles:
kit/groundbanana <- kit + banana) is Woody's own `laydown` (generic/objects.xml,
the ACTION step game.exe builds at 0x44b109-0x44b141), the remaster's
TakeGround items.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canon         # noqa: E402
import lap_model     # noqa: E402
import pc_reactions  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))


def combinations(L):
    text = canon.read(os.path.join(lap_model.X, L.folder, 'combine.xml'))
    out = {}
    for m in re.finditer(r'<combination name="([^"]+)"[^>]*>(.*?)</combination>', text, re.S):
        out[m.group(1)] = re.findall(r'<ingredient name="([^"]+)"', m.group(2))
    return out


def mobile_items(n):
    """{item name: (component, [required inventory types], Woody's use clip)} of the
    mobile level"""
    d = json.load(open('%s/levels/s1/Level%d.json' % (ROOT, n)))['objects']
    out = {}
    for o in d.values():
        dd = o.get('data') or {}
        nm = (dd.get('m_GameObject') or {}).get('name')
        if o.get('type') in ('TrickItem', 'Drawing', 'Rake', 'Toilet', 'Television') and nm:
            out[nm] = (o['type'], [x for x in (dd.get('RequiredInventory'), dd.get('SecondRequiredInventory'))
                                   if x and x != 'IT_NONE'], dd.get('Animation'))
    return out


def woody_seconds(n):
    """{item: ({key: seconds}, notes)}: the PC action Woody plays for each mobile
    inventory type the item takes (or `use`)"""
    L = lap_model.Level(n)
    combos = combinations(L)
    items = mobile_items(n)
    out = {}
    for item, spec in sorted(pc_reactions.TABLE.get(n, {}).items()):
        if item not in items:
            continue
        ing = combos.get(spec['pc'])
        if not ing:
            continue
        base = next((i for i in ing if '/' in i), None)
        invs = [i for i in ing if '/' not in i]
        if base is None:
            continue
        vals = {}
        notes = []
        kind, req, _clip = items[item]
        for t in req:
            name = canon.norm(t)
            cands = [name] + [i for i in invs if i != name]
            for nm in cands:
                v = L.action_ticks(base, nm, actor='woody')
                if v is not None:
                    vals[t] = round(v / lap_model.TICK, 3)
                    notes.append('%s <- %s %s %d ticks' % (t, base, nm, v))
                    break
        if not req:
            v = L.action_ticks(base, 'use', actor='woody')
            if v is None and invs:
                v = L.action_ticks(base, invs[0], actor='woody')
            if v is not None:
                vals['use'] = round(v / lap_model.TICK, 3)
                notes.append('use <- %s %d ticks' % (base, v))
        if vals:
            out[item] = (kind, vals, notes)
    # the floor drops: Woody's `laydown` for every item the remaster lays with TakeGround
    lay = L.action_ticks('woody', 'laydown', actor='woody')
    for item, (kind, req, clip) in sorted(items.items()):
        if item in out or clip != 'TakeGround' or lay is None or not req:
            continue
        out[item] = (kind, {t: round(lay / lap_model.TICK, 3) for t in req},
                     ['%s <- woody laydown %d ticks' % (t, lay) for t in req])
    return out


def main(argv):
    show = '--show' in argv
    for n in range(101, 115):
        res = woody_seconds(n)
        print('%d: %s' % (n, '; '.join('%s %s' % (it, v[1]) for it, v in res.items())))
        if show:
            continue
        p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
        ov = json.load(open(p))
        ov['patches'] = [e for e in ov['patches'] if not ('PCWoodySeconds' in (e.get('set') or {})
                                                          and len(e['set']) == 1)]
        for item, (kind, vals, notes) in res.items():
            src = ("Woody's trick action (level_%s's objects.xml, the Loader's time at 12 a second, "
                   "tools/pcref/pc_woody.py): %s" % (canon.pc_level(n)['folder'][6:], '; '.join(notes)))
            ov['patches'].append({'object': item, 'component': kind, 'set': {'PCWoodySeconds': vals},
                                  'source': src})
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
        open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
