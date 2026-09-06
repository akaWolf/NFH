"""The PC canon per level, from the unpacked gamedata.bnd (tools/pcref/gamedata.py),
next to the mobile level's data — the categories the two can be compared on:

  python3 tools/pcref/canon.py [--root ~/nfh-bench/pcref/pc] <level number ...>

Per level: the tricks (tricks.xml: quota / rage, angrytime), the recipes
(combine.xml: which object plus which inventory item makes the trick), the
containers and what they hold (objects.xml <content>), the walk-by triggers
(trigger.xml nearobj), the neighbour's actions per object with their length
(objects.xml <action actor="neighbor"> time in 1/20 s, "auto" = the
animation's frames at 20 fps from anims.xml), the rooms and doors (level.xml),
the level's angrytime and time limit (leveldata.xml). The mobile side: the
TrickItems (TrickScore / AngerAmount, the inventory they take), the search
items (the IT_ types they hold), NoticeWhenWalkNearby, the items the neighbour's
routine uses with their RottweilerUseAnimation length, the zones and doors.
"""
import json
import os
import re
import sys

ROOT = os.path.expanduser('~/nfh-bench/pcref/pc')
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S1 = {101: 'peep', 102: 'sofa', 103: 'mail', 104: 'pie', 105: 'piano', 106: 'bath', 107: 'art',
      108: 'suntan', 109: 'pig', 110: 'barbecue', 111: 'laundry', 112: 'fitness', 113: 'DIY', 114: 'hunter'}
S2 = {201: 'ship1', 202: 'cn_b1', 203: 'cn_c2', 204: 'cn_c1', 205: 'cn_b2', 206: 'ship2', 207: 'in_b1',
      208: 'in_c1', 209: 'in_c2', 210: 'in_b2', 211: 'ship3', 212: 'me_c1', 213: 'me_c2', 214: 'ship4'}


def read(p):
    b = open(p, 'rb').read()
    return b.decode('utf-16') if b[:2] in (b'\xff\xfe', b'\xfe\xff') else b.decode('utf-8', 'replace')


def pc_level(n):
    season = 'nfh1' if n < 200 else 'nfh2'
    folder = ('level_' + S1[n]) if n < 200 else S2[n]
    d = '%s/%s/x/%s' % (ROOT, season, folder)
    out = {'folder': folder}
    lv = read(d + '/level.xml')
    m = re.search(r'<level [^>]*angrytime="(\d+)"', lv)
    out['angrytime'] = int(m.group(1)) if m else None
    out['rooms'] = {}
    for rm in re.finditer(r'<room name="(\w+)"[^>]*>(.*?)</room>', lv, re.S):
        out['rooms'][rm.group(1)] = {
            'doors': re.findall(r'<door name="([^"]+)"', rm.group(2)),
            'neighbors': re.findall(r'<neighbor name="(\w+)"', rm.group(2)),
            'objects': re.findall(r'<object name="([^"]+)"', rm.group(2)),
            'actors': re.findall(r'<actor name="(\w+)"', rm.group(2))}
    tr = read(d + '/tricks.xml')
    out['tricks'] = {}
    for m in re.finditer(r'<trick name="([^"]+)"([^>]*)/>', tr):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
        out['tricks'][m.group(1)] = {k: (int(v) if v.isdigit() else v) for k, v in a.items()}
    cb = read(d + '/combine.xml')
    out['combos'] = {}
    for m in re.finditer(r'<combination name="([^"]+)"([^>]*)>(.*?)</combination>', cb, re.S):
        out['combos'][m.group(1)] = {'trick': 'trick="true"' in m.group(2),
                                     'ingredients': re.findall(r'<ingredient name="([^"]+)"', m.group(3))}
    ob = read(d + '/objects.xml')
    an = read(d + '/anims.xml')
    frames = {}
    for om in re.finditer(r'<object name="([^"]+)">(.*?)</object>', an, re.S):
        for am in re.finditer(r'<animation name="([^"]+)"[^>]*>(.*?)</animation>', om.group(2), re.S):
            frames[(om.group(1), am.group(1))] = len(re.findall(r'<frame', am.group(2)))
    out['objects'] = {}
    for om in re.finditer(r'<(object|door) name="([^"]+)"([^>]*)>(.*?)</\1>', ob, re.S):
        body = om.group(4); name = om.group(2)
        gfx = re.search(r'gfx="([^"]+)"', om.group(3))
        o = {'kind': om.group(1), 'gfx': gfx.group(1) if gfx else None,
             'flags': re.findall(r'<flag name="(\w+)"', body),
             'stdaction': re.findall(r'<stdaction name="(\w+)"', body),
             'contents': re.findall(r'<content name="(\w+)" count="(\d+)"', body),
             'hotspots': re.findall(r'<hotspot name="(\w+)"', body),
             'actions': []}
        for am in re.finditer(r'<action\s+name="([^"]+)"([^>]*)/>', body):
            a = dict(re.findall(r'(\w+)="([^"]*)"', am.group(2)))
            t = a.get('time', 'auto')
            if t == 'auto':
                key = (gfx.group(1) if gfx else name, a.get('objanim', '')) if a.get('actoranim', 'inv') == 'inv' \
                    else (a.get('actor', ''), a.get('actoranim', ''))
                n_frames = frames.get(key)
                secs = n_frames / 20.0 if n_frames else None
            else:
                secs = int(t) / 20.0 if t.isdigit() else None
            o['actions'].append({'name': am.group(1), 'actor': a.get('actor'), 'anim': a.get('actoranim'),
                                 'objanim': a.get('objanim'), 'time': t, 'secs': secs, 'noise': a.get('noise')})
        out['objects'][name] = o
    out['inventory'] = re.findall(r'<inventar name="(\w+)">', ob)
    tg = read(d + '/trigger.xml')
    out['triggers'] = []
    for am in re.finditer(r'<actor name="(\w+)">(.*?)</actor>', tg, re.S):
        for bm in re.finditer(r'<behavior name="(\w+)">(.*?)</behavior>', am.group(2), re.S):
            for t in re.finditer(r'<trigger ([^>]*)/>', bm.group(2)):
                a = dict(re.findall(r'(\w+)="([^"]*)"', t.group(1)))
                a['who'] = am.group(1); a['behavior'] = bm.group(1); out['triggers'].append(a)
    ld = read('%s/%s/x/leveldata.xml' % (ROOT, season))
    m = re.search(r'<level name="%s"([^>]*)/>' % folder, ld, re.S)
    out['leveldata'] = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1))) if m else {}
    return out


