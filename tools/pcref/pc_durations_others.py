"""The other actors' stands under the PC profile, from the PC data.

    python3 tools/pcref/pc_durations_others.py            # print the pairings
    python3 tools/pcref/pc_durations_others.py --write    # rewrite the PCUseSecondsRole patches

A `<action actor="mother" … time="N">` of the PC level's objects.xml lasts N
ticks (12 per second); `time="auto"` lasts its clip (the enter/leave clips of a
stand, a second or two) and a loop's length is not in the data, so only the
explicit waits are carried. The mobile stands come from the profile's idle runs
(runs/idlepc2s2, the other roles' `using` stretches — NFH_SCRATCH/
s2_idle_others.json) and are paired by hand per level in ALIAS: a mobile stand
that covers two PC stations in one room takes their sum less the walk between.

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
    212: {'MumWaitZone3': ('Mother', ['midleft/red_bull.use'], 0.0),
          'MumWaitZone4': ('Mother', ['midright/statue_hideout.use'], 0.0)},
    213: {'MotherWaitZone2': ('Mother', ['bottomright/water.use'], 0.0),
          # the port's Zone05 holds the statue and the flowers: two PC stations
          'MotherWaitZone5': ('Mother', ['midright/statue_hideout.use', 'topright/flowers.use'], 2.0)},
    # her reling step after the sleep (0x10039f34: the GoTo and the reling's use)
    214: {'MotherWait': ('Mother', ['bottomright/reling.use'], 0.0)},
}
# level -> mobile item -> (the Mother script's sleep step, the chair) — the step
# whose fcn.1000e7f2 bar holds her in the chair (lap_model_s2.run_step reads the
# pushed ticks)
BARS = {214: {'DeckChairMother': (0x1003a0b8, 'topright_deckchair')}}
# level -> mobile item -> (role, {mobile clip: the PC's part}) — another actor's
# clips at the PC's ticks (PCClipSecondsRole): (object, action) of the level
# data, ('anim', object, clip) a clip's frames (a loop's pace). 202's Olga on
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
CLIPS_ROLE = {210: {'DeckChairMother': ('Mother', {'MotherSitPillow': ('pool_deckchair', 'enter'),
                                                   'MotherSleepPillow': ('ticks', 0),
                                                   'MotherSleepSingle': ('bar', 0x10018c0b, 3),
                                                   'MotherLookLoop': ('bar', 0x100187d8),
                                                   'MotherGetUpPillow': ('pool_deckchair', 'leave')}),
                    'CallRTMother': ('Mother', {'MotherCall': ('mother', 'callneighbor'),
                                                'MotherOrder': ('mother', 'order')})},
              202: {'OlgaMat': ('Olga', {'BeachLayDown': ('beachleft_mat_olga_guarded', 'enter'),
                                         'TowelSleep': ('anim', 'beachleft/mat_olga_guarded', 'sun'),
                                         'TowelLaydown': ('beachleft_mat_olga_guarded', 'wakeup'),
                                         'BeachGetUp': ('beachleft_mat_olga_guarded', 'leave')}),
                    'Submarine': ('Olga', {'OlgaPutSub': ('beachleft_sub', 'take'),
                                           'OlgaPutSubTricked': ('beachleft_shark', 'take')})}}


# level -> mobile item -> {the item's clip: the PC's part} — an item's own
# clips while another role uses it hidden (PCItemClipSeconds): 205's mat,
# Olga's lie-down (the mat's `enter`), the sun loop, the `wakeup` and the
# `leave` her `pingpong` step plays (0x10025b2a) — the mobile's UseNormal-
# Sequence, frame for frame the PC's at 8 a second
ITEM_CLIPS = {205: {'OlgaMatBeach': ('Olga', {'N2TrickItemExtra1': ('beachright_mat_guarded', 'enter'),
                                              'N2TrickItemUseNormal': ('anim', 'beachright/mat', 'sun'),
                                              'N2TrickItemExtra3': ('beachright_mat_guarded', 'wakeup'),
                                              'N2TrickItemExtra2': ('beachright_mat_guarded', 'leave')})}}
# level -> mobile item -> (role, wait): another actor's clip held until a role
# has used an item or begun to (PCWaitForRole, the runtime's PCWaitFor for that
# role): 210's Mother waits at her chair after the call until he stands there
# (her order step's poll) — his use of the call begun
WAITS_ROLE = {210: {'CallRTMother': ('Mother', {'clip': 'MotherStandDownInfinite', 'role': 'Rottweiler',
                                                'item': 'CallRTMother', 'at': 'start', 'then': 0.0})}}


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
            elif src[0] == 'bar':
                ev, _nxt = lap_model_s2.run_step(lap_model_s2.Level(n), src[1], {})
                t = next((e[2] for e in ev if e[0] == 'WAITEVENT' and isinstance(e[2], int)), None)
                if t is not None and len(src) > 2:
                    # the bar less so many ticks, over so many mobile clips
                    t = (t - (src[3] if len(src) > 3 else 0)) / float(src[2])
            else:
                t = d.action_ticks(src[0], src[1], actor=role.lower())
            if t is not None:
                cl[clip] = round(t / 12.0, 2)
        out[item] = (role, cl)
    return out


def bar_secs(n, step, chair):
    """(sit, sleep, get-up) seconds: the chair's `enter`, the bar's ticks and
    the chair's `leave`, at 12 ticks a second"""
    sys.path.insert(0, HERE)
    import lap_model_s2
    ev, _nxt = lap_model_s2.run_step(lap_model_s2.Level(n), step, {})
    ticks = [e[2] for e in ev if e[0] == 'WAITEVENT' and isinstance(e[2], int)]
    d = lap_model_s2.Data(n)
    sit = d.action_ticks(chair, 'enter'); leave = d.action_ticks(chair, 'leave')
    return round(sit / 12.0, 2), round(ticks[0] / 12.0, 2), round(leave / 12.0, 2)


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


