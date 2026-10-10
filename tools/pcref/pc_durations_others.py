"""The other actors' stands under the PC profile, from the PC data.

    python3 tools/pcref/pc_durations_others.py            # print the pairings
    python3 tools/pcref/pc_durations_others.py --write    # rewrite the PCUseSecondsRole patches

The stands are the code's where her script's lap is read (ROLE_LAPS,
lap_model_s2.role_lap: each station a step — its GoTo, the DoActions job of the
Loader's time + 2, the step's own two ticks; a hideout left by the route of
the walk after it); elsewhere a `<action actor="mother" … time="N">` of the PC
level's objects.xml as N ticks (12 per second) — `time="auto"` lasts its clip
and a loop's length is not in the data, so only the explicit waits are carried.
The mobile stands come from the profile's idle runs (runs/idlepc2s2, the other
roles' `using` stretches — NFH_SCRATCH/s2_idle_others.json) and are paired by
hand per level in ALIAS: a mobile stand that covers two PC stations in one room
takes their sum less the walk between.

Her script is the one GameLogic.dll's registry pairs with her level folder
(0x10011000-0x10013fff: each folder's actors and their scripts' factories —
in_c1's `mother` 0x1001d2ec, in_c2's 0x1001f87a, ship3's 0x1002f92e, me_c1's
0x1003533d; the factory's constructor stores her first step), and where the
mobile list starts elsewhere her ActionManager starts at that step's item
(ROLE_START).

A Mother's bar in her own script (BARS: 214's deck chair — GameLogic.dll's
sleep step 0x1003a0b8 walks her to the chair and holds her there for the
ticks it pushes to fcn.1000e7f2, 600 at 0x1003a1e0, before the reling step
0x10039f34) is carried with the chair's clips: PCSitSeconds the chair's `enter`
(the mobile's sit, MotherSleepBehaviour's FirstAnimation), PCSleepSeconds the
bar's ticks (her sleeps) and PCGetUpSeconds the chair's `leave` (the get-up,
its LastAnimation) — MotherSleepBehaviour's PC arm plays them at that pace."""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRATCH = os.environ.get('NFH_SCRATCH', '/tmp/claude-1000/-home-akawolf-projects-own-NFH/ac3a80a3-83a6-48a6-96d4-81dc371f54eb/scratchpad')
PCX = os.environ.get('NFH_PCREF', os.path.expanduser('~/nfh-bench/pcref/pc/nfh2/x'))
S2 = {201: 'ship1', 202: 'cn_b1', 203: 'cn_c2', 204: 'cn_c1', 205: 'cn_b2', 206: 'ship2', 207: 'in_b1',
      208: 'in_c1', 209: 'in_c2', 210: 'in_b2', 211: 'ship3', 212: 'me_c1', 213: 'me_c2', 214: 'ship4'}
# level -> mobile item -> (role, [PC "object.action" ...], walk between them in s)
ALIAS = {
    # 212's waits by their rooms (their PCApproach, the mobile scene's
    # zones: Zone04 the midleft room of the red bull, Zone03 the midright
    # of the statue) — and the bubble's icons, the mobile's bull at
    # MumWaitZone4, E12's bull's head over her first 15.3 s, the red
    # bull's `use` of 144 ticks after her walk (paired the other way round
    # until 2026-09-30)
    212: {'MumWaitZone3': ('Mother', ['midright/statue_hideout.use'], 0.0),
          'MumWaitZone4': ('Mother', ['midleft/red_bull.use'], 0.0)},
    213: {'MotherWaitZone2': ('Mother', ['bottomright/water.use'], 0.0),
          # the port's Zone05 holds the statue and the flowers; her script's
          # lap is the water and the flowers alone (0x100372f0 <->
          # 0x100374a6): me_c2's statue_hideout `use` for her is data no
          # step plays (until 2026-10-03 summed with the flowers', less a
          # 2-s walk)
          'MotherWaitZone5': ('Mother', ['topright/flowers.use'], 0.0)},
    # her reling step after the sleep (0x10039f34: the GoTo and the reling's use)
    214: {'MotherWait': ('Mother', ['bottomright/reling.use'], 0.0)},
    # her shop step (0x1001f729: the GoTo and the fakir's shop's `use`, 120
    # ticks) — the mobile's MotherStart, its MotherStandDownSingle
    209: {'MotherStart': ('Mother', ['bazar/shop.use'], 0.0)},
}
# level -> role -> the step her script's lap starts from (lap_model_s2.role_lap):
# the stays are the code's since 2026-10-03 — each station a step (the GoTo,
# the DoActions `use`: the Loader's time + 2, the step's own 2 ticks), a chair
# left by the route of the walk after it — where they had been the data's
# `time` alone (212's Mother 212: the statue 0x10035048 <-> the red bull
# 0x10035208; 213: the water 0x100372f0 <-> the flowers 0x100374a6; 214: the
# deck chair 0x1003a0b8, the reling 0x10039f34)
# 209's Mother: the fakir's shop 0x1001f729 <-> the dressing room's bar
# 0x1001f564 (the script registry's in_c2 `mother`, 0x1001f87a: her first step)
# 210's Olga: her mat's bar 0x1001bced, the leave 0x1001bb8d, the shower
# 0x1001ba35 (its go-and-enter), the bra put and the wait 0x1001b8c3, the bra
# taken and the leave 0x1001b5e1 (in_b2's `olga`, 0x1001bea9)
ROLE_LAPS = {209: {'Mother': 0x1001f729}, 210: {'Olga': 0x1001bced}, 212: {'Mother': 0x10035048},
             213: {'Mother': 0x100372f0}, 214: {'Mother': 0x1003a0b8}}
