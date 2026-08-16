"""Dump every level's trick inventory: what pays, what it needs, where the
inventory comes from — the raw material of the pass-3 plans."""
import glob, json, sys

def name_of(objs, pid):
    o = objs.get(str(pid)) or {}
    d = o.get('data', {})
    go = d.get('m_GameObject')
    if isinstance(go, dict) and go.get('name'):
        return go['name']
    return d.get('name') or d.get('m_Name')

def ref(d, key):
    v = d.get(key)
    if isinstance(v, dict):
        return v.get('path') or None
    return None

def refname(d, key):
    v = d.get(key)
    if isinstance(v, dict):
        return v.get('name') or v.get('path')
    return None

for path in sorted(glob.glob('levels/s*/Level*.json')):
    d = json.load(open(path))
    objs = d['objects']
    items = {}
    for pid, o in objs.items():
        if o['type'] in ('TrickItem', 'SearchItem', 'HideItem', 'Door',
                         'Toilet', 'Television', 'Rake', 'Drawing',
                         'GroundItem', 'InspectItem'):
            items[pid] = o
    lvl = path.split('/')[-1][:-5]
    print('==', lvl)
    for pid, o in items.items():
        dd = o['data']
        nm = name_of(objs, ref(dd, 'm_GameObject') or pid) or '?'
        t = o['type']
        if t == 'SearchItem':
            inv = dd.get('InventoryItems') or []
            names = []
            for iv in inv:
                if isinstance(iv, dict):
                    names.append('%s x%s' % (iv.get('Type'),
                                             iv.get('UseCount')))
            extra = []
            for k in ('Locked', 'Dexterity', 'RequirePriming', 'KeepFull',
                      'TrickAfterWoodyUse', 'PigKeys'):
                if dd.get(k):
                    extra.append(k)
            print('  S %-22s %s inv=[%s] %s' % (
                nm, pid, ', '.join(names), ' '.join(extra)))
        else:
            score = dd.get('TrickScore') or 0
            fields = []
            for k in ('RequiredInventory', 'SecondRequiredInventory',
                      'CompoundRequiredInventory', 'PrimeWithInventory',
                      'PrimedInventoryType'):
                v = dd.get(k)
                if v and v != 'IT_NONE':
                    fields.append('%s=%s' % (k[:14], v))
            for k in ('RequirePriming', 'RequirePrimingOnlyWhenTricked',
                      'Locked', 'Compound', 'RequireUnprime', 'Neutral',
                      'RottweilerUseTogglesPrime', 'Dexterity', 'CanFix',
                      'GetTrickedAtOnce', 'NoticeWhenEnterZone',
                      'NoticeWhenWalkNearby', 'UseOnce', 'CanUndoTrick',
                      'DontUseOn', 'Tricked', 'Primed'):
                if dd.get(k):
                    fields.append(k)
            for k in ('LinkedItemTrick', 'DependsOn', 'PrimingItem',
                      'ObjectToPrimeWhenPrimed', 'FixingItem',
                      'DexterityUnlocker'):
                r = refname(dd, k)
                if r:
                    fields.append('%s->%s' % (k[:12], r))
            if dd.get('DexterityUnlocker') and dd['DexterityUnlocker'] != 'IT_NONE' and not isinstance(dd['DexterityUnlocker'], dict):
                fields.append('DexUnlock=%s' % dd['DexterityUnlocker'])
            mark = '*' if score else ' '
            print('  %s %s %-20s %s score=%s %s' % (
                mark, t[0], nm, pid, score, ' '.join(fields)))
