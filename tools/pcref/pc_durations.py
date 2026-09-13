#!/usr/bin/env python3
"""The neighbour's station durations from the PC data into the Season 1 overlays.

    python3 tools/pcref/pc_durations.py            # rewrite the PCUseSeconds patches
    python3 tools/pcref/pc_durations.py --show     # print the pairing only

Each PC station of the level class's lap (tools/pcref/lap_model.py: the ICON groups
of the walker's tokens, the DoActions' ticks summed at 12 a second) is paired with the
mobile routine's item that visits it — PAIRS: (mobile item, PC icon, k-th visit of that
icon, and how many consecutive mobile visits share one PC station — or, a tuple of the
station's action names, the consecutive mobile visits that split it: 111's machines, the
mobile's prime, use and unprime legs, are the case's give, wash, get_clothes and give,
dry, take). The overlay entry
PCUseSeconds carries one value per visit, cycling — every visit counts, the prime and
unprime legs of a toggling station included (Routine._pc_visit_seconds: 111's first
ironing is the give, its second the ironing); RoutineAction._pc_use_seconds plays
the mobile use clips at the pace that lasts it (AnimPlayer.time_scale), or holds a
walk-by stand for it. Left to the mobile: 106's bath, 104's shaving chain.
The walker (tools/pcref/routine_order.py) follows the objects' presence along the lap
(isObjectPresent over level.xml and the switches): 111's second ironing irons the clothes
case 8 gave the board, 113's valve is switched off and on, 114's third phonograph visit
plays the record.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import canon      # noqa: E402
import lap_model  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
PAIRS = {
    101: [('Sofa', 'sofa', 0), ('Binoculars', 'binoculars', 0)],
    102: [('Sofa', 'sofa', 0), ('Beer', 'beer', 0)],
    103: [('Candle', 'candle', 0), ('BirthdayCake', 'cake', 0, 2), ('LetterBox', 'mail', 0)],
    104: [('ApplePie', 'applepie', 0), ('Microwave', 'microwave', 0), ('WhippedCream', 'whippedcream', 0)],
    105: [('Piano', 'piano', 0), ('Football', 'football', 0), ('Window', 'football', 1), ('PlantStink', 'flower', 0)],
    106: [('PhotoAlbum', 'photo_album', 0), ('Pudding', 'milk_bottle', 0)],
    107: [('Camera', 'camera', 0), ('MagnesiumBottle', 'magnesium', 0), ('Camera', 'camera', 1),
          ('DieselGenerator', 'potterswheel', 0), ('MumStatueFootStool', 'statue', 1)],
    108: [('ToothBrush', 'toothbrush', 0), ('CoffeeMaker', 'coffee', 0), ('Shezlong', 'foldingchair', 0),
          ('WateringCan', 'ewer', 1), ('Plant', 'flower', 0), ('WateringCan', 'ewer', 2)],
    109: [('Teeth', 'teeth', 0), ('Bed', 'sleep', 0), ('AlarmClock', 'alarm_clock', 0), ('Teeth', 'teeth', 1),
          ('PigKeys', 'pig_key', 0), ('PigMilk', 'milk_bottle', 0), ('Pig', 'pig', 1), ('PigMilk', 'milk_bottle', 1),
          ('CornChips', 'cookies', 0), ('Chili', 'parrot', 1), ('PigKeys', 'pig_key', 1)],
    110: [('SteakMeat', 'meatbowl', 0), ('Beer', 'beer', 0), ('BBQ', 'bbq', 0), ('CarnivorPlantSpray', 'plant', 0),
          ('BBQ', 'bbq', 1), ('SteakChair', 'table', 0), ('SteakWine', 'wine', 0)],
    111: [('Detergent', 'detergent', 0), ('WashingMachine', 'washing_machine', 0, ('give', 'wash', 'get_clothes')),
          ('Drier', 'tumble_drier', 0, ('give', 'dry', 'take')), ('Iron', 'ironing', 0), ('Airer', 'laundry_rack', 0),
          ('FishTank', 'aquarium', 0), ('Airer', 'laundry_rack', 1), ('Iron', 'ironing', 1)],
    112: [('YogaBook', 'book', 0), ('FishTank', 'aquarium', 0), ('Yoga', 'yoga_mat', 0), ('YogaBook', 'book', 1),
          ('Trampoline', 'trampoline', 0), ('Bicycle', 'home_trainer', 0), ('Mixer', 'mixer', 0, 2),
          ('ChestExpander', 'expander', 0), ('Weights', 'barbell', 0), ('Rope', 'skipping_rope', 0)],
    113: [('ChairAssembly', 'chairkit', 0), ('AngleGrinder', 'powertool', 0), ('ValveMain', 'valve', 0),
          ('Radiator', 'heater', 0), ('Sink', 'basin', 0), ('ValveMain', 'valve', 1), ('FuseBox', 'fuse', 0),
          ('Ladder', 'ladder', 0), ('FuseBox', 'fuse', 1)],
    114: [('Polish', 'polish', 0), ('GoldCup', 'cups', 0), ('Polish', 'polish', 1), ('Pipe', 'smoke', 0),
          ('Gramaphone', 'phonograph', 0), ('CDs', 'records', 0), ('Gramaphone', 'phonograph', 1), ('Pipe', 'smoke', 1),
          ('Gramaphone', 'phonograph', 2), ('Shotgun', 'gun', 0), ('Hat', 'hat', 0), ('Horn', 'horn', 0)],
}


def pc_stations(n, toks):
    """icon -> [seconds of each visit], and icon -> [[(action, seconds)] of each visit]"""
    L = lap_model.Level(n)
    legs = lap_model.model(L, toks[n])
    st = lap_model.stations(legs)
    acts = []
    for kind, text, t in legs:
        if kind == 'icon':
            acts.append([])
        elif kind == 'action' and acts:
            acts[-1].append((text.split()[-1], t / lap_model.TICK))
    if len(st) > 1 and st[-1][0].split()[-1] == st[0][0].split()[-1]:
        st[0][1] += st[-1][1]; st = st[:-1]
        acts[0] += acts[-1]; acts = acts[:-1]
    by = {}; parts = {}
    for (icon, ta, tw), aa in zip(st, acts):
        by.setdefault(icon.split()[-1], []).append(ta / lap_model.TICK)
        parts.setdefault(icon.split()[-1], []).append(aa)
    return by, parts


def item_kind(n, name):
    d = json.load(open('%s/levels/s1/Level%d.json' % (ROOT, n)))['objects']
    for o in d.values():
        dd = o.get('data') or {}
        if o['type'] in ('TrickItem', 'Item', 'SearchItem') and (dd.get('m_GameObject') or {}).get('name') == name:
            return o['type']
    return None


def main(argv):
    show = '--show' in argv
    toks = lap_model.tokens_of([], os.environ.get('LAP_TOKENS'))
    for n, pairs in sorted(PAIRS.items()):
        if not pairs:
            continue
        by, parts = pc_stations(n, toks)
        secs = {}
        notes = []
        for pr in pairs:
            item, icon, k = pr[0], pr[1], pr[2]
            share = pr[3] if len(pr) > 3 else 1
            vals = by.get(icon, [])
            if k >= len(vals):
                print('%d: no PC station %s #%d for %s' % (n, icon, k, item)); continue
            if isinstance(share, tuple):
                # the station split by its actions, one mobile visit each
                aa = parts[icon][k]
                got = []
                for name in share:
                    v = [s for a, s in aa if a == name]
                    if not v:
                        print('%d: no action %s at %s#%d for %s' % (n, name, icon, k, item)); break
                    got.append(v[0])
                else:
                    secs.setdefault(item, []).extend(round(v, 2) for v in got)
                    notes.append('%s <- %s#%d %s' % (item, icon, k, ', '.join(
                        '%s %.2f s' % (a, v) for a, v in zip(share, got))))
                continue
            v = round(vals[k] / share, 2)
            for _ in range(share):
                secs.setdefault(item, []).append(v)
            notes.append('%s <- %s#%d %.1f s%s' % (item, icon, k, vals[k], ' /%d' % share if share > 1 else ''))
        print('%d: %s' % (n, '; '.join(notes)))
        if show:
            continue
        p = '%s/levels/pc/Level%d.overlay.json' % (ROOT, n)
        ov = json.load(open(p)) if os.path.exists(p) else {'source': 'the PC data (tools/pcref)', 'patches': []}
        # in place: an entry keeps its other keys (tools/pcref/pc_reactions.py merges the
        # trick step's into the same object's entry) and its place in the file
        patches = []
        for e in ov.get('patches', []):
            st = e.get('set') or {}
            if 'PCUseSeconds' in st and e.get('object') not in secs:
                st = {k: v for k, v in st.items() if k != 'PCUseSeconds'}
                if not st:
                    continue
                e = dict(e, set=st)
            patches.append(e)
        ov['patches'] = patches
        for item, vals in secs.items():
            kind = item_kind(n, item)
            if kind is None:
                print('%d: no item %s' % (n, item)); continue
            src = ("the PC station's DoActions at 12 ticks a second (level_%s's objects.xml and anims.xml through "
                   "tools/pcref/lap_model.py, paired in tools/pcref/pc_durations.py): %s"
                   % (canon.pc_level(n)['folder'][6:], '; '.join(x for x in notes if x.startswith(item + ' <-'))))
            v = vals if len(vals) > 1 else vals[0]
            e = next((e for e in ov['patches'] if e.get('object') == item and e.get('component') == kind
                      and 'PCUseSeconds' in (e.get('set') or {})), None)
            if e is not None:
                e['set']['PCUseSeconds'] = v
                e['source'] = src
            else:
                ov['patches'].append({'object': item, 'component': kind, 'set': {'PCUseSeconds': v}, 'source': src})
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
