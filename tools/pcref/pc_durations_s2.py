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
# stations kept out of the whole-stay pairing per level: 202's swim is timed
# per clip with its wait for Olga's sub (CLIPS, WAITS below). (214's
# neighbour-Mother handshake is the PC's under the profile since 2026-09-23 —
# he polls her at the pistol, GameLogic 0x1003abc9-0x1003ad7d,
# RottweilerMotherBehaviour — and its stays are the code's.)
SKIP_LEVEL = {202: {'Swimming'}}
# a station's clips at the PC's ticks (PCClipSeconds): mobile clip -> the code's
# part — (object, action) of the level data, ('bar', step) the ticks the step's
# fcn.1000e7f2 pushes, ('anim', actor, clip) a clip's frames (a loop's pace).
# 202's swim (GameLogic 0x10022410, 0x10022046, 0x10021d68): he waits at the
# shore, the kid's sub dives and runs ashore, he goes into the sea (its
# `enter`), holds the bar, and the GoTo to the bridge leaves the sea (its
# `leave`); tricked, the shark's bar (0x10021fb9)
CLIPS = {202: {'Swimming': {'WaitSea': ('anim', 'neighbor', 'waitsea'),
                            'EnterSea': ('beachright_theocean', 'enter'),
                            'SeeSub': ('bar', 0x10021d68),
                            'SeeShark': ('bar', 0x10021fb9),
                            'LeaveSea': ('beachright_theocean', 'leave')},
               # his mat and beer (the mat step 0x10022c8d: the hideout's `enter`,
               # the bar of 120 ticks over the mobile's seven sleep clips; the
               # beer step 0x1002299f: the `use`, getbeer — tricked the crab's,
               # takecrab — and the `leave`): its flag 4 ends where the PC's does
               'BeerMat': {'BeachLayDown': ('beachright_mat_hn_guarded', 'enter'),
                           'BeachPinLayDown': ('beachright_mat_hn_guarded', 'enter'),
                           'BeachSleep': ('bar', 0x10022c8d, 7),
                           'BeachSleepCrab': ('bar', 0x10022c8d, 7),
                           'BeachGetBeer': ('beachright_mat_hn_guarded', 'use'),
                           'BeachCrabGetBeer': ('beachright_mat_hn_guarded_manip', 'use'),
                           'BeachGetUp': ('beachright_mat_hn_guarded', 'leave')}},
        # 210's deck chair (his chair step 0x100195a4: the hideout's `enter`,
        # the bar of 120 ticks over the mobile's four sun clips; then the
        # chair's `wakeup` and the awake loop he waits in for the Mother's
        # call, 0x10018f4a; the call's step leaves it, 0x1001911e)
        210: {'DeckChair': {'ChairEnter': ('beachleft_deckchair_guarded', 'enter'),
                            'ChairSun': ('bar', 0x100195a4, 4),
                            'ChairWakeup': ('beachleft_deckchair_guarded', 'wakeup'),
                            'ChairAwake': ('anim', 'beachleft/deckchair', 'awake'),
                            'ChairLeave': ('beachleft_deckchair_guarded', 'leave')},
              # at her chair he stands for her order: her order step
              # (0x10018682) polls for him at its `neighbor` hotspot
              # (fcn.1000e172) and plays `order`, whose behavior="order"
              # (generic objects.xml), posted as its job ends (state 2,
              # fcn.1004000a at 0x10002708), sends him on to Fifi on the tick
              # after (his handler 0x1001b4f6 -> 0x1001aecc) — the order's job
              # and the offer's tick over the mobile's three stands
              'CallRTMother': {'Stand_Left': ('job', 'mother', 'order', 'mother', 3)}},
        # 205's table (his table step 0x100254d5: `play` on the guarded table
        # once Olga is there)
        205: {'TabbleTennis': {'Tennis': ('beachright_pingpong_guarded', 'play')}},
        # 207's board (his board step 0x100169c5: the `dive` once the Mother
        # sits in her deck chair, the pool's `enter`, 0 ticks, and its `leave`
        # as the bar step walks him out; the wait before is the Mother's —
        # Level207MotherBehavior holds his WaitWatch)
        207: {'PoolBoard': {'PoolDive': ('pool_divingboard', 'dive'),
                            'PoolGetOut': ('pool_pool', 'leave')}}}
