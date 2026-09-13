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
Level214's lap is a neighbour-Mother handshake and keeps the mobile pace whole
(docs/PC_FIDELITY.md "Season 2 station durations")."""
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
}


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
    levels = [int(a) for a in argv if a.isdigit()] or sorted(ALIAS)
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
        if write:
            p = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
            ov = json.load(open(p))
            ov['patches'] = [e for e in ov.get('patches', []) if 'PCUseSecondsRole' not in (e.get('set') or {})]
            for item, roles in per.items():
                ov['patches'].append({'object': item, 'component': 'TrickItem', 'set': {'PCUseSecondsRole': roles}})
            note = " The other actors' stands (tools/pcref/pc_durations_others.py): the PC data's `time` ticks / 12 of the actions paired in ALIAS, as PCUseSecondsRole."
            if 'pc_durations_others' not in ov['source']:
                ov['source'] += note
            json.dump(ov, open(p, 'w'), indent=1, ensure_ascii=False); open(p, 'a').write('\n')
            print('   wrote', p)


if __name__ == '__main__':
    main(sys.argv[1:])
