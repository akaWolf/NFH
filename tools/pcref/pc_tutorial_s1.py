#!/usr/bin/env python3
"""The PC's Season 1 tutorials into the Intro scenes' levels/pc overlays.

    python3 tools/pcref/pc_tutorial_s1.py            # print the data
    python3 tools/pcref/pc_tutorial_s1.py --write    # PCTutorial and the items' PC data into Intro10x.overlay.json

The remaster's three Intro scenes are the PC's tutorial levels (canon.TUTORIALS):
game.exe runs each as a level class of its own — Level_Tutorial1 (vtable
0x4e2ec8: its run 0x45b600, its trigger handler 0x45b4a0), and for tutorial_2
and tutorial_3 a director on the invisible HAL (0x45a550 / 0x45a3d0, 0x459520
/ 0x459370) and a script on the neighbour (0x45acd0 / 0x45ae00, 0x459b10 /
0x459eb0). Under the profile the runtime runs those scripts in place of the
mobile's LevelScript and camera scripts (runtime/tutorial.py TutorialPC101-103);
this tool gives them the level's data:

  PCTutorial on the LevelScript
    folder      the PC tutorial
    texts       the director's messages: strings.xml's texts by their code names
                (fcn.0047b150 shows the text of the name)
    lead        the director's opening count (state 0 stores 12, state 1 counts it
                down a tick at a time)
    start       level.xml's placements [x, y, room]: Woody, the neighbour
    doors       a PC door -> [the mobile door, its zone]: the director opens a
                door by hiding its closed dummy and showing it (fcn.00438c80,
                fcn.0043ab40), and tutorial_3 closes lir/kit the other way
    markers     a PC object -> the mobile item the marker arrow stands over
                (fcn.00438760) and the closed container shown (anc/ark_dummy ->
                anc/ark, the mobile's locked chest)
    signs       tutorial_1's signs: [x, y, room] of their `woody` hotspot (the
                object's level.xml position + objects.xml's offset) — the
                nearobj triggers of trigger.xml (the same room, |dx| < 15 px,
                fcn.00471bc0)
    at          tutorial_2's flower: its `woody` hotspot, where isActorAtObject
                (fcn.0047aa90: the same room, the actor's point the hotspot)
                finds him
    points      the neighbour's GoTo targets: lir_sign1 / kit_sign2, the signs'
                `neighbor` hotspots
    wait        tutorial_2's count at sign 1 (state 2 stores 0x60)
    tricks      tutorial_1's closing trick (state 8: `trick`'s quota, 100)

  the items (the PC data the Season 1 profile reads, runtime/scene.py)
    Rottweiler  PCAngryTime: level.xml's angrytime
    MumPicture  tutorial_2's `mum_smeared` handler (0x45ae73): StopMsg, the
                GoToObjX (fcn.0047a4a0), doubletake1 or doubletake3 by his facing,
                the tut_laugh1 message step (fcn.00459db0 under fcn.0047c640), the
                OBJ2 fire (fcn.0047c290: index 0, flags 0) and the repair
                (fcn.0047ae70: lir/mum_smeared's `clean`, the switch back): the
                look walk-by of the levels (tools/pcref/pc_reactions.py `wb`) with
                the message step's tick before the fire (PCFireWait)
    PCWalkPoint the objects Woody's actions take place at (their `woody`
                hotspots, as tools/pcref/pc_walks_s1.py's woody_targets): the
                flower, the chest, the picture, the wardrobe
    Dog         tutorial_3's alarm: the neighbour's state 3 builds the pets'
                alarm list (fcn.0047a690, as the levels' cases do: the
                Alerter's PCSurpriseSeconds and PCAlarmShoutSeconds, tools/
                pcref/pc_durations.py ALERTERS)
    Ground      the `marbles` handlers (tutorial_2 0x45b14a, tutorial_3 0x459f63):
                FIRE4 (fcn.0047c3b0: `marbles`, index 2 — the step keeps
                `index != 0`, fcn.0047bc00 0x47bc60-0x47bc73: shout2 —, flags 0)
                pushed alone with the run-now flag 0 in the trigger pass — it fires
                in that tick's actors' pass (PCReactLead 0) — its ready step a list
                of [StopMsg, (tutorial_3: the tut_laugh message step), slip1 or
                slip3, (tutorial_3: the closing message step)]: the fire's two
                ticks, the ready list's first update and the instants carried by
                the fall's paced span (PCFireLead, PCSlipSeconds); no removal of
                the floor object
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import canon       # noqa: E402
import lap_model   # noqa: E402

X1 = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x')
FPS = 12.0
# the director's opening count: state 0 stores it (Level_Tutorial1 0x45b63c,
# tutorial_2 0x45a589, tutorial_3 0x459559)
LEAD = 12
# tutorial_2's count at sign 1 (the neighbour's state 2, 0x45ad58)
WAIT = 0x60
# the markers and the containers: the PC objects the directors name, the mobile
# items at them
MARKERS = {'Intro102': {'anc/flower': 'PlantStink', 'anc/ark': 'Drawer', 'lir/mum': 'MumPicture'},
           'Intro103': {'anc/ark': 'Drawer'}}
# Woody's objects: the mobile item -> (its component, the PC object)
WOODY = {'Intro102': {'PlantStink': ('TrickItem', 'anc/flower'), 'Drawer': ('SearchItem', 'anc/ark'),
                      'MumPicture': ('TrickItem', 'lir/mum')},
         'Intro103': {'Drawer': ('SearchItem', 'anc/ark'), 'Wardrobe': ('HideItem', 'anc/wardrobe')}}
# the PC's messages, the tutorials' own strings.xml
MESSAGES = {'Intro101': ('tut_target1', 'tut_door', 'tut_target2', 'tut_target3', 'tut_exit'),
            'Intro102': ('tut_lookat_plant', 'tut_take_objects', 'tut_use_marker', 'tut_hallway1',
                         'tut_watch2', 'tut_laugh1', 'tut_hallway2', 'tut_watch3'),
            'Intro103': ('introduction', 'tut_take_marbles', 'tut_put_marbles', 'tut_hiding',
                         'tut_hiding2', 'tut_watch', 'tut_laugh')}
# the extra instants of the handlers' lists, in ticks
LAUGH1_STEP = 1          # tutorial_2's tut_laugh1 message step before the fire
# the fire step's own two ticks (its fire, its list's first update), carried by
# the fall's paced span as the levels' slips carry them (PCFireLead;
# runtime/pcprofile.py S1_FIRE_LEAD_TICKS, tools/pcref/pc_reactions.py FIRE_LEAD)
FIRE_LEAD = 2
# after the fire (FIRE4's first update) to the fall: its list's first update, the
# ready list's first update, its StopMsg, tutorial_3's tut_laugh message step
SLIP_LEAD = {'Intro102': 2, 'Intro103': 3}
SLIP_TAIL = {'Intro102': 0, 'Intro103': 1}   # tutorial_3's closing message step


def pc_strings(folder):
    """{name: text} of the tutorial's strings.xml, the XML entities undone"""
    t = canon.read(os.path.join(X1, folder, 'strings.xml'))
    out = {}
    for n, v in re.findall(r'<string name="([^"]+)"[^>]*text="([^"]*)"', t):
        v = v.replace('&#xA;', '\n').replace('&quot;', '"').replace('&apos;', "'") \
            .replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        out[n] = v
    return out


