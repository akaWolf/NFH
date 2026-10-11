"""The mobile plan vocabulary onto the PC's objects, for the oracle: the item -> PC object map (the
overlay's PCApproach Woody `obj`), the combine target of an inventory item (combine.xml), a trick item's
bare-hand use target (objects.xml's own `use` of Woody's), the mobile zones' PC rooms, the inventory type
names (IT2_X -> x). Shared by port2script.py and oracle_plan.py."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pcref'))
import canon
sys.path.insert(0, HERE)
import pcgeo


class PCMap(pcgeo.MapOps):
    def __init__(self, n):
        self.n = n
        self.geo = pcgeo.Geo(n)           # the port's level: the zones' limits and PC rooms, the floor items
        ov = json.load(open(os.path.join(ROOT, 'levels', 'pc', 'Level%d.overlay.json' % n)))
        self.objs = {}; self.rooms = {}; self.stations = {}
        for e in ov['patches']:
            s = e.get('set') or {}
            ap = s.get('PCApproach')
            if ap and 'Woody' in ap and 'obj' in ap['Woody']:
                self.objs[e['object']] = ap['Woody']['obj']
            if ap and 'Rottweiler' in ap and 'obj' in ap['Rottweiler']:
                self.stations[e['object']] = ap['Rottweiler']['obj']       # the neighbour's station object
            if s.get('PCRoom'):
                self.rooms[e['object']] = s['PCRoom']
        folder = canon.pc_level(n)['folder']
        X = os.path.expanduser('~/nfh-bench/pcref/pc/%s/x/%s' % ('nfh1' if n < 200 else 'nfh2', folder))
        def rd(name):
            b = open(os.path.join(X, name), 'rb').read()
            return b.decode('utf-16') if b[:2] in (b'\xff\xfe', b'\xfe\xff') else b.decode('latin-1')
        self.combos = []
        for m in re.finditer(r'<combination name="([^"]+)"([^>]*)>(.*?)</combination>', rd('combine.xml'), re.S):
            if 'wrong="true"' in m.group(2): continue
            self.combos.append((m.group(1), re.findall(r'<ingredient name="([^"]+)"', m.group(3)),
                                re.search(r'game="([^"]+)"', m.group(2))))
        self.uses = set()
        for m in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', rd('objects.xml'), re.S):
            if re.search(r'<action name="use" actor="woody"', m.group(2)): self.uses.add(m.group(1))
        raw = json.load(open(os.path.join(ROOT, 'levels', 's1' if n < 200 else 's2', 'Level%d.json' % n)))
        self.kinds = {}; self.gives = {}
        for o in raw['objects'].values():
            d = o.get('data') or {}
            name = (d.get('m_GameObject') or {}).get('name')
            if name and d.get('m_GameObject') and ('Item' in str(o.get('type')) or o.get('type') in ('Rake',)):
                self.kinds[name] = o['type']
            for e in d.get('InventoryItems') or []:
                self.gives.setdefault(name, e['Type'])

    @staticmethod
    def family(name):
        """the room and the base of a PC object name: beachright/mat_hn_guarded -> (beachright, mat) — the
        guarded / container / ground variants of one station are one family"""
        room, _, base = name.rpartition('/')
        return room, base.split('_')[0]

    def station(self, mobile_item):
        """the PC object the neighbour's actions on the mobile item's station are logged on"""
        return self.stations.get(mobile_item) or self.objs.get(mobile_item)

    @staticmethod
    def pc_item(it):
        """IT2_Sandbucketeel -> sandbucketeel"""
        return it.split('_', 1)[1].lower()

    def combine_target(self, mobile_item, item):
        """the PC object `item` (a PC inventory name) is combined with: the combination whose ingredients
        are the item and an object of the mobile item's PC family — and the minigame it opens, if any.
        `item` None: a dexterity unlock without a tool (203's handbag, 205's duck cage) — the combination of
        the family with a `game` and a single object ingredient; its object is the one to use"""
        obj = self.objs.get(mobile_item)
        if obj is None: return None, None
        base = obj.split('/')[-1].split('_')[0]
        for name, ings, game in self.combos:
            objs = [i for i in ings if '/' in i and i.split('/')[-1].split('_')[0] == base]
            if item is None:
                if game and objs and all('/' in i for i in ings): return objs[0], game.group(1)
            elif item in ings and objs:
                return objs[0], (game.group(1) if game else None)
        return obj, None

    def use_target(self, mobile_item):
        """a bare-hand click: a SearchItem's take on the overlay's object, a trick item's own `use`"""
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
        """the PC room of a mobile zone and the middle of its floor line"""
        pr = self.rooms.get(zone)
        if not pr: return None, None
        return pr['room'], (pr['x1'] + pr['x2']) // 2