# the items whose per-visit stays stand beside their clips: the clips time a
# visit whose stay is 0
KEEP_STAYS = {}
# the tricked use's clip after which the PC's trick action has ended
# (PCCreditAfter): the record's action (objects.xml) pays as it completes —
# the action step's end, fcn.1000140b — and 202's `shark` sits on the shark
# sea's `enter` (entersea), before the 119-tick bar the mobile's SeeShark plays
CREDIT = {202: {'Swimming': ('EnterSea', 'beachright/theocean_shark', 'enter', 'shark')}}
# a clip held until another role has used an item (PCWaitFor), then `then` —
# the (object, action) parts after it: 202's swim step polls for the `sub`
# (0x100224a8-0x10022563) that Olga's Submarine use switches into the sea,
# and goes on to the dive step at once, which pushes the kid's dive, the
# switch and his run ashore onto the KID's queue (fcn.1000aeb8's sequence,
# fcn.10049216 on the actor fcn.1004ba02 finds for `kid`, 0x100220a1-
# 0x100221e3) and hands over to the sea step (0x10021d68) — he waits for
# none of it (the video: into the sea as the shark's fin shows); until
# 2026-09-25 `then` held him for the dive and the run ashore
WAITS = {202: {'Swimming': {'clip': 'WaitSea', 'role': 'Olga', 'item': 'Submarine',
                            'then': []}},
         # 205's table: his step polls for the guarded table Olga's `pingpong`
         # step shows as she arrives (0x10025d76), then plays; the play's
         # behavior="sun" (cn_b2 objects.xml), posted as its job ends,
         # sends her back to her mat (her step 0x1002621c) — his use's end,
         # the use's PawnToAbortMutexOnFinish
         205: {'TabbleTennis': {'clip': 'Tennis', 'role': 'Olga', 'item': 'TabbleTennis', 'at': 'start',
                                'then': [('beachright_pingpong_guarded', 'play')]}},
         # 210's chair: awake until her call — her `callneighbor` carries
         # behavior="call" (generic objects.xml), posted as its job ends,
         # and on the tick after his handler (0x1001b4f6) sends him out of the
         # chair (0x1001911e: its `leave`, then the run to her chair); `at`
         # start: the awaited role's use begun, `then` her call's job and the
         # offer's tick (an (object, action, actor) part)
         210: {'DeckChair': {'clip': 'ChairAwake', 'role': 'Mother', 'item': 'CallRTMother',
                             'at': 'start', 'then': [('mother', 'callneighbor', 'mother')]}}}
# the stations whose action posts a behaviour another actor's script answers
# early in the stay: the seconds from the use's start to the offer — the
# parts' jobs up to the posting one and the offer's tick (PCBehaviourAt):
# 205's mat, whose `talk` (2 frames) carries behavior="pingpong" for Olga
# (her step 0x10025b2a gets her off the mat); 213's controls, whose step posts
# `bull` to Olga as he arrives, before the controls' `use` (0x10037f5e): the
# offer's tick alone
BEHAVIOUR_AT = {205: {'OlgaMatBeach': [('neighbor', 'talk', 'neighbor')]},
                213: {'MechanicalBullControls': []}}