# level -> role -> the mobile item her script's first step stands for, where
# the mobile list starts elsewhere: the ActionManager starts there and wraps to
# 0 (ActionStartIndex, LoopFromStartIndex off — AdvanceActionIndex's third
# arm, ActionManager.cs:566-584). 209's Mother goes to the fakir's shop first
# (her constructor's step 0x1001f821 stores 0x1001f729), the mobile to the
# dressing room
ROLE_START = {209: {'Mother': 'MotherStart'},
              # 210's Olga lies on her mat first (0x1001bced), the mobile's
              # list starts at the shower (ActionStartIndex 1)
              210: {'Olga': 'OlgaMatBeach'}}
# level -> mobile item -> (the Mother script's sleep step, the chair) — the step
# whose fcn.1000e7f2 bar holds her in the chair (lap_model_s2.run_step reads the
# pushed ticks)
BARS = {214: {'DeckChairMother': (0x1003a0b8, 'topright_deckchair')}}
# level -> mobile item -> (role, {mobile clip: the PC's part}) — another actor's
# clips at the PC's ticks (PCClipSecondsRole): (object, action) of the level
# data — with 'step' the stand's first clip after her walk, the step's own
# ticks before it (lap_model_s2.WALK_STEP_TICKS) —, ('anim', object, clip) a
# clip's frames (a loop's pace). 202's Olga on
# her mat (beachleft/mat_olga_guarded: `enter`, the `sun` loop, the `wakeup`
# her script plays on `kid_cry`, 0x100233ed, and `leave`) and at the sub
# (beachleft/sub's `take`, takesub; the shark's, takeshark)
# 210's Mother (her script: 0x10018c0b sits her in pool/deckchair — its
# `enter`, sitdown — for fcn.1000e7f2's 240-tick bar asleep, the chair's
# `sleep`; the check 0x10018983 at its end sends her to 0x100187d8, 180 ticks
# awake — the chair's `awake`, fcn.100185e5 — and back to the 240 while he is
# not in his chair, else gets her up — the chair's `leave`, getup — and plays
# `callneighbor`, then — her order step 0x10018682 polling for him at its
# `neighbor` hotspot, fcn.1000e172 — `order`): no pillow pose of its own, the
# three sleeps the 240 (the mobile's repeat, TargetSequenceIndex 2, is the
# three alone), the look the 180; her wait for him at the call held (WAITS_ROLE)
# 207's Mother (her script: 0x100140af to the pool — its `enter`, m_enter —
# for a bar of 200 ticks, 0x1001447d to the deck chair — its `enter`, sitdown
# — for 240, then the check 0x100141e0, which keeps her in the chair while he
# is in the pool room and else sends her to the pool again, leaving the chair —
# getup — and the pool — m_leave — on the way): the pool's two swims the 200,
# the chair's three sleeps the 240
CLIPS_ROLE = {207: {'DeckChair': ('Mother', {'MotherSitPillow': ('pool_deckchair', 'enter', 'step'),
                                             'MotherSleepLoop': ('bar', 0x1001447d, 3),
                                             'MotherGetUpPillow': ('pool_deckchair', 'leave')}),
                    'PoolLadder': ('Mother', {'MotherPoolLadderEnter': ('pool_pool', 'enter', 'step'),
                                              'MotherPoolLadderSwim': ('bar', 0x100140af, 2),
                                              'MotherPoolLadderLeave': ('pool_pool', 'leave')}),
                    # 207's Olga onto her mat (her step 0x100174a5: the GoTo and
                    # the go-and-enter's `enter` of beachright/mat_guarded), asleep
                    # on it after
                    'ShellLaydown': ('Olga', {'BeachLayDown': ('beachright_mat_guarded', 'enter', 'step')})},
              210: {'DeckChairMother': ('Mother', {'MotherSitPillow': ('pool_deckchair', 'enter', 'step'),
                                                   'MotherSleepPillow': ('ticks', 0),
                                                   'MotherSleepSingle': ('bar', 0x10018c0b, 3),
                                                   'MotherLookLoop': ('bar', 0x100187d8),
                                                   'MotherGetUpPillow': ('pool_deckchair', 'leave')}),
                    'CallRTMother': ('Mother', {'MotherCall': ('mother', 'callneighbor'),
                                                'MotherOrder': ('mother', 'order')}),
                    # 210's Olga in the shower (her lap, ROLE_LAPS: the go-and-
                    # enter's `enter`, the bra put, the 120-tick wait, the bra
                    # taken, the `leave`) — the mobile's water loop the wait
                    'OlgaShower': ('Olga', {'OlgaShowerEnter': ('part', 'beachleft_shower_guarded', 'enter'),
                                            'OlgaShowerPutBra': ('part', 'beachleft_shower_guarded', 'putbra'),
                                            'OlgaShowerWater': ('part', '-', 'wait'),
                                            'OlgaShowerTakeBra': ('part', 'beachleft_shower_guarded', 'takebra'),
                                            'OlgaShowerLeave': ('part', 'beachleft_shower_guarded', 'leave')})},
              202: {'OlgaMat': ('Olga', {'BeachLayDown': ('beachleft_mat_olga_guarded', 'enter', 'step'),
                                         'TowelSleep': ('anim', 'beachleft/mat_olga_guarded', 'sun'),
                                         'TowelLaydown': ('beachleft_mat_olga_guarded', 'wakeup'),
                                         'BeachGetUp': ('beachleft_mat_olga_guarded', 'leave')}),
                    'Submarine': ('Olga', {'OlgaPutSub': ('beachleft_sub', 'take', 'step'),
                                           'OlgaPutSubTricked': ('beachleft_shark', 'take', 'step')})},
              # 206's Mother after the lesson (her script: 0x1002b9fe to her
              # chair — its `enter`, sitdown_pillow — for fcn.1000e7f2's
              # 720-tick bar asleep, the chair's `sleep`; 0x1002b972 then
              # clears her flag 4 and shows the chair's `look`, and
              # 0x1002b72a counts 360 ticks, 0x168 at 0x1002b73f, before the
              # chair's `sleep_pillow`, her flag 4 set, and the 720 again):
              # the mobile's second-use set, the nine sleeps the 720 and the
              # two looks the 360 (TutorialPC206 gives her first visit the
              # sit alone)
              206: {'DeckChair': ('Mother', {'MotherSitPillow': ('topleft_deckchair', 'enter', 'step'),
                                             'MotherSleepLoop': ('bar', 0x1002b9fe, 9),
                                             'MotherLook': ('ticks', 180)})},
              # 208's and 209's Mother in the dressing room (her step 0x1001d1b2 /
              # 0x1001f564: the GoTo, then fcn.1000e7f2's 360-tick bar inside —
              # the room's `enter` first, its `leave` the route's as she walks on):
              # the mobile's Hide_In, thirty MotherRoomIdle and Hide_Out; 208's at
              # Fifi (0x1001d030: the GoTo alone while Fifi is there, then the
              # dressing room — the step's own ticks, lap_model_s2.WALK_STEP_TICKS)
              208: {'DressingRoom': ('Mother', {'Hide_In': ('bazar_dressing_room', 'enter', 'step'),
                                                'MotherRoomIdle': ('bar', 0x1001d1b2, 30),
                                                'Hide_Out': ('bazar_dressing_room', 'leave')}),
                    'Fifi': ('Mother', {'MotherStandDownSingle': ('step',)})},
              209: {'DressingRoom': ('Mother', {'Hide_In': ('bazar_dressing_room', 'enter', 'step'),
                                                'MotherRoomIdle': ('bar', 0x1001f564, 30),
                                                'Hide_Out': ('bazar_dressing_room', 'leave')})},
              # 211's Mother (her script: 0x1002f83f to topright/deckchair — its
              # `enter`, sitdown — for fcn.1000e7f2's 240-tick bar asleep, then
              # 0x1002f570 to the kid for his `shout`, her walk leaving the chair
              # — getup): no pillow pose of its own, the three sleeps the 240
              211: {'DeckChairMother': ('Mother', {'MotherSitPillow': ('topright_deckchair', 'enter', 'step'),
                                                   'MotherSleepPillow': ('ticks', 0),
                                                   'MotherSleepSingle': ('bar', 0x1002f83f, 3),
                                                   'MotherGetUpPillow': ('topright_deckchair', 'leave')}),
                    'OlgaChild': ('Mother', {'MotherBawlLeft': ('kid', 'shout', 'step')}),
                    # 211's Olga into the toilet (her step 0x10031591: the GoTo
                    # and wcright's `enter`, olga_enter) and out of it (the
                    # `bonbons` handler's `leave`, olga_leave) — held inside
                    # until then (WAITS_ROLE)
                    'ToiletWomen': ('Olga', {'OlgaWCEnter': ('topleft_wcright', 'enter', 'step'),
                                             'OlgaWCLeave': ('topleft_wcright', 'leave')})},
              # 204's Olga into the rickshaw (her step 0x10033305: the go-and-
              # enter's `enter`, waiting inside after)
              204: {'PullKart': ('Olga', {'RickshawEnter': ('groundleft_rickshaw', 'enter', 'step')})},
              # 201's Olga at the buffet (her step 0x1002abfa: the GoTo and the
              # `eat`, the step run again as each ends — no next step) and her
              # `crash` on his flirt at the damaged one (`buffet_crash`,
              # 0x1002ae7b)
              201: {'Buffet': ('Olga', {'BuffetEat': ('topleft_buffet', 'eat', 'again'),
                                        'BuffetCrash': ('topleft_buffet_damaged', 'crash')})},
              # 214's Olga at the pillar (her step 0x1003c2a0 after `flowers`:
              # the GoTo and her own `wait`, 30 ticks) — the mobile's
              # BirdPerch, five OlgaStandDownInfinite
              214: {'BirdPerch': ('Olga', {'OlgaStandDownInfinite': ('split', 'olga', 'wait', 5)})},
              # 213's Olga on the bull (her step 0x10039078: the walk to it, the
              # latch her `bull` handler sets — his controls step posts it as
              # he arrives, 0x10037f5e — and bottomleft/bullride_olga's `use`,
              # ride, whose job posts `leave` to him as it ends)
              213: {'MechanicalBull': ('Olga', {'BullRide': ('bottomleft_bullride_olga', 'use', 'step')}),
                    # ... and into the picnic (0x100392f2: the GoTo and the
                    # picnic's `enter`, olga_enter) and out of it (0x100391cc on
                    # his `leave`: hers, olga_leave) — held inside until then
                    # (WAITS_ROLE)
                    'BoatPicnic': ('Olga', {'PicnicEnter': ('bottomright_picnic', 'enter', 'step'),
                                            'PicnicLeave': ('bottomright_picnic', 'leave')})}}


