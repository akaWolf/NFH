#!/usr/bin/env python3
"""The Season 2 neighbour's station durations from the PC videos into the overlays.
    python3 tools/pcref/pc_durations_s2.py            # print the pairing
    python3 tools/pcref/pc_durations_s2.py --write    # rewrite the PCUseSeconds patches
The PC lap is the HUD bubble's span sequence of docs/PC_LAPS_DETAIL.md (its second
lap, the first starts mid-station); a span runs from the icon's appearance — the
walk to the station — to the next icon, so the stay is the span less the walk the
profile's neighbour takes to that station (runs/idlepc2s2, the port's idle laps at
the PC's walking speeds: scratchpad s2_idle_visits.json = per visit its `using` stay
and the gap since the previous stay). A PC span that covers several consecutive
mobile uses is split over them in the port's own proportions. The overlay entry
PCUseSeconds carries one value per visit of the item, cycling (RoutineAction.
_pc_use_seconds, the Season 1 mechanism).
"""
import json
import os
import re
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VISITS = os.path.join(os.environ.get('NFH_SCRATCH', '/tmp/claude-1000/-home-akawolf-projects-own-NFH/ac3a80a3-83a6-48a6-96d4-81dc371f54eb/scratchpad'), 's2_idle_visits.json')
# a PC bubble name -> the mobile uses it covers, in order
ALIAS = {
    'Puddle/Rail': ['WaterPuddle', 'DeckRail'],
    'Toilet': ['ToiletPaper', 'ToiletFlush'],
    'Gong': ['GongDrumstick'],
    'TableTennis': ['TabbleTennis'],
    'WaterSkis': ['WaterSkiis', 'WaterSkiis'],
    'DeckChair(mum)': ['DeckChair'],
    'CaptainWheel': ['CaptainDoor'],
}
PER_LEVEL = {
    213: {'MechanicalBull': ['MechanicalBullControls', 'MechanicalBullControlsWait', 'MechanicalBullControls']},
    212: {'AztecThrone': ['PreAztecThrone', 'AztecThrone'], 'ParrotLedge': ['PreParrotLedge', 'ParrotLedge']},
    209: {'TadjMahal': ['HotShoe', 'TadjMahal'], 'HotShoe': ['HotShoe']},
    210: {'DogBasket#2': ['DogBasketPut']},
}
SKIP = {'Fifi', 'Mother', 'ToiletMen', 'Rake'}   # other actors' icons, a walk-by without a use
MIN_STAY = 0.5


def pc_spans(n):
    """the first PC lap's spans (name, start, end); a station whose first span is
    degenerate (the level's opening frame) takes its next occurrence"""
    doc = open(os.path.join(ROOT, 'docs', 'PC_LAPS_DETAIL.md')).read()
    m = re.search(r'### n2_E%02d[^\n]*\n\nPC \(bubble[^\n]*: ([^\n]*)' % (n - 200), doc)
    allspans = [(a, int(b), int(c)) for a, b, c in re.findall(r'([\w/()]+) (\d+)-(\d+)', m.group(1))] if m else []
    if not allspans:
        return []
    first = allspans[0][0]
    nxt = [i for i, s in enumerate(allspans) if s[0] == first and i > 0]
    lap = allspans[:nxt[0]] if nxt else allspans
    out = []
    for i, (name, a, b) in enumerate(lap):
        if b <= a:
            later = [s for s in allspans[i + 1:] if s[0] == name and s[2] > s[1]]
            if later:
                out.append(later[0])
            continue
        out.append((name, a, b))
    return out


def port_lap(n):
    """one lap of the port's idle visits: from the first visit to the next of its item"""
    vis = json.load(open(VISITS)).get(str(n), [])
    if not vis:
        return []
    first = vis[0]['item']
    for i in range(1, len(vis)):
        if vis[i]['item'] == first:
            return vis[:i]
    return vis


def pair(n):
    spans = pc_spans(n)
    lap = port_lap(n)
    alias = dict(ALIAS); alias.update(PER_LEVEL.get(n, {}))
    out = []      # (mobile item, visit index within the lap, stay, pc name, span, walk)
    li = 0
    seen = {}
    occ = {}
    prev_end = None
    for name, a, b in spans:
        gap = (a - prev_end) if prev_end is not None else 0
        prev_end = b
        if name in SKIP:
            continue
        occ[name] = occ.get(name, 0) + 1
        group = alias.get('%s#%d' % (name, occ[name]), alias.get(name, [name]))
        # consume the next len(group) port visits that match by name in order
        picked = []
        j = li
        for g in group:
            while j < len(lap) and lap[j]['item'] != g:
                j += 1
            if j >= len(lap):
                break
            picked.append(lap[j]); j += 1
        if len(picked) == len(group) and j - li > len(group) + 2:
            picked = []      # the match skipped most of the lap: not this lap's station
        if len(picked) != len(group):
            out.append((None, None, None, name, b - a, None))
            continue
        li = j
        span = float(b - a)
        # the bubble shows the next icon through the walk when the spans touch;
        # an unlabelled gap before the span is walk already outside it
        walk = max(0.0, picked[0]['walk'] - max(0, gap))
        stay = max(MIN_STAY, span - walk)
        port_total = sum(max(0.1, v['end'] - v['start']) for v in picked)
        for v in picked:
            share = stay * max(0.1, v['end'] - v['start']) / port_total
            k = seen.get(v['item'], 0); seen[v['item']] = k + 1
            out.append((v['item'], k, round(share, 1), name, span, walk))
    return out


def main(argv):
    write = '--write' in argv
    levels = [int(a) for a in argv if a.isdigit()] or list(range(202, 215))
    for n in levels:
        rows = pair(n)
        print('== %d' % n)
        per = {}
        for item, k, stay, name, span, walk in rows:
            if item is None:
                print('   (no port visit for PC %s %ss)' % (name, span)); continue
            print('   %-26s visit %d: %5.1f s  <- PC %s %s s - walk %s' % (item, k, stay, name, span, walk))
            per.setdefault(item, []).append(stay)
        stays = sum(v for vals in per.values() for v in vals)
        lap = port_lap(n); walks = sum(v['walk'] for v in lap)
        print('   sum of stays %.1f + the port lap\'s walks %.1f = %.1f s' % (stays, walks, stays + walks))
        if write and per:
            p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
            ov = json.load(open(p))
            ov['patches'] = [e for e in ov.get('patches', []) if 'PCUseSeconds' not in (e.get('set') or {})]
            for item, vals in per.items():
                ov['patches'].append({'object': item, 'component': 'TrickItem',
                                      'set': {'PCUseSeconds': vals if len(vals) > 1 else vals[0]}})
            note = ' Station durations (tools/pcref/pc_durations_s2.py): the PC video bubble spans of docs/PC_LAPS_DETAIL.md less the walk to each station where the spans touch (an unlabelled gap before a span is walk outside it), PCUseSeconds per visit.'
            if 'pc_durations_s2' not in ov['source']:
                ov['source'] += note
            json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
            print('   written', p)


if __name__ == '__main__':
    main(sys.argv[1:])
