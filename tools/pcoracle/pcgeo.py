"""The port's level geometry for the oracle's plan runner, shared by pcmap.py and pcmap_s1.py: the level loaded
by the port's own loader (runtime/scene.py Level) with the PC overlay applied (runtime/pcprofile.py), so a
plan's mobile coordinates land where the port lands them — a `walk x y` on its zone's PC room, a floor trick's
`x=` on the room's floor line (runtime/world.py pc_room_x: the zone's walking limits against the room's
x1-x2), the zone's Ground item's own spot when the leg names none (tests/run_tricks.py _floor_x). Also the
PC inventory name a mobile type stands for in a combination (combine.xml's ingredient of the object's family
that is no object: Level103's IT_Wcpaper is level_mail's `toiletpaper`)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'runtime'))
import scene, pcprofile


class Geo:
    def __init__(self, n):
        self.s1 = n < 200
        self.level = scene.Level(os.path.join(ROOT, 'levels', 's1' if self.s1 else 's2', 'Level%d.json' % n))
        pcprofile.apply_overlay(self.level)

    def zone(self, name):
        return next((z for z in self.level.zones if z.name == name), None)

    def pc_room(self, z):
        """the zone's PC room record: PCWalkRoom (Season 1: room, x1, x2, floor) or PCRoom (Season 2)"""
        return z.pc_walk_room if self.s1 else z.pc_room

    def pc_x(self, z, x):
        """runtime/world.py pc_room_x: a mobile x of the zone on its PC room's floor line"""
        pr = self.pc_room(z)
        if not pr: return None, None
        w = (z.right - z.left) or 1.0
        return pr['room'], pr['x1'] + (x - z.left) * (pr['x2'] - pr['x1']) / w

    def zone_at(self, x, y):
        """the zone of a world point: the collider box that holds it, else the zone whose walking limits hold
        the x with the nearest floor"""
        box = [z for z in self.level.zones if abs(x - z.x) <= z.w * 0.5 and abs(y - z.y) <= z.h * 0.5]
        if box: return min(box, key=lambda z: abs(z.y - y))
        cands = [z for z in self.level.zones if z.left - 0.05 <= x <= z.right + 0.05]
        return min(cands, key=lambda z: abs(z.y - y)) if cands else None

    def room_graph(self):
        """the PC rooms' adjacency from the port's doors (a door's zone and its linked door's zone)"""
        if hasattr(self, '_graph'): return self._graph
        def room(zpid):
            z = self.level.zone_by_pid(zpid) if zpid is not None else None
            pr = self.pc_room(z) if z is not None else None
            return pr['room'] if pr else None
        doors = self.level.doors; doors = list(doors.values()) if isinstance(doors, dict) else list(doors)
        by_pid = {d.pid: d for d in doors}; g = {}
        for d in doors:
            o = by_pid.get(getattr(d, 'link_to', None))
            if o is None: continue
            a, b = room(d.zone), room(o.zone)
            if a and b and a != b: g.setdefault(a, set()).add(b); g.setdefault(b, set()).add(a)
        self._graph = g; return g

    def route(self, src, dst):
        """the rooms Woody crosses from src to dst (a breadth-first walk of the port's door graph — the PC's
        own path finder may take another way, 204's stairs), src excluded, dst included; [dst] when unknown"""
        if not dst: return []
        if not src or src == dst: return [dst]
        g = self.room_graph(); prev = {src: None}; q = [src]
        while q:
            r = q.pop(0)
            if r == dst: break
            for n in sorted(g.get(r, ())):
                if n not in prev: prev[n] = r; q.append(n)
        if dst not in prev: return [dst]
        path = []; r = dst
        while r != src: path.append(r); r = prev[r]
        return path[::-1]

    def floor_item_x(self, name, zone_name):
        """the mobile x of a zone's floor item (`Ground@Zone`): the item's spot, tests/run_tricks.py _floor_x"""
        for it in self.level.items.values():
            z = self.level.zone_by_pid(it.zone) if it.zone is not None else None
            if it.name == name and z is not None and z.name == zone_name:
                return it.x + (getattr(it, 'dx', 0.0) or 0.0)
        return None