# level -> mobile item -> {the item's clip: the PC's part} — an item's own
# clips while another role uses it hidden (PCItemClipSeconds): 205's mat,
# Olga's lie-down (the mat's `enter`), the sun loop, the `wakeup` and the
# `leave` her `pingpong` step plays (0x10025b2a) — the mobile's UseNormal-
# Sequence, frame for frame the PC's at 8 a second
ITEM_CLIPS = {205: {'OlgaMatBeach': ('Olga', {'N2TrickItemExtra1': ('beachright_mat_guarded', 'enter', 'step'),
                                              'N2TrickItemUseNormal': ('anim', 'beachright/mat', 'sun'),
                                              'N2TrickItemExtra3': ('beachright_mat_guarded', 'wakeup'),
                                              'N2TrickItemExtra2': ('beachright_mat_guarded', 'leave')})},
              # 210's mat under Olga: her lap's `enter`, the 120-tick bar
              # asleep and the `leave` (0x1001bced, 0x1001bb8d)
              210: {'OlgaMatBeach': ('Olga', {'N2TrickItemExtra1': ('part', 'beachleft_mat_olga_guarded', 'enter'),
                                              'N2TrickItemUseNormal': ('part', 'beachleft_mat_olga_guarded', 'bar'),
                                              'N2TrickItemExtra2': ('part', 'beachleft_mat_olga_guarded', 'leave')})}}