def placed_objects(folder):
    """{object: (room, x, y)} of level.xml's objects with a position"""
    lv = canon.read(os.path.join(X1, folder, 'level.xml'))
    out = {}
    for rm in re.finditer(r'<room name="(\w+)"[^>]*>(.*?)</room>', lv, re.S):
        for om in re.finditer(r'<object name="([^"]+)"[^>]*position="(-?\d+)/(-?\d+)"', rm.group(2)):
            out[om.group(1)] = (rm.group(1), int(om.group(2)), int(om.group(3)))
    return out


def mobile_scene(scene):
    from runtime.scene import Level
    return Level(os.path.join(ROOT, 'levels', 's1', scene + '.json'))


def door_map(scene, L):
    """PC door `a/b` -> [the mobile door, its zone]: the door of the zone that
    is room a whose link leads into the zone that is room b (the overlay's
    PCWalkRoom, tools/pcref/pc_walks_s1.py)"""
    sys.path.insert(0, HERE)
    import pc_walks_s1
    zmap = pc_walks_s1.zone_map(mobile_scene(scene), pc_walks_s1.pc_rooms(scene), L)
    M = mobile_scene(scene)
    zname = {z.pid: z.name for z in M.zones}
    out = {}
    for d in M.doors:
        o = M.door_by_pid(d.link_to) if d.link_to is not None else None
        if o is None:
            continue
        a, b = zmap.get(zname.get(d.zone)), zmap.get(zname.get(o.zone))
        if a and b:
            out['%s/%s' % (a, b)] = [d.name, zname.get(d.zone)]
    return out


def tutorial_data(scene):
    folder = canon.TUTORIALS[scene]
    L = lap_model.Level(scene)
    strs = pc_strings(folder)
    data = {'folder': folder, 'texts': {k: strs[k] for k in MESSAGES[scene]}, 'lead': LEAD}
    start = {}
    for actor in ('woody', 'neighbor'):
        p = L.placed.get(actor)
        if p:
            start[actor] = [p[1], p[2], p[0]]
    data['start'] = start
    data['doors'] = door_map(scene, L)
    if scene in MARKERS:
        data['markers'] = MARKERS[scene]
    if scene == 'Intro101':
        placed = placed_objects(folder)
        signs = {}
        for obj in ('kit/sign', 'lir/sign', 'anc/sign'):
            room, x, y = placed[obj]
            hx, hy = L.objects[obj]['hot']['woody']
            signs[obj] = [x + hx, y + hy, room]
        data['signs'] = signs
        data['tricks'] = {k: v['quota1'] for k, v in canon.pc_level(scene)['tricks'].items()}
    else:
        pts = {}
        for name, obj in (('lir_sign1', 'lir/sign1'), ('kit_sign2', 'kit/sign2')):
            room, x, y = L.object_point(obj)
            pts[name] = [x, y, room]
        data['points'] = pts
    if scene == 'Intro102':
        room, x, y = L.object_point('anc/flower', actor='woody')
        data['at'] = {'anc/flower': [x, y, room]}
        data['wait'] = WAIT
    return data


