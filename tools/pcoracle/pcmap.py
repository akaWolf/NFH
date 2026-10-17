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
        # the rooms a pet watches (the mobile's Alerter items' zones): the port's auto-sneak tiptoes there
        self.alerter_rooms = set()
        for it in self.geo.level.items.values():
            z = self.geo.level.zone_by_pid(it.zone) if it.kind == 'Alerter' and it.zone is not None else None
            pr = self.geo.pc_room(z) if z is not None else None
            if pr: self.alerter_rooms.add(pr['room'])
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
        self.uses = set(); self.hideouts = {}
        try:
            self.placed = set(re.findall(r'<object [^>]*name="([^"]+)"', rd('level.xml')))   # placed at the start
        except OSError:
            self.placed = set()
        for m in re.finditer(r'<object name="([^"]+)"[^>]*>(.*?)</object>', rd('objects.xml'), re.S):
            if re.search(r'<action name="use" actor="woody"', m.group(2)): self.uses.add(m.group(1))
            h = re.search(r'<flag name="(neighbor_hideout|hideout)"', m.group(2))
            if h: self.hideouts[m.group(1)] = h.group(1)        # (the PC's flag 4: the enter step sets it, the leave clears)
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

    def placed_variant(self, obj, variant=None):
        """the object of the family that is in the scene: the variant a combination left there (the runner's
        record), else the one level.xml places at the start when the named one is not placed (113's ValveMain
        is the alias valve_off, the level starts with bas/valve_on — a message on the unplaced one crashed)"""
        if obj is None: return None
        if variant is not None: return variant
        if obj in self.placed or not self.placed: return obj
        fam = self.family(obj)
        same = [o for o in self.placed if '/' in o and self.family(o) == fam]
        return same[0] if len(same) == 1 else obj

    def combine_result(self, obj, item):
        """the combination's own name — the object that stands in the family's place afterwards (213's
        tortilla + tequila -> bottomright/tortilla_tequila; the runner records it as the family's variant)"""
        for name, ings, game in self.combos:
            if obj in ings and item in ings and '/' in name: return name
        return None

    def combine_target(self, mobile_item, item, variant=None):
        if variant is not None and item is not None:
            # the family's current variant first (the object a previous combination left in its place)
            for name, ings, game in self.combos:
                if item in ings and variant in ings: return variant, (game.group(1) if game else None)
        return self._combine_target(mobile_item, item)

    def _combine_target(self, mobile_item, item):
        """the PC object `item` (a PC inventory name) is combined with: the combination whose ingredients
        are the item and an object of the mobile item's PC family — and the minigame it opens, if any.
        `item` None: a dexterity unlock without a tool (203's handbag, 205's duck cage) — the combination of
        the family with a `game` and a single object ingredient; its object is the one to use"""
        obj = self.objs.get(mobile_item) or self.stations.get(mobile_item)    # (209's cow: the neighbour's station, no Woody approach)
        if obj is None:
            # no PC object for the name: the held item's own partner, if it has one (208's IndianMagician
            # has no approach in the overlay — the balloon's combination names amusement/fakir)
            alt = [(name, ings, game) for name, ings, game in self.combos if item is not None and item in ings and len(ings) == 2]
            if len(alt) == 1:
                name, ings, game = alt[0]
                return next(i for i in ings if i != item), (game.group(1) if game else None)
            return None, None
        base = obj.split('/')[-1].split('_')[0]; found = []
        for name, ings, game in self.combos:
            objs = [i for i in ings if '/' in i and i.split('/')[-1].split('_')[0] == base]
            if item is None:
                if game and objs and all('/' in i for i in ings): return objs[0], game.group(1)
            elif item in ings and objs:
                found.append((objs[0], (game.group(1) if game else None)))
        if found:
            # the family's plain object first (a variant may not be placed yet — a combine on one crashes)
            found.sort(key=lambda f: (f[0] != obj, f[0] not in self.placed, len(f[0])))
            return found[0]
        # the family read loosely: an object whose base contains the plain name (209's coal_area/hot_coal
        # takes the pants; its family by the first word is `hot`)
        for name, ings, game in self.combos:
            if item in ings:
                objs = [i for i in ings if '/' in i and base in i.split('/')[-1]]
                if objs: return objs[0], (game.group(1) if game else None)
        # no combination on the item's family: the one the held item has with a single object, if it is
        # the only one (104's IT_Hairrestorer goes on toi/grease — the plan names the deodorant's spot)
        if item is not None:
            # (the other ingredient is the object, a room-less helper too: 107's dove is `aux` + scissors)
            alt = [(name, ings, game) for name, ings, game in self.combos if item in ings and len(ings) == 2]
            if len(alt) == 1:
                name, ings, game = alt[0]
                return next(i for i in ings if i != item), (game.group(1) if game else None)
        return obj, None

    def use_target(self, mobile_item):
        """a bare-hand click: a SearchItem's take on the overlay's object, a trick item's own `use`"""
        obj = self.objs.get(mobile_item) or self.stations.get(mobile_item)
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
