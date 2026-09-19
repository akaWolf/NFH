#!/usr/bin/env python3
"""The Season 2 catch of the PC original into the levels/pc overlays.

    python3 tools/pcref/pc_catch_s2.py            # check the table against the data, print it
    python3 tools/pcref/pc_catch_s2.py --write    # PCHideout on the catchers' stations

The catch is data: generic/trigger.xml gives the neighbour and the Mother a
`fight` behaviour on Woody, `<trigger object="woody" position="room"
type="always"/>` (and Woody a `die` one on either). Loader.dll's trigger parser
(0x1000a869-0x1000a936) turns `position` room / nearobj / house into the mode
bits 1 / 2 / 4 and `type` once / always into 0x1000 / 0x2000 of the
AddObjectTriggerMsg's `flag`; GameLogic.dll parses the message (fcn.1004fa5c:
actor, actionactor, behavior, flag, object) into the watch table the level
tick walks (fcn.1003fc90), and a firing entry starts the behaviour on its
actor (fcn.1003f086 -> fcn.10005b94: the fear, the fight, the respawn). Under
mode 1 the predicate (fcn.1003f573) is: both objects' room pointers set and
equal (fcn.10040a7d; a pass holds none from `<actor>_in` to `<actor>_out`,
fcn.100037f8 / fcn.10003647 / fcn.10003454), the target placed (flag 0x20)
and neither carrying flag 4 — no busy, sleep, sneak or animation term. Olga,
the kid and the others have no trigger: they never catch.

Flag 4 is the hideout state. The enter step (vtable 0x100ab2ec, run at
0x100066ef) sets it when the entered object carries hideout or
neighbor_hideout (0x140, 0x100067d4-0x100067e9) and the leave step (vtable
0x100ab304) clears it when its `leave` has played (0x10006ab7); the level
steps set and clear it themselves at a few places — every call of the flag
setter fcn.100450bf with mask 4 in GameLogic.dll is in the table below, and
the one flag element of mask 4 (fcn.1000fac4, whose run 0x1000d037 calls the
setter as the sequence reaches it: 210's chair clears his after the `wakeup`,
0x1001902c). Woody's
own (his HideItems, the PC's `hideout` objects) are the port's hiding plus the
leave clip; the catchers' are the stations below, per role:

  {}                 the station's use, enter to leave (the whole visit)
  {"clear": [...]}   ... less the clips from the one named on, where a level
  {"set": [...]}         step clears the flag (and back on at a `set` clip)
  {"until": item}    set at this use when the routine goes on to `item`,
                     kept through the walk, cleared at the end of that use

The station is the mobile routine item; its PC object is the one the level
script enters (the go-and-enter helpers fcn.1000ea30 / fcn.1000e7f2, the enter
step fcn.10006bd4 — the addresses in the table), checked below to carry the
flag and an `enter` action for the actor in the level's objects.xml. The clips
are the mobile use sequence's own names for the PC step's animation on the
object (`sleep`, `sleep_pillow` -> MotherSleep*, `look`, `awake` -> MotherLook*,
the beer -> BeachGetBeer).
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
from canon import S2  # noqa: E402

PC = os.path.expanduser('~/nfh-bench/pcref/pc/nfh2/x')
ACTOR = {'Rottweiler': 'neighbor', 'Mother': 'mother'}

# level -> station -> role -> (PC object entered, [the script's addresses], spec)
HIDEOUTS = {
    202: {'BeerMat': {'Rottweiler': ('beachright/mat_hn_guarded', [0x10022e6f, 0x10022a5b],
                                     {'clear': ['BeachGetBeer']})},        # asleep until the beer step clears it
          'Swimming': {'Rottweiler': ('beachright/theocean', [0x1002248d, 0x10021de0], {})}},
    206: {'DeckChair': {'Mother': ('topleft/deckchair', [0x1002baaa, 0x1002b77b, 0x1002b9e3],
                                   {'clear': ['MotherLook', 'MotherLookLoop'],
                                    'set': ['MotherSleepLoop', 'MotherSleepSingle']})}},
    207: {'BeachTowel': {'Rottweiler': ('beachleft/mat_guarded', [0x10015119], {})},
          'DeckChair': {'Mother': ('pool/deckchair', [0x10014516, 0x10014428], {})},
          'PoolLadder': {'Mother': ('pool/pool', [0x10014148], {})}},
    208: {'IndianPlatform': {'Rottweiler': ('amusement/platform', [0x1001ee50], {})},
          'DressingRoom': {'Mother': ('bazar/dressing_room', [0x1001d27d], {})}},
    209: {'TadjMahal': {'Rottweiler': ('tadj_mahal/curtain', [0x10020dd4, 0x10020c5c], {})},
          'HotShoe': {'Rottweiler': ('tadj_mahal/shoe_mat', [0x10020d0e, 0x10020888],
                                     {'until': 'TadjMahal'})},             # set at the shoe mat, the curtain's leave clears
          'DressingRoom': {'Mother': ('bazar/dressing_room', [0x1001f62f], {})}},
    210: {'DeckChair': {'Rottweiler': ('beachleft/deckchair_guarded', [0x10019635, 0x100190d1, 0x1001902c],
                                       {'clear': ['ChairAwake']})},        # awake after the wakeup's flag element
          'DeckChairMother': {'Mother': ('pool/deckchair', [0x1001886c, 0x10018d60, 0x1001866f],
                                         {'clear': ['MotherLookLoop'],
                                          'set': ['MotherSleepPillow', 'MotherSleepSingle']})}},
    211: {'DeckChairMother': {'Mother': ('topright/deckchair', [0x1002f8ca], {})}},
    212: {'SleepBench': {'Rottweiler': ('midleft/bank', [0x10036550], {})}},
    214: {'DeckChairMother': {'Mother': ('topright/deckchair', [0x10039eeb, 0x10039efa, 0x1003a1c5],
                                         {'clear': ['MotherLookLoop'],
                                          'set': ['MotherSleepSingle']})}},
}
# the flag setter's mask-4 calls (and the flag element's) outside the enter / leave
# steps, each placed above
SCRIPT_FLAGS = {0x1001866f, 0x10018d60, 0x1001902c, 0x10020d0e, 0x1002248d, 0x10022a5b,
                0x1002b77b, 0x1002b9e3, 0x10039efa, 0x1003a1c5}


def xml(path):
    raw = open(path, 'rb').read()
    t = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')
    return ET.fromstring(re.sub(r'<\?xml[^>]*\?>', '', t))


def objects(lv):
    """{object: ([(action, actor)], [flag])} of a level's objects.xml"""
    out = {}
    for o in xml('%s/%s/objects.xml' % (PC, lv)).iter():
        if o.tag in ('object', 'actor', 'door'):
            out[o.get('name')] = ([(a.get('name'), a.get('actor')) for a in o.findall('action')],
                                  [f.get('name') for f in o.findall('flag')])
    return out


