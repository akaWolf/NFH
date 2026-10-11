#!/usr/bin/env python3
"""The ticks an actor stands between a station's last animation and its next walk's first move, from the
oracle's trace — the step dispatch the port's departure must carry (the GoTo's first movement comes two
ticks after the GoTo call; a hand-over between steps may cost one more).

    python3 tools/pcoracle/exit_ticks.py ~/nfh-bench/wine/logs/oracle_cn_b1_idle.jsonl [neighbor|olga|...]

Per walk start: the station animation that ended, the tick it ended (the stand animation appearing), the
GoTo call's tick on the actor (the `goto` hook's first record for the walk's target), the first move's tick
(x or y changing), and the stands: end -> goto, goto -> move, end -> move."""
import json, os, sys

STANDS = ('ms0', 'ms1', 'ms2', 'ms3')
WALKS = ('mg0', 'mg1', 'mg2', 'mg3')

def main(argv):
    role = argv[2] if len(argv) > 2 else 'neighbor'
    rows = [json.loads(l) for l in open(os.path.expanduser(argv[1]))]
    ticks = []          # (tick, anim, x, y)
    gotos = []          # (tick, target)
    actor_ptr = None
    for r in rows:
        if r['ev'] == 'tick':
            a = r['actors'].get(role)
            if a: ticks.append((r['tick'], a['anim'], a['x'], a['y']))
        elif r['ev'] == 'goto' and isinstance(r['args'][2], str):
            gotos.append((r['tick'], r['args'][1], r['args'][2]))
    # the actor's GoTo records: the `goto` hook's args[1] is the actor object; the pointer that is this
    # actor's is the one whose first records fall within three ticks before the actor's first moves most often
    firsts = []
    last = None
    for t, ptr, target in gotos:
        if (ptr, target) != last:
            firsts.append((t, ptr, target)); last = (ptr, target)
    moves = set()
    for i in range(1, len(ticks)):
        if ticks[i][1] in WALKS and (ticks[i][2], ticks[i][3]) != (ticks[i - 1][2], ticks[i - 1][3]) and ticks[i - 1][1] not in WALKS:
            moves.add(ticks[i][0])
    votes = {}
    for t, ptr, target in firsts:
        if any(t <= m <= t + 3 for m in moves): votes[ptr] = votes.get(ptr, 0) + 1
    mine = max(votes, key=votes.get) if votes else None
    firsts = [f for f in firsts if f[1] == mine]
    print('# %s = actor %s (%s)' % (role, mine, votes))
    print('%-6s %-14s %6s %6s %6s %5s %5s %5s  %s' % ('role', 'after', 'end', 'goto', 'move', 'e->g', 'g->m', 'e->m', 'target'))
    i = 0
    while i < len(ticks):
        t, anim, x, y = ticks[i]
        if anim in WALKS:
            # the first move: the first tick of the walk whose x/y differ from the previous tick's
            j = i
            while j < len(ticks) and ticks[j][1] in WALKS and (ticks[j][2], ticks[j][3]) == (x, y): j += 1
            move = ticks[j][0] if j < len(ticks) else None
            # the station animation before the stand
            k = i - 1
            while k >= 0 and ticks[k][1] in STANDS: k -= 1
            after = ticks[k][1] if k >= 0 else '-'
            end = ticks[k + 1][0] if k + 1 < len(ticks) else t
            g = [gt for gt in firsts if end - 2 <= gt[0] <= t + 1]
            gt = g[-1][0] if g else None; target = g[-1][2] if g else '?'
            if after not in WALKS:
                print('%-6s %-14s %6d %6s %6s %5s %5s %5s  %s' % (role, after, end, gt if gt is not None else '-', move if move is not None else '-',
                      (gt - end) if gt is not None else '-', (move - gt) if (gt is not None and move is not None) else '-',
                      (move - end) if move is not None else '-', target))
            while i < len(ticks) and ticks[i][1] in WALKS: i += 1
            continue
        i += 1

if __name__ == '__main__':
    main(sys.argv)
