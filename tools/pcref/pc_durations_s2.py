#!/usr/bin/env python3
"""The Season 2 neighbour's station durations into the overlays: the code's where
the level script's lap is read, the PC videos' elsewhere.
    python3 tools/pcref/pc_durations_s2.py            # print the pairing
    python3 tools/pcref/pc_durations_s2.py --write    # rewrite the PCUseSeconds patches
On the levels of CODE the stays are GameLogic.dll's (tools/pcref/lap_model_s2.py
code_stays: the parts of the untricked lap — the DoActions' `time` or clips, a
hideout's enter/leave, a bar's ticks — summed per mobile item by its PAIRS); an
item the model leaves untimed (209's fire fakir, whose `spit` is untimed, 213's
picnic behind its polls) falls back to the video.
The video: the PC lap is the HUD bubble's span sequence of docs/PC_LAPS_DETAIL.md
(its second lap, the first starts mid-station); a span runs from the icon's
appearance — the walk to the station — to the next icon, so the stay is the span
less the walk the profile's neighbour takes to that station (the port's idle laps
under the profile: scratchpad s2_idle_visits.json = per visit its `using` stay and
the gap since the previous stay — since 2026-09-23 with the PC's door passes and
station runs, tools/pcref/pc_walks_s2.py, so the walk taken off is the PC's). A PC
span that covers several consecutive mobile uses is split over them in the port's
own proportions. The overlay entry PCUseSeconds carries one value per visit of the
item, cycling (RoutineAction._pc_use_seconds, the Season 1 mechanism).
"""
import json
import os
import re
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.environ.get('NFH_SCRATCH', '/tmp/claude-1000/-home-akawolf-projects-own-NFH/ac3a80a3-83a6-48a6-96d4-81dc371f54eb/scratchpad')
VISITS = os.path.join(SCRATCH, 's2_idle_visits.json')
VISITS_S1 = os.path.join(SCRATCH, 's1_idle_visits.json')   # runs/idlepc4, the Season 1 idle laps
# a PC bubble name -> the mobile uses it covers, in order
ALIAS = {
    'Puddle/Rail': ['WaterPuddle', 'DeckRail'],
    'Toilet': ['ToiletPaper', 'ToiletFlush'],
    'Gong': ['GongDrumstick'],
    'TableTennis': ['TabbleTennis'],
    'WaterSkis': ['WaterSkiis', 'WaterSkiis'],
    'DeckChair(mum)': ['DeckChair'],
}
# Season 1: the PC bubble names against the mobile's stations (the toilet, the
# phone and the vacuum are PC stations the mobile's routine has not)
ALIAS_S1 = {
    'Sofa/TV': ['Sofa'], 'Cake+Candle': ['Candle', 'BirthdayCake', 'BirthdayCake'],
    'Sink(shave)': ['SinkAftershave', 'SinkDeodrant'], 'Deodorant': ['Deodrant'],
    'Coffee': ['CoffeeMaker'], 'DeckChair': ['Shezlong'], 'Pottery(Diesel)': ['DieselChair', 'DieselGenerator'],
    'MumStatue': ['MumStatueFootStool'], 'Wine': ['SteakWine'],
}
PER_LEVEL = {
    105: {'Plant': ['PlantStink']},
    108: {'Plant': ['Plant']},
    213: {'MechanicalBull': ['MechanicalBullControls', 'MechanicalBullControlsWait', 'MechanicalBullControls']},
    212: {'AztecThrone': ['PreAztecThrone', 'AztecThrone'], 'ParrotLedge': ['PreParrotLedge', 'ParrotLedge']},
    # the PC does the Taj before the shoes (no first shoe visit): the Taj span
    # is the Taj's alone, the shoe span the second shoe visit's
    209: {'TadjMahal': ['TadjMahal'], 'HotShoe': ['HotShoe']},
    210: {'DogBasket#2': ['DogBasketPut']},
}
SKIP = {'Fifi', 'Mother', 'ToiletMen', 'Rake',
        'Toilet', 'Phone', 'Vacuum', 'Towel', 'Candy', 'MagnesiumBottle'}   # other actors' icons, a walk-by without a use; Season 1 stations the mobile routine has not or takes in a second
# stations kept at the mobile pace per level: 214's lap is a neighbour-Mother
# handshake timed as a whole (his pistol sequence fires mother_sleep, her sit
# fires mother_sit and releases his WaitWatch at the second pistol,
# Level214 behaviour cs:62-65/130-147): with the PC stays he reaches the pistol
# after her sit and both wait for each other for good; the PC's Mother script
# is unread, so the whole lap stays the mobile's
SKIP_LEVEL = {214: {'Shower', 'Bouquet', 'CaptainWheel', 'Pistol', 'Hatch'}}
MIN_STAY = 0.5