def item_data(scene):
    """{(object, component): {field: value}} of the scene's PC item data"""
    L = lap_model.Level(scene)
    out = {}
    angry = canon.pc_level(scene)['angrytime']
    if scene == 'Intro101':
        return out
    out[('Rottweiler', 'Rottweiler')] = {'PCAngryTime': angry}
    slip = L.job_ticks('neighbor', 'slip1')
    assert slip == L.job_ticks('neighbor', 'slip3')
    ground = {'PCShoutIndex': 1, 'PCFixSeconds': 0.0, 'PCFireBefore': True, 'PCFireLead': True,
              'PCSlipSeconds': round((FIRE_LEAD + SLIP_LEAD[scene] + slip + SLIP_TAIL[scene]) / FPS, 3),
              'PCReactLead': 0}
    out[('Ground', 'TrickItem')] = ground
    for item, (comp, obj) in WOODY.get(scene, {}).items():
        room, x, y = L.object_point(obj, actor='woody')
        out.setdefault((item, comp), {})['PCWalkPoint'] = {'Woody': [x, y, room]}
    if scene == 'Intro103':
        search = L.job_ticks('neighbor', 'search')
        out[('Dog', 'Alerter')] = {'PCSurpriseSeconds': round((search + 1) / FPS, 3),
                                   'PCAlarmShoutSeconds': round(L.job_ticks('neighbor', 'shout0_light') / FPS, 3)}
    if scene == 'Intro102':
        dt = L.job_ticks('neighbor', 'doubletake1')
        assert dt == L.job_ticks('neighbor', 'doubletake3')
        room, x, y = L.object_point('lir/mum_smeared')
        out.setdefault(('MumPicture', 'TrickItem'), {}).update({
            'PCSurpriseSeconds': round(dt / FPS, 3), 'PCFireWait': LAUGH1_STEP,
            'PCFixSeconds': round(L.job_ticks('lir/mum_smeared', 'clean') / FPS, 3),
            'PCAlignX': True, 'PCFixPoint': [x, y, room], 'PCReactLead': 2, 'PCReactTail': 1})
    return out


def write(scene, data, items):
    p = os.path.join(ROOT, 'levels', 'pc', scene + '.overlay.json')
    ov = json.load(open(p)) if os.path.exists(p) else {'source': '', 'patches': []}
    drop = {'PCDescriptions', 'PCTutorial'} | {k for v in items.values() for k in v}
    for e in ov['patches']:
        if (e.get('object'), e.get('component')) in items or e.get('object') == 'LevelScript':
            for k in drop:
                (e.get('set') or {}).pop(k, None)
    ov['patches'] = [e for e in ov['patches'] if e.get('set') != {}]
    src = ("the PC's %s (tools/pcref/pc_tutorial_s1.py: game.exe's tutorial classes, the "
           "tutorial's level.xml, objects.xml, trigger.xml, strings.xml)" % data['folder'])
    ov['patches'].append({'object': 'LevelScript', 'component': 'LevelScript',
                          'set': {'PCTutorial': data}, 'source': src})
    for (obj, comp), st in sorted(items.items()):
        ov['patches'].append({'object': obj, 'component': comp, 'set': st, 'source': src})
    note = ("The PC's tutorial (tools/pcref/pc_tutorial_s1.py): the level class's director "
            "and neighbour scripts run in place of the LevelScript and the camera script "
            "(runtime/tutorial.py TutorialPC101-103), their data in PCTutorial.")
    old = ("The director's messages (tools/pcref/pc_tutorial_s1.py): the PC's %s "
           "strings.xml texts by their code names, paired one to one with the "
           "LevelScript actions' PC-build keys (PCDescriptions)." % data['folder'])
    s = ov.get('source', '').replace(old, '').strip()
    if note not in s:
        s = (s + ' ' + note).strip()
    ov['source'] = s
    json.dump(ov, open(p, 'w'), indent=1, ensure_ascii=False)
    open(p, 'a').write('\n')


def main(argv):
    do_write = '--write' in argv
    for scene in sorted(canon.TUTORIALS):
        data = tutorial_data(scene)
        items = item_data(scene)
        print('==', scene, data['folder'])
        for k, v in data.items():
            if k != 'texts':
                print('   %-8s %s' % (k, v))
        print('   texts    %s' % ' '.join(sorted(data['texts'])))
        for (obj, comp), st in sorted(items.items()):
            print('   %s/%s %s' % (obj, comp, st))
        if do_write:
            write(scene, data, items)
            print('   wrote levels/pc/%s.overlay.json' % scene)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