# level -> mobile item -> (role, wait): another actor's clip held until a role
# has used an item or begun to (PCWaitForRole, the runtime's PCWaitFor for that
# role): 210's Mother waits at her chair after the call until he stands there
# (her order step's poll) — his use of the call begun
WAITS_ROLE = {210: {'CallRTMother': ('Mother', {'clip': 'MotherStandDownInfinite', 'role': 'Rottweiler',
                                                'item': 'CallRTMother', 'at': 'start', 'then': 0.0})},
              # 211's Olga on his uses (her script's handler 0x10031888, the
              # behaviours his actions post as their jobs end — ship3's
              # objects.xml): in the toilet until the dish's `bonbons` (the
              # mobile's Sweets), at the kid until the rod's `roddone`
              # (FishingRod), at the reling until the diving gear's `goup`
              # (DivingGear)
              211: {'ToiletWomen': ('Olga', {'clip': 'OlgaWCUse', 'role': 'Rottweiler', 'item': 'Sweets',
                                             'then': 0.0}),
                    'OlgaStandStill': ('Olga', {'clip': 'OlgaStandUpInfinite', 'role': 'Rottweiler',
                                                'item': 'FishingRod', 'then': 0.0}),
                    'OlgaSeaView': ('Olga', {'clip': 'OlgaStandLeftInfinite', 'role': 'Rottweiler',
                                             'item': 'DivingGear', 'then': 0.0})},
              # 213's Olga (her script's latches, 0x100393ee): at her towel until
              # `boat`, posted as he arrives at the tortilla (0x10038696: its
              # use begun), in the picnic until his `leave` there (his
              # BoatPicnic's end), at the bull until `bull`, posted as he
              # arrives at its controls (0x10037f5e) — the first of the two
              # MechanicalBullControls visits (`visit`: his list's first)
              213: {'OlgaBackTowel': ('Olga', {'clip': 'Workout', 'role': 'Rottweiler', 'item': 'Tortilla',
                                               'at': 'start', 'then': 0.0}),
                    'BoatPicnic': ('Olga', {'clip': 'PicnicWait', 'role': 'Rottweiler', 'item': 'BoatPicnic',
                                            'then': 0.0}),
                    'MechanicalBullWait': ('Olga', {'clip': 'OlgaStandUpInfinite', 'role': 'Rottweiler',
                                                    'item': 'MechanicalBullControls', 'at': 'start',
                                                    'visit': 0, 'then': 0.0})},
              # 214's Olga at the bouquet (0x1003c19e) until his `use` of it
              # posts `flowers` — her handler (0x1003c37a) pushes her own `wait`
              # (`then_action`, its job's ticks) before the pillar step;
              # bouquet_manip's `crash` sends her on at once (`then_tricked`)
              214: {'Glass': ('Olga', {'clip': 'OlgaStandDownInfinite', 'role': 'Rottweiler', 'item': 'Bouquet',
                                       'then_action': ('olga', 'wait'), 'then_tricked': 0.0})}}