def _strip_key(patches, key):
    """drop `key` from every patch's set; a patch left empty goes"""
    out = []
    for e in patches:
        st = e.get('set')
        if isinstance(st, dict) and key in st:
            st = dict(st); del st[key]
            if not st:
                continue
            e = dict(e); e['set'] = st
        out.append(e)
    return out


def _set_key(patches, item, key, value):
    """set `key` on the item's TrickItem patch, or add one"""
    for e in patches:
        if e.get('object') == item and e.get('component') == 'TrickItem' and isinstance(e.get('set'), dict):
            e['set'][key] = value; return
    patches.append({'object': item, 'component': 'TrickItem', 'set': {key: value}})
# visits of the port's lap the PC never makes (209's first shoe: the PC does the
# Taj before the shoes) keep the mobile length — written as a leading 0
LEAD_MOBILE = {209: {'HotShoe': 1}}
# the levels whose stays are the code's (lap_model_s2.code_stays)
CODE = (203, 208, 209, 211, 212, 213)


def pc_spans(n):
    """the first PC lap's spans (name, start, end); a station whose first span is
    degenerate (the level's opening frame) takes its next occurrence"""
    doc = open(os.path.join(ROOT, 'docs', 'PC_LAPS_DETAIL.md')).read()
    m = re.search(r'### [^\n]*\(mobile Level%d\)[^\n]*\n\nPC \(bubble[^\n]*: ([^\n]*)' % n, doc)
    allspans = [(a, int(b), int(c)) for a, b, c in re.findall(r'([\w/()+]+) (\d+)-(\d+)', m.group(1))] if m else []
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
    vis = json.load(open(VISITS_S1 if n < 200 else VISITS)).get(str(n), [])
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
    alias = dict(ALIAS if n >= 200 else ALIAS_S1); alias.update(PER_LEVEL.get(n, {}))
    out = []      # (mobile item, visit index within the lap, stay, pc name, span, walk)
    li = 0
    seen = {}
    occ = {}
    prev_end = None
    for name, a, b in spans:
        gap = (a - prev_end) if prev_end is not None else 0
        prev_end = b
        if name in SKIP or name in SKIP_LEVEL.get(n, ()):
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
    levels = [int(a) for a in argv if a.isdigit()] or list(range(202, 215))   # or 101-114 with the Season 1 idle visits
    for n in levels:
        rows = pair(n)
        print('== %d' % n)
        per = {}
        for item, k, stay, name, span, walk in rows:
            if item is None:
                print('   (no port visit for PC %s %ss)' % (name, span)); continue
            print('   %-26s visit %d: %5.1f s  <- PC %s %s s - walk %s' % (item, k, stay, name, span, walk))
            per.setdefault(item, []).append(stay)
        if n in CODE:
            sys.path.insert(0, HERE)
            import lap_model_s2
            code = lap_model_s2.code_stays(n)
            for item, secs in sorted(code.items()):
                k = len(per.get(item, [])) or 1
                print('   %-26s code %5.2f s (video %s)' % (item, secs, per.get(item)))
                per[item] = [secs] * k
        stays = sum(v for vals in per.values() for v in vals)
        lap = port_lap(n); walks = sum(v['walk'] for v in lap)
        print('   sum of stays %.1f + the port lap\'s walks %.1f = %.1f s' % (stays, walks, stays + walks))
        if write:      # (a level with nothing to carry loses its stale patches too)
            p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
            ov = json.load(open(p))
            if n >= 200:
                ov['patches'] = _strip_key(ov.get('patches', []), 'PCUseSeconds')
            for item, vals in per.items():
                vals = [0] * LEAD_MOBILE.get(n, {}).get(item, 0) + vals
                _set_key(ov['patches'], item, 'PCUseSeconds', vals if len(vals) > 1 else vals[0])
            note = ' Station durations (tools/pcref/pc_durations_s2.py): the PC video bubble spans of docs/PC_LAPS_DETAIL.md less the walk to each station where the spans touch (an unlabelled gap before a span is walk outside it), PCUseSeconds per visit.'
            if n in CODE:
                note = ' Station durations (tools/pcref/pc_durations_s2.py): GameLogic.dll\'s level script (tools/pcref/lap_model_s2.py code_stays: the untricked lap\'s actions, hideouts and bars per mobile item), the PC video bubble spans of docs/PC_LAPS_DETAIL.md less the walk for the items the model leaves untimed, PCUseSeconds per visit.'
            src = ov['source']
            i = src.find(' Station durations (tools/pcref/pc_durations_s2.py)')
            if i >= 0:
                j = src.find(' The ', i + 1)
                src = src[:i] + (src[j:] if j >= 0 else '')
            ov['source'] = src + note
            json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
            print('   written', p)


if __name__ == '__main__':
    main(sys.argv[1:])