def main(argv):
    write = '--write' in argv
    levels = [int(a) for a in argv if a.isdigit()] or sorted(set(ALIAS) | set(BARS) | set(CLIPS_ROLE) | set(WAITS_ROLE)
                                                             | set(ITEM_CLIPS))
    mob = json.load(open(os.path.join(SCRATCH, 's2_idle_others.json')))
    for n in levels:
        d = S2[n]; acts = pc_actions(d)
        byname = {}
        for actor, obj, name, an, secs in acts:
            if actor not in (None, 'neighbor', 'woody') and secs != 'auto':
                byname['%s.%s' % (obj, name)] = (actor, secs)
        print('== %d %s: PC explicit waits: %s' % (n, d, ' | '.join('%s:%s %ss' % (v[0], k, v[1]) for k, v in byname.items())))
        per = {}
        for item, (role, pcs, walk) in ALIAS.get(n, {}).items():
            secs = sum(byname[k][1] for k in pcs) - walk
            m = [(k, sum(v) / len(v)) for k, v in mob.get(str(n), {}).items() if k.startswith(role + ':' + item + '@')]
            print('   %-18s %-7s %5.1f s  <- PC %s%s   (mobile %s)' % (
                item, role, secs, ' + '.join(pcs), ' - walk %.1f' % walk if walk else '',
                ', '.join('%.1f' % x[1] for x in m) or '?'))
            per.setdefault(item, {})[role] = round(secs, 1)
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
            print('   %-18s %-7s holds %s until %s %s %s' % (
                item, role, wt['clip'], wt['role'], 'began' if wt.get('at') == 'start' else 'used', wt['item']))
        if write:
            p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
            ov = json.load(open(p))
            ov['patches'] = _strip_key(ov.get('patches', []), 'PCUseSecondsRole')
            for k in ('PCSitSeconds', 'PCSleepSeconds', 'PCGetUpSeconds', 'PCClipSecondsRole', 'PCWaitForRole',
                      'PCItemClipSeconds'):
                ov['patches'] = _strip_key(ov['patches'], k)
            for item, cl in iclips.items():
                _set_key(ov['patches'], item, 'PCItemClipSeconds', cl)
            for item, (role, cl) in rclips.items():
                _set_key(ov['patches'], item, 'PCClipSecondsRole', {role: cl})
            for item, (role, wt) in rwaits.items():
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
            json.dump(ov, open(p, 'w'), indent=1, ensure_ascii=False); open(p, 'a').write('\n')
            print('   wrote', p)


if __name__ == '__main__':
    main(sys.argv[1:])
