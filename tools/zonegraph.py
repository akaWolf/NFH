"""Rebuild the zone navigation graph statically from an exported level.

The graph is not serialized; ZoneController.Start() builds it at runtime. Its
rule, from the decompiled source:

    for each zone:
        for each Door in the zone's transform subtree:
            if (!door.Locked || door.TemporalLock) and door.LinkTo != null:
                neighbour = door.LinkTo.transform.parent.GetComponent<Zone>()
                zone.AddNeighbor(neighbour)

Every input that rule needs is in the serialized data, so the graph can be
reconstructed offline. Path costs are uniform (Helpers.GetShortestPath adds 1.0
per hop), so shortest paths are plain BFS.
"""
import json, sys, collections

# ZoneController uses GetComponentsInChildren<Door>(), which also matches Door's
# subclasses. Transition is the only one (see src/), and it is what Season 2 uses
# for almost all of its zone links — Season 2 levels have 116 Transitions and 8
# plain Doors.
DOOR_TYPES = ('Door', 'Transition')


class Level:
    def __init__(self, path):
        self.objs = json.load(open(path))['objects']
        self.meta = json.load(open(path))
        self.tr_of_go = {}        # gameObject path -> transform path
        self.comps_of_go = collections.defaultdict(list)
        for pid, o in self.objs.items():
            d = o.get('data')
            if d is None:
                continue
            if o['type'] == 'GameObject':
                for c in d['components']:
                    self.comps_of_go[int(pid)].append((c['type'], c['path']))
                    if c['type'] == 'Transform':
                        self.tr_of_go[int(pid)] = c['path']

    def obj(self, pid):
        return self.objs.get(str(pid))

    def go_of(self, pid):
        """the GameObject a component hangs on"""
        o = self.obj(pid)
        if not o or 'data' not in o:
            return None
        d = o['data']
        g = d.get('gameObject')
        if g is None:
            g = (d.get('m_GameObject') or {}).get('path')
        return g

    def component(self, go, type_name):
        wanted = DOOR_TYPES if type_name == 'Door' else (type_name,)
        for t, p in self.comps_of_go.get(go, []):
            if t in wanted:
                return p
        return None

    def subtree(self, go):
        """GameObject ids in the transform subtree rooted at go, self included"""
        out, stack = [], [go]
        while stack:
            cur = stack.pop()
            out.append(cur)
            tr = self.tr_of_go.get(cur)
            if tr is None:
                continue
            for child_tr in (self.obj(tr)['data']['children'] or []):
                cgo = self.obj(child_tr)['data'].get('gameObject')
                if cgo is None:
                    cgo = self.go_of(child_tr)
                if cgo is not None:
                    stack.append(cgo)
        return out

    def parent_go(self, go):
        tr = self.tr_of_go.get(go)
        if tr is None:
            return None
        father = self.obj(tr)['data'].get('father')
        if not father:
            return None
        return self.obj(father)['data'].get('gameObject')

    def name(self, go):
        o = self.obj(go)
        return o['data']['name'] if o and o['type'] == 'GameObject' else '#%s' % go

    def zone_graph(self):
        zones = [int(p) for p, o in self.objs.items() if o['type'] == 'Zone']
        edges = collections.defaultdict(list)
        for z in zones:
            zgo = self.go_of(z)
            for go in self.subtree(zgo):
                dp = self.component(go, 'Door')
                if dp is None:
                    continue
                door = self.obj(dp)['data']
                if door.get('Locked') and not door.get('TemporalLock'):
                    continue
                link = door.get('LinkTo')
                if not link:
                    continue
                target_go = self.go_of(link['path'])
                pgo = self.parent_go(target_go)
                if pgo is None:
                    continue
                nz = self.component(pgo, 'Zone')
                if nz is not None:
                    edges[zgo].append((self.name(pgo), self.name(go), door.get('DoorType')))
        return zones, edges


def main(path):
    lv = Level(path)
    zones, edges = lv.zone_graph()
    print('### %s — %d zones' % (lv.meta.get('unity_scene') or path, len(zones)))
    names = {}
    for z in zones:
        names[lv.go_of(z)] = lv.name(lv.go_of(z))
    for zgo in sorted(names, key=lambda g: names[g]):
        out = edges.get(zgo, [])
        seen = sorted(set(t for t, _, _ in out))
        print('  %-9s -> %s' % (names[zgo], ', '.join(seen) if seen else '(dead end)'))
        for target, door, dtype in sorted(out):
            print('%14svia %-17s %s' % ('', door, dtype))
    # connectivity check via BFS, mirroring Helpers.GetShortestPath (uniform cost)
    adj = {g: set(t for t, _, _ in edges.get(g, [])) for g in names}
    byname = {names[g]: g for g in names}
    start = sorted(names.values())[0]
    seen, q = {start}, collections.deque([start])
    while q:
        cur = q.popleft()
        for nb in adj.get(byname.get(cur, -1), ()):
            if nb not in seen:
                seen.add(nb); q.append(nb)
    print('\n  reachable from %s: %d / %d zones%s' % (
        start, len(seen), len(names),
        '' if len(seen) == len(names) else '  UNREACHABLE: %s' % (set(names.values()) - seen)))


if __name__ == '__main__':
    main(sys.argv[1])
