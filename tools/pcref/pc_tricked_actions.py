"""PC Season 1: the TRICKED objects' neighbour actions in seconds (objects.xml
`time` ticks, or the actor/object clip's frames at 12 fps for `auto`) next
to the normal object's, paired by the level scripts' `If <tricked> of
<normal>` steps (docs/PC_ROUTINES.md). The profile's PCUseSeconds are the
normal stations' stays; a tricked use plays the tricked object's own action
on the PC (106's make_foampudding 3.17 s against make_pudding 8.00), which
the port stretches to the normal stay — the numbers behind the open
divergence in docs/PC_FIDELITY.md (2026-09-22).

    python3 tools/pcref/pc_tricked_actions.py
"""
import re, os, sys, glob
X = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
doc = open('docs/PC_ROUTINES.md').read()
def anims(level):
    fr = {}
    for f in (os.path.join(X, 'generic/anims.xml'), os.path.join(X, level, 'anims.xml')):
        t = open(f, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'<animation name="([^"]+)"[^>]*>(.*?)</animation>', t, re.S):
            fr[m.group(1)] = len(re.findall(r'<frame\b', m.group(2)))
    return fr
def actions(level):
    t = open(os.path.join(X, level, 'objects.xml'), encoding='utf-8', errors='replace').read()
    fr = anims(level); out = {}
    for m in re.finditer(r'<object\b[^>]*\bname="([^"]+)"[^>]*>(.*?)</object>', t, re.S):
        acts = []
        for a in re.finditer(r'<action\b([^>]*)/?>', m.group(2)):
            at = dict(re.findall(r'(\w+)="([^"]*)"', a.group(1)))
            if at.get('actor') != 'neighbor': continue
            tm = at.get('time', 'auto')
            if tm == 'auto':
                n = fr.get(at.get('actoranim', ''), 0) or fr.get(at.get('objanim', ''), 0)
                secs = n / 12.0
            else:
                secs = int(tm) / 12.0
            acts.append('%s=%.2f' % (at.get('name'), secs))
        out[m.group(1)] = acts
    return out
for sec in re.finditer(r'## (level_\w+) \(Level(\d+)\)\n(.*?)(?=\n## |\Z)', doc, re.S):
    level, num, body = sec.group(1), sec.group(2), sec.group(3)
    if int(num) >= 200: continue
    pairs = re.findall(r'If (\S+) of (\S+)', body)
    acts = actions(level)
    print('== %s Level%s' % (level, num))
    seen = set()
    for tricked, normal in pairs:
        if (tricked, normal) in seen: continue
        seen.add((tricked, normal))
        print('  %-22s %-40s | %-18s %s' % (tricked, ' '.join(acts.get(tricked, ['-'])), normal, ' '.join(acts.get(normal, ['-']))))
