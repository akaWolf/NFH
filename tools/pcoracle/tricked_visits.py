#!/usr/bin/env python3
"""The tricked visits of a Season 2 run on the original, measured, against the overlay's model of them: for
each trick record paid (the trace's `credit` events, the PC's fcn.100522e6) the neighbour's visit that paid it
— the station (his last GoTo target before it), the actions posted on it, the SHOUT level, his animations
with their lengths from his arrival to his first step away, the credit's offset from the arrival — next to
the item's PCUseSecondsTricked / PCCreditAt / PCShout / PCFixSeconds / PCShoutTail of levels/pc. A line
per paid trick; `--all` lists every visit of a station with a tricked flow, paid or not.

    python3 tools/pcoracle/tricked_visits.py 203 ~/nfh-bench/wine/logs/oracle_cn_c2_nocatch.jsonl"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

GAITS = ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3')
STANDS = ('ms0', 'ms1', 'ms2', 'ms3')
KEYS = ('PCUseSeconds', 'PCUseSecondsTricked', 'PCCreditAt', 'PCShout', 'PCShoutTail', 'PCFixSeconds', 'PCLaugh', 'PCPairNext', 'PCPair')


def runs(anims):
    """[(anim, start tick, ticks)] from a tick -> anim series"""
    out = []
    for t, a in anims:
        if out and out[-1][0] == a: out[-1][2] += 1
        else: out.append([a, t, 1])
    return out


def main(argv):
    n = int(argv[1]); rows = [json.loads(l) for l in open(os.path.expanduser(argv[2]))]
    import pcmap
    m = pcmap.PCMap(n)
    ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
    keys = {}
    for e in ov['patches']:
        st = e.get('set') or {}
        if e.get('object') and any(k in st for k in KEYS):
            keys.setdefault(e['object'], {}).update({k: v for k, v in st.items() if k in KEYS})
    fam_item = {}
    for it, obj in list(m.stations.items()) + list(m.objs.items()):
        fam_item.setdefault(m.family(obj), it)
    actors = {r['name']: r['ptr'] for r in rows if r['ev'] == 'actor'}
    nb = actors.get('neighbor')
    ticks = [(r['tick'], r['actors']['neighbor']['anim']) for r in rows if r['ev'] == 'tick' and r['actors'].get('neighbor')]
    gotos = [(r['tick'], r['args'][2]) for r in rows if r['ev'] == 'goto' and r['args'][1] == nb and isinstance(r['args'][2], str)]
    credits = [r['tick'] for r in rows if r['ev'] == 'credit']
    shouts = [(r['tick'], r['args'][3]) for r in rows if r['ev'] == 'shout']
    actions = [(r['tick'], r['args'][1], r['args'][2]) for r in rows if r['ev'] == 'action' and isinstance(r['args'][1], str)]
    print('== %d: %d credits, %d shouts' % (n, len(credits), len(shouts)))
    seen = set(); changed = []
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref'))
    for c in credits:
        # the visit: the stand the credit falls in — from the tick after his last step before it to his
        # first step after it (the tantrum and the repair are stands too; a station is left on foot)
        before = [t for t, a in ticks if t < c and a in GAITS]
        start = (before[-1] + 1) if before else ticks[0][0]
        end = next((t for t, a in ticks if t > c and a in GAITS), ticks[-1][0])
        g = [x for x in gotos if x[0] <= start]
        station = g[-1][1] if g else next((o for t, o, a in actions if start <= t <= end), '?')
        if (start, station) in seen:
            print('  %7.2f %-28s a second credit %+6.2f s in (the pair / the linked record)' % (start / 12.0, station, (c - start) / 12.0)); continue
        seen.add((start, station))
        anims = runs([(t, a) for t, a in ticks if start <= t < end])
        acts = [(t, a) for t, o, a in actions if start - 2 <= t <= end and m.family(o) == m.family(station)]
        sh = [lv for t, lv in shouts if start <= t <= end]
        item = fam_item.get(m.family(station))
        model = keys.get(item, {}) if item else {}
        print('  %7.2f %-28s item %-16s visit %6.2f s, the credit %+6.2f s in, SHOUT %s' % (
            start / 12.0, station, item, (end - start) / 12.0, (c - start) / 12.0, sh or '-'))
        print('           actions %s' % [a for t, a in acts][:8])
        print('           anims   %s' % ', '.join('%s %.2f' % (a, k / 12.0) for a, t, k in anims if a not in STANDS or k >= 6))
        print('           overlay %s' % {k: v for k, v in model.items() if k != 'PCPair'})
        # the measure in the model's terms: the tricked stand to the SHOUT's clip (lookaround, inv, fear
        # included), the SHOUT's level, the repair clip after it, the stand after that before the step
        react = next((i for i, (a, t, k) in enumerate(anims) if a.startswith(('shout2', 'freakout'))), None)
        if item and react is not None and 'PCUseSecondsTricked' in model and not any(k in model for k in ('PCPair', 'PCPairNext', 'PCUseSecondsLinked', 'PCUseSecondsCompound')):
            # (a `fear` in the stand and what follows it is the port's own WaitInFear clip after the tricked
            # stand — 204's kart, 207's shell: the stand measured ends where the fear begins)
            fear = next((i for i, (a, t, k) in enumerate(anims[:react]) if a.startswith('fear')), None)
            stand = (anims[fear if fear is not None else react][1] - start) / 12.0
            fix = sum(k for a, t, k in anims[react + 1:] if a.startswith(('uselow', 'usemid', 'usehigh'))) / 12.0
            tail = sum(k for a, t, k in anims[react + 1:] if a in STANDS) / 12.0
            want = {'PCUseSecondsTricked': round(stand, 2), 'PCCreditAt': round((c - start) / 12.0, 2), 'PCShout': int(sh[0]) if sh else model.get('PCShout'),
                    'PCFixSeconds': round(fix, 2), 'PCShoutTail': round(tail, 2)}
            diff = {k: (model.get(k), v) for k, v in want.items() if v is not None and abs(float(model.get(k) or 0) - v) > 0.26}   # (an absent key is 0: three ticks and more count)
            # (a tail under a second is the departure's few ticks, PCDepartTicks' ground; a repair the model
            # holds at the station while the PC walks off to repair elsewhere — 203's stage and its
            # generator, 4.75 s — keeps its stand: the time is the same, the place is not)
            diff = {k: v for k, v in diff.items() if not (k == 'PCShoutTail' and v[1] < 1.0) and not (k == 'PCFixSeconds' and v[1] == 0 and (v[0] or 0) > 3)}
            if diff:
                print('           measured %s' % diff)
                if '--write' in argv:
                    import pc_durations_s2
                    for k, (old_v, v) in diff.items():
                        pc_durations_s2._set_key(ov['patches'], item, k, v)
                    changed.append(item)
    if '--write' in argv and changed:
        ovp = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
        json.dump(ov, open(ovp, 'w'), ensure_ascii=False, indent=1); open(ovp, 'a').write('\n')
        print('  written: %s' % changed)


if __name__ == '__main__':
    main(sys.argv)