# another actor's use whose action posts a behaviour as its job ends: the
# seconds from the use's end (its clip paced to the action's frames) to the
# offer — the job's ticks past the frames and the offer's tick
# (PCBehaviourAtEnd): 213's ride, `leave` to the neighbour, whose controls
# step waits for it (the latch +0x20)
BEHAVIOUR_AT_END = {213: {'MechanicalBull': ('bottomleft_bullride_olga', 'use', 'olga')}}
# stays read from the level script where the video's pairing had split a
# span: {item: [the parts of each visit] or None (no stay of its own)} —
# 213's bull (the controls step 0x10037e80: the controls' `use`, activate;
# then the step that waits for Olga's `leave`, a one-tick pass once it is
# set; the mobile's wait between them ends on her ride's end, no stay)
STAYS_CODE = {213: {'MechanicalBullControls': [[('bottomleft_bullride_controls', 'use')], [('ticks', 1)]],
                    'MechanicalBullControlsWait': None}}
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


def _strip_item_key(patches, item, key):
    """drop `key` from the item's patches; a patch left empty goes"""
    out = []
    for e in patches:
        st = e.get('set')
        if e.get('object') == item and isinstance(st, dict) and key in st:
            st = dict(st); del st[key]
            if not st:
                continue
            e = dict(e); e['set'] = st
        out.append(e)
    patches[:] = out


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
CODE = (201, 202, 203, 204, 205, 207, 208, 209, 210, 211, 212, 213, 214)
# the stations a tricked flow runs him to, off his lap: the use there lasts
# the level script's action — 211's sweets send him to the toilet
# (0x10030dc2): the women's wc with the sign tricked (wcright's `puke`, whose
# record wcright pays at 27), else the men's (wcleft's)
RUSH = {211: {'ToiletWomen': ('topleft_wcright', 'puke'), 'ToiletMen': ('topleft_wcleft', 'puke')}}
# the level scripts' actor names as the port's roles
ROLE = {'olga': 'Olga', 'mother': 'Mother', 'neighbor': 'Rottweiler'}
# the levels whose tricked visits are the code's too (code_stays_tricked)
# ... and 206's, whose untricked stays stay the video's (its mobile lap has
# visits the PC's does not: lap_model_s2.TRICKED_ROWS)
TRICKED = CODE + (206,)


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


def clip_secs(n):
    """({item: {clip: seconds}}, {item: wait}) of CLIPS and WAITS, read from the
    level data and the code (tools/pcref/lap_model_s2.py)"""
    if n not in CLIPS and n not in WAITS:
        return {}, {}
    sys.path.insert(0, HERE)
    import lap_model_s2
    d = lap_model_s2.Data(n)
    clips = {}
    for item, table in CLIPS.get(n, {}).items():
        out = {}
        for clip, src in table.items():
            if src[0] == 'bar':
                ev, _nxt = lap_model_s2.run_step(lap_model_s2.Level(n), src[1], {})
                t = next((e[2] for e in ev if e[0] == 'WAITEVENT' and isinstance(e[2], int)), None)
                if t is not None and len(src) > 2:
                    t = t / float(src[2])      # the bar over so many mobile clips
            elif src[0] == 'anim':
                t = d.frames.get((src[1], src[2])) or d.gframes.get((src[1], src[2]))
            elif src[0] == 'none':
                t = 0                          # the PC plays nothing there
            elif src[0] == 'job':
                # another actor's action whose job posts the behaviour the
                # stand waits for, and the offer's tick, over so many clips
                t = d.job_ticks(src[1], src[2], src[3])
                if t is not None:
                    t = (t + 1) / float(src[4])
            else:
                t = d.action_ticks(src[0], src[1])
            if t is not None:
                out[clip] = round(t / 12.0, 2)
        clips[item] = out
    for item, (clip, obj, act, rec) in CREDIT.get(n, {}).items():
        # the record must sit on that action in the level's objects.xml
        text = lap_model_s2.canon.read('%s/nfh2/x/%s/objects.xml' % (
            lap_model_s2.canon.ROOT, lap_model_s2.canon.pc_level(n)['folder']))
        m = re.search(r'<object name="%s"[^>]*>(.*?)</object>' % re.escape(obj), text, re.S)
        am = m and re.search(r'<action name="%s"[^>]*>(.*?)</action>' % act, m.group(1), re.S)
        assert am and 'name="%s"' % rec in am.group(1), (obj, act, rec)
        clips.setdefault(item, {})['@credit'] = clip
    waits = {}

    def part(p):
        # (object, action): the action's ticks; (object, action, actor): an
        # action whose job posts a behaviour, to its offer's tick
        if len(p) == 3:
            return (d.job_ticks(*p) or 0) + 1
        return d.action_ticks(*p) or 0
    for item, w in WAITS.get(n, {}).items():
        then = sum(part(p) for p in w['then'])
        waits[item] = {'clip': w['clip'], 'role': w['role'], 'item': w['item'],
                       'then': round(then / 12.0, 2)}
        for k in ('at', 'abort'):
            if w.get(k):
                waits[item][k] = w[k]
    return clips, waits


