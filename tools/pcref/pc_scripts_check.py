"""Check a level's extracted script (tools/pcref/pc_scripts.py) against an oracle trace of the original: every
ICON / ACTION / SWITCH event the NFH1 oracle logged (its `ret` is the instruction after the step's call: the
call's own address is ret - 5) must be a step of the script, and the steps' cases must follow the script's
`next` links — the proof that the trees hold the whole routine the game ran.

    python3 tools/pcref/pc_scripts_check.py <level> <trace.jsonl> [--script levels/pc/scripts/LevelN.json]
"""
import json, os, sys


def load(level, path):
    sc = json.load(open(path))
    steps = {}; case_of = {}
    for cls in sc['classes']:
        for a, t in cls['steps'].items():
            steps[int(a, 16)] = t
        for c in cls['cases']:
            def walk(node):
                for s in node['steps']:
                    case_of.setdefault(int(s['a']) if not isinstance(s['a'], str) else int(s['a'], 16), c['index'][0])
                for v in ('true', 'false'):
                    if v in node: walk(node[v])
            walk(c['tree'])
    return sc, steps, case_of


def main(argv):
    n = int(argv[0]); trace = argv[1]
    path = argv[argv.index('--script') + 1] if '--script' in argv else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'levels', 'pc', 'scripts', 'Level%d.json' % n)
    sc, steps, case_of = load(n, path)
    seen = []; missing = {}
    # the rets that are no script step by design: the GUI's handlers of Woody's own clicks, and the steps'
    # sub-calls (the fire's shout and its icon, GOTOENTER's enter/leave, the walk's arrival action, the pets)
    KNOWN = {'0x44b098': 'woody combine', '0x44b1e5': 'woody use', '0x475228': 'woody open', '0x47f00c': 'woody take',
             '0x47f07e': 'woody surprise', '0x47bf82': "the fire's shout", '0x47964d': "the fire's icon",
             '0x4739a5': 'GOTOENTER enter', '0x473c8b': 'GOTOENTER leave', '0x479ccf': "the walk's arrival action",
             '0x45c1dc': 'the pet', '0x47a718': 'the noise case', '0x47a81b': 'the noise case', '0x47a88c': 'the noise case',
             '0x4790ed': 'woody idle', '0x478a99': 'woody triumph', '0x47afdf': 'the repair helper', '0x47b064': 'the repair helper',
             '0x47bb8a': 'the slip', '0x47db7b': 'the slip', '0x47bbaf': "the fire's own animation (FIRE5's +0x18)",
             '0x47d8be': "a room trigger's behaviour", '0x47d686': "a room trigger's behaviour", '0x47d8e6': "a room trigger's behaviour",
             '0x47d65e': "a room trigger's behaviour", '0x47d271': "a room trigger's behaviour", '0x479c13': 'the DoAction wrapper (behaviours)'}
    known = {}
    for l in open(trace):
        r = json.loads(l); ev = r.get('ev')
        if ev not in ('icon', 'action', 'switch'): continue
        call = int(r['ret'], 16) - 5
        if ev == 'action' and r['args'][1] == 'woody': continue           # Woody's own (the GUI's DoActions)
        if call in steps:
            seen.append((r['tick'] / 12.0, ev, call, case_of.get(call)))
        elif r['ret'] in KNOWN:
            known[KNOWN[r['ret']]] = known.get(KNOWN[r['ret']], 0) + 1
        else:
            key = (ev, r['ret'], r['args'][1] if ev != 'icon' else r['args'][0], r['args'][2] if ev == 'action' else '')
            missing[key] = missing.get(key, 0) + 1
    in_script = len(seen); out = sum(missing.values())
    print('level %d: %d events on script steps, %d by the steps\' sub-calls and the GUI (%s), %d unexplained (%d kinds)' % (
        n, in_script, sum(known.values()), ', '.join('%s x%d' % kv for kv in sorted(known.items())), out, len(missing)))
    for k, v in sorted(missing.items(), key=lambda kv: -kv[1])[:20]:
        print('   off  %-7s ret %s %s %s x%d' % k[:1] + (k[1], k[2], k[3], v) if False else '   off  %-7s ret %-10s %-28s %-16s x%d' % (k[0], k[1], k[2], k[3], v))
    # the case sequence the events imply
    cases = []
    for t, ev, call, c in seen:
        if c is not None and (not cases or cases[-1][1] != c): cases.append((round(t, 1), c))
    print('   cases in order: ' + ' '.join('%s@%s' % (c, t) for t, c in cases[:60]))


if __name__ == '__main__':
    main(sys.argv[1:])
