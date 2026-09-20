#!/usr/bin/env python3
"""The Season 2 respawn's landing, from the PC data onto the remaster's sheet.

    python3 tools/pcref/pc_respawn_s2.py            # print the animation and its checks
    python3 tools/pcref/pc_respawn_s2.py --write    # levels/pc/Season2.overlay.json

GameLogic's catch fiber (fcn.100061dc, case 4) puts Woody 900 px above the
middle of the room's path and pushes his `respawn` action (generic/objects.xml:
actoranim `respawn`, actornextanim `ms2`, time auto, a <translation
object="true" starttime="0" endtime="5" destination="0/900"/>). The DoActions
job moves him by the translation every tick of its count (fcn.100015c4: at
count t in (start, end] the base plus destination * (t - start) / (end - start),
integer division, the base the position at the job's start), and the GFX plays
generic/anims.xml's `respawn`: 38 frames of landing.tga and landing_0000-0013
with their sounds.

The remaster ships the fifteen images as textures/s2/W_Landing.png (4 x 4
cells of 165 x 243, the last one empty) though no level uses it. Its cells are
crops of the PC canvas at one origin — every image's top in its cell less its
gfxdata.xml offset gives the same canvas row (231 +- 1), as W_Stand's twelve
cells do against the stand frames ms0-ms3 (308) — so the sheet is drawn where
the PC draws the frames when its DeltaLocation is the difference of the two
origins (W_Stand's own DeltaLocation is 0/0): the median x and y of each set.

The output is a Season 2 overlay op: Woody's PawnAnimationController (by its
BaseAnimationPath) gets `PCRespawn`, the pattern of the 38 frames over the
cells, the sounds on their frames, 12 frames a second (a frame a level tick).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import canon  # noqa: E402

X = '%s/nfh2/x/generic' % canon.ROOT
TEX = os.path.join(ROOT, 'textures', 's2')
OUT = os.path.join(ROOT, 'levels', 'pc', 'Season2.overlay.json')


def _block(text, tag, name):
    """the body of <tag name="name"> … </tag> (the first)"""
    m = re.search(r'<%s name="%s"[^>]*>(.*?)</%s>' % (tag, name, tag), text, re.S)
    return m.group(1) if m else ''


def woody_anims():
    """generic/anims.xml's <object name="woody"> block"""
    an = canon.read(X + '/anims.xml')
    i = an.find('<object name="woody"')
    return an[i:an.find('</object>', i)]


def respawn_frames():
    """[(gfx, sfx or None)] of Woody's `respawn` animation (generic/anims.xml)"""
    body = _block(woody_anims(), 'animation', 'respawn')
    out = []
    for f in re.findall(r'<frame ([^>]*)/>', body):
        at = dict(re.findall(r'(\w+)="([^"]*)"', f))
        out.append((at.get('gfx'), at.get('sfx')))
    return out


def respawn_action():
    """Woody's `respawn` action record and its translation (generic/objects.xml)"""
    ob = canon.read(X + '/objects.xml')
    woody = _block(ob, 'actor', 'woody')
    m = re.search(r'<action name="respawn" ([^>]*)>(.*?)</action>', woody, re.S)
    at = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    tr = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r'<translation ([^>]*)/>', m.group(2)).group(1)))
    return at, tr


def offsets():
    """{image: (x, y)} of Woody's frames (generic/gfxdata.xml)"""
    gx = canon.read(X + '/gfxdata.xml')
    w = gx[gx.find('<object name="woody"'):]
    return {i: tuple(map(int, o.split('/'))) for i, o in
            re.findall(r'<file image="([^"]+)" offset="([^"]+)"', w)}


def cell_tops(path, cols, rows):
    """[(left, top) of the opaque pixels or None] per cell of a sheet"""
    from PIL import Image
    import numpy as np
    im = np.array(Image.open(path).convert('RGBA'))
    h, w = im.shape[:2]
    cw, ch = w / cols, h / rows
    out = []
    for r in range(rows):
        for c in range(cols):
            a = im[int(round(r * ch)):int(round((r + 1) * ch)),
                   int(round(c * cw)):int(round((c + 1) * cw)), 3]
            ys, xs = np.nonzero(a > 40)
            out.append(None if len(xs) == 0 else (int(xs.min()), int(ys.min())))
    return (w, h), out