def behaviour_at(n):
    """{item: seconds} of BEHAVIOUR_AT, read from the level data"""
    if n not in BEHAVIOUR_AT:
        return {}
    sys.path.insert(0, HERE)
    import lap_model_s2
    d = lap_model_s2.Data(n)
    out = {}
    for item, parts in BEHAVIOUR_AT[n].items():
        t = [d.job_ticks(*p) for p in parts]
        if None not in t:
            out[item] = round((sum(t) + 1) / 12.0, 2)
    return out


def behaviour_at_end(n):
    """{item: seconds} of BEHAVIOUR_AT_END, read from the level data"""
    if n not in BEHAVIOUR_AT_END:
        return {}
    sys.path.insert(0, HERE)
    import lap_model_s2
    d = lap_model_s2.Data(n)
    out = {}
    for item, (obj, act, actor) in BEHAVIOUR_AT_END[n].items():
        j, f = d.job_ticks(obj, act, actor), d.action_ticks(obj, act, actor)
        if None not in (j, f):
            out[item] = round((j - f + 1) / 12.0, 2)
    return out


def stays_code(n):
    """{item: [seconds per visit] or None} of STAYS_CODE, read from the level data"""
    if n not in STAYS_CODE:
        return {}
    sys.path.insert(0, HERE)
    import lap_model_s2
    d = lap_model_s2.Data(n)
    out = {}
    for item, visits in STAYS_CODE[n].items():
        if visits is None:
            out[item] = None
            continue
        vals = []
        for parts in visits:
            t = 0
            for p in parts:
                t += p[1] if p[0] == 'ticks' else (d.action_ticks(*p) or 0)
            vals.append(round(t / 12.0, 2))
        out[item] = vals
    return out


