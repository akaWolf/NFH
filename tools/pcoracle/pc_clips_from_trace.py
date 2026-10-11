#!/usr/bin/env python3
"""A Season 2 station's clip seconds from the oracle's trace: where the port's PCClipSeconds names the PC
actor's own animations (202's Swimming: WaitSea / EnterSea / SeeSub / LeaveSea are the neighbour's waitsea /
entersea / seesub / leavesea), each clip lasts from its animation's first tick to the next clip's — the
DoAction-to-animation and bar-end ticks the lap model's parts carry are then in the measure — and the last
to the walk's first move less the exit's PCDepartTicks. A clip the port waits on (PCWaitFor) keeps its
value; a station whose clips are object animations (the mat's `inv`) is left to the lap model.

    python3 tools/pcoracle/pc_clips_from_trace.py 202 ~/nfh-bench/wine/logs/oracle_cn_b1_park.jsonl [--write]

Per visit the clips' ticks are listed; the value written is the most frequent per clip (a station's visits
agree on the untricked lap)."""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref')); sys.path.insert(0, HERE)

WALKS = ('mg0', 'mg1', 'mg2', 'mg3', 'mr0', 'mr1', 'mr2', 'mr3')
STANDS = ('ms0', 'ms1', 'ms2', 'ms3')
ROLES = {'neighbor': 'Rottweiler', 'olga': 'Olga', 'mother': 'Mother'}

def norm(name):
    return name.lower().replace('_', '')

def stays(rows, role):
    """[(first stay tick, [(tick, anim)...], first move tick)] per stay of the actor between walks"""
    ticks = [(r['tick'], r['actors'][role]['anim'], r['actors'][role]['x'], r['actors'][role]['y'])
             for r in rows if r['ev'] == 'tick' and r['actors'].get(role)]
    out = []; i = 0
    while i < len(ticks):
        if ticks[i][1] in WALKS:
            i += 1; continue
        j = i; anims = []
        while j < len(ticks) and ticks[j][1] not in WALKS:
            if not anims or anims[-1][1] != ticks[j][1]: anims.append((ticks[j][0], ticks[j][1]))
            j += 1
        # the first move: the first walk tick whose position differs from the stay's end
        k = j
        while k < len(ticks) and ticks[k][1] in WALKS and (ticks[k][2], ticks[k][3]) == (ticks[j - 1][2], ticks[j - 1][3]): k += 1
        out.append((ticks[i][0], anims, ticks[k][0] if k < len(ticks) else None))
        i = j
    return out

def main(argv):
    n = int(argv[1]); rows = [json.loads(l) for l in open(os.path.expanduser(argv[2]))]
    write = '--write' in argv
    ov_path = os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)
    ov = json.load(open(ov_path))
    items = {}
    for e in ov['patches']:
        s = e.get('set') or {}
        if s.get('PCClipSeconds') and e.get('object'):
            items.setdefault(e['object'], {})['clips'] = s['PCClipSeconds']
        if s.get('PCWaitFor') and e.get('object'):
            items.setdefault(e['object'], {})['wait'] = s['PCWaitFor'].get('clip')
        if s.get('PCDepartTicks') and e.get('object'):
            items.setdefault(e['object'], {})['depart'] = s['PCDepartTicks']
    import pc_durations_s2
    changed = 0
    for pc_role, role in ROLES.items():
        for start, anims, move in stays(rows, pc_role):
            names = [a for t, a in anims if a not in STANDS]
            if not names: continue
            # the item whose PCClipSeconds names these animations
            for item, d in items.items():
                clips = d.get('clips')
                if not clips: continue
                byname = {norm(c): c for c in clips}
                if sum(1 for a in names if norm(a) in byname) < max(2, len(clips) - 1): continue
                depart = (d.get('depart') or {}).get(role, 0)
                measured = {}
                seq = [(t, a) for t, a in anims if norm(a) in byname]
                for i, (t, a) in enumerate(seq):
                    end = seq[i + 1][0] if i + 1 < len(seq) else ((move - depart) if move is not None else None)
                    if end is None: continue
                    measured[byname[norm(a)]] = end - t
                print('%-10s %-14s at tick %5d: %s  (overlay %s)' % (role, item, start, {c: '%d ticks %.2f s' % (v, v / 12.0) for c, v in measured.items()}, clips))
                items[item].setdefault('seen', []).append(measured)
    for item, d in items.items():
        seen = d.get('seen')
        if not seen or not d.get('clips'): continue
        new = dict(d['clips'])
        for c in d['clips']:
            vals = [m[c] for m in seen if c in m]
            if not vals or c == d.get('wait'): continue
            v = collections.Counter(vals).most_common(1)[0][0]
            new[c] = round(v / 12.0, 2)
        if new != d['clips']:
            print('%s: %s -> %s' % (item, d['clips'], new))
            if write:
                pc_durations_s2._set_key(ov['patches'], item, 'PCClipSeconds', new); changed += 1
    if write and changed:
        json.dump(ov, open(ov_path, 'w'), ensure_ascii=False, indent=1); open(ov_path, 'a').write('\n')
        print('written %d items to %s' % (changed, ov_path))

if __name__ == '__main__':
    main(sys.argv)
