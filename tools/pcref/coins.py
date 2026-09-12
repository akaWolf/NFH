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
            lst.append((am.group(1), names, own))
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
            for act, names, own in acts.get(obj, []):
                for t in names:
                    recs.append((act, t, rage.get(t)))
                if own and act in rage:
                    recs.append((act, act, rage[act]))
            out.append((cname, c['trick'], recs))
    return out


def show(n):
    rage, coins, combos, acts = pc_actions(n)
    print('=' * 100)
    print('LEVEL %d  PC %s  tricks: %s' % (n, canon.S2[n], ' '.join('%s=%d' % kv for kv in rage.items())))
    for it in mobile_items(n):
        mob_total = (it['anger'] or 0) + sum(MOBILE_EXTRA.get(f, 0) for f in it['extras']) + int(it['extras'].get('ExtraCoinAngerAmount') or 0)
        line = '  %-22s anger %-3s score %-3s req %-18s linked %-16s extras %s' % (
            it['name'], it['anger'], it['score'], ','.join(it['requires']) or '-', it['linked'] or '-', it['extras'] or '')
        print(line)
        for inv in it['requires']:
            for cname, isTrick, recs in credits_for(inv, rage, combos, acts):
                uniq = {}
                for act, t, r in recs:
                    uniq.setdefault(t, (act, r))
                tot = sum(r or 0 for r in (v[1] for v in uniq.values()))
                print('      %s <- %s (trick=%s): %s  = %d' % (cname, inv, isTrick, ' '.join('%s@%s=%s' % (t, a, r) for t, (a, r) in uniq.items()), tot))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    for a in args:
        show(int(a))