def triggers():
    """generic/trigger.xml: [(actor, behaviour, object, position, type)]"""
    out = []
    for a in xml('%s/generic/trigger.xml' % PC).findall('actor'):
        for b in a.findall('behavior'):
            for t in b.findall('trigger'):
                out.append((a.get('name'), b.get('name'), t.get('object'), t.get('position'), t.get('type')))
    return out


def check():
    """the table against the data: the catch triggers, each station's PC object, its
    flag and enter action, the clips in the mobile use sequence; every script flag
    site placed"""
    import scene
    tr = triggers()
    catch = sorted((a, p, t) for a, b, o, p, t in tr if b == 'fight' and o == 'woody')
    assert catch == [('mother', 'room', 'always'), ('neighbor', 'room', 'always')], catch
    placed = set()
    rows = []
    for n, st in sorted(HIDEOUTS.items()):
        objs = objects(S2[n])
        lv = scene.Level('%s/levels/s2/Level%d.json' % (ROOT, n))
        for item, per in st.items():
            its = [it for it in lv.items.values() if it.name == item]
            assert its, (n, item)
            for role, (obj, addrs, spec) in per.items():
                acts, flags = objs[obj]
                if 'until' not in spec:
                    assert 'neighbor_hideout' in flags, (n, obj, flags)
                    assert ('enter', ACTOR[role]) in acts, (n, obj, acts)
                # the clips are the pawn's (206's and 214's Mother alternates
                # her look and sleep loops outside the station's sequence)
                clips = {a.name for a in lv.pawns[role]['sprite'].anims}
                for clip in spec.get('clear', []) + spec.get('set', []):
                    assert clip in clips, (n, role, clip)
                assert spec.get('until') in (None,) + tuple(st), (n, item, spec)
                placed.update(a for a in addrs if a in SCRIPT_FLAGS)
                rows.append((n, item, role, obj, spec, addrs))
    assert placed == SCRIPT_FLAGS, sorted(hex(a) for a in SCRIPT_FLAGS - placed)
    return rows


def main(argv):
    write = '--write' in argv
    rows = check()
    for n, item, role, obj, spec, addrs in rows:
        print('%d %-16s %-10s %-28s %-60s %s' % (n, item, role, obj, json.dumps(spec),
                                                ' '.join(hex(a) for a in addrs)))
    if not write:
        return 0
    for n in range(201, 215):
        p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
        ov = json.load(open(p))
        raw = json.load(open('%s/levels/s2/Level%d.json' % (ROOT, n)))
        want = []
        for pid, o in sorted(raw['objects'].items(), key=lambda kv: int(kv[0])):
            d = o.get('data') or {}
            name = (d.get('m_GameObject') or {}).get('name')
            per = HIDEOUTS.get(n, {}).get(name)
            if not per or 'Zone' not in d or o['type'] in ('Transition', 'Door'):
                continue
            want.append({'object': name, 'component': o['type'], 'zone': (d.get('Zone') or {}).get('name'),
                         'set': {'PCHideout': {role: spec for role, (_o, _a, spec) in per.items()}}})
        # the key is rewritten in place — a patch it shares with the other
        # tools' keys (the Mother's chair timings, pc_durations_others.py)
        # keeps them — a station's new one appended, a gone one dropped
        patches = []
        for e in ov.get('patches', []):
            s = e.get('set') or {}
            if 'PCHideout' not in s:
                patches.append(e)
                continue
            w = next((w for w in want if (w['object'], w['component'], w['zone'])
                      == (e['object'], e.get('component'), e.get('zone'))), None)
            if w is not None:
                s['PCHideout'] = w['set']['PCHideout']
                want.remove(w)
            else:
                s.pop('PCHideout')
            if s:
                patches.append(e)
        patches += want
        ov['patches'] = patches
        note = (" The catch (tools/pcref/pc_catch_s2.py): PCHideout on the catchers' stations = per role"
                " the span of the PC's flag 4 (the enter step to the leave step, less the level steps'"
                " clears), in which the neighbour or the Mother neither catches nor is seen.")
        src = ov.get('source', '')
        i = src.find(' The catch (tools/pcref/pc_catch_s2.py)')
        if i >= 0:
            # the note in its place (its own last words end it)
            end = 'neither catches nor is seen.'
            j = src.find(end, i)
            j = j + len(end) if j >= 0 else src.find(' The ', i + 1)
            src = src[:i] + (note if n in HIDEOUTS else '') + (src[j:] if j >= 0 else '')
        elif n in HIDEOUTS:
            src += note
        ov['source'] = src
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1)
        open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