ALIAS = {'toiletpaper': 'wcpaper', 'superglue': 'glue', 'hairrestorer': 'hairrestorer'}


def norm(t):
    """a PC inventory name or a mobile IT_ type, lowercased and aliased"""
    t = t.lower()
    if t.startswith('it2_'):
        t = t[4:]
    elif t.startswith('it_'):
        t = t[3:]
    return ALIAS.get(t, t)


def mobile_level(n):
    p = '%s/levels/%s/Level%d.json' % (REPO, 's1' if n < 200 else 's2', n)
    lv = json.load(open(p))
    objs = lv['objects']
    def goname(o):
        return ((o.get('data') or {}).get('m_GameObject') or {}).get('name')
    anims = {}
    for k, o in objs.items():
        d = o.get('data') or {}
        if isinstance(d.get('Animations'), list):
            for a in d['Animations']:
                if a.get('Name') and a['Name'] not in anims:
                    fr = (a.get('EndFrame') or 0) - (a.get('StartFrame') or 0) + 1
                    anims[a['Name']] = (fr, a.get('FrameRate') or 0)
    def seq_secs(names):
        tot = 0.0
        for nm in names:
            fr, fps = anims.get(nm, (0, 0))
            if fps:
                tot += fr / float(fps)
        return round(tot, 1)
    out = {'items': {}, 'search': {}, 'zones': set(), 'routine': [], 'walkby': []}
    for k, o in objs.items():
        d = o.get('data') or {}
        t = o.get('type'); g = goname(o)
        if t in ('TrickItem', 'Item', 'SearchItem'):
            z = (d.get('Zone') or {}).get('name')
            if z:
                out['zones'].add(z)
        if t == 'TrickItem':
            req = [norm(x) for x in (d.get('RequiredInventory'), d.get('SecondRequiredInventory')) if x and x != 'IT_NONE']
            out['items']['%s#%s' % (g, k)] = {'name': g, 'score': d.get('TrickScore'), 'anger': d.get('AngerAmount'), 'requires': req,
                               'walkby': bool(d.get('NoticeWhenWalkNearby')),
                               'use_anims': [a for a in (d.get('RottweilerUseAnimation') or []) if isinstance(a, str)],
                               'use_secs': seq_secs([a for a in (d.get('RottweilerUseAnimation') or []) if isinstance(a, str)])}
            if d.get('NoticeWhenWalkNearby'):
                out['walkby'].append(g)
            out['items']['%s#%s' % (g, k)]['name'] = g
        if t == 'SearchItem':
            out['search'][g] = [norm(i.get('Type')) for i in (d.get('InventoryItems') or []) if isinstance(i, dict) and i.get('Type')]
        if t == 'ActionManager' and ((d.get('Owner') or {}).get('name') or 'Rottweiler').startswith('Rottweiler'):
            out['routine'] = [((a.get('Item') or {}).get('name'), a.get('MoveOnly')) for a in (d.get('Actions') or [])]
    return out