def item_clips(n):
    """{item: {clip: seconds}} of ITEM_CLIPS (the specs of CLIPS_ROLE)"""
    return {item: cl for item, (_role, cl) in role_clips(n, ITEM_CLIPS).items()}


def role_clips(n, tables=CLIPS_ROLE):
    """{item: (role, {clip: seconds})} of CLIPS_ROLE, read from the level data"""
    if n not in tables:
        return {}
    sys.path.insert(0, HERE)
    import lap_model_s2
    d = lap_model_s2.Data(n)
    out = {}
    for item, (role, table) in tables[n].items():
        cl = {}
        for clip, src in table.items():
            if src[0] == 'anim':
                t = d.frames.get((src[1], src[2]))
            elif src[0] == 'ticks':
                t = src[1]
            elif src[0] == 'part':
                # a part of her lap by code (ROLE_LAPS, lap_model_s2.role_lap):
                # its ticks with the step's own that go with it
                t = next((pt for _c, ps in lap_model_s2.role_lap(n, ROLE_LAPS[n][role], role.lower())
                          for o, a, pt in ps if (o, a) == (src[1], src[2])), None)
            elif src[0] == 'step':
                # a stand the step plays nothing at: its own ticks (a GoTo's
                # done tick, the next step's first)
                t = lap_model_s2.WALK_STEP_TICKS
            elif src[0] == 'split':
                # a walking step's one DoAction over so many mobile clips (214's
                # pillar: Olga's `wait`, 0x1003c2a0, for the five stands)
                t = d.action_ticks(src[1], src[2], actor=role.lower())
                if t is not None:
                    t = (t + lap_model_s2.WALK_STEP_TICKS) / float(src[3])
            elif src[0] == 'bar':
                ev, _nxt = lap_model_s2.run_step(lap_model_s2.Level(n), src[1], {})
                t = next((e[2] for e in ev if e[0] == 'WAITEVENT' and isinstance(e[2], int)), None)
                if t is not None and len(src) > 2:
                    # the bar less so many ticks, over so many mobile clips
                    t = (t - (src[3] if len(src) > 3 else 0)) / float(src[2])
            else:
                t = d.action_ticks(src[0], src[1], actor=role.lower())
                if t is not None and len(src) > 2 and src[2] == 'step':
                    # the stand's first clip after her walk: the step's own
                    # ticks before it (lap_model_s2.WALK_STEP_TICKS)
                    t += lap_model_s2.WALK_STEP_TICKS
                elif t is not None and len(src) > 2 and src[2] == 'again':
                    # an action the step pushes again each time it runs at
                    # the same place: the step's one tick with it (201's
                    # buffet, 0x1002abfa, stores no next step)
                    t += 1
            if t is not None:
                cl[clip] = round(t / 12.0, 2)
        out[item] = (role, cl)
    return out


def role_parts(n, role):
    """{(object, action): [ticks per visit]} of the role's lap by code
    (lap_model_s2.role_lap from ROLE_LAPS), objects in 'room/object' form"""
    sys.path.insert(0, HERE)
    import lap_model_s2
    st = ROLE_LAPS.get(n, {}).get(role)
    if st is None:
        return {}
    d = lap_model_s2.Data(n)
    out = {}
    for _cur, parts in lap_model_s2.role_lap(n, st, role.lower()):
        for o, a, t in parts:
            out.setdefault((d.real.get(o, o), a), []).append(t)
    return out


def bar_secs(n, step, chair):
    """(sit, sleep, get-up) seconds: the chair's `enter` with the step's own
    ticks, the bar's ticks and the chair's `leave` — the route's first job
    on her walk to the reling (lap_model_s2.role_lap) — at 12 ticks a
    second"""
    sys.path.insert(0, HERE)
    import lap_model_s2
    lap = lap_model_s2.role_lap(n, ROLE_LAPS[n]['Mother'], 'mother')
    # the chair's parts wherever her lap has them (214's `enter` is the
    # go-and-enter step's before the bar step, 0x10039e6c)
    parts = {(o, a): t for cur, ps in lap for o, a, t in ps if o == chair}
    sit, sleep, leave = parts[(chair, 'enter')], parts[(chair, 'bar')], parts[(chair, 'leave')]
    return round(sit / 12.0, 2), round(sleep / 12.0, 2), round(leave / 12.0, 2)


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


