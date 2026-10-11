"""The mobile Season 1 plan vocabulary onto NFH1's objects, for the oracle (pcmap.py's Season 1 twin): the
item -> PC object (the item's name in the room its PCWalkPoint names, lower-cased — ALIASES where the PC
calls it otherwise), a combination's target from combine.xml, the neighbour's station objects, the zones'
PC rooms (PCWalkRoom), the inventory type names (IT_Egg -> egg). The PlanRunner of s1_oracle.py imports
this as `pcmap`."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref'))
import canon

ALIASES = {'Television': 'tv', 'Drawer': 'ark', 'FirstAid': 'firstaid', 'TV': 'tv'}


class PCMap:
    def __init__(self, n):
        self.n = n
        ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
        folder = canon.pc_level(n)['folder']
        X = os.path.expanduser('~/nfh-bench/pcref/pc/nfh1/x/%s' % folder)
        def rd(name):
            b = open(os.path.join(X, name), 'rb').read()
            return b.decode('utf-16') if b[:2] in (b'\xff\xfe', b'\xfe\xff') else b.decode('latin-1')
        objects_xml = rd('objects.xml')
        self.names = re.findall(r'<object name="([^"]+)"', objects_xml)
        self.uses = set()
        for m in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', objects_xml, re.S):
            if re.search(r'<action name="use" actor="woody"', m.group(2)): self.uses.add(m.group(1))
        self.combos = []
        try:
            for m in re.finditer(r'<combination name="([^"]+)"([^>]*)>(.*?)</combination>', rd('combine.xml'), re.S):
                if 'wrong="true"' in m.group(2): continue
                self.combos.append((m.group(1), re.findall(r'<ingredient name="([^"]+)"', m.group(3)),
                                    re.search(r'game="([^"]+)"', m.group(2))))
        except OSError:
            pass
        self.rooms = {}; walk = {}
        for e in ov['patches']:
            s = e.get('set') or {}
            if s.get('PCWalkRoom'):
                self.rooms[e['object']] = s['PCWalkRoom']
            if s.get('PCWalkPoint'):
                walk[e['object']] = s['PCWalkPoint']
        raw = json.load(open(os.path.join(ROOT, 'levels', 's1', 'Level%d.json' % n)))
        self.kinds = {}; self.gives = {}; items = []
        for o in raw['objects'].values():
            d = o.get('data') or {}
            name = (d.get('m_GameObject') or {}).get('name')
            if name and d.get('m_GameObject') and 'Item' in str(o.get('type')):
                self.kinds[name] = o['type']; items.append(name)
            for e in d.get('InventoryItems') or []:
                self.gives.setdefault(name, e['Type'])
        self.objs = {}; self.stations = {}
        by_base = {}
        for nm in self.names:
            if '/' in nm:
                room, base = nm.split('/', 1); by_base.setdefault(base, []).append(nm)
        for it in items:
            base = ALIASES.get(it, it.lower())
            cands = by_base.get(base, [])
            wp = walk.get(it) or {}
            def room_of(v):
                # a walk point: [x, y, room], or one per visit [[x, y, room], ...]
                if isinstance(v, list) and v and isinstance(v[0], list): v = v[0]
                return v[2] if isinstance(v, list) and len(v) >= 3 else None
            room = room_of(wp.get('Woody'))
            pick = next((c for c in cands if room is None or c.split('/')[0] == room), cands[0] if cands else None)
            if pick: self.objs[it] = pick
            if pick and room_of(wp.get('Rottweiler')): self.stations[it] = pick
        self.unmapped = [it for it in items if it not in self.objs]

    @staticmethod
    def family(name):
        room, _, base = name.rpartition('/')
        return room, base.split('_')[0]

    def station(self, mobile_item):
        return self.stations.get(mobile_item) or self.objs.get(mobile_item)

    @staticmethod
    def pc_item(it):
        """IT_Fartbag -> fartbag"""
        return it.split('_', 1)[1].lower()

    def combine_target(self, mobile_item, item):
        obj = self.objs.get(mobile_item)
        if obj is None: return None, None
        base = obj.split('/')[-1].split('_')[0]
        for name, ings, game in self.combos:
            if item in ings:
                objs = [i for i in ings if '/' in i and i.split('/')[-1].split('_')[0] == base]
                if objs: return objs[0], (game.group(1) if game else None)
        return obj, None

    def use_target(self, mobile_item):
        obj = self.objs.get(mobile_item)
        if obj is None: return None
        if self.kinds.get(mobile_item) != 'SearchItem':
            base = obj.split('/')[-1].split('_')[0]
            cands = sorted(u for u in self.uses if u.split('/')[-1].split('_')[0] == base and u.split('/')[0] == obj.split('/')[0])
            if cands: return cands[0]
        return obj

    def room_of_zone(self, zone):
        return (self.rooms.get(zone) or {}).get('room')

    def zone_center(self, zone):
        pr = self.rooms.get(zone)
        if not pr: return None, None
        return pr['room'], (pr['x1'] + pr['x2']) // 2


if __name__ == '__main__':
    for n in [int(a) for a in sys.argv[1:]] or range(101, 115):
        m = PCMap(n)
        print(n, m.objs, 'stations', m.stations, 'unmapped', m.unmapped, 'rooms', list(m.rooms))
