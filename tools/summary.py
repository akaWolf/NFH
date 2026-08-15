"""Human-readable summary of an exported level."""
import json, sys


def nm(v):
    if isinstance(v, dict):
        return v.get('name') or ('#%s' % v.get('path'))
    return v


def main(path):
    d = json.load(open(path))
    objs = d['objects']
    print('### %s  (%s)' % (d['scene'], d.get('unity_scene')))
    # Transition derives from Door, and is what Season 2 uses for nearly all of
    # its zone links; report the two together.
    subclasses = {'Door': ('Door', 'Transition')}

    def by(t):
        want = subclasses.get(t, (t,))
        return [(p, o['data']) for p, o in objs.items()
                if o['type'] in want and 'data' in o]

    def geometry(comp):
        """Zone extents are not in the Zone component: they come from the
        GameObject's Transform and BoxCollider."""
        go = (comp.get('m_GameObject') or {}).get('path')
        g = objs.get(str(go))
        if not g or 'data' not in g: return '', ''
        pos = box = ''
        for c in g['data'].get('components', []):
            child = objs.get(str(c['path']))
            if not child or 'data' not in child: continue
            if child['type'] == 'Transform':
                pos = '(%.2f %.2f %.2f)' % tuple(child['data']['position'])
            elif child['type'] == 'BoxCollider':
                b = child['data']
                box = '%.1fx%.1fx%.1f' % tuple(b['size'])
        return pos, box

    zones = by('Zone')
    print('\n-- ZONES (%d) --  (extent = Transform + BoxCollider; the adjacency'
          ' graph is built at runtime, not serialized)' % len(zones))
    for p, z in zones:
        pos, box = geometry(z)
        flags = ' '.join(k for k in ('ExitZone',) if z.get(k))
        print('  %-10s pos=%-22s box=%-14s %s %s' % (
            nm(z.get('m_GameObject')), pos, box, z.get('EndString') or '', flags))

    doors = by('Door')
    print('\n-- DOORS (%d) --' % len(doors))
    for p, dd in doors:
        print('  %-16s type=%-12s link=%-14s woody=%s/%s' % (
            nm(dd.get('m_GameObject')), dd.get('DoorType'), nm(dd.get('LinkTo')),
            dd.get('WoodyEnterAnimation'), dd.get('WoodyLeaveAnimation')))

    for t in ('TrickItem', 'SearchItem', 'GroundItem', 'HideItem'):
        items = by(t)
        if not items: continue
        print('\n-- %s (%d) --' % (t.upper(), len(items)))
        for p, it in items:
            bits = []
            for k in ('TrickScore', 'RequiredInventory', 'DependsOn', 'Compound',
                      'GivesInventory', 'InventoryToGive', 'NoticeWhenEnterZone',
                      'DestroyAfterUseTricked', 'KeepAfterUse', 'WrongTrick'):
                v = it.get(k)
                if v in (None, False, 0, '', []): continue
                bits.append('%s=%s' % (k, nm(v)))
            print('  %-18s zone=%-9s %s' % (nm(it.get('m_GameObject')),
                                            nm(it.get('Zone')), '  '.join(bits)))
            for k in ('NameString', 'DescriptionString'):
                if it.get(k): print('%22s %s=%s' % ('', k, it[k]))

    for t in ('Alerter', 'Woody', 'Rottweiler', 'ActionManager'):
        for p, o in by(t):
            print('\n-- %s --' % t.upper())
            for k, v in o.items():
                if v in (None, False, 0, '', []) or k.startswith('m_'): continue
                s = json.dumps(v, ensure_ascii=False)
                print('   %-30s %s' % (k, s[:100]))


if __name__ == '__main__':
    main(sys.argv[1])