def write_tricked_keys(ov, n, clips):
    """the tricked visits' keys (lap_model_s2.code_stays_tricked) into the
    overlay dict — the --write path's and --code-keys'"""
    if n not in TRICKED:
        return
    # the tricked visit (lap_model_s2.code_stays_tricked: the
    # station's step with the item's trick in the scene): its
    # stand up to the SHOUT, the SHOUT's level with the
    # repair after it (0: none) where the step has a SHOUT of a
    # level the walker reads, and the second its first named
    # record pays at (fcn.1000140b) where no clip carries it;
    # the same for the linked variant (both tricks in the
    # scene, or the script's other step) with the second the
    # linked trick's own record pays at (PCLinkedPaysAt)
    for k in ('PCUseSecondsTricked', 'PCUseSecondsLinked', 'PCShout', 'PCFixSeconds',
              'PCCreditAt', 'PCCreditAtLinked', 'PCShoutLinked', 'PCFixSecondsLinked',
              'PCLinkedPaysAt', 'PCHitSeconds', 'PCHitSecondsLinked', 'PCResumeHeadSeconds',
              'PCExtraCoinLinked', 'PCExtraPaysAtLinked', 'PCTrickArm', 'PCTrickFire',
              'PCToiletPaysAt', 'PCFixDepart'):
        ov['patches'] = _strip_key(ov['patches'], k)
    sys.path.insert(0, HERE)
    import lap_model_s2
    rage = lap_model_s2.trick_rage(n)
    for item, tr in sorted(lap_model_s2.code_stays_tricked(n).items()):
        if item in clips:
            continue      # timed per clip (CLIPS)
        if tr['tricked'] is not None and (tr['tricked'] > 0 or tr['credit'] is not None):
            # (a variant with no action of its own — 214's
            # captain's door on the bridge — plays nothing to time)
            _set_key(ov['patches'], item, 'PCUseSecondsTricked', tr['tricked'])
        if tr.get('linked') is not None:
            _set_key(ov['patches'], item, 'PCUseSecondsLinked', tr['linked'])
        if tr['shout'] is not None and tr['shout'] >= 0:
            _set_key(ov['patches'], item, 'PCShout', tr['shout'])
            _set_key(ov['patches'], item, 'PCFixSeconds', tr['repair'] or 0)
        elif tr['shout'] == -1 and (tr.get('rejoins') or 'cont' in tr):
            # no SHOUT in the tricked flow at all: no reaction
            _set_key(ov['patches'], item, 'PCShout', -1)
            _set_key(ov['patches'], item, 'PCFixSeconds', tr['repair'] or 0)
        if tr.get('hit'):
            # the co-actor's `fight` (the generic action's ticks)
            _set_key(ov['patches'], item, 'PCHitSeconds',
                     {ROLE[a]: v for a, v in tr['hit'].items() if v is not None})
        if tr['credit'] is not None and item not in CREDIT.get(n, {}):
            _set_key(ov['patches'], item, 'PCCreditAt', tr['credit'])
        if tr.get('linked_credit') is not None:
            _set_key(ov['patches'], item, 'PCCreditAtLinked', tr['linked_credit'])
        if tr.get('linked_shout') is not None and tr['linked_shout'] >= 0:
            _set_key(ov['patches'], item, 'PCShoutLinked', tr['linked_shout'])
            _set_key(ov['patches'], item, 'PCFixSecondsLinked', tr.get('linked_repair') or 0)
        if tr.get('linked_pays') is not None:
            _set_key(ov['patches'], item, 'PCLinkedPaysAt', tr['linked_pays'])
        if tr.get('linked_hit') is not None and tr.get('linked_extra_at') == tr['linked_hit']:
            # the co-actor's action the linked flow waits on,
            # the rest of the flow's parts after it, and the
            # record they pay — at the action's end
            _set_key(ov['patches'], item, 'PCHitSecondsLinked', {'Olga': tr['linked_hit']})
            _set_key(ov['patches'], item, 'PCResumeHeadSeconds', tr['linked_after_hit'])
            _set_key(ov['patches'], item, 'PCExtraCoinLinked', rage.get(tr['linked_extra']))
        elif tr.get('linked_extra_at') is not None:
            # the linked shot's third record, its own tick
            # (206's rubberrabbit: the ExtraCoin206)
            _set_key(ov['patches'], item, 'PCExtraPaysAtLinked', tr['linked_extra_at'])
        if tr.get('fix_depart') is not None:
            # the repair's walk leaves him at the repaired
            # object: his next walk from its hotspot (x, px)
            _set_key(ov['patches'], item, 'PCFixDepart', list(tr['fix_depart']))
        if tr.get('toilet_pays_at') is not None:
            # the rush's own record, its tick into the wc's
            # action (211's wcright, 27 of the puke's 40)
            _set_key(ov['patches'], item, 'PCToiletPaysAt', tr['toilet_pays_at'])
        if tr.get('arm') and tr.get('hit'):
            # the visits the trick arms and fires at (206's
            # load and shoot: lap_model_s2.TRICKED_ARM)
            _set_key(ov['patches'], item, 'PCTrickArm', tr['arm'])
        elif tr.get('arm'):
            # the linked item's own firing visit and the visit
            # that drops it (206's harpoon: the take, the put)
            _set_key(ov['patches'], item, 'PCTrickFire', tr['arm'])


