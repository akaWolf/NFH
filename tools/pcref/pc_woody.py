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
TakeGround items. Season 2 (GameLogic.dll) plays the same records as a
DoActions job on Woody's queue, the Loader's time + 2 ticks
(lap_model_s2.Data.job_ticks); its tricks are paired by the inventory the
mobile item takes (the trick combination holding it, as tools/pcref/coins.py
does), a combination with a mini-game left to the game (PCMinigameTicks).
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
    # the containers: Woody's `take` from the PC object whose `<content>`s are the
    # remaster's SearchItem's inventory (open and close are 0 ticks for him: a
    # one-frame oneshot of his and none of the object's) — take0/1/3 18 ticks,
    # take_low0 11, take_high 14
    d = json.load(open('%s/levels/s1/Level%d.json' % (ROOT, n)))['objects']
    ob = canon.read(os.path.join(lap_model.X, L.folder, 'objects.xml'))
    contents = {}
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', ob, re.S):
        cs = set(re.findall(r'<content name="([^"]+)"', om.group(2)))
        if cs:
            contents[om.group(1)] = cs
    for o in d.values():
        dd = o.get('data') or {}
        nm = (dd.get('m_GameObject') or {}).get('name')
        if o.get('type') != 'SearchItem' or not nm or nm in out:
            continue
        invs = {canon.norm(i.get('Type')) for i in (dd.get('InventoryItems') or [])
                if isinstance(i, dict) and i.get('Type')}
        if not invs:
            continue
        cands = [obj for obj, cs in contents.items() if invs & cs]
        ticks = {L.action_ticks(obj, 'take', actor='woody') for obj in cands}
        ticks.discard(None)
        if len(ticks) != 1:
            continue
        t = ticks.pop()
        out[nm] = ('SearchItem', {'use': round(t / lap_model.TICK, 3)},
                   ['use <- %s take %d ticks' % ('/'.join(sorted(cands)), t)])
    # the hideouts: Woody's `enter` and `leave` of the PC object carrying the
    # hideout flag and the HideItem's name (the wardrobe 19 and 19 ticks, the
    # bed 4 and 4) — the remaster's hide clip and its leave clip paced to them
    for o in d.values():
        dd = o.get('data') or {}
        nm = (dd.get('m_GameObject') or {}).get('name')
        if o.get('type') != 'HideItem' or not nm or nm in out:
            continue
        cands = [obj for obj in L.objects if obj.split('/')[-1] == nm.lower()
                 and re.search(r'<object name="%s"[^>]*>(?:(?!</object>).)*<flag name="hideout"' % re.escape(obj),
                               ob, re.S)]
        vals = {}
        for act in ('enter', 'leave'):
            ts = {L.action_ticks(obj, act, actor='woody') for obj in cands}
            ts.discard(None)
            if len(ts) == 1:
                vals[act] = round(ts.pop() / lap_model.TICK, 3)
        if vals:
            out[nm] = ('HideItem', vals, ['%s <- %s %s' % (k, '/'.join(sorted(cands)), v) for k, v in vals.items()])
    # the floor drops: Woody's `laydown` for every item the remaster lays with TakeGround
    lay = L.action_ticks('woody', 'laydown', actor='woody')
    for item, (kind, req, clip) in sorted(items.items()):
        if item in out or clip != 'TakeGround' or lay is None or not req:
            continue
        out[item] = (kind, {t: round(lay / lap_model.TICK, 3) for t in req},
                     ['%s <- woody laydown %d ticks' % (t, lay) for t in req])
    return out


