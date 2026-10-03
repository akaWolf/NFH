#!/usr/bin/env python3
"""The PC's Season 1 tutorial texts into the Intro scenes' levels/pc overlays.

    python3 tools/pcref/pc_tutorial_s1.py            # print the pairing
    python3 tools/pcref/pc_tutorial_s1.py --write    # PCDescriptions into Intro10x.overlay.json

The remaster's three Intro scenes are the PC's tutorial levels step for step
(tutorial_1-3: game.exe's Level_Tutorial1::run at 0x45b600 shows tut_target1,
tut_door, tut_target2, tut_target3 and tut_exit through its cases; the
tutorial_2 and tutorial_3 classes around 0x45a5fd and 0x459581 theirs): each
LevelScript action's PC-build key (Description, TUT<n>MSG<m>_PC) is one of
the PC's director messages, reworded — "neighbor" for "neighbour", "Woody is
now using the marker pen on the picture" for "A progress bar above Woody's
head shows you the duration of an action". Under the profile the director
says the PC's own text (runtime/tutorial.py Tutorial.get_description): the
level's strings.xml message by its code name, the pairing below read off the
texts, one to one. The two "Ha, ha!" boxes the PC shows after the slips
(tut_laugh2, tut_laugh) have no action in the remaster's scripts."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from tools.pcref import canon  # noqa: E402

X1 = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
# intro scene -> (PC tutorial folder, {the action's Description key: the PC message's name})
PAIRS = {
    'Intro101': ('tutorial_1', {'TUT1MSG1_PC': 'tut_target1', 'TUT1MSG2_PC': 'tut_door',
                                'TUT1MSG3_PC': 'tut_target2', 'TUT1MSG4_PC': 'tut_target3',
                                'TUT1MSG5_PC': 'tut_exit'}),
    'Intro102': ('tutorial_2', {'TUT2MSG1_PC': 'tut_lookat_plant', 'TUT2MSG2_PC': 'tut_take_objects',
                                'TUT2MSG3_PC': 'tut_use_marker', 'TUT2MSG4_PC': 'tut_hallway1',
                                'TUT2MSG5_PC': 'tut_watch2', 'TUT2MSG6_PC': 'tut_laugh1',
                                'TUT2MSG7_PC': 'tut_hallway2', 'TUT2MSG8_PC': 'tut_watch3'}),
    'Intro103': ('tutorial_3', {'TUT3MSG1_PC': 'introduction', 'TUT3MSG2_PC': 'tut_take_marbles',
                                'TUT3MSG3_PC': 'tut_put_marbles', 'TUT3MSG4_PC': 'tut_hiding',
                                'TUT3MSG5_PC': 'tut_hiding2', 'TUT3MSG6_PC': 'tut_watch'}),
}


def pc_strings(folder):
    """{name: text} of the tutorial's strings.xml, the XML entities undone"""
    t = canon.read(os.path.join(X1, folder, 'strings.xml'))
    out = {}
    for n, v in re.findall(r'<string name="([^"]+)"[^>]*text="([^"]*)"', t):
        v = v.replace('&#xA;', '\n').replace('&quot;', '"').replace('&apos;', "'") \
            .replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        out[n] = v
    return out


def descriptions(scene):
    """{Description key: the PC text} of an intro scene; every key its
    LevelScript uses must be paired"""
    folder, pairs = PAIRS[scene]
    strs = pc_strings(folder)
    d = json.load(open(os.path.join(ROOT, 'levels', 's1', scene + '.json')))
    ls = next(o for o in d['objects'].values() if o.get('type') == 'LevelScript')['data']
    used = set()
    for a in ls.get('Actions') or []:
        for k in ('Description', 'AlternateDescription'):
            if a.get(k):
                used.add(a[k])
    missing = used - set(pairs)
    assert not missing, (scene, missing)
    return {k: strs[v] for k, v in pairs.items() if k in used}


def main(argv):
    write = '--write' in argv
    for scene in sorted(PAIRS):
        desc = descriptions(scene)
        print('==', scene, PAIRS[scene][0])
        for k, v in desc.items():
            print('   %-12s %s: %s' % (k, PAIRS[scene][1][k], v[:90].replace('\n', ' ')))
        if write:
            p = os.path.join(ROOT, 'levels', 'pc', scene + '.overlay.json')
            ov = json.load(open(p)) if os.path.exists(p) else {'source': '', 'patches': []}
            ov['patches'] = [e for e in ov.get('patches', []) if 'PCDescriptions' not in (e.get('set') or {})]
            ov['patches'].append({'object': 'LevelScript', 'component': 'LevelScript',
                                  'set': {'PCDescriptions': desc}})
            note = ("The director's messages (tools/pcref/pc_tutorial_s1.py): the PC's %s "
                    "strings.xml texts by their code names, paired one to one with the "
                    "LevelScript actions' PC-build keys (PCDescriptions)." % PAIRS[scene][0])
            if note not in ov.get('source', ''):
                ov['source'] = (ov.get('source', '') + ' ' + note).strip()
            json.dump(ov, open(p, 'w'), indent=1, ensure_ascii=False)
            open(p, 'a').write('\n')
            print('   wrote', p)


if __name__ == '__main__':
    main(sys.argv[1:])