def write_code_stays(ov, n, clips):
    """the stays the level script times (code_stays, RUSH, STAYS_CODE) into
    the overlay dict in place of those items' — the --write path's for
    them, the visits per item the overlay's own count (the video pairing's
    at the last --write)"""
    if n not in CODE:
        return
    sys.path.insert(0, HERE)
    import lap_model_s2
    lead = LEAD_MOBILE.get(n, {})

    def visits(item):
        for e in ov['patches']:
            st = e.get('set') or {}
            if e.get('object') == item and 'PCUseSeconds' in st:
                v = st['PCUseSeconds']
                return max(1, (len(v) if isinstance(v, list) else 1) - lead.get(item, 0))
        return 1

    def put(item, vals):
        vals = [0] * lead.get(item, 0) + list(vals)
        _strip_item_key(ov['patches'], item, 'PCUseSeconds')
        _set_key(ov['patches'], item, 'PCUseSeconds', vals if len(vals) > 1 else vals[0])
    for item, secs in sorted(lap_model_s2.code_stays(n).items()):
        if item in clips and item not in KEEP_STAYS.get(n, ()):
            continue
        put(item, list(secs) if isinstance(secs, list) else [secs] * visits(item))
    for item, vals in stays_code(n).items():
        if vals:
            put(item, vals)
        else:
            _strip_item_key(ov['patches'], item, 'PCUseSeconds')
    if n in RUSH:
        d = lap_model_s2.Data(n)
        for item, (obj, act) in RUSH[n].items():
            t = d.action_ticks(obj, act)
            if t is not None:
                put(item, [round(t / 12.0, 2)])


def write_code_keys(n):
    """the keys read from the code and the level data alone (PCClipSeconds,
    PCWaitFor, PCCreditAfter, PCBehaviourAt) into the level's overlay — the
    --write path's, without the video pairing's idle visits"""
    p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
    ov = json.load(open(p))
    clips, waits = clip_secs(n)
    for k in ('PCClipSeconds', 'PCWaitFor', 'PCCreditAfter', 'PCBehaviourAt'):
        ov['patches'] = _strip_key(ov['patches'], k)
    for item, cl in clips.items():
        cl = dict(cl)
        credit = cl.pop('@credit', None)
        if cl:
            _set_key(ov['patches'], item, 'PCClipSeconds', cl)
        if credit:
            _set_key(ov['patches'], item, 'PCCreditAfter', credit)
    for item, wt in waits.items():
        _set_key(ov['patches'], item, 'PCWaitFor', wt)
    for item, secs in behaviour_at(n).items():
        _set_key(ov['patches'], item, 'PCBehaviourAt', secs)
    ov['patches'] = _strip_key(ov['patches'], 'PCBehaviourAtEnd')
    for item, secs in behaviour_at_end(n).items():
        _set_key(ov['patches'], item, 'PCBehaviourAtEnd', secs)
    write_tricked_keys(ov, n, clips)
    write_code_stays(ov, n, clips)
    json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
    print('   written', p)