class MapOps:
    """the plan runner's geometry and naming on a PCMap (needs geo, combos, objs, pc_item)"""
    def walk_point(self, x, y):
        """`walk x y`: the PC room and x of the world point"""
        z = self.geo.zone_at(x, y)
        if z is None: return None, None
        return self.geo.pc_x(z, x)

    def floor_target(self, zone, mx, it_type):
        """a floor trick (`usewith Ground@Zone IT_X [x=]`): the zone's PC room, the drop's x on its floor line
        (the leg's x=, else the zone's Ground item's spot) and the item's PC name — the combination of the
        room object with the item (level_mail's toi/groundsoap <- toi + soap); the result object last"""
        z = self.geo.zone(zone)
        if z is None: return None, None, None, None
        if mx is None: mx = self.geo.floor_item_x('Ground', zone)
        if mx is None: return None, None, None, None
        room, px = self.geo.pc_x(z, mx)
        if room is None: return None, None, None, None
        self.floor_y = (self.geo.pc_room(z) or {}).get('floor', 0)       # the room's path line (NFH1: y 420)
        want = self.pc_item(it_type); cands = []; result = None
        for name, ings, game in self.combos:
            if room in ings:
                items = [i for i in ings if '/' not in i and i != room]
                cands += items
                if want in items: result = name
        item = want if want in cands else (cands[0] if len(set(cands)) == 1 else want)
        if result is None:
            result = next((name for name, ings, game in self.combos if room in ings and item in ings), None)
        return room, px, item, result

    def single_combo(self, obj):
        """the object is the sole ingredient of a combination (no tool, no game): the GUI's click on it is a
        CombineMsg with a NULL second object, as for a tool-less unlock — 101's lir/tv (lir/twistedantenna)"""
        if obj is None: return False
        fam = obj.split('/')[-1].split('_')[0]; room = obj.split('/')[0]
        for name, ings, game in self.combos:
            if len(ings) == 1 and '/' in ings[0] and ings[0].split('/')[0] == room and ings[0].split('/')[-1].split('_')[0] == fam:
                return True
        return False

    def item_name(self, mobile_item, it_type):
        """the PC inventory name of a mobile type for a combination on the item: combine.xml's ingredient of
        the object's family that is no object — the type's own lower-cased name where it is one, the single
        candidate else, the one sharing the name else, the type's name as a last resort"""
        want = self.pc_item(it_type)
        # the type's own name where any combination takes it (209's pants on the hot coal: the coal family's
        # other combination, the air pump's, is no reason to rename the pants)
        if any(want in ings for name, ings, game in self.combos): return want
        # a type no combination knows by that name: the PC content of the object the mobile item giving the
        # type maps to (209's IT2_Flowers come from the Flowers item, whose PC object holds `gras`)
        giver = next((it for it, t in self.gives.items() if t == it_type), None)
        gobj = self.objs.get(giver) if giver else None
        if gobj:
            fam = self.family(gobj)
            held = [c for o, cs in getattr(self, 'contents', {}).items() if self.family(o) == fam for c in cs]
            if not held: held = [fam[1]]          # (a plain object taken whole: its base name is the item's — fire_fakir/gras)
            if len(set(held)) == 1 and any(held[0] in ings for name, ings, game in self.combos): return held[0]
        obj = self.objs.get(mobile_item)
        if obj is None: return want
        base = obj.split('/')[-1].split('_')[0]
        cands = []
        for name, ings, game in self.combos:
            if any('/' in i and i.split('/')[-1].split('_')[0] == base for i in ings):
                cands += [i for i in ings if '/' not in i]
        if want in cands: return want
        c = sorted(set(cands))
        if len(c) == 1: return c[0]
        near = [i for i in c if want in i or i in want]
        return near[0] if len(near) == 1 else want
