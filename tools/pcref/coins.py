"""The Season 2 coins, PC against the profile: for each mobile scoring
TrickItem (the ones that pay a coin), the PC trick records its setup leads
to and their rage — through the combination whose ingredient is the
inventory the mobile item takes, the object variant it makes, and the
`<trick name=...>` records inside that object's actions (GameLogic.dll
fcn.1000140b credits every named record of a playing action once, at its
`time`: coins += tricks.xml coins, rage += tricks.xml rage).

  python3 tools/pcref/coins.py [--root ~/nfh-bench/pcref/pc] <level number ...>
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canon

ROOT = canon.ROOT
REPO = canon.REPO
FLAGS = ('CompoundExtraCoin', 'ExtraCoin206', 'ExtraCoin210', 'PlantCarnivoreExtra',
         'ExtraCoinLinkedTrick', 'ExtraCoinAngerAmount')
# the mobile ladder's hard-coded extras (Rottweiler.cs:613-639)
MOBILE_EXTRA = {'CompoundExtraCoin': 20, 'ExtraCoin206': 15, 'ExtraCoin210': 10, 'PlantCarnivoreExtra': 10}


def pc_actions(n):
    """objects.xml with the action bodies: {object: [(action, [trick names], own)]}"""
    folder = canon.S2[n]
    season = 'nfh2'
    d = '%s/%s/x/%s' % (ROOT, season, folder)
    ob = canon.read(d + '/objects.xml')
    tr = canon.read(d + '/tricks.xml')
    rage = {m.group(1): int(m.group(2)) // 1000 for m in re.finditer(r'<trick name="([^"]+)"[^>]*rage="(\d+)"', tr)}
    coins = {m.group(1): int(m.group(2)) for m in re.finditer(r'<trick name="([^"]+)"[^>]*coins="(\d+)"', tr)}
    cb = canon.read(d + '/combine.xml')
    combos = {}
    for m in re.finditer(r'<combination name="([^"]+)"([^>]*)>(.*?)</combination>', cb, re.S):
        combos[m.group(1)] = {'trick': 'trick="true"' in m.group(2),
                              'ingredients': re.findall(r'<ingredient name="([^"]+)"', m.group(3))}
    acts = {}
    for om in re.finditer(r'<object name="([^"]+)"([^>]*)>(.*?)</object>', ob, re.S):
        name, body = om.group(1), om.group(3)
        lst = []
        for am in re.finditer(r'<action\s+name="([^"]+)"([^>]*?)(/>|>(.*?)</action>)', body, re.S):
            inner = am.group(4) or ''
            names = re.findall(r'<trick\b[^>]*\bname="([^"]+)"', inner)
            own = bool(re.search(r'<trick\b(?![^>]*\bname=)[^>]*jingle="true"', inner))
            ticks = {}
            laughs = {}
            for tm in re.finditer(r'<trick\b([^>]*)/?>', inner):
                a = dict(re.findall(r'(\w+)="([^"]*)"', tm.group(1)))
                if a.get('name') and a.get('time', '').isdigit():
                    ticks.setdefault(a['name'], int(a['time']))
                if a.get('name') and a.get('laugh', '').isdigit():
                    laughs[a['name']] = int(a['laugh'])
            lst.append((am.group(1), names, own, ticks, laughs))
        acts[name] = lst
    return rage, coins, combos, acts


def plan_items(n):
    """the items the profile's plan awaits (tests/plans/pc/s2, else tests/plans/s2): the coin tricks"""
    names = set()
    for sub in ('pc/s2', 's2'):
        p = '%s/tests/plans/%s/Level%d.txt' % (REPO, sub, n)
        if os.path.exists(p):
            for ln in open(p):
                ln = ln.split('#')[0].strip()
                m = re.match(r'await\s+([A-Za-z_][\w@:]*)', ln)
                if m:
                    names.add(m.group(1).split('@')[0])
            if names:
                break
    return names


def mobile_items(n):
    lv = json.load(open('%s/levels/s2/Level%d.json' % (REPO, n)))
    objs = lv['objects']
    def goname(o):
        return ((o.get('data') or {}).get('m_GameObject') or {}).get('name')
    byid = {}
    for k, o in objs.items():
        if o.get('type') == 'TrickItem':
            byid[int(k)] = goname(o)
    items = []
    for k, o in objs.items():
        if o.get('type') != 'TrickItem':
            continue
        d = o.get('data') or {}
        if goname(o) not in plan_items(n):
            continue
        req = [canon.norm(x) for x in (d.get('RequiredInventory'), d.get('SecondRequiredInventory')) if x and x != 'IT_NONE']
        linked = ((d.get('LinkedItemTrick') or {}).get('path'))
        extras = {f: d.get(f) for f in FLAGS if d.get(f)}
        items.append({'name': goname(o), 'score': d.get('TrickScore'), 'anger': d.get('AngerAmount'),
                      'requires': req, 'linked': byid.get(linked) if isinstance(linked, int) else linked, 'extras': extras})
    return items