def woody_seconds_s2(n):
    """Season 2: {item: (component, {type: seconds}, notes)} — the trick
    combination holding the inventory type the item takes, the base object's
    action of Woody named after it, the job's ticks"""
    import lap_model_s2
    d = os.path.join(canon.ROOT, 'nfh2', 'x', canon.S2[n])
    cb = canon.read(os.path.join(d, 'combine.xml'))
    combos = []
    for m in re.finditer(r'<combination name="([^"]+)"([^>]*)>(.*?)</combination>', cb, re.S):
        if 'trick="true"' in m.group(2) and 'game=' not in m.group(2):
            combos.append(re.findall(r'<ingredient name="([^"]+)"', m.group(3)))
    D = lap_model_s2.Data(n)
    mob = json.load(open('%s/levels/s2/Level%d.json' % (ROOT, n)))['objects']
    # the level's mini-game item (PCMinigameTicks, tools/pcref/pc_minigames.py)
    # is left to the game
    ovp = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
    games = {e.get('object') for e in json.load(open(ovp)).get('patches', [])
             if 'PCMinigameTicks' in (e.get('set') or {})} if os.path.exists(ovp) else set()
    out = {}
    for o in mob.values():
        dd = o.get('data') or {}
        nm = (dd.get('m_GameObject') or {}).get('name')
        if o.get('type') != 'TrickItem' or not nm or nm in games:
            continue
        req = [x for x in (dd.get('RequiredInventory'), dd.get('SecondRequiredInventory'))
               if x and x not in ('IT_NONE', 'IT2_NONE')]
        vals = {}
        notes = []
        for t in req:
            inv = canon.norm(t)
            for ing in combos:
                base = next((i for i in ing if '/' in i), None)
                if inv not in ing or base is None:
                    continue
                jt = D.job_ticks(base, inv, actor='woody')
                if jt is not None:
                    vals[t] = round(jt / lap_model.TICK, 3)
                    notes.append('%s <- %s %s, the job %d ticks' % (t, base, inv, jt))
                    break
        if vals:
            out[nm] = (o['type'], vals, notes)
    # the containers: Woody's `take` of the PC object whose contents are the
    # SearchItem's inventory, as a job (16 ticks on most)
    ob = canon.read(os.path.join(d, 'objects.xml'))
    contents = {}
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', ob, re.S):
        cs = set(re.findall(r'<content name="([^"]+)"', om.group(2)))
        # a container that is a mini-game (flag `game`) is left to the game
        if cs and '<flag name="game"' not in om.group(2):
            contents[om.group(1)] = cs
    for o in mob.values():
        dd = o.get('data') or {}
        nm = (dd.get('m_GameObject') or {}).get('name')
        if o.get('type') != 'SearchItem' or not nm or nm in out or nm in games:
            continue
        invs = {canon.norm(i.get('Type')) for i in (dd.get('InventoryItems') or [])
                if isinstance(i, dict) and i.get('Type')}
        cands = [obj for obj, cs in contents.items() if invs & cs]
        ticks = {D.job_ticks(obj, 'take', actor='woody') for obj in cands}
        ticks.discard(None)
        if len(ticks) != 1:
            continue
        t = ticks.pop()
        out[nm] = ('SearchItem', {'use': round(t / lap_model.TICK, 3)},
                   ['use <- %s take, the job %d ticks' % ('/'.join(sorted(cands)), t)])
    # the hideouts: the PC objects with the hideout flag and Woody's enter and
    # leave, each paired with the level's HideItem — the one of each, else the
    # one whose name shares a word with the object's (lorry, statue)
    hides = []
    for om in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', ob, re.S):
        if '<flag name="hideout"' in om.group(2):
            e = D.job_ticks(om.group(1), 'enter', actor='woody')
            l = D.job_ticks(om.group(1), 'leave', actor='woody')
            if e is not None and l is not None:
                hides.append((om.group(1), e, l))
    items = [((o.get('data') or {}).get('m_GameObject') or {}).get('name') for o in mob.values()
             if o.get('type') == 'HideItem']
    items = [i for i in items if i]
    for nm in sorted(set(items)):
        if nm in out:
            continue
        low = nm.lower()
        match = [h for h in hides if len(hides) == 1 and len(set(items)) == 1
                 or any(w in h[0].split('/')[-1] for w in re.findall(r'[a-z]{4,}', re.sub(r'([A-Z])', r' \1', nm).lower()))]
        if len(match) != 1:
            continue
        obj, e, l = match[0]
        out[nm] = ('HideItem', {'enter': round(e / lap_model.TICK, 3), 'leave': round(l / lap_model.TICK, 3)},
                   ['enter <- %s the job %d ticks' % (obj, e), 'leave <- %s the job %d ticks' % (obj, l)])
    return out


def main(argv):
    show = '--show' in argv
    for n in list(range(101, 115)) + list(range(201, 215)):
        res = woody_seconds(n) if n < 200 else woody_seconds_s2(n)
        print('%d: %s' % (n, '; '.join('%s %s' % (it, v[1]) for it, v in res.items())))
        if show:
            continue
        p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
        ov = json.load(open(p))
        ov['patches'] = [e for e in ov['patches'] if not ('PCWoodySeconds' in (e.get('set') or {})
                                                          and len(e['set']) == 1)]
        for item, (kind, vals, notes) in res.items():
            where = ("level_%s's objects.xml, the Loader's time" % canon.pc_level(n)['folder'][6:]) if n < 200 \
                else ("%s's objects.xml, the DoActions job: the Loader's time + 2" % canon.S2[n])
            src = ("Woody's trick action (%s at 12 a second, tools/pcref/pc_woody.py): %s"
                   % (where, '; '.join(notes)))
            ov['patches'].append({'object': item, 'component': kind, 'set': {'PCWoodySeconds': vals},
                                  'source': src})
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
        open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