def median(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2.0


def build():
    frames = respawn_frames()
    act, tr = respawn_action()
    off = offsets()
    # the sheet holds the distinct images in the order of their names
    images = sorted({g for g, _s in frames}, key=lambda g: (g != 'landing.tga', g))
    cell = {g: i for i, g in enumerate(images)}
    (lw, lh), ltops = cell_tops(os.path.join(TEX, 'W_Landing.png'), 4, 4)
    (sw, sh), stops = cell_tops(os.path.join(TEX, 'W_Stand.png'), 4, 3)
    # W_Stand's cells: Stand_Up 0-2, Stand_Right 3-5, Stand_Down 6-8, Stand_Left 9-11
    # (the level data's Stand_* frames) — the PC's ms0-ms3 (generic/anims.xml)
    an = woody_anims()
    stand = []
    for k in range(4):
        body = _block(an, 'animation', 'ms%d' % k)
        seen = []
        for g in re.findall(r'<frame gfx="([^"]+)"', body):
            if g not in seen:
                seen.append(g)
        stand.extend(seen)
    lo = [(off[g][0] - ltops[cell[g]][0], off[g][1] - ltops[cell[g]][1]) for g in images]
    so = [(off[g][0] - stops[i][0], off[g][1] - stops[i][1]) for i, g in enumerate(stand)]
    dx = median([o[0] for o in lo]) - median([o[0] for o in so])
    dy = median([o[1] for o in lo]) - median([o[1] for o in so])
    pattern = [cell[g] for g, _s in frames]
    sounds = [{'Frame': i, 'FileName': os.path.splitext(os.path.basename(s))[0]}
              for i, (_g, s) in enumerate(frames) if s]
    anim = {
        'Name': 'PCRespawn', 'SheetTexture': 'W_Landing', 'TextureFileName': 'W_Landing',
        'SheetColumns': 4, 'SheetRows': 4, 'StartFrame': 0, 'EndFrame': len(images) - 1,
        'FrameRate': 12.0, 'OriginalWidth': float(lw), 'OriginalHeight': float(lh),
        'DeltaLocation': {'x': float(dx), 'y': float(dy)}, 'Type': 'Single',
        'InfiniteLoop': False, 'HoldOnLastFrame': False, 'Blocking': False,
        'UsePattern': True, 'Pattern': pattern, 'Sounds': sounds,
    }
    checks = {'images': images, 'landing_origins': lo, 'stand_origins': so,
              'action': act, 'translation': tr, 'frames': len(frames)}
    return anim, checks


def fight_ops():
    """the catchers' `fight_woody` (generic/anims.xml) is the remaster's FightWoody /
    MotherHitWoody pattern frame for frame — the images numbered by their first
    appearance, the sounds on the same frames — slowed to 8 and 9 frames a second;
    the PC plays it a frame a tick. Returns the overlay ops and the checks"""
    an = canon.read(X + '/anims.xml')
    ops, ck = [], []
    for actor, role, name, level in (('neighbor', 'Rottweiler', 'FightWoody', 201),
                                     ('mother', 'Mother', 'MotherHitWoody', 206)):
        i = an.find('<object name="%s"' % actor)
        blk = an[i:an.find('</object>', i)]
        body = _block(blk, 'animation', 'fight_woody')
        fr = [dict(re.findall(r'(\w+)="([^"]*)"', f)) for f in re.findall(r'<frame ([^>]*)/>', body)]
        first = {}
        for f in fr:
            first.setdefault(f.get('gfx'), len(first))
        pat = [first[f.get('gfx')] for f in fr]
        snd = [(k, os.path.splitext(os.path.basename(f['sfx']))[0]) for k, f in enumerate(fr) if f.get('sfx')]
        lv = json.load(open(os.path.join(ROOT, 'levels', 's2', 'Level%d.json' % level)))
        path = 'Textures/NFH2/Characters/%s/' % role
        mob = None
        for o in lv['objects'].values():
            d = o.get('data') or {}
            if o.get('type') == 'PawnAnimationController' and d.get('BaseAnimationPath') == path:
                mob = next((a for a in d['Animations'] if a['Name'] == name), None)
        same = mob is not None and mob.get('Pattern') == pat and \
            [(s['Frame'], s['FileName']) for s in mob.get('Sounds') or []] == snd
        ck.append((actor, name, len(pat), same, mob.get('FrameRate') if mob else None))
        if same:
            ops.append({'component': 'PawnAnimationController', 'match': {'BaseAnimationPath': path},
                        'anim': name, 'anim_set': {'FrameRate': float(12)}})
    return ops, ck


def fear_anims():
    """Woody's fear1 / fear3 and their loops (generic/anims.xml; the catch fiber's case 1
    picks fear1 when the catcher's x is the greater, 0x100064fe-0x1000651e) over the
    remaster's W_Fear: its ten cells a side are the PC's fear3_0000-0009 (the FearLeft
    half) and fear1_0000-0009 (FearRight) — each half's cells against the gfxdata offsets
    hold one x origin within 8-11 px, the other assignment 21-31 — but the halves were
    cropped apart and the loop frames 0005-0009 sit 6 px off frames 0000-0004 in both, so
    no one DeltaLocation places them as the PC does: the frames and their order are the
    PC's, the placement the remaster's own FearLeft / FearRight DeltaLocation"""
    wa = woody_anims()
    lv = json.load(open(os.path.join(ROOT, 'levels', 's2', 'Level201.json')))
    dl = {}
    for o in lv['objects'].values():
        d = o.get('data') or {}
        if o.get('type') == 'PawnAnimationController' and \
                d.get('BaseAnimationPath') == 'Textures/NFH2/Characters/Woody/':
            for a in d['Animations']:
                if a['Name'] in ('FearLeft', 'FearRight'):
                    dl[a['Name']] = a['DeltaLocation']
    out = []
    for side, base, half in (('fear1', 10, 'FearRight'), ('fear3', 0, 'FearLeft')):
        for nm, typ in ((side, 'Single'), (side + '_loop', 'Looping')):
            fr = [dict(re.findall(r'(\w+)="([^"]*)"', f)) for f in
                  re.findall(r'<frame ([^>]*)/>', _block(wa, 'animation', nm))]
            pat = [base + int(re.search(r'_(\d{4})\.tga', f['gfx']).group(1)) for f in fr]
            snd = [{'Frame': k, 'FileName': os.path.splitext(os.path.basename(f['sfx']))[0]}
                   for k, f in enumerate(fr) if f.get('sfx')]
            out.append({
                'Name': 'PC' + side.capitalize() + ('Loop' if typ == 'Looping' else ''), 'SheetTexture': 'W_Fear',
                'TextureFileName': 'W_Fear', 'SheetColumns': 5, 'SheetRows': 4, 'StartFrame': min(pat),
                'EndFrame': max(pat), 'FrameRate': 12.0, 'OriginalWidth': 810.0, 'OriginalHeight': 735.0,
                'DeltaLocation': dict(dl[half]), 'Type': typ, 'InfiniteLoop': False,
                'HoldOnLastFrame': False, 'Blocking': False, 'UsePattern': True, 'Pattern': pat,
                'Sounds': snd})
    return out


def main(argv):
    anim, ck = build()
    fears = fear_anims()
    print('fear:', [(a['Name'], a['Pattern'], a['DeltaLocation'], a['Sounds']) for a in fears])
    fops, fck = fight_ops()
    print('fight_woody against the remaster:', fck)
    print('respawn: %d frames, action %s, translation %s' % (ck['frames'], ck['action'], ck['translation']))
    print('landing origins (image offset - cell top):', ck['landing_origins'])
    print('stand origins:', ck['stand_origins'])
    print('DeltaLocation', anim['DeltaLocation'], 'pattern', anim['Pattern'])
    print('sounds', anim['Sounds'])
    if '--write' in argv:
        ov = {'source': 'GameLogic.dll fcn.100061dc case 4 (the respawn) and fcn.100015c4 (the '
                        'translation); generic/anims.xml `respawn`, generic/gfxdata.xml, '
                        'generic/objects.xml; textures/s2/W_Landing.png; tools/pcref/pc_respawn_s2.py',
              'patches': [{'component': 'PawnAnimationController',
                           'match': {'BaseAnimationPath': 'Textures/NFH2/Characters/Woody/'},
                           'append': {'Animations': [anim] + fears}}] + fops}
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(ov, f, indent=1, ensure_ascii=False)
            f.write('\n')
        print('wrote', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