def credits_for(inv, rage, combos, acts):
    """the PC combinations taking this inventory -> the variant objects -> the credited records"""
    out = []
    for cname, c in combos.items():
        if any(canon.norm(i) == inv for i in c['ingredients']):
            obj = cname
            recs = []
            for act, names, own, ticks, laughs in acts.get(obj, []):
                for t in names:
                    recs.append((act, t, rage.get(t), ticks.get(t), laughs.get(t)))
                if own and act in rage:
                    recs.append((act, act, rage[act], ticks.get(act), laughs.get(act)))
            out.append((cname, c['trick'], recs))
    return out


def _strip_key(patches, key):
    """drop `key` from every patch's set; a patch left empty goes"""
    out = []
    for e in patches:
        st = e.get('set')
        if isinstance(st, dict) and key in st:
            st = dict(st); del st[key]
            if not st:
                continue
            e = dict(e); e['set'] = st
        out.append(e)
    return out


def _set_key(patches, item, key, value):
    """set `key` on the item's TrickItem patch, or add one"""
    for e in patches:
        if e.get('object') == item and e.get('component') == 'TrickItem' and isinstance(e.get('set'), dict):
            e['set'][key] = value; return
    patches.append({'object': item, 'component': 'TrickItem', 'set': {key: value}})


def show(n, write_laugh=False):
    rage, coins, combos, acts = pc_actions(n)
    found = {}
    found_laugh = {}
    print('=' * 100)
    print('LEVEL %d  PC %s  tricks: %s' % (n, canon.S2[n], ' '.join('%s=%d' % kv for kv in rage.items())))
    for it in mobile_items(n):
        mob_total = (it['anger'] or 0) + sum(MOBILE_EXTRA.get(f, 0) for f in it['extras']) + int(it['extras'].get('ExtraCoinAngerAmount') or 0)
        line = '  %-22s anger %-3s score %-3s req %-18s linked %-16s extras %s' % (
            it['name'], it['anger'], it['score'], ','.join(it['requires']) or '-', it['linked'] or '-', it['extras'] or '')
        print(line)
        for inv in it['requires']:
            cands = credits_for(inv, rage, combos, acts)
            own = [c for c in cands if it['name'].lower() in c[0].lower().replace('_', '')]
            for cname, isTrick, recs in (own or cands):
                uniq = {}
                for act, t, r, tk, lg in recs:
                    uniq.setdefault(t, (act, r, tk, lg))
                tot = sum(r or 0 for r in (v[1] for v in uniq.values()))
                print('      %s <- %s (trick=%s): %s  = %d' % (cname, inv, isTrick, ' '.join('%s@%s=%s/t%s/l%s' % (t, a, r, tk, lg) for t, (a, r, tk, lg) in uniq.items()), tot))
                ticks = [tk for (_a, _r, tk, _l) in uniq.values() if tk is not None]
                if ticks:
                    found.setdefault(it['name'], min(ticks))
                laughs = [lg for (_a, _r, _t, lg) in uniq.values() if lg is not None]
                if laughs and isTrick:
                    found_laugh[it['name']] = max(found_laugh.get(it['name'], 0), max(laughs))


    if write_laugh:
        # an item whose records the pairing did not reach takes the level's
        # commonest laugh level (tricks.xml: the mode over the objects' records)
        import collections
        allv = collections.Counter(lg for lst in acts.values() for (_a, _n, _o, _t, lgs) in lst for lg in lgs.values())
        if allv:
            mode = allv.most_common(1)[0][0]
            for it in mobile_items(n):
                if it['name'] not in found_laugh and it['requires']:
                    found_laugh[it['name']] = mode
        p = '%s/levels/pc/Level%d.overlay.json' % (REPO, n)
        ov = json.load(open(p))
        ov['patches'] = _strip_key(ov.get('patches', []), 'PCLaugh')
        for item, lg in found_laugh.items():
            _set_key(ov['patches'], item, 'PCLaugh', lg)
        note = " The reactions (tools/pcref/coins.py --write-laugh): PCLaugh = the `<trick laugh=>` level of the records the item's trick fires, which picks the PC neighbour's reaction clip (pcprofile.S2_REACTION_CLIPS)."
        if 'PCLaugh' not in ov['source']:
            ov['source'] += note
        json.dump(ov, open(p, 'w'), ensure_ascii=False, indent=1); open(p, 'a').write('\n')
        print('   written PCLaugh:', found_laugh)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    for a in args:
        show(int(a), write_laugh='--write-laugh' in sys.argv)