def role_index(n, role, item, visit=0):
    """the role's routine index of the item's `visit`-th entry (mobile level
    data)"""
    raw = json.load(open(os.path.join(ROOT, 'levels', 's2', 'Level%d.json' % n)))
    objs = raw['objects']
    def goname(o):
        g = ((o.get('data') or {}).get('m_GameObject') or {}).get('path')
        return ((objs.get(str(g)) or {}).get('data') or {}).get('name')
    for o in objs.values():
        d = o.get('data') or {}
        if o.get('type') != 'ActionManager' or (d.get('Owner') or {}).get('type') != role:
            continue
        names = [goname(objs.get(str((a.get('Item') or {}).get('path'))) or {}) for a in d.get('Actions') or []]
        return [k for k, nm in enumerate(names) if nm == item][visit]
    raise KeyError('%d: no %s ActionManager' % (n, role))


def role_start(n, role, item):
    """(the role's ActionManager GameObject name, the index of `item` in its
    Actions) of the mobile level data"""
    raw = json.load(open(os.path.join(ROOT, 'levels', 's2', 'Level%d.json' % n)))
    objs = raw['objects']
    def goname(o):
        g = ((o.get('data') or {}).get('m_GameObject') or {}).get('path')
        return ((objs.get(str(g)) or {}).get('data') or {}).get('name')
    for o in objs.values():
        d = o.get('data') or {}
        if o.get('type') != 'ActionManager' or (d.get('Owner') or {}).get('type') != role:
            continue
        names = [goname(objs.get(str((a.get('Item') or {}).get('path'))) or {}) for a in d.get('Actions') or []]
        return goname(o), names.index(item)
    raise KeyError('%d: no %s ActionManager' % (n, role))


def pc_actions(d):
    """(actor, object, action name, actoranim, seconds|'auto') of the level's objects.xml"""
    p = os.path.join(PCX, d, 'objects.xml')
    raw = open(p, 'rb').read()
    t = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')
    obj = None; out = []
    for m in re.finditer(r'<object name="([^"]*)"|<action ([^>]*)/?>', t):
        if m.group(1):
            obj = m.group(1); continue
        a = m.group(2)
        g = lambda k: (re.search(r'(?:^| )' + k + r'="([^"]*)"', a) or [None, None])[1]
        tv = g('time') or 'auto'
        out.append((g('actor'), obj, g('name'), g('actoranim'), round(int(tv) / 12.0, 1) if tv.isdigit() else tv))
    return out


# level -> mobile item -> (role, icon spec): another role's bubble at the
# item where her script's icon element (fcn.100422a5) is not the mobile
# item's — ('step', address) the icon that step sets, ('icon', name) one read
# off a branch the walker does not take ('' none)
ICON_ROLE = {
    # 209's shop step 0x1001f729 sets the fakir's shop (E09: Ramschid's over
    # her first 13 s), the mobile's MotherStart the shoe cleaner
    209: {'MotherStart': ('Mother', ('step', 0x1001f729))},
    # 211's script sets her none (0x1002f83f, the chair; 0x1002f570, the
    # kid): E11 shows her no bubble
    211: {'DeckChairMother': ('Mother', ('icon', '')), 'OlgaChild': ('Mother', ('icon', ''))},
    # 213's water step 0x100372f0 and 214's reling step 0x10039f34 set
    # `water`, the mobile's waits goswim
    213: {'MotherWaitZone2': ('Mother', ('step', 0x100372f0))},
    214: {'MotherWait': ('Mother', ('step', 0x10039f34))},
    # 206's after the lesson: her chair step 0x1002b9fe clears it (E06: none
    # from her sleep on)
    206: {'DeckChair': ('Mother', ('step', 0x1002b9fe))},
}
# level -> mobile item -> (role, {clip: icon spec}): the clips of her stays
# under other icons — ('bar',) none (fcn.1000e7f2's stay hides the bubble
# until a step sets an icon again), ('step', address) the icon of the step
# whose route plays the clip's leave, ('icon', name) a branch's
ICON_CLIPS_ROLE = {
    # 207: the pool's bar, the chair step 0x1001447d's route out of the pool
    # (E07: the deck chair's icon at 47.87, over the ladder); the chair's
    # bar (the check step 0x100141e0 sets the chair's icon again for the
    # get-up)
    207: {'PoolLadder': ('Mother', {'MotherPoolLadderSwim': ('bar',),
                                    'MotherPoolLadderLeave': ('step', 0x1001447d)}),
          'DeckChair': ('Mother', {'MotherSleepLoop': ('bar',)})},
    # 208's and 209's dressing room: the bar, the next step's route out of
    # it (Fifi's 0x1001d030 — E08: fifi at 36.47 —, the shop's 0x1001f729)
    208: {'DressingRoom': ('Mother', {'MotherRoomIdle': ('bar',), 'Hide_Out': ('step', 0x1001d030)})},
    209: {'DressingRoom': ('Mother', {'MotherRoomIdle': ('bar',), 'Hide_Out': ('step', 0x1001f729)})},
    # 210's deck chair: the sleep's bar, the awake one (0x100187d8 clears
    # the icon for it), and the check's call branch (0x10018a93: the
    # neighbour's icon, then the chair's `leave`, E10: 22.34)
    210: {'DeckChairMother': ('Mother', {'MotherSleepPillow': ('bar',), 'MotherSleepSingle': ('bar',),
                                         'MotherLookLoop': ('bar',),
                                         'MotherGetUpPillow': ('icon', 'neighbor')})},
    # 214's deck chair: the bar, the reling step 0x10039f34's route out of
    # the chair
    214: {'DeckChairMother': ('Mother', {'MotherSleepSingle': ('bar',),
                                         'MotherGetUpPillow': ('step', 0x10039f34)})},
}