def multiset(xs):
    from collections import Counter
    return Counter(xs)


def diff_ms(a, b):
    a, b = multiset(a), multiset(b)
    only_a = sorted((a - b).elements()); only_b = sorted((b - a).elements())
    return ('same' if not only_a and not only_b else 'PC-only %s | mobile-only %s' % (only_a, only_b))


def show(n):
    pc = pc_level(n); mob = mobile_level(n)
    print('=' * 100)
    print('LEVEL %d  PC %s  angrytime=%s  leveldata=%s' % (n, pc['folder'], pc['angrytime'], pc['leveldata']))
    print('-- rooms: PC %d %s | mobile zones %d' % (len(pc['rooms']), sorted(pc['rooms']), len(mob['zones'])))
    # tricks: the score multisets
    pcq = sorted((v['quota1'] if 'quota1' in v else v.get('rage', 0) // 1000) for v in pc['tricks'].values())
    mq = sorted(e['score'] or e['anger'] for e in mob['items'].values() if e['score'] or e['anger'])
    print('-- trick values: %s' % diff_ms(pcq, mq))
    print('   PC:', ' '.join('%s=%s' % (t.split('/')[-1], v['quota1'] if 'quota1' in v else v.get('rage', 0) // 1000) for t, v in pc['tricks'].items()))
    print('   mob:', ' '.join('%s=%s%s' % (e['name'], e['score'] or e['anger'], '*' if e['walkby'] else '') for g, e in mob['items'].items() if e['score'] or e['anger']))
    # recipes: the inventory types the tricks take
    pc_ing = [norm(i) for c, v in pc['combos'].items() if v['trick'] for i in v['ingredients'] if i.lower() in [x.lower() for x in pc['inventory']]]
    mob_ing = [t for e in mob['items'].values() for t in e['requires']]
    print('-- recipe inventory: %s' % diff_ms(pc_ing, mob_ing))
    print('   PC:', ' | '.join('%s <- %s' % (c.split('/')[-1], '+'.join(i.split('/')[-1] for i in v['ingredients'])) for c, v in pc['combos'].items()))
    print('   mob:', ' | '.join('%s <- %s' % (e['name'], '+'.join(e['requires'])) for g, e in mob['items'].items() if e['requires']))
    # containers
    pc_c = [norm(k) + ('*' if int(cnt) > 5 else '') for v in pc['objects'].values() for k, cnt in v['contents'] for _ in range(min(int(cnt), 1) if int(cnt) > 5 else int(cnt))]
    mob_c = [t for ts in mob['search'].values() for t in ts]
    print('-- containers: %s' % diff_ms(pc_c, mob_c))
    print('   PC:', ' | '.join('%s: %s' % (o, ','.join(k + ('*' if int(c) > 5 else (('x' + c) if int(c) > 1 else '')) for k, c in v['contents'])) for o, v in pc['objects'].items() if v['contents']))
    print('   mob:', ' | '.join('%s: %s' % (g, ','.join(ts)) for g, ts in mob['search'].items()))
    print('-- walk-by: PC %s | mobile %s' % ([t.get('object', '').split('/')[-1] for t in pc['triggers'] if t.get('position') == 'nearobj'], mob['walkby']))
    acts = []
    for o, v in pc['objects'].items():
        na = [a for a in v['actions'] if a['actor'] == 'neighbor' and a['name'] not in ('clean', 'repair', 'enter', 'leave', 'take', 'give', 'open', 'close')]
        if na:
            acts.append('%s: %s' % (o.split('/')[-1], ' '.join('%s=%s' % (a['name'], ('%.1f' % a['secs']) if a['secs'] is not None else a['time']) for a in na)))
    print('-- PC neighbour actions (s):', ' | '.join(acts))
    print('-- mobile routine:', ' > '.join(x[0] or '?' for x in mob['routine']))
    seen = set(); uses = []
    for it, mo in mob['routine']:
        e = next((e for e in mob['items'].values() if e['name'] == it), None)
        if e is not None and it not in seen and e['use_anims']:
            seen.add(it); uses.append('%s=%s' % (it, e['use_secs']))
    print('-- mobile routine uses (s):', ' | '.join(uses))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    for a in args:
        show(int(a))