def main(argv):
    write = '--write' in argv
    if '--code-keys' in argv:
        for n in [int(a) for a in argv if a.isdigit()]:
            write_code_keys(n)
        return
    levels = [int(a) for a in argv if a.isdigit()] or list(range(201, 215))   # or 101-114 with the Season 1 idle visits
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
                if isinstance(secs, list):
                    # one per visit, in the routine's order
                    print('   %-26s code %s s per visit (video %s)' % (item, secs, per.get(item)))
                    per[item] = list(secs)
                    continue
                k = len(per.get(item, [])) or 1
                print('   %-26s code %5.2f s (video %s)' % (item, secs, per.get(item)))
                per[item] = [secs] * k
        for item, vals in stays_code(n).items():
            # the level script's stays over the video's split
            print('   %-26s code %s s per visit (video %s)' % (item, vals, per.get(item)))
            if vals:
                per[item] = list(vals)
            else:
                per.pop(item, None)
        clips, waits = clip_secs(n)
        for item in clips:
            if item not in KEEP_STAYS.get(n, ()):
                per.pop(item, None)        # timed per clip, no whole stay
        for item, cl in sorted(clips.items()):
            print('   %-26s clips %s' % (item, ', '.join('%s %s' % kv for kv in sorted(cl.items()))))
        for item, wt in sorted(waits.items()):
            print('   %-26s holds %s until %s %s %s, then %.2f s' % (
                item, wt['clip'], wt['role'], 'began' if wt.get('at') == 'start' else 'used',
                wt['item'], wt['then']))
        stays = sum(v for vals in per.values() for v in vals)
        lap = port_lap(n); walks = sum(v['walk'] for v in lap)
        print('   sum of stays %.1f + the port lap\'s walks %.1f = %.1f s' % (stays, walks, stays + walks))
        if write:      # (a level with nothing to carry loses its stale patches too)
            p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
            ov = json.load(open(p))
            if n >= 200:
                ov['patches'] = _strip_key(ov.get('patches', []), 'PCUseSeconds')
                for k in ('PCClipSeconds', 'PCWaitFor'):
                    ov['patches'] = _strip_key(ov['patches'], k)
                ov['patches'] = _strip_key(ov['patches'], 'PCCreditAfter')
                for item, cl in clips.items():
                    cl = dict(cl)
                    credit = cl.pop('@credit', None)
                    if cl:
                        _set_key(ov['patches'], item, 'PCClipSeconds', cl)
                    if credit:
                        _set_key(ov['patches'], item, 'PCCreditAfter', credit)
                for item, wt in waits.items():
                    _set_key(ov['patches'], item, 'PCWaitFor', wt)
                ov['patches'] = _strip_key(ov['patches'], 'PCBehaviourAt')
                for item, secs in behaviour_at(n).items():
                    _set_key(ov['patches'], item, 'PCBehaviourAt', secs)
                ov['patches'] = _strip_key(ov['patches'], 'PCBehaviourAtEnd')
                for item, secs in behaviour_at_end(n).items():
                    _set_key(ov['patches'], item, 'PCBehaviourAtEnd', secs)
                write_tricked_keys(ov, n, clips)
            for item, vals in per.items():
                vals = [0] * LEAD_MOBILE.get(n, {}).get(item, 0) + vals
                _set_key(ov['patches'], item, 'PCUseSeconds', vals if len(vals) > 1 else vals[0])
            if n >= 200 and n in RUSH:
                d = lap_model_s2.Data(n)
                for item, (obj, act) in RUSH[n].items():
                    t = d.action_ticks(obj, act)
                    if t is not None:
                        _set_key(ov['patches'], item, 'PCUseSeconds', round(t / 12.0, 2))
            note = ' Station durations (tools/pcref/pc_durations_s2.py): the PC video bubble spans of docs/PC_LAPS_DETAIL.md less the walk to each station where the spans touch (an unlabelled gap before a span is walk outside it), PCUseSeconds per visit.'
            if n in CODE:
                note = ' Station durations (tools/pcref/pc_durations_s2.py): GameLogic.dll\'s level script (tools/pcref/lap_model_s2.py code_stays: the untricked lap\'s actions, hideouts and bars per mobile item), the PC video bubble spans of docs/PC_LAPS_DETAIL.md less the walk for the items the model leaves untimed, PCUseSeconds per visit.'
            src = ov['source']
            i = src.find(' Station durations (tools/pcref/pc_durations_s2.py)')
            if i >= 0:
                # the note in its place (its own last words end it)
                end = 'PCUseSeconds per visit.'
                j = src.find(end, i)
                j = j + len(end) if j >= 0 else src.find(' The ', i + 1)
                src = src[:i] + note + (src[j:] if j >= 0 else '')
            else:
                src += note
            ov['source'] = src
            json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
            print('   written', p)


if __name__ == '__main__':
    main(sys.argv[1:])