def _role_icon(n, spec):
    import lap_model_s2
    if spec[0] == 'bar':
        return ''
    if spec[0] == 'icon':
        return spec[1]
    return lap_model_s2.step_icon(n, spec[1]) or ''


def icon_role_keys(n):
    """{item: {PCIconRole: {role: icon}} | {PCIconClipsRole: {role: {clip:
    icon}}}} of ICON_ROLE and ICON_CLIPS_ROLE"""
    sys.path.insert(0, HERE)
    out = {}
    for item, (role, spec) in ICON_ROLE.get(n, {}).items():
        out.setdefault(item, {})['PCIconRole'] = {role: _role_icon(n, spec)}
    for item, (role, clips) in ICON_CLIPS_ROLE.get(n, {}).items():
        out.setdefault(item, {})['PCIconClipsRole'] = {role: {c: _role_icon(n, sp) for c, sp in clips.items()}}
    return out


def write_icon_role_keys(n):
    p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
    ov = json.load(open(p))
    for k in ('PCIconRole', 'PCIconClipsRole'):
        ov['patches'] = _strip_key(ov.get('patches', []), k)
    keys = icon_role_keys(n)
    for item, kv in keys.items():
        for k, v in kv.items():
            _set_key(ov['patches'], item, k, v)
    note = (' The Mother\'s bubble (tools/pcref/pc_durations_others.py ICON_ROLE, ICON_CLIPS_ROLE):'
            ' PCIconRole and PCIconClipsRole from her script\'s icon elements (GameLogic.dll'
            ' fcn.100422a5) where they are not the mobile items\' — \'\' no bubble: a null icon,'
            ' and a bar (fcn.1000e7f2) until the next icon.')
    if keys and note not in ov.get('source', ''):
        ov['source'] = ov.get('source', '') + note
    json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')


def main(argv):
    if '--icons' in argv:
        for n in [int(a) for a in argv if a.isdigit()] or sorted(set(ICON_ROLE) | set(ICON_CLIPS_ROLE)):
            print(n, json.dumps(icon_role_keys(n), ensure_ascii=False))
            if '--write' in argv:
                write_icon_role_keys(n)
        return
    write = '--write' in argv
    levels = [int(a) for a in argv if a.isdigit()] or sorted(set(ALIAS) | set(BARS) | set(CLIPS_ROLE) | set(WAITS_ROLE)
                                                             | set(ITEM_CLIPS) | set(ROLE_START))
    # the profile's idle runs, for the printed comparison only
    mp = os.path.join(SCRATCH, 's2_idle_others.json')
    mob = json.load(open(mp)) if os.path.exists(mp) else {}
    for n in levels:
        d = S2[n]; acts = pc_actions(d)
        byname = {}
        for actor, obj, name, an, secs in acts:
            if actor not in (None, 'neighbor', 'woody') and secs != 'auto':
                byname['%s.%s' % (obj, name)] = (actor, secs)
        print('== %d %s: PC explicit waits: %s' % (n, d, ' | '.join('%s:%s %ss' % (v[0], k, v[1]) for k, v in byname.items())))
        per = {}
        code = {role: role_parts(n, role) for role in ROLE_LAPS.get(n, {})}
        for item, (role, pcs, walk) in ALIAS.get(n, {}).items():
            # the code's stay: the parts' ticks of her lap (each its first
            # visit's), else the data's `time`
            ticks = [code.get(role, {}).get(tuple(k.rsplit('.', 1)), [None])[0] for k in pcs]
            if all(t is not None for t in ticks):
                secs = sum(ticks) / 12.0 - walk
            else:
                secs = sum(byname[k][1] for k in pcs) - walk
            m = [(k, sum(v) / len(v)) for k, v in mob.get(str(n), {}).items() if k.startswith(role + ':' + item + '@')]
            print('   %-18s %-7s %5.1f s  <- PC %s%s   (mobile %s)' % (
                item, role, secs, ' + '.join(pcs), ' - walk %.1f' % walk if walk else '',
                ', '.join('%.1f' % x[1] for x in m) or '?'))
            per.setdefault(item, {})[role] = round(secs, 2)
        bars = {}
        for item, (step, chair) in BARS.get(n, {}).items():
            sit, sleep, getup = bar_secs(n, step, chair)
            print('   %-18s Mother  sit %.2f s, sleep %.2f s, get-up %.2f s  <- the step %#x\'s bar and %s\'s enter/leave' % (
                item, sit, sleep, getup, step, chair))
            bars[item] = (sit, sleep, getup)
        rclips = role_clips(n)
        for item, (role, cl) in sorted(rclips.items()):
            print('   %-18s %-7s clips %s' % (item, role, ', '.join('%s %.2f' % kv for kv in sorted(cl.items()))))
        iclips = item_clips(n)
        for item, cl in sorted(iclips.items()):
            print('   %-18s item    clips %s' % (item, ', '.join('%s %.2f' % kv for kv in sorted(cl.items()))))
        rwaits = WAITS_ROLE.get(n, {})
        for item, (role, wt) in sorted(rwaits.items()):
            print('   %-18s %-7s holds %s until %s %s %s%s' % (
                item, role, wt['clip'], wt['role'], 'began' if wt.get('at') == 'start' else 'used', wt['item'],
                (' and its %s.%s' % wt['then_action']) if 'then_action' in wt else ''))
        starts = {}
        for role, item in ROLE_START.get(n, {}).items():
            am, k = role_start(n, role, item)
            print('   %-18s %-7s starts the list (%s index %d), wraps to 0' % (item, role, am, k))
            starts[am] = k
        if write:
            p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
            ov = json.load(open(p))
            ov['patches'] = [e for e in ov.get('patches', []) if not (
                e.get('component') == 'ActionManager' and 'ActionStartIndex' in (e.get('set') or {}))]
            for am, k in sorted(starts.items()):
                ov['patches'].append({'object': am, 'component': 'ActionManager',
                                      'set': {'ActionStartIndex': k, 'LoopFromStartIndex': False}})
            ov['patches'] = _strip_key(ov.get('patches', []), 'PCUseSecondsRole')
            for k in ('PCSitSeconds', 'PCSleepSeconds', 'PCGetUpSeconds', 'PCClipSecondsRole', 'PCWaitForRole',
                      'PCItemClipSeconds'):
                ov['patches'] = _strip_key(ov['patches'], k)
            for item, cl in iclips.items():
                _set_key(ov['patches'], item, 'PCItemClipSeconds', cl)
            for item, (role, cl) in rclips.items():
                _set_key(ov['patches'], item, 'PCClipSecondsRole', {role: cl})
            for item, (role, wt) in rwaits.items():
                wt = dict(wt)
                if 'then_action' in wt:
                    # the seconds held after the release: the action's job
                    import lap_model_s2
                    o, a = wt.pop('then_action')
                    wt['then'] = round(lap_model_s2.Data(n).action_ticks(o, a, actor=role.lower()) / 12.0, 2)
                if 'visit' in wt:
                    # the awaited role's routine index of that visit of the
                    # item (the runtime's `index`: another visit's mark goes by)
                    wt['index'] = role_index(n, wt['role'], wt['item'], wt.pop('visit'))
                _set_key(ov['patches'], item, 'PCWaitForRole', {role: wt})
            for item, roles in per.items():
                _set_key(ov['patches'], item, 'PCUseSecondsRole', roles)
            for item, (sit, sleep, getup) in bars.items():
                _set_key(ov['patches'], item, 'PCSitSeconds', sit)
                _set_key(ov['patches'], item, 'PCSleepSeconds', sleep)
                _set_key(ov['patches'], item, 'PCGetUpSeconds', getup)
            note = " The other actors' stands (tools/pcref/pc_durations_others.py): the PC data's `time` ticks / 12 of the actions paired in ALIAS, as PCUseSecondsRole."
            if per and note not in ov['source']:
                ov['source'] += note
            elif not per:
                ov['source'] = ov['source'].replace(note, '')
            note2 = " The Mother's bar in her chair (tools/pcref/pc_durations_others.py BARS): PCSitSeconds the chair's enter, PCSleepSeconds the sleep step's bar ticks, PCGetUpSeconds the chair's leave, at 12 a second."
            if bars and 'BARS' not in ov['source']:
                ov['source'] += note2
            note3 = " Another actor's clips at the PC's ticks (tools/pcref/pc_durations_others.py CLIPS_ROLE): PCClipSecondsRole, the level data's actions and clips paired by hand."
            if rclips and 'CLIPS_ROLE' not in ov['source']:
                ov['source'] += note3
            note5 = " An item's own clips while another role uses it hidden (tools/pcref/pc_durations_others.py ITEM_CLIPS): PCItemClipSeconds, the level data's actions and clips paired by hand."
            if iclips and 'ITEM_CLIPS' not in ov['source']:
                ov['source'] += note5
            note4 = " Another actor's clip held (tools/pcref/pc_durations_others.py WAITS_ROLE): PCWaitForRole, until a role's use of an item has begun (at start) or ended."
            if rwaits and 'WAITS_ROLE' not in ov['source']:
                ov['source'] += note4
            note6 = " Another actor's first station (tools/pcref/pc_durations_others.py ROLE_START): her ActionManager starts at the item her script's first step stands for and wraps to 0."
            if starts and 'ROLE_START' not in ov['source']:
                ov['source'] += note6
            json.dump(ov, open(p, 'w'), indent=1, ensure_ascii=False); open(p, 'a').write('\n')
            print('   wrote', p)


if __name__ == '__main__':
    main(sys.argv[1:])
